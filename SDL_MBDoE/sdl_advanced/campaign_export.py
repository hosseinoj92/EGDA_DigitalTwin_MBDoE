"""
Per-campaign scientific record: the long-form tables of ONE autonomous run.

WHERE THIS SITS.  `audit_export.py` answers "what happened across a
benchmark of many scenarios, strategies and seeds"; this module answers
"what happened inside ONE campaign, round by round, in enough detail to
audit the decisions".  It therefore REUSES audit_export wherever a table
already exists there (model probabilities, posterior covariance, governor
diagnostics, blind predictions, resource events, identifiability) and adds
only the campaign-centred tables that have no benchmark equivalent: the
one-row-per-round summary, the per-acquisition concentration record, the QC
history, the per-round resource ledger and the transfer-line decomposition.

THE RULES THIS MODULE OBEYS, all for the same reason - a report that could
change a result would not be a report:

  * it runs only AFTER a campaign has returned, reading `res`,
    `res.history`, the inference/ensemble objects, `lab.meter`, measurement
    metadata and the passive recorder;
  * it draws NO random number, so nothing it does can shift a seeded stream;
  * it re-evaluates a DETERMINISTIC forward model where a report needs a
    predicted profile to plot the data against, and never an EIG, a
    posterior fit or any other quantity that was produced stochastically
    during the run - those are read back from the retained records;
  * hidden truth is read only through the same post-campaign channels the
    benchmark already uses for `param_err_pct` / `blind_rmse_M`, plus
    `lab.reveal_transfer_log()`, which is counted as a truth reveal exactly
    like `lab.reveal_truth()`.  Every truth-derived column is named
    `*_true*` or lives in a table documented as validation-only, and every
    one of them is optional: a record built without a truth source simply
    omits them.

DETERMINISM.  For a fixed seed and configuration every file this module
writes is byte-reproducible, with exactly two documented exceptions, both of
which measure the RUN rather than the chemistry and are named so:
`controller_timing.csv` (per-round wall clock) and the
`runtime_s_wall_clock` column of `strategy_comparison.csv`.  Column order is
first-mention order over deterministically-built rows, so it is stable too.

Table inventory (file name -> builder):

    campaign_rounds.csv          round_rows              one row per round
    measurements.csv             measurement_rows        one row per attempt
    concentrations.csv           concentration_rows      accepted acquisitions
    kinetic_parameters.csv       parameter_rows          per round, per param
    posterior_covariance.csv     (audit_export)          per round, per pair
    model_probabilities.csv      (audit_export)          per round, per model
    design_candidate_scores.csv  (recorder)              per round, per cand.
    spatial_candidate_scores.csv (recorder)              per round, per z
    qc_history.csv               qc_rows                 per round
    governor_history.csv         (audit_export)          per round
    resource_history.csv         resource_round_rows     per round
    resource_events.csv          (audit_export)          per metered event
    transfer_history.csv         transfer_rows           per acquisition
    controller_timing.csv        (recorder)              per round
    blind_predictions.csv        (audit_export)          validation only
    identifiability.csv          (audit_export)          final round
    strategy_comparison.csv      strategy_summary_rows   one row per strategy
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from sdl.campaign import StrategyResult

#: subdirectories of the campaign output root
LAYOUT = ("config", "data", "figures", "spectra", "report")

#: natural-unit label of every parameter this framework estimates
PARAM_UNITS = {"k1_ref": "L_per_mol_s", "k2_ref": "L_per_mol_s",
               "Ea1_J": "J_per_mol", "Ea2_J": "J_per_mol",
               "K1_ref": "dimensionless", "K2_ref": "dimensionless"}

#: units of the metered resource totals, for column naming
RESOURCE_UNITS = {"time_s": "s", "egda_mol": "mol", "acid_mol": "mol",
                  "liquid_mL": "mL", "waste_mL": "mL", "sample_mL": "mL",
                  "nmr_acquisitions": "count",
                  "nmr_reacquisitions": "count", "qc_rejected": "count",
                  "capillary_travel_m": "m", "condition_changes": "count",
                  "temperature_changes": "count", "energy_kJ": "kJ",
                  "reactor_conditions": "count", "spatial_samples": "count"}


# ------------------------------------------------------------------------- #
# the container the whole reporting layer is written against
# ------------------------------------------------------------------------- #
@dataclass
class CampaignRecord:
    """Everything ONE finished campaign retained, in one place.

    Nothing here is computed by this module: the runner fills it from what
    the campaign returned, so every consumer below reads the same objects
    the campaign itself produced."""
    scenario: str
    strategy: str
    seed: int
    spec: object
    res: object
    lab: object
    extra: object = None
    recorder: object = None
    #: audit_export.collect_campaign() output for this campaign
    audit: Dict[str, List[Dict]] = field(default_factory=dict)
    #: benchmark._round_metrics() output: (round rows, per-parameter rows)
    metric_rows: List[Dict] = field(default_factory=list)
    param_rows: List[Dict] = field(default_factory=list)
    species: Tuple[str, ...] = ()
    length_m: float = float("nan")
    spatial_mode: str = ""
    budget: int = 0
    observation_mode: str = ""
    #: SIMULATION VALIDATION ONLY - None on a record with no truth source
    truth: Optional[Dict[str, float]] = None
    #: (u, z, species) -> species-major true reactor concentrations, or None
    truth_predict: Optional[Callable] = None

    @property
    def stop_reason(self) -> str:
        return str(getattr(self.res, "stop_reason", "") or "")

    @property
    def is_baseline(self) -> bool:
        return isinstance(self.res, StrategyResult)

    @property
    def has_truth(self) -> bool:
        return self.truth is not None

    def tag(self) -> Dict:
        return {"scenario": self.scenario, "strategy": self.strategy,
                "seed": int(self.seed)}


# ------------------------------------------------------------------------- #
# small shared helpers
# ------------------------------------------------------------------------- #
def _f(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def _u_cols(u) -> Dict:
    """The commanded experiment, with units in every column name."""
    return {"T_C": _f(getattr(u, "T_C", np.nan)),
            "Q1_mL_min": _f(getattr(u, "Q1_mL_min", np.nan)),
            "Q2_mL_min": _f(getattr(u, "Q2_mL_min", np.nan)),
            "Q_total_mL_min": _f(getattr(u, "Q1_mL_min", np.nan)
                                 + getattr(u, "Q2_mL_min", np.nan)),
            "C_EGDA_M": _f(getattr(u, "C_EGDA_M", np.nan)),
            "C_cat_M": _f(getattr(u, "C_cat_M", np.nan))}


def _join(xs, fmt: str = "{:.6g}") -> str:
    return ";".join(fmt.format(float(x)) for x in xs)


def prepare_outdir(root: str) -> Dict[str, str]:
    """Create the campaign layout under an ALREADY-RESOLVED root.

    The root itself is the runner's decision (and its overwrite policy);
    this only lays out the subfolders inside it."""
    paths = {"root": root}
    for sub in LAYOUT:
        p = os.path.join(root, sub)
        os.makedirs(p, exist_ok=True)
        paths[sub] = p
    return paths


def write_rows(rows: Sequence[Dict], path: str,
               verbose: bool = True) -> Optional[str]:
    """One CSV, with a DETERMINISTIC column order.

    Columns appear in the order the rows first mention them, which for
    deterministically-built rows is itself deterministic - so two runs of
    the same configuration produce byte-comparable files."""
    if not rows:
        return None
    keys: List[str] = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, restval="")
        w.writeheader()
        w.writerows(rows)
    if verbose:
        print(f"saved: {path}")
    return path


# ------------------------------------------------------------------------- #
# per-round model access (the SAME resolution the benchmark scoring uses)
# ------------------------------------------------------------------------- #
def model_for_round(res, rec):
    """(space, bridge, candidate_model_or_None) that produced this round's
    reported parameters.  Mirrors benchmark._round_metrics exactly, so a
    prediction drawn here is the prediction that round's numbers describe."""
    if isinstance(res, StrategyResult):
        inf = res.inference
        return (inf.space, inf.bridge, None) if inf is not None \
            else (None, None, None)
    ens = getattr(res, "ensemble", None)
    best = getattr(rec, "best_model", "wls")
    if ens is not None and best != "wls":
        names = [c.name for c in ens.models]
        if best in names:
            cm = ens.models[names.index(best)]
            return cm.space, cm.bridge, cm
    inf = getattr(res, "inference", None)
    return (inf.space, inf.bridge, None) if inf is not None \
        else (None, None, None)


def natural_bounds(space) -> Dict[str, Tuple[float, float]]:
    """The estimation box, per parameter, in NATURAL units.

    Reported alongside every estimate because an estimate resting on one of
    these is not an estimate: it is the edge of the declared search space,
    and the interval next to it is not a confidence interval."""
    out: Dict[str, Tuple[float, float]] = {}
    if space is None:
        return out
    try:
        lo, hi = space.bounds()
    except Exception:                                  # pragma: no cover
        return out
    for q, k in enumerate(space.param_keys):
        if space.is_log(q):
            out[k] = (float(math.exp(lo[q])), float(math.exp(hi[q])))
        else:
            out[k] = (float(lo[q] * 1e3), float(hi[q] * 1e3))
    return out


def _rel_ci_pct(space, theta_nat, sigma) -> Dict[str, float]:
    if space is None or sigma is None:
        return {}
    try:
        vals = space.rel_ci_percent(space.to_vector(theta_nat),
                                    np.asarray(sigma, dtype=float))
    except Exception:                                  # pragma: no cover
        return {}
    return {k: _f(vals[q]) for q, k in enumerate(space.param_keys)}


def _corr_max_offdiag(rec) -> float:
    """Worst |correlation| between two estimated parameters this round.

    Taken from the record the round already wrote where it is there
    (strategy F/E), and otherwise read off the round's own correlation
    matrix - never refitted."""
    v = _f(getattr(rec, "corr_max_offdiag", np.nan))
    if np.isfinite(v):
        return v
    corr = getattr(rec, "theta_corr", None)
    if corr is None:
        report = getattr(rec, "report", None)
        corr = getattr(report, "corr", None)
    if corr is None:
        return float("nan")
    c = np.abs(np.asarray(corr, dtype=float))
    np.fill_diagonal(c, 0.0)
    return float(np.max(c)) if c.size else float("nan")


# ------------------------------------------------------------------------- #
# 1. campaign_rounds.csv - the central per-round record
# ------------------------------------------------------------------------- #
def round_rows(recs: Sequence[CampaignRecord]) -> List[Dict]:
    """ONE row per (strategy, round), carrying everything that round decided,
    measured, inferred and spent.

    Every column is a value the campaign already produced: the design comes
    from the round record, the accuracy/uncertainty columns from the
    benchmark's own `_round_metrics` (so this table cannot disagree with the
    benchmark), the resources from `ResourceMeter.totals()` snapshots, and
    the truth-side columns - present only for a simulation record - from the
    same post-campaign scoring."""
    rows: List[Dict] = []
    for rec_c in recs:
        res = rec_c.res
        by_round = {int(r["round"]): r for r in rec_c.metric_rows}
        # the WINNING candidate row of the decision that produced each
        # round's experiment (the recorder stamps it with the round it is
        # designing FOR, so the join is exact)
        won = {int(r["round"]): r
               for r in (rec_c.audit.get("design_candidate_scores", []) or [])
               if int(_f(r.get("selected", 0))) == 1}
        prm_by_round: Dict[int, List[Dict]] = {}
        for pr in rec_c.param_rows:
            prm_by_round.setdefault(int(pr["round"]), []).append(pr)
        n_hist = len(getattr(res, "history", ()) or ())
        for i, rr in enumerate(getattr(res, "history", ()) or ()):
            rnd = int(rr.round)
            met = by_round.get(rnd, {})
            space, _bridge, _cm = model_for_round(res, rr)
            theta = dict(getattr(rr, "theta_nat", {}) or {})
            sigma = getattr(rr, "sigma_scaled", None)
            report = getattr(rr, "report", None)
            if sigma is None and report is not None:
                sigma = getattr(report, "sigma", None)
            bound = tuple(getattr(rr, "bound_active", ()) or
                          (getattr(report, "active_bounds", ()) or ()))
            zs = np.asarray(getattr(rr, "z_positions", []),
                            dtype=float).ravel()
            if zs.size == 0 and rec_c.is_baseline:
                # baselines record no positions: they measure the ports (or
                # the outlet) of their own measurement for that round
                meas = _assimilated(res)
                if i < len(meas):
                    zs = np.asarray(meas[i].z_m, dtype=float).ravel()
            rel_ci = _rel_ci_pct(space, theta, sigma)
            nb = natural_bounds(space)
            probs = dict(getattr(rr, "model_probs", {}) or {})
            gov = getattr(rr, "governor", None)
            resources = dict(getattr(rr, "resources", {}) or {})
            if not resources:
                adapter = rec_c.extra
                hist = list(getattr(adapter, "totals_history", ()) or ())
                resources = dict(hist[i]) if i < len(hist) else {}
            row = {
                **rec_c.tag(), "round": rnd,
                "rounds_completed": n_hist,
                "rounds_planned": int(rec_c.budget),
                "observation_mode": rec_c.observation_mode,
                "spatial_mode": rec_c.spatial_mode,
                # ---- the experiment this round ran --------------------- #
                **_u_cols(rr.u),
                "n_positions": int(zs.size),
                "z_positions_m": _join(zs),
                "z_over_L": _join(zs / rec_c.length_m) if rec_c.length_m
                else "",
                # ---- why it was chosen --------------------------------- #
                "design_mode": str(getattr(rr, "design_mode", "fixed")),
                "eig_param_nats": _f(getattr(rr, "eig_param", np.nan)),
                "eig_model_nats": _f(getattr(rr, "eig_model", np.nan)),
                # ---- what was inferred --------------------------------- #
                "best_model": str(getattr(rr, "best_model", "wls")),
                "n_data": int(getattr(rr, "n_data", 0) or 0),
                "n_params_estimated": (len(space.param_keys)
                                       if space is not None else 0),
            }
            for k in sorted(theta):
                unit = PARAM_UNITS.get(k, "natural")
                row[f"theta_{k}_{unit}"] = _f(theta[k])
            if space is not None and sigma is not None:
                for q, k in enumerate(space.param_keys):
                    row[f"sigma_scaled_{k}"] = (_f(sigma[q])
                                                if q < len(sigma)
                                                else float("nan"))
            for k in sorted(rel_ci):
                row[f"rel_ci95_pct_{k}"] = rel_ci[k]
            for k in sorted(nb):
                row[f"bound_lo_{k}"] = nb[k][0]
                row[f"bound_hi_{k}"] = nb[k][1]
            row.update({
                "max_rel_ci_pct": _f(met.get("max_rel_ci_pct", np.nan)),
                "corr_max_offdiag": _corr_max_offdiag(rr),
                "n_bound_active": len(bound),
                "bound_active_params": ";".join(bound),
                # ---- model discrimination ------------------------------ #
                "n_models": len(probs),
                "model_entropy_nats": _f(met.get("model_entropy", np.nan)),
                "probs_reliable": _f(met.get("probs_reliable", np.nan)),
                "evidence_warning": str(met.get("evidence_warning", ""))[:300],
            })
            for name in sorted(probs):
                row[f"p_model_{name}"] = _f(probs[name])
            row.update({
                # ---- governor ------------------------------------------ #
                "governor_state": (gov.state if gov is not None
                                   else str(met.get("gov_state", ""))),
                "governor_chi2_over_dof": (_f(gov.score) if gov is not None
                                           else _f(met.get("gov_score",
                                                           np.nan))),
                "governor_p_value": (_f(gov.p_value) if gov is not None
                                     else _f(met.get("gov_p", np.nan))),
                "governor_p_bootstrap": (_f(getattr(gov, "p_boot", np.nan))
                                         if gov is not None else float("nan")),
                "governor_alpha_round": (_f(getattr(gov, "alpha_round",
                                                    np.nan))
                                         if gov is not None else float("nan")),
                "governor_dispersion_phi": (_f(getattr(gov, "dispersion",
                                                       np.nan))
                                            if gov is not None
                                            else float("nan")),
                "governor_affected_species": (
                    ";".join(getattr(gov, "affected_species", None) or [])
                    if gov is not None else ""),
                "governor_affected_region": (
                    str(getattr(gov, "affected_region", "") or "")
                    if gov is not None else ""),
                "governor_trigger_reasons": (
                    " | ".join(getattr(gov, "reasons", None) or [])[:400]
                    if gov is not None else ""),
                # ---- QC ------------------------------------------------- #
                "qc_rejected_this_round": int(getattr(rr, "n_rejected", 0)
                                              or 0),
                "qc_reacquired_this_round": int(getattr(rr, "n_reacquired", 0)
                                                or 0),
            })
            # ---- cumulative resources after this round ------------------ #
            for k in sorted(resources):
                row[f"cum_{k}_{RESOURCE_UNITS.get(k, 'unit')}"] = \
                    _f(resources[k])
            # ---- POST-CAMPAIGN VALIDATION (simulation only) ------------- #
            if rec_c.has_truth:
                row["param_err_pct_vs_truth"] = _f(
                    met.get("param_err_pct", np.nan))
                row["blind_rmse_M_vs_truth"] = _f(
                    met.get("blind_rmse_M", np.nan))
                covered = [pr for pr in prm_by_round.get(rnd, [])
                           if np.isfinite(_f(pr.get("covered95", np.nan)))]
                row["n_params_covered_by_ci95"] = int(
                    sum(int(pr["covered95"]) for pr in covered))
            # ---- the winning candidate's own objective decomposition --- #
            # The selector's two objective terms are NOT the same quantity
            # in every mode: in `eig` mode they are the parameter and
            # model-discrimination expected information gains, and in
            # `diagnostic` mode they are the model disagreement and the
            # exploration stress.  They therefore travel with a column that
            # NAMES them, and the EIG columns above stay empty unless the
            # round really produced an EIG - a diagnostic score reported as
            # an EIG would be a fabricated number.
            w = won.get(rnd, {})
            mode = str(w.get("design_mode", row["design_mode"]))
            names = ("eig_param;eig_model" if mode in ("eig", "predictive")
                     else ("model_disagreement;exploration_stress"
                           if mode == "diagnostic" else ""))
            row.update({
                "selected_utility": _f(w.get("utility_total", np.nan)),
                "selected_resource_penalty": _f(w.get("resource_penalty",
                                                      np.nan)),
                "selected_screen_score": _f(w.get("screen_score", np.nan)),
                "design_objective_term_1": _f(w.get("eig_param", np.nan)),
                "design_objective_term_2": _f(w.get("eig_model", np.nan)),
                "design_objective_term_names": names,
                "n_candidates_screened": int(sum(
                    1 for r in (rec_c.audit.get("design_candidate_scores",
                                                []) or [])
                    if int(_f(r.get("round", -1))) == rnd)),
            })
            row["stop_reason"] = rec_c.stop_reason
            row["is_final_round"] = int(i == n_hist - 1)
            rows.append(row)
    return rows


# ------------------------------------------------------------------------- #
# 2/3. the measurement record
# ------------------------------------------------------------------------- #
def _assimilated(res) -> List:
    """Measurements that entered the posterior, in assimilation order."""
    if isinstance(res, StrategyResult):
        inf = getattr(res, "inference", None)
        return list(inf.measurements) if inf is not None else []
    ens = getattr(res, "ensemble", None)
    if ens is not None:
        return list(ens.best.inference.measurements)
    inf = getattr(res, "inference", None)
    return list(inf.measurements) if inf is not None else []


def _round_of_measurement(res, rec_c) -> List[int]:
    """Round number of each assimilated measurement, by the same walk
    audit_export.design_history_rows uses."""
    out: List[int] = []
    meas = _assimilated(res)
    if isinstance(res, StrategyResult):
        for i, rr in enumerate(res.history):
            if i < len(meas):
                out.append(int(rr.round))
        return out
    mi = 0
    for rr in res.history:
        want = len(np.asarray(rr.z_positions, dtype=float).ravel())
        taken = 0
        while taken < want and mi < len(meas):
            out.append(int(rr.round))
            taken += meas[mi].n_z
            mi += 1
    while len(out) < len(meas):
        out.append(int(res.history[-1].round) if res.history else 0)
    return out


def measurement_rows(recs: Sequence[CampaignRecord]) -> List[Dict]:
    """EVERY acquisition attempt, accepted or not, one row per species.

    For the strategies that run through the QC gate this is the recorder's
    own `nmr_measurements_long` (the only place a REJECTED spectrum survives
    at all, since the gate drops it before assimilation).  Baselines have no
    gate and no recorder, so their rows are reconstructed from the
    measurements themselves and are accepted by construction - which the
    `disposition` column states rather than implies."""
    rows: List[Dict] = []
    for rec_c in recs:
        rec_rows = list(rec_c.audit.get("nmr_measurements_long", []) or [])
        if rec_rows:
            for r in rec_rows:
                z = _f(r.get("z_m", np.nan))
                rows.append({**r,
                             "z_over_L": (z / rec_c.length_m
                                          if rec_c.length_m else float("nan")),
                             "source": "qc_gate_recorder"})
            continue
        meas = _assimilated(rec_c.res)
        rounds = _round_of_measurement(rec_c.res, rec_c)
        order = 0
        for mi, m in enumerate(meas):
            n_s, n_z = len(m.species), m.n_z
            qc_all = (m.meta or {}).get("qc", [])
            for k in range(n_z):
                order += 1
                idx = [i * n_z + k for i in range(n_s)]
                cov = (m.cov_y[np.ix_(idx, idx)]
                       if m.cov_y is not None else None)
                sig = (np.sqrt(np.maximum(np.diag(np.asarray(cov, float)),
                                          0.0))
                       if cov is not None else np.full(n_s, np.nan))
                qc = qc_all[k] if k < len(qc_all) else {}
                z = float(m.z_m[k])
                for i, sp in enumerate(m.species):
                    rows.append({
                        **rec_c.tag(),
                        "round": rounds[mi] if mi < len(rounds) else 0,
                        "acquisition_order": order, "attempt": 1,
                        "disposition": "accepted",
                        "assimilated": 1,
                        "z_m": z,
                        "z_over_L": (z / rec_c.length_m if rec_c.length_m
                                     else float("nan")),
                        **_u_cols(m.u),
                        "species": sp,
                        "conc_fitted_M": float(m.y[i * n_z + k]),
                        "sigma_M": float(sig[i]),
                        "censored": int(sp in (qc.get("censored", []) or [])),
                        "qc_flags": ";".join(str(x) for x in
                                             qc.get("qc_flags", [])),
                        "qc_fail": 0,
                        "residual_rms": _f(qc.get("residual_rms", np.nan)),
                        "fit_condition_number": _f(
                            qc.get("condition_number", np.nan)),
                        "observation_mode": str(qc.get("mode", "")),
                        "source": "assimilated_measurement",
                    })
    return rows


def concentration_rows(recs: Sequence[CampaignRecord]) -> List[Dict]:
    """The ACCEPTED spatial measurements: what the NMR pathway reported at
    each position, its uncertainty and cross-species covariance, the current
    model's prediction there, and - for a simulation record - the hidden
    true reactor composition at the same point.

    The predictions are a DETERMINISTIC re-evaluation of the round's own
    fitted model at the measured positions (`predict_at` for the expected
    observation, `concentrations_at` for the reactor state).  Nothing
    stochastic is recomputed: the parameters, the model choice and the data
    are all read back from the finished campaign."""
    rows: List[Dict] = []
    for rec_c in recs:
        res = rec_c.res
        meas = _assimilated(res)
        rounds = _round_of_measurement(res, rec_c)
        rec_by_round = {int(r.round): r for r in
                        (getattr(res, "history", ()) or ())}
        order = 0
        for mi, m in enumerate(meas):
            rnd = rounds[mi] if mi < len(rounds) else 0
            rr = rec_by_round.get(rnd)
            space, bridge, cm = (model_for_round(res, rr) if rr is not None
                                 else (None, None, None))
            z = np.asarray(m.z_m, dtype=float)
            n_s, n_z = len(m.species), m.n_z
            pred_obs = pred_reactor = None
            if rr is not None and space is not None:
                theta_vec = space.to_vector(rr.theta_nat)
                inf = (cm.inference if cm is not None
                       else getattr(res, "inference", None))
                if inf is not None:
                    pred_obs = np.asarray(
                        inf.predict_at(theta_vec, m.u, z, m.species),
                        dtype=float)
                if bridge is not None:
                    pred_reactor = np.asarray(
                        bridge.concentrations_at(
                            space.to_natural(theta_vec), m.u, z,
                            tuple(m.species)), dtype=float)
            truth_prof = None
            if rec_c.truth_predict is not None:
                truth_prof = np.asarray(
                    rec_c.truth_predict(m.u, z, tuple(m.species)),
                    dtype=float)
            qc_all = (m.meta or {}).get("qc", [])
            for k in range(n_z):
                order += 1
                idx = [i * n_z + k for i in range(n_s)]
                cov = (np.asarray(m.cov_y[np.ix_(idx, idx)], dtype=float)
                       if m.cov_y is not None else None)
                qc = qc_all[k] if k < len(qc_all) else {}
                for i, sp in enumerate(m.species):
                    j = i * n_z + k
                    sig = (float(np.sqrt(max(cov[i, i], 0.0)))
                           if cov is not None else float("nan"))
                    row = {
                        **rec_c.tag(), "round": rnd,
                        "acquisition_order": order,
                        **_u_cols(m.u),
                        "z_m": float(z[k]),
                        "z_over_L": (float(z[k]) / rec_c.length_m
                                     if rec_c.length_m else float("nan")),
                        "species": sp,
                        "c_measured_M": float(m.y[j]),
                        "sigma_M": sig,
                        # WHERE the uncertainty came from: the deconvolution
                        # reports its own covariance, whereas the baselines
                        # are handed data with cov_y stripped and assume
                        # their configured NoiseModel instead - so a blank
                        # sigma here means "not reported by the
                        # measurement", never "no uncertainty".
                        "sigma_source": ("measurement_covariance"
                                         if cov is not None
                                         else "assumed_noise_model"),
                        "ci95_lo_M": float(m.y[j]) - 1.96 * sig,
                        "ci95_hi_M": float(m.y[j]) + 1.96 * sig,
                        "censored": int(sp in (qc.get("censored", []) or [])),
                        "qc_flags": ";".join(str(x) for x in
                                             qc.get("qc_flags", [])),
                        "observation_mode": str(qc.get("mode", "")),
                        "best_model": (str(getattr(rr, "best_model", "wls"))
                                       if rr is not None else ""),
                        "c_model_observed_M": (float(pred_obs[j])
                                               if pred_obs is not None
                                               else float("nan")),
                        "c_model_reactor_M": (float(pred_reactor[j])
                                              if pred_reactor is not None
                                              else float("nan")),
                    }
                    row["residual_M"] = (row["c_measured_M"]
                                         - row["c_model_observed_M"])
                    row["standardized_residual"] = (
                        row["residual_M"] / sig if sig > 0 else float("nan"))
                    if cov is not None:
                        for i2, sp2 in enumerate(m.species):
                            row[f"cov_M2_with_{sp2}"] = float(cov[i, i2])
                    if truth_prof is not None:
                        row["c_true_reactor_M"] = float(truth_prof[j])
                        row["error_vs_true_M"] = (row["c_measured_M"]
                                                  - row["c_true_reactor_M"])
                    rows.append(row)
    return rows


# ------------------------------------------------------------------------- #
# 4. kinetic parameters
# ------------------------------------------------------------------------- #
def parameter_rows(recs: Sequence[CampaignRecord]) -> List[Dict]:
    """Per (round, parameter): estimate, interval, identifiability flags and
    - simulation only - the true value and the realized error.

    The numbers come straight from the benchmark's own `_param_rows`, so
    this table and the benchmark's parameter table cannot drift apart; this
    adds the unit, the estimation box and the campaign tags."""
    rows: List[Dict] = []
    for rec_c in recs:
        res = rec_c.res
        rec_by_round = {int(r.round): r for r in
                        (getattr(res, "history", ()) or ())}
        bounds_cache: Dict[int, Dict] = {}
        for pr in rec_c.param_rows:
            rnd = int(pr["round"])
            if rnd not in bounds_cache:
                rr = rec_by_round.get(rnd)
                space = (model_for_round(res, rr)[0] if rr is not None
                         else None)
                bounds_cache[rnd] = natural_bounds(space)
            k = str(pr["param"])
            lo, hi = bounds_cache[rnd].get(k, (float("nan"), float("nan")))
            row = {**rec_c.tag(), "round": rnd,
                   "param": k,
                   "unit": PARAM_UNITS.get(k, "natural"),
                   "estimate_natural": _f(pr.get("estimate", np.nan)),
                   "sigma_scaled": _f(pr.get("sigma_scaled", np.nan)),
                   "ci95_lo_natural": _f(pr.get("ci_lo", np.nan)),
                   "ci95_hi_natural": _f(pr.get("ci_hi", np.nan)),
                   "rel_ci95_width_pct": _f(pr.get("rel_width_pct", np.nan)),
                   "bound_active": int(pr.get("bound_active", 0)),
                   "bound_lo_natural": lo, "bound_hi_natural": hi}
            if rec_c.has_truth:
                row.update({
                    "true_value_natural": _f(pr.get("true_value", np.nan)),
                    "rel_error_pct_vs_truth": _f(pr.get("rel_error_pct",
                                                        np.nan)),
                    "covered_by_ci95": _f(pr.get("covered95", np.nan))})
            rows.append(row)
    return rows


# ------------------------------------------------------------------------- #
# 5. QC history
# ------------------------------------------------------------------------- #
def _qc_reason(flags: Sequence[str]) -> str:
    fails = [str(f) for f in flags if str(f).startswith("FAIL")]
    return ";".join(fails)


def qc_rows(recs: Sequence[CampaignRecord],
            measurements: Sequence[Dict] = ()) -> List[Dict]:
    """Per round: what the gate saw and what it did about it.

    Built from the unified measurement table so EVERY strategy appears,
    including the ones that run no gate at all - a baseline row says
    `qc_gate_active = 0` rather than reporting zero rejections, because
    "nothing was rejected" and "nothing could be rejected" are different
    facts and a reader must not have to infer which one they are looking at.

    The rolling and consecutive counters are re-derived from the recorded
    acquisition DISPOSITIONS, which is a pure replay of the gate's own
    bookkeeping (QCMonitor counts acquisitions, one entry each) - no
    spectrum is refitted and no verdict is re-decided; whether the gate
    actually tripped is read from the campaign's stop reason."""
    rows: List[Dict] = []
    by_campaign: Dict[Tuple[str, str, int], List[Dict]] = {}
    for r in measurements:
        by_campaign.setdefault((str(r.get("scenario", "")),
                                str(r.get("strategy", "")),
                                int(_f(r.get("seed", 0)))), []).append(r)
    for rec_c in recs:
        key = (rec_c.scenario, rec_c.strategy, int(rec_c.seed))
        acq = by_campaign.get(key)
        if acq is None:
            acq = list(rec_c.audit.get("nmr_measurements_long", []) or [])
        gate_active = any(str(r.get("source", "")) == "qc_gate_recorder"
                          for r in acq)
        # one entry per ACQUISITION (the species rows repeat it)
        per_acq: Dict[Tuple[int, int, int], Dict] = {}
        for r in acq:
            key = (int(r.get("round", 0)), int(r.get("acquisition_order", 0)),
                   int(r.get("attempt", 0)))
            e = per_acq.setdefault(key, {"round": key[0],
                                         "disposition": r.get("disposition",
                                                              ""),
                                         "z_m": _f(r.get("z_m", np.nan)),
                                         "flags": set()})
            for f in str(r.get("qc_flags", "") or "").split(";"):
                if f:
                    e["flags"].add(f)
        gate_tripped = "MEASUREMENT_FAULT" in rec_c.stop_reason
        consecutive = 0
        max_consecutive = 0
        window: List[int] = []
        rounds = sorted({e["round"] for e in per_acq.values()}) or \
            [int(r.round) for r in (getattr(rec_c.res, "history", ()) or ())]
        by_round: Dict[int, List[Dict]] = {}
        for key in sorted(per_acq):
            by_round.setdefault(key[0], []).append(per_acq[key])
        hist_by_round = {int(r.round): r for r in
                         (getattr(rec_c.res, "history", ()) or ())}
        for rnd in rounds:
            entries = by_round.get(rnd, [])
            n_att = len(entries)
            n_acc = sum(1 for e in entries
                        if str(e["disposition"]).startswith("accepted"))
            n_rej = sum(1 for e in entries if e["disposition"] == "rejected")
            n_re = sum(1 for e in entries
                       if e["disposition"] == "failed_qc_reacquiring")
            reasons: List[str] = []
            for e in entries:
                r_txt = _qc_reason(sorted(e["flags"]))
                if r_txt:
                    reasons.append(r_txt)
                if str(e["disposition"]).startswith("accepted"):
                    consecutive = 0
                    window.append(0)
                elif e["disposition"] == "rejected":
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                    window.append(1)
                if len(window) > 8:
                    window.pop(0)
            rr = hist_by_round.get(rnd)
            rows.append({
                **rec_c.tag(), "round": int(rnd),
                "observation_mode": rec_c.observation_mode,
                "qc_gate_active": int(gate_active),
                "n_acquisition_attempts": n_att,
                "n_accepted": n_acc,
                "n_rejected": (int(getattr(rr, "n_rejected", n_rej) or 0)
                               if rr is not None else n_rej),
                "n_reacquired": (int(getattr(rr, "n_reacquired", n_re) or 0)
                                 if rr is not None else n_re),
                "reject_fraction": (n_rej / n_att if n_att else 0.0),
                "consecutive_rejects_after_round": consecutive,
                "max_consecutive_rejects_so_far": max_consecutive,
                "rejects_in_last_8_acquisitions": int(sum(window)),
                "failure_reasons": " | ".join(sorted(set(reasons)))[:400],
                "gate_tripped_this_campaign": int(gate_tripped),
                "stop_reason": rec_c.stop_reason,
            })
    return rows


# ------------------------------------------------------------------------- #
# 6. resources per round
# ------------------------------------------------------------------------- #
def resource_round_rows(recs: Sequence[CampaignRecord]) -> List[Dict]:
    """Cumulative and per-round metered cost.

    The cumulative values are the `ResourceMeter.totals()` snapshots the
    rounds already stored; the deltas are their differences, so the ledger
    and the event log in `resource_events.csv` describe the same meter."""
    rows: List[Dict] = []
    for rec_c in recs:
        prev: Dict[str, float] = {}
        hist = getattr(rec_c.res, "history", ()) or ()
        adapter_hist = list(getattr(rec_c.extra, "totals_history", ()) or ())
        for i, rr in enumerate(hist):
            tot = dict(getattr(rr, "resources", {}) or {})
            if not tot and i < len(adapter_hist):
                tot = dict(adapter_hist[i])
            row = {**rec_c.tag(), "round": int(rr.round)}
            for k in sorted(tot):
                unit = RESOURCE_UNITS.get(k, "unit")
                row[f"cum_{k}_{unit}"] = _f(tot[k])
                row[f"delta_{k}_{unit}"] = _f(tot[k]) - _f(prev.get(k, 0.0))
            prev = tot
            rows.append(row)
    return rows


# ------------------------------------------------------------------------- #
# 7. transfer line (SIMULATION VALIDATION ONLY)
# ------------------------------------------------------------------------- #
def transfer_rows(recs: Sequence[CampaignRecord]) -> List[Dict]:
    """Reactor sampling point -> NMR cell -> reported concentration, per
    acquisition and species.

    This is the only table that separates TRANSPORT distortion from
    QUANTIFICATION error, because it is the only place both intermediate
    states exist.  Both are truth-side, so the record is available only
    where the laboratory kept one (`store_transfer_log`) and is read through
    `reveal_transfer_log()`, which counts as a truth reveal - it is a
    post-campaign validation artifact and nothing in the loop can see it."""
    rows: List[Dict] = []
    for rec_c in recs:
        lab = rec_c.lab
        if not rec_c.has_truth or lab is None or \
                not hasattr(lab, "reveal_transfer_log"):
            continue
        log = lab.reveal_transfer_log()
        for e in log:
            for sp in e.get("c_reactor_M", {}):
                c_r = _f(e["c_reactor_M"].get(sp, np.nan))
                c_c = _f(e.get("c_cell_M", {}).get(sp, np.nan))
                c_m = _f(e.get("c_measured_M", {}).get(sp, np.nan))
                sig = _f(e.get("sigma_M", {}).get(sp, np.nan))
                rows.append({
                    **rec_c.tag(),
                    "acquisition_index": int(e.get("acquisition_index", 0)),
                    "reacquisition": int(e.get("reacquisition", 0)),
                    "z_m": _f(e.get("z_m", np.nan)),
                    "z_over_L": (_f(e.get("z_m", np.nan)) / rec_c.length_m
                                 if rec_c.length_m else float("nan")),
                    "T_C": _f(e.get("T_C", np.nan)),
                    "Q_total_mL_min": _f(e.get("Q_total_mL_min", np.nan)),
                    "C_EGDA_M": _f(e.get("C_EGDA_M", np.nan)),
                    "C_cat_M": _f(e.get("C_cat_M", np.nan)),
                    "T_line_C": _f(e.get("T_line_C", np.nan)),
                    "transfer_enabled": int(e.get("transfer_enabled", 0)),
                    "mean_tau_line_s": _f(e.get("mean_tau_line_s", np.nan)),
                    "species": sp,
                    "c_reactor_true_M": c_r,
                    "c_cell_true_M": c_c,
                    "c_measured_M": c_m,
                    "sigma_M": sig,
                    "transport_delta_M": c_c - c_r,
                    "quantification_delta_M": c_m - c_c,
                    "total_delta_M": c_m - c_r,
                    "transport_delta_sigma": ((c_c - c_r) / sig
                                              if sig > 0 else float("nan")),
                    "quantification_delta_sigma": ((c_m - c_c) / sig
                                                   if sig > 0
                                                   else float("nan")),
                    "qc_flags": ";".join(str(x) for x in
                                         (e.get("qc_flags") or [])),
                })
    return rows


# ------------------------------------------------------------------------- #
# 8. final strategy comparison
# ------------------------------------------------------------------------- #
def strategy_summary_rows(recs: Sequence[CampaignRecord]) -> List[Dict]:
    """One row per strategy actually run: where it ended up, and what it
    spent getting there."""
    rows: List[Dict] = []
    for rec_c in recs:
        hist = list(getattr(rec_c.res, "history", ()) or ())
        met = sorted(rec_c.metric_rows, key=lambda r: int(r["round"]))
        last_met = met[-1] if met else {}
        last = hist[-1] if hist else None
        tot = {}
        meter = getattr(rec_c.lab, "meter", None)
        if meter is not None:
            tot = meter.totals()
        acq = rec_c.audit.get("nmr_measurements_long", []) or []
        n_species = max(len(rec_c.species), 1)
        n_attempts = len({(int(r.get("round", 0)),
                           int(r.get("acquisition_order", 0)),
                           int(r.get("attempt", 0))) for r in acq})
        z_all = [np.asarray(getattr(r, "z_positions", []),
                            dtype=float).ravel() for r in hist]
        row = {
            **rec_c.tag(),
            "observation_mode": rec_c.observation_mode,
            "spatial_mode": rec_c.spatial_mode,
            "rounds_planned": int(rec_c.budget),
            "rounds_completed": len(hist),
            "n_conditions_run": _f(tot.get("reactor_conditions", np.nan)),
            "n_spatial_samples": _f(tot.get("spatial_samples", np.nan)),
            "n_nmr_acquisitions": _f(tot.get("nmr_acquisitions", np.nan)),
            "n_nmr_reacquisitions": _f(tot.get("nmr_reacquisitions", np.nan)),
            "n_qc_rejected": _f(tot.get("qc_rejected", np.nan)),
            "n_acquisition_attempts_recorded": n_attempts,
            "n_measurement_rows": len(acq) // n_species if acq else 0,
            "n_positions_final_round": (int(z_all[-1].size) if z_all
                                        else 0),
            "best_model_final": (str(getattr(last, "best_model", "wls"))
                                 if last is not None else ""),
            "governor_state_final": str(last_met.get("gov_state", "")),
            "max_rel_ci_pct_final": _f(last_met.get("max_rel_ci_pct",
                                                    np.nan)),
            "corr_max_offdiag_final": (_corr_max_offdiag(last)
                                       if last is not None else float("nan")),
            "time_s": _f(tot.get("time_s", np.nan)),
            "egda_mol": _f(tot.get("egda_mol", np.nan)),
            "waste_mL": _f(tot.get("waste_mL", np.nan)),
            "energy_kJ": _f(tot.get("energy_kJ", np.nan)),
            "capillary_travel_m": _f(tot.get("capillary_travel_m", np.nan)),
            "runtime_s_wall_clock": _f(getattr(rec_c.res, "runtime_s",
                                               np.nan)),
            "stop_reason": rec_c.stop_reason or "budget exhausted",
        }
        if rec_c.has_truth:
            row["param_err_pct_final_vs_truth"] = _f(
                last_met.get("param_err_pct", np.nan))
            row["blind_rmse_M_final_vs_truth"] = _f(
                last_met.get("blind_rmse_M", np.nan))
            ident = rec_c.audit.get("identifiability_summary", []) or []
            errs = [_f(r.get("rel_error_pct", np.nan)) for r in ident]
            errs = [e for e in errs if np.isfinite(e)]
            row["worst_param_rel_error_pct"] = (max(errs) if errs
                                                else float("nan"))
        rows.append(row)
    return rows


# ------------------------------------------------------------------------- #
# 9. stored spectra -> one CSV each, plus an index
# ------------------------------------------------------------------------- #
def export_spectra(rec_c: CampaignRecord, outdir: str,
                   max_per_campaign: int = 12,
                   verbose: bool = True) -> List[Dict]:
    """Write the retained deconvolutions (spectrum, fit, residual, per-species
    components) as CSVs and return one index row each.

    The laboratory logged these AS IT MEASURED (`store_spectra`); nothing is
    re-simulated or refitted here, so the traces are the actual spectra the
    campaign quantified - including the ones QC rejected, which is the whole
    reason the log records every attempt rather than every assimilation.

    `max_per_campaign` caps the export by spreading the selection evenly
    over the acquisition sequence, and always keeps every QC failure: a
    representative set plus every exception is what a reader needs, and
    writing thousands of 2048-point CSVs is not."""
    log = list(getattr(rec_c.lab, "spectrum_log", ()) or ())
    if not log:
        return []
    failed = [i for i, e in enumerate(log)
              if any(str(f).startswith("FAIL")
                     for f in (e.get("qc", {}).get("qc_flags", []) or []))]
    n_even = max(max_per_campaign - len(failed), 1)
    even = (np.unique(np.linspace(0, len(log) - 1, min(n_even, len(log)))
                      .round().astype(int)).tolist())
    keep = sorted(set(even) | set(failed))[:max(max_per_campaign,
                                                len(failed))]
    index: List[Dict] = []
    for i in keep:
        e = log[i]
        qc = e.get("qc", {}) or {}
        name = (f"spectrum_{rec_c.strategy}_acq{int(e['acquisition_index']):04d}"
                f"_z{e['z_m']:.4f}m")
        path = os.path.join(outdir, f"{name}.csv")
        comps = e.get("components", {}) or {}
        header = (["ppm", "observed", "fitted", "residual"]
                  + [f"component_{k}" for k in comps])
        ppm = np.asarray(e["ppm"], dtype=float)
        cols = [ppm, np.asarray(e["observed"], float),
                np.asarray(e["fitted"], float),
                np.asarray(e["residual"], float)] + \
               [np.asarray(comps[k], float) for k in comps]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            fh.write(",".join(header) + "\n")
            for r in range(len(ppm)):
                fh.write(",".join(f"{c[r]:.6g}" for c in cols) + "\n")
        flags = list(qc.get("qc_flags", []) or [])
        row = {**rec_c.tag(),
               "acquisition_index": int(e["acquisition_index"]),
               "z_m": _f(e["z_m"]),
               "z_over_L": (_f(e["z_m"]) / rec_c.length_m
                            if rec_c.length_m else float("nan")),
               "reacquisition": int(e.get("reacquisition", 0)),
               **_u_cols(_UStub(e)),
               "qc_state": ("FAIL" if any(str(f).startswith("FAIL")
                                          for f in flags)
                            else ("WARN" if flags else "PASS")),
               "qc_flags": ";".join(str(f) for f in flags),
               "residual_rms": _f(qc.get("residual_rms", np.nan)),
               "fit_condition_number": _f(qc.get("condition_number", np.nan)),
               "hardware_fault": int(qc.get("hardware_fault", 0) or 0),
               "spectrum_csv": os.path.basename(path)}
        for j, sp in enumerate(e.get("species", ())):
            row[f"c_{sp}_M"] = float(np.asarray(e["conc_M"])[j])
            row[f"sigma_{sp}_M"] = float(np.asarray(e["sigma_M"])[j])
        index.append(row)
    if verbose:
        print(f"saved: {len(index)} spectra in {outdir}")
    return index


class _UStub:
    """Adapter so a spectrum-log entry can go through `_u_cols`."""

    def __init__(self, e: Dict):
        self.T_C = e.get("T_C", float("nan"))
        q = e.get("Q_total_mL_min", float("nan"))
        self.Q1_mL_min = q / 2.0
        self.Q2_mL_min = q / 2.0
        self.C_EGDA_M = e.get("C_EGDA_M", float("nan"))
        self.C_cat_M = e.get("C_cat_M", float("nan"))
