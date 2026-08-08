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
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field, replace
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
from .resources import ResourceCosts, ResourceMeter
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

# predetermined BLIND validation set - never visible to any controller
VALIDATION_CONDS = [
    OperatingConditions(70.0, 0.35, 0.35, 1.0, 0.8),
    OperatingConditions(110.0, 1.5, 1.5, 1.0, 0.6),
    OperatingConditions(150.0, 0.5, 0.5, 1.0, 1.0),
    OperatingConditions(50.0, 3.0, 3.0, 1.0, 1.0),
]

TRANSFER_TRUE = TransferConfig(
    enabled=True, Q_sample_mL_min=0.5, V_fixed_mL=0.15, geometry="constant",
    rtd="gamma", n_tanks=4.0, n_quad=5, react_in_line=True,
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
    resource_costs: ResourceCosts = ResourceCosts()
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
             costs: Optional[ResourceCosts] = None
             ) -> AdvancedVirtualLaboratory:
    truth_bridge = Layer1Bridge(GEOMETRY, T_REF_C + 273.15,
                                activity_model="pitzer")
    return AdvancedVirtualLaboratory(
        spec.truth, truth_bridge,
        InstrumentConfig(observation_mode=spec.observation_mode,
                         nmr_mode=spec.nmr_mode,
                         store_spectra=store_spectra),
        ACQ, NMR_NUISANCE_TRUE, spec.transfer,
        costs if costs is not None else spec.resource_costs,
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


_SCREEN_CACHE: Dict[int, Tuple[str, ...]] = {}


def screened_dropped_keys(budget: int) -> Tuple[str, ...]:
    """Pre-campaign identifiability screen (same code as
    run_sdl_campaign.py), computed once per budget and applied identically
    to every strategy."""
    if budget not in _SCREEN_CACHE:
        t_ref_K = T_REF_C + 273.15
        bridge = Layer1Bridge(GEOMETRY, t_ref_K, activity_model="pitzer")
        space = ParameterSpace(t_ref_K=t_ref_K,
                               initial_guess=literature_guess(t_ref_K))
        ports = fixed_equal_positions(GEOMETRY["length_m"], N_PORTS)
        sr = screen(space, bridge, NOISE_DIRECT,
                    build_candidates(DESIGN) + reference_design(DESIGN),
                    ports, SPECIES, budget=budget, max_rel_ci_pct=200.0)
        _SCREEN_CACHE[budget] = sr.dropped
        if sr.dropped:
            print(f"  identifiability screen: holding fixed {sr.dropped}")
    return _SCREEN_CACHE[budget]


def _spatial_cfg(mode: str) -> SpatialDesignConfig:
    return SpatialDesignConfig(
        mode=mode, n_positions=N_PORTS, candidate_grid_size=41,
        z_min_fraction=0.02, z_max_fraction=1.0, min_spacing_fraction=0.02,
        continuous_refinement=False,
        allow_profile_early_stop=(mode == "adaptive_sequential"))


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
                           v_per_m_mL=cfg.v_per_m_mL, length_m=length_m)


def run_one_campaign(spec: ScenarioSpec, strategy: str, seed: int,
                     budget: int, verbose: bool = False,
                     store_spectra: bool = False):
    """One (scenario, strategy, seed) campaign.  Returns (result, lab,
    extra)."""
    t_ref_K = T_REF_C + 273.15
    variant = spec.f_variants.get(strategy, {})
    lab = make_lab(spec, seed, store_spectra=store_spectra,
                   costs=variant.get("costs"))
    ports = fixed_equal_positions(lab.length_m, N_PORTS)
    candidates = build_candidates(DESIGN)
    fixed = build_fixed_design(DESIGN, budget=budget)
    guess = literature_guess(t_ref_K, "H2SO4")
    dropped = screened_dropped_keys(budget)

    if strategy in ("A", "B", "C", "D"):
        bkw = dict(activity_model="pitzer", **spec.baseline_bridge_kwargs)
        bridge = Layer1Bridge(GEOMETRY, t_ref_K, **bkw)
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
            criterion="D") if strategy in ("C", "D") else None
        res = run_strategy(strategy, adapter, inference, fixed, selector,
                           budget=budget, verbose=verbose)
        return res, lab, adapter

    if strategy == "E":
        bridge = Layer1Bridge(GEOMETRY, t_ref_K, activity_model="pitzer")
        space = ParameterSpace(t_ref_K=t_ref_K, initial_guess=dict(guess))
        if dropped:
            space = space.holding_fixed(list(dropped))
        inference = InferenceModel(space, bridge, NOISE_DIRECT)
        res = run_strategy_e(lab, inference, candidates, fixed[0],
                             _spatial_cfg("optimized"), budget,
                             verbose=verbose)
        return res, lab, None

    # F and its variants -------------------------------------------------- #
    transport_aware = variant.get("transport_aware",
                                  spec.transfer.enabled)
    assumed = (_assumed_transfer_from(spec.transfer, lab.length_m)
               if transport_aware else AssumedTransfer(enabled=False))
    family = build_egda_family(GEOMETRY, t_ref_K, include=spec.family,
                               noise_assumed=NOISE_DIRECT,
                               fixed={k: guess[k] for k in dropped},
                               assumed_transfer=assumed)
    ensemble = ModelEnsemble(family)
    # kappa: NMR scenarios declare floor-level quantification systematics in
    # Sigma_y; the governor's nulls are widened by exactly that allowance
    # (0 for direct observation -> exact nulls)
    # kappa is DERIVED from the measured held-out validation coverage, not
    # tuned: suite B (reachable reaction compositions) shows the calibrated
    # Sigma_y is understated by a factor r (median r = 1.6 from coverages
    # 0.73-0.89 via 2*Phi(1.96/r) - 1 = coverage), so the governor must
    # tolerate a bounded measurement systematic of that size:
    #     kappa = sqrt(r^2 - 1) ~ 1.25
    # Re-derive whenever the NMR calibration changes.  kappa = 0 for direct
    # observation, where Sigma is exact by construction.
    governor = AdequacyGovernor(GovernorConfig(
        n_rounds_planned=budget,
        systematic_allowance=(1.25 if spec.observation_mode == "nmr"
                              else 0.0)))
    cov_model = None
    if spec.observation_mode == "nmr" \
            and variant.get("expected_cov", "spectral") == "spectral":
        cov_model = SpectralCovarianceModel(SpectralFitter(ACQ))
    spatial_mode = variant.get("spatial_mode", "optimized")
    design_cfg = AdvancedDesignConfig(
        top_k=3, n_particles=16, n_outer=24,
        objective=variant.get("objective", "parameter"))
    res = run_strategy_f(
        lab, ensemble, candidates, fixed[0], _spatial_cfg(spatial_mode),
        budget, design_cfg=design_cfg, governor=governor,
        use_governor=variant.get("use_governor", True),
        cov_model=cov_model,
        qc=QCGateConfig(enabled=spec.observation_mode == "nmr"),
        bounds=DESIGN["continuous_bounds"], seed=seed, verbose=verbose,
        key=strategy)
    return res, lab, governor


# ------------------------------------------------------------------------- #
def _truth_prediction(truth: Dict[str, float],
                      z_val: np.ndarray) -> np.ndarray:
    bridge = Layer1Bridge(GEOMETRY, T_REF_C + 273.15, activity_model="pitzer")
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
                blind_rmse_M=blind_rmse(inf.bridge, inf.space,
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
            blind_rmse_M=blind_rmse(bridge, space,
                                    space.to_vector(rec.theta_nat),
                                    z_val, y_true),
            **{k: rec.resources.get(k, 0.0)
               for k in ResourceMeter.TOTAL_KEYS}))
        prows.extend(_param_rows(spec, strategy, None, rec.round, space,
                                 rec.theta_nat, sig, rec.bound_active,
                                 truth))
    return rows, prows


# ------------------------------------------------------------------------- #
def run_scenario(spec: ScenarioSpec, seeds: Sequence[int], budget: int,
                 verbose: bool = False
                 ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Returns (round rows, per-parameter rows, per-campaign status rows).

    NO campaign is ever dropped: a run that PAUSES on a measurement fault
    keeps its completed rounds (its last valid posterior is the final row
    for that seed) and is recorded in the status table with its completion
    flag, fault counts and stop reason - so accuracy statistics and
    completion/fault rates are reported side by side (no survivorship
    bias)."""
    budget = spec.budget_override or budget
    z_val = np.array([GEOMETRY["length_m"] / 3.0, GEOMETRY["length_m"]])
    y_true = _truth_prediction(spec.truth, z_val)
    rows, prows, status = [], [], []
    for strategy in spec.strategies:
        for seed in seeds:
            t0 = time.time()
            res, lab, extra = run_one_campaign(spec, strategy, seed, budget,
                                               verbose=verbose)
            r, p = _round_metrics(spec, strategy, res, lab, extra, z_val,
                                  y_true)
            rows.extend([dict(x, seed=seed) for x in r])
            prows.extend([dict(x, seed=seed) for x in p])
            stop = getattr(res, "stop_reason", "budget exhausted")
            tot = lab.meter.totals()
            status.append({
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
                "runtime_s": time.time() - t0,
            })
            if verbose:
                print(f"    {spec.name}/{strategy}/seed{seed}: "
                      f"{time.time() - t0:.1f} s"
                      + ("" if len(r) >= budget
                         else f"  [PAUSED after {len(r)}/{budget} rounds]"))
    return rows, prows, status


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
def governor_mc_validation(seeds: Sequence[int], budget: int = 6,
                           verbose: bool = False) -> Dict:
    """Monte Carlo validation of the governor (#calibration honesty):

      * correct-family scenario (S2-style)  -> realized campaign-level
        false-inadequacy rate;
      * wrong-family scenario (S5)          -> detection probability and
        the distribution of first-detection rounds.

    The rates REPORTED here are the empirically measured ones; no exact
    false-positive control is claimed beyond them."""
    fp = 0
    det_rounds = []
    for seed in seeds:
        res, _, gov = run_one_campaign(SCENARIOS["S2_nmr"], "F", seed,
                                       budget, verbose=False)
        if any(r.governor and r.governor.state
               == GovernorState.MODEL_INADEQUATE for r in res.history):
            fp += 1
        if verbose:
            print(f"    governor-MC correct-family seed {seed}: "
                  f"{'FP' if fp else 'ok'}")
    detected = 0
    for seed in seeds:
        res, _, gov = run_one_campaign(SCENARIOS["S5_inadequacy"], "F",
                                       seed, budget, verbose=False)
        rd = next((r.round for r in res.history
                   if r.governor and r.governor.state
                   == GovernorState.MODEL_INADEQUATE), None)
        if rd is not None:
            detected += 1
            det_rounds.append(rd)
    n = len(list(seeds))
    return {"n_seeds": n,
            "false_inadequacy_campaign_rate": fp / n,
            "detection_probability": detected / n,
            "detection_rounds": det_rounds,
            "median_detection_round": (float(np.median(det_rounds))
                                       if det_rounds else None)}
