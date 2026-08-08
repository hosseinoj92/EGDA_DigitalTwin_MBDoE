"""
Model-inadequacy governor: distinguishes "my parameters are uncertain" from
"my model is systematically wrong" BEFORE the controller exploits the
current model for D-optimal/Bayesian refinement.

STATISTICAL DESIGN (this module's contract):

Per candidate model, four lack-of-fit components are computed on the MAP
whitened residuals r_w (~ N(0, I) when model + measurement model are both
correct), each yielding a CONTINUOUS p-value:

  1. magnitude      T1 = r_w' r_w                   vs  chi2_{n-p}
  2. z-structure    pooled lag-1 autocorrelation of r_w along z (model error
                    is smooth along the reactor; acquisition noise is not);
                    z-score = rho * sqrt(N_pairs), one-sided normal.  Being a
                    correlation it is IMMUNE to a conservative Sigma_y that
                    masks the chi2 test.
  3. species bias   max_s |sqrt(n_s) mean(r_w,s)|, two-sided normal with
                    Sidak correction over the species
  4. T-trend        per-experiment mean residual vs reactor T, Fisher-z
                    two-sided (needs >= 4 distinct experiments)

They are combined by min-p with a Sidak correction over the m components
actually evaluated:  p_model = 1 - (1 - p_min)^m .  The analytic reference
distributions are approximations for a fitted nonlinear model; the
`bootstrap_pvalue` method provides the rigorous alternative - a parametric
bootstrap WITH REFIT that returns a real empirical tail probability

    p_boot = (1 + #{ T*_b  at least as extreme as  T_obs }) / (B + 1)

of the same composite statistic (Westfall-Young style: the min-p observed is
compared against the bootstrap distribution of min-p under the fitted
model).  The benchmark's governor-validation study measures the REALIZED
false-alarm rate; no exact false-positive control is claimed beyond what
that study demonstrates.

SEQUENTIAL TESTING: the governor is consulted every round.  To keep the
CAMPAIGN-level false-alarm probability near `alpha_campaign`, a uniform
alpha-spending rule is applied: each round tests at
alpha_round = alpha_campaign / n_rounds_planned (Bonferroni spending -
conservative, simple, and defensible; refine with an O'Brien-Fleming
schedule later if wanted).

States:
    NORMAL_LEARNING       data consistent with >= 1 model, one model dominant
    MODEL_DISCRIMINATION  data consistent, but several models plausible
    MODEL_INADEQUATE      ALL candidate models show calibrated lack of fit
    MEASUREMENT_FAULT     the spectral-fit QC itself failed (handled as a
                          CONTROL state by the QC gate in controller.py:
                          failing spectra are never assimilated)
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
    p_value: float                   # combined (Sidak min-p) of best model
    p_values_all: Dict[str, float]   # combined p per candidate model
    components: Dict[str, float]     # best model's per-component p-values
    alpha_round: float               # spending-adjusted threshold used
    species_bias: Dict[str, float]   # standardized mean residual per species
    z_trend_r: float                 # pooled residual-vs-z autocorrelation
    T_trend_r: float                 # mean-residual-vs-T correlation
    reasons: List[str] = field(default_factory=list)
    affected_species: List[str] = field(default_factory=list)
    affected_region: str = ""
    round_detected: Optional[int] = None
    p_boot: Optional[float] = None   # set when a bootstrap p was requested


@dataclass(frozen=True)
class GovernorConfig:
    alpha_campaign: float = 0.05     # campaign-level false-alarm target
    n_rounds_planned: int = 10       # alpha spending denominator
    discrimination_prob: float = 0.90   # below this, discriminate models
    qc_fail_fraction: float = 0.25   # spectra with FAIL flags -> fault state
    chi2_dof_ratio_override: float = 25.0   # gross-misfit emergency trip
    # MEASUREMENT-SYSTEMATIC ALLOWANCE kappa: the claimed Sigma_y of the NMR
    # pathway deliberately includes floor terms describing residual
    # quantification SYSTEMATICS (post-calibration lineshape/overlap bias,
    # ~2-3%).  A systematic bias b with |b| <= kappa * sigma_claimed is
    # therefore CONSISTENT with the declared measurement model and must not
    # accumulate into a kinetic-inadequacy verdict as mean*sqrt(n) grows.
    # Each component's null is widened accordingly:
    #   bias:      z = mean / sqrt(1/n + kappa^2)
    #   autocorr:  z = (rho - rho0) sqrt(n),  rho0 = kappa^2/(1+kappa^2)
    #   chi2:      T scaled by 1/(1+kappa^2)
    # kappa = 0 (direct-observation scenarios) recovers the exact nulls.
    # The value is tied to the fitter's declared floor share (ASSUMED /
    # CAL: refine from replicate mixture standards).
    systematic_allowance: float = 0.0


class AdequacyGovernor:
    def __init__(self, cfg: GovernorConfig = GovernorConfig()):
        self.cfg = cfg
        self.round_first_inadequate: Optional[int] = None

    # ------------------------------------------------------------------ #
    @staticmethod
    def _whitened_by_measurement(cm, theta) -> List[np.ndarray]:
        from scipy.linalg import solve_triangular
        out = []
        for m, L in zip(cm.inference.measurements, cm.inference._chols):
            r = cm.inference.predict(theta, m) - m.y
            out.append(solve_triangular(L, r, lower=True))
        return out

    # ---- individual components (continuous p-values) ------------------ #
    def _p_chi2(self, rw: np.ndarray, n_params: int) -> Tuple[float, float]:
        kap2 = self.cfg.systematic_allowance ** 2
        dof = max(len(rw) - n_params, 1)
        stat = float(rw @ rw)
        return stat / dof, float(stats.chi2.sf(stat / (1.0 + kap2), dof))

    def _autocorr(self, cm, rws) -> Tuple[float, float, int]:
        kap2 = self.cfg.systematic_allowance ** 2
        rho0 = kap2 / (1.0 + kap2)         # allowance-induced autocorrelation
        a_pairs, b_pairs = [], []
        for m, r in zip(cm.inference.measurements, rws):
            if m.n_z < 4:
                continue
            order = np.argsort(m.z_m)
            for i in range(len(m.species)):
                series = r[i * m.n_z:(i + 1) * m.n_z][order]
                a_pairs.extend(series[:-1])
                b_pairs.extend(series[1:])
        n = len(a_pairs)
        if n < 8:
            return 0.0, 1.0, n
        a, b = np.asarray(a_pairs), np.asarray(b_pairs)
        denom = np.sqrt(np.sum(a * a) * np.sum(b * b))
        rho = float(np.sum(a * b) / denom) if denom > 0 else 0.0
        return rho, float(stats.norm.sf((rho - rho0) * np.sqrt(n))), n

    def _species_bias(self, cm, rws) -> Tuple[Dict[str, float], float]:
        kap2 = self.cfg.systematic_allowance ** 2
        bias: Dict[str, float] = {}
        if not rws:
            return bias, 1.0
        for sp in cm.inference.measurements[0].species:
            vals = []
            for m, r in zip(cm.inference.measurements, rws):
                i = list(m.species).index(sp)
                vals.extend(r[i * m.n_z:(i + 1) * m.n_z])
            v = np.asarray(vals)
            # a bounded systematic (<= kappa sigma) never averages away:
            # widen the null accordingly instead of mean*sqrt(n) vs N(0,1)
            bias[sp] = float(np.mean(v) / np.sqrt(1.0 / len(v) + kap2))
        if not bias:
            return bias, 1.0
        p_each = [2.0 * stats.norm.sf(abs(b)) for b in bias.values()]
        p_min = min(p_each)
        m_tests = len(p_each)
        return bias, float(1.0 - (1.0 - p_min) ** m_tests)   # Sidak

    def _worst_cell(self, cm, rws) -> Tuple[float, float]:
        """Max standardized mean residual over (experiment x species) CELLS,
        Sidak-corrected for the number of cells.  A refitted wrong model
        spreads its misfit thin GLOBALLY but cannot silence it LOCALLY: the
        residual concentrates in the few conditions that expose the missing
        structure - exactly what this component looks for.  The kappa
        allowance widens the null for bounded quantification systematics."""
        kap2 = self.cfg.systematic_allowance ** 2
        zs = []
        for m, r in zip(cm.inference.measurements, rws):
            for i in range(len(m.species)):
                cell = r[i * m.n_z:(i + 1) * m.n_z]
                if len(cell) == 0:
                    continue
                zs.append(float(np.mean(cell))
                          / np.sqrt(1.0 / len(cell) + kap2))
        if not zs:
            return 0.0, 1.0
        worst = float(np.max(np.abs(zs)))
        p_one = 2.0 * stats.norm.sf(worst)
        return worst, float(1.0 - (1.0 - p_one) ** len(zs))   # Sidak

    def _t_trend(self, cm, rws) -> Tuple[float, float]:
        kap2 = self.cfg.systematic_allowance ** 2
        r0 = kap2 / (1.0 + kap2)
        t_cs = [m.u.T_C for m in cm.inference.measurements]
        means = [float(np.mean(r)) for r in rws]
        if len(set(t_cs)) < 4:
            return 0.0, 1.0
        r = float(np.corrcoef(t_cs, means)[0, 1])
        n = len(t_cs)
        r_eff = max(abs(r) - r0, 0.0)
        z = 0.5 * np.log((1 + r_eff) / max(1 - r_eff, 1e-12)) \
            * np.sqrt(max(n - 3, 1))
        return r, float(2.0 * stats.norm.sf(abs(z)))

    # ------------------------------------------------------------------ #
    def _model_components(self, cm) -> Tuple[Dict[str, float], float,
                                             Dict[str, float], float, float]:
        """(component p-values, combined Sidak min-p, species bias,
        chi2/dof score, pooled z-autocorrelation) for one model."""
        theta = cm.posterior.theta_map
        if theta is None:
            return {}, 1.0, {}, 0.0, 0.0
        rws = self._whitened_by_measurement(cm, theta)
        rw = np.concatenate(rws) if rws else np.zeros(0)
        score, p1 = self._p_chi2(rw, cm.space.n_params)
        rho, p2, n_pairs = self._autocorr(cm, rws)
        bias, p3 = self._species_bias(cm, rws)
        _t_r, p4 = self._t_trend(cm, rws)
        _w, p5 = self._worst_cell(cm, rws)
        comps = {"chi2": p1, "z_autocorr": p2, "species_bias": p3,
                 "T_trend": p4, "worst_cell": p5}
        p_comb = self.combine(comps, n_pairs)
        return comps, p_comb, bias, score, rho

    # ------------------------------------------------------------------ #
    def decision_components(self, comps: Dict[str, float],
                            n_pairs: int) -> Dict[str, float]:
        """THE single definition of which diagnostics enter the decision.

        Used identically by assess(), the analytical combined p-value, the
        bootstrap OBSERVED statistic and every bootstrap REPLICATE, so the
        null distribution always refers to the statistic actually used.

        MEASURED LIMITATION (documented): under NMR observation the
        composition-dependent quantification bias varies SMOOTHLY with z,
        producing rho ~ 0.3-0.7 even for a correct kinetic model - the
        z-autocorrelation cannot separate that from kinetic misfit there.
        With a nonzero systematic allowance it is therefore excluded from
        the DECISION (still computed and reported); with kappa = 0
        (direct observation) it is a decision component, where it is the
        most sensitive test."""
        excluded = {"z_autocorr"} if self.cfg.systematic_allowance > 0.0 \
            else set()
        if n_pairs < 8:
            excluded = excluded | {"z_autocorr"}
        return {k: v for k, v in comps.items() if k not in excluded}

    def combine(self, comps: Dict[str, float], n_pairs: int) -> float:
        """Sidak-combined min-p over the DECISION components."""
        used = self.decision_components(comps, n_pairs)
        if not used:
            return 1.0
        p_min = min(used.values())
        return float(1.0 - (1.0 - p_min) ** len(used))

    # ------------------------------------------------------------------ #
    def assess(self, ensemble: ModelEnsemble, round_no: int
               ) -> AdequacyReport:
        cfg = self.cfg
        alpha_round = cfg.alpha_campaign / max(cfg.n_rounds_planned, 1)

        best = ensemble.best
        comps_best, p_best, bias, score, rho = self._model_components(best)
        p_all: Dict[str, float] = {}
        for cm in ensemble.models:
            if cm is best:
                p_all[cm.name] = p_best
            else:
                _, p_c, _, _, _ = self._model_components(cm)
                p_all[cm.name] = p_c

        # T-trend value for the report (best model)
        theta = best.posterior.theta_map
        rws = self._whitened_by_measurement(best, theta) if theta is not None \
            else []
        T_r, _ = self._t_trend(best, rws)

        # QC of the spectral fits (informational here; the CONTROL response
        # to QC failure happens in the controller's gate BEFORE assimilation)
        n_fail = n_spec = 0
        for m in best.inference.measurements:
            for q in (m.meta or {}).get("qc", []):
                n_spec += 1
                if any(str(f).startswith("FAIL")
                       for f in q.get("qc_flags", [])):
                    n_fail += 1
        qc_frac = n_fail / n_spec if n_spec else 0.0

        # ---- state machine -------------------------------------------- #
        reasons: List[str] = []
        state = GovernorState.NORMAL_LEARNING
        if qc_frac > cfg.qc_fail_fraction:
            state = GovernorState.MEASUREMENT_FAULT
            reasons.append(f"{qc_frac:.0%} of assimilated spectra carry FAIL "
                           "QC (gate misconfigured?)")
        elif (all(pv < alpha_round for pv in p_all.values())
              or score > cfg.chi2_dof_ratio_override):
            state = GovernorState.MODEL_INADEQUATE
            reasons.append(
                f"every candidate rejected at alpha_round={alpha_round:.2e} "
                f"(campaign alpha={cfg.alpha_campaign:g} Bonferroni-spent "
                f"over {cfg.n_rounds_planned} rounds); best model "
                f"p={p_best:.2e}, chi2/dof={score:.2f}, "
                f"z-autocorr={rho:.2f}")
            if self.round_first_inadequate is None:
                self.round_first_inadequate = round_no
        elif float(np.max(ensemble.probs)) < cfg.discrimination_prob:
            state = GovernorState.MODEL_DISCRIMINATION
            reasons.append(
                "several models plausible: "
                + ", ".join(f"{cm.name} {pr:.2f}"
                            for cm, pr in zip(ensemble.models,
                                              ensemble.probs)))

        affected = [sp for sp, b in bias.items() if abs(b) > 3.0]
        region = ""
        if abs(rho) > 0.3:
            region = ("misfit smooth along z toward the outlet" if rho > 0
                      else "misfit smooth along z toward the inlet")
        if abs(T_r) > 0.5:
            region += ((" | " if region else "")
                       + "misfit correlated with temperature")

        return AdequacyReport(
            state=state, score=score, p_value=p_best, p_values_all=p_all,
            components=comps_best, alpha_round=alpha_round,
            species_bias=bias, z_trend_r=rho, T_trend_r=T_r,
            reasons=reasons, affected_species=affected,
            affected_region=region,
            round_detected=self.round_first_inadequate)

    # ------------------------------------------------------------------ #
    def min_replicates_for(self, alpha: float) -> int:
        """B must satisfy  1/(B+1) <= alpha  or the bootstrap p-value can
        never reach the threshold: the smallest attainable value is
        1/(B+1).  Returns the minimum admissible B."""
        return int(np.ceil(1.0 / max(alpha, 1e-12))) - 1

    def bootstrap_pvalue(self, ensemble: ModelEnsemble,
                         rng: np.random.Generator, B: Optional[int] = None,
                         alpha: Optional[float] = None) -> float:
        """Parametric-bootstrap empirical p-value of the DECISION statistic
        (same components as assess(), via decision_components) for the BEST
        model, WITH refit per replicate:

            p_boot = (1 + #{ minp*_b <= minp_obs }) / (B + 1)

        B defaults to the smallest value that can actually resolve the
        per-round threshold (>= ceil(1/alpha_round) - 1); passing a smaller
        B raises, because a bootstrap that cannot reach the threshold can
        never reject.  Expensive (B refits): for validation studies and
        post-hoc confirmation, not for every decision."""
        alpha_round = (alpha if alpha is not None
                       else self.cfg.alpha_campaign
                       / max(self.cfg.n_rounds_planned, 1))
        b_min = self.min_replicates_for(alpha_round)
        if B is None:
            B = b_min
        elif B < b_min:
            raise ValueError(
                f"B={B} cannot resolve alpha_round={alpha_round:.4g}: the "
                f"smallest attainable p-value is 1/(B+1)={1.0/(B+1):.4g}. "
                f"Use B >= {b_min}.")
        best = ensemble.best
        inf = best.inference
        theta0 = best.posterior.theta_map.copy()

        def _decision_minp() -> float:
            comps, _, _, _, _ = self._model_components(best)
            _rho, _p, n_pairs = self._autocorr(
                best, self._whitened_by_measurement(
                    best, best.posterior.theta_map))
            used = self.decision_components(comps, n_pairs)
            return min(used.values()) if used else 1.0

        minp_obs = _decision_minp()
        y_backup = [m.y.copy() for m in inf.measurements]
        count = 0
        try:
            for _ in range(B):
                for m, L in zip(inf.measurements, inf._chols):
                    clean = inf.predict(theta0, m)
                    m.y = clean + L @ rng.standard_normal(m.size)
                best.posterior.fit_map()
                if _decision_minp() <= minp_obs:
                    count += 1
        finally:
            for m, y in zip(inf.measurements, y_backup):
                m.y = y
            best.posterior.fit_map()
        return (1.0 + count) / (B + 1.0)
