"""
Post-campaign reporting: the A/B/C/D showcase.

This is the ONLY module that calls VirtualLaboratory.reveal_truth() - after
all campaigns have finished - to benchmark the estimates against the hidden
parameters.  Styling follows the Layer 1 plotting conventions (same palette,
single axis per chart, direct end labels + frameless legend).
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Optional, Sequence

import numpy as np

from .layer1_bridge import Layer1Bridge, OperatingConditions
from .campaign import STRATEGY_NAMES, StrategyResult
from .parameters import (LOG_KEYS, PARAM_LABELS, ParameterSpace,
                         theta_component_name)


def _scale_unit(pk: str):
    """(display scale, unit string) for a natural parameter key."""
    if "Ea" in pk:
        return 1e-3, "kJ/mol"
    if pk.startswith("K"):
        return 1.0, "-"
    return 1.0, "L/(mol s)"


def _param_keys(results: Dict[str, StrategyResult]):
    """Estimated parameter keys of this campaign (shared by all strategies)."""
    return next(iter(results.values())).inference.space.param_keys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pfr_twin.plotting import SURFACE, INK, INK2, MUTED, GRID, AXIS, SERIES

# fixed strategy -> categorical slot assignment (never re-ordered)
STRATEGY_COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a", "D": "#eda100"}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _new_axes(title: str, xlabel: str, ylabel: str, figsize=(8.0, 5.0)):
    fig, ax = plt.subplots(figsize=figsize, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=12, loc="left", pad=12)
    ax.set_xlabel(xlabel, color=INK2, fontsize=10)
    ax.set_ylabel(ylabel, color=INK2, fontsize=10)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelsize=9)
    return fig, ax


def _save(fig, path: str):
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def _scored_keys(theta_nat: Dict[str, float], truth: Dict[str, float],
                 keys: Optional[Sequence[str]] = None,
                 exclude: Sequence[str] = ()) -> List[str]:
    pool = list(keys) if keys is not None else list(theta_nat)
    return [k for k in pool
            if k in truth and k in theta_nat and k not in set(exclude)]


def mean_rel_error_pct(theta_nat: Dict[str, float], truth: Dict[str, float],
                       keys: Optional[Sequence[str]] = None,
                       exclude: Sequence[str] = ()) -> float:
    """Arithmetic mean |relative error|.  Kept for continuity, but do NOT rank
    strategies on it: it is unbounded above and bounded by 100 % below, so a
    single badly-determined parameter swamps five well-determined ones and can
    invert the ranking.  Use log_mean_rel_error_pct for that."""
    ks = _scored_keys(theta_nat, truth, keys, exclude)
    if not ks:
        return float("nan")
    return 100.0 * float(np.mean([abs(theta_nat[k] / truth[k] - 1.0)
                                  for k in ks]))


def log_mean_rel_error_pct(theta_nat: Dict[str, float],
                           truth: Dict[str, float],
                           keys: Optional[Sequence[str]] = None,
                           exclude: Sequence[str] = ()) -> float:
    """Geometric-mean multiplicative error, exp(mean|ln(est/true)|) - 1, in %.

    The right summary for parameters estimated in log space: symmetric under
    est/true <-> true/est (a 2x overestimate and a 2x underestimate both score
    100 %), and no single component can dominate the mean the way an unbounded
    relative error can."""
    ks = _scored_keys(theta_nat, truth, keys, exclude)
    if not ks:
        return float("nan")
    ratios = []
    for k in ks:
        est, tru = theta_nat[k], truth[k]
        if est <= 0.0 or tru <= 0.0:        # non-positive: fall back to |rel|
            ratios.append(abs(est / tru - 1.0) if tru else float("inf"))
        else:
            ratios.append(abs(np.log(est / tru)))
    return 100.0 * float(np.exp(np.mean(ratios)) - 1.0)


def record_score_pct(rec, pkeys: Sequence[str],
                     truth: Dict[str, float]) -> float:
    """Score of one round: geometric-mean error over the parameters genuinely
    estimated at that round - identifiable (still in theta) and not resting on
    a box bound, since a pinned component reports the constraint, not data."""
    return log_mean_rel_error_pct(rec.theta_nat, truth, keys=pkeys,
                                  exclude=rec.report.active_bounds)


def campaign_score_pct(res: StrategyResult, truth: Dict[str, float]) -> float:
    """Ranking metric: record_score_pct of the final round."""
    return record_score_pct(res.history[-1],
                            res.inference.space.param_keys, truth)


# --------------------------------------------------------------------------- #
# figures
# --------------------------------------------------------------------------- #
def plot_error_convergence(results: Dict[str, StrategyResult],
                           truth: Dict[str, float], path: str):
    fig, ax = _new_axes("Parameter recovery vs experiment budget",
                        "experiments completed",
                        "geometric-mean parameter error (%)\n"
                        "(components at a box bound excluded)")
    ax.set_yscale("log")
    x_end = max(len(r.history) for r in results.values())
    for key, res in results.items():
        pkeys = results[key].inference.space.param_keys
        n = [rec.n_experiments for rec in res.history]
        e = [record_score_pct(rec, pkeys, truth) for rec in res.history]
        label = f"{key}: {STRATEGY_NAMES[key]}"
        ax.plot(n, e, color=STRATEGY_COLORS[key], linewidth=2, label=label,
                marker="o", markersize=5, markerfacecolor=SURFACE,
                markeredgecolor=STRATEGY_COLORS[key])
        ax.annotate(key, xy=(n[-1], e[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center",
                    color=INK2, fontsize=9)
    ax.set_xlim(0.8, x_end * 1.06)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9)
    _save(fig, path)


def plot_uncertainty_convergence(results: Dict[str, StrategyResult], path: str):
    fig, ax = _new_axes(
        "Predicted joint uncertainty vs experiment budget",
        "experiments completed",
        "D-criterion  (det V)^(1/2p)  - geometric-mean sigma")
    ax.set_yscale("log")
    x_end = max(len(r.history) for r in results.values())
    for key, res in results.items():
        n = np.array([rec.n_experiments for rec in res.history], dtype=float)
        d = np.array([rec.report.d_criterion for rec in res.history])
        ok = np.isfinite(d)
        label = f"{key}: {STRATEGY_NAMES[key]}"
        ax.plot(n[ok], d[ok], color=STRATEGY_COLORS[key], linewidth=2,
                label=label, marker="o", markersize=5,
                markerfacecolor=SURFACE, markeredgecolor=STRATEGY_COLORS[key])
        if ok.any():
            ax.annotate(key, xy=(n[ok][-1], d[ok][-1]), xytext=(6, 0),
                        textcoords="offset points", va="center",
                        color=INK2, fontsize=9)
    ax.set_xlim(0.8, x_end * 1.06)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9)
    _save(fig, path)


def plot_final_estimates(results: Dict[str, StrategyResult],
                         truth: Dict[str, float], path: str):
    """Small multiples: final estimate +-95% CI per strategy vs truth."""
    pkeys = _param_keys(results)
    n = len(pkeys)
    ncols = 3 if n > 4 else 2
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.4 * ncols, 3.5 * nrows),
                             facecolor=SURFACE)
    axes = np.atleast_1d(axes).ravel()
    keys = list(results.keys())
    xpos = np.arange(len(keys))
    for ip, (pk, ax) in enumerate(zip(pkeys, axes)):
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=MUTED, labelsize=9)
        scale, _ = _scale_unit(pk)
        ax.axhline(truth[pk] * scale, color=AXIS, linewidth=1.5,
                   linestyle="--", zorder=1)
        for i, key in enumerate(keys):
            rec = results[key].history[-1]
            val = rec.theta_nat[pk] * scale
            sig = rec.report.sigma[ip]
            if pk in rec.report.active_bounds:
                # resting on its box constraint: no valid interval to draw
                ax.plot(i, val, marker="x", markersize=9, markeredgewidth=2.2,
                        color=STRATEGY_COLORS[key], zorder=3)
                ax.annotate("at bound", xy=(i, val), xytext=(0, 8),
                            textcoords="offset points", ha="center",
                            color=MUTED, fontsize=7)
                continue
            if pk in LOG_KEYS:                 # log-space CI -> asymmetric
                arg = min(1.96 * float(sig), 700.0)   # guard exp() overflow
                lo = val * (1.0 - np.exp(-arg))
                hi = val * (np.exp(arg) - 1.0)
            else:
                lo = hi = 1.96 * sig            # sigma already in kJ
            ax.errorbar(i, val, yerr=[[lo], [hi]], fmt="o", markersize=7,
                        markerfacecolor=SURFACE, capsize=4, linewidth=2,
                        markeredgewidth=1.5, color=STRATEGY_COLORS[key],
                        zorder=3)
        ax.set_xticks(xpos, keys)
        ax.set_title(PARAM_LABELS[pk] + "   (dashed = hidden truth)",
                     color=INK, fontsize=10, loc="left")
    for ax in axes[n:]:
        ax.set_visible(False)
    fig.suptitle("Final estimates with 95% confidence intervals",
                 color=INK, fontsize=12, x=0.02, ha="left")
    _save(fig, path)


def plot_validation_profiles(bridge: Layer1Bridge, truth: Dict[str, float],
                             best: StrategyResult, u_val: OperatingConditions,
                             path: str):
    """Predictive check at a validation condition: hidden truth (solid) vs
    the best strategy's identified model (dashed)."""
    res_true = bridge.full_profiles(truth, u_val)
    res_est = bridge.full_profiles(best.history[-1].theta_nat, u_val)
    fig, ax = _new_axes(
        f"Validation at {u_val.T_C:.0f} °C (unseen) - truth solid, "
        f"strategy {best.key} model dashed",
        "reactor position x (m)", "concentration (mol/L)", figsize=(8.5, 5.0))
    for sp in ("EGDA", "EGMA", "EG", "AcOH"):
        ax.plot(res_true.x_m, res_true.conc[sp], color=SERIES[sp],
                linewidth=2, label=sp)
        ax.plot(res_est.x_m, res_est.conc[sp], color=SERIES[sp],
                linewidth=2, linestyle=(0, (4, 3)))
        ax.annotate(sp, xy=(res_true.x_m[-1], res_true.conc[sp][-1]),
                    xytext=(5, 0), textcoords="offset points",
                    va="center", color=INK2, fontsize=9)
    ax.set_xlim(0.0, res_true.x_m[-1] * 1.12)
    ax.set_ylim(bottom=0.0)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9)
    _save(fig, path)


# --------------------------------------------------------------------------- #
# tables and text report
# --------------------------------------------------------------------------- #
def write_history_csv(results: Dict[str, StrategyResult],
                      truth: Dict[str, float], path: str):
    pkeys = _param_keys(results)
    val_cols = [pk.replace("_J", "_kJ") for pk in pkeys]
    sig_cols = ["sigma_" + theta_component_name(pk).replace(" ", "")
                + ("_kJ" if "Ea" in pk else "") for pk in pkeys]
    cols = (["strategy", "round", "n_experiments", "n_data", "T_C",
             "Q_total_mL_min", "C_EGDA_M", "C_cat_M"] + val_cols + sig_cols
            + ["logdet_F", "d_criterion", "max_rel_ci_pct", "mean_rel_err_pct",
               "log_mean_rel_err_pct", "active_bounds"])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for key, res in results.items():
            for rec in res.history:
                t, s = rec.theta_nat, rec.report.sigma
                vals = [f"{t[pk] * _scale_unit(pk)[0]:.6e}" for pk in pkeys]
                sigs = [f"{s[q]:.4e}" for q in range(len(pkeys))]
                w.writerow([
                    key, rec.round, rec.n_experiments, rec.n_data,
                    rec.u.T_C, rec.u.Q1_mL_min + rec.u.Q2_mL_min,
                    rec.u.C_EGDA_M, rec.u.C_cat_M] + vals + sigs + [
                    f"{rec.report.logdet_F:.4f}",
                    f"{rec.report.d_criterion:.4e}",
                    f"{rec.report.max_rel_ci_pct:.3f}",
                    f"{mean_rel_error_pct(rec.theta_nat, truth, pkeys):.3f}",
                    f"{log_mean_rel_error_pct(rec.theta_nat, truth, pkeys):.3f}",
                    "|".join(rec.report.active_bounds)])


def write_final_report(results: Dict[str, StrategyResult],
                       truth: Dict[str, float], lab_stats: Dict[str, int],
                       path: str, screen_lines: Optional[Sequence[str]] = None):
    pkeys = _param_keys(results)
    space = next(iter(results.values())).inference.space
    lines = ["=" * 74,
             "Virtual self-driving laboratory - final campaign report",
             "=" * 74, ""]
    if screen_lines:
        lines += list(screen_lines) + [""]
    lines.append("Hidden truth (revealed post-campaign for benchmarking only):")
    for pk in pkeys:
        scale, unit = _scale_unit(pk)
        lines.append(f"  {pk:8s} = {truth[pk] * scale:.4g} {unit}")
    for pk in space.fixed_keys:
        scale, unit = _scale_unit(pk)
        lines.append(f"  {pk:8s} = {truth[pk] * scale:.4g} {unit}"
                     f"   [NOT ESTIMATED - held at "
                     f"{space.fixed[pk] * scale:.4g}]")
    lines.append("")
    lines += ["Ranking metric: geometric-mean parameter error over the "
              "identifiable, unpinned",
              "components (exp(mean|ln est/true|) - 1).  The arithmetic mean "
              "is also shown but",
              "is not used to rank: it is unbounded above and one bad "
              "component swamps the rest.", ""]

    for key, res in results.items():
        rec = res.history[-1]
        rep = rec.report
        scored = [k for k in pkeys if k not in rep.active_bounds]
        lines += ["-" * 74,
                  f"Strategy {key}: {STRATEGY_NAMES[key]}",
                  f"  experiments run      : {rec.n_experiments} "
                  f"({rec.n_data} concentration observations)",
                  f"  stopping             : {res.stop_reason}",
                  f"  SCORE geo-mean err   : "
                  f"{campaign_score_pct(res, truth):.2f} %"
                  + (f"   (over {len(scored)}/{len(pkeys)} unpinned)"
                     if len(scored) != len(pkeys) else ""),
                  f"  mean |rel err|       : "
                  f"{mean_rel_error_pct(rec.theta_nat, truth, pkeys):.2f} %",
                  f"  max 95% rel CI       : {rep.max_rel_ci_pct:.2f} %",
                  f"  log det F            : {rep.logdet_F:.2f}"
                  + ("" if rep.well_posed else "   [RANK-DEFICIENT]")]
        if rep.active_bounds:
            lines.append("  !! AT BOX BOUND      : "
                         + ", ".join(rep.active_bounds)
                         + "  - these are the CONSTRAINT, not estimates;")
            lines.append("                         their intervals are void "
                         "and they are excluded from the score.")
        lines.append("  estimates (95% CI) vs truth:")
        for ip, pk in enumerate(pkeys):
            scale, _ = _scale_unit(pk)
            v = rec.theta_nat[pk] * scale
            if pk in rep.active_bounds:
                lines.append(f"    {pk:8s}: {v:11.4g}  "
                             f"[{'AT BOUND - no valid CI':>22s}]"
                             f"   true {truth[pk] * scale:11.4g}")
                continue
            if pk in LOG_KEYS:
                lo, hi = v * np.exp(-1.96 * rep.sigma[ip]), v * np.exp(1.96 * rep.sigma[ip])
            else:
                lo, hi = v - 1.96 * rep.sigma[ip], v + 1.96 * rep.sigma[ip]
            lines.append(f"    {pk:8s}: {v:11.4g}  [{lo:10.4g}, {hi:10.4g}]"
                         f"   true {truth[pk] * scale:11.4g}")
        lines.append("  parameter correlation matrix ("
                     + ", ".join(theta_component_name(pk) for pk in pkeys)
                     + "):")
        for row in rep.corr:
            lines.append("    " + "  ".join(f"{v: .3f}" for v in row))
        lines.append("  FIM eigenvalues (ascending): "
                     + ", ".join(f"{v:.3e}" for v in rep.eigvals))
        lines.append("  experiments chosen: "
                     + "; ".join(r.u.label() for r in res.history))
        lines.append("")

    lines += ["-" * 74,
              f"Virtual lab usage: {lab_stats['experiments']} experiments run, "
              f"truth revealed {lab_stats['reveals']} time(s), "
              "all after the campaigns ended.", ""]
    text = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text
