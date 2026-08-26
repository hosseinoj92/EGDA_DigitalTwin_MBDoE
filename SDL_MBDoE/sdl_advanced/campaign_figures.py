"""
Figures of ONE autonomous campaign.

Every function here is a PURE FUNCTION OF THE EXPORTED TABLES (the row
dictionaries `campaign_export.py` builds, which are also what the CSVs
contain) or of records the laboratory kept while it measured.  Nothing is
re-simulated, no campaign object is asked to compute anything new, and no
random number is drawn - so a figure cannot disagree with the CSV next to
it, and the CSV remains the authoritative source.

Each function returns the path it wrote, or None when the campaign has
nothing meaningful to draw: a scenario without a transfer line has no
transport decomposition, a single-model strategy has no model
probabilities, a direct-observation strategy has no spectra.  Returning
None rather than an empty axis is deliberate - an empty panel in a report
reads as a result.

Where a truth-side quantity appears (parameter convergence reference lines,
error curves, the transport decomposition) it is POST-CAMPAIGN VALIDATION of
a simulation, is labelled as such in the figure itself, and is absent from a
record built without a truth source.
"""

from __future__ import annotations

import os
import textwrap
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .reporting import STRAT_COLOR, _save

#: fallback palette for strategy keys reporting.STRAT_COLOR does not know
_PALETTE = ("#1b3a5c", "#a23b2e", "#2a7f62", "#c98a3a", "#7a4fa3",
            "#5b7fbc", "#8c5a2b", "#8a8a8a")

SPECIES_COLOR = {"EGDA": "#1b3a5c", "EGMA": "#2a7f62", "EG": "#a23b2e",
                 "AcOH": "#8c5a2b", "H2O": "#5b7fbc"}

#: printable names of the estimated parameters
PARAM_LABEL = {"k1_ref": r"$k_{1,ref}$", "Ea1_J": r"$E_{a1}$",
               "k2_ref": r"$k_{2,ref}$", "Ea2_J": r"$E_{a2}$",
               "K1_ref": r"$K_1$", "K2_ref": r"$K_2$"}

#: (divisor, axis label) for plotting - activation energies are stored in
#: J/mol and read in kJ/mol, and an axis a chemist has to divide in their
#: head is an axis that will be misread
PARAM_DISPLAY = {
    "k1_ref": (1.0, r"$k_{1,ref}$ / L mol$^{-1}$ s$^{-1}$"),
    "k2_ref": (1.0, r"$k_{2,ref}$ / L mol$^{-1}$ s$^{-1}$"),
    "Ea1_J": (1.0e3, r"$E_{a1}$ / kJ mol$^{-1}$"),
    "Ea2_J": (1.0e3, r"$E_{a2}$ / kJ mol$^{-1}$"),
    "K1_ref": (1.0, r"$K_1$ / -"),
    "K2_ref": (1.0, r"$K_2$ / -"),
}


def color_for(strategy: str, strategies: Sequence[str] = ()) -> str:
    if strategy in STRAT_COLOR:
        return STRAT_COLOR[strategy]
    idx = list(strategies).index(strategy) if strategy in strategies else 0
    return _PALETTE[idx % len(_PALETTE)]


def _num(row: Dict, key: str, default=np.nan) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _group(rows: Sequence[Dict], key: str) -> Dict[str, List[Dict]]:
    """Rows grouped by a column, in FIRST-SEEN order (deterministic)."""
    out: Dict[str, List[Dict]] = {}
    for r in rows:
        out.setdefault(str(r.get(key, "")), []).append(r)
    return out


def _strategies(rows: Sequence[Dict]) -> List[str]:
    seen: List[str] = []
    for r in rows:
        s = str(r.get("strategy", ""))
        if s and s not in seen:
            seen.append(s)
    return seen


def _series(rows: Sequence[Dict], x: str, y: str) -> Tuple[np.ndarray,
                                                           np.ndarray]:
    pts = sorted(((_num(r, x), _num(r, y)) for r in rows),
                 key=lambda t: t[0])
    if not pts:
        return np.array([]), np.array([])
    a = np.array(pts, dtype=float)
    return a[:, 0], a[:, 1]


#: relative interval widths above this are not measurements of anything -
#: they come from a rank-deficient information matrix.  The benchmark
#: clamps its own `max_rel_ci_pct` at the same value, so the two agree.
CI_CLIP_PCT = 1.0e4


def _int_xaxis(ax) -> None:
    """Rounds are integers; a 1.25 on a round axis is a reading error
    waiting to happen."""
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))


def _clip_ci(values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """(plottable values, clipped mask) for a relative-CI series."""
    v = np.asarray(values, dtype=float)
    clipped = ~np.isfinite(v) | (v > CI_CLIP_PCT)
    out = np.where(clipped, CI_CLIP_PCT, v)
    return out, clipped


def _finish(fig, path: str, note: str = "") -> str:
    """Lay the figure out, then hang the caveat BELOW the axes.

    The note is placed in negative figure coordinates on purpose: with
    `bbox_inches="tight"` it is still captured, but it can never land on top
    of an axis label - and a caveat a reader has to decode around is a
    caveat that will be skipped."""
    try:
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    except Exception:                                  # pragma: no cover
        pass
    if note:
        fig.text(0.005, -0.015, note, fontsize=7, color="#666666",
                 ha="left", va="top")
    return _save(fig, path)


# ------------------------------------------------------------------------- #
# 1. the experiments that were run
# ------------------------------------------------------------------------- #
def figure_conditions(round_rows: Sequence[Dict], path: str) -> Optional[str]:
    """T, total flow, catalyst and EGDA concentration vs round, per
    strategy: the experimental trajectory the controller chose."""
    if not round_rows:
        return None
    panels = (("T_C", "temperature / degC"),
              ("Q_total_mL_min", "total flow / mL/min"),
              ("C_cat_M", "catalyst / M"),
              ("C_EGDA_M", "EGDA feed / M"))
    strats = _strategies(round_rows)
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 6.8), sharex=True)
    for ax, (key, label) in zip(axes.ravel(), panels):
        for s in strats:
            rr = [r for r in round_rows if r["strategy"] == s]
            x, y = _series(rr, "round", key)
            if not x.size:
                continue
            ax.plot(x, y, "-o", ms=5, lw=1.4, color=color_for(s, strats),
                    label=f"strategy {s}")
        ax.set_ylabel(label)
        ax.grid(alpha=0.25, lw=0.5)
    for ax in axes[1]:
        ax.set_xlabel("campaign round")
    for ax in axes.ravel():
        _int_xaxis(ax)
    axes[0][0].legend(fontsize=8, frameon=False)
    fig.suptitle("Experimental trajectory: the conditions each strategy "
                 "chose, round by round")
    return _finish(fig, path)


def figure_positions(round_rows: Sequence[Dict], path: str) -> Optional[str]:
    """Where the capillary sampled, per round and strategy, annotated with
    the temperature and the design mode that produced each set."""
    if not round_rows:
        return None
    strats = _strategies(round_rows)
    fig, axes = plt.subplots(1, len(strats), squeeze=False, sharey=True,
                             figsize=(max(4.6 * len(strats), 5.2), 4.6))
    for ax, s in zip(axes[0], strats):
        rr = sorted((r for r in round_rows if r["strategy"] == s),
                    key=lambda r: _num(r, "round"))
        for r in rr:
            raw = str(r.get("z_over_L", "") or "")
            zs = [float(v) for v in raw.split(";") if v]
            if not zs:
                continue
            rnd = _num(r, "round")
            ax.scatter([rnd] * len(zs), zs, s=34, alpha=0.85,
                       color=color_for(s, strats), zorder=3)
            ax.annotate(f"{_num(r, 'T_C'):.0f}C", (rnd, 1.07), ha="center",
                        fontsize=7, color="#555555")
            ax.annotate(str(r.get("design_mode", "")), (rnd, -0.09),
                        ha="center", fontsize=6, color="#888888",
                        rotation=90)
        ax.set_title(f"strategy {s}", fontsize=10)
        ax.set_xlabel("campaign round")
        ax.set_ylim(-0.22, 1.16)
        ax.grid(alpha=0.25, lw=0.5, axis="y")
        _int_xaxis(ax)
    axes[0][0].set_ylabel("sampling position  z / L")
    fig.suptitle("Spatial sampling decisions across the campaign")
    return _finish(fig, path)


# ------------------------------------------------------------------------- #
# 2. what was measured
# ------------------------------------------------------------------------- #
def figure_concentration_profiles(conc_rows: Sequence[Dict], strategy: str,
                                  path: str,
                                  max_rounds: int = 6) -> Optional[str]:
    """NMR-derived concentrations against reactor position, with their
    uncertainty, next to the prediction of the model that was current at
    that round.

    One column per round, one row per species: the residual structure that
    matters (a species systematically off at one end of the reactor) is
    visible per round, and disappears if the rounds are pooled."""
    rows = [r for r in conc_rows if r["strategy"] == strategy]
    if not rows:
        return None
    rounds = sorted({int(_num(r, "round")) for r in rows})
    if len(rounds) > max_rounds:
        keep = np.unique(np.linspace(0, len(rounds) - 1, max_rounds)
                         .round().astype(int))
        rounds = [rounds[i] for i in keep]
    species: List[str] = []
    for r in rows:
        if r["species"] not in species:
            species.append(str(r["species"]))
    fig, axes = plt.subplots(len(species), len(rounds), squeeze=False,
                             sharex=True,
                             figsize=(2.9 * len(rounds), 2.1 * len(species)))
    for j, rnd in enumerate(rounds):
        rr = [r for r in rows if int(_num(r, "round")) == rnd]
        for i, sp in enumerate(species):
            ax = axes[i][j]
            sr = sorted((r for r in rr if r["species"] == sp),
                        key=lambda r: _num(r, "z_over_L"))
            if not sr:
                ax.set_axis_off()
                continue
            z = np.array([_num(r, "z_over_L") for r in sr])
            y = np.array([_num(r, "c_measured_M") for r in sr])
            e = np.array([_num(r, "sigma_M") for r in sr])
            pred = np.array([_num(r, "c_model_observed_M") for r in sr])
            col = SPECIES_COLOR.get(sp, "#333333")
            if np.any(np.isfinite(e)):
                ax.errorbar(z, y, yerr=1.96 * np.nan_to_num(e, nan=0.0),
                            fmt="o", ms=4, lw=0.9, capsize=2, color=col,
                            label="measured (95%)", zorder=3)
            else:
                ax.plot(z, y, "o", ms=4, color=col, label="measured")
            if np.any(np.isfinite(pred)):
                o = np.argsort(z)
                ax.plot(z[o], pred[o], "-", lw=1.3, color="#a23b2e",
                        alpha=0.9, label="fitted model")
            tr = np.array([_num(r, "c_true_reactor_M") for r in sr])
            if np.any(np.isfinite(tr)):
                o = np.argsort(z)
                ax.plot(z[o], tr[o], "--", lw=1.0, color="0.45",
                        label="truth (validation)")
            ax.grid(alpha=0.2, lw=0.5)
            if j == 0:
                ax.set_ylabel(f"{sp}\n/ M", fontsize=9)
            if i == 0:
                ax.set_title(f"round {rnd}", fontsize=9)
            if i == len(species) - 1:
                ax.set_xlabel("z / L")
    axes[0][0].legend(fontsize=6, frameon=False)
    fig.suptitle(f"Measured concentration profiles and the current model - "
                 f"strategy {strategy}")
    return _finish(fig, path,
                   "dashed grey line, where present, is the hidden truth: "
                   "post-campaign validation only.")


# ------------------------------------------------------------------------- #
# 3. what was inferred
# ------------------------------------------------------------------------- #
def figure_parameter_convergence(param_rows: Sequence[Dict], path: str,
                                 show_truth: bool = True) -> Optional[str]:
    """Every estimated parameter against round, with its 95% interval, one
    panel per parameter and one series per strategy.

    THE AXIS IS SET FROM THE ESTIMATES, not from the intervals.  An early
    round with a rank-deficient information matrix produces an interval many
    orders of magnitude wide; letting it drive the y-axis compresses every
    estimate in the panel to a flat line and destroys the only thing the
    figure is for.  Such a band therefore fills its panel and is called out
    in the caption, rather than rescaling the plot."""
    if not param_rows:
        return None
    params: List[str] = []
    for r in param_rows:
        if r["param"] not in params:
            params.append(str(r["param"]))
    strats = _strategies(param_rows)
    ncol = min(3, len(params))
    nrow = int(np.ceil(len(params) / ncol))
    fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                             figsize=(4.5 * ncol, 3.2 * nrow))
    used_truth = False
    clipped_any = False
    for q, p in enumerate(params):
        ax = axes[q // ncol][q % ncol]
        scale, label = PARAM_DISPLAY.get(p, (1.0, PARAM_LABEL.get(p, p)))
        logy = p in ("k1_ref", "k2_ref")
        seen: List[float] = []
        for s in strats:
            rr = sorted((r for r in param_rows
                         if r["param"] == p and r["strategy"] == s),
                        key=lambda r: _num(r, "round"))
            if not rr:
                continue
            x = np.array([_num(r, "round") for r in rr])
            y = np.array([_num(r, "estimate_natural") for r in rr]) / scale
            lo = np.array([_num(r, "ci95_lo_natural") for r in rr]) / scale
            hi = np.array([_num(r, "ci95_hi_natural") for r in rr]) / scale
            c = color_for(s, strats)
            ok = np.isfinite(lo) & np.isfinite(hi)
            if ok.any():
                ax.fill_between(x[ok], lo[ok], hi[ok], color=c, alpha=0.15,
                                lw=0)
            ax.plot(x, y, "-o", ms=5, lw=1.5, color=c, label=s)
            bound = np.array([_num(r, "bound_active") for r in rr]) > 0
            if bound.any():
                ax.plot(x[bound], y[bound], "x", ms=9, mew=2,
                        color="#000000")
            seen += [v for v in y if np.isfinite(v)]
        tv = [_num(r, "true_value_natural") / scale for r in param_rows
              if r["param"] == p]
        tv = [v for v in tv if np.isfinite(v)]
        if show_truth and tv:
            ax.axhline(tv[0], color="0.35", ls="--", lw=1.1)
            used_truth = True
            seen.append(tv[0])
        # the axis follows the ESTIMATES (and the truth line), never the
        # intervals - see the docstring
        if seen:
            lo_v, hi_v = min(seen), max(seen)
            if logy and lo_v > 0:
                ax.set_yscale("log")
                ax.set_ylim(lo_v / 3.0, hi_v * 3.0)
            else:
                pad = max((hi_v - lo_v) * 0.35, abs(hi_v) * 0.08, 1e-9)
                ax.set_ylim(lo_v - pad, hi_v + pad)
            for s in strats:
                rr = [r for r in param_rows
                      if r["param"] == p and r["strategy"] == s]
                if any(not np.isfinite(_num(r, "ci95_hi_natural"))
                       or _num(r, "ci95_hi_natural") / scale > hi_v + 1e-12
                       for r in rr):
                    clipped_any = True
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("campaign round")
        ax.grid(alpha=0.25, lw=0.5)
        _int_xaxis(ax)
    for q in range(len(params), nrow * ncol):
        axes[q // ncol][q % ncol].set_axis_off()
    axes[0][0].legend(fontsize=8, frameon=False, title="strategy",
                      title_fontsize=8)
    fig.suptitle("Kinetic parameter convergence (shaded: 95% interval; "
                 "x: estimate resting on a box bound)")
    note = []
    if used_truth:
        note.append("dashed line = hidden true value, shown for "
                    "post-campaign validation only")
    if clipped_any:
        note.append("a band filling its panel is an interval wider than the "
                    "plotted range - an early rank-deficient posterior, not "
                    "a measurement")
    return _finish(fig, path, "; ".join(note))


def figure_parameter_error(param_rows: Sequence[Dict],
                           path: str) -> Optional[str]:
    """Relative parameter error against round - SIMULATION VALIDATION ONLY,
    since it needs the hidden truth."""
    rows = [r for r in param_rows
            if np.isfinite(_num(r, "rel_error_pct_vs_truth"))]
    if not rows:
        return None
    strats = _strategies(rows)
    params: List[str] = []
    for r in rows:
        if r["param"] not in params:
            params.append(str(r["param"]))
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    ax = axes[0]
    for s in strats:
        rr = [r for r in rows if r["strategy"] == s]
        by_round: Dict[int, List[float]] = {}
        for r in rr:
            by_round.setdefault(int(_num(r, "round")), []).append(
                _num(r, "rel_error_pct_vs_truth"))
        x = sorted(by_round)
        ax.plot(x, [float(np.mean(by_round[k])) for k in x], "-o", ms=5,
                lw=1.6, color=color_for(s, strats), label=f"{s} (mean)")
        ax.plot(x, [float(np.max(by_round[k])) for k in x], ":s", ms=4,
                lw=1.0, color=color_for(s, strats), alpha=0.7,
                label=f"{s} (worst)")
    ax.set_yscale("log")
    ax.set_xlabel("campaign round")
    ax.set_ylabel("relative parameter error / %")
    ax.set_title("accuracy vs round")
    ax.grid(alpha=0.25, lw=0.5)
    _int_xaxis(ax)
    ax.legend(fontsize=7, frameon=False, ncol=2)
    ax2 = axes[1]
    width = 0.8 / max(len(strats), 1)
    for i, s in enumerate(strats):
        finals = []
        for p in params:
            rr = [r for r in rows if r["strategy"] == s and r["param"] == p]
            rr.sort(key=lambda r: _num(r, "round"))
            finals.append(_num(rr[-1], "rel_error_pct_vs_truth")
                          if rr else np.nan)
        ax2.bar(np.arange(len(params)) + i * width, finals, width,
                color=color_for(s, strats), label=f"strategy {s}")
    ax2.set_xticks(np.arange(len(params)) + 0.4 - width / 2)
    ax2.set_xticklabels([PARAM_LABEL.get(p, p) for p in params])
    ax2.set_ylabel("final relative error / %")
    ax2.set_title("final accuracy per parameter")
    ax2.grid(alpha=0.25, lw=0.5, axis="y")
    ax2.legend(fontsize=8, frameon=False)
    fig.suptitle("Parameter accuracy against the hidden truth - "
                 "POST-CAMPAIGN VALIDATION ONLY")
    return _finish(fig, path,
                   "the controller never saw any quantity on this figure.")


def _posterior_logdet(cov_rows: Sequence[Dict]) -> Dict[Tuple[str, int],
                                                        float]:
    """log det of the posterior PRECISION per (strategy, round), rebuilt
    from the stored upper triangle.  A linear-algebra summary of a matrix
    the round already computed - no refit."""
    out: Dict[Tuple[str, int], float] = {}
    by: Dict[Tuple[str, int], List[Dict]] = {}
    for r in cov_rows:
        by.setdefault((str(r["strategy"]), int(_num(r, "round"))),
                      []).append(r)
    for key, rows in by.items():
        keys: List[str] = []
        for r in rows:
            for k in (str(r["param_i"]), str(r["param_j"])):
                if k not in keys:
                    keys.append(k)
        n = len(keys)
        M = np.full((n, n), np.nan)
        for r in rows:
            i, j = keys.index(str(r["param_i"])), keys.index(str(r["param_j"]))
            M[i, j] = M[j, i] = _num(r, "cov_scaled")
        if not np.all(np.isfinite(M)):
            continue
        sign, ld = np.linalg.slogdet(M)
        out[key] = float(-ld) if sign > 0 else float("nan")
    return out


def figure_uncertainty(round_rows: Sequence[Dict],
                       param_rows: Sequence[Dict],
                       cov_rows: Sequence[Dict],
                       path: str) -> Optional[str]:
    """How well determined the parameters are, and how badly entangled:
    worst relative interval, per-parameter intervals, worst pairwise
    correlation, and the information content of the posterior."""
    if not round_rows:
        return None
    strats = _strategies(round_rows)
    logdet = _posterior_logdet(cov_rows)
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.0))
    ax = axes[0][0]
    clipped_any = False
    for s in strats:
        x, y = _series([r for r in round_rows if r["strategy"] == s],
                       "round", "max_rel_ci_pct")
        if not x.size:
            continue
        yv, clip = _clip_ci(y)
        ax.plot(x, yv, "-o", ms=5, color=color_for(s, strats), label=s)
        if clip.any():
            ax.plot(x[clip], yv[clip], "^", ms=8, mfc="none",
                    color=color_for(s, strats))
            clipped_any = True
    ax.set_yscale("log")
    ax.set_ylabel("worst 95% relative CI / %")
    ax.set_title("parameter uncertainty")
    ax.legend(fontsize=8, frameon=False, title="strategy", title_fontsize=8)

    ax = axes[0][1]
    params: List[str] = []
    for r in param_rows:
        if r["param"] not in params:
            params.append(str(r["param"]))
    for q, p in enumerate(params):
        for s in strats:
            rr = sorted((r for r in param_rows if r["param"] == p
                         and r["strategy"] == s),
                        key=lambda r: _num(r, "round"))
            if not rr:
                continue
            x = np.array([_num(r, "round") for r in rr])
            y, clip = _clip_ci([_num(r, "rel_ci95_width_pct") for r in rr])
            ax.plot(x, y, lw=1.2, alpha=0.85,
                    color=_PALETTE[q % len(_PALETTE)],
                    ls="-" if s == strats[0] else "--",
                    label=f"{p} ({s})")
            if clip.any():
                ax.plot(x[clip], y[clip], "^", ms=6, mfc="none",
                        color=_PALETTE[q % len(_PALETTE)])
                clipped_any = True
    ax.set_yscale("log")
    ax.set_ylim(top=CI_CLIP_PCT * 3.0)
    ax.set_ylabel("95% CI width / %")
    ax.set_title("per-parameter interval width")
    ax.legend(fontsize=6, frameon=False, ncol=2)

    ax = axes[1][0]
    for s in strats:
        x, y = _series([r for r in round_rows if r["strategy"] == s],
                       "round", "corr_max_offdiag")
        if x.size:
            ax.plot(x, y, "-o", ms=5, color=color_for(s, strats), label=s)
    ax.axhline(0.95, color="#a23b2e", ls=":", lw=1.0)
    ax.annotate("0.95: practically non-identifiable pair", (0.02, 0.90),
                xycoords=("axes fraction", "data"), fontsize=7,
                color="#a23b2e")
    ax.set_ylim(0.0, 1.08)
    ax.set_ylabel("worst |parameter correlation|")
    ax.set_xlabel("campaign round")
    ax.set_title("identifiability")

    ax = axes[1][1]
    drawn = False
    for s in strats:
        pts = sorted((rnd, v) for (st, rnd), v in logdet.items() if st == s)
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", ms=5,
                    color=color_for(s, strats), label=s)
            drawn = True
    if not drawn:
        ax.set_axis_off()
    else:
        ax.set_ylabel("log det posterior precision / nats")
        ax.set_xlabel("campaign round")
        ax.set_title("information accumulated")
    for a in axes.ravel():
        a.grid(alpha=0.25, lw=0.5)
        _int_xaxis(a)
    fig.suptitle("Uncertainty and identifiability across the campaign")
    return _finish(fig, path,
                   f"open triangles: interval clipped at {CI_CLIP_PCT:.0g} % "
                   f"- a rank-deficient information matrix gives a width "
                   f"that is not a measurement of anything."
                   if clipped_any else "")


def figure_correlation_matrices(cov_rows: Sequence[Dict], strategy: str,
                                path: str) -> Optional[str]:
    """Posterior parameter correlation at the start, the middle and the end
    of the campaign - where the entanglement was, and whether the campaign
    broke it."""
    rows = [r for r in cov_rows if r["strategy"] == strategy]
    if not rows:
        return None
    rounds = sorted({int(_num(r, "round")) for r in rows})
    if not rounds:
        return None
    picks = sorted({rounds[0], rounds[len(rounds) // 2], rounds[-1]})
    fig, axes = plt.subplots(1, len(picks), squeeze=False,
                             figsize=(3.9 * len(picks), 3.6))
    im = None
    for ax, rnd in zip(axes[0], picks):
        rr = [r for r in rows if int(_num(r, "round")) == rnd]
        keys: List[str] = []
        for r in rr:
            for k in (str(r["param_i"]), str(r["param_j"])):
                if k not in keys:
                    keys.append(k)
        n = len(keys)
        M = np.full((n, n), np.nan)
        for r in rr:
            i, j = keys.index(str(r["param_i"])), keys.index(str(r["param_j"]))
            M[i, j] = M[j, i] = _num(r, "corr")
        im = ax.imshow(M, vmin=-1.0, vmax=1.0, cmap="RdBu_r")
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels([PARAM_LABEL.get(k, k) for k in keys],
                           rotation=45, fontsize=8, ha="right")
        ax.set_yticklabels([PARAM_LABEL.get(k, k) for k in keys], fontsize=8)
        for i in range(n):
            for j in range(n):
                if np.isfinite(M[i, j]):
                    ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center",
                            fontsize=7,
                            color="white" if abs(M[i, j]) > 0.6 else "black")
        ax.set_title(f"round {rnd}", fontsize=10)
    if im is not None:
        fig.colorbar(im, ax=axes[0].tolist(), shrink=0.85,
                     label="posterior correlation")
    fig.suptitle(f"Posterior parameter correlation - strategy {strategy}")
    return _save(fig, path)


def figure_model_probabilities(prob_rows: Sequence[Dict],
                               path: str) -> Optional[str]:
    """Candidate-model probability against round, for the strategies that
    carry a model ensemble at all.

    Rounds whose Laplace evidence was flagged unreliable are marked: a
    probability derived from an evidence computed at a box bound is not a
    probability, and reading one off this curve without the marker would be
    the mistake the flag exists to prevent."""
    if not prob_rows:
        return None
    # a single-candidate family has nothing to discriminate: a flat line at
    # p = 1 is not a model-discrimination result, and drawing one invites
    # the reader to treat it as one.  The test is PER STRATEGY - two
    # strategies each carrying one (different) model is still two campaigns
    # that discriminated nothing.
    per_strategy = {}
    for r in prob_rows:
        per_strategy.setdefault(str(r.get("strategy", "")),
                                set()).add(str(r["model"]))
    if max((len(v) for v in per_strategy.values()), default=0) < 2:
        return None
    strats = _strategies(prob_rows)
    fig, axes = plt.subplots(1, len(strats), squeeze=False, sharey=True,
                             figsize=(max(5.0 * len(strats), 5.6), 4.2))
    for ax, s in zip(axes[0], strats):
        rr = [r for r in prob_rows if r["strategy"] == s]
        models: List[str] = []
        for r in rr:
            if r["model"] not in models:
                models.append(str(r["model"]))
        for i, m in enumerate(models):
            mr = sorted((r for r in rr if r["model"] == m),
                        key=lambda r: _num(r, "round"))
            ax.plot([_num(r, "round") for r in mr],
                    [_num(r, "probability") for r in mr], "-o", ms=4,
                    lw=1.5, color=_PALETTE[i % len(_PALETTE)], label=m)
        unreliable = sorted({int(_num(r, "round")) for r in rr
                             if not int(_num(r, "probs_reliable_all_models",
                                             1))})
        for rnd in unreliable:
            ax.axvspan(rnd - 0.25, rnd + 0.25, color="#c98a3a", alpha=0.18,
                       lw=0)
        ax.set_ylim(-0.03, 1.03)
        ax.set_xlabel("campaign round")
        ax.set_title(f"strategy {s}", fontsize=10)
        ax.grid(alpha=0.25, lw=0.5)
        _int_xaxis(ax)
        ax.legend(fontsize=7, frameon=False)
    axes[0][0].set_ylabel("posterior model probability")
    fig.suptitle("Model discrimination (shaded rounds: Laplace evidence "
                 "flagged unreliable)")
    return _finish(fig, path)


# ------------------------------------------------------------------------- #
# 4. why the controller chose what it chose
# ------------------------------------------------------------------------- #
def figure_design_decisions(cand_rows: Sequence[Dict], strategy: str,
                            path: str, max_rounds: int = 6) -> Optional[str]:
    """The shortlist behind each decision: screen score, the two expected
    information gains, the resource penalty and the total utility, with the
    selected candidate marked.

    EIG columns are populated only for the candidates the controller
    actually evaluated (the top-k it took to Monte Carlo); the rest are
    blank here for the same reason they are blank in the CSV - filling them
    in would mean running the estimator on candidates the campaign never
    considered."""
    rows = [r for r in cand_rows if r["strategy"] == strategy]
    if not rows:
        return None
    rounds = sorted({int(_num(r, "round")) for r in rows})
    if len(rounds) > max_rounds:
        keep = np.unique(np.linspace(0, len(rounds) - 1, max_rounds)
                         .round().astype(int))
        rounds = [rounds[i] for i in keep]
    fig, axes = plt.subplots(2, len(rounds), squeeze=False, sharex="col",
                             figsize=(2.9 * len(rounds), 6.0),
                             gridspec_kw={"height_ratios": [2.0, 1.3]})
    for j, rnd in enumerate(rounds):
        rr = sorted((r for r in rows if int(_num(r, "round")) == rnd),
                    key=lambda r: _num(r, "rank"))
        x = np.arange(len(rr))
        sel = np.array([int(_num(r, "selected")) for r in rr]) > 0
        top, bot = axes[0][j], axes[1][j]
        util = np.array([_num(r, "utility_total") for r in rr])
        eig_p = np.array([_num(r, "eig_param") for r in rr])
        eig_m = np.array([_num(r, "eig_model") for r in rr])
        cost = np.array([_num(r, "resource_penalty") for r in rr])
        top.bar(x - 0.22, np.nan_to_num(eig_p), 0.2, color="#1b3a5c",
                label="parameter EIG")
        top.bar(x, np.nan_to_num(eig_m), 0.2, color="#2a7f62",
                label="model EIG")
        top.bar(x + 0.22, -np.nan_to_num(cost), 0.2, color="#c98a3a",
                label="-resource penalty")
        top.plot(x, util, "k_", ms=16, label="total utility")
        for i in np.where(sel)[0]:
            top.axvspan(i - 0.45, i + 0.45, color="#a23b2e", alpha=0.12, lw=0)
        top.set_title(f"round {rnd}", fontsize=9)
        top.axhline(0.0, color="0.6", lw=0.6)
        bot.bar(x, [_num(r, "screen_score") for r in rr], 0.6,
                color=["#a23b2e" if s else "#8a8a8a" for s in sel])
        bot.set_xticks(x)
        bot.set_xticklabels([f"{_num(r, 'T_C'):.0f}C\n"
                             f"{_num(r, 'Q_total_mL_min'):.2g}mL"
                             for r in rr], fontsize=6)
        if j == 0:
            top.set_ylabel("expected information / nats")
            bot.set_ylabel("screen score")
        for a in (top, bot):
            a.grid(alpha=0.2, lw=0.5, axis="y")
    axes[0][0].legend(fontsize=6, frameon=True, framealpha=0.85, ncol=2,
                      loc="upper left", edgecolor="none")
    fig.suptitle(f"Why the next experiment won - strategy {strategy} "
                 f"(shaded = selected)")
    return _finish(fig, path,
                   "blank EIG bars = candidate screened but never Monte-"
                   "Carlo evaluated (see design_candidate_scores.csv).")


def figure_spatial_design(spatial_rows: Sequence[Dict], strategy: str,
                          path: str, max_rounds: int = 6) -> Optional[str]:
    """Information value over the candidate axial grid, and the positions
    the greedy design took from it."""
    rows = [r for r in spatial_rows if r["strategy"] == strategy
            and int(_num(r, "candidate_selected", 0)) == 1]
    if not rows:
        return None
    rounds = sorted({int(_num(r, "round")) for r in rows})
    if len(rounds) > max_rounds:
        keep = np.unique(np.linspace(0, len(rounds) - 1, max_rounds)
                         .round().astype(int))
        rounds = [rounds[i] for i in keep]
    fig, axes = plt.subplots(1, len(rounds), squeeze=False, sharey=True,
                             figsize=(2.8 * len(rounds), 3.8))
    any_curve = False
    for ax, rnd in zip(axes[0], rounds):
        rr = [r for r in rows if int(_num(r, "round")) == rnd]
        grid = sorted((r for r in rr
                       if str(r.get("row_kind")) == "candidate_z"),
                      key=lambda r: _num(r, "z_over_L"))
        chosen = sorted((r for r in rr
                         if str(r.get("row_kind")) == "selected_z"),
                        key=lambda r: _num(r, "selection_order"))
        final = [r for r in rr if str(r.get("row_kind")) == "final_z"]
        if grid:
            z = np.array([_num(r, "z_over_L") for r in grid])
            g = np.array([_num(r, "marginal_gain_nats") for r in grid])
            if np.any(np.isfinite(g)):
                ax.plot(z, g, "-", lw=1.5, color="#2a7f62")
                ax.fill_between(z, np.nanmin(g), g, color="#2a7f62",
                                alpha=0.15, lw=0)
                any_curve = True
        for r in chosen:
            order = int(_num(r, "selection_order"))
            early = order <= 3
            ax.axvline(_num(r, "z_over_L"), color="#a23b2e",
                       lw=1.1 if early else 0.7,
                       ls="--", alpha=0.85 if early else 0.35)
            if early:
                # only the first picks are labelled: ten numbers crowded
                # into one axis is not a reading of the selection order
                ax.annotate(str(order), (_num(r, "z_over_L"), 0.03),
                            xycoords=("data", "axes fraction"), fontsize=7,
                            color="#a23b2e", ha="center")
        if final:
            ax.plot([_num(r, "z_over_L") for r in final],
                    [0.0] * len(final), "|", ms=10, mew=1.6,
                    color="#1b3a5c", clip_on=False,
                    transform=ax.get_xaxis_transform())
        ax.set_title(f"round {rnd}", fontsize=9)
        ax.set_xlabel("z / L")
        ax.grid(alpha=0.2, lw=0.5)
    axes[0][0].set_ylabel("marginal log-det gain\n/ nats per acquisition")
    fig.suptitle(f"Spatial design - information over candidate positions "
                 f"and the order they were taken (strategy {strategy})")
    if not any_curve:
        plt.close(fig)
        return None
    return _finish(fig, path,
                   "curve = marginal gain of the first greedy step; dashed "
                   "lines = greedy picks (the first three are numbered in "
                   "selection order); blue ticks = the refined positions "
                   "actually measured.")


# ------------------------------------------------------------------------- #
# 5. the measurement chain
# ------------------------------------------------------------------------- #
def figure_nmr_diagnostics(spectrum_log: Sequence[Dict], strategy: str,
                           path: str, n_show: int = 3,
                           full: Tuple[float, float] = (0.5, 6.0),
                           zoom: Tuple[float, float] = (3.4, 4.7)
                           ) -> Optional[str]:
    """Observed spectrum, deconvolution fit, per-species components and
    residual for representative acquisitions of THIS campaign, with the
    concentration each one produced and its QC verdict.

    Three rows per acquisition, because one is not enough to see what
    matters: the full window shows that the fit tracks the spectrum, the
    backbone zoom shows the EGDA/EGMA overlap that actually drives the
    quantification uncertainty (on the full axis the water resonance is
    two orders of magnitude larger and hides it completely), and the
    residual gets its own scale, since a deconvolution is only as
    trustworthy as its residual is structureless.

    A failing spectrum is preferred over a passing one when the campaign
    produced any: the QC verdict is only meaningful if the reader can see
    what it rejected."""
    log = list(spectrum_log or [])
    if not log:
        return None

    def _failed(e):
        return any(str(f).startswith("FAIL")
                   for f in ((e.get("qc") or {}).get("qc_flags") or []))

    bad = [e for e in log if _failed(e)]
    good = [e for e in log if not _failed(e)]
    picks = bad[:1] + good[:max(n_show - min(len(bad), 1), 0)]
    if len(picks) < n_show:
        picks += [e for e in log if e not in picks][:n_show - len(picks)]
    picks = picks[:n_show]
    if not picks:
        return None
    fig, axes = plt.subplots(3, len(picks), squeeze=False,
                             figsize=(4.6 * len(picks), 8.2),
                             gridspec_kw={"height_ratios": [2.4, 2.4, 1.2]})
    for j, e in enumerate(picks):
        ppm = np.asarray(e["ppm"], dtype=float)
        obs = np.asarray(e["observed"], dtype=float)
        fit = np.asarray(e["fitted"], dtype=float)
        res = np.asarray(e["residual"], dtype=float)
        qc = e.get("qc") or {}
        comps = {k: np.asarray(v, dtype=float)
                 for k, v in (e.get("components") or {}).items()}
        wide, close, bot = axes[0][j], axes[1][j], axes[2][j]
        for ax, (lo, hi) in ((wide, full), (close, zoom)):
            m = (ppm >= lo) & (ppm <= hi)
            ax.plot(ppm[m], obs[m], lw=0.9, color="0.3", label="observed")
            ax.plot(ppm[m], fit[m], lw=1.2, color="#a23b2e", label="fit")
            for sp, c in comps.items():
                if sp in ("baseline", "exchange_pool"):
                    continue
                ax.plot(ppm[m], c[m], lw=0.9, ls="--", alpha=0.85,
                        color=SPECIES_COLOR.get(sp, "#888888"), label=sp)
            ax.set_xlim(hi, lo)
            ax.set_ylabel("intensity / a.u.", fontsize=8)
            ax.tick_params(labelsize=8)
        close.set_title(f"backbone zoom {zoom[0]}-{zoom[1]} ppm "
                        f"(EGDA/EGMA overlap)", fontsize=8)
        flags = list(qc.get("qc_flags", []) or [])
        state = ("FAIL" if _failed(e) else ("WARN" if flags else "PASS"))
        where = (f"z={float(e['z_m']) * 100:.1f} cm" if "z_m" in e
                 else "position unrecorded")
        wide.set_title(f"acquisition {int(e['acquisition_index'])}  {where}"
                       f"  -  QC {state}\n"
                       + ("; ".join(str(f) for f in flags)[:70]
                          if flags else "no flags raised"), fontsize=8.5)
        wide.legend(fontsize=6, frameon=False, ncol=3)
        m = (ppm >= full[0]) & (ppm <= full[1])
        bot.plot(ppm[m], res[m], lw=0.8, color="#2a7f62")
        bot.axhline(0.0, color="0.6", lw=0.6)
        bot.set_xlim(full[1], full[0])
        bot.set_xlabel(r"$\delta$ / ppm")
        bot.set_ylabel("residual", fontsize=8)
        bot.tick_params(labelsize=8)
        conc = np.asarray(e.get("conc_M", []), dtype=float)
        sig = np.asarray(e.get("sigma_M", []), dtype=float)
        txt = "\n".join(f"{sp} = {conc[i]:.4f} +- {sig[i]:.4f} M"
                         for i, sp in enumerate(e.get("species", ()))
                         if i < len(conc))
        wide.annotate(f"residual rms {_num(qc, 'residual_rms'):.3g}   "
                      f"cond {_num(qc, 'condition_number'):.3g}\n{txt}",
                      (0.40, 0.97), xycoords="axes fraction", fontsize=6.5,
                      va="top", family="monospace", color="#444444")
    fig.suptitle(f"NMR quantification diagnostics - strategy {strategy} "
                 f"(spectra as acquired during the campaign)")
    return _finish(fig, path)


def figure_transfer_diagnostics(transfer_rows: Sequence[Dict], strategy: str,
                                path: str) -> Optional[str]:
    """Reactor sampling point -> NMR cell -> reported value, so transport
    distortion and quantification error can be told apart.

    SIMULATION VALIDATION ONLY: both intermediate states are truth-side."""
    rows = [r for r in transfer_rows if r["strategy"] == strategy]
    if not rows:
        return None
    # a scenario with no transfer line has no transport stage to separate:
    # every point would sit exactly on the diagonal by construction, which
    # reads as a result and is not one.  The measurement-vs-truth comparison
    # such a scenario DOES support lives in concentrations.csv and on the
    # concentration-profile figure.
    if not any(int(_num(r, "transfer_enabled", 0)) for r in rows):
        return None
    species: List[str] = []
    for r in rows:
        if r["species"] not in species:
            species.append(str(r["species"]))
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.0))
    ax = axes[0][0]
    for sp in species:
        rr = [r for r in rows if r["species"] == sp]
        ax.scatter([_num(r, "c_reactor_true_M") for r in rr],
                   [_num(r, "c_cell_true_M") for r in rr], s=14, alpha=0.7,
                   color=SPECIES_COLOR.get(sp, "#888888"), label=sp)
    lim = [0.0, max([_num(r, "c_reactor_true_M") for r in rows] + [1e-6])]
    ax.plot(lim, lim, "k--", lw=0.8)
    ax.set_xlabel("true concentration at the sampling point / M")
    ax.set_ylabel("true concentration at the NMR cell / M")
    ax.set_title("transport distortion (line reaction + dispersion)")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[0][1]
    for sp in species:
        rr = [r for r in rows if r["species"] == sp]
        ax.scatter([_num(r, "c_cell_true_M") for r in rr],
                   [_num(r, "c_measured_M") for r in rr], s=14, alpha=0.7,
                   color=SPECIES_COLOR.get(sp, "#888888"), label=sp)
    ax.plot(lim, lim, "k--", lw=0.8)
    ax.set_xlabel("true concentration at the NMR cell / M")
    ax.set_ylabel("NMR-reported concentration / M")
    ax.set_title("quantification error (deconvolution)")

    ax = axes[1][0]
    width = 0.38
    x = np.arange(len(species))
    tr = [float(np.mean([_num(r, "transport_delta_M") for r in rows
                         if r["species"] == sp])) for sp in species]
    qu = [float(np.mean([_num(r, "quantification_delta_M") for r in rows
                         if r["species"] == sp])) for sp in species]
    ax.bar(x - width / 2, tr, width, color="#7a4fa3", label="transport")
    ax.bar(x + width / 2, qu, width, color="#c98a3a", label="quantification")
    ax.axhline(0.0, color="0.6", lw=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(species)
    ax.set_ylabel("mean signed deviation / M")
    ax.set_title("which stage moved the number")
    ax.legend(fontsize=8, frameon=False)

    ax = axes[1][1]
    for sp in species:
        rr = sorted((r for r in rows if r["species"] == sp),
                    key=lambda r: _num(r, "z_over_L"))
        ax.plot([_num(r, "z_over_L") for r in rr],
                [_num(r, "transport_delta_M") for r in rr], "o", ms=4,
                alpha=0.7, color=SPECIES_COLOR.get(sp, "#888888"), label=sp)
    ax.axhline(0.0, color="0.6", lw=0.6)
    ax.set_xlabel("sampling position z / L")
    ax.set_ylabel("transport deviation / M")
    ax.set_title("transport deviation vs sampling position")
    ax.legend(fontsize=7, frameon=False, ncol=2)
    for a in axes.ravel():
        a.grid(alpha=0.2, lw=0.5)
    fig.suptitle(f"Transfer-line decomposition - strategy {strategy}")
    return _finish(fig, path,
                   "both intermediate states are hidden truth: "
                   "post-campaign validation only.")


def figure_qc(qc_rows: Sequence[Dict], measurement_rows: Sequence[Dict],
              path: str) -> Optional[str]:
    """What the measurement-fault gate saw: dispositions per round, the
    persistence counters it decides on, and why spectra failed."""
    if not qc_rows:
        return None
    strats = _strategies(qc_rows)
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.0),
                             gridspec_kw={"height_ratios": [1.5, 1.0]})
    ax = axes[0][0]
    # ONE colour per DISPOSITION, not per strategy: colouring "accepted" by
    # strategy and "rejected" by a fixed red guarantees a clash as soon as a
    # strategy's colour is that red, and a legend a reader has to distrust
    # is worse than no legend.  The strategy is written under its bar.
    DISPO = (("n_accepted", "accepted", "#2a7f62"),
             ("n_rejected", "rejected", "#a23b2e"),
             ("n_reacquired", "reacquisitions", "#c98a3a"))
    width = 0.8 / max(len(strats), 1)
    rounds = sorted({int(_num(r, "round")) for r in qc_rows})
    ticks, labels = [], []
    for i, s in enumerate(strats):
        by_round = {int(_num(r, "round")): r for r in qc_rows
                    if r["strategy"] == s}
        x = np.arange(len(rounds)) + (i - (len(strats) - 1) / 2.0) * width
        bottom = np.zeros(len(rounds))
        for key, label, col in DISPO:
            v = np.array([_num(by_round.get(rn, {}), key, 0.0)
                          for rn in rounds])
            ax.bar(x, v, width * 0.92, bottom=bottom, color=col, alpha=0.9,
                   label=label if i == 0 else None)
            bottom += v
        ticks += list(x)
        labels += [s] * len(rounds)
    ax.set_xticks(list(np.arange(len(rounds))) + ticks,
                  [str(r) for r in rounds] + labels,
                  fontsize=7)
    for t in ax.get_xticklabels()[:len(rounds)]:
        t.set_fontsize(9)
        t.set_y(-0.07)
    ax.set_xlabel("campaign round  (bars labelled by strategy)")
    ax.set_ylabel("acquisitions")
    ax.set_title("acquisition dispositions")
    top = float(np.max(bottom)) if len(bottom) else 1.0
    ax.set_ylim(0.0, max(top, 1.0) * 1.28)
    ax.legend(fontsize=7, frameon=False, ncol=3, loc="upper center")

    ax = axes[0][1]
    for s in strats:
        rr = sorted((r for r in qc_rows if r["strategy"] == s),
                    key=lambda r: _num(r, "round"))
        ax.plot([_num(r, "round") for r in rr],
                [_num(r, "consecutive_rejects_after_round") for r in rr],
                "-o", ms=4, color=color_for(s, strats),
                label=f"{s} consecutive")
        ax.plot([_num(r, "round") for r in rr],
                [_num(r, "rejects_in_last_8_acquisitions") for r in rr],
                ":s", ms=4, color=color_for(s, strats), alpha=0.7,
                label=f"{s} rolling window")
    ax.set_xlabel("campaign round")
    ax.set_ylabel("rejections")
    ax.set_title("persistence counters the gate decides on")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[1][0]
    reasons: Dict[str, int] = {}
    for r in measurement_rows:
        if int(_num(r, "qc_fail", 0)) != 1:
            continue
        for f in str(r.get("qc_flags", "") or "").split(";"):
            if f.startswith("FAIL"):
                reasons[f] = reasons.get(f, 0) + 1
    if reasons:
        names = sorted(reasons, key=lambda k: -reasons[k])[:6]
        vals = [reasons[k] for k in names]
        ax.barh(range(len(names)), vals, color="#a23b2e")
        # QC flags carry their diagnosis in the string, which is far too
        # long for a tick label; wrapping it keeps the axis a readable
        # width instead of letting one label squeeze every other panel
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(["\n".join(textwrap.wrap(k, 34)[:2])
                            for k in names], fontsize=6.5)
        for i, v in enumerate(vals):
            ax.annotate(f" {int(v)}", (v, i), va="center", fontsize=7,
                        color="#333333")
        ax.set_xlim(0, max(vals) * 1.25)
        ax.invert_yaxis()
        ax.set_xlabel("species-rows flagged")
        ax.set_title("why spectra failed QC")
    else:
        ax.set_axis_off()
        ax.text(0.0, 1.0, "why spectra failed QC", va="top", ha="left",
                fontsize=11, color="#1b3a5c")
        ax.text(0.0, 0.86, "no spectrum failed QC in this campaign - every\n"
                           "acquisition was assimilated as measured.",
                va="top", ha="left", fontsize=8, family="monospace",
                color="#333333")

    ax = axes[1][1]
    tripped = [r for r in qc_rows
               if int(_num(r, "gate_tripped_this_campaign", 0)) == 1]
    lines = []
    for s in strats:
        rr = [r for r in qc_rows if r["strategy"] == s]
        n_rej = int(sum(_num(r, "n_rejected") for r in rr))
        n_re = int(sum(_num(r, "n_reacquired") for r in rr))
        stop = rr[-1].get("stop_reason", "") if rr else ""
        gate = int(_num(rr[-1], "qc_gate_active", 0)) if rr else 0
        lines.append(f"strategy {s}: "
                     + (f"{n_rej} rejected, {n_re} reacquired"
                        if gate else "no QC gate (direct assimilation)")
                     + f"\n    stop: {stop or 'budget exhausted'}")
    ax.set_axis_off()
    ax.text(0.0, 1.0, "gate verdict" + ("  -  TRIPPED" if tripped
                                        else "  -  not tripped"),
            va="top", ha="left", fontsize=11, color="#1b3a5c")
    ax.text(0.0, 0.86, "\n".join(lines), va="top", ha="left", fontsize=8,
            family="monospace", color="#333333", wrap=True)
    for a in (axes[0][0], axes[0][1]):
        a.grid(alpha=0.2, lw=0.5, axis="y")
    _int_xaxis(axes[0][1])
    fig.suptitle("Measurement-fault QC diagnostics")
    return _finish(fig, path)


def figure_governor(gov_rows: Sequence[Dict], path: str) -> Optional[str]:
    """Model-adequacy governor: the dispersion it measured, the p-values it
    tested and the state it declared."""
    if not gov_rows:
        return None
    strats = _strategies(gov_rows)
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.0))
    ax = axes[0]
    for s in strats:
        x, y = _series([r for r in gov_rows if r["strategy"] == s],
                       "round", "chi2_over_dof")
        if x.size:
            ax.plot(x, y, "-o", ms=5, color=color_for(s, strats), label=s)
    ax.axhline(1.0, color="0.5", ls="--", lw=0.8)
    ax.set_ylabel(r"$\chi^2$ / dof")
    ax.set_xlabel("campaign round")
    ax.set_title("realized misfit")
    ax.legend(fontsize=8, frameon=False, title="strategy", title_fontsize=8)

    ax = axes[1]
    for s in strats:
        rr = sorted((r for r in gov_rows if r["strategy"] == s),
                    key=lambda r: _num(r, "round"))
        ax.semilogy([_num(r, "round") for r in rr],
                    [max(_num(r, "p_combined_best_model"), 1e-16)
                     for r in rr], "-o", ms=5, color=color_for(s, strats),
                    label=f"{s}: p")
        alpha = [_num(r, "alpha_round_threshold") for r in rr]
        if np.any(np.isfinite(alpha)):
            ax.semilogy([_num(r, "round") for r in rr], alpha, ":",
                        lw=1.2, color=color_for(s, strats),
                        label=f"{s}: threshold")
    ax.set_ylabel("p-value")
    ax.set_xlabel("campaign round")
    ax.set_title("adequacy test vs its round threshold")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[2]
    states: List[str] = []
    for r in gov_rows:
        if r["state"] not in states:
            states.append(str(r["state"]))
    for s in strats:
        rr = sorted((r for r in gov_rows if r["strategy"] == s),
                    key=lambda r: _num(r, "round"))
        ax.plot([_num(r, "round") for r in rr],
                [states.index(str(r["state"])) for r in rr], "-o", ms=6,
                color=color_for(s, strats), label=s)
        for r in rr:
            why = str(r.get("trigger_reasons", "") or "")
            if why and str(r["state"]) != "NORMAL_LEARNING":
                ax.annotate(why[:40], (_num(r, "round"),
                                       states.index(str(r["state"]))),
                            fontsize=6, color="#666666",
                            xytext=(0, 8), textcoords="offset points")
    ax.set_yticks(range(len(states)))
    ax.set_yticklabels(states, fontsize=8)
    ax.set_xlabel("campaign round")
    ax.set_title("declared state")
    for a in axes:
        a.grid(alpha=0.2, lw=0.5)
        _int_xaxis(a)
    fig.suptitle("Model-inadequacy governor")
    return _finish(fig, path)


def figure_resources(resource_rows: Sequence[Dict],
                     path: str) -> Optional[str]:
    """Cumulative laboratory cost against round - the axis a real campaign
    is actually budgeted on."""
    if not resource_rows:
        return None
    panels = [("cum_time_s_s", "campaign time / s"),
              ("cum_egda_mol_mol", "EGDA consumed / mol"),
              ("cum_waste_mL_mL", "waste / mL"),
              ("cum_energy_kJ_kJ", "energy proxy / kJ"),
              ("cum_nmr_acquisitions_count", "NMR acquisitions"),
              ("cum_spatial_samples_count", "spatial samples"),
              ("cum_capillary_travel_m_m", "capillary travel / m"),
              ("cum_nmr_reacquisitions_count", "reacquisitions")]
    panels = [p for p in panels
              if any(np.isfinite(_num(r, p[0])) for r in resource_rows)]
    if not panels:
        return None
    strats = _strategies(resource_rows)
    ncol = 4
    nrow = int(np.ceil(len(panels) / ncol))
    fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                             figsize=(3.3 * ncol, 2.7 * nrow))
    for q, (key, label) in enumerate(panels):
        ax = axes[q // ncol][q % ncol]
        for s in strats:
            x, y = _series([r for r in resource_rows if r["strategy"] == s],
                           "round", key)
            if x.size:
                ax.plot(x, y, "-o", ms=4, color=color_for(s, strats),
                        label=s)
        ax.set_ylabel(label, fontsize=8)
        ax.set_xlabel("round", fontsize=8)
        ax.grid(alpha=0.2, lw=0.5)
        ax.tick_params(labelsize=8)
        _int_xaxis(ax)
    for q in range(len(panels), nrow * ncol):
        axes[q // ncol][q % ncol].set_axis_off()
    axes[0][0].legend(fontsize=8, frameon=False, title="strategy",
                      title_fontsize=8)
    fig.suptitle("Cumulative resource consumption")
    return _finish(fig, path)


def figure_strategy_comparison(summary_rows: Sequence[Dict],
                               path: str) -> Optional[str]:
    """The end-of-campaign scoreboard for whichever strategies were run."""
    if not summary_rows:
        return None
    strats = [str(r["strategy"]) for r in summary_rows]
    # (column, axis label, "lower is better")
    metrics = [("param_err_pct_final_vs_truth", "parameter error / %", True),
               ("blind_rmse_M_final_vs_truth", "blind RMSE / M", True),
               ("max_rel_ci_pct_final", "worst 95% CI / %", True),
               ("n_nmr_acquisitions", "NMR acquisitions", False),
               ("n_spatial_samples", "spatial samples", False),
               ("time_s", "campaign time / s", True),
               ("egda_mol", "EGDA consumed / mol", True),
               ("waste_mL", "waste / mL", True),
               ("energy_kJ", "energy proxy / kJ", True),
               ("n_qc_rejected", "QC rejected", True),
               ("n_nmr_reacquisitions", "reacquisitions", True),
               ("rounds_completed", "rounds completed", False)]
    metrics = [m for m in metrics
               if any(np.isfinite(_num(r, m[0])) for r in summary_rows)]
    ncol = 4
    nrow = int(np.ceil(len(metrics) / ncol))
    fig, axes = plt.subplots(nrow, ncol, squeeze=False,
                             figsize=(3.2 * ncol, 2.9 * nrow))
    x = np.arange(len(strats))
    for q, (key, label, lower_better) in enumerate(metrics):
        ax = axes[q // ncol][q % ncol]
        vals = [_num(r, key) for r in summary_rows]
        # LINEAR axes only.  A bar on a log axis starts at an arbitrary
        # baseline, so its LENGTH - the thing a bar chart is read by - no
        # longer means anything; the printed value carries the magnitude
        # instead.
        ax.bar(x, np.nan_to_num(vals), 0.62,
               color=[color_for(s, strats) for s in strats])
        hi = max([v for v in vals if np.isfinite(v)] + [0.0]) or 1.0
        ax.set_ylim(0.0, hi * 1.22)
        for i, v in enumerate(vals):
            ax.annotate("-" if not np.isfinite(v) else
                        (f"{v:.3g}" if abs(v) < 1e4 else f"{v:.2e}"),
                        (i, max(v, 0.0) if np.isfinite(v) else 0.0),
                        textcoords="offset points", xytext=(0, 3),
                        ha="center", fontsize=7, color="#333333")
        ax.set_xticks(x)
        ax.set_xticklabels(strats, fontsize=8)
        ax.set_ylabel(label + ("  (lower better)" if lower_better else ""),
                      fontsize=8)
        ax.grid(alpha=0.2, lw=0.5, axis="y")
        ax.tick_params(labelsize=8)
    for q in range(len(metrics), nrow * ncol):
        axes[q // ncol][q % ncol].set_axis_off()
    fig.suptitle("Final strategy comparison")
    return _finish(fig, path,
                   "accuracy panels use the hidden truth: post-campaign "
                   "validation only.")
