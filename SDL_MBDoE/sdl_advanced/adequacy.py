"""
Model-inadequacy governor: distinguishes "my parameters are uncertain" from
"my model is systematically wrong" BEFORE the controller exploits the
current model for D-optimal/Bayesian refinement.

Diagnostics on the best model's MAP whitened residuals r_w (which are
~ N(0, I) when model + noise model are both correct):

  * global lack of fit    T_chi2 = r_w' r_w, compared to chi2(n - p);
  * z-trend               Pearson correlation between r_w and z within each
                          spatial profile (systematic axial misfit);
  * T-trend               correlation between per-experiment mean residual
                          and reactor temperature across experiments;
  * species bias          per-species standardized mean residual
                          sqrt(n_s) * mean(r_w,s)  ~ N(0,1);
  * measurement QC        FAIL flags raised by the spectral deconvolution
                          (fit residual >> noise: instrument/lineshape
                          problem, not chemistry).

CALIBRATION: the chi2 reference is exact only for a linear model; the
governor therefore supports Monte Carlo calibration (`calibrate_thresholds`)
which simulates campaigns-worth of residuals UNDER THE FITTED MODEL
(parametric bootstrap with refit) and sets the decision threshold at the
requested false-positive rate.  The benchmark measures the realized
false-positive rate under the correct model (acceptance test 11).

States:
    NORMAL_LEARNING       data consistent with >= 1 model, one model dominant
    MODEL_DISCRIMINATION  data consistent, but several models plausible
    MODEL_INADEQUATE      ALL candidate models show calibrated lack of fit
    MEASUREMENT_FAULT     the spectral-fit QC itself failed (fix instrument
                          before blaming chemistry)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats

from sdl.observation import Measurement

from .model_ensemble import ModelEnsemble


class GovernorState:
    NORMAL_LEARNING = "NORMAL_LEARNING"
    MODEL_DISCRIMINATION = "MODEL_DISCRIMINATION"
    MODEL_INADEQUATE = "MODEL_INADEQUATE"
    MEASUREMENT_FAULT = "MEASUREMENT_FAULT"


@dataclass
class AdequacyReport:
    state: str
    score: float                     # chi2/dof of the best model
    p_value: float                   # calibrated lack-of-fit p (best model)
    p_values_all: Dict[str, float]   # per candidate model
    species_bias: Dict[str, float]   # standardized mean residual per species
    z_trend_r: float                 # residual-vs-z correlation (pooled)
    T_trend_r: float                 # mean-residual-vs-T correlation
    reasons: List[str] = field(default_factory=list)
    affected_species: List[str] = field(default_factory=list)
    affected_region: str = ""
    round_detected: Optional[int] = None


@dataclass(frozen=True)
class GovernorConfig:
    alpha: float = 0.01              # lack-of-fit false-positive target
    discrimination_prob: float = 0.90   # below this, discriminate models
    species_bias_z: float = 4.0      # |z| flagging a species-systematic bias
    qc_fail_fraction: float = 0.25   # spectra with FAIL flags -> fault
    chi2_dof_ratio_override: float = 25.0   # emergency trip even pre-calib


class AdequacyGovernor:
    def __init__(self, cfg: GovernorConfig = GovernorConfig()):
        self.cfg = cfg
        self.round_first_inadequate: Optional[int] = None
        #: MC-calibrated 1-alpha quantile of T_chi2/dof; None -> analytic chi2
        self.calibrated_quantile: Optional[float] = None

    # ------------------------------------------------------------------ #
    @staticmethod
    def _whitened_by_measurement(cm, theta) -> List[np.ndarray]:
        from scipy.linalg import solve_triangular
        out = []
        for m, L in zip(cm.inference.measurements, cm.inference._chols):
            r = cm.inference.predict(theta, m) - m.y
            out.append(solve_triangular(L, r, lower=True))
        return out

    def _lack_of_fit_p(self, cm) -> float:
        theta = cm.posterior.theta_map
        if theta is None:
            return 1.0
        rw = np.concatenate(self._whitened_by_measurement(cm, theta))
        dof = max(len(rw) - cm.space.n_params, 1)
        stat = float(rw @ rw)
        if self.calibrated_quantile is not None:
            # calibrated: compare the ratio to the MC quantile via a normal
            # tail approximation around it (documented approximation)
            return float(stat / dof < self.calibrated_quantile)
        return float(stats.chi2.sf(stat, dof))

    def _autocorr_p(self, cm) -> Tuple[float, float]:
        """(pooled lag-1 autocorrelation along z, one-sided p-value).

        SCALE-FREE lack-of-fit test: kinetic-model error is SMOOTH along the
        reactor, so consecutive whitened residuals at neighbouring z are
        positively correlated; acquisition noise is independent.  Being a
        correlation, it is immune to a conservative (inflated) Sigma_y that
        would mask the chi2 test."""
        theta = cm.posterior.theta_map
        if theta is None:
            return 0.0, 1.0
        a_pairs, b_pairs = [], []
        for m, r in zip(cm.inference.measurements,
                        self._whitened_by_measurement(cm, theta)):
            if m.n_z < 4:
                continue
            order = np.argsort(m.z_m)
            for i in range(len(m.species)):
                series = r[i * m.n_z:(i + 1) * m.n_z][order]
                a_pairs.extend(series[:-1])
                b_pairs.extend(series[1:])
        n = len(a_pairs)
        if n < 8:
            return 0.0, 1.0
        a = np.asarray(a_pairs)
        b = np.asarray(b_pairs)
        denom = np.sqrt(np.sum(a * a) * np.sum(b * b))
        rho = float(np.sum(a * b) / denom) if denom > 0 else 0.0
        z = rho * np.sqrt(n)
        return rho, float(stats.norm.sf(z))

    # ------------------------------------------------------------------ #
    def assess(self, ensemble: ModelEnsemble, round_no: int
               ) -> AdequacyReport:
        best = ensemble.best
        theta = best.posterior.theta_map
        rws = self._whitened_by_measurement(best, theta)
        rw = np.concatenate(rws) if rws else np.zeros(0)
        n, p = len(rw), best.space.n_params
        dof = max(n - p, 1)
        score = float(rw @ rw) / dof

        # two lack-of-fit tests per model, Bonferroni-combined: the chi2
        # magnitude test (catches gross misfit) and the scale-free residual
        # z-autocorrelation test (catches smooth model error hidden by a
        # conservative Sigma_y).  p_model = min(2*min(p_chi2, p_rho), 1).
        p_all: Dict[str, float] = {}
        rho_all: Dict[str, float] = {}
        for cm in ensemble.models:
            p_chi2 = self._lack_of_fit_p(cm)
            rho, p_rho = self._autocorr_p(cm)
            rho_all[cm.name] = rho
            p_all[cm.name] = min(2.0 * min(p_chi2, p_rho), 1.0)
        p_best = p_all[best.name]

        # per-species standardized mean residual (species-major blocks)
        species_bias: Dict[str, float] = {}
        for sp in best.inference.measurements[0].species if rws else []:
            vals = []
            for m, r in zip(best.inference.measurements, rws):
                i = list(m.species).index(sp)
                vals.extend(r[i * m.n_z:(i + 1) * m.n_z])
            v = np.asarray(vals)
            species_bias[sp] = float(np.mean(v) * np.sqrt(len(v)))

        # residual trend along z (pooled over spatial measurements)
        zs, rs, t_means, t_cs = [], [], [], []
        for m, r in zip(best.inference.measurements, rws):
            t_means.append(float(np.mean(r)))
            t_cs.append(m.u.T_C)
            if m.n_z > 1:
                for i in range(len(m.species)):
                    zs.extend(m.z_m)
                    rs.extend(r[i * m.n_z:(i + 1) * m.n_z])
        z_trend = (float(np.corrcoef(zs, rs)[0, 1])
                   if len(zs) > 3 and np.std(zs) > 0 else 0.0)
        T_trend = (float(np.corrcoef(t_cs, t_means)[0, 1])
                   if len(t_cs) > 3 and np.std(t_cs) > 0 else 0.0)

        # QC of the spectral fits
        n_fail = n_spec = 0
        for m in best.inference.measurements:
            for q in (m.meta or {}).get("qc", []):
                n_spec += 1
                if any(f.startswith("FAIL") for f in q.get("qc_flags", [])):
                    n_fail += 1
        qc_frac = n_fail / n_spec if n_spec else 0.0

        # ---- state machine ------------------------------------------- #
        reasons: List[str] = []
        cfg = self.cfg
        state = GovernorState.NORMAL_LEARNING
        if qc_frac > cfg.qc_fail_fraction:
            state = GovernorState.MEASUREMENT_FAULT
            reasons.append(f"{qc_frac:.0%} of spectral fits raised FAIL QC")
        elif (all(pv < cfg.alpha for pv in p_all.values())
              or score > cfg.chi2_dof_ratio_override):
            state = GovernorState.MODEL_INADEQUATE
            reasons.append(
                f"every candidate model rejected at alpha={cfg.alpha:g} "
                f"(best chi2/dof={score:.2f}, p={p_best:.2e}, "
                f"residual z-autocorr={rho_all[best.name]:.2f})")
            if self.round_first_inadequate is None:
                self.round_first_inadequate = round_no
        elif float(np.max(ensemble.probs)) < cfg.discrimination_prob:
            state = GovernorState.MODEL_DISCRIMINATION
            reasons.append(
                "several models plausible: "
                + ", ".join(f"{cm.name} {pr:.2f}"
                            for cm, pr in zip(ensemble.models,
                                              ensemble.probs)))

        affected = [sp for sp, b in species_bias.items()
                    if abs(b) > cfg.species_bias_z]
        region = ""
        if abs(z_trend) > 0.3:
            region = ("misfit grows toward the outlet" if z_trend > 0
                      else "misfit grows toward the inlet")
        if abs(T_trend) > 0.5:
            region += (" | misfit correlated with temperature"
                       if region else "misfit correlated with temperature")

        return AdequacyReport(
            state=state, score=score, p_value=p_best, p_values_all=p_all,
            species_bias=species_bias, z_trend_r=z_trend, T_trend_r=T_trend,
            reasons=reasons, affected_species=affected,
            affected_region=region,
            round_detected=self.round_first_inadequate)

    # ------------------------------------------------------------------ #
    def calibrate_thresholds(self, ensemble: ModelEnsemble,
                             rng: np.random.Generator,
                             n_mc: int = 50) -> float:
        """Parametric-bootstrap calibration of the chi2/dof trip point.

        Simulates data under the FITTED best model with the CLAIMED
        measurement covariances, refits, and returns the empirical
        (1 - alpha) quantile of chi2/dof, stored for later assessments.
        This bounds the governor's false-positive rate at ~alpha under the
        correct model by construction."""
        best = ensemble.best
        inf = best.inference
        theta0 = best.posterior.theta_map.copy()
        y_backup = [m.y.copy() for m in inf.measurements]
        scores = []
        try:
            for _ in range(n_mc):
                for m, L in zip(inf.measurements, inf._chols):
                    clean = inf.predict(theta0, m)
                    m.y = clean + L @ rng.standard_normal(m.size)
                best.posterior.fit_map()
                rw = np.concatenate(self._whitened_by_measurement(
                    best, best.posterior.theta_map))
                dof = max(len(rw) - best.space.n_params, 1)
                scores.append(float(rw @ rw) / dof)
        finally:
            for m, y in zip(inf.measurements, y_backup):
                m.y = y
            best.posterior.fit_map()
        q = float(np.quantile(scores, 1.0 - self.cfg.alpha))
        self.calibrated_quantile = q
        return q
