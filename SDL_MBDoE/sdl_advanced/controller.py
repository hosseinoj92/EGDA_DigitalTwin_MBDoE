"""
Advanced closed-loop campaign controller: strategies E and F (+ ablations).

    E   optimized spatial positions + the CURRENT FIM/D-optimal MBDoE
        (baseline InferenceModel/MBDoESelector, direct concentration
        observation) - isolates the value of WHERE you sample.
    F   optimized/adaptive spatial positions + Bayesian multi-model,
        resource-aware EIG design + realistic NMR/transport observation
        + the model-inadequacy governor.

Ablations of F are expressed through the lab/flags the caller passes in
(benchmark.py builds them):

    F-noNMR       lab.observation_mode='direct'  (ideal conc. observation)
    F-noTransport transfer.enabled=False
    F-noGovernor  use_governor=False
    F-full        everything on

FIREWALL: this module only ever touches lab.run_profile() and the resulting
Measurement objects.  Baseline strategies A-D remain in sdl.campaign,
untouched.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from sdl.design import MBDoESelector
from sdl.inference import InferenceModel
from sdl.layer1_bridge import OperatingConditions
from sdl.observation import NoiseModel

from .adequacy import AdequacyGovernor, AdequacyReport, GovernorState
from .bayes_design import (AdvancedDesignConfig, AdvancedSelector,
                           DesignDecision, NoiseSurrogate)
from .instrument import AdvancedVirtualLaboratory
from .model_ensemble import ModelEnsemble
from .spatial_design import (SensitivityField, SpatialDesignConfig,
                             SpatialDesigner, fixed_equal_positions)

ADV_STRATEGY_NAMES = {
    "E": "optimized spatial + FIM MBDoE",
    "F": "adaptive spatial + Bayesian multi-model + realistic NMR/transport",
}


@dataclass
class AdvRoundRecord:
    round: int
    u: OperatingConditions
    z_positions: np.ndarray
    theta_nat: Dict[str, float]           # best model's MAP, natural units
    best_model: str
    model_probs: Dict[str, float]
    governor: Optional[AdequacyReport]
    resources: Dict[str, float]           # cumulative totals after the round
    n_data: int
    design_mode: str = "fim"              # fim | eig | diagnostic | fixed
    eig_param: float = float("nan")
    eig_model: float = float("nan")
    sigma_scaled: Optional[np.ndarray] = None


@dataclass
class AdvancedStrategyResult:
    key: str
    history: List[AdvRoundRecord] = field(default_factory=list)
    ensemble: Optional[ModelEnsemble] = None
    inference: Optional[InferenceModel] = None
    runtime_s: float = 0.0


# --------------------------------------------------------------------------- #
def _noise_cov_builder(noise: NoiseModel, species: Sequence[str]):
    def cov_at(y_pos: np.ndarray) -> np.ndarray:
        return noise.covariance(y_pos, tuple(species), 1)
    return cov_at


def run_strategy_e(lab: AdvancedVirtualLaboratory,
                   inference: InferenceModel,
                   candidates: List[OperatingConditions],
                   first_u: OperatingConditions,
                   spatial_cfg: SpatialDesignConfig,
                   budget: int,
                   mbdoe_criterion: str = "D",
                   continuous_bounds: Optional[Dict] = None,
                   verbose: bool = True) -> AdvancedStrategyResult:
    """E: baseline WLS/FIM inference + baseline condition MBDoE, but the
    POSITIONS each round are the greedy incremental D-optimal set."""
    t0 = time.time()
    result = AdvancedStrategyResult(key="E", inference=inference)
    L = lab.length_m
    designer = SpatialDesigner(
        spatial_cfg, L, _noise_cov_builder(inference.noise, lab.species))

    def field_for(u: OperatingConditions) -> SensitivityField:
        def predict(th, z):
            return inference.bridge.concentrations_at(
                inference.space.to_natural(th), u, z, lab.species)
        return SensitivityField(predict, inference.theta,
                                inference.space.fd_steps,
                                designer.candidate_grid(), len(lab.species))

    u_next = first_u
    z_next = fixed_equal_positions(L, spatial_cfg.n_positions)
    for r in range(1, budget + 1):
        if r > 1 or spatial_cfg.mode != "fixed_equal":
            F0 = inference.fisher_information()
            z_next = designer.positions(field_for(u_next), F0)
        meas = lab.run_profile(u_next, z_next)
        inference.add_measurement(meas)
        inference.fit()
        rep = inference.uncertainty()
        result.history.append(AdvRoundRecord(
            round=r, u=u_next, z_positions=np.asarray(z_next),
            theta_nat=inference.space.to_natural(inference.theta),
            best_model="wls", model_probs={"wls": 1.0}, governor=None,
            resources=lab.meter.totals(), n_data=inference.n_data,
            design_mode="fim", sigma_scaled=rep.sigma))
        if verbose:
            print(f"  [E] round {r}/{budget}  {u_next.label():34s} "
                  f"z/L={np.round(np.asarray(z_next) / L, 3)} "
                  f"maxCI={rep.max_rel_ci_pct:7.1f}%")
        if r == budget:
            break
        selector = MBDoESelector(
            inference=inference, candidates=candidates, spatial=True,
            ports_z_m=np.asarray(z_next), outlet_z_m=np.array([L]),
            species=lab.species, criterion=mbdoe_criterion,
            continuous=continuous_bounds is not None,
            continuous_bounds=continuous_bounds)
        u_next = selector.select()
    result.runtime_s = time.time() - t0
    return result


# --------------------------------------------------------------------------- #
def run_strategy_f(lab: AdvancedVirtualLaboratory,
                   ensemble: ModelEnsemble,
                   candidates: List[OperatingConditions],
                   first_u: OperatingConditions,
                   spatial_cfg: SpatialDesignConfig,
                   budget: int,
                   design_cfg: AdvancedDesignConfig = AdvancedDesignConfig(),
                   governor: Optional[AdequacyGovernor] = None,
                   use_governor: bool = True,
                   surrogate: Optional[NoiseSurrogate] = None,
                   bounds: Optional[Dict] = None,
                   seed: int = 0,
                   verbose: bool = True,
                   key: str = "F") -> AdvancedStrategyResult:
    """F: the full advanced loop (see module docstring)."""
    t0 = time.time()
    result = AdvancedStrategyResult(key=key, ensemble=ensemble)
    governor = governor or AdequacyGovernor()
    surrogate = surrogate or NoiseSurrogate(lab.species)
    L = lab.length_m
    designer = SpatialDesigner(spatial_cfg, L, surrogate.cov_at)
    selector = AdvancedSelector(ensemble, candidates, designer, surrogate,
                                lab.meter, lab.species, design_cfg,
                                bounds=bounds, seed=seed)
    state = GovernorState.NORMAL_LEARNING
    decision: Optional[DesignDecision] = None
    u_next = first_u
    for r in range(1, budget + 1):
        # ---- spatial measurement set for this condition ----------------- #
        if spatial_cfg.mode == "adaptive_sequential" and r > 1:
            meas = _adaptive_profile(lab, ensemble, designer, u_next,
                                     spatial_cfg, surrogate)
        else:
            if decision is not None:
                zs = decision.z_positions
            elif spatial_cfg.mode == "fixed_equal":
                zs = fixed_equal_positions(L, spatial_cfg.n_positions)
            else:
                zs = _initial_positions(ensemble, designer, u_next,
                                        lab.species)
            meas = lab.run_profile(u_next, zs)
        surrogate.observe(meas)
        ensemble.add_measurement(meas)
        ensemble.update()
        gov_rep = governor.assess(ensemble, r)
        state = gov_rep.state if use_governor \
            else GovernorState.NORMAL_LEARNING
        best = ensemble.best
        result.history.append(AdvRoundRecord(
            round=r, u=u_next, z_positions=np.asarray(meas.z_m),
            theta_nat=best.space.to_natural(best.posterior.theta_map),
            best_model=best.name,
            model_probs={cm.name: float(p) for cm, p
                         in zip(ensemble.models, ensemble.probs)},
            governor=gov_rep, resources=lab.meter.totals(),
            n_data=sum(m.size for m in best.inference.measurements),
            design_mode=decision.mode if decision else "seed",
            eig_param=decision.eig_param if decision else float("nan"),
            eig_model=decision.eig_model if decision else float("nan"),
            sigma_scaled=np.sqrt(np.maximum(
                np.diag(best.posterior.cov), 0.0))))
        if verbose:
            probs = " ".join(f"{cm.name}={p:.2f}" for cm, p
                             in zip(ensemble.models, ensemble.probs))
            print(f"  [{key}] round {r}/{budget}  {u_next.label():34s} "
                  f"n_z={meas.n_z}  {gov_rep.state:20s} {probs}")
        if r == budget:
            break
        decision = selector.select(state)
        u_next = decision.u
    result.runtime_s = time.time() - t0
    return result


# --------------------------------------------------------------------------- #
def _initial_positions(ensemble: ModelEnsemble, designer: SpatialDesigner,
                       u: OperatingConditions,
                       species: Sequence[str]) -> np.ndarray:
    cm = ensemble.best
    theta = (cm.posterior.theta_map if cm.posterior.theta_map is not None
             else cm.space.to_vector(cm.space.initial_guess))

    def predict(th, z):
        return cm.bridge.concentrations_at(cm.space.to_natural(th), u, z,
                                           tuple(species))

    field = SensitivityField(predict, theta, cm.space.fd_steps,
                             designer.candidate_grid(), len(species))
    p = cm.space.n_params
    return designer.positions(field, np.zeros((p, p)))


def _adaptive_profile(lab: AdvancedVirtualLaboratory,
                      ensemble: ModelEnsemble, designer: SpatialDesigner,
                      u: OperatingConditions, cfg: SpatialDesignConfig,
                      surrogate: NoiseSurrogate):
    """Measure one position at a time at the SAME condition; stop when the
    expected marginal information per acquisition falls below the
    threshold or n_positions is reached.  The between-acquisition update is
    the (cheap) FIM update; the full Bayesian update runs once per round."""
    cm = ensemble.best
    theta = cm.posterior.theta_map

    def predict(th, z):
        return cm.bridge.concentrations_at(cm.space.to_natural(th), u, z,
                                           tuple(lab.species))

    field = SensitivityField(predict, theta, cm.space.fd_steps,
                             designer.candidate_grid(), len(lab.species))
    F = cm.inference.fisher_information(theta)
    chosen: List[float] = []
    parts = []
    while len(chosen) < cfg.n_positions:
        z_next, gain = designer.next_position(field, F, chosen)
        if z_next is None:
            break
        if chosen and cfg.allow_profile_early_stop \
                and gain < cfg.marginal_information_threshold:
            break
        m = lab.run_profile(u, [z_next])
        parts.append(m)
        chosen.append(float(z_next))
        F = F + designer._fim_at(field, float(z_next))
    # merge the single-z measurements into one species-major Measurement
    from sdl.observation import Measurement
    n_s, n_z = len(lab.species), len(parts)
    y = np.zeros(n_s * n_z)
    cov = np.zeros((n_s * n_z, n_s * n_z))
    qc = []
    have_cov = all(m.cov_y is not None for m in parts)
    for k, m in enumerate(parts):
        for i in range(n_s):
            y[i * n_z + k] = m.y[i]
            if have_cov:
                for j in range(n_s):
                    cov[i * n_z + k, j * n_z + k] = m.cov_y[i, j]
        qc.extend((m.meta or {}).get("qc", []))
    return Measurement(u=u, z_m=np.array(chosen), species=lab.species, y=y,
                       cov_y=cov if have_cov else None,
                       meta={"qc": qc, "adaptive": True})


# --------------------------------------------------------------------------- #
def run_advanced_strategy(key: str, **kwargs) -> AdvancedStrategyResult:
    """Dispatch: key 'E' -> run_strategy_e, 'F*' -> run_strategy_f."""
    if key == "E":
        return run_strategy_e(**kwargs)
    if key.startswith("F"):
        return run_strategy_f(key=key, **kwargs)
    raise ValueError(f"Unknown advanced strategy '{key}' (A-D live in "
                     f"sdl.campaign).")
