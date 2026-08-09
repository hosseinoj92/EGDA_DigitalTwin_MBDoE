"""
Bayesian expected-information-gain (EIG) active learning with a FIM
pre-screen and a resource-aware utility.

Design d = {T, Q, C_EGDA, C_H2SO4, Z} where Z is a set of capillary
positions.  Hierarchical, computationally practical pipeline (never a single
enormous joint optimizer):

    1. feasible operating-condition grid  (hard bounds = hard constraints)
    2. per condition: optimize its spatial set Z (spatial_design)
    3. FIM D-score - resource cost  ->  keep top K candidates
    4. Bayesian EIG on the top K (particle estimator below)
    5. winner executed; optional continuous refinement is inherited from
       the spatial designer (positions) - operating variables stay on the
       vetted grid in this implementation.

EIG estimator (nested Monte Carlo over the joint (M, theta) posterior):

    I(d) = E_{y ~ p(y|d,D)} KL( p(M,theta | y, d, D) || p(M,theta | D) )
        ~ (1/N_o) sum_o [ log p(y_o | th_{j(o)})
                          - log (1/N_i) sum_i p(y_o | th_i) ]

with particles th_i from the current posterior, outer samples y_o drawn by
picking a particle j(o) and adding noise from the EXPECTED observation
covariance (see NoiseSurrogate), all in log-sum-exp arithmetic.  The model-
discrimination component is  E_y KL( p(M|y) || p(M) )  computed from the
same likelihood table.  NMR pixel-level simulation is NEVER run for
hypothetical candidates - the surrogate provides Sigma_y; full spectra are
generated only for experiments the laboratory actually executes.

Resource-aware utility:

    U(d) = alpha * EIG_param(d) + beta * EIG_model(d) - cost(d)

with cost(d) from ResourceMeter.cost_of_candidate (lambda-weighted time,
material, waste, energy, condition switches, capillary motion) and
alpha/beta modulated by the governor state (MODEL_DISCRIMINATION boosts
beta; MODEL_INADEQUATE switches to the diagnostic objective, which scores
expected MODEL DISAGREEMENT instead of parameter information).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.special import logsumexp

from sdl.layer1_bridge import OperatingConditions
from sdl.observation import Measurement

from .adequacy import GovernorState
from .model_ensemble import ModelEnsemble, Particle
from .resources import ResourceMeter
from .spatial_design import SensitivityField, SpatialDesigner

_EIG_FLOOR = 1e-12


def _logdet_floored(F: np.ndarray) -> float:
    return float(np.sum(np.log(np.maximum(np.linalg.eigvalsh(F),
                                          _EIG_FLOOR))))


# --------------------------------------------------------------------------- #
class NoiseSurrogate:
    """Expected observation-covariance model LEARNED from the campaign's own
    deconvolution covariances (permitted QC metadata - never the truth).

    Model per position:  sigma_i = a + b * max(C_i, 0), one (a, b) fitted by
    least squares to all (concentration, claimed sigma) pairs seen so far,
    plus the running-mean EGDA/EGMA error correlation.  Before any data
    arrives it falls back to configured prior guesses (the baseline
    NoiseModel numbers, documented as assumptions)."""

    def __init__(self, species: Sequence[str], sigma_abs0: float = 0.004,
                 sigma_rel0: float = 0.02, rho0: float = 0.0):
        self.species = tuple(species)
        self.a, self.b, self.rho = sigma_abs0, sigma_rel0, rho0
        self._c: List[float] = []
        self._s: List[float] = []
        self._rhos: List[float] = []

    def observe(self, m: Measurement) -> None:
        if m.cov_y is None:
            return
        n_z, n_s = m.n_z, len(m.species)
        for k in range(n_z):
            idx = [i * n_z + k for i in range(n_s)]
            sub = m.cov_y[np.ix_(idx, idx)]
            sig = np.sqrt(np.maximum(np.diag(sub), 0.0))
            self._c.extend(np.maximum(m.y[idx], 0.0))
            self._s.extend(sig)
            if {"EGDA", "EGMA"} <= set(m.species):
                ia = list(m.species).index("EGDA")
                ib = list(m.species).index("EGMA")
                if sig[ia] > 0 and sig[ib] > 0:
                    self._rhos.append(sub[ia, ib] / (sig[ia] * sig[ib]))
        if len(self._c) >= 8:
            A = np.stack([np.ones(len(self._c)), np.array(self._c)], axis=1)
            coef, *_ = np.linalg.lstsq(A, np.array(self._s), rcond=None)
            self.a = float(max(coef[0], 1e-5))
            self.b = float(min(max(coef[1], 0.0), 1.0))
        if self._rhos:
            self.rho = float(np.clip(np.mean(self._rhos), -0.95, 0.95))

    def cov_at(self, y_pos: np.ndarray) -> np.ndarray:
        """Sigma for ONE position's species vector."""
        sig = self.a + self.b * np.maximum(y_pos, 0.0)
        cov = np.diag(sig ** 2)
        if abs(self.rho) > 0 and {"EGDA", "EGMA"} <= set(self.species):
            ia = self.species.index("EGDA")
            ib = self.species.index("EGMA")
            cov[ia, ib] = cov[ib, ia] = self.rho * sig[ia] * sig[ib]
        return cov

    def cov_profile(self, y: np.ndarray, n_z: int) -> np.ndarray:
        """Species-major covariance for a whole profile (block per z)."""
        n_s = len(self.species)
        cov = np.zeros((n_s * n_z, n_s * n_z))
        for k in range(n_z):
            idx = [i * n_z + k for i in range(n_s)]
            cov[np.ix_(idx, idx)] = self.cov_at(y[idx])
        return cov


# --------------------------------------------------------------------------- #
def expected_information_gain(preds: np.ndarray, models: np.ndarray,
                              cov: np.ndarray, rng: np.random.Generator,
                              n_outer: int = 32
                              ) -> Tuple[float, float]:
    """(EIG_total, EIG_model) in nats, from cached particle predictions.

    preds: (N, n_y) predicted observation per particle
    models: (N,) model index per particle
    cov: (n_y, n_y) expected observation covariance for this candidate."""
    N, n_y = preds.shape
    L = np.linalg.cholesky(cov + 1e-14 * np.eye(n_y))
    # whitened predictions: log p(y|th_i) = -0.5 ||w(y) - w_i||^2 + const
    W = np.linalg.solve(L, preds.T).T                     # (N, n_y)
    uniq = np.unique(models)
    prior_m = np.array([np.mean(models == m) for m in uniq])
    eig_tot, eig_mod = 0.0, 0.0
    for _ in range(n_outer):
        j = rng.integers(N)
        w_obs = W[j] + rng.standard_normal(n_y)
        ll = -0.5 * np.sum((W - w_obs[None, :]) ** 2, axis=1)   # (N,)
        log_marg = logsumexp(ll) - np.log(N)
        eig_tot += ll[j] - log_marg
        # posterior model probabilities after this hypothetical outcome
        log_pm = np.array([logsumexp(ll[models == m]) for m in uniq]) \
            - logsumexp(ll)
        pm = np.exp(log_pm)
        with np.errstate(divide="ignore", invalid="ignore"):
            terms = pm * (log_pm - np.log(prior_m))
        eig_mod += float(np.nansum(terms))
    return eig_tot / n_outer, eig_mod / n_outer


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AdvancedDesignConfig:
    top_k: int = 4                     # candidates surviving the FIM screen
    n_particles: int = 24
    n_outer: int = 32
    alpha_param: float = 1.0
    beta_model: float = 1.0
    beta_model_discrimination: float = 4.0   # boost while discriminating
    seed_offset: int = 104729          # design RNG stream separator
    # design objective (#identifiability vs #prediction):
    #   "parameter"  - D-optimal information / EIG on theta (default)
    #   "predictive" - minimize predictive variance over a reference
    #                  prediction grid (V-optimality flavour): accurate
    #                  process prediction may be reachable before every
    #                  microscopic parameter is individually identifiable
    objective: str = "parameter"


@dataclass
class DesignDecision:
    u: OperatingConditions
    z_positions: np.ndarray
    utility: float
    eig_param: float
    eig_model: float
    cost: float
    mode: str                          # "eig" | "diagnostic"
    screen_scores: Dict[str, float] = field(default_factory=dict)


class AdvancedSelector:
    """Hierarchical (u, Z) selector for strategy F."""

    def __init__(self, ensemble: ModelEnsemble,
                 candidates: Sequence[OperatingConditions],
                 designer: SpatialDesigner,
                 surrogate: NoiseSurrogate,
                 meter: ResourceMeter,
                 species: Sequence[str],
                 cfg: AdvancedDesignConfig = AdvancedDesignConfig(),
                 bounds: Optional[Dict[str, Sequence[float]]] = None,
                 seed: int = 0,
                 reference_conditions: Optional[Sequence] = None,
                 recorder=None):
        # reference_conditions: [(u, z_array), ...] defining the PREDICTIVE
        # objective's reference grid.  Must be an internal documented grid -
        # NEVER the blind validation set (which stays invisible by design).
        self.reference_conditions = list(reference_conditions or [])
        # PASSIVE audit sink (sdl_advanced/audit.py) or None.  It only ever
        # receives numbers this selector had already computed for its own
        # decision; it is never consulted, and it never draws a random
        # number, so the decision sequence is identical with and without it.
        self.recorder = recorder
        if not candidates:
            raise ValueError("Need at least one operating-condition candidate.")
        self.ensemble = ensemble
        self.candidates = list(candidates)
        self.designer = designer
        self.surrogate = surrogate
        self.meter = meter
        self.species = tuple(species)
        self.cfg = cfg
        self.bounds = bounds
        self._rng = np.random.default_rng(seed + cfg.seed_offset)
        if bounds:
            for u in self.candidates:
                self._assert_within_bounds(u)

    def _assert_within_bounds(self, u: OperatingConditions) -> None:
        b = self.bounds
        vals = {"T_C": u.T_C, "Q_total_mL_min": u.Q1_mL_min + u.Q2_mL_min,
                "C_cat_M": u.C_cat_M, "C_EGDA_M": u.C_EGDA_M}
        for k, v in vals.items():
            lo, hi = b[k]
            if not (lo <= v <= hi):
                raise ValueError(f"Candidate violates hard bound {k}: {v} "
                                 f"not in [{lo}, {hi}].")

    # ------------------------------------------------------------------ #
    def _field_for(self, u: OperatingConditions) -> SensitivityField:
        """Sensitivity field of the EXPECTED OBSERVATION (through the
        candidate's predict_observation operator, so spatial design and FIM
        screening see the same transport-corrected observable as
        estimation and EIG do)."""
        cm = self.ensemble.best

        def predict(th: np.ndarray, z: np.ndarray) -> np.ndarray:
            return cm.predict_observation(th, u, z, self.species)

        return SensitivityField(predict, cm.theta_hat, cm.space.fd_steps,
                                self.designer.candidate_grid(),
                                len(self.species))

    def _accumulated_fim(self) -> np.ndarray:
        return self.ensemble.best.inference.fisher_information(
            self.ensemble.best.posterior.theta_map)

    # ------------------------------------------------------------------ #
    def _reference_G(self) -> Optional[np.ndarray]:
        """Sensitivity matrix of the reference-grid predictions wrt theta
        (best model, through the observation operator) - the G of the
        predictive V-optimality objective.  None when no grid configured."""
        if not self.reference_conditions:
            return None
        cm = self.ensemble.best
        th = cm.theta_hat
        rows = []
        y0 = np.concatenate([cm.predict_observation(th, u, z, self.species)
                             for u, z in self.reference_conditions])
        for q in range(cm.space.n_params):
            tp = th.copy()
            tp[q] += cm.space.fd_steps[q]
            yq = np.concatenate([
                cm.predict_observation(tp, u, z, self.species)
                for u, z in self.reference_conditions])
            rows.append((yq - y0) / cm.space.fd_steps[q])
        return np.stack(rows, axis=1)          # (n_pred, p)

    @staticmethod
    def _pred_var(G: np.ndarray, F: np.ndarray) -> float:
        w, V = np.linalg.eigh(F)
        Vinv = V @ np.diag(1.0 / np.maximum(w, _EIG_FLOOR)) @ V.T
        return float(np.trace(G @ Vinv @ G.T))

    def select(self, governor_state: str = GovernorState.NORMAL_LEARNING
               ) -> DesignDecision:
        cfg = self.cfg
        F0 = self._accumulated_fim()
        G = (self._reference_G() if cfg.objective == "predictive" else None)
        pv0 = self._pred_var(G, F0) if G is not None else 0.0
        screened: List[Tuple[float, OperatingConditions, np.ndarray,
                             SensitivityField]] = []
        for u in self.candidates:
            field = self._field_for(u)
            zs = self.designer.positions(field, F0)
            F = F0.copy()
            for z in zs:
                F = F + self.designer._fim_at(field, float(z))
            cost = self.meter.cost_of_candidate(
                u.T_C, u.Q1_mL_min + u.Q2_mL_min, u.C_EGDA_M, u.C_cat_M, zs)
            if G is not None:            # predictive-variance reduction
                score = pv0 - self._pred_var(G, F) - cost
            else:                        # D-optimal information gain
                score = _logdet_floored(F) - _logdet_floored(F0) - cost
            screened.append((score, u, zs, field))
        screened.sort(key=lambda t: -t[0])
        top = screened[:max(cfg.top_k, 1)]

        if governor_state == GovernorState.MODEL_INADEQUATE:
            return self._select_diagnostic(top, screened, governor_state)
        if cfg.objective == "predictive":
            score, u, zs, _f = top[0]
            cost = self.meter.cost_of_candidate(
                u.T_C, u.Q1_mL_min + u.Q2_mL_min, u.C_EGDA_M, u.C_cat_M, zs)
            self._record(governor_state, "predictive", screened,
                         {0: {"utility": score, "cost": cost}}, 0)
            return DesignDecision(u=u, z_positions=zs, utility=score,
                                  eig_param=np.nan, eig_model=np.nan,
                                  cost=cost, mode="predictive")

        beta = (cfg.beta_model_discrimination
                if governor_state == GovernorState.MODEL_DISCRIMINATION
                else cfg.beta_model)
        particles = self.ensemble.particles(cfg.n_particles, self._rng)
        if not particles:
            score, u, zs, _ = top[0]
            self._record(governor_state, "eig", screened,
                         {0: {"utility": score, "cost": 0.0}}, 0)
            return DesignDecision(u=u, z_positions=zs, utility=score,
                                  eig_param=np.nan, eig_model=np.nan,
                                  cost=0.0, mode="eig")
        best: Optional[DesignDecision] = None
        best_rank, evaluated = None, {}
        for rank, (screen_score, u, zs, _field) in enumerate(top):
            preds = np.stack([self.ensemble.predict(pt, u, zs, self.species)
                              for pt in particles])
            models = np.array([pt.model_index for pt in particles])
            y_ref = np.mean(preds, axis=0)
            cov = self.surrogate.cov_profile(y_ref, len(zs))
            eig_t, eig_m = expected_information_gain(
                preds, models, cov, self._rng, cfg.n_outer)
            cost = self.meter.cost_of_candidate(
                u.T_C, u.Q1_mL_min + u.Q2_mL_min, u.C_EGDA_M, u.C_cat_M, zs)
            util = (cfg.alpha_param * (eig_t - eig_m) + beta * eig_m - cost)
            evaluated[rank] = {"eig_param": eig_t - eig_m, "eig_model": eig_m,
                               "cost": cost, "utility": util}
            dec = DesignDecision(u=u, z_positions=zs, utility=util,
                                 eig_param=eig_t - eig_m, eig_model=eig_m,
                                 cost=cost, mode="eig",
                                 screen_scores={u.label(): screen_score})
            if best is None or util > best.utility:
                best = dec
                best_rank = rank
        self._record(governor_state, "eig", screened, evaluated, best_rank,
                     beta)
        return best

    # ------------------------------------------------------------------ #
    def _record(self, governor_state: str, mode: str, screened,
                evaluated: Dict[int, Dict], chosen_rank: Optional[int],
                beta: float = float("nan")) -> None:
        """Hand the ALREADY-COMPUTED scores to the audit sink, if any.

        Nothing here is recomputed and no RNG is touched, so this call is
        invisible to the campaign - see sdl_advanced/audit.py."""
        if self.recorder is None:
            return
        self.recorder.record_candidates(governor_state, mode, screened,
                                        evaluated, chosen_rank, beta)

    # ------------------------------------------------------------------ #
    def _normalized_u(self, u: OperatingConditions) -> np.ndarray:
        """Operating point in [0,1]^4 (bounds-normalized) for distances."""
        vals = {"T_C": u.T_C, "Q_total_mL_min": u.Q1_mL_min + u.Q2_mL_min,
                "C_cat_M": u.C_cat_M, "C_EGDA_M": u.C_EGDA_M}
        out = []
        for k, v in vals.items():
            if self.bounds and k in self.bounds:
                lo, hi = self.bounds[k]
                out.append((v - lo) / max(hi - lo, 1e-12))
            else:
                out.append(0.0)
        return np.array(out)

    def _select_diagnostic(self, top, screened=None,
                           governor_state: str = "") -> DesignDecision:
        """MODEL_INADEQUATE: stop exploiting the (wrong) model's FIM.

        Score = expected whitened DISAGREEMENT between the candidate models'
        MAP predictions (the experiment most able to separate 'parameters
        uncertain' from 'structure wrong', because structure errors grow
        where model families diverge)  +  a structural-stress exploration
        term (distance to already-visited operating points x the screened
        information gain), which drives the search toward unexplored regions
        where interpolation cannot hide a structural failure - and is the
        active term when the family has only one member."""
        visited = [self._normalized_u(m.u)
                   for m in self.ensemble.best.inference.measurements]
        best_dec, best_score = None, -np.inf
        best_rank, evaluated = None, {}
        for rank, (screen_gain, u, zs, _field) in enumerate(top):
            preds = []
            for cm in self.ensemble.models:
                preds.append(cm.predict_observation(cm.theta_hat, u, zs,
                                                    self.species))
            P = np.stack(preds)
            y_ref = np.mean(P, axis=0)
            cov = self.surrogate.cov_profile(y_ref, len(zs))
            L = np.linalg.cholesky(cov + 1e-14 * np.eye(cov.shape[0]))
            W = np.linalg.solve(L, (P - y_ref[None, :]).T).T
            disagreement = float(np.mean(np.sum(W ** 2, axis=1)))
            xu = self._normalized_u(u)
            min_dist = (min(float(np.linalg.norm(xu - v)) for v in visited)
                        if visited else 1.0)
            stress = min_dist * max(float(screen_gain), 0.0)
            cost = self.meter.cost_of_candidate(
                u.T_C, u.Q1_mL_min + u.Q2_mL_min, u.C_EGDA_M, u.C_cat_M, zs)
            score = disagreement + stress - cost
            # the diagnostic objective has no EIG decomposition; the audit
            # trail carries its two terms in the same columns so the CSV
            # stays one shape (documented in audit_export.py)
            evaluated[rank] = {"eig_param": disagreement, "eig_model": stress,
                               "cost": cost, "utility": score}
            if score > best_score:
                best_score = score
                best_rank = rank
                best_dec = DesignDecision(
                    u=u, z_positions=zs, utility=score,
                    eig_param=np.nan, eig_model=np.nan, cost=cost,
                    mode="diagnostic")
        self._record(governor_state, "diagnostic",
                     screened if screened is not None else top,
                     evaluated, best_rank)
        return best_dec
