"""
Post-campaign reporting: the A/B/C/D showcase.

This is the ONLY module that calls VirtualLaboratory.reveal_truth() - after
all campaigns have finished - to benchmark the estimates against the hidden
parameters.  Styling follows the Layer 1 plotting conventions (same palette,
single axis per chart, direct end labels + frameless legend).

Every figure ships with a sibling CSV of exactly the data it draws, written
by `_save`, which takes the data as a REQUIRED argument so a new plot cannot
quietly skip it (the same rule `pfr_twin.plotting._save` enforces in Layer 1).
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .design import _EIG_FLOOR
from .layer1_bridge import Layer1Bridge, OperatingConditions
from .campaign import STRATEGY_NAMES, StrategyResult
from .parallel import FIMSpec, ParallelConfig, information_matrices
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
from pfr_twin.runio import csv_beside, write_columns_csv, write_rows_csv

# fixed strategy -> categorical slot assignment (never re-ordered)
STRATEGY_COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a", "D": "#eda100"}
# distinct SHAPES too, for scatters where strategies can land on the same
# point: A and B run the identical fixed design, so colour alone would let
# whichever is drawn last hide the other entirely.
STRATEGY_MARKERS = {"A": "o", "B": "s", "C": "^", "D": "D"}


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


def _save(fig, path: str, data) -> str:
    """Write the figure AND the CSV of exactly what it draws.

    `data` is required, not optional: the project rule is that no figure ships
    without re-usable data behind it, and a required argument is the only way
    to make forgetting it impossible rather than merely discouraged.

        {name: values}    equal-length numeric columns
        (header, rows)    when the table mixes text and numbers

    Returns the CSV path."""
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    if isinstance(data, tuple):
        header, rows = data
        return write_rows_csv(csv_beside(path), header, rows)
    return write_columns_csv(csv_beside(path), data)


def _padded(values: Sequence[float], n: int) -> np.ndarray:
    """Column of length n, NaN-filled past the end.

    Strategies can stop early, so their histories differ in length; a CSV
    still needs rectangular columns."""
    v = np.asarray(values, dtype=float).ravel()
    if len(v) >= n:
        return v[:n]
    return np.concatenate([v, np.full(n - len(v), np.nan)])


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
    data = {"n_experiments": np.arange(1, x_end + 1, dtype=float)}
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
        data[f"geo_mean_err_pct_{key}"] = _padded(e, x_end)
    ax.set_xlim(0.8, x_end * 1.06)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9)
    return _save(fig, path, data)


def plot_uncertainty_convergence(results: Dict[str, StrategyResult], path: str):
    fig, ax = _new_axes(
        "Predicted joint uncertainty vs experiment budget",
        "experiments completed",
        "D-criterion  (det V)^(1/2p)  - geometric-mean sigma")
    ax.set_yscale("log")
    x_end = max(len(r.history) for r in results.values())
    data = {"n_experiments": np.arange(1, x_end + 1, dtype=float)}
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
        # inf rounds are kept in the CSV: "not yet identifiable" is a result,
        # and silently dropping them would misalign the experiment axis.
        data[f"d_criterion_{key}"] = _padded(d, x_end)
    ax.set_xlim(0.8, x_end * 1.06)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9)
    return _save(fig, path, data)


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
    rows = []
    for ip, (pk, ax) in enumerate(zip(pkeys, axes)):
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=MUTED, labelsize=9)
        scale, unit = _scale_unit(pk)
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
                rows.append([pk, unit, key, f"{val:.8e}", "", "",
                             f"{truth[pk] * scale:.8e}", "1"])
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
            rows.append([pk, unit, key, f"{val:.8e}", f"{val - lo:.8e}",
                         f"{val + hi:.8e}", f"{truth[pk] * scale:.8e}", "0"])
        ax.set_xticks(xpos, keys)
        ax.set_title(PARAM_LABELS[pk] + "   (dashed = hidden truth)",
                     color=INK, fontsize=10, loc="left")
    for ax in axes[n:]:
        ax.set_visible(False)
    fig.suptitle("Final estimates with 95% confidence intervals",
                 color=INK, fontsize=12, x=0.02, ha="left")
    return _save(fig, path, (["parameter", "unit", "strategy", "estimate",
                              "ci95_low", "ci95_high", "truth", "at_bound"],
                             rows))


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
    data = {"x_m": res_true.x_m, "tau_s": res_true.tau_s}
    for sp in ("EGDA", "EGMA", "EG", "AcOH"):
        ax.plot(res_true.x_m, res_true.conc[sp], color=SERIES[sp],
                linewidth=2, label=sp)
        ax.plot(res_est.x_m, res_est.conc[sp], color=SERIES[sp],
                linewidth=2, linestyle=(0, (4, 3)))
        ax.annotate(sp, xy=(res_true.x_m[-1], res_true.conc[sp][-1]),
                    xytext=(5, 0), textcoords="offset points",
                    va="center", color=INK2, fontsize=9)
        data[f"C_{sp}_truth"] = res_true.conc[sp]
        data[f"C_{sp}_strategy_{best.key}"] = res_est.conc[sp]
    ax.set_xlim(0.0, res_true.x_m[-1] * 1.12)
    ax.set_ylim(bottom=0.0)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9)
    return _save(fig, path, data)


def _panel(ax):
    """Apply the house style to one axes of a small-multiples grid."""
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelsize=9)
    return ax


def profile_rmse_M(res_a, res_b, species=("EGDA", "EGMA", "EG", "AcOH")) -> float:
    """RMS concentration difference between two axial profiles, mol/L,
    pooled over the measured species."""
    diffs = np.concatenate([res_a.conc[sp] - res_b.conc[sp] for sp in species])
    return float(np.sqrt(np.mean(diffs ** 2)))


def plot_prediction_improvement(bridge: Layer1Bridge, truth: Dict[str, float],
                                literature: Dict[str, float],
                                best: StrategyResult,
                                u_val: OperatingConditions, path: str) -> str:
    """What the campaign actually bought, in the only currency that matters
    to a user of the model: predictive accuracy at a condition nobody
    measured.

    Three profiles per species - the hidden truth, the literature kinetics the
    campaign started from, and the model identified by the best strategy.  The
    literature curve is the honest "do nothing" baseline: it is what an
    engineer would have predicted with published parameters and no experiments
    at all, so the gap between it and the truth is the error the campaign had
    to remove, and the gap that remains is what it did not."""
    species = ("EGDA", "EGMA", "EG", "AcOH")
    res_true = bridge.full_profiles(truth, u_val)
    res_lit = bridge.full_profiles(literature, u_val)
    res_est = bridge.full_profiles(best.history[-1].theta_nat, u_val)
    rmse_lit = profile_rmse_M(res_lit, res_true, species)
    rmse_est = profile_rmse_M(res_est, res_true, species)

    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.4), facecolor=SURFACE)
    axes = np.atleast_1d(axes).ravel()
    data = {"x_m": res_true.x_m, "tau_s": res_true.tau_s}
    for sp, ax in zip(species, axes):
        _panel(ax)
        x = res_true.x_m
        # truth as a wide translucent band, identified as a crisp dashed line
        # on top: where the campaign succeeded the dashes sit INSIDE the band,
        # which reads as agreement.  A thin solid truth line would simply be
        # hidden by the estimate and look like a missing curve.
        ax.plot(x, res_true.conc[sp], color=SERIES[sp], linewidth=5.0,
                alpha=0.35, solid_capstyle="round", label="hidden truth",
                zorder=3)
        ax.plot(x, res_lit.conc[sp], color=MUTED, linewidth=1.8,
                linestyle=(0, (1, 2)), label="literature kinetics (0 experiments)",
                zorder=2)
        ax.plot(x, res_est.conc[sp], color=SERIES[sp], linewidth=1.8,
                linestyle=(0, (5, 3)),
                label=f"identified by strategy {best.key}", zorder=4)
        e_lit = np.sqrt(np.mean((res_lit.conc[sp] - res_true.conc[sp]) ** 2))
        e_est = np.sqrt(np.mean((res_est.conc[sp] - res_true.conc[sp]) ** 2))
        ax.set_title(f"{sp}    RMSE  literature {e_lit * 1e3:.0f} mM  ->  "
                     f"identified {e_est * 1e3:.0f} mM",
                     color=INK, fontsize=10, loc="left")
        ax.set_xlabel("reactor position x (m)", color=INK2, fontsize=9)
        ax.set_ylabel("concentration (mol/L)", color=INK2, fontsize=9)
        ax.set_xlim(0.0, x[-1])
        ax.set_ylim(bottom=0.0)
        data[f"C_{sp}_truth"] = res_true.conc[sp]
        data[f"C_{sp}_literature"] = res_lit.conc[sp]
        data[f"C_{sp}_identified"] = res_est.conc[sp]
    axes[0].legend(frameon=False, labelcolor=INK2, fontsize=8, loc="best")
    gain = (f"{rmse_lit / rmse_est:.1f}x lower" if rmse_est > 0
            else "exact")
    fig.suptitle(
        f"Predictive accuracy at an unseen condition "
        f"({u_val.T_C:.0f} °C, {u_val.Q1_mL_min + u_val.Q2_mL_min:.1f} mL/min, "
        f"EGDA {u_val.C_EGDA_M:.2f} M, cat {u_val.C_cat_M:.2f} M)\n"
        f"pooled RMSE   literature {rmse_lit * 1e3:.0f} mM   ->   "
        f"strategy {best.key} {rmse_est * 1e3:.0f} mM   ({gain})",
        color=INK, fontsize=11.5, x=0.02, ha="left")
    return _save(fig, path, data)


def experiments_to_target(res: StrategyResult, truth: Dict[str, float],
                          target_pct: float) -> Optional[int]:
    """First experiment count at which this strategy has determined EVERY
    estimated parameter to `target_pct`, or None if it never does.

    Two conditions beyond the error itself, and both are load-bearing.
    `record_score_pct` averages only over parameters not resting on a box
    bound, because a pinned component reports the constraint rather than the
    data - correct for scoring a final answer, but it means an early round
    with four of six parameters parked on their bounds is scored on the
    remaining two and can post a spuriously low number.  On the acid route the
    conventional design does exactly that: it scores under 5 % at round three
    and finishes the campaign at over 200 %.  Reading that as "reached the
    target in three experiments" would be plainly wrong, so a round only
    counts when

      * no estimated parameter sits on a bound - the score covers all of
        theta, so strategies are compared on the same quantity, and
      * the FIM is well posed - a rank-deficient round has not determined
        anything, however close its point estimate happens to land.
    """
    pkeys = res.inference.space.param_keys
    for rec in res.history:
        if rec.report.active_bounds or not rec.report.well_posed:
            continue
        if record_score_pct(rec, pkeys, truth) <= target_pct:
            return rec.n_experiments
    return None


def plot_budget_to_target(results: Dict[str, StrategyResult],
                          truth: Dict[str, float], path: str,
                          targets: Sequence[float] = (50.0, 25.0, 10.0, 5.0)
                          ) -> str:
    """The proposal's headline number: how many reactor experiments each
    strategy needs to reach a stated accuracy.

    Error-vs-budget curves are the honest scientific plot but a reviewer reads
    them as "the lines go down".  This one answers the question a funder
    actually asks - how much lab time does the method save - by inverting the
    same curves onto the axis that costs money."""
    keys = list(results.keys())
    budget = max(len(r.history) for r in results.values())
    fig, ax = _new_axes(
        "Experiments required to determine EVERY kinetic parameter to a "
        "target accuracy\n"
        "counted only from rounds with a well-posed FIM and no parameter on "
        "a bound; hatched = never reached",
        "target geometric-mean parameter error",
        "reactor experiments needed", figsize=(9.4, 5.8))
    width = 0.8 / max(len(keys), 1)
    xpos = np.arange(len(targets))
    rows = []
    for j, key in enumerate(keys):
        heights, hatches = [], []
        for t in targets:
            n = experiments_to_target(results[key], truth, t)
            heights.append(float(n) if n is not None else float(budget))
            hatches.append(n is None)
            rows.append([f"{t:g}", key, "" if n is None else n,
                         "0" if n is None else "1", budget])
        offs = xpos + (j - (len(keys) - 1) / 2) * width
        for i, (x, h, unreached) in enumerate(zip(offs, heights, hatches)):
            ax.bar(x, h, width=width * 0.9,
                   color=SURFACE if unreached else STRATEGY_COLORS[key],
                   edgecolor=STRATEGY_COLORS[key],
                   hatch="///" if unreached else None, linewidth=1.4,
                   label=f"{key}: {STRATEGY_NAMES[key]}" if i == 0 else None)
            # "never" is written INSIDE the bar: a hatched bar drawn to the
            # budget line is the honest height, but a number floating above it
            # reads at a glance as an achieved result.
            if unreached:
                ax.annotate("never", xy=(x, h * 0.5), rotation=90,
                            ha="center", va="center", color=MUTED, fontsize=8)
            else:
                ax.annotate(f"{h:.0f}", xy=(x, h), xytext=(0, 3),
                            textcoords="offset points", ha="center",
                            color=INK2, fontsize=9)
    ax.set_xticks(xpos, [f"≤ {t:g} %" for t in targets])
    ax.set_ylim(0.0, budget * 1.16)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.axhline(budget, color=AXIS, linewidth=1.2, linestyle="--", zorder=1)
    ax.annotate(f"campaign budget = {budget}", xy=(1.0, budget),
                xycoords=("axes fraction", "data"), xytext=(0, 4),
                textcoords="offset points", ha="right", color=MUTED,
                fontsize=8)
    # legend below the axes: with four strategies x four targets there is no
    # empty corner left inside the plot
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9, loc="upper center",
              bbox_to_anchor=(0.5, -0.14), ncol=min(len(keys), 4))
    return _save(fig, path, (["target_geo_mean_err_pct", "strategy",
                              "experiments_needed", "reached", "budget"], rows))


def plot_information_landscape(spec: FIMSpec, theta: np.ndarray,
                               candidates: Sequence[OperatingConditions],
                               results: Dict[str, StrategyResult], path: str,
                               parallel: Optional[ParallelConfig] = None) -> str:
    """WHY the autonomous strategies win, in one picture.

    Background: the information a SINGLE experiment can supply, log det of its
    own Fisher matrix, over the declared (T, Q) grid.  Each cell is the best
    value achievable at that temperature and flow over the feed compositions
    in the design space, so every experiment can be plotted on it regardless
    of its own feed - the cell is an upper bound on what that (T, Q) can give.

    Foreground: where each strategy actually spent its budget.  The fixed
    design walks a temperature ladder at one nominal flow because that is what
    it was told to do; the MBDoE strategies concentrate on the bright ridge
    because they can see this surface (at their current estimate) and the
    ladder cannot."""
    mats = information_matrices(spec, theta, candidates, parallel)
    scores = np.array([np.sum(np.log(np.maximum(np.linalg.eigvalsh(M),
                                                _EIG_FLOOR))) for M in mats])
    t_vals = np.array([u.T_C for u in candidates])
    q_vals = np.array([u.Q1_mL_min + u.Q2_mL_min for u in candidates])
    t_levels = np.unique(t_vals)
    q_levels = np.unique(q_vals)

    grid = np.full((len(q_levels), len(t_levels)), -np.inf)
    for s, t, q in zip(scores, t_vals, q_vals):
        i, j = int(np.searchsorted(q_levels, q)), int(np.searchsorted(t_levels, t))
        grid[i, j] = max(grid[i, j], s)

    fig, ax = _new_axes(
        "Single-experiment information over the design space, and where each "
        "strategy spent its budget\n"
        "marker size grows with round number; A and B run the same fixed "
        "design, so their markers coincide",
        "temperature (°C)", "total flow (mL/min)  -  log scale",
        figsize=(10.4, 6.2))
    mesh = ax.pcolormesh(_edges(t_levels), _edges(q_levels, log=True),
                         np.ma.masked_invalid(grid), cmap="Blues",
                         shading="auto", zorder=0)
    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label("log det of one experiment's Fisher matrix\n"
                   "(best over feed compositions at this T, Q)",
                   color=INK2, fontsize=9)
    cbar.ax.tick_params(colors=MUTED, labelsize=8)
    cbar.outline.set_edgecolor(AXIS)

    rows = [["landscape", "", "", f"{t:g}", f"{q:g}", "", "",
             f"{grid[i, j]:.6f}"]
            for i, q in enumerate(q_levels) for j, t in enumerate(t_levels)
            if np.isfinite(grid[i, j])]
    for key, res in results.items():
        xs = [rec.u.T_C for rec in res.history]
        ys = [rec.u.Q1_mL_min + rec.u.Q2_mL_min for rec in res.history]
        # marker grows with round number: the path through the box is the story
        sizes = 34.0 + 20.0 * np.arange(len(xs))
        ax.scatter(xs, ys, s=sizes, marker=STRATEGY_MARKERS[key],
                   facecolor="none", edgecolor=STRATEGY_COLORS[key],
                   linewidth=2.0, zorder=4,
                   label=f"{key}: {STRATEGY_NAMES[key]}")
        for rec in res.history:
            rows.append(["experiment", key, rec.round, f"{rec.u.T_C:g}",
                         f"{rec.u.Q1_mL_min + rec.u.Q2_mL_min:g}",
                         f"{rec.u.C_EGDA_M:g}", f"{rec.u.C_cat_M:g}", ""])
    ax.set_yscale("log")
    leg = ax.legend(frameon=True, labelcolor=INK2, fontsize=9, loc="lower left",
                    facecolor=SURFACE, edgecolor=AXIS, framealpha=0.92)
    leg.get_frame().set_linewidth(0.8)
    return _save(fig, path, (["kind", "strategy", "round", "T_C",
                              "Q_total_mL_min", "C_EGDA_M", "C_cat_M",
                              "logdet_single_experiment_FIM"], rows))


def _edges(levels: np.ndarray, log: bool = False) -> np.ndarray:
    """Cell edges around unevenly spaced levels, for pcolormesh."""
    v = np.log(levels) if log else np.asarray(levels, dtype=float)
    mid = 0.5 * (v[1:] + v[:-1])
    out = np.concatenate([[v[0] - (mid[0] - v[0])] if len(mid) else [v[0] - 0.5],
                          mid,
                          [v[-1] + (v[-1] - mid[-1])] if len(mid) else [v[0] + 0.5]])
    return np.exp(out) if log else out


def plot_confidence_ellipses(results: Dict[str, StrategyResult],
                             truth: Dict[str, float], path: str) -> str:
    """Joint 95% confidence regions for each rate constant's (ln k_ref, Ea)
    pair - the shape of what the campaign learned, not just its size.

    A rate constant and its activation energy are almost perfectly correlated
    when every experiment sits at a similar temperature: the data then fixes
    the product, not the pair, and the confidence region is a long thin
    diagonal sliver.  Breaking that correlation is precisely what an
    experiment design is for, so a short, round, small ellipse is the visual
    signature of a good campaign in a way that a single error bar cannot
    show."""
    space = next(iter(results.values())).inference.space
    pkeys = list(space.param_keys)
    pairs = [(k, e) for k, e in (("k1_ref", "Ea1_J"), ("k2_ref", "Ea2_J"))
             if k in pkeys and e in pkeys]
    if not pairs:
        raise ValueError("No (k_ref, Ea) pair survived the identifiability "
                         "screen; nothing to draw.")
    ang = np.linspace(0.0, 2.0 * np.pi, 181)
    circle = np.vstack([np.cos(ang), np.sin(ang)])
    chi2_95 = 5.991                              # 2 degrees of freedom

    fig, axes = plt.subplots(1, len(pairs), figsize=(5.6 * len(pairs), 5.0),
                             facecolor=SURFACE)
    axes = np.atleast_1d(axes).ravel()
    rows = []
    for (kk, ek), ax in zip(pairs, axes):
        _panel(ax)
        ik, ie = pkeys.index(kk), pkeys.index(ek)
        tx, ty = float(np.log(truth[kk])), float(truth[ek] / 1e3)
        xs_lim, ys_lim = [tx], [ty]
        for key, res in results.items():
            rec = res.history[-1]
            centre = np.array([res.inference.theta[ik], res.inference.theta[ie]])
            cov = rec.report.cov[np.ix_([ik, ie], [ik, ie])]
            try:
                L = np.linalg.cholesky(cov)
            except np.linalg.LinAlgError:
                L = None                          # not positive definite
            ax.plot(*centre, marker="o", markersize=7, markerfacecolor=SURFACE,
                    markeredgecolor=STRATEGY_COLORS[key], markeredgewidth=1.8,
                    zorder=4)
            rows.append([f"{kk}|{ek}", key, "centre", 0,
                         f"{centre[0]:.8e}", f"{centre[1]:.8e}"])
            if L is None:
                continue
            pts = centre[:, None] + np.sqrt(chi2_95) * (L @ circle)
            ax.plot(pts[0], pts[1], color=STRATEGY_COLORS[key], linewidth=2,
                    label=f"{key}: {STRATEGY_NAMES[key]}", zorder=3)
            for i in range(pts.shape[1]):
                rows.append([f"{kk}|{ek}", key, "ellipse95", i,
                             f"{pts[0, i]:.8e}", f"{pts[1, i]:.8e}"])
            # only well-posed rounds set the view: a rank-deficient ellipse is
            # astronomically large and would compress everything else to a dot
            if rec.report.well_posed:
                xs_lim += [pts[0].min(), pts[0].max()]
                ys_lim += [pts[1].min(), pts[1].max()]
        ax.plot(tx, ty, marker="*", markersize=17,
                color=INK, zorder=5, linestyle="none", label="hidden truth")
        rows.append([f"{kk}|{ek}", "truth", "truth", 0,
                     f"{tx:.8e}", f"{ty:.8e}"])
        px = 0.22 * max(np.ptp(xs_lim), 1e-3)
        py = 0.22 * max(np.ptp(ys_lim), 1e-3)
        ax.set_xlim(min(xs_lim) - px, max(xs_lim) + px)
        ax.set_ylim(min(ys_lim) - py, max(ys_lim) + py)
        ax.set_xlabel(f"ln {kk.replace('_ref', '')}_ref   [L/(mol s)]",
                      color=INK2, fontsize=9)
        ax.set_ylabel(f"{ek.replace('_J', '')}  (kJ/mol)", color=INK2,
                      fontsize=9)
        ax.set_title(f"{kk.replace('_ref', '')} step - joint 95 % region",
                     color=INK, fontsize=10, loc="left")
        # framed: ellipses fill the panel, so a frameless legend sits on top
        # of the very curves it is naming
        leg = ax.legend(frameon=True, labelcolor=INK2, fontsize=8, loc="best",
                        facecolor=SURFACE, edgecolor=AXIS, framealpha=0.92)
        leg.get_frame().set_linewidth(0.8)
    fig.suptitle("Joint parameter uncertainty (ellipses clipped to the "
                 "well-posed strategies' scale)",
                 color=INK, fontsize=11.5, x=0.02, ha="left")
    return _save(fig, path, (["pair", "strategy", "role", "point_index",
                              "ln_k_ref", "Ea_kJ_mol"], rows))


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


def write_summary_csv(results: Dict[str, StrategyResult],
                      truth: Dict[str, float], path: str,
                      prediction_rmse_M: Optional[Dict[str, float]] = None,
                      targets: Sequence[float] = (50.0, 25.0, 10.0, 5.0)
                      ) -> str:
    """One row per strategy with the numbers a proposal quotes.

    `campaign_history.csv` is the full round-by-round record; this is the
    end-of-campaign digest, so the comparison can be pasted into a table
    without re-deriving anything from the history."""
    pkeys = _param_keys(results)
    header = (["strategy", "description", "experiments", "n_observations",
               "stopped_early", "stop_reason", "geo_mean_err_pct",
               "mean_rel_err_pct", "max_rel_ci_pct", "logdet_F",
               "d_criterion", "well_posed", "params_at_bound"]
              + [f"experiments_to_{t:g}pct" for t in targets]
              + [f"rel_err_pct_{pk}" for pk in pkeys])
    rows = []
    for key, res in results.items():
        rec = res.history[-1]
        rep = rec.report
        errs = []
        for pk in pkeys:
            if pk in rep.active_bounds:
                errs.append("")            # the constraint, not an estimate
            else:
                errs.append(f"{abs(rec.theta_nat[pk] / truth[pk] - 1.0) * 100.0:.4f}")
        rows.append([
            key, STRATEGY_NAMES[key], rec.n_experiments, rec.n_data,
            int(res.stopped_early), res.stop_reason,
            f"{campaign_score_pct(res, truth):.4f}",
            f"{mean_rel_error_pct(rec.theta_nat, truth, pkeys):.4f}",
            f"{rep.max_rel_ci_pct:.4f}", f"{rep.logdet_F:.4f}",
            f"{rep.d_criterion:.6e}", int(rep.well_posed),
            "|".join(rep.active_bounds)]
            + [experiments_to_target(res, truth, t) or "" for t in targets]
            + errs)
    if prediction_rmse_M:
        header.append("validation_profile_rmse_M")
        for row, key in zip(rows, results):
            row.append(f"{prediction_rmse_M.get(key, float('nan')):.6e}")
    return write_rows_csv(path, header, rows)


def headline_lines(results: Dict[str, StrategyResult],
                   truth: Dict[str, float], best_key: str,
                   rmse_literature_M: Optional[float] = None,
                   rmse_best_M: Optional[float] = None,
                   targets: Sequence[float] = (50.0, 25.0, 10.0, 5.0)
                   ) -> List[str]:
    """The two claims the campaign is evidence for, stated as numbers:
    fewer experiments for the same knowledge, and a model that predicts an
    unmeasured condition the literature parameters get wrong."""
    budget = max(len(r.history) for r in results.values())
    lines = ["HEADLINE COMPARISON", "-" * 74,
             "Reactor experiments needed to determine EVERY estimated "
             "parameter to a target",
             "geometric-mean accuracy, counting only rounds whose FIM is well "
             "posed and whose",
             f"parameters are all off their bounds ('-' = not reached within "
             f"{budget}):", ""]
    width = max(len(STRATEGY_NAMES[k]) for k in results) + 6
    lines.append("  " + "strategy".ljust(width)
                 + "".join(f"{'<=' + f'{t:g}%':>10s}" for t in targets))
    for key, res in results.items():
        cells = []
        for t in targets:
            n = experiments_to_target(res, truth, t)
            cells.append(f"{n:>10d}" if n is not None else f"{'-':>10s}")
        lines.append("  " + f"{key}: {STRATEGY_NAMES[key]}".ljust(width)
                     + "".join(cells))
    lines.append("")
    if rmse_literature_M is not None and rmse_best_M is not None:
        gain = (rmse_literature_M / rmse_best_M if rmse_best_M > 0
                else float("inf"))
        lines += [
            "Predictive accuracy at the validation condition (never measured):",
            f"  literature kinetics, 0 experiments : "
            f"{rmse_literature_M * 1e3:8.1f} mM pooled RMSE",
            f"  strategy {best_key} identified model       : "
            f"{rmse_best_M * 1e3:8.1f} mM pooled RMSE   ({gain:.1f}x lower)",
            ""]
    return lines


def write_final_report(results: Dict[str, StrategyResult],
                       truth: Dict[str, float], lab_stats: Dict[str, int],
                       path: str, screen_lines: Optional[Sequence[str]] = None,
                       headline: Optional[Sequence[str]] = None):
    pkeys = _param_keys(results)
    space = next(iter(results.values())).inference.space
    lines = ["=" * 74,
             "Virtual self-driving laboratory - final campaign report",
             "=" * 74, ""]
    if headline:
        lines += list(headline) + ["=" * 74, ""]
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
