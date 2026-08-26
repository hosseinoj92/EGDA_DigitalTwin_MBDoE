"""
Conventional-vs-optimized comparison: how much does the methodology actually
buy, in units a reader understands at a glance?

THE PROBLEM WITH CONVERGENCE CURVES.  Two curves of error-vs-round look
persuasive and answer the wrong question.  A round is not a cost - one
"round" of the conventional ladder and one round of an adaptive campaign
consume different amounts of feedstock, time and instrument occupancy - so a
curve that wins per round may lose per gram.  And "our curve is lower" is
not a number anybody can put in an abstract.

WHAT THIS MODULE COMPUTES INSTEAD.  Two paired quantities, both standard in
the active-learning literature and both expressible as one sentence:

  1. BUDGET TO TARGET (sample efficiency).  Fix an accuracy target; ask what
     each method SPENT to first reach it - experiments, EGDA, campaign time,
     energy, NMR acquisitions.  Reported as a ratio against the conventional
     reference on the SAME SEED, so it is a paired comparison under common
     random numbers.
         "reached 20% parameter error with 0.34x the EGDA of the ladder"

  2. ACCURACY AT MATCHED RESOURCE.  Fix the resource the conventional method
     spent in total; ask how accurate each method was at that same spend.
         "at the ladder's full material budget, error was 3.1x lower"

They are duals and disagree in informative ways: a method can be
material-efficient but slow, and the pair shows it.

CENSORING IS REPORTED, NOT HIDDEN.  A campaign that never reaches a target
within its budget has no budget-to-target - it is right-censored.  Dropping
those seeds would report the mean of the successes and call it the mean.
Every row therefore carries `reached`, and every aggregate carries
`n_reached` beside `n_seeds`; a target that most seeds never hit is visible
as such rather than appearing as a confident ratio over the lucky few.

REPRODUCIBILITY.  Everything here is post-processing of `benchmark_rounds.csv`
and `campaign_status.csv`.  It runs after the campaigns, draws no random
numbers except a fixed-seed bootstrap for interval estimates, and is a pure
function of its input rows.
"""

from __future__ import annotations

import zlib
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


def stable_seed(key) -> int:
    """A reproducible bootstrap seed derived from a column identity.

    NOT `hash()`.  CPython randomizes the hash of strings and of tuples
    containing them once per process (PYTHONHASHSEED), so a seed derived
    from `hash()` differs between two runs of the same configuration and the
    confidence intervals move with it - a reported interval that changes
    between two reads of the same data is worse than no interval at all.
    CRC-32 of the key's repr is stable across processes, platforms and
    Python versions, which is the only property required here."""
    return int(zlib.crc32(repr(key).encode("utf-8")) & 0x7FFFFFFF)

#: cumulative resource columns carried on every per-round row
RESOURCE_KEYS = ("time_s", "egda_mol", "acid_mol", "waste_mL", "energy_kJ",
                 "nmr_acquisitions", "spatial_samples", "capillary_travel_m",
                 "reactor_conditions")

#: accuracy metrics, all "lower is better"
METRICS = ("param_err_pct", "blind_rmse_M")


def _rounds(rows: List[Dict], scenario: str, strategy: str,
            seed: int) -> List[Dict]:
    sel = [r for r in rows if r["scenario"] == scenario
           and r["strategy"] == strategy and int(r["seed"]) == int(seed)]
    return sorted(sel, key=lambda r: int(r["round"]))


def _first_reaching(hist: List[Dict], metric: str,
                    target: float) -> Optional[Dict]:
    """First round whose metric is at or below `target`.

    "First" and not "best": a campaign that dips below the target and later
    drifts back above it did reach the target at that cost, and an
    experimenter would have stopped there.  Using the best-ever round
    instead would credit the method with hindsight it does not have."""
    for r in hist:
        v = float(r.get(metric, np.nan))
        if np.isfinite(v) and v <= target:
            return r
    return None


def _at_or_before(hist: List[Dict], resource: str,
                  budget: float) -> Optional[Dict]:
    """Last round whose CUMULATIVE resource use is still within `budget` -
    i.e. what the method had achieved for that spend."""
    ok = [r for r in hist
          if np.isfinite(float(r.get(resource, np.nan)))
          and float(r[resource]) <= budget]
    return ok[-1] if ok else None


# ------------------------------------------------------------------------- #
# 1. budget to target
# ------------------------------------------------------------------------- #
def budget_to_target_rows(rows: List[Dict], scenario: str,
                          strategies: Sequence[str], reference: str,
                          seeds: Sequence[int],
                          targets: Dict[str, Sequence[float]]) -> List[Dict]:
    """One row per (strategy, seed, metric, target).

    The reference's own cost for the same target and seed travels on the
    row, so the ratio is paired by construction and a reader can audit it
    without joining tables."""
    out: List[Dict] = []
    for metric, tgts in targets.items():
        for target in tgts:
            ref_hit = {}
            for seed in seeds:
                ref_hit[seed] = _first_reaching(
                    _rounds(rows, scenario, reference, seed), metric, target)
            for strat in strategies:
                for seed in seeds:
                    hit = _first_reaching(
                        _rounds(rows, scenario, strat, seed), metric, target)
                    ref = ref_hit.get(seed)
                    row = {
                        "scenario": scenario, "strategy": strat,
                        "reference_strategy": reference,
                        "seed": int(seed), "metric": metric,
                        "target": float(target),
                        "reached": int(hit is not None),
                        "reference_reached": int(ref is not None),
                        "round": int(hit["round"]) if hit else -1,
                        "reference_round": int(ref["round"]) if ref else -1,
                    }
                    for k in RESOURCE_KEYS:
                        a = float(hit[k]) if hit and k in hit else float("nan")
                        b = float(ref[k]) if ref and k in ref else float("nan")
                        row[k] = a
                        row[f"reference_{k}"] = b
                        # ratio < 1 means the strategy needed LESS than the
                        # conventional reference to reach the same accuracy
                        row[f"ratio_{k}"] = (a / b if np.isfinite(a)
                                             and np.isfinite(b) and b > 0
                                             else float("nan"))
                    out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 2. accuracy at matched resource
# ------------------------------------------------------------------------- #
def matched_resource_rows(rows: List[Dict], scenario: str,
                          strategies: Sequence[str], reference: str,
                          seeds: Sequence[int],
                          resources: Sequence[str] = ("egda_mol", "time_s",
                                                      "energy_kJ",
                                                      "nmr_acquisitions")
                          ) -> List[Dict]:
    """What accuracy had each method reached by the time it had spent what
    the conventional reference spent IN TOTAL?

    This is the fair 'same money, who is further ahead' comparison, and it
    is defined even when neither method ever reaches a fixed target."""
    out: List[Dict] = []
    for resource in resources:
        for seed in seeds:
            ref_hist = _rounds(rows, scenario, reference, seed)
            if not ref_hist:
                continue
            budget = float(ref_hist[-1].get(resource, np.nan))
            if not np.isfinite(budget) or budget <= 0:
                continue
            for strat in strategies:
                hist = _rounds(rows, scenario, strat, seed)
                at = _at_or_before(hist, resource, budget)
                row = {"scenario": scenario, "strategy": strat,
                       "reference_strategy": reference, "seed": int(seed),
                       "resource": resource,
                       "reference_total": budget,
                       "spent": float(at[resource]) if at else float("nan"),
                       "round_at_budget": int(at["round"]) if at else -1,
                       "reference_final_round": int(ref_hist[-1]["round"])}
                for metric in METRICS:
                    a = float(at[metric]) if at else float("nan")
                    b = float(ref_hist[-1].get(metric, np.nan))
                    row[metric] = a
                    row[f"reference_{metric}"] = b
                    # > 1 means the strategy is BETTER (error reduced by
                    # this factor) at the same spend
                    row[f"improvement_factor_{metric}"] = (
                        b / a if np.isfinite(a) and np.isfinite(b) and a > 0
                        else float("nan"))
                out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 3. per-experiment trajectory: what was chosen, what it cost, what it bought
# ------------------------------------------------------------------------- #
def trajectory_rows(rows: List[Dict], design_rows: List[Dict],
                    scenario: str, reference: str) -> List[Dict]:
    """One row per (strategy, seed, round): the DECISION and its consequence,
    with the conventional reference's decision for the same round alongside.

    This is the table behind the 'first glance' figure - it lets a reader
    see that at round 4 the conventional ladder was still at 80 C by
    protocol while the optimizer had moved to 150 C at low flow, and what
    each choice cost."""
    by_key: Dict[Tuple[str, int, int], Dict] = {}
    for d in design_rows:
        if d.get("scenario") != scenario:
            continue
        k = (d["strategy"], int(d["seed"]), int(d["round"]))
        e = by_key.setdefault(k, {"z": [], "T_C": float(d["T_C"]),
                                  "Q_total_mL_min": float(d["Q_total_mL_min"]),
                                  "C_cat_M": float(d["C_cat_M"]),
                                  "C_EGDA_M": float(d["C_EGDA_M"]),
                                  "design_mode": d.get("design_mode", "")})
        e["z"].append(float(d["z_over_L"]))

    out: List[Dict] = []
    sel = [r for r in rows if r["scenario"] == scenario]
    for r in sorted(sel, key=lambda r: (r["strategy"], int(r["seed"]),
                                        int(r["round"]))):
        strat, seed, rnd = r["strategy"], int(r["seed"]), int(r["round"])
        d = by_key.get((strat, seed, rnd), {})
        ref_r = next((q for q in sel if q["strategy"] == reference
                      and int(q["seed"]) == seed and int(q["round"]) == rnd),
                     None)
        zs = sorted(d.get("z", []))
        row = {
            "scenario": scenario, "strategy": strat, "seed": seed,
            "round": rnd,
            "is_reference": int(strat == reference),
            "reference_strategy": reference,
            "T_C": d.get("T_C", float("nan")),
            "Q_total_mL_min": d.get("Q_total_mL_min", float("nan")),
            "C_cat_M": d.get("C_cat_M", float("nan")),
            "C_EGDA_M": d.get("C_EGDA_M", float("nan")),
            "design_mode": d.get("design_mode", ""),
            "n_positions": len(zs),
            "z_over_L_list": ";".join(f"{v:.4f}" for v in zs),
            "z_over_L_min": min(zs) if zs else float("nan"),
            "z_over_L_max": max(zs) if zs else float("nan"),
        }
        for k in RESOURCE_KEYS + METRICS:
            row[f"cum_{k}" if k in RESOURCE_KEYS else k] = float(
                r.get(k, np.nan))
            if ref_r is not None:
                row[f"reference_{k}"] = float(ref_r.get(k, np.nan))
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 4. aggregation over seeds
# ------------------------------------------------------------------------- #
def _agg(values: Sequence[float], seed: int = 12345) -> Dict[str, float]:
    v = np.array([x for x in values if np.isfinite(x)], dtype=float)
    if v.size == 0:
        return {"median": float("nan"), "q25": float("nan"),
                "q75": float("nan"), "boot_lo": float("nan"),
                "boot_hi": float("nan"), "n": 0}
    rng = np.random.default_rng(seed)          # fixed: post-processing only
    boot = np.array([np.median(rng.choice(v, v.size)) for _ in range(2000)]) \
        if v.size > 1 else np.array([v[0]])
    return {"median": float(np.median(v)),
            "q25": float(np.quantile(v, 0.25)),
            "q75": float(np.quantile(v, 0.75)),
            "boot_lo": float(np.quantile(boot, 0.025)),
            "boot_hi": float(np.quantile(boot, 0.975)),
            "n": int(v.size)}


def summarize_budget_to_target(btt: List[Dict]) -> List[Dict]:
    """Median resource ratio per (scenario, strategy, metric, target).

    Ratios are aggregated only over the seeds where BOTH the strategy and
    the reference reached the target - the only seeds on which a ratio is
    defined - and `n_paired` says how many that was, next to how many seeds
    existed.  A ratio computed over three lucky seeds out of forty is a
    different claim from one computed over forty, and the table makes the
    difference visible instead of averaging it away."""
    out: List[Dict] = []
    keys = sorted({(r["scenario"], r["strategy"], r["reference_strategy"],
                    r["metric"], r["target"]) for r in btt})
    for scen, strat, ref, metric, target in keys:
        sel = [r for r in btt if r["scenario"] == scen
               and r["strategy"] == strat and r["metric"] == metric
               and r["target"] == target]
        n_seeds = len(sel)
        n_reached = sum(int(r["reached"]) for r in sel)
        n_ref = sum(int(r["reference_reached"]) for r in sel)
        paired = [r for r in sel
                  if int(r["reached"]) and int(r["reference_reached"])]
        row = {"scenario": scen, "strategy": strat,
               "reference_strategy": ref, "metric": metric,
               "target": target, "n_seeds": n_seeds,
               "n_reached": n_reached, "n_reference_reached": n_ref,
               "n_paired": len(paired),
               "frac_reached": n_reached / n_seeds if n_seeds else float("nan")}
        for k in RESOURCE_KEYS:
            a = _agg([r[f"ratio_{k}"] for r in paired],
                     seed=stable_seed((scen, strat, metric, target, k)))
            row[f"ratio_{k}_median"] = a["median"]
            row[f"ratio_{k}_q25"] = a["q25"]
            row[f"ratio_{k}_q75"] = a["q75"]
            row[f"ratio_{k}_ci_lo"] = a["boot_lo"]
            row[f"ratio_{k}_ci_hi"] = a["boot_hi"]
        # fraction of paired seeds where the strategy was strictly cheaper
        for k in ("egda_mol", "time_s", "energy_kJ", "nmr_acquisitions"):
            rr = [r[f"ratio_{k}"] for r in paired
                  if np.isfinite(r[f"ratio_{k}"])]
            row[f"p_cheaper_{k}"] = (float(np.mean([x < 1.0 for x in rr]))
                                     if rr else float("nan"))
        out.append(row)
    return out


def summarize_matched_resource(mr: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    keys = sorted({(r["scenario"], r["strategy"], r["reference_strategy"],
                    r["resource"]) for r in mr})
    for scen, strat, ref, resource in keys:
        sel = [r for r in mr if r["scenario"] == scen
               and r["strategy"] == strat and r["resource"] == resource]
        row = {"scenario": scen, "strategy": strat,
               "reference_strategy": ref, "resource": resource,
               "n_seeds": len(sel)}
        for metric in METRICS:
            a = _agg([r[f"improvement_factor_{metric}"] for r in sel],
                     seed=stable_seed((scen, strat, resource, metric)))
            row[f"improvement_{metric}_median"] = a["median"]
            row[f"improvement_{metric}_q25"] = a["q25"]
            row[f"improvement_{metric}_q75"] = a["q75"]
            row[f"improvement_{metric}_ci_lo"] = a["boot_lo"]
            row[f"improvement_{metric}_ci_hi"] = a["boot_hi"]
            row[f"improvement_{metric}_n"] = a["n"]
            rr = [r[f"improvement_factor_{metric}"] for r in sel
                  if np.isfinite(r[f"improvement_factor_{metric}"])]
            row[f"p_better_{metric}"] = (float(np.mean([x > 1.0 for x in rr]))
                                         if rr else float("nan"))
        out.append(row)
    return out


# ------------------------------------------------------------------------- #
# 5. the one-glance headline
# ------------------------------------------------------------------------- #
def headline_rows(btt_summary: List[Dict],
                  mr_summary: List[Dict]) -> List[Dict]:
    """One line per (scenario, strategy) a reader can quote directly.

    The target chosen is the TIGHTEST one at least half the seeds reached,
    which is the strongest claim the data actually supports rather than the
    most flattering one available."""
    out: List[Dict] = []
    keys = sorted({(r["scenario"], r["strategy"]) for r in btt_summary})
    for scen, strat in keys:
        sel = [r for r in btt_summary if r["scenario"] == scen
               and r["strategy"] == strat
               and r["metric"] == "param_err_pct"
               and r["frac_reached"] >= 0.5 and r["n_paired"] >= 2]
        best = min(sel, key=lambda r: r["target"]) if sel else None
        mr = [r for r in mr_summary if r["scenario"] == scen
              and r["strategy"] == strat and r["resource"] == "egda_mol"]
        row = {"scenario": scen, "strategy": strat,
               "reference_strategy": (best or (mr[0] if mr else {})).get(
                   "reference_strategy", ""),
               "tightest_target_reached_by_half": (best["target"] if best
                                                   else float("nan")),
               "n_paired_at_target": best["n_paired"] if best else 0,
               "frac_seeds_reached": (best["frac_reached"] if best
                                      else float("nan"))}
        for k in ("egda_mol", "time_s", "energy_kJ", "nmr_acquisitions"):
            row[f"resource_ratio_{k}"] = (best[f"ratio_{k}_median"] if best
                                          else float("nan"))
            row[f"saving_pct_{k}"] = ((1.0 - best[f"ratio_{k}_median"]) * 100.0
                                      if best and
                                      np.isfinite(best[f"ratio_{k}_median"])
                                      else float("nan"))
        if mr:
            row["accuracy_gain_at_equal_material"] = \
                mr[0]["improvement_param_err_pct_median"]
            row["p_better_at_equal_material"] = \
                mr[0]["p_better_param_err_pct"]
        out.append(row)
    return out
