"""
Benchmark aggregation: the publication-grade SUMMARY of a whole run.

WHERE THIS SITS.  `audit_export.py` produces the long-form record of every
campaign; `benchmark.py` produces the per-round metric rows and the
distributional strategy table; `efficiency.py` answers the
budget-to-target and matched-resource questions; `audit_summary.py` answers
"did the run produce what was asked for".  This module answers the question
none of them answers on its own:

    across many stochastic realizations, does the framework work reliably,
    where does it work, when does it fail, and what does each added
    capability buy?

It therefore AGGREGATES the tables those modules already wrote and adds
nothing to the science.  Every function here is a pure function of saved
rows: it runs after the compute phase, draws no random number except the
fixed-seed bootstrap the benchmark already uses for its own confidence
intervals (`efficiency._agg`, seeded per key so it is reproducible), and
never touches a laboratory, a posterior or an RNG a campaign consumed.

TWO RULES THAT SHAPE EVERY TABLE HERE.

  * NO SURVIVORSHIP.  Accuracy is never reported without the completion and
    fault rate beside it, and every "final" statistic uses each seed's LAST
    VALID round (`benchmark.last_valid_rows`), so a campaign that paused on
    a measurement fault stays in the statistics with the posterior it
    actually had instead of vanishing.

  * NO CLAIM FROM AN UNRELIABLE NUMBER.  A model probability derived from a
    Laplace evidence computed at a box bound is not a probability; the
    columns that would let someone quote one carry the reliability flag
    next to them, and the discrimination summary counts unreliable
    campaigns separately rather than averaging them in.

Table inventory (file name -> builder):

    benchmark_master_summary.csv      master_summary_rows
    parameter_performance_summary.csv parameter_performance_rows
    design_selection_distribution.csv design_selection_rows
    design_selection_by_round.csv     design_by_round_rows
    paired_seed_differences.csv       paired_seed_rows
    robustness_summary.csv            robustness_rows
    model_discrimination_summary.csv  model_discrimination_rows
    nmr_performance_summary.csv       nmr_performance_rows
    transfer_effect_summary.csv       transfer_effect_rows
    transfer_decomposition_summary.csv transfer_decomposition_summary_rows
    resource_summary.csv              resource_summary_rows
    scenario_strategy_matrix.csv      matrix_rows
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from . import benchmark as bm
from .efficiency import _agg, stable_seed

#: metered totals carried on every per-round row, with their units
RESOURCE_UNITS = {
    "time_s": "s", "egda_mol": "mol", "acid_mol": "mol", "liquid_mL": "mL",
    "waste_mL": "mL", "sample_mL": "mL", "nmr_acquisitions": "count",
    "nmr_reacquisitions": "count", "qc_rejected": "count",
    "capillary_travel_m": "m", "condition_changes": "count",
    "temperature_changes": "count", "energy_kJ": "kJ",
    "reactor_conditions": "count", "spatial_samples": "count",
}

#: the design variables whose SELECTED values this module characterizes
DESIGN_VARS = (("T_C", "degC"), ("Q_total_mL_min", "mL_min"),
               ("C_cat_M", "M"), ("C_EGDA_M", "M"))

#: a model is "decided" once its probability passes this
DECIDED_P = 0.90

#: a relative 95 % interval wider than this says the parameter was not
#: determined at all; any coverage it produces is vacuous
VACUOUS_CI_PCT = 1.0e3


def _f(x, default=np.nan) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def _finite(values: Iterable) -> np.ndarray:
    v = np.array([_f(x) for x in values], dtype=float)
    return v[np.isfinite(v)]


def _stat_block(values: Iterable, prefix: str, key: str) -> Dict:
    """median / IQR / bootstrap CI of the median, under one column prefix.

    The bootstrap seed is derived from the column identity, so the interval
    is reproducible for a fixed set of inputs - this is post-processing, and
    a confidence interval that moved between two reads of the same CSV would
    be worse than none."""
    a = _agg(_finite(values), seed=stable_seed((prefix, key)))
    return {f"{prefix}_median": a["median"], f"{prefix}_q25": a["q25"],
            f"{prefix}_q75": a["q75"], f"{prefix}_ci_lo": a["boot_lo"],
            f"{prefix}_ci_hi": a["boot_hi"], f"{prefix}_n": a["n"]}


def _scen_strats(rows: Sequence[Dict]) -> List[Tuple[str, str]]:
    return sorted({(str(r["scenario"]), str(r["strategy"])) for r in rows})


def _sel(rows: Sequence[Dict], scen: str, strat: str) -> List[Dict]:
    return [r for r in rows if r["scenario"] == scen
            and r["strategy"] == strat]


def _final_per_seed(rows: Sequence[Dict], keys=("scenario", "strategy",
                                                "seed")) -> List[Dict]:
    """The LAST round of each group - the same last-valid rule the benchmark
    uses, so a paused campaign contributes its last valid posterior."""
    best: Dict[Tuple, Dict] = {}
    for r in rows:
        k = tuple(str(r.get(x, "")) for x in keys)
        if k not in best or int(_f(r.get("round", 0))) > int(
                _f(best[k].get("round", 0))):
            best[k] = r
    return list(best.values())


# ------------------------------------------------------------------------- #
# 1. the master summary
# ------------------------------------------------------------------------- #
def master_summary_rows(rows: Sequence[Dict], status: Sequence[Dict],
                        prows: Sequence[Dict] = (),
                        model_prob_rows: Sequence[Dict] = (),
                        gov_rows: Sequence[Dict] = (),
                        specs: Optional[Dict] = None) -> List[Dict]:
    """ONE row per (scenario, strategy) - the table a reader starts from.

    Accuracy, uncertainty, cost, completion and failure all live on the same
    row deliberately.  A median parameter error quoted without the fraction
    of campaigns that reached the end is not a benchmark result, and putting
    the two in different files is how they get separated."""
    specs = specs or bm.SCENARIOS
    out: List[Dict] = []
    for scen, strat in _scen_strats(rows):
        spec = specs.get(scen)
        fin = bm.last_valid_rows(list(rows), scen, strat)
        st = _sel(status, scen, strat)
        n_camp = len(st) or len(fin)
        n_done = sum(int(_f(s.get("completed", 0))) for s in st)
        n_fault = sum(int(_f(s.get("faulted", 0))) for s in st)
        stops: Dict[str, int] = {}
        for s in st:
            key = str(s.get("stop_reason", "") or "budget exhausted")
            key = ("MEASUREMENT_FAULT" if key.startswith("MEASUREMENT_FAULT")
                   else key)
            stops[key] = stops.get(key, 0) + 1
        row = {
            "scenario": scen, "strategy": strat,
            "reference_strategy": (bm.reference_strategy(scen)
                                   if scen in specs else ""),
            "observation_mode": getattr(spec, "observation_mode", ""),
            "uses_transfer_line": int(bool(getattr(spec, "uses_transfer",
                                                   False))),
            "n_candidate_models": len(getattr(spec, "family", ()) or ()),
            "n_seeds": len({int(_f(r["seed"])) for r in fin}),
            "n_campaigns": n_camp,
            "n_completed": n_done,
            "n_faulted": n_fault,
            "completion_rate": (n_done / n_camp) if n_camp else float("nan"),
            "fault_rate": (n_fault / n_camp) if n_camp else float("nan"),
            "rounds_planned": max([int(_f(s.get("rounds_planned", 0)))
                                   for s in st] or [0]),
            "median_rounds_completed": float(np.median(
                [int(_f(s.get("rounds_completed", 0))) for s in st])
            ) if st else float("nan"),
        }
        # ---- accuracy and uncertainty at the last valid round ----------- #
        row.update(_stat_block([r.get("param_err_pct") for r in fin],
                               "param_err_pct", (scen, strat, "pe")))
        row.update(_stat_block([r.get("blind_rmse_M") for r in fin],
                               "blind_rmse_M", (scen, strat, "br")))
        row.update(_stat_block([r.get("max_rel_ci_pct") for r in fin],
                               "max_rel_ci_pct", (scen, strat, "ci")))
        # ---- what it cost --------------------------------------------- #
        for k, unit in RESOURCE_UNITS.items():
            v = _finite([r.get(k) for r in fin])
            row[f"median_{k}_{unit}"] = (float(np.median(v)) if v.size
                                         else float("nan"))
            row[f"total_{k}_{unit}"] = float(np.sum(v)) if v.size else 0.0
        acq = _f(row.get("total_nmr_acquisitions_count"), 0.0)
        row["qc_rejection_rate"] = (
            _f(row.get("total_qc_rejected_count"), 0.0) / acq
            if acq > 0 else float("nan"))
        row["reacquisition_rate"] = (
            _f(row.get("total_nmr_reacquisitions_count"), 0.0) / acq
            if acq > 0 else float("nan"))
        # ---- model selection, where the scenario has an ensemble -------- #
        tracked = getattr(spec, "track_correct_model", None) or ""
        row["tracked_correct_model"] = tracked
        row["truth_in_candidate_family"] = int(bool(
            getattr(spec, "well_specified", False)))
        mp = _sel(model_prob_rows, scen, strat)
        if mp:
            fin_mp = _final_per_seed(mp, ("scenario", "strategy", "seed"))
            sel_by_seed: Dict[int, Dict] = {}
            for r in mp:
                sd = int(_f(r["seed"]))
                rd = int(_f(r["round"]))
                cur = sel_by_seed.get(sd)
                if cur is None or rd > int(_f(cur["round"])):
                    sel_by_seed[sd] = r
                if rd == int(_f(sel_by_seed[sd]["round"])) \
                        and int(_f(r.get("is_selected_model", 0))):
                    sel_by_seed[sd] = r
            n_sel = len(sel_by_seed)
            row["n_seeds_with_model_ensemble"] = n_sel
            if tracked and n_sel:
                row["model_selection_success_rate"] = float(np.mean(
                    [str(r.get("selected_model", "")) == tracked
                     for r in sel_by_seed.values()]))
            else:
                row["model_selection_success_rate"] = float("nan")
            row["frac_seeds_evidence_reliable"] = float(np.mean(
                [int(_f(r.get("probs_reliable_all_models", 0)))
                 for r in sel_by_seed.values()])) if n_sel else float("nan")
            # "undecided" = no candidate reached the decision threshold
            top = []
            for sd in sel_by_seed:
                rr = [r for r in fin_mp if int(_f(r["seed"])) == sd]
                probs = _finite([r.get("probability") for r in mp
                                 if int(_f(r["seed"])) == sd
                                 and int(_f(r["round"]))
                                 == int(_f(sel_by_seed[sd]["round"]))])
                top.append(float(np.max(probs)) if probs.size else np.nan)
                del rr
            fin_top = _finite(top)
            row["median_top_model_probability"] = (
                float(np.median(fin_top)) if fin_top.size else float("nan"))
            row["undecided_rate"] = (
                float(np.mean(fin_top < DECIDED_P)) if fin_top.size
                else float("nan"))
        row.update(_stat_block([r.get("p_correct") for r in fin],
                               "p_correct_final", (scen, strat, "pc")))
        row.update(_stat_block([r.get("model_entropy") for r in fin],
                               "model_entropy_final", (scen, strat, "me")))
        # ---- governor --------------------------------------------------- #
        gr = _sel(gov_rows, scen, strat)
        if gr:
            by_seed: Dict[int, List[Dict]] = {}
            for r in gr:
                by_seed.setdefault(int(_f(r["seed"])), []).append(r)
            flagged = [any(str(x.get("state", "")) == "MODEL_INADEQUATE"
                           for x in v) for v in by_seed.values()]
            row["governor_inadequate_campaign_rate"] = (
                float(np.mean(flagged)) if flagged else float("nan"))
            row["median_chi2_over_dof_final"] = float(np.median(_finite(
                [max(v, key=lambda x: int(_f(x["round"])))["chi2_over_dof"]
                 for v in by_seed.values()]))) if by_seed else float("nan")
        else:
            inad = [r for r in _sel(rows, scen, strat)
                    if str(r.get("gov_state", "")) == "MODEL_INADEQUATE"]
            seeds_all = {int(_f(r["seed"])) for r in _sel(rows, scen, strat)}
            row["governor_inadequate_campaign_rate"] = (
                len({int(_f(r["seed"])) for r in inad}) / len(seeds_all)
                if seeds_all else float("nan"))
        # ---- parameters resting on a bound at the end -------------------- #
        pf = [r for r in _final_per_seed(_sel(prows, scen, strat),
                                         ("scenario", "strategy", "seed",
                                          "param"))]
        if pf:
            by_seed_bound: Dict[int, int] = {}
            for r in pf:
                sd = int(_f(r["seed"]))
                by_seed_bound[sd] = max(by_seed_bound.get(sd, 0),
                                        int(_f(r.get("bound_active", 0))))
            row["frac_campaigns_with_bound_active"] = float(
                np.mean(list(by_seed_bound.values())))
            cov = _finite([r.get("covered95") for r in pf])
            row["parameter_ci95_coverage"] = (float(np.mean(cov))
                                              if cov.size else float("nan"))
        # ---- how the campaigns ended ------------------------------------- #
        row["n_stopped_measurement_fault"] = stops.get("MEASUREMENT_FAULT", 0)
        row["n_stopped_budget_exhausted"] = stops.get("budget exhausted", 0)
        row["stop_reason_distribution"] = "; ".join(
            f"{k}={v}" for k, v in sorted(stops.items()))
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 2. parameter-by-parameter performance
# ------------------------------------------------------------------------- #
def parameter_performance_rows(prows: Sequence[Dict],
                               ident_rows: Sequence[Dict] = (),
                               cov_rows: Sequence[Dict] = ()) -> List[Dict]:
    """One row per (scenario, strategy, parameter), across seeds.

    WHY THIS EXISTS SEPARATELY FROM `param_err_pct`.  The aggregate error is
    a geometric mean over parameters, and a geometric mean hides exactly the
    failure mode that matters here: one parameter that the campaign never
    identified.  A method can carry a 10 % aggregate error while K2 is
    unconstrained across every seed, and only a per-parameter table shows
    that.

    Accuracy and precision are reported side by side for the same reason -
    a small interval around a wrong value ("precise but wrong") and a
    correct value with a huge interval are different failures, and the
    empirical 95 % coverage is what separates them."""
    out: List[Dict] = []
    finals = _final_per_seed(prows, ("scenario", "strategy", "seed", "param"))
    ident_final = _final_per_seed(
        [r for r in ident_rows], ("scenario", "strategy", "seed", "param")) \
        if ident_rows else []
    keys = sorted({(str(r["scenario"]), str(r["strategy"]), str(r["param"]))
                   for r in finals})
    for scen, strat, param in keys:
        sel = [r for r in finals if r["scenario"] == scen
               and r["strategy"] == strat and r["param"] == param]
        est = _finite([r.get("estimate") for r in sel])
        tru = _finite([r.get("true_value") for r in sel])
        rel = _finite([r.get("rel_error_pct") for r in sel])
        row = {"scenario": scen, "strategy": strat, "param": param,
               "n_seeds": len(sel),
               "median_estimate_natural": (float(np.median(est))
                                           if est.size else float("nan")),
               "true_value_natural": (float(tru[0]) if tru.size
                                      else float("nan"))}
        if est.size and tru.size and est.size == tru.size:
            err = est - tru
            row["bias_natural"] = float(np.mean(err))
            row["rmse_natural"] = float(np.sqrt(np.mean(err ** 2)))
            with np.errstate(divide="ignore", invalid="ignore"):
                relb = np.where(tru != 0.0, (est / tru - 1.0) * 100.0, np.nan)
            relb = relb[np.isfinite(relb)]
            row["median_rel_bias_pct"] = (float(np.median(relb))
                                          if relb.size else float("nan"))
        else:
            row.update({"bias_natural": float("nan"),
                        "rmse_natural": float("nan"),
                        "median_rel_bias_pct": float("nan")})
        row.update(_stat_block(rel, "abs_rel_error_pct",
                               (scen, strat, param, "e")))
        row.update(_stat_block([r.get("sigma_scaled") for r in sel],
                               "sigma_scaled", (scen, strat, param, "s")))
        row.update(_stat_block([r.get("rel_width_pct") for r in sel],
                               "rel_ci95_width_pct",
                               (scen, strat, param, "w")))
        cov = _finite([r.get("covered95") for r in sel])
        row["ci95_coverage"] = float(np.mean(cov)) if cov.size else float("nan")
        row["n_coverage_evaluable"] = int(cov.size)
        # A 100 % coverage produced by an interval thousands of percent wide
        # is not a calibrated posterior, it is an unidentified parameter.
        # Coverage must never be read without this flag beside it.
        row["coverage_is_vacuous"] = int(
            np.isfinite(row["rel_ci95_width_pct_median"])
            and row["rel_ci95_width_pct_median"] > VACUOUS_CI_PCT)
        row["frac_bound_active"] = float(np.mean(
            [int(_f(r.get("bound_active", 0))) for r in sel])) if sel \
            else float("nan")
        # ---- identifiability diagnostics, where the audit trail has them - #
        idr = [r for r in ident_final if r["scenario"] == scen
               and r["strategy"] == strat and r["param"] == param]
        if idr:
            row["median_condition_number"] = float(np.median(_finite(
                [r.get("condition_number") for r in idr])) or np.nan) \
                if _finite([r.get("condition_number")
                            for r in idr]).size else float("nan")
            eff = _finite([r.get("effective_rank") for r in idr])
            row["median_effective_rank"] = (float(np.median(eff))
                                            if eff.size else float("nan"))
            row["matrix_kind"] = str(idr[0].get("matrix_kind", ""))
        # ---- worst partner correlation at the final round ---------------- #
        cr = [r for r in cov_rows if r["scenario"] == scen
              and r["strategy"] == strat
              and (r["param_i"] == param or r["param_j"] == param)
              and not int(_f(r.get("is_diagonal", 0)))]
        if cr:
            fin_cr = _final_per_seed(cr, ("scenario", "strategy", "seed",
                                          "param_i", "param_j"))
            worst: Dict[int, Tuple[float, str]] = {}
            for r in fin_cr:
                sd = int(_f(r["seed"]))
                c = abs(_f(r.get("corr")))
                other = (r["param_j"] if r["param_i"] == param
                         else r["param_i"])
                if np.isfinite(c) and (sd not in worst or c > worst[sd][0]):
                    worst[sd] = (c, str(other))
            vals = _finite([v[0] for v in worst.values()])
            row["median_max_abs_correlation"] = (float(np.median(vals))
                                                 if vals.size
                                                 else float("nan"))
            partners: Dict[str, int] = {}
            for _c, o in worst.values():
                partners[o] = partners.get(o, 0) + 1
            row["most_correlated_with"] = (max(partners, key=partners.get)
                                           if partners else "")
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 3. where the algorithms choose to experiment
# ------------------------------------------------------------------------- #
def _condition_rows(design_rows: Sequence[Dict]) -> List[Dict]:
    """One row per (scenario, strategy, seed, round) - the CONDITION, not the
    acquisition.

    `design_history` carries one row per assimilated acquisition, so a
    ten-position profile would weight its operating condition ten times and
    a one-position adaptive round once.  For "which conditions does this
    method choose" that weighting is simply wrong, so the conditions are
    de-duplicated first; the positions keep the acquisition-level rows,
    where per-acquisition weighting is exactly right."""
    seen: Dict[Tuple, Dict] = {}
    for r in design_rows:
        k = (str(r["scenario"]), str(r["strategy"]), int(_f(r["seed"])),
             int(_f(r["round"])))
        seen.setdefault(k, r)
    return list(seen.values())


def design_selection_rows(design_rows: Sequence[Dict],
                          n_bins: int = 12) -> List[Dict]:
    """Binned distribution of every selected design variable, per
    (scenario, strategy).

    Answers the question a benchmark of an experimental designer has to
    answer: WHERE does the method repeatedly go for information?  Bins are
    shared across the strategies of a scenario (they are computed over the
    pooled values), because histograms on different supports cannot be
    compared, which is the whole point of the table."""
    out: List[Dict] = []
    if not design_rows:
        return out
    conds = _condition_rows(design_rows)
    scenarios = sorted({str(r["scenario"]) for r in design_rows})
    for scen in scenarios:
        pool_c = [r for r in conds if r["scenario"] == scen]
        pool_a = [r for r in design_rows if r["scenario"] == scen]
        strategies = sorted({str(r["strategy"]) for r in pool_c})
        variables = [(k, u, pool_c, False) for k, u in DESIGN_VARS]
        variables.append(("z_over_L", "dimensionless", pool_a, True))
        for var, unit, pool, per_acq in variables:
            vals = _finite([r.get(var) for r in pool])
            if not vals.size:
                continue
            lo, hi = float(np.min(vals)), float(np.max(vals))
            if hi <= lo:
                hi = lo + max(abs(lo) * 1e-6, 1e-9)
            edges = np.linspace(lo, hi, n_bins + 1)
            for strat in strategies:
                sv = _finite([r.get(var) for r in pool
                              if r["strategy"] == strat])
                if not sv.size:
                    continue
                counts, _ = np.histogram(sv, bins=edges)
                total = int(counts.sum())
                for b in range(n_bins):
                    out.append({
                        "scenario": scen, "strategy": strat,
                        "variable": var, "unit": unit,
                        "weighting": ("per_acquisition" if per_acq
                                      else "per_reactor_condition"),
                        "bin_index": b + 1,
                        "bin_lo": float(edges[b]),
                        "bin_hi": float(edges[b + 1]),
                        "bin_center": float(0.5 * (edges[b] + edges[b + 1])),
                        "count": int(counts[b]),
                        "fraction": (float(counts[b]) / total if total
                                     else float("nan")),
                        "n_total": total,
                        "median_selected": float(np.median(sv)),
                        "q25_selected": float(np.quantile(sv, 0.25)),
                        "q75_selected": float(np.quantile(sv, 0.75)),
                        "min_selected": float(np.min(sv)),
                        "max_selected": float(np.max(sv)),
                    })
    return out


def design_by_round_rows(design_rows: Sequence[Dict]) -> List[Dict]:
    """Selected design variables against ROUND, across seeds.

    A distribution pooled over the whole campaign cannot show a policy that
    starts cold and moves hot, which is exactly the behaviour an adaptive
    designer is supposed to have."""
    out: List[Dict] = []
    conds = _condition_rows(design_rows)
    keys = sorted({(str(r["scenario"]), str(r["strategy"]),
                    int(_f(r["round"]))) for r in conds})
    for scen, strat, rnd in keys:
        sel = [r for r in conds if r["scenario"] == scen
               and r["strategy"] == strat and int(_f(r["round"])) == rnd]
        acq = [r for r in design_rows if r["scenario"] == scen
               and r["strategy"] == strat and int(_f(r["round"])) == rnd]
        row = {"scenario": scen, "strategy": strat, "round": rnd,
               "n_seeds": len(sel),
               "n_acquisitions": len(acq)}
        for var, unit in DESIGN_VARS:
            v = _finite([r.get(var) for r in sel])
            row[f"{var}_median"] = float(np.median(v)) if v.size else np.nan
            row[f"{var}_q25"] = (float(np.quantile(v, 0.25)) if v.size
                                 else np.nan)
            row[f"{var}_q75"] = (float(np.quantile(v, 0.75)) if v.size
                                 else np.nan)
        z = _finite([r.get("z_over_L") for r in acq])
        row["z_over_L_median"] = float(np.median(z)) if z.size else np.nan
        row["z_over_L_q25"] = (float(np.quantile(z, 0.25)) if z.size
                               else np.nan)
        row["z_over_L_q75"] = (float(np.quantile(z, 0.75)) if z.size
                               else np.nan)
        row["n_positions_per_round_median"] = (
            float(len(acq)) / max(len(sel), 1))
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 4. paired-seed differences (common random numbers)
# ------------------------------------------------------------------------- #
#: metrics compared seed-by-seed; True = lower is better
PAIRED_METRICS = {"param_err_pct": True, "blind_rmse_M": True,
                  "max_rel_ci_pct": True, "time_s": True, "egda_mol": True,
                  "waste_mL": True, "energy_kJ": True,
                  "nmr_acquisitions": True}


def paired_seed_rows(rows: Sequence[Dict], specs: Optional[Dict] = None,
                     metrics: Optional[Dict[str, bool]] = None
                     ) -> List[Dict]:
    """EVERY seed's paired difference against its scenario's reference
    strategy, not just the aggregate.

    The benchmark runs common random numbers, so the same seed means the
    same measurement noise, the same fault draws and the same EIG stream for
    both strategies.  That makes the per-seed difference a genuine paired
    observation, and it is the only way to tell "wins on most seeds" from
    "loses on most seeds but is rescued by two spectacular runs" - two
    results with the same median and completely different standing."""
    specs = specs or bm.SCENARIOS
    metrics = metrics or PAIRED_METRICS
    out: List[Dict] = []
    for scen in sorted({str(r["scenario"]) for r in rows}):
        ref = bm.reference_strategy(scen) if scen in specs else None
        if ref is None:
            continue
        ref_fin = {int(_f(r["seed"])): r
                   for r in bm.last_valid_rows(list(rows), scen, ref)}
        if not ref_fin:
            continue
        for strat in sorted({str(r["strategy"]) for r in rows
                             if r["scenario"] == scen}):
            if strat == ref:
                continue
            fin = {int(_f(r["seed"])): r
                   for r in bm.last_valid_rows(list(rows), scen, strat)}
            for seed in sorted(set(fin) & set(ref_fin)):
                a, b = fin[seed], ref_fin[seed]
                for metric, lower_better in metrics.items():
                    va, vb = _f(a.get(metric)), _f(b.get(metric))
                    if not (np.isfinite(va) and np.isfinite(vb)):
                        continue
                    diff = va - vb
                    better = ((diff < 0.0) if lower_better else (diff > 0.0))
                    out.append({
                        "scenario": scen, "strategy": strat,
                        "reference_strategy": ref, "seed": seed,
                        "metric": metric,
                        "lower_is_better": int(lower_better),
                        "value_strategy": va, "value_reference": vb,
                        "difference": diff,
                        "ratio": (va / vb if vb not in (0.0,)
                                  and np.isfinite(vb) else float("nan")),
                        "strategy_better": int(better),
                        "round_strategy": int(_f(a.get("round", 0))),
                        "round_reference": int(_f(b.get("round", 0))),
                    })
    return out


def paired_summary_rows(paired: Sequence[Dict]) -> List[Dict]:
    """Median paired difference, its bootstrap CI, and the WIN FRACTION.

    The win fraction is reported next to the median because they answer
    different questions and can disagree: a method can have a favourable
    median difference while losing on most seeds."""
    out: List[Dict] = []
    keys = sorted({(str(r["scenario"]), str(r["strategy"]),
                    str(r["reference_strategy"]), str(r["metric"]))
                   for r in paired})
    for scen, strat, ref, metric in keys:
        sel = [r for r in paired if r["scenario"] == scen
               and r["strategy"] == strat and r["metric"] == metric]
        d = _finite([r["difference"] for r in sel])
        row = {"scenario": scen, "strategy": strat,
               "reference_strategy": ref, "metric": metric,
               "n_pairs": int(d.size),
               "lower_is_better": int(_f(sel[0]["lower_is_better"], 1)),
               "win_fraction": float(np.mean(
                   [int(r["strategy_better"]) for r in sel])) if sel
               else float("nan")}
        row.update(_stat_block(d, "difference", (scen, strat, metric, "d")))
        row.update(_stat_block([r["ratio"] for r in sel], "ratio",
                               (scen, strat, metric, "r")))
        # A bootstrap over ONE observation returns that observation, so it
        # would report an interval of zero width that "excludes zero" for
        # every single-seed run.  That is not a confidence interval, and
        # emitting one invites exactly the claim this table exists to
        # discipline - so a single pair reports no interval at all.
        if int(d.size) < 2:
            for k in ("difference_ci_lo", "difference_ci_hi",
                      "ratio_ci_lo", "ratio_ci_hi"):
                row[k] = float("nan")
            row["ci_excludes_zero"] = 0
        else:
            lo, hi = row["difference_ci_lo"], row["difference_ci_hi"]
            row["ci_excludes_zero"] = int(np.isfinite(lo) and np.isfinite(hi)
                                          and (lo > 0.0 or hi < 0.0))
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 5. robustness and failure
# ------------------------------------------------------------------------- #
def robustness_rows(rows: Sequence[Dict], status: Sequence[Dict],
                    prows: Sequence[Dict] = (),
                    gov_rows: Sequence[Dict] = (),
                    nmr_rows: Sequence[Dict] = (),
                    model_prob_rows: Sequence[Dict] = (),
                    specs: Optional[Dict] = None) -> List[Dict]:
    """Everything that went WRONG, per (scenario, strategy).

    Published next to the accuracy table and never instead of it.  An
    estimate produced by the 60 % of campaigns that survived is not the same
    result as one produced by all of them, and this is the table that says
    which of the two a reader is looking at."""
    specs = specs or bm.SCENARIOS
    out: List[Dict] = []
    for scen, strat in _scen_strats(rows):
        spec = specs.get(scen)
        st = _sel(status, scen, strat)
        sel = _sel(rows, scen, strat)
        seeds = sorted({int(_f(r["seed"])) for r in sel})
        n = len(st) or len(seeds)
        acq = sum(_f(s.get("nmr_acquisitions"), 0.0) for s in st)
        rej = sum(_f(s.get("qc_rejected"), 0.0) for s in st)
        reacq = sum(_f(s.get("nmr_reacquisitions"), 0.0) for s in st)
        row = {
            "scenario": scen, "strategy": strat,
            "observation_mode": getattr(spec, "observation_mode", ""),
            "n_campaigns": n,
            "completion_rate": (sum(int(_f(s.get("completed", 0)))
                                    for s in st) / n) if n else float("nan"),
            "n_measurement_fault_stops": sum(int(_f(s.get("faulted", 0)))
                                             for s in st),
            "measurement_fault_rate": (sum(int(_f(s.get("faulted", 0)))
                                           for s in st) / n) if n
            else float("nan"),
            "n_nmr_acquisitions": acq,
            "n_qc_rejected": rej,
            "qc_rejection_rate": (rej / acq) if acq > 0 else float("nan"),
            "n_reacquisitions": reacq,
            "reacquisition_rate": (reacq / acq) if acq > 0 else float("nan"),
        }
        # ---- QC failure reasons, where the audit trail has them --------- #
        nr = _sel(nmr_rows, scen, strat)
        if nr:
            fails: Dict[str, int] = {}
            for r in nr:
                if not int(_f(r.get("qc_fail", 0))):
                    continue
                for flag in str(r.get("qc_flags", "") or "").split(";"):
                    if flag.startswith("FAIL"):
                        fails[flag] = fails.get(flag, 0) + 1
            row["n_censored_species_rows"] = sum(
                int(_f(r.get("censored", 0))) for r in nr)
            row["top_qc_failure_reason"] = (max(fails, key=fails.get)[:160]
                                            if fails else "")
            row["n_qc_failure_flag_rows"] = sum(fails.values())
        # ---- governor ---------------------------------------------------- #
        gr = _sel(gov_rows, scen, strat)
        if gr:
            by_seed: Dict[int, List[Dict]] = {}
            for r in gr:
                by_seed.setdefault(int(_f(r["seed"])), []).append(r)
            flagged = [any(str(x.get("state")) == "MODEL_INADEQUATE"
                           for x in v) for v in by_seed.values()]
            row["governor_inadequate_rate"] = (float(np.mean(flagged))
                                               if flagged else float("nan"))
            # on a WELL-SPECIFIED scenario that rate IS the false-alarm rate
            row["governor_rate_is_false_alarm"] = int(bool(
                getattr(spec, "well_specified", False)))
        # ---- boundary and evidence pathologies --------------------------- #
        pf = _final_per_seed(_sel(prows, scen, strat),
                             ("scenario", "strategy", "seed", "param"))
        if pf:
            by_seed_b: Dict[int, int] = {}
            for r in pf:
                sd = int(_f(r["seed"]))
                by_seed_b[sd] = max(by_seed_b.get(sd, 0),
                                    int(_f(r.get("bound_active", 0))))
            row["bound_hit_rate"] = float(np.mean(list(by_seed_b.values())))
            row["n_param_rows_on_bound"] = sum(
                int(_f(r.get("bound_active", 0))) for r in pf)
        rel = [int(_f(r.get("probs_reliable", -1))) for r in sel]
        rel = [x for x in rel if x >= 0]
        row["unreliable_evidence_round_rate"] = (
            float(np.mean([x == 0 for x in rel])) if rel else float("nan"))
        mp = _sel(model_prob_rows, scen, strat)
        if mp:
            fin_mp = _final_per_seed(mp, ("scenario", "strategy", "seed"))
            rounds = {int(_f(r["seed"])): int(_f(r["round"]))
                      for r in fin_mp}
            tops = []
            for sd, rnd in rounds.items():
                p = _finite([r.get("probability") for r in mp
                             if int(_f(r["seed"])) == sd
                             and int(_f(r["round"])) == rnd])
                tops.append(float(np.max(p)) if p.size else np.nan)
            t = _finite(tops)
            row["undecided_rate"] = (float(np.mean(t < DECIDED_P))
                                     if t.size else float("nan"))
        # ---- non-finite results are a failure mode of their own ---------- #
        row["nonfinite_param_err_round_rate"] = (
            float(np.mean([not np.isfinite(_f(r.get("param_err_pct")))
                           for r in sel])) if sel else float("nan"))
        stops: Dict[str, int] = {}
        for s in st:
            key = str(s.get("stop_reason", "") or "budget exhausted")
            key = ("MEASUREMENT_FAULT" if key.startswith("MEASUREMENT_FAULT")
                   else key)
            stops[key] = stops.get(key, 0) + 1
        row["stop_reason_distribution"] = "; ".join(
            f"{k}={v}" for k, v in sorted(stops.items()))
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 6. model discrimination
# ------------------------------------------------------------------------- #
def model_discrimination_rows(model_prob_rows: Sequence[Dict],
                              rows: Sequence[Dict] = (),
                              specs: Optional[Dict] = None,
                              decided_p: float = DECIDED_P) -> List[Dict]:
    """One row per (scenario, strategy) that carries a model ensemble.

    THREE OUTCOMES ARE KEPT APART, because collapsing them is the mistake
    this table exists to prevent:

      * DISCRIMINATED - a candidate passed the decision threshold and its
        evidence was reliable;
      * AMBIGUOUS     - no candidate passed it, which for a genuinely
        ambiguous scenario is the CORRECT answer, not a failure;
      * UNRELIABLE    - a candidate passed it on an evidence computed at a
        box bound, which is apparent certainty and must never be quoted.
    """
    specs = specs or bm.SCENARIOS
    out: List[Dict] = []
    for scen, strat in _scen_strats(model_prob_rows):
        spec = specs.get(scen)
        sel = _sel(model_prob_rows, scen, strat)
        models = sorted({str(r["model"]) for r in sel})
        if len(models) < 2:
            continue                     # nothing to discriminate
        tracked = getattr(spec, "track_correct_model", None) or ""
        seeds = sorted({int(_f(r["seed"])) for r in sel})
        per_seed_final: Dict[int, List[Dict]] = {}
        for sd in seeds:
            ss = [r for r in sel if int(_f(r["seed"])) == sd]
            last = max(int(_f(r["round"])) for r in ss)
            per_seed_final[sd] = [r for r in ss
                                  if int(_f(r["round"])) == last]
        top_p, sel_model, reliable, first_decided = [], [], [], []
        for sd, rr in per_seed_final.items():
            p = _finite([r.get("probability") for r in rr])
            top_p.append(float(np.max(p)) if p.size else np.nan)
            chosen = [r for r in rr if int(_f(r.get("is_selected_model", 0)))]
            sel_model.append(str(chosen[0]["selected_model"]) if chosen
                             else "")
            reliable.append(int(_f(rr[0].get("probs_reliable_all_models", 0))))
            # first round at which ANY candidate passed the threshold
            hit = None
            ss = [r for r in sel if int(_f(r["seed"])) == sd]
            for rnd in sorted({int(_f(r["round"])) for r in ss}):
                p_r = _finite([r.get("probability") for r in ss
                               if int(_f(r["round"])) == rnd])
                if p_r.size and float(np.max(p_r)) >= decided_p:
                    hit = rnd
                    break
            first_decided.append(hit if hit is not None else np.nan)
        t = _finite(top_p)
        decided = t >= decided_p if t.size else np.array([], dtype=bool)
        rel_arr = np.array(reliable, dtype=float)
        row = {
            "scenario": scen, "strategy": strat,
            "n_seeds": len(seeds),
            "n_candidate_models": len(models),
            "candidate_models": ";".join(models),
            "tracked_correct_model": tracked,
            "truth_in_candidate_family": int(bool(
                getattr(spec, "well_specified", False))),
            "decision_threshold": float(decided_p),
            "median_top_model_probability": (float(np.median(t)) if t.size
                                             else float("nan")),
            "decided_rate": (float(np.mean(decided)) if decided.size
                             else float("nan")),
            "undecided_rate": (float(np.mean(~decided)) if decided.size
                               else float("nan")),
            "evidence_reliable_rate": (float(np.mean(rel_arr))
                                       if rel_arr.size else float("nan")),
            # decided AND reliable: the only combination a claim may rest on
            "decided_and_reliable_rate": (
                float(np.mean([bool(d) and bool(r) for d, r
                               in zip(decided, rel_arr)]))
                if decided.size else float("nan")),
            "apparent_certainty_unreliable_rate": (
                float(np.mean([bool(d) and not bool(r) for d, r
                               in zip(decided, rel_arr)]))
                if decided.size else float("nan")),
        }
        if tracked:
            row["selection_success_rate"] = float(np.mean(
                [m == tracked for m in sel_model])) if sel_model \
                else float("nan")
            pc = _finite([r.get("probability") for rr in
                          per_seed_final.values() for r in rr
                          if str(r["model"]) == tracked])
            row.update(_stat_block(pc, "p_tracked_model_final",
                                   (scen, strat, "pt")))
        fd = _finite(first_decided)
        row["frac_seeds_ever_decided"] = (
            float(np.mean(np.isfinite(np.array(first_decided, dtype=float))))
            if first_decided else float("nan"))
        row["median_round_first_decided"] = (float(np.median(fd)) if fd.size
                                             else float("nan"))
        ent = _finite([r.get("model_entropy") for r in
                       bm.last_valid_rows(list(rows), scen, strat)]) \
            if rows else np.array([])
        row["median_final_model_entropy_nats"] = (float(np.median(ent))
                                                  if ent.size
                                                  else float("nan"))
        row["max_possible_entropy_nats"] = float(np.log(len(models)))
        # frequency of each final selection, so a reader can see WHICH model
        freq: Dict[str, int] = {}
        for m in sel_model:
            freq[m or "(none)"] = freq.get(m or "(none)", 0) + 1
        row["final_selection_frequency"] = "; ".join(
            f"{k}={v}" for k, v in sorted(freq.items()))
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 7. NMR / measurement system
# ------------------------------------------------------------------------- #
#: concentration regimes the deconvolution behaves differently in
CONC_BINS = (0.0, 0.01, 0.05, 0.15, 0.4, 1.0, np.inf)


def _conc_bin_label(c: float) -> str:
    for i in range(len(CONC_BINS) - 1):
        if CONC_BINS[i] <= c < CONC_BINS[i + 1]:
            hi = CONC_BINS[i + 1]
            return (f"{CONC_BINS[i]:g}-{hi:g} M" if np.isfinite(hi)
                    else f">{CONC_BINS[i]:g} M")
    return "unclassified"


def nmr_performance_rows(nmr_rows: Sequence[Dict]) -> List[Dict]:
    """Deconvolution behaviour by species and concentration regime.

    NOTE ON WHAT IS AND IS NOT HERE.  `nmr_measurements_long` carries no
    truth - the fitter never sees one - so this table reports the
    UNCERTAINTY the pathway claimed and the QC behaviour it produced, per
    regime.  The BIAS and COVERAGE of the pathway against known
    compositions come from the dedicated quantification validation
    (`quantification_validation.csv`), which measures prepared standards
    outside any campaign; the two are complementary and are deliberately
    not merged, because one is measured against truth and the other is not.
    """
    out: List[Dict] = []
    # A direct-observation campaign records acquisitions too, but they never
    # went through a spectrometer and carry no fitted sigma - including them
    # would fill the table with empty rows under a heading that claims to
    # describe deconvolution performance.
    nmr_rows = [r for r in nmr_rows
                if str(r.get("observation_mode", "nmr")) == "nmr"]
    if not nmr_rows:
        return out
    keys = sorted({(str(r["scenario"]), str(r["strategy"]),
                    str(r["species"]),
                    _conc_bin_label(_f(r.get("conc_fitted_M"), 0.0)))
                   for r in nmr_rows})
    for scen, strat, sp, cbin in keys:
        sel = [r for r in nmr_rows if r["scenario"] == scen
               and r["strategy"] == strat and r["species"] == sp
               and _conc_bin_label(_f(r.get("conc_fitted_M"), 0.0)) == cbin]
        conc = _finite([r.get("conc_fitted_M") for r in sel])
        sig = _finite([r.get("sigma_M") for r in sel])
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = (sig / conc if sig.size == conc.size and conc.size
                   else np.array([]))
        rel = rel[np.isfinite(rel)] if rel.size else rel
        n = len(sel)
        row = {
            "scenario": scen, "strategy": strat, "species": sp,
            "concentration_bin": cbin,
            "n_species_rows": n,
            "n_assimilated": sum(int(_f(r.get("assimilated", 0)))
                                 for r in sel),
            "median_conc_fitted_M": (float(np.median(conc)) if conc.size
                                     else float("nan")),
            "median_sigma_M": (float(np.median(sig)) if sig.size
                               else float("nan")),
            "median_relative_sigma": (float(np.median(rel)) if rel.size
                                      else float("nan")),
            "qc_fail_rate": float(np.mean(
                [int(_f(r.get("qc_fail", 0))) for r in sel])) if n
            else float("nan"),
            "censored_rate": float(np.mean(
                [int(_f(r.get("censored", 0))) for r in sel])) if n
            else float("nan"),
            "rejected_rate": float(np.mean(
                [str(r.get("disposition", "")) == "rejected" for r in sel]))
            if n else float("nan"),
            "reacquired_rate": float(np.mean(
                [str(r.get("disposition", "")).startswith("failed_qc")
                 for r in sel])) if n else float("nan"),
        }
        row.update(_stat_block([r.get("residual_rms") for r in sel],
                               "residual_rms", (scen, strat, sp, cbin, "r")))
        row.update(_stat_block([r.get("fit_condition_number") for r in sel],
                               "fit_condition_number",
                               (scen, strat, sp, cbin, "c")))
        out.append(row)
    return out


def nmr_by_round_rows(nmr_rows: Sequence[Dict]) -> List[Dict]:
    """Per (scenario, strategy, round, species): does quantification degrade
    or improve as the campaign moves into harder chemistry?"""
    out: List[Dict] = []
    nmr_rows = [r for r in nmr_rows
                if str(r.get("observation_mode", "nmr")) == "nmr"]
    keys = sorted({(str(r["scenario"]), str(r["strategy"]),
                    int(_f(r["round"])), str(r["species"]))
                   for r in nmr_rows})
    for scen, strat, rnd, sp in keys:
        sel = [r for r in nmr_rows if r["scenario"] == scen
               and r["strategy"] == strat and int(_f(r["round"])) == rnd
               and r["species"] == sp]
        conc = _finite([r.get("conc_fitted_M") for r in sel])
        sig = _finite([r.get("sigma_M") for r in sel])
        out.append({
            "scenario": scen, "strategy": strat, "round": rnd,
            "species": sp, "n_species_rows": len(sel),
            "median_conc_fitted_M": (float(np.median(conc)) if conc.size
                                     else float("nan")),
            "median_sigma_M": (float(np.median(sig)) if sig.size
                               else float("nan")),
            "qc_fail_rate": float(np.mean(
                [int(_f(r.get("qc_fail", 0))) for r in sel])) if sel
            else float("nan"),
        })
    return out


# ------------------------------------------------------------------------- #
# 8. transfer line
# ------------------------------------------------------------------------- #
def transfer_effect_rows(rows: Sequence[Dict],
                         ladder: Sequence[str] = (),
                         specs: Optional[Dict] = None) -> List[Dict]:
    """The transport ABLATION ladder: what each transfer-line effect costs.

    Reads only the final accuracy of the scenarios that differ by one
    transport effect at a time, so the difference between two rows IS the
    effect of that ablation - no truth-side record is needed, which is why
    this table exists for every run while the decomposition below exists
    only where the laboratory kept a transfer log."""
    specs = specs or bm.SCENARIOS
    present = [s for s in (ladder or sorted({str(r["scenario"])
                                             for r in rows}))
               if s in {str(r["scenario"]) for r in rows}]
    out: List[Dict] = []
    base = None
    for scen in present:
        spec = specs.get(scen)
        tr = getattr(spec, "transfer", None)
        for strat in sorted({str(r["strategy"]) for r in rows
                             if r["scenario"] == scen}):
            fin = bm.last_valid_rows(list(rows), scen, strat)
            pe = _finite([r.get("param_err_pct") for r in fin])
            br = _finite([r.get("blind_rmse_M") for r in fin])
            row = {
                "scenario": scen, "strategy": strat,
                "n_seeds": len(fin),
                "transfer_enabled": int(bool(getattr(tr, "enabled", False))),
                "transfer_rtd": str(getattr(tr, "rtd", "")),
                "transfer_react_in_line": int(bool(
                    getattr(tr, "react_in_line", False))),
                "transfer_carryover": int(bool(
                    getattr(tr, "carryover", False))),
                "transfer_T_line_C": _f(getattr(tr, "T_line_C", np.nan)),
                "transfer_mean_delay_s": _f(
                    tr.mean_tau_s(0.0, 1.0) if tr is not None
                    and getattr(tr, "enabled", False) else np.nan),
                "median_param_err_pct": (float(np.median(pe)) if pe.size
                                         else float("nan")),
                "median_blind_rmse_M": (float(np.median(br)) if br.size
                                        else float("nan")),
            }
            if base is None:
                base = {}
            key = (strat,)
            if key not in base:
                base[key] = row["median_blind_rmse_M"]
            b = base[key]
            row["blind_rmse_ratio_vs_first_rung"] = (
                row["median_blind_rmse_M"] / b
                if np.isfinite(b) and b > 0 else float("nan"))
            row["first_rung_scenario"] = present[0] if present else ""
            out.append(row)
    return out


def transfer_decomposition_summary_rows(trans_rows: Sequence[Dict]
                                        ) -> List[Dict]:
    """Transport distortion vs quantification error, aggregated by species.

    SIMULATION VALIDATION ONLY.  Both intermediate states are truth-side and
    reach this table through `reveal_transfer_log()`, after the campaign has
    ended; no controller-side object ever sees either of them."""
    out: List[Dict] = []
    if not trans_rows:
        return out
    keys = sorted({(str(r["scenario"]), str(r["strategy"]),
                    str(r["species"])) for r in trans_rows})
    for scen, strat, sp in keys:
        sel = [r for r in trans_rows if r["scenario"] == scen
               and r["strategy"] == strat and r["species"] == sp]
        tr = _finite([r.get("transport_delta_M") for r in sel])
        qu = _finite([r.get("quantification_delta_M") for r in sel])
        tot = _finite([r.get("total_delta_M") for r in sel])
        c_r = _finite([r.get("c_reactor_true_M") for r in sel])
        row = {
            "scenario": scen, "strategy": strat, "species": sp,
            "n_acquisition_rows": len(sel),
            "median_c_reactor_true_M": (float(np.median(c_r)) if c_r.size
                                        else float("nan")),
            "mean_transport_delta_M": (float(np.mean(tr)) if tr.size
                                       else float("nan")),
            "rms_transport_delta_M": (float(np.sqrt(np.mean(tr ** 2)))
                                      if tr.size else float("nan")),
            "mean_quantification_delta_M": (float(np.mean(qu)) if qu.size
                                            else float("nan")),
            "rms_quantification_delta_M": (float(np.sqrt(np.mean(qu ** 2)))
                                           if qu.size else float("nan")),
            "rms_total_delta_M": (float(np.sqrt(np.mean(tot ** 2)))
                                  if tot.size else float("nan")),
        }
        a, b = row["rms_transport_delta_M"], row["rms_quantification_delta_M"]
        row["transport_share_of_total_error"] = (
            a ** 2 / (a ** 2 + b ** 2)
            if np.isfinite(a) and np.isfinite(b) and (a or b)
            else float("nan"))
        row["dominant_error_stage"] = (
            "" if not np.isfinite(a) or not np.isfinite(b)
            else ("transport" if a > b else "quantification"))
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 9. resources
# ------------------------------------------------------------------------- #
def resource_summary_rows(rows: Sequence[Dict],
                          event_rows: Sequence[Dict] = ()) -> List[Dict]:
    """What each strategy actually SPENT, and on what.

    The per-round totals give the budget; the event log gives the
    breakdown, which is the part an aggregate cost hides - two strategies
    can spend the same total time with one of them dominated by reactor
    stabilization and the other by spectrometer time, and only the second
    is improved by a faster NMR."""
    out: List[Dict] = []
    ev_by: Dict[Tuple[str, str], List[Dict]] = {}
    for r in event_rows:
        ev_by.setdefault((str(r["scenario"]), str(r["strategy"])),
                         []).append(r)
    for scen, strat in _scen_strats(rows):
        fin = bm.last_valid_rows(list(rows), scen, strat)
        row = {"scenario": scen, "strategy": strat, "n_seeds": len(fin)}
        for k, unit in RESOURCE_UNITS.items():
            row.update(_stat_block([r.get(k) for r in fin], f"{k}_{unit}",
                                   (scen, strat, k)))
        rounds = _finite([r.get("round") for r in fin])
        acq = _finite([r.get("nmr_acquisitions") for r in fin])
        t = _finite([r.get("time_s") for r in fin])
        row["median_time_per_round_s"] = (
            float(np.median(t / rounds)) if t.size and rounds.size
            and t.size == rounds.size and np.all(rounds > 0)
            else float("nan"))
        row["median_time_per_acquisition_s"] = (
            float(np.median(t[acq > 0] / acq[acq > 0]))
            if t.size == acq.size and np.any(acq > 0) else float("nan"))
        # ---- where the time went, from the metered event log ------------ #
        evs = ev_by.get((scen, strat), [])
        if evs:
            per_seed: Dict[int, Dict[str, float]] = {}
            for e in evs:
                sd = int(_f(e.get("seed", 0)))
                kind = str(e.get("event_kind", ""))
                per_seed.setdefault(sd, {})
                per_seed[sd][kind] = (per_seed[sd].get(kind, 0.0)
                                      + _f(e.get("d_time_s"), 0.0))
            kinds = sorted({k for v in per_seed.values() for k in v})
            for kind in kinds:
                v = _finite([d.get(kind, 0.0) for d in per_seed.values()])
                row[f"median_time_{kind}_s"] = (float(np.median(v))
                                                if v.size else float("nan"))
            tot = _finite([sum(d.values()) for d in per_seed.values()])
            for kind in kinds:
                v = _finite([d.get(kind, 0.0) for d in per_seed.values()])
                row[f"time_share_{kind}"] = (
                    float(np.median(v)) / float(np.median(tot))
                    if v.size and tot.size and float(np.median(tot)) > 0
                    else float("nan"))
            row["n_event_kinds"] = len(kinds)
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 10. the scenario x strategy matrix
# ------------------------------------------------------------------------- #
#: (column in the master summary, printable label, lower-is-better)
MATRIX_METRICS = (
    ("param_err_pct_median", "median parameter error / %", True),
    ("blind_rmse_M_median", "median blind RMSE / M", True),
    ("max_rel_ci_pct_median", "median worst 95% CI / %", True),
    ("completion_rate", "campaign completion rate", False),
    ("median_time_s_s", "median campaign time / s", True),
    ("median_egda_mol_mol", "median EGDA consumed / mol", True),
    ("median_waste_mL_mL", "median waste / mL", True),
    ("median_nmr_acquisitions_count", "median NMR acquisitions", True),
    ("qc_rejection_rate", "QC rejection rate", True),
    ("model_selection_success_rate", "model-selection success rate", False),
    ("governor_inadequate_campaign_rate",
     "campaigns declaring MODEL_INADEQUATE", False),
)


def matrix_rows(master: Sequence[Dict]) -> List[Dict]:
    """Long-form (metric, strategy, scenario, value) for the overview
    heatmaps, with only the combinations that actually ran."""
    out: List[Dict] = []
    for key, label, lower in MATRIX_METRICS:
        for r in master:
            v = _f(r.get(key))
            out.append({"metric": key, "metric_label": label,
                        "lower_is_better": int(lower),
                        "scenario": r["scenario"], "strategy": r["strategy"],
                        "value": v,
                        "n_campaigns": int(_f(r.get("n_campaigns"), 0)),
                        "defined": int(np.isfinite(v))})
    return out
