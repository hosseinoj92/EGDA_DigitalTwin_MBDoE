"""
Reproducible Monte Carlo benchmark of strategies A-F on the EGDA/H2SO4
system.

FAIRNESS RULES:

  * every strategy in a scenario faces the SAME AdvancedVirtualLaboratory
    physics, differing only in what the controller/inference may assume;
  * baselines A-D run UNCHANGED sdl.campaign code through a thin adapter
    (their measurements have cov_y stripped -> legacy assumed-NoiseModel);
  * resources are metered identically from one event log; results are
    reportable per reactor condition AND per actual resource budget;
  * the same seed list is used for every strategy (common random numbers),
    so per-seed PAIRED differences are meaningful;
  * hidden truth is revealed only in post-campaign scoring.

Scenario map (see SCENARIOS):

  S1_ideal        correct model, ideal direct observation, no transport
  S2_nmr          synthetic 80 MHz spectra (WITH truth-model mismatch) +
                  deconvolution covariance
  S3_transport    + position delay, RTD, in-line reaction, carryover
  S3ab_*          transport ablation: which physical effect biases naive
                  inference (delay only / +RTD / +carryover)
  S4a_ambiguity   hard realistic model discrimination (3 candidates,
                  extended budget) - may honestly end undecided
  S4b_identifiable structurally identifiable discrimination (reversible vs
                  irreversible under strongly reversible truth): the
                  discriminating region exists and the learner must find it
  S5_inadequacy   correct model removed from the candidate family
  S6_resources    resource-aware design, lambda-sweep -> Pareto frontier

Modes: "smoke" (seconds), "demo" (default), "publication" (many seeds) -
see MODES; runners may override any entry.

PARALLELISM: the unit of work is ONE (scenario, strategy, seed) campaign,
which is a pure function of those three labels plus the budget - see
`campaign_task`.  Passing an executor to `run_scenario` /
`governor_mc_validation` distributes those units over processes and
reassembles them in submission order, so the saved results are identical to
a one-core run at any worker count (sdl_advanced/parallel.py explains how
that identity is maintained).
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import (asdict as dataclasses_asdict,
                         dataclass, field, fields as dataclasses_fields,
                         is_dataclass as dataclasses_is_dataclass,
                         replace)
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from sdl import (Layer1Bridge, OperatingConditions, ParameterSpace,
                 NoiseModel, InferenceModel, MBDoESelector,
                 build_candidates, build_fixed_design, literature_guess,
                 run_strategy, param_keys_for, screen, reference_design)
from sdl.campaign import StrategyResult
from sdl.reporting import log_mean_rel_error_pct

from .adequacy import AdequacyGovernor, GovernorConfig, GovernorState
from .bayes_design import AdvancedDesignConfig
from .controller import (AdvancedStrategyResult, QCGateConfig,
                         run_strategy_e, run_strategy_f)
from .instrument import AdvancedVirtualLaboratory, InstrumentConfig
from .model_ensemble import (AssumedTransfer, ModelEnsemble,
                             build_egda_family)
from . import parallel as par
from .resources import ResourceCosts, ResourceMeter
from sdl.design_space import DesignResolution
from .spatial_design import SpatialDesignConfig, fixed_equal_positions
from .spectral import AcquisitionSettings, SpectralNuisance
from .spectral_fit import SpectralCovarianceModel, SpectralFitter
from .transfer import TransferConfig

# ------------------------------------------------------------------------- #
# Shared benchmark configuration
# ------------------------------------------------------------------------- #
# PROPOSED demonstration CPR geometry (20 cm x 7 mm ID, open/unpacked).
# This is a documented hardware proposal, NOT an optimization result; every
# consumer reads it from here, so it stays configurable.  Set
# packing_enabled/bed_void_fraction to model an inert-packed CPR instead.
GEOMETRY = {"length_m": 0.20, "diameter_m": 0.007,
            "packing_enabled": False, "bed_void_fraction": 1.0}
T_REF_C = 60.0
TRUTH = {"k1_ref": 1.00e-3, "Ea1_J": 40_000.0,          # hidden truth
         "k2_ref": 6.50e-4, "Ea2_J": 48_000.0,
         "K1_ref": 0.90, "K2_ref": 0.07}
SPECIES = ("EGDA", "EGMA", "EG", "AcOH")
N_PORTS = 10

DESIGN = {
    "T_C_levels": [40, 60, 80, 100, 120, 140, 160],
    "Q_total_mL_min_levels": [0.5, 2.0, 8.0],
    "C_cat_M_levels": [0.5, 1.0],
    "C_EGDA_M_levels": [1.0],
    "C_EGDA_M": 1.0,
    "fixed_design_T_C": [40, 60, 80, 100, 120, 140, 160],
    "nominal_Q_total_mL_min": 1.0,
    "nominal_C_cat_M": 0.5,
    "continuous_bounds": {"T_C": [40.0, 160.0],
                          "Q_total_mL_min": [0.5, 8.0],
                          "C_cat_M": [0.5, 1.0],
                          "C_EGDA_M": [1.0, 1.0]},
}

# ------------------------------------------------------------------------- #
# DESIGN SPACE MODE: discrete grid (classical) or continuous within bounds
# ------------------------------------------------------------------------- #
# A real platform sets a thermostat, not a grid corner.  With
# `continuous=True` the design optimizer may propose ANY point inside
# `DESIGN["continuous_bounds"]`, snapped to the resolution the hardware can
# actually command.  It is OFF by default so an unchanged configuration
# reproduces the published discrete benchmark exactly.
#
# The refinement is accepted only when it strictly beats the best grid point
# on the same criterion (sdl/design_space.py), so continuous mode cannot be
# worse than discrete mode by that criterion - it is a superset of the
# search, not a replacement for it.
DESIGN_SPACE = {
    "continuous": False,
    # smallest commandable change per variable; a real instrument limit,
    # not a modelling choice
    "resolution": {"T_C": 0.1,            # deg C
                   "Q_total_mL_min": 0.1,  # mL/min
                   "C_cat_M": 1.0e-4,      # 0.1 mM
                   "C_EGDA_M": 1.0e-4},    # 0.1 mM
    "continuous_maxiter": 40,   # Powell iterations per refinement
    "continuous_restarts": 2,   # extra random starts (advanced selector only)
}


# ------------------------------------------------------------------------- #
# CONTROLLER / INSTRUMENT KNOBS
# ------------------------------------------------------------------------- #
# Previously constructed inline inside run_one_campaign, which meant a runner
# could not change them without editing this file.  They live here so
# `apply_config` (and therefore the runner's CONFIG) can reach every one.
GOVERNOR = {
    "alpha_campaign": 0.05,          # campaign-level false-alarm target
    "discrimination_prob": 0.90,     # below this -> discriminate models
    "qc_fail_fraction": 0.25,        # assimilated FAIL fraction -> fault state
    "chi2_dof_ratio_override": 25.0,  # gross-misfit emergency trip
    # MEASUREMENT-SYSTEMATIC ALLOWANCE kappa.  DERIVED FROM WELL-SPECIFIED
    # CONTROL DATA, never from kinetic-benchmark performance:
    # validation.derive_systematic_allowance() measures the standardized
    # residual z of the CALIBRATED NMR pathway on an independent control
    # stream and returns kappa = sqrt(rms(z)^2 - 1).  With the shared
    # calibration artifact rms(z) = 1.11 and a bounded residual BIAS survives
    # in the overlapped resonances (z-mean EGMA -0.72, AcOH -0.52), hence
    # kappa = 0.47 (down from 1.25 when the governor was compensating for a
    # broken Sigma_y).  Re-derive whenever the NMR calibration changes.
    # SEE: tests/test_calibration_governor.py::test_allowance_is_derived...
    "systematic_allowance_nmr": 0.47,
    # direct observation: Sigma is exact by construction -> exact nulls
    "systematic_allowance_direct": 0.0,
}

QC_GATE = {
    "enabled_for_nmr": True,     # QC gate active whenever observation is NMR
    "max_retries": 1,            # reacquisitions per failing position
    "max_reject_fraction": 0.5,  # above this per round -> pause the campaign
}

ADVANCED_DESIGN = {
    "top_k": 3,                  # candidates surviving the FIM screen
    "n_particles": 16,           # posterior particles per EIG estimate
    "n_outer": 24,               # outer MC samples per EIG estimate
    "alpha_param": 1.0,          # weight on parameter EIG
    "beta_model": 1.0,           # weight on model-discrimination EIG
    "beta_model_discrimination": 4.0,   # boost while discriminating
}

SPATIAL = {
    "candidate_grid_size": 41,
    "z_min_fraction": 0.02,
    "z_max_fraction": 1.0,
    "min_spacing_fraction": 0.02,
    "continuous_refinement": False,
    "marginal_information_threshold": None,   # None -> SpatialDesignConfig default
}


# ------------------------------------------------------------------------- #
# One entry point for a runner to set EVERY knob above
# ------------------------------------------------------------------------- #
#: name -> the module-level object a runner may override.  Dicts are updated
#: key by key; frozen dataclasses are rebuilt with dataclasses.replace.
_OVERRIDABLE = ("GEOMETRY", "GEOMETRY_DESIGN", "COMPARISON",
                "TRUTH", "DESIGN", "DESIGN_SPACE", "GOVERNOR",
                "QC_GATE", "ADVANCED_DESIGN", "SPATIAL", "TRANSFER_TRUE",
                "NMR_NUISANCE_TRUE", "ACQ", "NOISE_DIRECT", "RESOURCE_COSTS",
                "T_REF_C", "N_PORTS")


def apply_config(overrides: Optional[Dict]) -> Dict:
    """Apply a runner's CONFIG knobs to this module's configuration blocks.

    The runner's CONFIG is the authority for a run; the constants above are
    library defaults for tests and direct API use.  Applying them here -
    rather than duplicating values in the runner - is what keeps the two
    from drifting apart.

    STRICT BY DESIGN: an unknown block or field raises instead of being
    ignored, because a silently-dropped knob is indistinguishable from a
    knob that had no effect, and that is exactly the failure mode that
    wastes a nine-hour run.  Returns the resolved state for the
    reproducibility record.

    NOTE for parallel runs: worker processes re-import this module and get
    the DEFAULTS, so a runner that overrides anything must pass the same
    overrides to the pool initializer (`worker_init`).  run_advanced_benchmark
    does this; a custom driver must too.
    """
    if not overrides:
        return resolved_config()
    for name, value in overrides.items():
        if name not in _OVERRIDABLE:
            raise KeyError(
                f"Unknown configuration block '{name}'. Overridable blocks: "
                + ", ".join(_OVERRIDABLE))
        current = globals()[name]
        if isinstance(current, dict):
            unknown = [k for k in value if k not in current]
            if unknown:
                raise KeyError(f"{name}: unknown field(s) {unknown}. "
                               f"Known: {sorted(current)}")
            if name == "DESIGN_SPACE" and "resolution" in value:
                res_unknown = [k for k in value["resolution"]
                               if k not in current["resolution"]]
                if res_unknown:
                    raise KeyError(f"DESIGN_SPACE.resolution: unknown field(s) "
                                   f"{res_unknown}")
                current["resolution"].update(value["resolution"])
                value = {k: v for k, v in value.items() if k != "resolution"}
            current.update(value)
        elif dataclasses_is_dataclass(current):
            fields = {f.name for f in dataclasses_fields(current)}
            unknown = [k for k in value if k not in fields]
            if unknown:
                raise KeyError(f"{name}: unknown field(s) {unknown}. "
                               f"Known: {sorted(fields)}")
            globals()[name] = replace(current, **value)
        else:                                   # plain scalar (T_REF_C, ...)
            globals()[name] = value
    return resolved_config()


def resolved_config() -> Dict:
    """Every knob's CURRENT value - what the run actually used."""
    out = {}
    for name in _OVERRIDABLE:
        v = globals()[name]
        if isinstance(v, dict):
            out[name] = {k: (dict(x) if isinstance(x, dict) else x)
                         for k, x in v.items()}
        elif dataclasses_is_dataclass(v):
            out[name] = dataclasses_asdict(v)
        else:
            out[name] = v
    return out


# ------------------------------------------------------------------------- #
# REACTOR GEOMETRY AS A DESIGN VARIABLE (optional)
# ------------------------------------------------------------------------- #
# Two different questions the framework can answer:
#
#   enabled=False  "I HAVE this reactor - what experiments should I run in
#                   it?"  GEOMETRY is a fixed constant.  (Default: this is
#                   the question the published benchmark answers.)
#   enabled=True   "I am going to BUILD a reactor for this chemistry - what
#                   geometry, and what experiments?"  Length and diameter
#                   join the design vector.
#
# `mode` matters physically and is not a detail:
#
#   "per_campaign"    ONE geometry is chosen and then every experiment runs
#                     in it.  This is what designing a reactor means, and it
#                     is the default.  The choice is made once, from the
#                     prior, before the first experiment.
#   "per_experiment"  the geometry may change between rounds - only
#                     meaningful for a modular/rack setup, and expensive:
#                     `switch_cost_s` is charged whenever it changes, since
#                     swapping a reactor is not free the way changing a
#                     setpoint is.
GEOMETRY_DESIGN = {
    "enabled": False,
    "mode": "per_campaign",          # "per_campaign" | "per_experiment"
    "bounds": {"length_m": [0.05, 0.60],
               "diameter_m": [0.002, 0.012]},
    # discrete levels used when DESIGN_SPACE["continuous"] is False
    "levels": {"length_m": [0.10, 0.20, 0.40, 0.60],
               "diameter_m": [0.004, 0.007, 0.010]},
    # commandable resolution: you cannot order a tube to the micron
    "resolution": {"length_m": 0.005,      # 5 mm
                   "diameter_m": 0.0005},  # 0.5 mm
    "switch_cost_s": 1800.0,         # per geometry change (per_experiment)

    # ---- ideality: open tube vs packed bed ------------------------------ #
    # The kinetics are intrinsic - geometry never changes the constants -
    # but it DOES change whether the plug-flow model is valid.  In an open
    # laminar tube the validity metric is the radial-mixing ratio
    #     t_rad / tau = (R^2/D) / (eps V/Q) = Q / (pi D L eps)
    # (Layer 1's own diagnostic; note the BORE CANCELS - only length, flow
    # and holdup help).  Candidates whose ratio exceeds `max_radial_ratio`
    # at the reference design's nominal flow are INFEASIBLE: an optimizer
    # must not select a reactor in which the model it is fitting does not
    # apply.  The default 10.0 is Layer 1's published advisory boundary
    # between "moderate deviation" and "radially segregated streamlines"
    # (pfr_twin/diagnostics.py), not a number invented here.
    #
    # `packing` is the engineering fix: random-packed spherical beads
    # (eps ~ 0.4) break up the laminar streamlines, so a packed candidate
    # is treated as plug-flow valid.  ASSUMPTION (CAL): beads chosen with
    # d_p <= d/10 and L/d_p >= 100, the standard packed-bed plug-flow
    # criteria; bed RTD itself is not simulated (future work).  Packing
    # costs holdup: tau_liquid = eps V/Q, so a packed reactor needs ~2.5x
    # the volume for the same residence time - the optimizer sees that
    # automatically through Layer 1.
    #   "auto"  consider every geometry both open and packed, pick the best
    #   True    all candidates packed;  False  open tubes only (may make
    #           every candidate infeasible -> raises with guidance)
    "packing": "auto",
    "bed_void_fraction": 0.40,       # random-packed spheres
    "max_radial_ratio": 10.0,        # open-tube feasibility threshold

    # ---- information-resource exchange rate for the sizing objective ---- #
    #     score = logdet F(reference design)  -  sum_r lambda_r * resource_r
    # where the resources are what the reference campaign would consume in
    # that reactor (stabilization scales with liquid volume, so this is
    # what stops "bigger is always better").  The weights are THE SAME 1x
    # vector the S6 resource-aware controller uses - one exchange rate for
    # the whole framework, swept in S6 precisely so no single value is
    # presented as universal.  All zeros recovers pure information.
    "objective_lambdas": {"lambda_time_per_s": 2e-3,
                          "lambda_material_per_mol": 50.0,
                          "lambda_waste_per_mL": 5e-3,
                          "lambda_energy_per_kJ": 0.05},
}


# ------------------------------------------------------------------------- #
# CONVENTIONAL-VS-OPTIMIZED COMPARISON
# ------------------------------------------------------------------------- #
# Which strategy plays "the conventional method" in each scenario - the
# thing the methodology has to beat.  A is the classical temperature ladder
# at nominal flow read out at the outlet; where a scenario has no A (the
# transport and resource scenarios start at D) the naive spatial MBDoE is
# the incumbent.
COMPARISON = {
    "reference_strategy": {"S1_ideal": "A", "S2_nmr": "B",
                           "S4b_identifiable": "D", "S4a_ambiguity": "D",
                           "S3_transport": "D", "S3ab_delay": "D",
                           "S3ab_rtd": "D", "S5_inadequacy": "D",
                           "S6_resources": "D", "S7_spatial_modes": "F-zfixed",
                           "S4c_out_of_domain": "F"},
    "default_reference": "A",
    # accuracy ladders for the budget-to-target analysis.  Deliberately
    # spanning loose to tight: a target every method reaches says nothing,
    # and one nobody reaches says nothing either.
    "targets": {"param_err_pct": [50.0, 30.0, 20.0, 10.0, 5.0],
                "blind_rmse_M": [1.0e-2, 5.0e-3, 2.0e-3, 1.0e-3]},
    # seed whose decision trajectory is drawn for the "what did it do"
    # figure; fixed so the figure is reproducible
    "trajectory_seed": 1,
}


#: pre-campaign geometry choices, cached per budget (a pure function of the
#: configuration, so a worker process re-derives the same answer)
_GEOMETRY_CACHE: Dict[Tuple, Dict] = {}


def _geometry_candidates() -> List[Dict]:
    """Discrete geometry grid x packing state, from the declared levels.

    `packing="auto"` doubles the grid (every size open AND packed) and lets
    the objective decide; True/False pin the state.  A packed candidate
    carries eps = bed_void_fraction, which Layer 1 turns into interstitial
    velocity and reduced liquid holdup - so its lower information per
    volume is priced in automatically, not assumed."""
    import itertools as _it
    lv = GEOMETRY_DESIGN["levels"]
    pk = GEOMETRY_DESIGN.get("packing", "auto")
    states = ((False, True) if pk == "auto" else
              ((True,) if pk else (False,)))
    eps = float(GEOMETRY_DESIGN.get("bed_void_fraction", 0.40))
    out = []
    for L, d in _it.product(lv["length_m"], lv["diameter_m"]):
        for packed in states:
            out.append({**GEOMETRY, "length_m": float(L),
                        "diameter_m": float(d),
                        "packing_enabled": bool(packed),
                        "bed_void_fraction": eps if packed else 1.0})
    return out


def _radial_ratio(geom: Dict) -> float:
    """Open-tube plug-flow validity ratio t_rad/tau = Q/(pi D L eps) at the
    reference design's nominal flow (Layer 1's diagnostic; the bore
    cancels).  Packed beds return 0.0: the beads break the laminar
    streamlines, which is the point of packing (assumptions documented in
    GEOMETRY_DESIGN)."""
    if geom.get("packing_enabled", False):
        return 0.0
    from pfr_twin.parameters import DIFFUSIVITY_LIQ
    q_m3s = float(DESIGN["nominal_Q_total_mL_min"]) * 1e-6 / 60.0
    return q_m3s / (np.pi * DIFFUSIVITY_LIQ * float(geom["length_m"]))


def _reference_campaign_cost(geom: Dict, budget: int) -> Dict[str, float]:
    """What the reference campaign would CONSUME in this reactor, replayed
    deterministically through the same ResourceMeter that meters real
    campaigns - one accounting, not a second model.  Stabilization scales
    with liquid volume, which is what stops 'bigger is always better'."""
    from pfr_twin.parameters import ReactorGeometry as _RG
    meter = ResourceMeter(RESOURCE_COSTS, _RG(**geom).liquid_volume_mL)
    z = fixed_equal_positions(float(geom["length_m"]), N_PORTS)
    for u in build_fixed_design(design_for_budget(budget), budget=budget):
        q = u.Q1_mL_min + u.Q2_mL_min
        meter.log_condition(u.T_C, q, u.C_EGDA_M, u.C_cat_M)
        for zk in z:
            meter.log_acquisition(float(zk), u.T_C, q, u.C_EGDA_M,
                                  u.C_cat_M)
    return meter.totals()


def _geometry_objective(geom: Dict, budget: int) -> Dict[str, float]:
    """score = information - resource penalty, with feasibility.

    Returns the decomposition so the sizing table can show WHY a reactor
    won, not just that it did."""
    lam = GEOMETRY_DESIGN["objective_lambdas"]
    ratio = _radial_ratio(geom)
    feasible = ratio <= float(GEOMETRY_DESIGN["max_radial_ratio"])
    info = _geometry_score(geom, budget) if feasible else float("nan")
    tot = _reference_campaign_cost(geom, budget) if feasible else {}
    penalty = (float(lam.get("lambda_time_per_s", 0.0)) * tot.get("time_s", 0.0)
               + float(lam.get("lambda_material_per_mol", 0.0))
               * tot.get("egda_mol", 0.0)
               + float(lam.get("lambda_waste_per_mL", 0.0))
               * tot.get("waste_mL", 0.0)
               + float(lam.get("lambda_energy_per_kJ", 0.0))
               * tot.get("energy_kJ", 0.0)) if feasible else float("nan")
    score = (info - penalty if feasible and np.isfinite(info)
             else float("-inf"))
    return {"score": score, "info_nats": info, "cost_penalty_nats": penalty,
            "radial_ratio": ratio, "feasible": float(feasible),
            "time_s": tot.get("time_s", float("nan")),
            "egda_mol": tot.get("egda_mol", float("nan")),
            "energy_kJ": tot.get("energy_kJ", float("nan"))}


def _geometry_score(geom: Dict, budget: int) -> float:
    """D-optimal information of a REFERENCE design in this reactor, under
    the PRIOR (literature) parameters.

    Firewall-clean: it reads `literature_guess`, never the hidden truth -
    sizing a reactor is something you do BEFORE you know the kinetics, and
    letting the truth in here would be the purest form of inverse crime.

    The reference design is the declared conventional ladder at nominal
    flow, sampled at equally spaced positions - i.e. "what would a
    standard campaign in this reactor tell me?"."""
    t_ref_K = T_REF_C + 273.15
    try:
        bridge = Layer1Bridge(geom, t_ref_K, activity_model="pitzer")
        space = ParameterSpace(t_ref_K=t_ref_K,
                               initial_guess=dict(literature_guess(t_ref_K)))
        inf = InferenceModel(space, bridge, NOISE_DIRECT)
        z = fixed_equal_positions(geom["length_m"], N_PORTS)
        F = np.zeros((space.n_params,) * 2)
        for u in build_fixed_design(design_for_budget(budget), budget=budget):
            F = F + inf.candidate_information(u, z, SPECIES)
        sign, logdet = np.linalg.slogdet(
            F + 1e-12 * np.eye(space.n_params))
        return float(logdet) if sign > 0 else float("-inf")
    except (ValueError, RuntimeError, FloatingPointError,
            np.linalg.LinAlgError):
        return float("-inf")


def optimal_geometry(budget: int) -> Dict:
    """Pre-campaign reactor sizing under the combined objective
    (information - resource penalty, plug-flow feasibility enforced).

    Discrete mode screens levels x packing states; continuous mode then
    refines (L, d) inside `bounds` WITHIN the winning packing state,
    snapped to what a tube can be ordered to (5 mm length, 0.5 mm bore) and
    accepted only when it strictly beats the grid winner - the same
    never-worse rule as the operating-condition design.

    Deterministic in (budget, configuration): every worker process
    re-derives the same reactor."""
    if GEOMETRY_DESIGN["mode"] != "per_campaign":
        raise NotImplementedError(
            "GEOMETRY_DESIGN['mode'] = 'per_experiment' is declared but not "
            "implemented: changing the reactor between rounds needs a "
            "swap-cost model in ResourceMeter and a per-round geometry in "
            "the truth-side laboratory.  Use 'per_campaign' (choose the "
            "reactor once, then run the campaign in it), which is what "
            "'design a reactor for this chemistry' means.")
    key = (int(budget), tuple(sorted(GEOMETRY.items())),
           tuple(sorted((k, tuple(v)) for k, v in
                        GEOMETRY_DESIGN["bounds"].items())),
           tuple(sorted((k, tuple(v)) for k, v in
                        GEOMETRY_DESIGN["levels"].items())),
           str(GEOMETRY_DESIGN.get("packing", "auto")),
           float(GEOMETRY_DESIGN.get("max_radial_ratio", 10.0)),
           tuple(sorted(GEOMETRY_DESIGN["objective_lambdas"].items())),
           bool(DESIGN_SPACE["continuous"]))
    if key in _GEOMETRY_CACHE:
        return _GEOMETRY_CACHE[key]

    cands = _geometry_candidates()
    table = []
    for g in cands:
        obj = _geometry_objective(g, budget)
        table.append((g, obj))
    feasible = [(g, o) for g, o in table if np.isfinite(o["score"])]
    if not feasible:
        best_ratio = min(o["radial_ratio"] for _g, o in table)
        raise ValueError(
            "Reactor sizing found NO feasible geometry: every open tube in "
            f"the declared space has t_rad/tau > "
            f"{GEOMETRY_DESIGN['max_radial_ratio']:g} at the nominal flow "
            f"(best was {best_ratio:.1f}; note the ratio = Q/(pi D L eps) - "
            "the bore cancels, only length and holdup help).  Either allow "
            "packed beds (GEOMETRY_DESIGN['packing'] = 'auto'), lengthen "
            "the bounds, or explicitly accept non-ideality by raising "
            "GEOMETRY_DESIGN['max_radial_ratio'].")
    best, best_obj = max(feasible, key=lambda t: t[1]["score"])

    if DESIGN_SPACE["continuous"]:
        from scipy.optimize import minimize as _minimize
        b = GEOMETRY_DESIGN["bounds"]
        res = GEOMETRY_DESIGN["resolution"]
        lo = [float(b["length_m"][0]), float(b["diameter_m"][0])]
        hi = [float(b["length_m"][1]), float(b["diameter_m"][1])]
        state = {k: best[k] for k in ("packing_enabled",
                                      "bed_void_fraction")}

        def _snap(x):
            out = []
            for v, step, l, h in zip(x, (res["length_m"], res["diameter_m"]),
                                     lo, hi):
                v = round(float(v) / step) * step if step > 0 else float(v)
                out.append(min(max(v, l), h))
            return out

        def _neg(x):
            L, d = _snap(x)
            sc = _geometry_objective({**GEOMETRY, **state, "length_m": L,
                                      "diameter_m": d}, budget)["score"]
            return -sc if np.isfinite(sc) else 1e100

        try:
            sol = _minimize(_neg, [best["length_m"], best["diameter_m"]],
                            method="Powell", bounds=list(zip(lo, hi)),
                            options={"maxiter": 30, "xtol": 1e-3,
                                     "ftol": 1e-6})
            L, d = _snap(np.atleast_1d(sol.x))
            cand = {**GEOMETRY, **state, "length_m": L, "diameter_m": d}
            cand_obj = _geometry_objective(cand, budget)
            if cand_obj["score"] > best_obj["score"]:
                best, best_obj = cand, cand_obj
                table.append((cand, cand_obj))
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            pass

    # An optimum sitting ON a bound means the bound is binding, not that an
    # interior optimum was found - say so rather than presenting the edge of
    # the declared box as a design result.
    on_bound = []
    for k in ("length_m", "diameter_m"):
        lo, hi = (float(v) for v in GEOMETRY_DESIGN["bounds"][k])
        step = float(GEOMETRY_DESIGN["resolution"].get(k, 0.0)) or 1e-12
        if abs(best[k] - lo) <= step or abs(best[k] - hi) <= step:
            on_bound.append(k)
    if _SCREEN_VERBOSE:
        packed = best.get("packing_enabled", False)
        print(f"  reactor sizing: L = {best['length_m'] * 100:.1f} cm, "
              f"ID = {best['diameter_m'] * 1e3:.1f} mm, "
              f"{'PACKED bed (eps=%.2f)' % best['bed_void_fraction'] if packed else 'open tube'} "
              f"({'continuous' if DESIGN_SPACE['continuous'] else 'grid'}, "
              f"prior-based)")
        print(f"    info = {best_obj['info_nats']:.2f} nats - cost "
              f"{best_obj['cost_penalty_nats']:.2f} nats "
              f"(t_rad/tau = {best_obj['radial_ratio']:.1f})")
        if on_bound:
            print(f"    NOTE: optimum rests on the {', '.join(on_bound)} "
                  f"bound - the constraint is binding, so this is the edge "
                  f"of the declared box rather than an interior optimum. "
                  f"Widen GEOMETRY_DESIGN['bounds'] to find the real one.")
    best = dict(best)
    best["_on_bound"] = tuple(on_bound)
    _GEOMETRY_CACHE[key] = best
    _GEOMETRY_CACHE[("table",) + key] = [
        {"length_m": g["length_m"], "diameter_m": g["diameter_m"],
         "packed": int(g.get("packing_enabled", False)),
         "bed_void_fraction": g.get("bed_void_fraction", 1.0),
         "selected": int(g is best or (g["length_m"] == best["length_m"]
                          and g["diameter_m"] == best["diameter_m"]
                          and g.get("packing_enabled")
                          == best.get("packing_enabled"))),
         **o} for g, o in table]
    return best


def geometry_sizing_table(budget: int) -> List[Dict]:
    """Every candidate the sizing considered, with the decomposed objective
    (info, cost penalty, validity ratio, feasibility) - the audit trail for
    WHY this reactor, written to geometry_sizing.csv by the runner."""
    optimal_geometry(int(budget))          # ensure evaluated + cached
    for k, v in _GEOMETRY_CACHE.items():
        if isinstance(k, tuple) and k and k[0] == "table"                 and k[1] == int(budget):
            return v
    return []


def active_geometry(budget: int) -> Dict:
    """The reactor this campaign runs in: the declared GEOMETRY, or the
    prior-optimal one when geometry is part of the design problem.

    Strips the diagnostic `_on_bound` marker, which is reporting metadata
    and not a ReactorGeometry field."""
    if not GEOMETRY_DESIGN.get("enabled", False):
        return GEOMETRY
    g = optimal_geometry(int(budget))
    return {k: v for k, v in g.items() if not k.startswith("_")}


def reference_strategy(scenario: str) -> str:
    spec = SCENARIOS[scenario]
    ref = COMPARISON["reference_strategy"].get(
        scenario, COMPARISON["default_reference"])
    return ref if ref in spec.strategies else spec.strategies[0]


def design_resolution() -> DesignResolution:
    return DesignResolution(**DESIGN_SPACE["resolution"])


def continuous_kwargs() -> Dict:
    """Keyword arguments for the BASELINE MBDoESelector (strategies C/D/E).

    Empty when continuous mode is off, so the selector is constructed
    exactly as it was before this option existed."""
    if not DESIGN_SPACE.get("continuous", False):
        return {}
    return {"continuous": True,
            "continuous_bounds": DESIGN["continuous_bounds"],
            "continuous_maxiter": int(DESIGN_SPACE["continuous_maxiter"]),
            "resolution": design_resolution()}


# predetermined BLIND validation set - never visible to any controller
VALIDATION_CONDS = [
    OperatingConditions(70.0, 0.35, 0.35, 1.0, 0.8),
    OperatingConditions(110.0, 1.5, 1.5, 1.0, 0.6),
    OperatingConditions(150.0, 0.5, 0.5, 1.0, 1.0),
    OperatingConditions(50.0, 3.0, 3.0, 1.0, 1.0),
]

# The transfer line is COOLED on the way to the NMR flow cell - it does not
# sit at reactor temperature.  T_line_C is the commanded line temperature;
# None would mean "sample stays at reactor T", which is not what the
# hardware does.  25 C is the assumed ambient/cooled value.
TRANSFER_TRUE = TransferConfig(
    enabled=True, Q_sample_mL_min=0.5, V_fixed_mL=0.15, geometry="constant",
    rtd="gamma", n_tanks=4.0, n_quad=5, react_in_line=True,
    T_line_C=25.0,
    carryover=True, flush_volumes=3.0)

# ASSUMED plausible imperfections of the synthetic 80 MHz NMR observation
# model - NOT measured Fourier-80 properties.  Includes the truth-model
# mismatch block (pseudo-Voigt, J mismatch, static shifts, AR(1) noise,
# cubic baseline) so the fitter never fits its own exact physics.
NMR_NUISANCE_TRUE = SpectralNuisance(
    noise_sigma=0.10, shift_drift_ppm=0.004, shift_jitter_ppm=0.001,
    linewidth_rel_sigma=0.08, baseline_offset=0.02, baseline_curve=0.03,
    phase_error_deg=2.0, gain_drift_rel_sigma=0.01,
    response_factors={"EGMA": 1.02})

ACQ = AcquisitionSettings(n_points=2048, nmr_temperature_C=27.0)
#: default per-campaign resource model; scenarios may override it (S6 sweeps
#: the lambda weights) but this is the value every other scenario uses
RESOURCE_COSTS = ResourceCosts()
NOISE_DIRECT = NoiseModel(sigma_abs_M=0.004, sigma_rel=0.02, rho_overlap=0.3)

#: benchmark modes (#14): reproducible seed lists, no cherry-picking
MODES = {
    "smoke": {"seeds": [1], "budget": 3,
              "scenarios": ["S1_ideal", "S3_transport", "S5_inadequacy"]},
    "demo": {"seeds": [1, 2, 3, 4, 5, 6], "budget": 6,
             "scenarios": ["S1_ideal", "S2_nmr", "S3_transport",
                           "S3ab_delay", "S3ab_rtd",
                           "S4a_ambiguity", "S4b_identifiable",
                           "S4c_out_of_domain", "S5_inadequacy", "S6_resources",
                           "S7_spatial_modes"]},
    "publication": {"seeds": list(range(1, 41)), "budget": 8,
                    "scenarios": ["S1_ideal", "S2_nmr", "S3_transport",
                                  "S3ab_delay", "S3ab_rtd",
                                  "S4a_ambiguity", "S4b_identifiable",
                                  "S4c_out_of_domain", "S5_inadequacy", "S6_resources",
                                  "S7_spatial_modes"]},
}


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    description: str
    observation_mode: str = "direct"       # "direct" | "nmr"
    nmr_mode: str = "ideal"
    transfer: TransferConfig = TransferConfig(enabled=False)
    family: Tuple[str, ...] = ("rev-pitzer",)
    strategies: Tuple[str, ...] = ("A", "B", "C", "D", "E", "F")
    #: None -> the module-level RESOURCE_COSTS (which a runner's CONFIG can
    #: override).  A scenario that needs its OWN cost model - S6 sweeps the
    #: lambda weights - sets this explicitly and is unaffected.
    resource_costs: Optional[ResourceCosts] = None
    baseline_bridge_kwargs: Dict = field(default_factory=dict)
    f_variants: Dict[str, Dict] = field(default_factory=dict)
    track_correct_model: Optional[str] = None
    truth_override: Dict[str, float] = field(default_factory=dict)
    budget_override: Optional[int] = None
    #: True only for scenarios that CLAIM correct-model recovery; such a
    #: scenario must pass check_truth_in_domain() (every hidden true value
    #: inside the candidate parameter box with margin)
    well_specified: bool = False

    @property
    def truth(self) -> Dict[str, float]:
        return {**TRUTH, **self.truth_override}


def _resource_lambdas(scale: float) -> ResourceCosts:
    """The S6 lambda sweep: one base weight vector x a scale factor.
    The base values are ARBITRARY units chosen for the study - the Pareto
    sweep exists precisely so no single weight vector is presented as
    universal."""
    return ResourceCosts(
        lambda_time_per_s=2e-3 * scale, lambda_material_per_mol=50.0 * scale,
        lambda_waste_per_mL=5e-3 * scale, lambda_energy_per_kJ=0.05 * scale,
        lambda_switch=1.0 * scale, lambda_motion_per_m=2.0 * scale)


SCENARIOS: Dict[str, ScenarioSpec] = {
    "S1_ideal": ScenarioSpec(
        name="S1_ideal",
        description="correct model, ideal direct observation, no transport",
        strategies=("A", "B", "C", "D", "E", "F")),
    "S2_nmr": ScenarioSpec(
        name="S2_nmr",
        description="synthetic 80 MHz spectra (truth-model mismatch active) "
                    "+ deconvolution covariance",
        observation_mode="nmr", nmr_mode="realistic",
        strategies=("B", "D", "F")),
    "S3_transport": ScenarioSpec(
        name="S3_transport",
        description="NMR + transport: delay, RTD, in-line reaction, carryover",
        observation_mode="nmr", nmr_mode="realistic",
        transfer=TRANSFER_TRUE, strategies=("D", "F-uncorr", "F"),
        f_variants={"F-uncorr": {"transport_aware": False},
                    "F": {"transport_aware": True}}),
    # ---- transport ablation (which effect matters?) --------------------- #
    "S3ab_delay": ScenarioSpec(
        name="S3ab_delay",
        description="transport ablation: mean delay + in-line reaction only "
                    "(plug RTD, no carryover)",
        observation_mode="nmr", nmr_mode="realistic",
        transfer=replace(TRANSFER_TRUE, rtd="delta", carryover=False),
        strategies=("D", "F"),
        f_variants={"F": {"transport_aware": True}}),
    "S3ab_rtd": ScenarioSpec(
        name="S3ab_rtd",
        description="transport ablation: delay + gamma RTD dispersion "
                    "(no carryover)",
        observation_mode="nmr", nmr_mode="realistic",
        transfer=replace(TRANSFER_TRUE, carryover=False),
        strategies=("D", "F"),
        f_variants={"F": {"transport_aware": True}}),
    # --------------------------------------------------------------------- #
    "S4a_ambiguity": ScenarioSpec(
        name="S4a_ambiguity",
        description="HARD model discrimination: pitzer vs dilute vs "
                    "irreversible (may honestly end undecided)",
        observation_mode="nmr", nmr_mode="realistic",
        family=("rev-pitzer", "rev-dilute", "irreversible"),
        strategies=("D", "F"), track_correct_model="rev-pitzer",
        budget_override=10),
    "S4b_identifiable": ScenarioSpec(
        name="S4b_identifiable",
        description="WELL-SPECIFIED correct-model recovery: reversible "
                    "(rev-pitzer) vs irreversible under the STANDARD "
                    "benchmark truth - no per-scenario truth override, so "
                    "nothing was tuned; the 20 cm CPR reaches phi ~ 1 at the "
                    "hot/slow corner, so reverse kinetics are observable and "
                    "the learner must find that region",
        observation_mode="nmr", nmr_mode="realistic",
        family=("rev-pitzer", "irreversible"),
        strategies=("D", "F"), track_correct_model="rev-pitzer",
        budget_override=8, well_specified=True),
    "S4c_out_of_domain": ScenarioSpec(
        name="S4c_out_of_domain",
        description="OUT-OF-DOMAIN / MODEL-MISSPECIFICATION (NOT a "
                    "correct-model-recovery test): truth K2=0.002 lies BELOW "
                    "the candidate parameter bound (0.0155), so the "
                    "reversible candidate cannot represent it and K2 pins to "
                    "its bound by construction",
        observation_mode="nmr", nmr_mode="realistic",
        family=("rev-pitzer", "irreversible"),
        strategies=("F",), track_correct_model="rev-pitzer",
        truth_override={"K1_ref": 0.15, "K2_ref": 0.002},
        budget_override=8),
    "S5_inadequacy": ScenarioSpec(
        name="S5_inadequacy",
        description="correct model REMOVED from the family; truth is an "
                    "explicitly OUT-OF-DOMAIN strongly reversible ester "
                    "(K1=0.15, K2=0.002) that NO candidate can represent - "
                    "the irreversible-only family has no K parameters at all",
        observation_mode="nmr", nmr_mode="realistic",
        family=("irreversible",),
        strategies=("D", "F-noGovernor", "F"),
        baseline_bridge_kwargs={"reversible": False},
        f_variants={"F-noGovernor": {"use_governor": False}, "F": {}},
        truth_override={"K1_ref": 0.15, "K2_ref": 0.002}),
    "S6_resources": ScenarioSpec(
        name="S6_resources",
        description="resource-aware design: lambda sweep -> Pareto frontier",
        observation_mode="nmr", nmr_mode="realistic",
        strategies=("D", "F", "F-res-0.5x", "F-res-1x", "F-res-2x",
                    "F-res-4x"),
        f_variants={"F": {},
                    "F-res-0.5x": {"costs": _resource_lambdas(0.5)},
                    "F-res-1x": {"costs": _resource_lambdas(1.0)},
                    "F-res-2x": {"costs": _resource_lambdas(2.0)},
                    "F-res-4x": {"costs": _resource_lambdas(4.0)}}),
    "S7_spatial_modes": ScenarioSpec(
        name="S7_spatial_modes",
        description="spatial policy comparison under identical physics: "
                    "fixed_equal vs optimized_batch vs adaptive_sequential",
        observation_mode="nmr", nmr_mode="realistic",
        strategies=("F-zfixed", "F-zbatch", "F-zadaptive"),
        f_variants={"F-zfixed": {"spatial_mode": "fixed_equal"},
                    "F-zbatch": {"spatial_mode": "optimized"},
                    "F-zadaptive": {"spatial_mode": "adaptive_sequential"}}),
}


# ------------------------------------------------------------------------- #
class BaselineLabAdapter:
    """Presents AdvancedVirtualLaboratory as the legacy VirtualLaboratory so
    sdl.campaign.run_strategy runs UNCHANGED.  Strips cov_y: the baselines
    assume their configured NoiseModel, exactly as before."""

    def __init__(self, lab: AdvancedVirtualLaboratory,
                 ports_z_m: np.ndarray, strip_cov: bool = True):
        self._lab = lab
        self.ports_z_m = np.asarray(ports_z_m, dtype=float)
        self.outlet_z_m = np.array([lab.length_m])
        self.strip_cov = strip_cov
        self.totals_history: List[Dict[str, float]] = []

    @property
    def n_experiments_run(self):
        return self._lab.n_experiments_run

    @property
    def n_truth_reveals(self):
        return self._lab.n_truth_reveals

    def run_experiment(self, u: OperatingConditions, spatial: bool):
        z = self.ports_z_m if spatial else self.outlet_z_m
        m = self._lab.run_profile(u, z)
        if self.strip_cov:
            m.cov_y = None
        self.totals_history.append(self._lab.meter.totals())
        return m

    def reveal_truth(self):
        return self._lab.reveal_truth()


# ------------------------------------------------------------------------- #
def make_lab(spec: ScenarioSpec, seed: int,
             store_spectra: bool = False,
             costs: Optional[ResourceCosts] = None,
             geometry: Optional[Dict] = None
             ) -> AdvancedVirtualLaboratory:
    geom = geometry if geometry is not None else GEOMETRY
    truth_bridge = Layer1Bridge(geom, T_REF_C + 273.15,
                                activity_model="pitzer")
    return AdvancedVirtualLaboratory(
        spec.truth, truth_bridge,
        InstrumentConfig(observation_mode=spec.observation_mode,
                         nmr_mode=spec.nmr_mode,
                         store_spectra=store_spectra),
        ACQ, NMR_NUISANCE_TRUE, spec.transfer,
        costs if costs is not None
        else (spec.resource_costs if spec.resource_costs is not None
              else RESOURCE_COSTS),
        seed=seed, noise_direct=NOISE_DIRECT)


def check_truth_in_domain(space: ParameterSpace, truth: Dict[str, float],
                          min_margin_efolds: float = 0.5) -> Dict:
    """Is every hidden true parameter inside the candidate model's domain?

    Returns a per-parameter report with the distance (in scaled units, i.e.
    e-folds for log parameters) to the nearer bound.  `ok` is False when any
    ESTIMATED parameter lies outside its box, or inside with less than
    `min_margin_efolds` of margin - in which case the estimate will pin to
    the bound and any 'correct-model recovery' claim is invalid.

    POST-CAMPAIGN / BENCHMARK-CONSTRUCTION USE ONLY: it reads the hidden
    truth and must never be called from controller-side code."""
    lo, hi = space.bounds()
    detail, ok = {}, True
    for q, k in enumerate(space.param_keys):
        if k not in truth:
            continue
        v = space.to_vector({**space.initial_guess, **truth})[q]
        margin = float(min(v - lo[q], hi[q] - v))
        inside = bool(lo[q] <= v <= hi[q])
        detail[k] = {"inside": inside, "margin_scaled": margin,
                     "enough_margin": bool(margin >= min_margin_efolds)}
        if not inside or margin < min_margin_efolds:
            ok = False
    return {"ok": ok, "detail": detail}


_SCREEN_CACHE: Dict[Tuple, Tuple[str, ...]] = {}
# Worker processes announce nothing: the screen is a deterministic function
# of the budget, so every process computes the SAME answer and only the
# parent should report it (set False by worker_init).
_SCREEN_VERBOSE = True


def screened_dropped_keys(budget: int) -> Tuple[str, ...]:
    """Pre-campaign identifiability screen (same code as
    run_sdl_campaign.py), computed once per budget and applied identically
    to every strategy.

    Deterministic in `budget` alone, so a worker process re-deriving it
    reaches the same result as the parent - the per-process cache is a
    speed-up, never a source of divergence."""
    geom = active_geometry(budget)
    key = (int(budget), float(geom["length_m"]), float(geom["diameter_m"]))
    if key not in _SCREEN_CACHE:
        t_ref_K = T_REF_C + 273.15
        bridge = Layer1Bridge(geom, t_ref_K, activity_model="pitzer")
        space = ParameterSpace(t_ref_K=t_ref_K,
                               initial_guess=literature_guess(t_ref_K))
        ports = fixed_equal_positions(geom["length_m"], N_PORTS)
        sr = screen(space, bridge, NOISE_DIRECT,
                    build_candidates(DESIGN) + reference_design(DESIGN),
                    ports, SPECIES, budget=budget, max_rel_ci_pct=200.0)
        _SCREEN_CACHE[key] = sr.dropped
        if sr.dropped and _SCREEN_VERBOSE:
            print(f"  identifiability screen: holding fixed {sr.dropped}")
    return _SCREEN_CACHE[key]


def worker_init(budget: Optional[int] = None,
                overrides: Optional[Dict] = None) -> None:
    """Initializer for a parallel worker process.

    Two jobs.  First, silence the per-process identifiability-screen
    announcement and warm the screen cache once, so the first campaign a
    worker runs is not slower than the rest - that changes no numerical
    result, the screen being a pure function of the budget.

    Second, and load-bearing: a spawned worker re-imports this module and
    therefore starts from the DEFAULT configuration.  The runner's overrides
    must be replayed here or the workers would silently run a different
    configuration from the parent - the worst possible failure, because the
    results would look plausible."""
    global _SCREEN_VERBOSE
    _SCREEN_VERBOSE = False
    if overrides:
        apply_config(overrides)
    if budget is not None:
        screened_dropped_keys(int(budget))


def _spatial_cfg(mode: str) -> SpatialDesignConfig:
    kw = {k: v for k, v in SPATIAL.items()
          if k != "marginal_information_threshold" or v is not None}
    return SpatialDesignConfig(
        mode=mode, n_positions=N_PORTS,
        allow_profile_early_stop=(mode == "adaptive_sequential"), **kw)


def _assumed_transfer_from(cfg: TransferConfig,
                           length_m: float) -> AssumedTransfer:
    """INFERENCE-side transfer correction from COMMANDED quantities only
    (nominal volume/flow/geometry; never the truth's RTD or carryover)."""
    if not cfg.enabled:
        return AssumedTransfer(enabled=False)
    return AssumedTransfer(enabled=True,
                           Q_sample_mL_min=cfg.Q_sample_mL_min,
                           V_fixed_mL=cfg.V_fixed_mL,
                           geometry=cfg.geometry,
                           v_per_m_mL=cfg.v_per_m_mL, length_m=length_m,
                           # COMMANDED, so the controller is entitled to it
                           T_line_C=cfg.T_line_C)


def design_for_budget(budget: int) -> Dict:
    """DESIGN with a conventional temperature ladder long enough for the
    requested budget.

    The fixed/conventional baselines (A, B) walk `fixed_design_T_C` one rung
    per round, and sdl.design.build_fixed_design only ever SUBSAMPLES that
    declared ladder - it never extends it.  A budget larger than the ladder
    therefore used to abort the campaign (publication mode: budget 8 vs a
    7-rung ladder).

    Rule, chosen so previously reported results stay reproducible:
      * budget <= declared rungs -> the declared ladder is used unchanged
        (demo mode is bit-for-bit as before);
      * budget >  declared rungs -> the ladder is REFINED to exactly
        `budget` evenly spaced temperatures over the SAME declared range,
        which is what a conventional experimenter with more runs would do.
    """
    ladder = list(DESIGN["fixed_design_T_C"])
    if budget <= len(ladder):
        return DESIGN
    lo, hi = float(min(ladder)), float(max(ladder))
    refined = [float(x) for x in np.linspace(lo, hi, int(budget))]
    return {**DESIGN, "fixed_design_T_C": refined}


def run_one_campaign(spec: ScenarioSpec, strategy: str, seed: int,
                     budget: int, verbose: bool = False,
                     store_spectra: bool = False, recorder=None):
    """One (scenario, strategy, seed) campaign.  Returns (result, lab,
    extra).

    `recorder`: passive audit sink (sdl_advanced/audit.py) or None.  It is
    handed to the advanced controllers, which report already-computed
    quantities to it; it never influences a decision.  Baselines A-D run
    unchanged sdl.campaign code and are audited entirely post-campaign."""
    t_ref_K = T_REF_C + 273.15
    variant = spec.f_variants.get(strategy, {})
    # ONE geometry for the whole campaign: the declared reactor, or the
    # prior-optimal one when geometry is part of the design problem
    geom = active_geometry(budget)
    lab = make_lab(spec, seed, store_spectra=store_spectra,
                   costs=variant.get("costs"), geometry=geom)
    ports = fixed_equal_positions(lab.length_m, N_PORTS)
    candidates = build_candidates(DESIGN)
    fixed = build_fixed_design(design_for_budget(budget),
                               budget=budget)
    guess = literature_guess(t_ref_K, "H2SO4")
    dropped = screened_dropped_keys(budget)

    if strategy in ("A", "B", "C", "D"):
        bkw = dict(activity_model="pitzer", **spec.baseline_bridge_kwargs)
        bridge = Layer1Bridge(geom, t_ref_K, **bkw)
        pkeys = (("k1_ref", "Ea1_J", "k2_ref", "Ea2_J")
                 if not bridge.reversible else param_keys_for("H2SO4"))
        space = ParameterSpace(t_ref_K=t_ref_K, initial_guess=dict(guess),
                               param_keys=pkeys)
        drop = [k for k in dropped if k in pkeys]
        if drop:
            space = space.holding_fixed(drop)
        inference = InferenceModel(space, bridge, NOISE_DIRECT)
        adapter = BaselineLabAdapter(lab, ports)
        selector = MBDoESelector(
            inference=inference, candidates=candidates,
            spatial=strategy in ("B", "D"), ports_z_m=ports,
            outlet_z_m=np.array([lab.length_m]), species=SPECIES,
            criterion="D",
            **continuous_kwargs()) if strategy in ("C", "D") else None
        res = run_strategy(strategy, adapter, inference, fixed, selector,
                           budget=budget, verbose=verbose)
        return res, lab, adapter

    if strategy == "E":
        bridge = Layer1Bridge(geom, t_ref_K, activity_model="pitzer")
        space = ParameterSpace(t_ref_K=t_ref_K, initial_guess=dict(guess))
        if dropped:
            space = space.holding_fixed(list(dropped))
        inference = InferenceModel(space, bridge, NOISE_DIRECT)
        res = run_strategy_e(lab, inference, candidates, fixed[0],
                             _spatial_cfg("optimized"), budget,
                             verbose=verbose, recorder=recorder,
                             **continuous_kwargs())
        return res, lab, None

    # F and its variants -------------------------------------------------- #
    transport_aware = variant.get("transport_aware",
                                  spec.transfer.enabled)
    assumed = (_assumed_transfer_from(spec.transfer, lab.length_m)
               if transport_aware else AssumedTransfer(enabled=False))
    family = build_egda_family(geom, t_ref_K, include=spec.family,
                               noise_assumed=NOISE_DIRECT,
                               fixed={k: guess[k] for k in dropped},
                               assumed_transfer=assumed)
    ensemble = ModelEnsemble(family)
    # kappa: NMR scenarios declare floor-level quantification systematics in
    # Sigma_y; the governor's nulls are widened by exactly that allowance
    # (0 for direct observation -> exact nulls)
    # kappa is DERIVED from WELL-SPECIFIED CONTROL data, never from the
    # kinetic benchmark: validation.derive_systematic_allowance() measures
    # the standardized residual z = (c_hat - c_true)/sigma_claimed of the
    # CALIBRATED NMR pathway on an independent control stream and returns
    #     kappa = sqrt(rms(z)^2 - 1).
    # With the shared calibration artifact (Priority 1) the covariance is
    # nearly right - rms(z) = 1.11, per-species z-std [1.00, 0.77, 1.16,
    # 1.06] - but a bounded residual BIAS survives in the overlapped
    # resonances (z-mean EGMA -0.72, AcOH -0.52), which is exactly what the
    # allowance is for.  Hence kappa = 0.47, down from 1.25 in v3 when the
    # governor was compensating for a broken Sigma_y.  Re-derive whenever
    # the NMR calibration changes.  kappa = 0 for direct observation, where
    # Sigma is exact by construction.
    # SEE: tests/test_calibration_governor.py::test_allowance_is_derived...
    governor = AdequacyGovernor(GovernorConfig(
        n_rounds_planned=budget,
        alpha_campaign=float(GOVERNOR["alpha_campaign"]),
        discrimination_prob=float(GOVERNOR["discrimination_prob"]),
        qc_fail_fraction=float(GOVERNOR["qc_fail_fraction"]),
        chi2_dof_ratio_override=float(GOVERNOR["chi2_dof_ratio_override"]),
        systematic_allowance=float(
            GOVERNOR["systematic_allowance_nmr"]
            if spec.observation_mode == "nmr"
            else GOVERNOR["systematic_allowance_direct"])))
    cov_model = None
    if spec.observation_mode == "nmr" \
            and variant.get("expected_cov", "spectral") == "spectral":
        # SAME public calibration artifact as the measurement pathway:
        # Sigma_expected(MBDoE) and Sigma_actual(instrument) are two
        # evaluations of one calibrated measurement model, not two
        # independently invented ones.
        cov_model = SpectralCovarianceModel(
            SpectralFitter(ACQ), calibration=getattr(lab, "calibration", None))
    spatial_mode = variant.get("spatial_mode", "optimized")
    design_cfg = AdvancedDesignConfig(
        top_k=int(ADVANCED_DESIGN["top_k"]),
        n_particles=int(ADVANCED_DESIGN["n_particles"]),
        n_outer=int(ADVANCED_DESIGN["n_outer"]),
        alpha_param=float(ADVANCED_DESIGN["alpha_param"]),
        beta_model=float(ADVANCED_DESIGN["beta_model"]),
        beta_model_discrimination=float(
            ADVANCED_DESIGN["beta_model_discrimination"]),
        objective=variant.get("objective", "parameter"),
        continuous=bool(DESIGN_SPACE.get("continuous", False)),
        continuous_maxiter=int(DESIGN_SPACE["continuous_maxiter"]),
        continuous_restarts=int(DESIGN_SPACE["continuous_restarts"]))
    res = run_strategy_f(
        lab, ensemble, candidates, fixed[0], _spatial_cfg(spatial_mode),
        budget, design_cfg=design_cfg, governor=governor,
        use_governor=variant.get("use_governor", True),
        cov_model=cov_model,
        qc=QCGateConfig(
            enabled=bool(QC_GATE["enabled_for_nmr"])
            and spec.observation_mode == "nmr",
            max_retries=int(QC_GATE["max_retries"]),
            max_reject_fraction=float(QC_GATE["max_reject_fraction"])),
        bounds=DESIGN["continuous_bounds"], seed=seed, verbose=verbose,
        key=strategy, recorder=recorder, resolution=design_resolution())
    return res, lab, governor


# ------------------------------------------------------------------------- #
def _rebridge(bridge: Layer1Bridge, geometry: Dict) -> Layer1Bridge:
    """The same model configuration in a different reactor - used to move a
    LEARNED model into the reference geometry for scoring.  Legitimate for
    exactly the reason the user of this framework would state: a plug-flow
    reactor changes tau(z), never the constants."""
    return Layer1Bridge(geometry, bridge.t_ref_K,
                        h_plus_model=bridge.h_plus_model,
                        engine=bridge.engine,
                        n_points=bridge.settings.n_points,
                        reversible=bridge.reversible,
                        catalyst=bridge.catalyst,
                        ka2_model=bridge.ka2_model,
                        activity_model=bridge.activity_model)


def _scoring_bridge(bridge: Layer1Bridge) -> Layer1Bridge:
    """Bridge used for BLIND SCORING: identical object when geometry
    optimization is off (the bit-identical legacy path), the same model
    rebuilt in the declared reference reactor when it is on."""
    if not GEOMETRY_DESIGN.get("enabled", False):
        return bridge
    g = bridge.geometry
    ref_void = (float(GEOMETRY.get("bed_void_fraction", 1.0))
                if GEOMETRY.get("packing_enabled", False) else 1.0)
    if (abs(g.length_m - GEOMETRY["length_m"]) < 1e-12
            and abs(g.diameter_m - GEOMETRY["diameter_m"]) < 1e-12
            and g.void_fraction == ref_void):
        return bridge
    return _rebridge(bridge, GEOMETRY)


def _truth_prediction(truth: Dict[str, float], z_val: np.ndarray,
                      geometry: Optional[Dict] = None) -> np.ndarray:
    bridge = Layer1Bridge(geometry if geometry is not None else GEOMETRY,
                          T_REF_C + 273.15, activity_model="pitzer")
    return np.concatenate([bridge.concentrations_at(truth, u, z_val, SPECIES)
                           for u in VALIDATION_CONDS])


def blind_rmse(bridge, space, theta_vec, z_val: np.ndarray,
               y_true: np.ndarray) -> float:
    """Blind predictive RMSE of the REACTOR state (transport correction is
    an observation artifact and deliberately excluded here: the question is
    'how well does the learned kinetic model predict the chemistry')."""
    nat = space.to_natural(theta_vec)
    y = np.concatenate([bridge.concentrations_at(nat, u, z_val, SPECIES)
                        for u in VALIDATION_CONDS])
    return float(np.sqrt(np.mean((y - y_true) ** 2)))


def _entropy(probs: Dict[str, float]) -> float:
    p = np.array([v for v in probs.values() if v > 0.0])
    return float(-np.sum(p * np.log(p))) if len(p) else 0.0


def _param_rows(spec, strategy, seed, rnd, space, theta_nat, sigma_scaled,
                bound_active, truth) -> List[Dict]:
    """Per-parameter posterior reporting (#identifiability): estimate,
    scaled sigma, 95% interval, relative width, bound flag, and - post-
    campaign evaluation ONLY - the true value and relative error."""
    rows = []
    vec = space.to_vector(theta_nat)
    for q, k in enumerate(space.param_keys):
        sig = float(sigma_scaled[q]) if sigma_scaled is not None else np.nan
        est = theta_nat[k]
        if space.is_log(q):
            # a rank-deficient FIM gives astronomically large sigma: report
            # the interval as unbounded instead of overflowing exp()
            arg = 1.96 * sig
            if not np.isfinite(arg) or arg > 500.0:
                lo, hi, rel_w = 0.0, float("inf"), float("inf")
            else:
                lo, hi = est * math.exp(-arg), est * math.exp(arg)
                rel_w = (math.exp(arg) - math.exp(-arg)) * 100.0
        else:
            lo, hi = est - 1.96 * sig * 1e3, est + 1.96 * sig * 1e3
            rel_w = 2 * 1.96 * sig * 1e3 / max(abs(est), 1e-12) * 100.0
        t = truth.get(k)
        rows.append(dict(
            scenario=spec.name, strategy=strategy, seed=seed, round=rnd,
            param=k, estimate=est, sigma_scaled=sig, ci_lo=lo, ci_hi=hi,
            rel_width_pct=rel_w,
            bound_active=int(k in (bound_active or ())),
            true_value=t if t is not None else np.nan,
            rel_error_pct=(abs(est / t - 1.0) * 100.0
                           if t not in (None, 0) else np.nan),
            covered95=(int(lo <= t <= hi) if t is not None
                       and np.isfinite(rel_w) else np.nan)))
    return rows


def _round_metrics(spec: ScenarioSpec, strategy: str, res, lab, extra,
                   z_val: np.ndarray, y_true: np.ndarray
                   ) -> Tuple[List[Dict], List[Dict]]:
    """Per-round metric rows + per-parameter rows for one campaign (hidden
    truth used HERE only, post-campaign)."""
    truth = spec.truth
    rows, prows = [], []
    if isinstance(res, StrategyResult):      # baselines A-D
        inf = res.inference
        adapter = extra
        for i, rec in enumerate(res.history):
            keys = tuple(k for k in rec.theta_nat if k in truth
                         and k in inf.space.param_keys)
            err = log_mean_rel_error_pct(rec.theta_nat, truth, keys)
            tot = (adapter.totals_history[i] if adapter
                   and i < len(adapter.totals_history) else {})
            rows.append(dict(
                scenario=spec.name, strategy=strategy, round=rec.round,
                param_err_pct=err,
                max_rel_ci_pct=min(float(rec.report.max_rel_ci_pct), 1e4),
                p_correct=float("nan"), model_entropy=float("nan"),
                gov_state="", gov_score=float("nan"),
                gov_p=float("nan"), stop_reason="",
                probs_reliable=-1,              # n/a: no Bayesian evidence
                evidence_reliable_by_model="", evidence_warning="",
                blind_rmse_M=blind_rmse(_scoring_bridge(inf.bridge),
                                        inf.space,
                                        inf.space.to_vector(rec.theta_nat),
                                        z_val, y_true),
                **{k: tot.get(k, 0.0) for k in ResourceMeter.TOTAL_KEYS}))
            prows.extend(_param_rows(spec, strategy, None, rec.round,
                                     inf.space, rec.theta_nat,
                                     rec.report.sigma,
                                     rec.report.active_bounds, truth))
        return rows, prows
    # E and F variants ---------------------------------------------------- #
    for rec in res.history:
        if res.ensemble is not None and rec.best_model != "wls":
            cm = res.ensemble.models[[c.name for c in res.ensemble.models]
                                     .index(rec.best_model)]
            space, bridge = cm.space, cm.bridge
        else:
            space, bridge = res.inference.space, res.inference.bridge
        keys = tuple(k for k in rec.theta_nat if k in truth
                     and k in space.param_keys)
        err = log_mean_rel_error_pct(rec.theta_nat, truth, keys)
        sig = rec.sigma_scaled
        max_ci = float(np.max(space.rel_ci_percent(
            space.to_vector(rec.theta_nat), sig))) if sig is not None \
            else float("nan")
        p_corr = (rec.model_probs.get(spec.track_correct_model, float("nan"))
                  if spec.track_correct_model else float("nan"))
        rows.append(dict(
            scenario=spec.name, strategy=strategy, round=rec.round,
            param_err_pct=err, max_rel_ci_pct=min(max_ci, 1e4),
            p_correct=p_corr, model_entropy=_entropy(rec.model_probs),
            gov_state=(rec.governor.state if rec.governor else ""),
            gov_score=(rec.governor.score if rec.governor else float("nan")),
            gov_p=(rec.governor.p_value if rec.governor else float("nan")),
            stop_reason=res.stop_reason,
            n_rejected=rec.n_rejected, n_reacquired=rec.n_reacquired,
            probs_reliable=int(rec.probs_reliable),
            evidence_reliable_by_model=";".join(
                f"{k}={int(v)}" for k, v in
                sorted(rec.evidence_reliable_by_model.items())),
            evidence_warning=rec.evidence_warning[:200],
            blind_rmse_M=blind_rmse(_scoring_bridge(bridge), space,
                                    space.to_vector(rec.theta_nat),
                                    z_val, y_true),
            **{k: rec.resources.get(k, 0.0)
               for k in ResourceMeter.TOTAL_KEYS}))
        prows.extend(_param_rows(spec, strategy, None, rec.round, space,
                                 rec.theta_nat, sig, rec.bound_active,
                                 truth))
    return rows, prows


# ------------------------------------------------------------------------- #
#: RELATIVE cost of one campaign round per strategy, measured from the demo
#: run (A/B/C/D ~ baseline WLS; E adds spatial optimisation; F adds the NMR
#: pathway + Bayesian ensemble).  Used ONLY to weight the progress bar so
#: its ETA does not swing when the mix of strategies changes; it has no
#: effect on any scientific result.
_STRATEGY_COST = {"A": 0.35, "B": 0.6, "C": 0.5, "D": 0.8, "E": 1.2}


def campaign_cost_units(strategy: str, budget: int) -> float:
    """Approximate work of one campaign, in arbitrary units ~ seconds."""
    base = _STRATEGY_COST.get(strategy, 2.6 if strategy.startswith("F")
                              else 1.0)
    return float(base * budget)


def total_cost_units(scenarios: Sequence[str], seeds: Sequence[int],
                     budget: int, n_governor_seeds: int = 0) -> float:
    """Total weighted work of a benchmark run (campaigns + governor MC)."""
    total = 0.0
    for name in scenarios:
        spec = SCENARIOS[name]
        b = spec.budget_override or budget
        for strategy in spec.strategies:
            total += len(seeds) * campaign_cost_units(strategy, b)
    total += 2.0 * n_governor_seeds * campaign_cost_units("F", budget)
    return total


def campaign_task(scenario_name: str, strategy: str, seed: int, budget: int,
                  verbose: bool = False, audit: bool = False) -> Dict:
    """ONE campaign, as a picklable pure function of its four labels.

    This is the unit of parallel work.  It takes and returns only primitives
    (never a ScenarioSpec, a laboratory or a posterior object), so it costs
    the same to hand to a worker process as to call in-process, and it reads
    no state that a worker would not have.  Everything random inside is
    seeded from `seed`, so the returned rows are the same on any core, in any
    process, at any level of parallelism.

    The scenario is looked up by NAME rather than passed in, both to keep the
    payload tiny and to guarantee the worker uses this module's own
    definition rather than a pickled copy of it.  A consequence worth
    knowing: a scenario must be defined at MODULE level in SCENARIOS to be
    parallelizable, because a spawned worker re-imports this module and sees
    only what is written here - one registered at run time would raise a
    KeyError naming itself.  `run_scenario` refuses to send an unregistered
    spec to a pool at all.
    """
    spec = SCENARIOS[scenario_name]
    budget = spec.budget_override or budget
    # Blind validation is ALWAYS scored in the DECLARED reference reactor,
    # whatever reactor the campaign ran in.  This is well-defined because
    # the estimated parameters are intrinsic - c(tau) depends on theta and
    # tau only, never on which tube produced the data - so "how well does
    # the learned model predict the reference reactor" is one fixed
    # question, and blind RMSE stays comparable across strategies AND
    # across runs with different geometry settings.
    z_val = np.array([GEOMETRY["length_m"] / 3.0, GEOMETRY["length_m"]])
    y_true = _truth_prediction(spec.truth, z_val, geometry=GEOMETRY)
    recorder = None
    if audit:
        from .audit import AuditRecorder
        recorder = AuditRecorder(spec.name, strategy, seed, SPECIES)
    t0 = time.time()
    res, lab, extra = run_one_campaign(spec, strategy, seed, budget,
                                       verbose=verbose, recorder=recorder)
    r, p = _round_metrics(spec, strategy, res, lab, extra, z_val, y_true)
    stop = getattr(res, "stop_reason", "budget exhausted")
    tot = lab.meter.totals()
    audit_bundle = None
    if audit:
        # POST-campaign derivation: reads the finished result/laboratory,
        # runs no controller code and touches no RNG (audit_export.py)
        from . import audit_export as aex
        spatial_mode = spec.f_variants.get(strategy, {}).get(
            "spatial_mode", "optimized" if strategy in ("E",) or
            strategy.startswith("F") else "fixed_equal")
        audit_bundle = aex.collect_campaign(
            spec, strategy, seed, res, lab, extra, recorder, z_val, y_true,
            VALIDATION_CONDS, SPECIES, spatial_mode,
            scoring_bridge=_scoring_bridge)
    return {
        "rows": [dict(x, seed=seed) for x in r],
        "prows": [dict(x, seed=seed) for x in p],
        "audit": audit_bundle,
        "status": {
            "scenario": spec.name, "strategy": strategy, "seed": seed,
            "rounds_completed": len(r),
            "rounds_planned": budget,
            "completed": int(len(r) >= budget),
            "faulted": int("MEASUREMENT_FAULT" in str(stop)),
            "stop_reason": stop,
            "qc_rejected": tot.get("qc_rejected", 0.0),
            "nmr_reacquisitions": tot.get("nmr_reacquisitions", 0.0),
            "nmr_acquisitions": tot.get("nmr_acquisitions", 0.0),
            "last_valid_blind_rmse_M": (r[-1]["blind_rmse_M"] if r
                                        else float("nan")),
            "last_valid_param_err_pct": (r[-1]["param_err_pct"] if r
                                         else float("nan")),
            # WALL CLOCK: the only field a worker count can change.  It
            # measures the run, not the chemistry; every scientific column
            # above is deterministic, and the simulated laboratory time the
            # figures plot against ("time_s") comes from ResourceMeter.
            "runtime_s": time.time() - t0,
        },
    }


def run_scenario(spec: ScenarioSpec, seeds: Sequence[int], budget: int,
                 verbose: bool = False, progress=None, executor=None,
                 audit: bool = False
                 ) -> Tuple[List[Dict], List[Dict], List[Dict], Optional[Dict]]:
    """Returns (round rows, per-parameter rows, per-campaign status rows).

    NO campaign is ever dropped: a run that PAUSES on a measurement fault
    keeps its completed rounds (its last valid posterior is the final row
    for that seed) and is recorded in the status table with its completion
    flag, fault counts and stop reason - so accuracy statistics and
    completion/fault rates are reported side by side (no survivorship
    bias).

    `executor`: an optional process pool (see sdl_advanced.parallel).  The
    campaigns are independent, so they are simply distributed over it and
    reassembled in SUBMISSION order - strategy-major, then seed - which is
    the order the serial loop produced.  Passing None keeps the original
    in-process loop exactly as it was."""
    budget = spec.budget_override or budget
    tasks = [(spec.name, strategy, seed, budget, verbose, audit)
             for strategy in spec.strategies for seed in seeds]

    # A worker rebuilds the scenario from SCENARIOS[name] (only the name
    # crosses the process boundary).  An ad-hoc spec that is not the
    # registered one would therefore be silently replaced by it, so such a
    # spec is run in-process instead - correctness before speed.
    if executor is not None and SCENARIOS.get(spec.name) is not spec:
        print(f"    note: '{spec.name}' is not the registered scenario "
              f"object; running it serially so the passed spec is honoured")
        executor = None

    def _landed(_i, args, out):
        """Parent-side reporting only; runs in completion order when
        parallel, so nothing saved may depend on it."""
        _scen, strategy, seed, b, _v, _a = args
        if verbose:
            n_done = out["status"]["rounds_completed"]
            print(f"    {spec.name}/{strategy}/seed{seed}: "
                  f"{out['status']['runtime_s']:.1f} s"
                  + ("" if n_done >= b
                     else f"  [PAUSED after {n_done}/{b} rounds]"))
        if progress is not None:
            progress(spec.name, strategy, seed, b)

    results = par.ordered_map(campaign_task, tasks, executor=executor,
                              on_result=_landed)
    rows, prows, status = [], [], []
    bundle = None
    if audit:
        from . import audit_export as aex
        bundle = aex.empty_bundle()
    for out in results:
        rows.extend(out["rows"])
        prows.extend(out["prows"])
        status.append(out["status"])
        if audit:
            from . import audit_export as aex
            aex.merge(bundle, out.get("audit"))
    return rows, prows, status, bundle


# ------------------------------------------------------------------------- #
# distributional statistics (#no-cherry-picking)
# ------------------------------------------------------------------------- #
def _boot_ci(x: np.ndarray, stat=np.median, B: int = 2000,
             seed: int = 0) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    if len(x) < 2:
        return float("nan"), float("nan")
    s = np.array([stat(rng.choice(x, len(x))) for _ in range(B)])
    return float(np.quantile(s, 0.025)), float(np.quantile(s, 0.975))


def last_valid_rows(rows: List[Dict], scenario: str,
                    strategy: str) -> List[Dict]:
    """One row per SEED: that seed's LAST COMPLETED round.

    Using the per-seed last round (not the global maximum) is what keeps a
    paused/faulted campaign in the statistics with its last valid posterior
    instead of silently vanishing (survivorship bias)."""
    s_rows = [r for r in rows if r["scenario"] == scenario
              and r["strategy"] == strategy]
    out = []
    for seed in sorted({r["seed"] for r in s_rows}):
        seed_rows = [r for r in s_rows if r["seed"] == seed]
        out.append(max(seed_rows, key=lambda r: int(r["round"])))
    return out


def summarize_final(rows: List[Dict], scenario: str,
                    metrics: Sequence[str] = ("param_err_pct",
                                              "blind_rmse_M")) -> List[Dict]:
    """Last-valid-round distributional summary per strategy: median, IQR,
    mean, bootstrap 95% CI of the median (paused campaigns retained)."""
    sc = [r for r in rows if r["scenario"] == scenario]
    out = []
    for strat in sorted({r["strategy"] for r in sc}):
        fr = last_valid_rows(rows, scenario, strat)
        n_partial = sum(1 for r in fr
                        if "MEASUREMENT_FAULT" in str(r.get("stop_reason", "")))
        rec = {"scenario": scenario, "strategy": strat, "n_seeds": len(fr),
               "n_faulted": n_partial,
               "median_rounds": float(np.median([int(r["round"])
                                                 for r in fr])) if fr else 0.0}
        for m in metrics:
            x = np.array([r[m] for r in fr if np.isfinite(r.get(m, np.nan))])
            if len(x) == 0:
                continue
            lo, hi = _boot_ci(x)
            rec.update({f"{m}_median": float(np.median(x)),
                        f"{m}_iqr_lo": float(np.quantile(x, 0.25)),
                        f"{m}_iqr_hi": float(np.quantile(x, 0.75)),
                        f"{m}_mean": float(np.mean(x)),
                        f"{m}_bootci_lo": lo, f"{m}_bootci_hi": hi})
        out.append(rec)
    return out


def paired_comparison(rows: List[Dict], scenario: str, strat_a: str,
                      strat_b: str, metric: str = "blind_rmse_M") -> Dict:
    """Common-random-number PAIRED comparison of two strategies at the
    final round: per-seed differences, bootstrap CI of the median
    difference, and P(a better than b)."""
    per_seed: Dict = {}
    for strat in (strat_a, strat_b):
        for r in last_valid_rows(rows, scenario, strat):
            per_seed.setdefault(r["seed"], {})[strat] = r.get(metric)
    # COMMON seeds only, explicitly identified (paired CRN comparison)
    diffs = [v[strat_a] - v[strat_b] for v in per_seed.values()
             if strat_a in v and strat_b in v
             and np.isfinite(v[strat_a]) and np.isfinite(v[strat_b])]
    if not diffs:
        return {}
    d = np.array(diffs)
    lo, hi = _boot_ci(d)
    return {"scenario": scenario, "a": strat_a, "b": strat_b,
            "metric": metric, "n_pairs": len(d),
            "median_diff": float(np.median(d)),
            "bootci_lo": lo, "bootci_hi": hi,
            "p_a_better": float(np.mean(d < 0.0))}


# ------------------------------------------------------------------------- #
def governor_task(scenario_name: str, seed: int, budget: int):
    """First round at which the governor declares MODEL_INADEQUATE, or None.

    The parallel unit of the governor validation, and like `campaign_task` a
    picklable pure function of its arguments returning a primitive."""
    res, _lab, _gov = run_one_campaign(SCENARIOS[scenario_name], "F", seed,
                                       budget, verbose=False)
    rd = next((r.round for r in res.history
               if r.governor and r.governor.state
               == GovernorState.MODEL_INADEQUATE), None)
    return None if rd is None else int(rd)


def governor_mc_validation(seeds: Sequence[int], budget: int = 6,
                           verbose: bool = False, progress=None,
                           executor=None) -> Dict:
    """Monte Carlo validation of the governor (#calibration honesty):

      * correct-family scenario (S2-style)  -> realized campaign-level
        false-inadequacy rate;
      * wrong-family scenario (S5)          -> detection probability and
        the distribution of first-detection rounds.

    The rates REPORTED here are the empirically measured ones; no exact
    false-positive control is claimed beyond them.

    `executor`: optional process pool.  Both halves are submitted as one
    batch so a pool never idles between them, and `ordered_map` restores
    seed order, so `detection_rounds` is listed in the same order a serial
    run would have produced."""
    seeds = list(seeds)
    n = len(seeds)

    def _landed(_i, args, _out):
        scen, seed, b = args
        if progress is not None:
            progress("governor-MC",
                     "well-specified" if scen == "S2_nmr" else "misspecified",
                     seed, b)

    tasks = ([("S2_nmr", s, budget) for s in seeds]
             + [("S5_inadequacy", s, budget) for s in seeds])
    out = par.ordered_map(governor_task, tasks, executor=executor,
                          on_result=_landed)
    fp_rounds, det_rounds_all = out[:n], out[n:]

    fp = sum(1 for rd in fp_rounds if rd is not None)
    det_rounds = [rd for rd in det_rounds_all if rd is not None]
    detected = len(det_rounds)
    if verbose:
        for label, got in (("correct-family", fp_rounds),
                           ("misspecified", det_rounds_all)):
            for seed, rd in zip(seeds, got):
                verdict = "no flag" if rd is None else f"flagged at round {rd}"
                print(f"    governor-MC {label} seed {seed}: {verdict}")
    return {"n_seeds": n,
            "false_inadequacy_campaign_rate": fp / n,
            "detection_probability": detected / n,
            "detection_rounds": det_rounds,
            "median_detection_round": (float(np.median(det_rounds))
                                       if det_rounds else None)}
