"""
Advanced closed-loop campaign controller: strategies E and F (+ ablations).

    E   optimized spatial positions + the CURRENT FIM/D-optimal MBDoE
        (baseline InferenceModel/MBDoESelector, direct concentration
        observation) - isolates the value of WHERE you sample.
    F   optimized/adaptive spatial positions + Bayesian multi-model,
        resource-aware EIG design + realistic NMR/transport observation
        + the model-inadequacy governor + the measurement-fault QC gate.

Ablations of F are expressed through the lab/flags the caller passes in
(benchmark.py builds them):

    F-noNMR       lab.observation_mode='direct'  (ideal conc. observation)
    F-noTransport transfer.enabled=False
    F-noGovernor  use_governor=False
    F-full        everything on

All controller-side predictions route through the models' single
expected-observation operator (`CandidateModel.predict_observation` /
`InferenceModel.predict_at`), so estimation, sensitivities, FIM, spatial
design, EIG and diagnostics are mutually consistent - including the assumed
transfer correction when configured.

QC GATE (measurement-fault handling): a spectrum whose deconvolution raises
FAIL quality flags is NEVER assimilated into the kinetic posterior.  The
controller re-acquires the same position up to `qc.max_retries` times
(metered as reacquisitions); persistently failing positions are dropped and
counted; and when the gate's policy concludes that the INSTRUMENT is broken
the campaign PAUSES safely (stop_reason='MEASUREMENT_FAULT') instead of
designing new chemistry experiments on corrupted data.  That policy is
batch-size aware (QCGateConfig / QCMonitor): a per-round rejection FRACTION
is only used where a batch is large enough for it to mean anything, and
persistent failure is detected by consecutive-rejection and rolling-window
rules that behave identically whether a round contains ten acquisitions or
one.  Single-measurement (adaptive_sequential) operation depends on that.

FIREWALL: this module only ever touches lab.run_profile() and the resulting
Measurement objects.  Baseline strategies A-D remain in sdl.campaign,
untouched.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from sdl.design import MBDoESelector
from sdl.inference import InferenceModel
from sdl.layer1_bridge import OperatingConditions
from sdl.observation import Measurement, NoiseModel

from .adequacy import AdequacyGovernor, AdequacyReport, GovernorState
from .bayes_design import (AdvancedDesignConfig, AdvancedSelector,
                           DesignDecision, NoiseSurrogate)
from .instrument import AdvancedVirtualLaboratory
from .model_ensemble import CandidateModel, ModelEnsemble
from .spatial_design import (SensitivityField, SpatialDesignConfig,
                             SpatialDesigner, fixed_equal_positions)

ADV_STRATEGY_NAMES = {
    "E": "optimized spatial + FIM MBDoE",
    "F": "adaptive spatial + Bayesian multi-model + realistic NMR/transport",
}


@dataclass(frozen=True)
class QCGateConfig:
    """When does QC rejection mean "the instrument is broken, stop"?

    The original rule was a per-round REJECTION FRACTION.  That is a
    reasonable statistic for a 10-position profile and a meaningless one for
    a single acquisition: in adaptive_sequential mode every round contains
    ONE measurement, so a single rejected spectrum gives a rejection
    fraction of 100 % and pauses the campaign.  In the archived v5
    publication run that fired on 40 of 40 F-zadaptive seeds - the adaptive
    spatial policy never completed a campaign, and the S7 comparison was
    measuring the gate, not the policy.

    The gate therefore now applies FOUR rules, and a fault is declared when
    any of them trips.  The first two are batch statistics (unchanged
    behaviour where they are meaningful); the last two are PERSISTENCE
    statistics that carry across acquisitions and rounds, so they work
    identically at any batch size - which is what makes single-measurement
    operation testable at all:

      1. `total_loss`   a batch of >= 2 positions of which NONE survived
      2. `fraction`     a batch of >= `min_batch_for_fraction` positions
                        with more than `max_reject_fraction` rejected
      3. `consecutive`  `max_consecutive_rejects` rejections in a row
      4. `window`       more than `max_rejects_in_window` rejections among
                        the last `rolling_window` acquisitions

    Rules 3 and 4 need memory, which lives in `QCMonitor` (one per campaign).
    A genuinely broken instrument fails repeatedly and trips them within a
    few acquisitions; an isolated bad spectrum does not, and the campaign
    simply samples elsewhere - which is the correct laboratory response."""
    enabled: bool = True
    max_retries: int = 1              # reacquisitions per failing position
    max_reject_fraction: float = 0.5  # batch rule (rule 2)
    #: below this batch size a rejection FRACTION carries no information
    #: (1/1 = 100 % is not evidence of anything), so rule 2 is not applied
    min_batch_for_fraction: int = 4
    #: rule 3: consecutive rejected acquisitions that mean "broken"
    max_consecutive_rejects: int = 3
    #: rule 4: rolling window over acquisitions, and how many may fail in it
    rolling_window: int = 8
    max_rejects_in_window: int = 4

    def __post_init__(self) -> None:
        if not 0.0 <= self.max_reject_fraction <= 1.0:
            raise ValueError("max_reject_fraction must lie in [0, 1].")
        if self.max_consecutive_rejects < 1:
            raise ValueError("max_consecutive_rejects must be >= 1.")
        if self.rolling_window < 1:
            raise ValueError("rolling_window must be >= 1.")
        if self.max_rejects_in_window < 0:
            raise ValueError("max_rejects_in_window must be >= 0.")


class QCGateFault(Exception):
    """Internal signal - never raised out of this module."""


class QCMonitor:
    """Per-campaign memory of acquisition dispositions (rules 3 and 4).

    Deliberately counts ACQUISITIONS, not rounds: an adaptive campaign takes
    one acquisition per round and a batch campaign takes ten, and the
    question "is the instrument working?" is about acquisitions either way.
    A successful acquisition resets the consecutive counter, because a
    spectrometer that produces a good spectrum is, at that moment, working."""

    def __init__(self, cfg: QCGateConfig):
        self.cfg = cfg
        self.consecutive_rejects = 0
        self.history: List[int] = []          # 1 = rejected, 0 = accepted
        self.n_accepted = 0
        self.n_rejected = 0
        self.trip_reason = ""

    def record(self, rejected: bool) -> None:
        self.history.append(1 if rejected else 0)
        if len(self.history) > max(self.cfg.rolling_window, 1):
            self.history.pop(0)
        if rejected:
            self.n_rejected += 1
            self.consecutive_rejects += 1
        else:
            self.n_accepted += 1
            self.consecutive_rejects = 0

    def tripped(self) -> bool:
        cfg = self.cfg
        if self.consecutive_rejects >= cfg.max_consecutive_rejects:
            self.trip_reason = (
                f"{self.consecutive_rejects} consecutive QC rejections "
                f"(limit {cfg.max_consecutive_rejects})")
            return True
        in_window = sum(self.history)
        if (len(self.history) >= cfg.rolling_window
                and in_window > cfg.max_rejects_in_window):
            self.trip_reason = (
                f"{in_window} QC rejections in the last "
                f"{len(self.history)} acquisitions "
                f"(limit {cfg.max_rejects_in_window})")
            return True
        return False

    def summary(self) -> Dict[str, float]:
        return {"qc_accepted": self.n_accepted, "qc_rejected": self.n_rejected,
                "qc_consecutive_rejects": self.consecutive_rejects,
                "qc_trip_reason": self.trip_reason}


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
    param_keys: Tuple[str, ...] = ()
    bound_active: Tuple[str, ...] = ()
    corr_max_offdiag: float = float("nan")
    n_rejected: int = 0
    n_reacquired: int = 0
    #: SNAPSHOT of the Laplace-evidence boundary diagnostics as they were AT
    #: THIS round (not the final ensemble's state)
    probs_reliable: bool = True
    evidence_reliable_by_model: Dict[str, bool] = field(default_factory=dict)
    evidence_warning: str = ""
    #: AUDIT ONLY (publication trail).  A REFERENCE to the posterior
    #: covariance/correlation the round already computed - stored, never
    #: recomputed, so keeping it cannot change a number.  None when the
    #: audit trail is off, which is the default.
    theta_cov: Optional[np.ndarray] = None
    theta_corr: Optional[np.ndarray] = None


@dataclass
class AdvancedStrategyResult:
    key: str
    history: List[AdvRoundRecord] = field(default_factory=list)
    ensemble: Optional[ModelEnsemble] = None
    inference: Optional[InferenceModel] = None
    runtime_s: float = 0.0
    stop_reason: str = "budget exhausted"


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def _noise_cov_builder(noise: NoiseModel, species: Sequence[str]):
    def cov_at(y_pos: np.ndarray) -> np.ndarray:
        return noise.covariance(y_pos, tuple(species), 1)
    return cov_at


def _field_for_model(cm: CandidateModel, u: OperatingConditions,
                     designer: SpatialDesigner,
                     species: Sequence[str]) -> SensitivityField:
    """Sensitivity field of the model's EXPECTED OBSERVATION at u."""
    def predict(th, z):
        return cm.predict_observation(th, u, z, species)
    return SensitivityField(predict, cm.theta_hat, cm.space.fd_steps,
                            designer.candidate_grid(), len(species))


def _split_positions(m: Measurement) -> List[Dict]:
    """Per-position view of a species-major Measurement."""
    n_s, n_z = len(m.species), m.n_z
    qc = (m.meta or {}).get("qc", [{} for _ in range(n_z)])
    spectra = (m.meta or {}).get("spectra")
    out = []
    for k in range(n_z):
        idx = [i * n_z + k for i in range(n_s)]
        out.append({
            "z": float(m.z_m[k]),
            "y": m.y[idx].copy(),
            "cov": (m.cov_y[np.ix_(idx, idx)].copy()
                    if m.cov_y is not None else None),
            "qc": qc[k] if k < len(qc) else {},
            "spectrum": spectra[k] if spectra and k < len(spectra) else None,
        })
    return out


def _combine_positions(u: OperatingConditions, species: Tuple[str, ...],
                       parts: List[Dict],
                       extra_meta: Optional[Dict] = None) -> Measurement:
    """Rebuild one species-major Measurement from per-position parts."""
    n_s, n_z = len(species), len(parts)
    y = np.zeros(n_s * n_z)
    have_cov = all(p["cov"] is not None for p in parts)
    cov = np.zeros((n_s * n_z, n_s * n_z)) if have_cov else None
    qc, spectra = [], []
    for k, p in enumerate(parts):
        for i in range(n_s):
            y[i * n_z + k] = p["y"][i]
            if have_cov:
                for j in range(n_s):
                    cov[i * n_z + k, j * n_z + k] = p["cov"][i, j]
        qc.append(p["qc"])
        if p["spectrum"] is not None:
            spectra.append(p["spectrum"])
    meta = {"qc": qc, **(extra_meta or {})}
    if spectra:
        meta["spectra"] = spectra
    return Measurement(u=u, z_m=np.array([p["z"] for p in parts]),
                       species=species, y=y, cov_y=cov, meta=meta)


def _qc_failed(qc_entry: Dict) -> bool:
    return any(str(f).startswith("FAIL")
               for f in qc_entry.get("qc_flags", []))


def qc_fault_verdict(n_positions: int, n_rejected: int, qc: QCGateConfig,
                     monitor: "Optional[QCMonitor]" = None
                     ) -> Tuple[bool, str]:
    """Apply the four gate rules (see QCGateConfig) and say WHICH one fired.

    Separated from the measurement loop so the policy can be unit-tested
    directly - including the case that used to be wrong, a single-position
    batch with one rejection."""
    if n_positions <= 0:
        return False, ""
    if n_positions >= 2 and n_rejected >= n_positions:
        return True, (f"total loss: all {n_positions} positions of the batch "
                      f"failed QC")
    if (n_positions >= max(int(qc.min_batch_for_fraction), 1)
            and n_rejected / n_positions > qc.max_reject_fraction):
        return True, (f"{n_rejected}/{n_positions} positions rejected "
                      f"(limit {qc.max_reject_fraction:.0%} of a batch of "
                      f"{qc.min_batch_for_fraction}+)")
    if monitor is not None and monitor.tripped():
        return True, monitor.trip_reason
    return False, ""


def measure_with_qc(lab: AdvancedVirtualLaboratory, u: OperatingConditions,
                    zs: Sequence[float], qc: QCGateConfig,
                    recorder=None, round_no: int = 0,
                    monitor: "Optional[QCMonitor]" = None
                    ) -> Tuple[Optional[Measurement], int, int, bool]:
    """Measure the positions with the QC gate applied BEFORE assimilation.

    Returns (measurement_of_passing_positions_or_None, n_rejected,
    n_reacquired, fault).  fault=True only when the gate's policy says the
    INSTRUMENT is broken (QCGateConfig) - the caller must then pause rather
    than continue designing.  An isolated rejection is not a fault: it
    returns fault=False with whatever survived, and the caller samples
    somewhere else.

    `monitor`: the campaign's QCMonitor, which carries the persistence rules
    across acquisitions and rounds.  None disables those two rules, leaving
    the batch rules - which is right for a one-off call.

    `recorder`: passive audit sink or None.  A REJECTED spectrum never
    reaches the posterior and would otherwise leave no trace beyond a
    counter, so each acquisition's disposition (accepted / reacquired /
    rejected) is reported to the sink as it is decided.  The sink is never
    consulted and draws nothing - the gate's behaviour is unchanged."""
    m = lab.run_profile(u, zs)
    if not qc.enabled or (m.meta or {}).get("observation_mode") == "direct" \
            or lab.config.observation_mode == "direct":
        if recorder is not None:
            recorder.record_acquisitions(round_no, u, m, "accepted",
                                         attempt=1)
        return m, 0, 0, False
    parts = _split_positions(m)
    kept, n_rej, n_re = [], 0, 0
    for p in parts:
        if not _qc_failed(p["qc"]):
            kept.append(p)
            if monitor is not None:
                monitor.record(False)
            if recorder is not None:
                recorder.record_acquisition_part(round_no, u, p, "accepted",
                                                 attempt=1)
            continue
        recovered = False
        for attempt in range(max(qc.max_retries, 0)):
            n_re += 1
            if recorder is not None:
                recorder.record_acquisition_part(round_no, u, p,
                                                 "failed_qc_reacquiring",
                                                 attempt=attempt + 1)
            m_re = lab.run_profile(u, [p["z"]], reacquire=True)
            p_re = _split_positions(m_re)[0]
            if not _qc_failed(p_re["qc"]):
                kept.append(p_re)
                if recorder is not None:
                    recorder.record_acquisition_part(
                        round_no, u, p_re, "accepted_after_reacquisition",
                        attempt=attempt + 2)
                recovered = True
                break
            if recorder is not None:
                recorder.record_acquisition_part(round_no, u, p_re,
                                                 "failed_qc",
                                                 attempt=attempt + 2)
        # A position that a RETRY rescued counts as a success for the
        # persistence rules: the instrument did deliver a usable spectrum.
        if monitor is not None:
            monitor.record(not recovered)
        if not recovered:
            n_rej += 1
            if recorder is not None:
                recorder.record_acquisition_part(round_no, u, p, "rejected",
                                                 attempt=0)
            lab.meter.log_qc_reject(p["z"])
    fault, _why = qc_fault_verdict(len(parts), n_rej, qc, monitor)
    if not kept:
        # No usable data from this batch.  That is NOT automatically an
        # instrument fault: for a single-acquisition batch it just means
        # "try another position", and only the policy above may pause the
        # campaign.
        return None, n_rej, n_re, fault
    kept.sort(key=lambda p: p["z"])
    return (_combine_positions(u, lab.species, kept,
                               {"observation_mode": "nmr"}),
            n_rej, n_re, fault)


def _posterior_diag(cm: CandidateModel) -> Dict:
    """Per-parameter posterior diagnostics for reporting (#13): scaled
    sigmas, active bounds, worst off-diagonal correlation."""
    sig = np.sqrt(np.maximum(np.diag(cm.posterior.cov), 0.0))
    theta = cm.posterior.theta_map
    bound_active = cm.space.active_bounds(theta)
    denom = np.outer(sig, sig)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.where(denom > 0, cm.posterior.cov / denom, 0.0)
    off = corr - np.diag(np.diag(corr))
    # `corr` is returned as well so the audit trail can export the full
    # correlation matrix without recomputing it; existing callers read only
    # the three keys they always did.
    return {"sigma": sig, "bound_active": tuple(bound_active),
            "corr": corr,
            "corr_max": float(np.max(np.abs(off))) if off.size else 0.0}


# --------------------------------------------------------------------------- #
def run_strategy_e(lab: AdvancedVirtualLaboratory,
                   inference: InferenceModel,
                   candidates: List[OperatingConditions],
                   first_u: OperatingConditions,
                   spatial_cfg: SpatialDesignConfig,
                   budget: int,
                   mbdoe_criterion: str = "D",
                   continuous: bool = False,
                   continuous_bounds: Optional[Dict] = None,
                   continuous_maxiter: int = 30,
                   resolution=None,
                   verbose: bool = True,
                   recorder=None) -> AdvancedStrategyResult:
    """E: baseline WLS/FIM inference + baseline condition MBDoE, but the
    POSITIONS each round are the greedy incremental D-optimal set.  All
    predictions route through inference.predict_at (the observation
    operator), so a transport-aware inference corrects E consistently too."""
    t0 = time.time()
    result = AdvancedStrategyResult(key="E", inference=inference)
    L = lab.length_m
    designer = SpatialDesigner(
        spatial_cfg, L, _noise_cov_builder(inference.noise, lab.species))
    designer.audit = recorder is not None      # write-only capture; see audit.py

    def field_for(u: OperatingConditions) -> SensitivityField:
        def predict(th, z):
            return inference.predict_at(th, u, z, lab.species)
        return SensitivityField(predict, inference.theta,
                                inference.space.fd_steps,
                                designer.candidate_grid(), len(lab.species))

    u_next = first_u
    z_next = fixed_equal_positions(L, spatial_cfg.n_positions)
    for r in range(1, budget + 1):
        t_round = time.perf_counter()
        if r > 1 or spatial_cfg.mode != "fixed_equal":
            F0 = inference.fisher_information()
            z_next = designer.positions(field_for(u_next), F0)
            if recorder is not None:
                recorder.record_spatial(
                    u_next, designer.last_selection, rank=0, selected=1,
                    mode="fim", length_m=L, round_no=r)
        meas = lab.run_profile(u_next, z_next)
        inference.add_measurement(meas)
        inference.fit()
        rep = inference.uncertainty()
        t_fit_done = time.perf_counter()
        result.history.append(AdvRoundRecord(
            round=r, u=u_next, z_positions=np.asarray(z_next),
            theta_nat=inference.space.to_natural(inference.theta),
            best_model="wls", model_probs={"wls": 1.0}, governor=None,
            resources=lab.meter.totals(), n_data=inference.n_data,
            design_mode="fim", sigma_scaled=rep.sigma,
            param_keys=tuple(inference.space.param_keys),
            bound_active=tuple(rep.active_bounds),
            theta_cov=(rep.cov if recorder is not None else None),
            theta_corr=(rep.corr if recorder is not None else None)))
        if verbose:
            print(f"  [E] round {r}/{budget}  {u_next.label():34s} "
                  f"z/L={np.round(np.asarray(z_next) / L, 3)} "
                  f"maxCI={rep.max_rel_ci_pct:7.1f}%")
        if r == budget:
            if recorder is not None:
                recorder.record_timing(
                    r, measure_fit_s=t_fit_done - t_round,
                    design_select_s=0.0,
                    round_total_s=time.perf_counter() - t_round)
            break
        t_sel = time.perf_counter()
        selector = MBDoESelector(
            inference=inference, candidates=candidates, spatial=True,
            ports_z_m=np.asarray(z_next), outlet_z_m=np.array([L]),
            species=lab.species, criterion=mbdoe_criterion,
            continuous=bool(continuous),
            continuous_bounds=continuous_bounds,
            continuous_maxiter=int(continuous_maxiter),
            **({"resolution": resolution} if resolution is not None else {}))
        u_next = selector.select()
        if recorder is not None:
            recorder.record_timing(
                r, measure_fit_s=t_fit_done - t_round,
                design_select_s=time.perf_counter() - t_sel,
                round_total_s=time.perf_counter() - t_round)
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
                   cov_model=None,
                   qc: QCGateConfig = QCGateConfig(),
                   bounds: Optional[Dict] = None,
                   seed: int = 0,
                   verbose: bool = True,
                   key: str = "F",
                   recorder=None,
                   resolution=None) -> AdvancedStrategyResult:
    """F: the full advanced loop (see module docstring).

    cov_model: optional measurement-aware expected-covariance model (e.g.
    SpectralCovarianceModel) used for spatial design and EIG; the
    NoiseSurrogate remains the fallback and keeps learning from data.

    recorder: passive audit sink (sdl_advanced/audit.py) or None.  When
    present it receives wall-clock timings and a reference to the posterior
    covariance each round already computed.  It draws no random numbers,
    evaluates nothing, and is never read back, so the campaign is identical
    with and without it - asserted by tests/test_audit_regression.py."""
    t0 = time.time()
    result = AdvancedStrategyResult(key=key, ensemble=ensemble)
    governor = governor or AdequacyGovernor()
    surrogate = surrogate or NoiseSurrogate(lab.species)
    exp_cov = cov_model if cov_model is not None else surrogate
    L = lab.length_m
    designer = SpatialDesigner(spatial_cfg, L, exp_cov.cov_at)
    ref_conds = None
    if design_cfg.objective == "predictive":
        # internal reference-prediction grid for the predictive objective:
        # a coarse sweep of the candidate space (documented; NOT the blind
        # validation set, which no controller code may see)
        z_ref = np.array([0.5 * L, L])
        step = max(len(candidates) // 6, 1)
        ref_conds = [(u, z_ref) for u in candidates[::step]]
    selector = AdvancedSelector(ensemble, candidates, designer, exp_cov,
                                lab.meter, lab.species, design_cfg,
                                bounds=bounds, seed=seed,
                                reference_conditions=ref_conds,
                                recorder=recorder, resolution=resolution)
    state = GovernorState.NORMAL_LEARNING
    decision: Optional[DesignDecision] = None
    u_next = first_u
    # ONE monitor for the whole campaign: the persistence rules must see the
    # acquisition stream, not a per-round slice of it - that is exactly the
    # information a per-round rejection fraction throws away.
    qc_monitor = QCMonitor(qc)
    for r in range(1, budget + 1):
        # ---- measure this round's spatial set --------------------------- #
        t_round = time.perf_counter()
        n_rej = n_re = 0
        if spatial_cfg.mode == "adaptive_sequential" and r > 1:
            meas_list, n_rej, n_re, fault = _adaptive_profile_bayes(
                lab, ensemble, designer, surrogate, u_next, spatial_cfg, qc,
                recorder=recorder, round_no=r, monitor=qc_monitor)
            zs_measured = np.concatenate([m.z_m for m in meas_list]) \
                if meas_list else np.array([])
        else:
            if decision is not None:
                zs = decision.z_positions
            elif spatial_cfg.mode == "fixed_equal":
                zs = fixed_equal_positions(L, spatial_cfg.n_positions)
            else:
                zs = designer.positions(
                    _field_for_model(ensemble.best, u_next, designer,
                                     lab.species),
                    np.zeros((ensemble.best.space.n_params,) * 2)
                    if ensemble.best.posterior.theta_map is None
                    else ensemble.best.inference.fisher_information(
                        ensemble.best.posterior.theta_map))
                if recorder is not None:
                    # the seed round designs its own positions without the
                    # selector, so the curve is reported from here instead
                    recorder.record_spatial(
                        u_next, designer.last_selection, rank=0, selected=1,
                        governor_state=str(state), mode="seed", length_m=L,
                        round_no=r)
            meas, n_rej, n_re, fault = measure_with_qc(
                lab, u_next, zs, qc, recorder=recorder, round_no=r,
                monitor=qc_monitor)
            if meas is not None and not fault:
                surrogate.observe(meas)
                ensemble.add_measurement(meas)
                ensemble.update()
            meas_list = [meas] if meas is not None else []
            zs_measured = meas.z_m if meas is not None else np.array([])
        if not fault and not meas_list:
            # Nothing survived QC but the instrument is not judged broken:
            # spend the round, record nothing, and let the next round design
            # afresh.  Appending a round record here would either report a
            # posterior that no data supports or crash on a None MAP.
            if verbose:
                print(f"  [{key}] round {r}: no assimilable data "
                      f"({n_rej} rejected); retrying next round")
            continue
        if fault:
            why = qc_monitor.trip_reason or f"{n_rej} positions rejected"
            result.stop_reason = (
                f"MEASUREMENT_FAULT: {why} (round {r}); campaign paused")
            if verbose:
                print(f"  [{key}] round {r}: {result.stop_reason}")
            break
        t_fit_done = time.perf_counter()
        gov_rep = governor.assess(ensemble, r)
        state = gov_rep.state if use_governor \
            else GovernorState.NORMAL_LEARNING
        best = ensemble.best
        diag = _posterior_diag(best)
        # snapshot NOW: copying (not referencing) the ensemble's current
        # reliability state, so later rounds cannot rewrite this record
        ev_by_model = dict(getattr(ensemble, "evidence_reliable", {}))
        ev_warn = "; ".join(getattr(ensemble, "evidence_warnings", []))
        result.history.append(AdvRoundRecord(
            round=r, u=u_next, z_positions=np.asarray(zs_measured),
            theta_nat=best.space.to_natural(best.posterior.theta_map),
            best_model=best.name,
            model_probs={cm.name: float(p) for cm, p
                         in zip(ensemble.models, ensemble.probs)},
            governor=gov_rep, resources=lab.meter.totals(),
            n_data=sum(m.size for m in best.inference.measurements),
            design_mode=decision.mode if decision else "seed",
            eig_param=decision.eig_param if decision else float("nan"),
            eig_model=decision.eig_model if decision else float("nan"),
            sigma_scaled=diag["sigma"],
            param_keys=tuple(best.space.param_keys),
            bound_active=diag["bound_active"],
            corr_max_offdiag=diag["corr_max"],
            n_rejected=n_rej, n_reacquired=n_re,
            probs_reliable=bool(all(ev_by_model.values())
                                if ev_by_model else False),
            evidence_reliable_by_model=ev_by_model,
            evidence_warning=ev_warn,
            # audit-only references to matrices this round already built
            theta_cov=(best.posterior.cov if recorder is not None else None),
            theta_corr=(diag["corr"] if recorder is not None else None)))
        if verbose:
            probs = " ".join(f"{cm.name}={p:.2f}" for cm, p
                             in zip(ensemble.models, ensemble.probs))
            print(f"  [{key}] round {r}/{budget}  {u_next.label():34s} "
                  f"n_z={len(zs_measured)}  {gov_rep.state:20s} {probs}")
        if r == budget:
            if recorder is not None:
                recorder.record_timing(
                    r, measure_fit_s=t_fit_done - t_round,
                    design_select_s=0.0,
                    round_total_s=time.perf_counter() - t_round)
            break
        if recorder is not None:
            recorder.set_decision_round(r + 1)   # the round being designed for
        t_sel = time.perf_counter()
        decision = selector.select(state)
        if recorder is not None:
            recorder.record_timing(
                r, measure_fit_s=t_fit_done - t_round,
                design_select_s=time.perf_counter() - t_sel,
                round_total_s=time.perf_counter() - t_round)
        u_next = decision.u
    result.runtime_s = time.time() - t0
    return result


# --------------------------------------------------------------------------- #
def _adaptive_profile_bayes(lab: AdvancedVirtualLaboratory,
                            ensemble: ModelEnsemble,
                            designer: SpatialDesigner,
                            surrogate: NoiseSurrogate,
                            u: OperatingConditions,
                            cfg: SpatialDesignConfig,
                            qc: QCGateConfig,
                            recorder=None, round_no: int = 0,
                            monitor: "Optional[QCMonitor]" = None
                            ) -> Tuple[List[Measurement], int, int, bool]:
    """TRULY data-adaptive sequential axial sampling:

        choose z -> acquire NMR -> deconvolve -> QC gate ->
        UPDATE THE FULL POSTERIOR with the actual measurement ->
        recompute the information landscape -> choose the next z

    for EVERY acquisition (the between-position update is the full Bayesian
    ensemble update, not just an expected-FIM bookkeeping step), so the
    realized measurement outcome can change the next selected position.
    Stops when the expected marginal information per acquisition falls
    below the threshold or n_positions is reached."""
    chosen: List[float] = []
    out: List[Measurement] = []
    n_rej_tot = n_re_tot = 0
    while len(chosen) < cfg.n_positions:
        cm = ensemble.best
        field = _field_for_model(cm, u, designer, lab.species)
        F = (cm.inference.fisher_information(cm.posterior.theta_map)
             if cm.posterior.theta_map is not None
             else np.zeros((cm.space.n_params,) * 2))
        z_next, gain = designer.next_position(field, F, chosen)
        if recorder is not None:
            # one adaptive step = one greedy evaluation over the z grid;
            # report the curve it just used (nothing re-evaluated)
            recorder.record_spatial(
                u, designer.last_selection, rank=0, selected=1,
                mode="adaptive_sequential", length_m=designer.length_m,
                round_no=round_no)
        if z_next is None:
            break
        if chosen and cfg.allow_profile_early_stop \
                and gain < cfg.marginal_information_threshold:
            break
        # ONE acquisition per iteration.  With the old per-round rejection
        # fraction this branch declared a MEASUREMENT_FAULT on the FIRST
        # rejected spectrum (1/1 = 100 %); the gate policy now needs
        # persistent failure, so a single bad spectrum simply costs this
        # position and the loop chooses another z.
        meas, n_rej, n_re, fault = measure_with_qc(lab, u, [float(z_next)],
                                                   qc, recorder=recorder,
                                                   round_no=round_no,
                                                   monitor=monitor)
        n_rej_tot += n_rej
        n_re_tot += n_re
        chosen.append(float(z_next))
        if fault:
            return out, n_rej_tot, n_re_tot, True
        if meas is None:
            continue                      # position rejected; try another z
        surrogate.observe(meas)
        ensemble.add_measurement(meas)
        ensemble.update()                 # <- posterior updated PER MEASUREMENT
        out.append(meas)
    return out, n_rej_tot, n_re_tot, False


# --------------------------------------------------------------------------- #
def run_advanced_strategy(key: str, **kwargs) -> AdvancedStrategyResult:
    """Dispatch: key 'E' -> run_strategy_e, 'F*' -> run_strategy_f."""
    if key == "E":
        return run_strategy_e(**kwargs)
    if key.startswith("F"):
        return run_strategy_f(key=key, **kwargs)
    raise ValueError(f"Unknown advanced strategy '{key}' (A-D live in "
                     f"sdl.campaign).")
