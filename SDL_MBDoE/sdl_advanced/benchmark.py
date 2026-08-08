"""
Reproducible Monte Carlo benchmark of strategies A-F on the EGDA/H2SO4
system (scenarios 1-6 of the concept document).

FAIRNESS RULES implemented here:

  * every strategy in a scenario faces the SAME AdvancedVirtualLaboratory
    physics (identical observation pathway, transport truth, noise class),
    differing only in what the controller/inference is allowed to assume;
  * baselines A-D run UNCHANGED sdl.campaign.run_strategy code through a
    thin adapter around the advanced instrument (their measurements have
    cov_y stripped, reproducing the legacy assumed-NoiseModel behaviour);
  * resources are metered identically for all strategies from the same
    event log, so results can be reported BOTH per reactor condition and
    per actual measurement/resource budget;
  * hidden truth is revealed only in the post-campaign scoring below.

Scenario -> strategy map (see SCENARIOS):

  S1_ideal      correct model, ideal direct observation, no transport
  S2_nmr        realistic spectra + deconvolution covariance
  S3_transport  + position delay, RTD, in-line reaction, carryover
  S4_ambiguity  multi-model truth-recovery (Bayesian discrimination)
  S5_inadequacy correct model REMOVED from the candidate family
  S6_resources  resource-aware vs pure-information design
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

from .adequacy import AdequacyGovernor, GovernorConfig
from .bayes_design import AdvancedDesignConfig
from .controller import (AdvancedStrategyResult, run_strategy_e,
                         run_strategy_f)
from .instrument import (AdvancedVirtualLaboratory, InstrumentConfig)
from .model_ensemble import (ModelEnsemble, TransportAwareInference,
                             build_egda_family)
from .resources import ResourceCosts, ResourceMeter
from .spatial_design import SpatialDesignConfig, fixed_equal_positions
from .spectral import AcquisitionSettings, SpectralNuisance
from .transfer import TransferConfig

# ------------------------------------------------------------------------- #
# Shared benchmark configuration (single source; runners may override)
# ------------------------------------------------------------------------- #
GEOMETRY = {"length_m": 0.06, "diameter_m": 0.004}     # Layer-1 base case
T_REF_C = 60.0
TRUTH = {"k1_ref": 1.00e-3, "Ea1_J": 40_000.0,          # run_sdl_campaign's
         "k2_ref": 6.50e-4, "Ea2_J": 48_000.0,          # hidden truth
         "K1_ref": 0.90, "K2_ref": 0.07}
SPECIES = ("EGDA", "EGMA", "EG", "AcOH")
N_PORTS = 10

DESIGN = {  # coarser than run_sdl_campaign (benchmark tractability)
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

NMR_NUISANCE_TRUE = SpectralNuisance(     # ASSUMED plausible imperfections
    noise_sigma=0.10, shift_drift_ppm=0.004, shift_jitter_ppm=0.001,
    linewidth_rel_sigma=0.08, baseline_offset=0.02, baseline_curve=0.03,
    phase_error_deg=2.0, gain_drift_rel_sigma=0.01,
    response_factors={"EGMA": 1.02})

ACQ = AcquisitionSettings(n_points=2048, nmr_temperature_C=27.0)
NOISE_DIRECT = NoiseModel(sigma_abs_M=0.004, sigma_rel=0.02, rho_overlap=0.3)


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
    # per-scenario hidden-truth override (Scenario 5 uses a documented
    # HYPOTHETICAL strongly reversible ester chemistry so that the removed
    # model family leaves a detectable footprint)
    truth_override: Dict[str, float] = field(default_factory=dict)

    @property
    def truth(self) -> Dict[str, float]:
        return {**TRUTH, **self.truth_override}


SCENARIOS: Dict[str, ScenarioSpec] = {
    "S1_ideal": ScenarioSpec(
        name="S1_ideal",
        description="correct model, ideal direct observation, no transport",
        strategies=("A", "B", "C", "D", "E", "F")),
    "S2_nmr": ScenarioSpec(
        name="S2_nmr",
        description="realistic Fourier-80 spectra + deconvolution",
        observation_mode="nmr", nmr_mode="realistic",
        strategies=("B", "D", "F")),
    "S3_transport": ScenarioSpec(
        name="S3_transport",
        description="NMR + transport: delay, RTD, in-line reaction, carryover",
        observation_mode="nmr", nmr_mode="realistic",
        transfer=TRANSFER_TRUE, strategies=("D", "F-uncorr", "F"),
        f_variants={"F-uncorr": {"assumed_tau": 0.0},
                    "F": {"assumed_tau": None}}),   # None -> commanded V/Q
    "S4_ambiguity": ScenarioSpec(
        name="S4_ambiguity",
        description="Bayesian model discrimination (reversible truth)",
        observation_mode="nmr", nmr_mode="realistic",
        family=("rev-pitzer", "rev-dilute", "irreversible"),
        strategies=("D", "F"), track_correct_model="rev-pitzer"),
    "S5_inadequacy": ScenarioSpec(
        name="S5_inadequacy",
        description="correct model removed from the candidate family "
                    "(truth: documented hypothetical strongly reversible "
                    "ester, K1=0.30, K2=0.02)",
        observation_mode="nmr", nmr_mode="realistic",
        family=("irreversible",),
        strategies=("D", "F-noGovernor", "F"),
        baseline_bridge_kwargs={"reversible": False},
        f_variants={"F-noGovernor": {"use_governor": False}, "F": {}},
        truth_override={"K1_ref": 0.30, "K2_ref": 0.02}),
    "S6_resources": ScenarioSpec(
        name="S6_resources",
        description="resource-aware vs pure-information design",
        observation_mode="nmr", nmr_mode="realistic",
        strategies=("D", "F", "F-resource"),
        resource_costs=ResourceCosts(),
        f_variants={"F": {},
                    "F-resource": {"costs": ResourceCosts(
                        lambda_time_per_s=2e-3, lambda_material_per_mol=50.0,
                        lambda_waste_per_mL=5e-3, lambda_energy_per_kJ=0.05,
                        lambda_switch=1.0, lambda_motion_per_m=2.0)}}),
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
             store_spectra: bool = False) -> AdvancedVirtualLaboratory:
    truth_bridge = Layer1Bridge(GEOMETRY, T_REF_C + 273.15,
                                activity_model="pitzer")
    return AdvancedVirtualLaboratory(
        spec.truth, truth_bridge,
        InstrumentConfig(observation_mode=spec.observation_mode,
                         nmr_mode=spec.nmr_mode,
                         store_spectra=store_spectra),
        ACQ, NMR_NUISANCE_TRUE, spec.transfer, spec.resource_costs,
        seed=seed, noise_direct=NOISE_DIRECT)


_SCREEN_CACHE: Dict[int, Tuple[str, ...]] = {}


def screened_dropped_keys(budget: int) -> Tuple[str, ...]:
    """Pre-campaign identifiability screen (same philosophy and code as
    run_sdl_campaign.py), computed once per budget and applied identically
    to every strategy so the comparison stays like-for-like."""
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
        continuous_refinement=False)


def run_one_campaign(spec: ScenarioSpec, strategy: str, seed: int,
                     budget: int, verbose: bool = False,
                     store_spectra: bool = False):
    """One (scenario, strategy, seed) campaign.  Returns (result, lab)."""
    t_ref_K = T_REF_C + 273.15
    lab = make_lab(spec, seed, store_spectra=store_spectra)
    ports = fixed_equal_positions(lab.length_m, N_PORTS)
    candidates = build_candidates(DESIGN)
    fixed = build_fixed_design(DESIGN, budget=budget)
    guess = literature_guess(t_ref_K, "H2SO4")
    variant = spec.f_variants.get(strategy, {})

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
    assumed_tau = variant.get("assumed_tau", 0.0)
    if assumed_tau is None:            # transport-aware: commanded V/Q delay
        assumed_tau = spec.transfer.mean_tau_s(lab.length_m / 2.0,
                                               lab.length_m)
    costs = variant.get("costs", spec.resource_costs)
    if costs is not spec.resource_costs:
        lab.meter.costs = costs        # design-side lambdas; same accounting
    family = build_egda_family(GEOMETRY, t_ref_K, include=spec.family,
                               noise_assumed=NOISE_DIRECT,
                               fixed={k: guess[k] for k in dropped},
                               assumed_extra_tau_s=float(assumed_tau))
    ensemble = ModelEnsemble(family)
    governor = AdequacyGovernor(GovernorConfig())
    res = run_strategy_f(
        lab, ensemble, candidates, fixed[0], _spatial_cfg("optimized"),
        budget,
        design_cfg=AdvancedDesignConfig(top_k=3, n_particles=16, n_outer=24),
        governor=governor,
        use_governor=variant.get("use_governor", True),
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
    nat = space.to_natural(theta_vec)
    y = np.concatenate([bridge.concentrations_at(nat, u, z_val, SPECIES)
                        for u in VALIDATION_CONDS])
    return float(np.sqrt(np.mean((y - y_true) ** 2)))


def _round_metrics(spec: ScenarioSpec, strategy: str, res, lab, extra,
                   z_val: np.ndarray, y_true: np.ndarray) -> List[Dict]:
    """Per-round metric rows for one campaign (truth used HERE only)."""
    truth = spec.truth
    rows = []
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
                p_correct=float("nan"),
                gov_state="", gov_score=float("nan"),
                blind_rmse_M=blind_rmse(inf.bridge, inf.space,
                                        inf.space.to_vector(rec.theta_nat),
                                        z_val, y_true),
                **{k: tot.get(k, 0.0) for k in ResourceMeter.TOTAL_KEYS}))
        return rows
    # E and F variants ---------------------------------------------------- #
    for rec in res.history:
        if res.ensemble is not None:
            cm = res.ensemble.models[[c.name for c in res.ensemble.models]
                                     .index(rec.best_model)] \
                if rec.best_model != "wls" else None
        else:
            cm = None
        if cm is not None:
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
            p_correct=p_corr,
            gov_state=(rec.governor.state if rec.governor else ""),
            gov_score=(rec.governor.score if rec.governor else float("nan")),
            blind_rmse_M=blind_rmse(bridge, space,
                                    space.to_vector(rec.theta_nat),
                                    z_val, y_true),
            **{k: rec.resources.get(k, 0.0)
               for k in ResourceMeter.TOTAL_KEYS}))
    return rows


# ------------------------------------------------------------------------- #
def run_scenario(spec: ScenarioSpec, seeds: Sequence[int], budget: int,
                 verbose: bool = False) -> List[Dict]:
    z_val = np.array([GEOMETRY["length_m"] / 3.0, GEOMETRY["length_m"]])
    y_true = _truth_prediction(spec.truth, z_val)
    rows: List[Dict] = []
    for strategy in spec.strategies:
        for seed in seeds:
            t0 = time.time()
            res, lab, extra = run_one_campaign(spec, strategy, seed, budget,
                                               verbose=verbose)
            rows.extend([dict(r, seed=seed)
                         for r in _round_metrics(spec, strategy, res, lab,
                                                 extra, z_val, y_true)])
            if verbose:
                print(f"    {spec.name}/{strategy}/seed{seed}: "
                      f"{time.time() - t0:.1f} s")
    return rows
