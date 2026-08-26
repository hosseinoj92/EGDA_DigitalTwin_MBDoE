"""
Benchmark figures: the visual half of the run-level summary.

Every function is a PURE FUNCTION OF THE EXPORTED TABLES - the row
dictionaries `benchmark_export.py`, `efficiency.py`, `audit_summary.py` and
`audit_export.py` produce, which are also what the CSVs contain.  Nothing
here re-runs a campaign, re-fits a posterior or draws a random number, so a
figure cannot disagree with the table next to it and the tables stay
authoritative.

Each builder returns the path it wrote or None when the run has nothing
meaningful to draw - a scenario with one candidate model has no
discrimination figure, a direct-observation scenario has no NMR figure, a
run without a transfer log has no transport decomposition.  Returning None
rather than an empty axis is deliberate: a blank panel in a report reads as
a result.

Truth-derived quantities (parameter error, blind RMSE, coverage, the
transport decomposition) are post-campaign validation of a simulation and
are labelled as such wherever they appear.

Layout note: the caller passes an explicit path, so the figures/<topic>/
tree is the runner's decision, not this module's.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .campaign_figures import _PALETTE, _int_xaxis, color_for
from .reporting import _save

SPECIES_COLOR = {"EGDA": "#1b3a5c", "EGMA": "#2a7f62", "EG": "#a23b2e",
                 "AcOH": "#8c5a2b", "H2O": "#5b7fbc"}

PARAM_LABEL = {"k1_ref": r"$k_{1,ref}$", "Ea1_J": r"$E_{a1}$",
               "k2_ref": r"$k_{2,ref}$", "Ea2_J": r"$E_{a2}$",
               "K1_ref": r"$K_1$", "K2_ref": r"$K_2$"}

#: relative CI widths above this come from a rank-deficient information
#: matrix, not from a measurement; the benchmark clamps its own
#: `max_rel_ci_pct` at the same value
CI_CLIP_PCT = 1.0e4


def _num(row: Dict, key: str, default=np.nan) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _order(rows: Sequence[Dict], key: str) -> List[str]:
    """Distinct values in FIRST-SEEN order - deterministic, and it keeps the
    scenario order the run actually used instead of alphabetising S10 before
    S2."""
    seen: List[str] = []
    for r in rows:
        v = str(r.get(key, ""))
        if v and v not in seen:
            seen.append(v)
    return seen


def _finish(fig, path: str, note: str = "") -> str:
    try:
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    except Exception:                                   # pragma: no cover
        pass
    if note:
        fig.text(0.005, -0.015, note, fontsize=7, color="#666666",
                 ha="left", va="top")
    return _save(fig, path)


def _short(scen: str) -> str:
    """S3ab_delay -> S3ab; a tick label, not a description."""
    return str(scen).split("_")[0]


# ------------------------------------------------------------------------- #
# 1. overview: the scenario x strategy matrix
# ------------------------------------------------------------------------- #
def figure_matrix(matrix_rows: Sequence[Dict], metric: str, path: str,
                  log_scale: bool = False) -> Optional[str]:
    """One metric across every scenario and strategy that ran.

    Cells that never ran are left blank rather than zero-filled: a strategy
    a scenario does not define is not a strategy that scored zero."""
    sel = [r for r in matrix_rows if r["metric"] == metric]
    if not sel or not any(int(_num(r, "defined", 0)) for r in sel):
        return None
    scen = _order(sel, "scenario")
    strat = sorted({str(r["strategy"]) for r in sel})
    M = np.full((len(strat), len(scen)), np.nan)
    for r in sel:
        if int(_num(r, "defined", 0)):
            M[strat.index(str(r["strategy"])),
              scen.index(str(r["scenario"]))] = _num(r, "value")
    lower = bool(int(_num(sel[0], "lower_is_better", 1)))
    label = str(sel[0].get("metric_label", metric))
    finite = M[np.isfinite(M)]
    if not finite.size:
        return None
    fig, ax = plt.subplots(figsize=(1.15 * len(scen) + 3.4,
                                    0.52 * len(strat) + 2.6))
    plot = M.copy()
    if log_scale and np.all(finite > 0):
        plot = np.log10(plot)
    cmap = "RdYlGn_r" if lower else "RdYlGn"
    im = ax.imshow(plot, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(scen)))
    ax.set_xticklabels([_short(s) for s in scen], fontsize=9)
    ax.set_yticks(range(len(strat)))
    ax.set_yticklabels(strat, fontsize=9)
    for i in range(len(strat)):
        for j in range(len(scen)):
            v = M[i, j]
            if not np.isfinite(v):
                ax.text(j, i, "-", ha="center", va="center", fontsize=8,
                        color="#999999")
                continue
            txt = (f"{v:.3g}" if abs(v) < 1e4 and abs(v) >= 1e-3
                   else (f"{v:.2e}" if v else "0"))
            ax.text(j, i, txt, ha="center", va="center", fontsize=7.5,
                    color="#111111")
    ax.set_xlabel("scenario")
    ax.set_ylabel("strategy")
    ax.set_title(label + ("  (lower is better)" if lower
                          else "  (higher is better)"), fontsize=11)
    fig.colorbar(im, ax=ax, shrink=0.85,
                 label=("log10 " + label) if log_scale and np.all(finite > 0)
                 else label)
    return _finish(fig, path,
                   "blank cell = the scenario does not define that strategy.")


def figure_overview_accuracy(master: Sequence[Dict], path: str
                             ) -> Optional[str]:
    """Final accuracy per scenario and strategy, with the IQR, the number of
    campaigns behind each bar, and the completion rate above it.

    Accuracy and completion are drawn on the SAME figure on purpose: a
    median error from campaigns that mostly paused is not comparable with
    one from campaigns that all finished, and separating the two panels is
    how that comparison gets made by accident."""
    if not master:
        return None
    scen = _order(master, "scenario")
    strat = sorted({str(r["strategy"]) for r in master})
    fig, axes = plt.subplots(3, 1, figsize=(max(1.9 * len(scen), 8.0), 9.5),
                             sharex=True)
    width = 0.8 / max(len(strat), 1)
    panels = (("param_err_pct", "median parameter error / %", True),
              ("blind_rmse_M", "median blind RMSE / M", True))
    for ax, (key, label, logy) in zip(axes[:2], panels):
        for i, s in enumerate(strat):
            x, y, lo, hi = [], [], [], []
            for j, sc in enumerate(scen):
                r = next((q for q in master if q["scenario"] == sc
                          and q["strategy"] == s), None)
                if r is None or not np.isfinite(_num(r, f"{key}_median")):
                    continue
                x.append(j + (i - (len(strat) - 1) / 2.0) * width)
                y.append(_num(r, f"{key}_median"))
                lo.append(max(_num(r, f"{key}_median")
                              - _num(r, f"{key}_q25"), 0.0))
                hi.append(max(_num(r, f"{key}_q75")
                              - _num(r, f"{key}_median"), 0.0))
            if not x:
                continue
            ax.bar(x, y, width * 0.9, color=color_for(s, strat), label=s,
                   yerr=[lo, hi], capsize=2,
                   error_kw={"lw": 0.8, "ecolor": "#444444"})
        if logy and all(v > 0 for v in
                        [_num(r, f"{key}_median") for r in master
                         if np.isfinite(_num(r, f"{key}_median"))]):
            ax.set_yscale("log")
        ax.set_ylabel(label, fontsize=9)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
    ax = axes[2]
    for i, s in enumerate(strat):
        x, y = [], []
        for j, sc in enumerate(scen):
            r = next((q for q in master if q["scenario"] == sc
                      and q["strategy"] == s), None)
            if r is None or not np.isfinite(_num(r, "completion_rate")):
                continue
            x.append(j + (i - (len(strat) - 1) / 2.0) * width)
            y.append(_num(r, "completion_rate"))
        if x:
            ax.bar(x, y, width * 0.9, color=color_for(s, strat), label=s)
    ax.axhline(1.0, color="0.5", ls="--", lw=0.8)
    ax.set_ylim(0.0, 1.12)
    ax.set_ylabel("campaign completion rate", fontsize=9)
    ax.set_xticks(range(len(scen)))
    ax.set_xticklabels([_short(s) for s in scen], fontsize=9)
    ax.grid(alpha=0.2, lw=0.5, axis="y")
    axes[0].legend(fontsize=8, frameon=False, ncol=min(len(strat), 6),
                   title="strategy", title_fontsize=8)
    fig.suptitle("Benchmark overview: final accuracy (median, IQR) and "
                 "campaign completion")
    return _finish(fig, path,
                   "accuracy panels use the hidden truth: post-campaign "
                   "validation of a simulation.")


# ------------------------------------------------------------------------- #
# 2. paired-seed comparisons (common random numbers)
# ------------------------------------------------------------------------- #
def figure_paired_seeds(paired: Sequence[Dict], summary: Sequence[Dict],
                        scenario: str, path: str,
                        metrics: Sequence[str] = ("param_err_pct",
                                                  "blind_rmse_M", "time_s",
                                                  "egda_mol",
                                                  "nmr_acquisitions")
                        ) -> Optional[str]:
    """EVERY seed's paired difference against the scenario's reference.

    The columns are metrics, the rows are strategies, and each panel shows
    one dot per seed with the median and its bootstrap CI.  Aggregates alone
    cannot separate "wins on nearly every seed" from "loses on most seeds
    and is rescued by two spectacular ones", and that distinction is the
    whole reason the benchmark spends common random numbers."""
    sel = [r for r in paired if r["scenario"] == scenario
           and r["metric"] in metrics]
    if not sel:
        return None
    strats = sorted({str(r["strategy"]) for r in sel})
    mets = [m for m in metrics if any(r["metric"] == m for r in sel)]
    fig, axes = plt.subplots(len(strats), len(mets), squeeze=False,
                             figsize=(3.0 * len(mets), 2.6 * len(strats)))
    ref = str(sel[0]["reference_strategy"])
    for i, s in enumerate(strats):
        for j, m in enumerate(mets):
            ax = axes[i][j]
            rr = [r for r in sel if r["strategy"] == s and r["metric"] == m]
            if not rr:
                ax.set_axis_off()
                continue
            d = np.array([_num(r, "difference") for r in rr])
            seeds = np.array([_num(r, "seed") for r in rr])
            wins = d < 0.0 if int(_num(rr[0], "lower_is_better", 1)) \
                else d > 0.0
            ax.axhline(0.0, color="0.4", lw=0.9)
            ax.scatter(seeds[wins], d[wins], s=18, color="#2a7f62",
                       label="strategy better", zorder=3)
            ax.scatter(seeds[~wins], d[~wins], s=18, color="#a23b2e",
                       label="reference better", zorder=3)
            sm = next((q for q in summary if q["scenario"] == scenario
                       and q["strategy"] == s and q["metric"] == m), None)
            if sm is not None:
                n_pairs = int(_num(sm, "n_pairs", 0))
                med = _num(sm, "difference_median")
                lo, hi = (_num(sm, "difference_ci_lo"),
                          _num(sm, "difference_ci_hi"))
                ax.axhline(med, color="#1b3a5c", lw=1.4)
                if n_pairs >= 2 and np.isfinite(lo) and np.isfinite(hi):
                    ax.axhspan(lo, hi, color="#1b3a5c", alpha=0.12, lw=0)
                ax.set_title(f"{m}\nwin {100 * _num(sm, 'win_fraction'):.0f}%"
                             f"  n={n_pairs}"
                             + ("  CI excl. 0"
                                if int(_num(sm, "ci_excludes_zero", 0))
                                else ("  (no CI: 1 pair)" if n_pairs < 2
                                      else "")), fontsize=8)
            _int_xaxis(ax)
            if j == 0:
                ax.set_ylabel(f"{s} - {ref}", fontsize=9)
            if i == len(strats) - 1:
                ax.set_xlabel("seed", fontsize=8)
            ax.grid(alpha=0.2, lw=0.5)
            ax.tick_params(labelsize=7)
    axes[0][0].legend(fontsize=6, frameon=False)
    fig.suptitle(f"Paired per-seed differences vs {ref} - {scenario} "
                 f"(common random numbers)")
    return _finish(fig, path,
                   "each dot is ONE seed measured under identical random "
                   "draws; line = median difference, band = bootstrap 95% CI.")


# ------------------------------------------------------------------------- #
# 3. parameter-by-parameter performance
# ------------------------------------------------------------------------- #
def figure_parameter_performance(pp_rows: Sequence[Dict], scenario: str,
                                 path: str) -> Optional[str]:
    """Per-parameter accuracy, precision, coverage and bound-hit rate.

    The aggregate `param_err_pct` is a geometric mean over parameters and
    can sit comfortably in single digits while one parameter is completely
    unidentified.  This figure is what makes that visible."""
    sel = [r for r in pp_rows if r["scenario"] == scenario]
    if not sel:
        return None
    params = _order(sel, "param")
    strats = sorted({str(r["strategy"]) for r in sel})
    panels = (("abs_rel_error_pct_median", "median |rel. error| / %", True),
              ("rel_ci95_width_pct_median", "median 95% CI width / %", True),
              ("ci95_coverage", "empirical 95% coverage", False),
              ("frac_bound_active", "fraction resting on a bound", False))
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.2))
    width = 0.8 / max(len(strats), 1)
    for ax, (key, label, logy) in zip(axes.ravel(), panels):
        for i, s in enumerate(strats):
            x, y = [], []
            for j, p in enumerate(params):
                r = next((q for q in sel if q["strategy"] == s
                          and q["param"] == p), None)
                v = _num(r, key) if r else np.nan
                if key.endswith("width_pct_median") and np.isfinite(v):
                    v = min(v, CI_CLIP_PCT)
                if not np.isfinite(v):
                    continue
                x.append(j + (i - (len(strats) - 1) / 2.0) * width)
                y.append(v)
            if x:
                ax.bar(x, y, width * 0.9, color=color_for(s, strats),
                       label=s)
        if key == "ci95_coverage":
            ax.axhline(0.95, color="#a23b2e", ls="--", lw=1.0)
            ax.annotate("nominal 0.95", (0.01, 0.96),
                        xycoords=("axes fraction", "data"), fontsize=7,
                        color="#a23b2e")
            ax.set_ylim(0.0, 1.08)
        if logy:
            vals = [_num(r, key) for r in sel if np.isfinite(_num(r, key))]
            if vals and all(v > 0 for v in vals):
                ax.set_yscale("log")
        ax.set_xticks(range(len(params)))
        ax.set_xticklabels([PARAM_LABEL.get(p, p) for p in params],
                           fontsize=9)
        ax.set_ylabel(label, fontsize=9)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
    axes[0][0].legend(fontsize=7, frameon=False, ncol=min(len(strats), 4),
                      title="strategy", title_fontsize=7)
    fig.suptitle(f"Parameter-by-parameter performance - {scenario}")
    return _finish(fig, path,
                   "error and coverage use the hidden truth: post-campaign "
                   "validation only. CI widths are clipped at "
                   f"{CI_CLIP_PCT:.0g} %.")


def figure_precision_vs_accuracy(pp_rows: Sequence[Dict], path: str
                                 ) -> Optional[str]:
    """Interval width against realized error, per parameter.

    A method can be PRECISE AND WRONG.  On these axes that failure is a
    point far to the right of the diagonal - a small reported interval next
    to a large actual error - and it is invisible in any single-number
    summary.  Points near the diagonal have intervals that match their
    errors, which is what a calibrated posterior looks like."""
    sel = [r for r in pp_rows
           if np.isfinite(_num(r, "abs_rel_error_pct_median"))
           and np.isfinite(_num(r, "rel_ci95_width_pct_median"))]
    if not sel:
        return None
    params = _order(sel, "param")
    strats = sorted({str(r["strategy"]) for r in sel})
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    for r in sel:
        p, s = str(r["param"]), str(r["strategy"])
        x = min(_num(r, "rel_ci95_width_pct_median"), CI_CLIP_PCT)
        y = _num(r, "abs_rel_error_pct_median")
        ax.scatter(x, y, s=46, color=color_for(s, strats),
                   marker=("o", "s", "^", "D", "v", "P")[
                       params.index(p) % 6],
                   alpha=0.85, edgecolors="none")
    lim = [min([_num(r, "abs_rel_error_pct_median") for r in sel]
               + [min(_num(r, "rel_ci95_width_pct_median"), CI_CLIP_PCT)
                  for r in sel]) * 0.5,
           max([_num(r, "abs_rel_error_pct_median") for r in sel]
               + [min(_num(r, "rel_ci95_width_pct_median"), CI_CLIP_PCT)
                  for r in sel]) * 2.0]
    lim[0] = max(lim[0], 1e-3)
    ax.plot(lim, lim, "k--", lw=0.9)
    ax.annotate("error = reported interval", (lim[1], lim[1]), fontsize=7,
                ha="right", va="bottom", color="#444444")
    # ABOVE the diagonal the realized error exceeds the interval that was
    # reported for it - that is the "precise but wrong" quadrant, and it is
    # upper-LEFT, not upper-right
    ax.annotate("over-confident:\nerror > reported interval",
                (lim[0] * 3.0, lim[1] * 0.4), fontsize=8, color="#a23b2e",
                ha="left", va="top")
    ax.annotate("conservative:\ninterval > error",
                (lim[1] * 0.6, lim[0] * 3.0), fontsize=8, color="#2a7f62",
                ha="right", va="bottom")
    if any(min(_num(r, "rel_ci95_width_pct_median"), CI_CLIP_PCT)
           >= CI_CLIP_PCT for r in sel):
        ax.axvline(CI_CLIP_PCT, color="#888888", ls=":", lw=1.0)
        ax.annotate(f"clipped at {CI_CLIP_PCT:.0g} %", (CI_CLIP_PCT, lim[0]),
                    rotation=90, fontsize=6.5, color="#888888",
                    ha="right", va="bottom")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_xlabel("median reported 95% CI width / %")
    ax.set_ylabel("median realized |relative error| / %")
    ax.grid(alpha=0.25, lw=0.5, which="both")
    handles = [plt.Line2D([], [], ls="", marker="o", color=color_for(s, strats),
                          label=s) for s in strats]
    handles += [plt.Line2D([], [], ls="", marker=("o", "s", "^", "D", "v",
                                                  "P")[i % 6], color="0.4",
                           label=PARAM_LABEL.get(p, p))
                for i, p in enumerate(params)]
    ax.legend(handles=handles, fontsize=7, frameon=False, ncol=2,
              loc="lower right")
    fig.suptitle("Is the reported uncertainty honest? "
                 "(all scenarios pooled)")
    return _finish(fig, path,
                   "one point per (scenario, strategy, parameter); intervals "
                   f"wider than {CI_CLIP_PCT:.0g} % are clipped and mark a "
                   "parameter that was not determined at all.")


def figure_parameter_bands(prows: Sequence[Dict], scenario: str,
                           strategy: str, path: str,
                           x_key: str = "round",
                           x_label: str = "campaign round",
                           rows: Sequence[Dict] = ()) -> Optional[str]:
    """Across-seed convergence of every parameter, against round,
    acquisitions or campaign time.

    Two bands are drawn and they mean different things: the SPREAD OF THE
    ESTIMATES across seeds (how repeatable the method is) and the median
    REPORTED interval (how uncertain it says it is).  A method whose
    estimates scatter far more widely than its own intervals is
    over-confident, and only plotting both shows it."""
    sel = [r for r in prows if r["scenario"] == scenario
           and r["strategy"] == strategy]
    if not sel:
        return None
    params = _order(sel, "param")
    # x axis: round, or a cumulative resource carried on the ROUND rows
    xmap: Dict[Tuple[int, int], float] = {}
    if x_key != "round":
        for r in rows:
            if r["scenario"] == scenario and r["strategy"] == strategy:
                xmap[(int(_num(r, "seed")), int(_num(r, "round")))] = \
                    _num(r, x_key)
        if not xmap:
            return None
    ncol = min(3, len(params))
    nrow = int(np.ceil(len(params) / ncol))
    fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                             figsize=(4.4 * ncol, 3.1 * nrow))
    for q, p in enumerate(params):
        ax = axes[q // ncol][q % ncol]
        pr = [r for r in sel if r["param"] == p]
        rounds = sorted({int(_num(r, "round")) for r in pr})
        xs, med, lo, hi, ci_lo, ci_hi = [], [], [], [], [], []
        for rnd in rounds:
            rr = [r for r in pr if int(_num(r, "round")) == rnd]
            est = np.array([_num(r, "estimate") for r in rr])
            est = est[np.isfinite(est)]
            if not est.size:
                continue
            if x_key == "round":
                xs.append(float(rnd))
            else:
                xv = np.array([xmap.get((int(_num(r, "seed")), rnd), np.nan)
                               for r in rr])
                xv = xv[np.isfinite(xv)]
                if not xv.size:
                    continue
                xs.append(float(np.median(xv)))
            med.append(float(np.median(est)))
            lo.append(float(np.quantile(est, 0.25)))
            hi.append(float(np.quantile(est, 0.75)))
            cl = np.array([_num(r, "ci_lo") for r in rr])
            ch = np.array([_num(r, "ci_hi") for r in rr])
            cl, ch = cl[np.isfinite(cl)], ch[np.isfinite(ch)]
            ci_lo.append(float(np.median(cl)) if cl.size else np.nan)
            ci_hi.append(float(np.median(ch)) if ch.size else np.nan)
        if not xs:
            ax.set_axis_off()
            continue
        ax.fill_between(xs, ci_lo, ci_hi, color="#8a8a8a", alpha=0.18, lw=0,
                        label="median reported 95% CI")
        ax.fill_between(xs, lo, hi, color="#1b3a5c", alpha=0.28, lw=0,
                        label="IQR of estimates across seeds")
        ax.plot(xs, med, "-o", ms=4, lw=1.5, color="#1b3a5c",
                label="median estimate")
        tv = np.array([_num(r, "true_value") for r in pr])
        tv = tv[np.isfinite(tv)]
        if tv.size:
            ax.axhline(float(tv[0]), color="#a23b2e", ls="--", lw=1.1,
                       label="hidden truth")
        seen = [v for v in med + list(tv[:1]) if np.isfinite(v)]
        if seen:
            if p in ("k1_ref", "k2_ref") and min(seen) > 0:
                ax.set_yscale("log")
                ax.set_ylim(min(seen) / 4.0, max(seen) * 4.0)
            else:
                pad = max((max(seen) - min(seen)) * 0.6,
                          abs(max(seen)) * 0.15, 1e-9)
                ax.set_ylim(min(seen) - pad, max(seen) + pad)
        ax.set_title(PARAM_LABEL.get(p, p), fontsize=10)
        ax.set_xlabel(x_label, fontsize=8)
        ax.grid(alpha=0.25, lw=0.5)
        if x_key == "round":
            _int_xaxis(ax)
    for q in range(len(params), nrow * ncol):
        axes[q // ncol][q % ncol].set_axis_off()
    axes[0][0].legend(fontsize=6.5, frameon=False)
    fig.suptitle(f"Parameter convergence across seeds - {scenario} / "
                 f"{strategy}")
    return _finish(fig, path,
                   "dark band = spread of the ESTIMATES (repeatability); "
                   "grey band = the median interval the method REPORTED; "
                   "truth line is post-campaign validation only.")


# ------------------------------------------------------------------------- #
# 4. where the algorithms choose to experiment
# ------------------------------------------------------------------------- #
def figure_design_distribution(dist_rows: Sequence[Dict], scenario: str,
                               path: str) -> Optional[str]:
    """Where each strategy repeatedly chooses to collect information.

    Bins are shared across strategies within a scenario, so the histograms
    are directly comparable - which is the only reason to draw them
    together."""
    sel = [r for r in dist_rows if r["scenario"] == scenario]
    if not sel:
        return None
    variables = _order(sel, "variable")
    strats = sorted({str(r["strategy"]) for r in sel})
    ncol = min(3, len(variables))
    nrow = int(np.ceil(len(variables) / ncol))
    fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                             figsize=(4.4 * ncol, 3.0 * nrow))
    for q, var in enumerate(variables):
        ax = axes[q // ncol][q % ncol]
        vr = [r for r in sel if r["variable"] == var]
        unit = str(vr[0].get("unit", ""))
        centers = sorted({_num(r, "bin_center") for r in vr})
        w = ((centers[1] - centers[0]) * 0.8 / max(len(strats), 1)
             if len(centers) > 1 else 0.5)
        for i, s in enumerate(strats):
            sr = sorted((r for r in vr if r["strategy"] == s),
                        key=lambda r: _num(r, "bin_center"))
            if not sr:
                continue
            x = np.array([_num(r, "bin_center") for r in sr])
            y = np.array([_num(r, "fraction") for r in sr])
            ax.bar(x + (i - (len(strats) - 1) / 2.0) * w, y, w * 0.92,
                   color=color_for(s, strats), alpha=0.85, label=s)
        ax.set_xlabel(f"{var} / {unit}" if unit else var, fontsize=8)
        ax.set_ylabel("fraction of selections", fontsize=8)
        ax.set_title(f"{var}  ({vr[0].get('weighting', '')})", fontsize=8.5)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
        ax.tick_params(labelsize=8)
    for q in range(len(variables), nrow * ncol):
        axes[q // ncol][q % ncol].set_axis_off()
    axes[0][0].legend(fontsize=7, frameon=False, ncol=min(len(strats), 3),
                      title="strategy", title_fontsize=7)
    fig.suptitle(f"Selected experimental design - {scenario}")
    return _finish(fig, path,
                   "operating conditions are counted once per reactor "
                   "condition; axial positions once per acquisition.")


def figure_design_joint(design_rows: Sequence[Dict], scenario: str,
                        path: str,
                        pairs: Sequence[Tuple[str, str]] = (
                            ("T_C", "Q_total_mL_min"),
                            ("T_C", "C_cat_M"))) -> Optional[str]:
    """Joint design-space occupancy: does the method concentrate on a
    particular REGION, not just a particular marginal?

    Two marginals can look identical while one method visits hot-and-slow
    and the other hot-and-fast - a difference the joint plot shows and the
    histograms cannot."""
    sel = [r for r in design_rows if r["scenario"] == scenario]
    if not sel:
        return None
    # de-duplicate to one point per (seed, round): the CONDITION, not the
    # acquisition, or a ten-position profile would count ten times
    seen: Dict[Tuple, Dict] = {}
    for r in sel:
        seen.setdefault((str(r["strategy"]), int(_num(r, "seed")),
                         int(_num(r, "round"))), r)
    conds = list(seen.values())
    strats = sorted({str(r["strategy"]) for r in conds})
    pairs = [p for p in pairs
             if any(np.isfinite(_num(r, p[0])) and np.isfinite(_num(r, p[1]))
                    for r in conds)]
    if not pairs:
        return None
    fig, axes = plt.subplots(len(pairs), len(strats), squeeze=False,
                             figsize=(3.1 * len(strats), 2.9 * len(pairs)))
    for i, (xk, yk) in enumerate(pairs):
        xs = np.array([_num(r, xk) for r in conds])
        ys = np.array([_num(r, yk) for r in conds])
        good = np.isfinite(xs) & np.isfinite(ys)
        xlim = ((float(np.min(xs[good])), float(np.max(xs[good])))
                if good.any() else (0.0, 1.0))
        ylim = ((float(np.min(ys[good])), float(np.max(ys[good])))
                if good.any() else (0.0, 1.0))
        for j, s in enumerate(strats):
            ax = axes[i][j]
            rr = [r for r in conds if r["strategy"] == s]
            x = np.array([_num(r, xk) for r in rr])
            y = np.array([_num(r, yk) for r in rr])
            m = np.isfinite(x) & np.isfinite(y)
            if m.any():
                rounds = np.array([_num(r, "round") for r in rr])[m]
                sc = ax.scatter(x[m], y[m], c=rounds, cmap="viridis", s=22,
                                alpha=0.75, edgecolors="none")
                if i == 0 and j == len(strats) - 1:
                    fig.colorbar(sc, ax=ax, shrink=0.85, label="round")
            ax.set_xlim(xlim[0] - 0.04 * (xlim[1] - xlim[0] or 1),
                        xlim[1] + 0.04 * (xlim[1] - xlim[0] or 1))
            ax.set_ylim(ylim[0] - 0.06 * (ylim[1] - ylim[0] or 1),
                        ylim[1] + 0.06 * (ylim[1] - ylim[0] or 1))
            if i == 0:
                ax.set_title(f"strategy {s}", fontsize=9)
            if j == 0:
                ax.set_ylabel(yk, fontsize=8)
            ax.set_xlabel(xk, fontsize=8)
            ax.grid(alpha=0.2, lw=0.5)
            ax.tick_params(labelsize=7)
    fig.suptitle(f"Joint design-space occupancy - {scenario} "
                 f"(one point per reactor condition, coloured by round)")
    return _finish(fig, path)


def figure_spatial_density(dist_rows: Sequence[Dict], scenario: str,
                           path: str) -> Optional[str]:
    """Axial sampling density along the reactor, per strategy."""
    sel = [r for r in dist_rows if r["scenario"] == scenario
           and r["variable"] == "z_over_L"]
    if not sel:
        return None
    strats = sorted({str(r["strategy"]) for r in sel})
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    for s in strats:
        sr = sorted((r for r in sel if r["strategy"] == s),
                    key=lambda r: _num(r, "bin_center"))
        if not sr:
            continue
        x = [_num(r, "bin_center") for r in sr]
        y = [_num(r, "fraction") for r in sr]
        ax.plot(x, y, "-o", ms=4, lw=1.6, color=color_for(s, strats),
                label=f"{s}  (median z/L {_num(sr[0], 'median_selected'):.2f})")
        ax.fill_between(x, 0, y, color=color_for(s, strats), alpha=0.12, lw=0)
    ax.set_xlabel("axial position  z / L")
    ax.set_ylabel("fraction of acquisitions")
    ax.grid(alpha=0.25, lw=0.5)
    ax.legend(fontsize=8, frameon=False)
    fig.suptitle(f"Where the capillary sampled - {scenario}")
    return _finish(fig, path)


def figure_design_by_round(by_round: Sequence[Dict], scenario: str,
                           path: str) -> Optional[str]:
    """Selected design variables against round: does the policy MOVE?"""
    sel = [r for r in by_round if r["scenario"] == scenario]
    if not sel:
        return None
    strats = sorted({str(r["strategy"]) for r in sel})
    panels = (("T_C", "temperature / degC"),
              ("Q_total_mL_min", "total flow / mL/min"),
              ("C_cat_M", "catalyst / M"),
              ("z_over_L", "axial position z / L"))
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 6.6), sharex=True)
    for ax, (var, label) in zip(axes.ravel(), panels):
        for s in strats:
            rr = sorted((r for r in sel if r["strategy"] == s),
                        key=lambda r: _num(r, "round"))
            x = [_num(r, "round") for r in rr]
            m = [_num(r, f"{var}_median") for r in rr]
            lo = [_num(r, f"{var}_q25") for r in rr]
            hi = [_num(r, f"{var}_q75") for r in rr]
            if not any(np.isfinite(v) for v in m):
                continue
            c = color_for(s, strats)
            ax.fill_between(x, lo, hi, color=c, alpha=0.15, lw=0)
            ax.plot(x, m, "-o", ms=4, lw=1.5, color=c, label=s)
        ax.set_ylabel(label, fontsize=9)
        ax.grid(alpha=0.2, lw=0.5)
        _int_xaxis(ax)
    for ax in axes[1]:
        ax.set_xlabel("campaign round")
    axes[0][0].legend(fontsize=8, frameon=False, title="strategy",
                      title_fontsize=8)
    fig.suptitle(f"Selected design vs round (median and IQR across seeds) - "
                 f"{scenario}")
    return _finish(fig, path)


# ------------------------------------------------------------------------- #
# 5. measurement system
# ------------------------------------------------------------------------- #
def figure_nmr_performance(nmr_summary: Sequence[Dict], path: str,
                           scenario: Optional[str] = None) -> Optional[str]:
    """Quantification behaviour by species and concentration regime.

    Reported uncertainty, relative uncertainty, QC failure and censoring, in
    the regimes the deconvolution actually meets.  The bias and coverage
    against KNOWN compositions live in the quantification-validation figure;
    they cannot be computed here, because a campaign spectrum has no truth
    attached to it."""
    sel = [r for r in nmr_summary
           if scenario is None or r["scenario"] == scenario]
    if not sel:
        return None
    species = _order(sel, "species")
    bins = _order(sel, "concentration_bin")
    panels = (("median_sigma_M", "median reported sigma / M", True),
              ("median_relative_sigma", "median sigma / concentration", True),
              ("qc_fail_rate", "QC failure rate", False),
              ("censored_rate", "non-negativity censoring rate", False))
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 7.0))
    width = 0.8 / max(len(species), 1)
    for ax, (key, label, logy) in zip(axes.ravel(), panels):
        for i, sp in enumerate(species):
            x, y = [], []
            for j, b in enumerate(bins):
                rr = [r for r in sel if r["species"] == sp
                      and r["concentration_bin"] == b]
                v = np.array([_num(r, key) for r in rr])
                v = v[np.isfinite(v)]
                if not v.size:
                    continue
                x.append(j + (i - (len(species) - 1) / 2.0) * width)
                y.append(float(np.median(v)))
            if x:
                ax.bar(x, y, width * 0.9,
                       color=SPECIES_COLOR.get(sp, "#888888"), label=sp)
        if logy and any(v > 0 for v in y or [0]):
            try:
                ax.set_yscale("log")
            except ValueError:                          # pragma: no cover
                pass
        ax.set_xticks(range(len(bins)))
        ax.set_xticklabels(bins, fontsize=7, rotation=20, ha="right")
        ax.set_ylabel(label, fontsize=9)
        ax.set_xlabel("fitted concentration regime", fontsize=8)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
    axes[0][0].legend(fontsize=7, frameon=False, ncol=2)
    fig.suptitle("NMR quantification behaviour by species and concentration"
                 + (f" - {scenario}" if scenario else " (all scenarios)"))
    return _finish(fig, path,
                   "no truth is available for a campaign spectrum: these are "
                   "the REPORTED uncertainties and the QC outcomes.")


def figure_quantification_validation(qv_rows: Sequence[Dict], path: str
                                     ) -> Optional[str]:
    """Bias, RMSE and interval coverage of the NMR pathway against KNOWN
    compositions, per validation suite.

    This is the measurement system's own validation, run outside any
    campaign, and it is the only place a measured bias can be quoted."""
    if not qv_rows:
        return None
    suites = _order(qv_rows, "suite")
    species = _order(qv_rows, "species")
    panels = (("bias_mM", "bias / mM", None),
              ("rmse_mM", "RMSE / mM", None),
              ("coverage95", "95% interval coverage", 0.95))
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.4))
    width = 0.8 / max(len(suites), 1)
    for ax, (key, label, ref) in zip(axes, panels):
        for i, su in enumerate(suites):
            x, y = [], []
            for j, sp in enumerate(species):
                r = next((q for q in qv_rows if q["suite"] == su
                          and q["species"] == sp), None)
                v = _num(r, key) if r else np.nan
                if not np.isfinite(v):
                    continue
                x.append(j + (i - (len(suites) - 1) / 2.0) * width)
                y.append(v)
            if x:
                ax.bar(x, y, width * 0.9,
                       color=_PALETTE[i % len(_PALETTE)], label=su)
        if ref is not None:
            ax.axhline(ref, color="#a23b2e", ls="--", lw=1.0)
            ax.set_ylim(0.0, 1.05)
        else:
            ax.axhline(0.0, color="0.5", lw=0.8)
        ax.set_xticks(range(len(species)))
        ax.set_xticklabels(species, fontsize=9)
        ax.set_ylabel(label, fontsize=9)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
    axes[0].legend(fontsize=7, frameon=False)
    fig.suptitle("NMR quantification validation against prepared standards")
    return _finish(fig, path,
                   "coverage below the dashed line means the pathway reports "
                   "intervals that are too narrow for its own error.")


def figure_transfer_decomposition(trans_summary: Sequence[Dict], path: str
                                  ) -> Optional[str]:
    """Transport distortion vs quantification error, per species and
    transport scenario.

    SIMULATION VALIDATION ONLY: both intermediate compositions are
    truth-side and were read after the campaigns ended."""
    if not trans_summary:
        return None
    scen = _order(trans_summary, "scenario")
    species = _order(trans_summary, "species")
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    ax = axes[0]
    width = 0.38
    x = np.arange(len(species))
    for k, (key, label, col) in enumerate(
            (("rms_transport_delta_M", "transport", "#7a4fa3"),
             ("rms_quantification_delta_M", "quantification", "#c98a3a"))):
        vals = []
        for sp in species:
            v = np.array([_num(r, key) for r in trans_summary
                          if r["species"] == sp])
            v = v[np.isfinite(v)]
            vals.append(float(np.median(v)) if v.size else np.nan)
        ax.bar(x + (k - 0.5) * width, np.nan_to_num(vals), width,
               color=col, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels(species)
    ax.set_ylabel("RMS deviation / M")
    ax.set_title("which stage moves the number")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(alpha=0.2, lw=0.5, axis="y")

    ax = axes[1]
    width = 0.8 / max(len(scen), 1)
    for i, sc in enumerate(scen):
        y = []
        for sp in species:
            v = np.array([_num(r, "transport_share_of_total_error")
                          for r in trans_summary if r["scenario"] == sc
                          and r["species"] == sp])
            v = v[np.isfinite(v)]
            y.append(float(np.median(v)) if v.size else np.nan)
        ax.bar(x + (i - (len(scen) - 1) / 2.0) * width, np.nan_to_num(y),
               width * 0.9, color=_PALETTE[i % len(_PALETTE)],
               label=_short(sc))
    ax.axhline(0.5, color="0.4", ls="--", lw=0.9)
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(x)
    ax.set_xticklabels(species)
    ax.set_ylabel("transport share of squared error")
    ax.set_title("transport vs quantification, by scenario")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(alpha=0.2, lw=0.5, axis="y")
    fig.suptitle("Transfer-line decomposition: reactor point -> NMR cell -> "
                 "reported concentration")
    return _finish(fig, path,
                   "above the dashed line transport dominates; below it the "
                   "deconvolution does. Post-campaign validation only.")


def figure_transfer_ablation_ladder(effect_rows: Sequence[Dict], path: str
                                    ) -> Optional[str]:
    """The transport ablation ladder: what each effect costs in accuracy."""
    if not effect_rows:
        return None
    scen = _order(effect_rows, "scenario")
    strats = sorted({str(r["strategy"]) for r in effect_rows})
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.4))
    width = 0.8 / max(len(strats), 1)
    for ax, (key, label, logy) in zip(
            axes, (("median_blind_rmse_M", "median blind RMSE / M", True),
                   ("median_param_err_pct", "median parameter error / %",
                    True))):
        for i, s in enumerate(strats):
            x, y = [], []
            for j, sc in enumerate(scen):
                r = next((q for q in effect_rows if q["scenario"] == sc
                          and q["strategy"] == s), None)
                v = _num(r, key) if r else np.nan
                if not np.isfinite(v):
                    continue
                x.append(j + (i - (len(strats) - 1) / 2.0) * width)
                y.append(v)
            if x:
                ax.bar(x, y, width * 0.9, color=color_for(s, strats),
                       label=s)
        if logy:
            vals = [_num(r, key) for r in effect_rows
                    if np.isfinite(_num(r, key))]
            if vals and all(v > 0 for v in vals):
                ax.set_yscale("log")
        ax.set_xticks(range(len(scen)))
        ax.set_xticklabels([_short(s) for s in scen], fontsize=8)
        ax.set_ylabel(label, fontsize=9)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
    axes[0].legend(fontsize=8, frameon=False, title="strategy",
                   title_fontsize=8)
    fig.suptitle("Transport ablation ladder: accuracy as transfer-line "
                 "effects are switched on")
    return _finish(fig, path,
                   "each scenario adds one transport effect to the previous "
                   "one; the gap between bars is that effect's cost.")


# ------------------------------------------------------------------------- #
# 6. robustness
# ------------------------------------------------------------------------- #
def figure_robustness_dashboard(rob_rows: Sequence[Dict], path: str
                                ) -> Optional[str]:
    """Everything that went wrong, in one place.

    Published beside the accuracy figures and never instead of them: an
    estimate from the campaigns that survived is a different claim from an
    estimate from all of them."""
    if not rob_rows:
        return None
    scen = _order(rob_rows, "scenario")
    strats = sorted({str(r["strategy"]) for r in rob_rows})
    panels = (("completion_rate", "campaign completion rate", False),
              ("measurement_fault_rate", "measurement-fault stop rate", True),
              ("qc_rejection_rate", "QC rejection rate", True),
              ("reacquisition_rate", "reacquisition rate", True),
              ("governor_inadequate_rate",
               "campaigns declaring MODEL_INADEQUATE", None),
              ("bound_hit_rate", "campaigns with a parameter on a bound",
               True),
              ("unreliable_evidence_round_rate",
               "rounds with unreliable evidence", True),
              ("undecided_rate", "campaigns ending undecided", None))
    have = [p for p in panels
            if any(np.isfinite(_num(r, p[0])) for r in rob_rows)]
    if not have:
        return None
    ncol = 2
    nrow = int(np.ceil(len(have) / ncol))
    fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                             figsize=(6.2 * ncol, 2.5 * nrow + 0.6))
    width = 0.8 / max(len(strats), 1)
    handles = None
    for q, (key, label, _lower) in enumerate(have):
        ax = axes[q // ncol][q % ncol]
        peak = 0.0
        for i, s in enumerate(strats):
            x, y = [], []
            for j, sc in enumerate(scen):
                r = next((z for z in rob_rows if z["scenario"] == sc
                          and z["strategy"] == s), None)
                v = _num(r, key) if r else np.nan
                if not np.isfinite(v):
                    continue
                x.append(j + (i - (len(strats) - 1) / 2.0) * width)
                y.append(v)
                peak = max(peak, v)
            if x:
                ax.bar(x, y, width * 0.9, color=color_for(s, strats),
                       label=s)
        # An all-zero panel is a RESULT - "this never happened" - so it is
        # drawn on a 0-anchored axis with the fact spelled out, instead of
        # matplotlib inventing a +-0.05 range around nothing.
        ax.set_ylim(0.0, max(peak * 1.2, 0.05))
        if peak <= 0.0:
            ax.annotate("none observed", (0.5, 0.5),
                        xycoords="axes fraction", ha="center", va="center",
                        fontsize=8, color="#888888")
        ax.set_xticks(range(len(scen)))
        ax.set_xticklabels([_short(s) for s in scen], fontsize=7)
        ax.set_ylabel(label, fontsize=8)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
        ax.tick_params(labelsize=7)
        if handles is None:
            handles = ax.get_legend_handles_labels()
    for q in range(len(have), nrow * ncol):
        axes[q // ncol][q % ncol].set_axis_off()
    if handles and handles[0]:
        fig.legend(*handles, fontsize=7, frameon=False,
                   ncol=min(len(strats), 8), loc="upper center",
                   bbox_to_anchor=(0.5, 0.955), title="strategy",
                   title_fontsize=7)
    fig.suptitle("Robustness and failure dashboard")
    try:
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.90))
    except Exception:                                   # pragma: no cover
        pass
    return _finish(fig, path,
                   "on a WELL-SPECIFIED scenario the MODEL_INADEQUATE rate "
                   "is a FALSE-ALARM rate; on a misspecified one it is a "
                   "detection rate. See robustness_summary.csv.")


def figure_governor_validation(gov: Dict, path: str) -> Optional[str]:
    """The governor's own Monte-Carlo validation: false alarms against its
    declared alpha, detection probability, and when detection happened."""
    if not gov:
        return None
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.0))
    ax = axes[0]
    fp = float(gov.get("false_inadequacy_campaign_rate", np.nan))
    alpha = float(gov.get("alpha_campaign_target", np.nan))
    ax.bar([0], [fp], 0.5, color="#a23b2e", label="measured false-alarm rate")
    ax.axhline(alpha, color="#1b3a5c", ls="--", lw=1.4,
               label=f"declared alpha = {alpha:g}")
    ax.set_xticks([0])
    ax.set_xticklabels(["well-specified\ncampaigns"], fontsize=8)
    ax.set_ylabel("campaign false-inadequacy rate")
    ax.set_ylim(0.0, max(fp, alpha, 0.05) * 1.5)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title(f"calibration  (n = {gov.get('n_seeds', '?')})", fontsize=9)

    ax = axes[1]
    det = float(gov.get("detection_probability", np.nan))
    ax.bar([0], [det], 0.5, color="#2a7f62")
    ax.set_xticks([0])
    ax.set_xticklabels(["misspecified\ncampaigns"], fontsize=8)
    ax.set_ylabel("detection probability")
    ax.set_ylim(0.0, 1.05)
    ax.annotate(f"{det:.2f}", (0, det), textcoords="offset points",
                xytext=(0, 4), ha="center", fontsize=9)
    ax.set_title("power", fontsize=9)

    ax = axes[2]
    rounds = [r for r in (gov.get("detection_rounds") or [])
              if r is not None]
    if rounds:
        ax.hist(rounds, bins=range(1, int(max(rounds)) + 2), align="left",
                color="#1b3a5c", rwidth=0.8)
        ax.set_xlabel("round of first MODEL_INADEQUATE")
        ax.set_ylabel("campaigns")
        _int_xaxis(ax)
        med = gov.get("median_detection_round")
        if med is not None:
            ax.axvline(float(med), color="#a23b2e", ls="--", lw=1.2,
                       label=f"median {float(med):g}")
            ax.legend(fontsize=7, frameon=False)
    else:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "no detection in the Monte-Carlo suite",
                ha="center", va="center", fontsize=9, color="#666666")
    ax.set_title("detection timing", fontsize=9)
    for a in axes:
        a.grid(alpha=0.2, lw=0.5, axis="y")
    drivers = gov.get("detection_drivers") or {}
    fig.suptitle("Model-adequacy governor: Monte-Carlo validation")
    return _finish(fig, path,
                   "detection carried by: "
                   + (", ".join(f"{k} x{v}" for k, v in sorted(
                       drivers.items())) if drivers else "nothing detected"))


# ------------------------------------------------------------------------- #
# 7. model discrimination
# ------------------------------------------------------------------------- #
def figure_model_discrimination(md_rows: Sequence[Dict], path: str
                                ) -> Optional[str]:
    """Discriminated, ambiguous, or apparently certain on unreliable
    evidence - the three outcomes kept apart.

    For a genuinely ambiguous scenario "undecided" is the CORRECT answer,
    so the figure never presents it as a failure; what it does flag is
    apparent certainty resting on an evidence computed at a box bound."""
    if not md_rows:
        return None
    labels = [f"{_short(r['scenario'])}\n{r['strategy']}" for r in md_rows]
    x = np.arange(len(md_rows))
    ok = np.array([_num(r, "decided_and_reliable_rate") for r in md_rows])
    bad = np.array([_num(r, "apparent_certainty_unreliable_rate")
                    for r in md_rows])
    und = np.array([_num(r, "undecided_rate") for r in md_rows])
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.6))
    ax = axes[0]
    ax.bar(x, np.nan_to_num(ok), 0.62, color="#2a7f62",
           label="decided, evidence reliable")
    ax.bar(x, np.nan_to_num(bad), 0.62, bottom=np.nan_to_num(ok),
           color="#c98a3a", label="decided, evidence UNRELIABLE")
    ax.bar(x, np.nan_to_num(und), 0.62,
           bottom=np.nan_to_num(ok) + np.nan_to_num(bad),
           color="#8a8a8a", label="undecided")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("fraction of campaigns")
    ax.set_ylim(0.0, 1.08)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("campaign outcome", fontsize=9)

    ax = axes[1]
    succ = np.array([_num(r, "selection_success_rate") for r in md_rows])
    ptr = np.array([_num(r, "p_tracked_model_final_median") for r in md_rows])
    w = 0.38
    ax.bar(x - w / 2, np.nan_to_num(succ), w, color="#1b3a5c",
           label="selected the tracked model")
    ax.bar(x + w / 2, np.nan_to_num(ptr), w, color="#5b7fbc",
           label="median P(tracked model)")
    for i, r in enumerate(md_rows):
        if not int(_num(r, "truth_in_candidate_family", 0)):
            ax.annotate("truth\noutside\nfamily", (i, 0.05), fontsize=6,
                        ha="center", color="#a23b2e")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylim(0.0, 1.08)
    ax.set_ylabel("fraction / probability")
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("tracked candidate", fontsize=9)
    for a in axes:
        a.grid(alpha=0.2, lw=0.5, axis="y")
    fig.suptitle("Model discrimination across seeds")
    return _finish(fig, path,
                   "where the truth is OUTSIDE the candidate family there is "
                   "no correct model, so the tracked probability is not a "
                   "success rate.")


# ------------------------------------------------------------------------- #
# 8. resources
# ------------------------------------------------------------------------- #
def figure_resource_summary(res_rows: Sequence[Dict], scenario: str,
                            path: str) -> Optional[str]:
    """What a campaign cost, per strategy, with the IQR across seeds."""
    sel = [r for r in res_rows if r["scenario"] == scenario]
    if not sel:
        return None
    strats = sorted({str(r["strategy"]) for r in sel})
    panels = (("time_s_s", "campaign time / s"),
              ("egda_mol_mol", "EGDA consumed / mol"),
              ("waste_mL_mL", "waste / mL"),
              ("energy_kJ_kJ", "energy proxy / kJ"),
              ("nmr_acquisitions_count", "NMR acquisitions"),
              ("reactor_conditions_count", "reactor conditions"),
              ("spatial_samples_count", "spatial samples"),
              ("capillary_travel_m_m", "capillary travel / m"))
    have = [p for p in panels
            if any(np.isfinite(_num(r, f"{p[0]}_median")) for r in sel)]
    if not have:
        return None
    ncol = 4
    nrow = int(np.ceil(len(have) / ncol))
    fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                             figsize=(3.2 * ncol, 2.8 * nrow))
    x = np.arange(len(strats))
    for q, (key, label) in enumerate(have):
        ax = axes[q // ncol][q % ncol]
        med = [_num(next((r for r in sel if r["strategy"] == s), None),
                    f"{key}_median") for s in strats]
        lo = [max(_num(next((r for r in sel if r["strategy"] == s), None),
                       f"{key}_median")
                  - _num(next((r for r in sel if r["strategy"] == s), None),
                         f"{key}_q25"), 0.0) for s in strats]
        hi = [max(_num(next((r for r in sel if r["strategy"] == s), None),
                       f"{key}_q75")
                  - _num(next((r for r in sel if r["strategy"] == s), None),
                         f"{key}_median"), 0.0) for s in strats]
        ax.bar(x, np.nan_to_num(med), 0.62,
               color=[color_for(s, strats) for s in strats],
               yerr=[np.nan_to_num(lo), np.nan_to_num(hi)], capsize=2,
               error_kw={"lw": 0.8, "ecolor": "#444444"})
        ax.set_xticks(x)
        ax.set_xticklabels(strats, fontsize=7.5)
        ax.set_ylabel(label, fontsize=8)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
        ax.tick_params(labelsize=7)
    for q in range(len(have), nrow * ncol):
        axes[q // ncol][q % ncol].set_axis_off()
    fig.suptitle(f"Resource consumption per campaign (median, IQR) - "
                 f"{scenario}")
    return _finish(fig, path)


def figure_resource_components(rows: Sequence[Dict], scenario: str,
                               path: str,
                               metric: str = "blind_rmse_M") -> Optional[str]:
    """Accuracy against EACH resource separately, not against one aggregate
    cost.

    A single combined cost axis hides which resource a method is actually
    trading: two strategies on the same aggregate Pareto point can differ by
    a factor of three in material while matching on time.  One panel per
    resource is what makes the trade inspectable."""
    sel = [r for r in rows if r["scenario"] == scenario]
    if not sel:
        return None
    strats = sorted({str(r["strategy"]) for r in sel})
    resources = (("time_s", "campaign time / s"),
                 ("egda_mol", "EGDA consumed / mol"),
                 ("waste_mL", "waste / mL"),
                 ("energy_kJ", "energy proxy / kJ"),
                 ("nmr_acquisitions", "NMR acquisitions"),
                 ("capillary_travel_m", "capillary travel / m"))
    have = [r for r in resources
            if any(np.isfinite(_num(q, r[0])) for q in sel)]
    if not have:
        return None
    ncol = 3
    nrow = int(np.ceil(len(have) / ncol))
    fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                             figsize=(4.2 * ncol, 3.2 * nrow))
    for q, (key, label) in enumerate(have):
        ax = axes[q // ncol][q % ncol]
        for s in strats:
            ss = [r for r in sel if r["strategy"] == s]
            rounds = sorted({int(_num(r, "round")) for r in ss})
            xs, ys = [], []
            for rnd in rounds:
                rr = [r for r in ss if int(_num(r, "round")) == rnd]
                xv = np.array([_num(r, key) for r in rr])
                yv = np.array([_num(r, metric) for r in rr])
                m = np.isfinite(xv) & np.isfinite(yv)
                if not m.any():
                    continue
                xs.append(float(np.median(xv[m])))
                ys.append(float(np.median(yv[m])))
            if xs:
                ax.plot(xs, ys, "-o", ms=4, lw=1.4,
                        color=color_for(s, strats), label=s)
        ax.set_yscale("log")
        ax.set_xlabel(label, fontsize=8)
        ax.set_ylabel(metric, fontsize=8)
        ax.grid(alpha=0.2, lw=0.5, which="both")
        ax.tick_params(labelsize=7)
    for q in range(len(have), nrow * ncol):
        axes[q // ncol][q % ncol].set_axis_off()
    axes[0][0].legend(fontsize=7, frameon=False, title="strategy",
                      title_fontsize=7)
    fig.suptitle(f"Accuracy against each resource separately - {scenario}")
    return _finish(fig, path,
                   "median across seeds at each round; the aggregate Pareto "
                   "figure collapses all of these onto one axis.")
