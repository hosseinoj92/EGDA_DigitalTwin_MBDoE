"""
Publication audit trail: derive the long-form tables from a FINISHED
campaign.

Everything here runs AFTER the campaign has returned, reading the retained
result, laboratory and recorder objects.  Nothing in this module runs inside
the closed loop, draws a random number, or re-evaluates an objective, so it
cannot influence any scientific result - the regression test in
tests/test_audit_regression.py asserts that.

Where the hidden truth is read (blind predictions, domain checks) it is the
same post-campaign scoring the benchmark already performs to compute
`param_err_pct` and `blind_rmse_M`; no controller-side code can reach it.

Table inventory (one dict of row-lists per campaign; the runner concatenates
across campaigns and writes one CSV each):

    design_history            one row per assimilated acquisition
    model_probabilities_long  one row per (round, candidate model)
    governor_diagnostics_long one row per round
    posterior_covariance_long one row per (round, parameter pair)
    identifiability_summary   one row per campaign (final round)
    blind_predictions_long    one row per (validation condition, z, species)
    resource_events_long      one row per metered resource event

plus the three tables the passive recorder collected during the run
(design_candidate_scores, controller_timing, nmr_measurements_long) and the
per-seed calibration record.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from sdl.campaign import StrategyResult

TABLES = ("design_history", "design_candidate_scores",
          "model_probabilities_long", "governor_diagnostics_long",
          "blind_predictions_long", "posterior_covariance_long",
          "identifiability_summary", "nmr_measurements_long",
          "nmr_calibration_by_seed", "resource_events_long",
          "controller_timing")


def _empty() -> Dict[str, List[Dict]]:
    return {t: [] for t in TABLES}


def _tag(spec, strategy: str, seed: int) -> Dict:
    return {"scenario": spec.name, "strategy": strategy, "seed": int(seed)}


def _u_cols(u) -> Dict:
    return {"T_C": float(u.T_C),
            "Q1_mL_min": float(u.Q1_mL_min),
            "Q2_mL_min": float(u.Q2_mL_min),
            "Q_total_mL_min": float(u.Q1_mL_min + u.Q2_mL_min),
            "C_EGDA_M": float(u.C_EGDA_M),
            "C_cat_M": float(u.C_cat_M)}


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


# ------------------------------------------------------------------------- #
# 1. design history: one row per assimilated acquisition
# ------------------------------------------------------------------------- #
def _measurement_walk(res) -> List:
    """Assimilated measurements in chronological order, whichever strategy
    produced them."""
    inf = getattr(res, "inference", None)
    if isinstance(res, StrategyResult):
        return list(inf.measurements) if inf is not None else []
    ens = getattr(res, "ensemble", None)
    if ens is not None:
        return list(ens.best.inference.measurements)
    return list(inf.measurements) if inf is not None else []


def _round_positions(res) -> List[Sequence[float]]:
    if isinstance(res, StrategyResult):
        return [None] * len(res.history)      # baselines: take the whole meas
    return [np.asarray(r.z_positions).ravel() for r in res.history]


def design_history_rows(spec, strategy: str, seed: int, res, lab,
                        length_m: float, spatial_mode: str) -> List[Dict]:
    """One row per acquisition that actually entered the posterior.

    Positions are matched to rounds by walking the measurements in the order
    they were assimilated and consuming each round's position count - the
    controller stores exactly the ASSIMILATED positions in
    `AdvRoundRecord.z_positions`, so the walk is exact for the fixed,
    optimized and adaptive spatial modes alike.  Rejected acquisitions are
    absent by construction; they are in nmr_measurements_long instead.
    """
    rows: List[Dict] = []
    meas = _measurement_walk(res)
    order = 0
    mi, inside = 0, 0            # measurement index, positions consumed in it
    for rec in res.history:
        rnd = int(rec.round)
        is_adv = not isinstance(res, StrategyResult)
        want = (len(np.asarray(rec.z_positions).ravel()) if is_adv
                else (meas[mi].n_z if mi < len(meas) else 0))
        taken = 0
        while taken < want and mi < len(meas):
            m = meas[mi]
            qc_all = (m.meta or {}).get("qc", [])
            while inside < m.n_z and taken < want:
                order += 1
                qc = qc_all[inside] if inside < len(qc_all) else {}
                z = float(m.z_m[inside])
                rows.append({
                    **_tag(spec, strategy, seed), "round": rnd,
                    "acquisition_order": order,
                    **_u_cols(m.u),
                    "z_m": z,
                    "z_over_L": z / length_m if length_m else float("nan"),
                    "spatial_mode": spatial_mode,
                    "design_mode": getattr(rec, "design_mode", "fixed"),
                    "eig_param": _f(getattr(rec, "eig_param", np.nan)),
                    "eig_model": _f(getattr(rec, "eig_model", np.nan)),
                    "qc_flags": ";".join(
                        str(x) for x in qc.get("qc_flags", [])),
                    "qc_pass": int(not any(str(x).startswith("FAIL")
                                           for x in qc.get("qc_flags", []))),
                    "censored_species": ";".join(qc.get("censored", [])),
                    "observation_mode": str(qc.get("mode", "")),
                    # per-ROUND totals (the gate is a round-level decision)
                    "round_n_rejected": int(getattr(rec, "n_rejected", 0)),
                    "round_n_reacquired": int(getattr(rec, "n_reacquired", 0)),
                    # CUMULATIVE resources after this round
                    **{f"cum_{k}": _f(v)
                       for k, v in (getattr(rec, "resources", {}) or {}).items()},
                })
                inside += 1
                taken += 1
            if inside >= m.n_z:
                mi += 1
                inside = 0
    return rows


# ------------------------------------------------------------------------- #
# 2. model probabilities (with the evidence-reliability caveat attached)
# ------------------------------------------------------------------------- #
def model_probability_rows(spec, strategy: str, seed: int, res) -> List[Dict]:
    """Every candidate's probability at every round.

    `evidence_reliable` and `probs_reliable` travel WITH the number, never
    in a separate file: a Laplace evidence computed at a parameter resting
    on a box bound is not valid evidence, and a probability derived from it
    must not be read as one.  Consumers are expected to filter on
    `probs_reliable` before making any model claim."""
    rows: List[Dict] = []
    if isinstance(res, StrategyResult):
        return rows                     # baselines carry no model ensemble
    for rec in res.history:
        rel_by = getattr(rec, "evidence_reliable_by_model", {}) or {}
        for name, p in sorted(rec.model_probs.items()):
            rows.append({
                **_tag(spec, strategy, seed), "round": int(rec.round),
                "model": name,
                "probability": _f(p),
                "is_selected_model": int(name == rec.best_model),
                "selected_model": rec.best_model,
                "evidence_reliable": int(bool(rel_by.get(name, True))),
                "probs_reliable_all_models": int(
                    bool(getattr(rec, "probs_reliable", False))),
                "n_bound_active": len(getattr(rec, "bound_active", ()) or ()),
                "bound_active_params": ";".join(
                    getattr(rec, "bound_active", ()) or ()),
                "evidence_warning": str(
                    getattr(rec, "evidence_warning", ""))[:300],
                "tracked_correct_model": spec.track_correct_model or "",
                "truth_in_candidate_family": int(bool(spec.well_specified)),
            })
    return rows


# ------------------------------------------------------------------------- #
# 3. governor diagnostics
# ------------------------------------------------------------------------- #
def governor_rows(spec, strategy: str, seed: int, res,
                  species: Sequence[str]) -> List[Dict]:
    rows: List[Dict] = []
    if isinstance(res, StrategyResult):
        return rows
    first_detect = None
    for rec in res.history:
        g = rec.governor
        if g is None:
            continue
        if first_detect is None and g.state == "MODEL_INADEQUATE":
            first_detect = int(rec.round)
        comps = dict(g.components or {})
        rows.append({
            **_tag(spec, strategy, seed), "round": int(rec.round),
            "state": g.state,
            "chi2_over_dof": _f(g.score),
            "p_combined_best_model": _f(g.p_value),
            "p_bootstrap": _f(g.p_boot) if g.p_boot is not None else float("nan"),
            "alpha_round_threshold": _f(g.alpha_round),
            "rejected_at_threshold": int(_f(g.p_value) < _f(g.alpha_round)),
            **{f"p_component_{k}": _f(v) for k, v in sorted(comps.items())},
            **{f"p_model_{k}": _f(v)
               for k, v in sorted((g.p_values_all or {}).items())},
            **{f"species_bias_z_{sp}": _f((g.species_bias or {}).get(sp, np.nan))
               for sp in species},
            "z_autocorr_r": _f(g.z_trend_r),
            "T_trend_r": _f(g.T_trend_r),
            "affected_species": ";".join(g.affected_species or []),
            "affected_region": g.affected_region or "",
            "trigger_reasons": " | ".join(g.reasons or [])[:500],
            "round_first_detected": (first_detect if first_detect is not None
                                     else -1),
        })
    return rows


# ------------------------------------------------------------------------- #
# 4/5. posterior covariance and identifiability
# ------------------------------------------------------------------------- #
def _space_of(res, rec):
    if isinstance(res, StrategyResult):
        return res.inference.space
    ens = getattr(res, "ensemble", None)
    if ens is not None and getattr(rec, "best_model", "") != "wls":
        names = [c.name for c in ens.models]
        if rec.best_model in names:
            return ens.models[names.index(rec.best_model)].space
    return res.inference.space if res.inference is not None else None


def posterior_covariance_rows(spec, strategy: str, seed: int,
                              res) -> List[Dict]:
    """Upper triangle (including the diagonal) of the SCALED-space posterior
    covariance and correlation, per round.  Both matrices are the ones the
    round already computed; nothing is refitted."""
    rows: List[Dict] = []
    for rec in res.history:
        cov = getattr(rec, "theta_cov", None)
        if isinstance(res, StrategyResult):
            cov = rec.report.cov
            corr = rec.report.corr
            sig = rec.report.sigma
            keys = tuple(res.inference.space.param_keys)
            bound = tuple(rec.report.active_bounds or ())
        else:
            corr = getattr(rec, "theta_corr", None)
            sig = rec.sigma_scaled
            keys = tuple(rec.param_keys)
            bound = tuple(rec.bound_active or ())
        if cov is None or sig is None or not keys:
            continue
        cov = np.asarray(cov, dtype=float)
        corr = (np.asarray(corr, dtype=float) if corr is not None
                else np.full_like(cov, np.nan))
        theta = rec.theta_nat
        for i, ki in enumerate(keys):
            for j in range(i, len(keys)):
                rows.append({
                    **_tag(spec, strategy, seed), "round": int(rec.round),
                    "param_i": ki, "param_j": keys[j],
                    "is_diagonal": int(i == j),
                    "cov_scaled": _f(cov[i, j]),
                    "corr": _f(corr[i, j]),
                    "estimate_i_natural": _f(theta.get(ki, np.nan)),
                    "sigma_i_scaled": _f(sig[i]),
                    "bound_active_i": int(ki in bound),
                })
    return rows


def identifiability_rows(spec, strategy: str, seed: int, res,
                         truth: Dict[str, float]) -> List[Dict]:
    """One row per parameter at the FINAL round of the campaign.

    `matrix_kind` states WHICH matrix the eigen-diagnostics come from, and
    it is not the same for every strategy - that is a fact about the
    estimators, not a defect:

      * baselines A-D and E are frequentist WLS/FIM, so `eigvals` are the
        genuine Fisher-information eigenvalues the round computed;
      * F is a Laplace posterior, whose curvature is H = F + prior
        precision.  Reporting H's eigenvalues as "FIM eigenvalues" would
        overstate what the data alone determined, so they are labelled
        `posterior_precision`.

    Recomputing a pure FIM for F would need a fresh finite-difference sweep
    over every assimilated measurement in every campaign; it is omitted
    rather than approximated silently."""
    rows: List[Dict] = []
    if not res.history:
        return rows
    rec = res.history[-1]
    space = _space_of(res, rec)
    if space is None:
        return rows
    keys = tuple(space.param_keys)
    if isinstance(res, StrategyResult):
        cov, sig = rec.report.cov, rec.report.sigma
        eig = np.asarray(rec.report.eigvals, dtype=float)
        kind = "fisher_information"
        bound = tuple(rec.report.active_bounds or ())
        rel_ci = rec.report.rel_ci_pct
    else:
        cov, sig = getattr(rec, "theta_cov", None), rec.sigma_scaled
        kind = ("fisher_information" if rec.best_model == "wls"
                else "posterior_precision")
        bound = tuple(rec.bound_active or ())
        rel_ci = None
        eig = np.array([])
        if cov is not None:
            try:
                eig = np.linalg.eigvalsh(np.linalg.inv(np.asarray(cov,
                                                                  float)))
            except np.linalg.LinAlgError:
                eig = np.array([])
    if sig is None:
        return rows
    if rel_ci is None:
        rel_ci = space.rel_ci_percent(space.to_vector(rec.theta_nat), sig)
    eig = np.sort(np.asarray(eig, dtype=float)) if eig.size else eig
    pos = eig[eig > 0] if eig.size else eig
    eig_max = float(np.max(eig)) if eig.size else float("nan")
    tol = eig_max * 1e-10 if np.isfinite(eig_max) else 0.0
    eff_rank = int(np.sum(eig > tol)) if eig.size else -1
    cond = (float(np.max(pos) / np.min(pos))
            if pos.size and np.min(pos) > 0 else float("inf"))
    for q, k in enumerate(keys):
        est = _f(rec.theta_nat.get(k, np.nan))
        tv = truth.get(k)
        rows.append({
            **_tag(spec, strategy, seed),
            "final_round": int(rec.round),
            "param": k,
            "estimate_natural": est,
            "true_value": _f(tv) if tv is not None else float("nan"),
            "rel_error_pct": (abs(est - tv) / abs(tv) * 100.0
                              if tv not in (None, 0) and np.isfinite(est)
                              else float("nan")),
            "sigma_scaled": _f(sig[q]) if q < len(sig) else float("nan"),
            "rel_ci_width_pct": (_f(rel_ci[q]) if rel_ci is not None
                                 and q < len(rel_ci) else float("nan")),
            "bound_active": int(k in bound),
            "matrix_kind": kind,
            "eigval_min": float(np.min(eig)) if eig.size else float("nan"),
            "eigval_max": eig_max,
            "effective_rank": eff_rank,
            "n_params": len(keys),
            "condition_number": cond,
            "eigenvalues_ascending": ";".join(f"{v:.6g}" for v in eig),
        })
    return rows


# ------------------------------------------------------------------------- #
# 6. blind predictions at the final round
# ------------------------------------------------------------------------- #
def blind_prediction_rows(spec, strategy: str, seed: int, res,
                          conds: Sequence, z_val: np.ndarray,
                          species: Sequence[str],
                          y_true: np.ndarray) -> List[Dict]:
    """Element-by-element blind validation at the final posterior.

    Uses the same predictor and the same pre-computed truth vector the
    benchmark already uses for `blind_rmse_M`, so this table decomposes an
    existing number rather than introducing a second one."""
    rows: List[Dict] = []
    if not res.history:
        return rows
    rec = res.history[-1]
    if isinstance(res, StrategyResult):
        space, bridge = res.inference.space, res.inference.bridge
    else:
        ens = getattr(res, "ensemble", None)
        if ens is not None and getattr(rec, "best_model", "wls") != "wls":
            cm = ens.models[[c.name for c in ens.models].index(rec.best_model)]
            space, bridge = cm.space, cm.bridge
        else:
            space, bridge = res.inference.space, res.inference.bridge
    theta = space.to_natural(space.to_vector(rec.theta_nat))
    n_z, n_s = len(z_val), len(species)
    for ci, u in enumerate(conds):
        pred = bridge.concentrations_at(theta, u, z_val, species)
        base = ci * n_s * n_z
        for i, sp in enumerate(species):
            for k in range(n_z):
                idx = i * n_z + k
                yt = float(y_true[base + idx])
                yp = float(pred[idx])
                rows.append({
                    **_tag(spec, strategy, seed),
                    "final_round": int(rec.round),
                    "validation_condition": ci + 1,
                    **_u_cols(u),
                    "z_m": float(z_val[k]),
                    "species": sp,
                    "c_true_M": yt,
                    "c_pred_M": yp,
                    "residual_M": yp - yt,
                    "squared_error_M2": (yp - yt) ** 2,
                    "best_model": getattr(rec, "best_model", "wls"),
                })
    return rows


# ------------------------------------------------------------------------- #
# 7. resource events
# ------------------------------------------------------------------------- #
def resource_event_rows(spec, strategy: str, seed: int, lab) -> List[Dict]:
    """The metered event log, with running cumulative totals.

    The totals recomputed here are the same ones ResourceMeter.totals()
    reports; the tests that re-derive campaign costs from raw events cover
    this identity."""
    rows: List[Dict] = []
    meter = getattr(lab, "meter", None)
    if meter is None:
        return rows
    keys = list(meter.TOTAL_KEYS)
    cum = {k: 0.0 for k in keys}
    for n, ev in enumerate(meter.events, start=1):
        q = ev.quantities or {}
        for k in keys:
            cum[k] += float(q.get(k, 0.0))
        rows.append({
            **_tag(spec, strategy, seed),
            "event_index": n, "event_kind": ev.kind,
            **{f"d_{k}": _f(q.get(k, 0.0)) for k in keys},
            **{f"cum_{k}": _f(cum[k]) for k in keys},
        })
    return rows


# ------------------------------------------------------------------------- #
# 8. the calibration actually used by this seed
# ------------------------------------------------------------------------- #
def calibration_rows(spec, strategy: str, seed: int, lab) -> List[Dict]:
    cal = getattr(lab, "calibration", None)
    if cal is None:
        return []
    rows = []
    n = len(cal.species)
    for i, sp in enumerate(cal.species):
        rows.append({
            **_tag(spec, strategy, seed),
            "species": sp,
            "response_factor": _f(cal.response_factors.get(sp, np.nan)),
            "bias_M": _f(cal.bias_M[i]),
            "var_const_M2": _f(cal.var_const_M2[i]),
            "rel_variance_term": _f(cal.rel[i]),
            "interval_scale": _f(cal.scale[i]),
            **{f"corr_with_{cal.species[j]}": _f(cal.corr[i, j])
               for j in range(n)},
            **{f"meta_{k}": v for k, v in sorted((cal.meta or {}).items())},
        })
    return rows


# ------------------------------------------------------------------------- #
# assembly
# ------------------------------------------------------------------------- #
def collect_campaign(spec, strategy: str, seed: int, res, lab, extra,
                     recorder, z_val: np.ndarray, y_true: np.ndarray,
                     conds: Sequence, species: Sequence[str],
                     spatial_mode: str) -> Dict[str, List[Dict]]:
    """Everything for ONE campaign, as plain dict rows ready to pickle."""
    out = _empty()
    if recorder is not None:
        for k, v in recorder.payload().items():
            out[k] = v
    length_m = float(getattr(lab, "length_m", 0.0) or 0.0)
    out["design_history"] = design_history_rows(spec, strategy, seed, res,
                                                lab, length_m, spatial_mode)
    out["model_probabilities_long"] = model_probability_rows(
        spec, strategy, seed, res)
    out["governor_diagnostics_long"] = governor_rows(spec, strategy, seed,
                                                     res, species)
    out["posterior_covariance_long"] = posterior_covariance_rows(
        spec, strategy, seed, res)
    out["identifiability_summary"] = identifiability_rows(
        spec, strategy, seed, res, spec.truth)
    out["blind_predictions_long"] = blind_prediction_rows(
        spec, strategy, seed, res, conds, z_val, species, y_true)
    out["resource_events_long"] = resource_event_rows(spec, strategy, seed,
                                                      lab)
    out["nmr_calibration_by_seed"] = calibration_rows(spec, strategy, seed,
                                                      lab)
    return out


def merge(into: Dict[str, List[Dict]],
          new: Optional[Dict[str, List[Dict]]]) -> Dict[str, List[Dict]]:
    if not new:
        return into
    for k, rows in new.items():
        into.setdefault(k, []).extend(rows)
    return into


def empty_bundle() -> Dict[str, List[Dict]]:
    return _empty()
