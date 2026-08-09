"""
Publication figures A-H and paired CSV exports for the advanced benchmark.

Every figure writes a PNG and a CSV with the plotted numbers next to it,
so the paper's plots can be regenerated from data alone.
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

STRAT_COLOR = {"A": "#8a8a8a", "B": "#5b7fbc", "C": "#c98a3a", "D": "#1b3a5c",
               "E": "#2a7f62", "F": "#a23b2e", "F-noNMR": "#d4779a",
               "F-noTransport": "#7a4fa3", "F-noGovernor": "#b8452f",
               "F-full": "#a23b2e"}


def _save(fig, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"saved: {path}")
    return path


def _csv(path: str, header: Sequence[str], rows: Sequence[Sequence]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"saved: {path}")


# ------------------------------------------------------------------------- #
def figure_a_spatial_value(z_profile: np.ndarray,
                           conc_profile: Dict[str, np.ndarray],
                           z_equal: np.ndarray, z_opt: np.ndarray,
                           info_z: np.ndarray, info_gain: np.ndarray,
                           path: str) -> None:
    """True concentration profile + equal vs optimized positions + the
    information-density curve: why are all axial positions not equally
    valuable?"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 7.0), sharex=True,
                                   height_ratios=[2.0, 1.2])
    L = z_profile[-1]
    for sp, col in (("EGDA", "#1b3a5c"), ("EGMA", "#2a7f62"),
                    ("EG", "#a23b2e"), ("AcOH", "#8c5a2b")):
        ax1.plot(z_profile / L, conc_profile[sp], color=col, lw=1.8, label=sp)
    for z in z_equal:
        ax1.axvline(z / L, color="#999999", lw=0.8, ls=":", alpha=0.7)
    for z in z_opt:
        ax1.axvline(z / L, color="#a23b2e", lw=1.2, ls="--", alpha=0.85)
    ax1.plot([], [], color="#999999", ls=":", label="equal positions")
    ax1.plot([], [], color="#a23b2e", ls="--", label="optimized positions")
    ax1.set_ylabel("concentration / M")
    ax1.legend(ncol=3, fontsize=9, frameon=False)
    ax1.set_title("Figure A - optimal vs equal spatial sampling "
                  "(true profile, hidden from the controller)")
    ax2.plot(info_z / L, info_gain, color="#2a7f62", lw=1.8)
    ax2.fill_between(info_z / L, 0, info_gain, color="#2a7f62", alpha=0.15)
    ax2.set_xlabel("z / L")
    ax2.set_ylabel("marginal log-det gain\n(nats / acquisition)")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["z_over_L", "info_gain_nats"]
         + [f"C_{sp}_M" for sp in conc_profile],
         [[z / L, g] + [np.interp(z, z_profile, conc_profile[sp])
                        for sp in conc_profile]
          for z, g in zip(info_z, info_gain)])


def figure_b_position_rounds(histories: Dict[str, List], length_m: float,
                             path: str) -> None:
    """Selected z/L per campaign round (one panel per strategy)."""
    fig, axes = plt.subplots(1, len(histories), figsize=(4.5 * len(histories),
                                                         4.2), squeeze=False)
    rows = []
    for ax, (key, hist) in zip(axes[0], histories.items()):
        for rec in hist:
            zs = np.asarray(rec.z_positions, dtype=float) / length_m
            ax.scatter([rec.round] * len(zs), zs, s=28,
                       c=STRAT_COLOR.get(key, "#333333"), alpha=0.8)
            t = rec.u.T_C
            ax.annotate(f"{t:.0f}C", (rec.round, 1.04), ha="center",
                        fontsize=7, color="#666666")
            rows.extend([[key, rec.round, rec.u.T_C, z] for z in zs])
        ax.set_xlabel("campaign round")
        ax.set_ylim(-0.02, 1.10)
        ax.set_title(f"strategy {key}")
    axes[0][0].set_ylabel("selected z / L")
    fig.suptitle("Figure B - spatial position decisions across rounds")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["strategy", "round", "T_C", "z_over_L"], rows)


def figure_c_spectrum(spectra: List[Tuple[np.ndarray, np.ndarray,
                                          np.ndarray]],
                      qc: List[Dict], z_positions: Sequence[float],
                      length_m: float, path: str,
                      zoom=(3.4, 4.7)) -> None:
    """Noisy spectrum, fitted spectrum, residual for representative
    positions, full range + backbone zoom (EGDA/EGMA overlap region)."""
    n = len(spectra)
    fig, axes = plt.subplots(n, 2, figsize=(12.0, 2.9 * n), squeeze=False)
    for k, ((ppm, y, fit), q) in enumerate(zip(spectra, qc)):
        for j, (lo, hi) in enumerate(((ppm[0], ppm[-1]), zoom)):
            ax = axes[k][j]
            msk = (ppm >= lo) & (ppm <= hi)
            ax.plot(ppm[msk], y[msk], color="#8a8a8a", lw=0.8,
                    label="simulated (noisy)")
            ax.plot(ppm[msk], fit[msk], color="#a23b2e", lw=1.2,
                    label="deconvolution fit")
            ax.plot(ppm[msk], (y - fit)[msk] - 0.08 * np.max(y[msk]),
                    color="#2a7f62", lw=0.7, label="residual (offset)")
            ax.invert_xaxis()
            ax.set_yticks([])
            if k == 0 and j == 0:
                ax.legend(fontsize=8, frameon=False)
            if j == 0:
                ax.set_ylabel(f"z/L={z_positions[k] / length_m:.2f}\n"
                              f"rms={q.get('residual_rms', 0):.3g}")
        axes[k][1].set_title("backbone zoom (EGDA 4.335 / EGMA 4.245 "
                             "overlap)", fontsize=9)
    axes[-1][0].set_xlabel(r"$\delta$ / ppm")
    axes[-1][1].set_xlabel(r"$\delta$ / ppm")
    fig.suptitle("Figure C - simulated Fourier-80 spectra and deconvolution")
    _save(fig, path)


def figure_d_truth_vs_recovered(truth_c: np.ndarray, est_c: np.ndarray,
                                sig_c: np.ndarray, species: Sequence[str],
                                path: str) -> Dict[str, float]:
    """Concentration truth vs NMR recovery with 95% intervals; returns and
    prints coverage + RMSE."""
    n_sp = len(species)
    fig, axes = plt.subplots(1, n_sp, figsize=(3.4 * n_sp, 3.6))
    stats = {}
    rows = []
    for i, (sp, ax) in enumerate(zip(species, np.atleast_1d(axes))):
        t, e, s = truth_c[:, i], est_c[:, i], sig_c[:, i]
        cover = float(np.mean(np.abs(e - t) <= 1.96 * s))
        rmse = float(np.sqrt(np.mean((e - t) ** 2)))
        ax.errorbar(t, e, yerr=1.96 * s, fmt="o", ms=3.5, lw=0.7,
                    color=STRAT_COLOR["F"], alpha=0.65, capsize=2)
        lim = [0.0, max(t.max(), e.max()) * 1.08]
        ax.plot(lim, lim, color="#555555", lw=0.8, ls="--")
        ax.set_title(f"{sp}\ncoverage {cover:.0%}, RMSE {rmse * 1e3:.2f} mM",
                     fontsize=9)
        ax.set_xlabel("true C / M")
        stats[f"coverage_{sp}"] = cover
        stats[f"rmse_M_{sp}"] = rmse
        rows.extend([[sp, tt, ee, ss] for tt, ee, ss in zip(t, e, s)])
    np.atleast_1d(axes)[0].set_ylabel("deconvolved C / M")
    fig.suptitle("Figure D - concentration truth vs NMR recovery "
                 "(95% intervals)")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["species", "true_M", "estimated_M", "sigma_M"], rows)
    return stats


def figure_e_convergence(curves: Dict[str, Dict[str, List[float]]],
                         x_key: str, path: str,
                         panels=(("param_err_pct",
                                  "parameter error (geo-mean) / %"),
                                 ("max_rel_ci_pct", "worst 95% CI / %"),
                                 ("p_correct", "P(correct model)"),
                                 ("blind_rmse_M", "blind RMSE / M"))
                         ) -> None:
    """Learning curves vs campaign resource for every strategy."""
    fig, axes = plt.subplots(1, len(panels), figsize=(4.4 * len(panels), 3.8))
    rows = []
    for key, cur in curves.items():
        x = cur[x_key]
        for j, (pk, _) in enumerate(panels):
            if pk not in cur or all(np.isnan(cur[pk])):
                continue
            axes[j].plot(x, cur[pk], "o-", ms=4, lw=1.4,
                         color=STRAT_COLOR.get(key, None), label=key)
        rows.extend([[key] + [cur[x_key][i]]
                     + [cur.get(pk, [np.nan] * len(x))[i]
                        for pk, _ in panels] for i in range(len(x))])
    for j, (pk, lab) in enumerate(panels):
        axes[j].set_xlabel(x_key)
        axes[j].set_ylabel(lab)
        if pk.endswith("pct") or pk.endswith("_M"):
            axes[j].set_yscale("log")
    axes[0].legend(fontsize=8, frameon=False)
    fig.suptitle("Figure E - learning vs campaign resource")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["strategy", x_key] + [pk for pk, _ in panels], rows)


def figure_f_inadequacy(rounds: List[int], naive_ci: List[float],
                        naive_err: List[float], gov_score: List[float],
                        gov_state: List[str], trip_round: Optional[int],
                        path: str) -> None:
    """The naive loop grows confident in a wrong model while the governor
    recognizes the systematic discrepancy."""
    fig, ax1 = plt.subplots(figsize=(8.0, 4.6))
    ax1.plot(rounds, naive_ci, "o-", color="#1b3a5c", lw=1.6,
             label="naive 95% CI width (shrinking = growing confidence)")
    ax1.plot(rounds, naive_err, "s--", color="#8a8a8a", lw=1.4,
             label="true parameter error (hidden)")
    ax1.set_yscale("log")
    ax1.set_xlabel("campaign round")
    ax1.set_ylabel("percent")
    ax2 = ax1.twinx()
    ax2.plot(rounds, gov_score, "^-", color="#a23b2e", lw=1.6,
             label="governor lack-of-fit score (chi2/dof)")
    ax2.axhline(1.0, color="#a23b2e", lw=0.7, ls=":")
    ax2.set_ylabel("chi2 / dof", color="#a23b2e")
    if trip_round is not None:
        ax1.axvline(trip_round, color="#a23b2e", lw=1.2, ls="--", alpha=0.7)
        ax1.annotate("MODEL_INADEQUATE declared", (trip_round, ax1.get_ylim()[1]),
                     rotation=90, va="top", ha="right", fontsize=8,
                     color="#a23b2e")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=8, frameon=False,
               loc="center right")
    fig.suptitle("Figure F - model-inadequacy challenge")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["round", "naive_ci_pct", "true_err_pct", "gov_chi2_dof", "state"],
         list(zip(rounds, naive_ci, naive_err, gov_score, gov_state)))


def figure_g_resources(points: Dict[str, Dict[str, float]], path: str,
                       axes_keys=(("egda_mol", "EGDA consumed / mol"),
                                  ("time_s", "campaign time / s"),
                                  ("nmr_acquisitions", "NMR acquisitions"),
                                  ("energy_kJ", "energy proxy / kJ"))
                       ) -> None:
    """Blind prediction quality vs each resource axis, one point per
    strategy."""
    fig, axs = plt.subplots(1, len(axes_keys), figsize=(4.2 * len(axes_keys),
                                                        3.8))
    rows = []
    for key, pt in points.items():
        for j, (rk, lab) in enumerate(axes_keys):
            axs[j].scatter(pt[rk], pt["blind_rmse_M"], s=60,
                           c=STRAT_COLOR.get(key, "#333333"), label=key)
            axs[j].set_xlabel(lab)
            axs[j].set_yscale("log")
        rows.append([key] + [pt[rk] for rk, _ in axes_keys]
                    + [pt["blind_rmse_M"]])
    axs[0].set_ylabel("blind RMSE / M")
    axs[0].legend(fontsize=8, frameon=False)
    fig.suptitle("Figure G - resource efficiency")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["strategy"] + [rk for rk, _ in axes_keys] + ["blind_rmse_M"], rows)


def figure_h_ablation(bars: Dict[str, Dict[str, float]], path: str) -> None:
    """Ablation: what each layer of realism/modeling buys."""
    labels = list(bars)
    metrics = [("param_err_pct", "parameter error / %"),
               ("blind_rmse_M", "blind RMSE / M")]
    fig, axs = plt.subplots(1, len(metrics), figsize=(5.2 * len(metrics), 4.0))
    x = np.arange(len(labels))
    for j, (mk, lab) in enumerate(metrics):
        vals = [bars[k][mk] for k in labels]
        axs[j].bar(x, vals, color=[STRAT_COLOR.get(k, "#5b7fbc")
                                   for k in labels], alpha=0.85)
        axs[j].set_xticks(x, labels, rotation=20, ha="right", fontsize=8)
        axs[j].set_ylabel(lab)
        axs[j].set_yscale("log")
    fig.suptitle("Figure H - ablation: realism hurts naive inference; "
                 "measurement-aware inference recovers")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["variant"] + [mk for mk, _ in metrics],
         [[k] + [bars[k][mk] for mk, _ in metrics] for k in labels])


def figure_param_evolution(param_rows: List[Dict], scenario: str,
                           strategy: str, path: str) -> None:
    """Per-parameter posterior evolution: median 95%-interval relative width
    and median true relative error vs round (identifiability vs accuracy,
    reported per parameter - not hidden behind an aggregate)."""
    rows = [r for r in param_rows
            if r["scenario"] == scenario and r["strategy"] == strategy]
    params = sorted({r["param"] for r in rows})
    if not params:
        return
    fig, axes = plt.subplots(1, len(params),
                             figsize=(2.9 * len(params), 3.6), squeeze=False)
    csv_rows = []
    for ax, pk in zip(axes[0], params):
        pr = [r for r in rows if r["param"] == pk]
        rounds = sorted({r["round"] for r in pr})
        w_med, e_med = [], []
        for rnd in rounds:
            rr = [r for r in pr if r["round"] == rnd]
            w = [x["rel_width_pct"] for x in rr
                 if np.isfinite(x["rel_width_pct"])]
            e = [x["rel_error_pct"] for x in rr
                 if np.isfinite(x.get("rel_error_pct", np.nan))]
            w_med.append(np.median(w) if w else np.nan)
            e_med.append(np.median(e) if e else np.nan)
            csv_rows.append([pk, rnd, w_med[-1], e_med[-1],
                             int(np.sum([x["bound_active"] for x in rr]))])
        ax.plot(rounds, w_med, "o-", color="#1b3a5c",
                label="95% interval width")
        ax.plot(rounds, e_med, "s--", color="#a23b2e",
                label="true |error| (post-hoc)")
        ax.set_yscale("log")
        ax.set_title(pk, fontsize=9)
        ax.set_xlabel("round")
    axes[0][0].set_ylabel("percent")
    axes[0][0].legend(fontsize=7, frameon=False)
    fig.suptitle(f"parameter posterior evolution - {scenario}/{strategy} "
                 "(median over seeds)")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["param", "round", "median_rel_width_pct",
          "median_rel_error_pct", "n_bound_active"], csv_rows)


def figure_transport_ablation(bars: Dict[str, Dict[str, float]],
                              path: str) -> None:
    """Which transport effect biases naive inference: final blind RMSE of
    naive D vs transport-aware F under each truth-physics variant."""
    labels = list(bars)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    x = np.arange(len(labels))
    wd = 0.36
    ax.bar(x - wd / 2, [bars[k].get("D", np.nan) for k in labels], wd,
           color="#1b3a5c", label="D (naive concentration-at-z)")
    ax.bar(x + wd / 2, [bars[k].get("F", np.nan) for k in labels], wd,
           color="#a23b2e", label="F (mean-delay corrected)")
    ax.set_xticks(x, labels, rotation=12, ha="right", fontsize=9)
    ax.set_yscale("log")
    ax.set_ylabel("final blind RMSE / M (median over seeds)")
    ax.legend(fontsize=9, frameon=False)
    fig.suptitle("transport ablation: which physical effect matters")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["variant", "D_blind_rmse_M", "F_blind_rmse_M"],
         [[k, bars[k].get("D", np.nan), bars[k].get("F", np.nan)]
          for k in labels])


# ------------------------------------------------------------------------- #
def write_strategy_table(rows: List[Dict], path: str) -> str:
    """The A-F comparison table (CSV + printable text)."""
    if not rows:
        return ""
    keys = list(rows[0].keys())
    _csv(path, keys, [[r[k] for k in keys] for r in rows])
    widths = {k: max(len(str(k)), *(len(f"{r[k]:.4g}"
                                        if isinstance(r[k], float)
                                        else str(r[k])) for r in rows))
              for k in keys}
    lines = ["  ".join(str(k).ljust(widths[k]) for k in keys)]
    for r in rows:
        lines.append("  ".join(
            (f"{r[k]:.4g}" if isinstance(r[k], float) else str(r[k]))
            .ljust(widths[k]) for k in keys))
    text = "\n".join(lines)
    with open(path.replace(".csv", ".txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return text


# ========================================================================= #
# Publication audit-trail figures
# ========================================================================= #
#: markers, not colour alone - the S6 Pareto has six overlapping strategies
#: and colour-only encoding is unreadable in print and to colour-blind
#: readers
_PARETO_MARKERS = ("o", "s", "^", "D", "v", "P", "X", "*", "<", ">")


def figure_convergence_band(summary_rows: List[Dict], scenario: str,
                            path: str, basis: str = "locf",
                            panels=(("param_err_pct",
                                     "parameter error (geo-mean) / %"),
                                    ("blind_rmse_M", "blind RMSE / M"),
                                    ("max_rel_ci_pct", "worst 95% CI / %"),
                                    ("p_correct", "P(model)"))) -> None:
    """Median with IQR band and bootstrap-CI whiskers, plus the ACTIVE
    SAMPLE COUNT on a second axis.

    Two things this fixes over a plain mean curve.  First, a mean over a
    heavy-tailed error distribution is dominated by the worst seed; the
    median and IQR describe where the campaigns actually are.  Second, the
    sample can THIN as rounds advance when campaigns pause on a measurement
    fault - so `n_in_summary` is drawn as a grey step on the right-hand
    axis of the first panel.  A curve that improves while that step falls is
    survivorship, not learning, and the figure makes the two separable at a
    glance.

    `basis` selects the observed-only or last-observation-carried-forward
    summary (see audit_summary.py); the basis is written into the title so
    a figure can never be mistaken for the other one."""
    rows = [r for r in summary_rows
            if r["scenario"] == scenario and r["basis"] == basis]
    if not rows:
        return
    strategies = sorted({r["strategy"] for r in rows})
    fig, axes = plt.subplots(1, len(panels), figsize=(4.5 * len(panels), 4.0))
    axes = np.atleast_1d(axes)
    out_rows = []
    for j, (metric, lab) in enumerate(panels):
        ax = axes[j]
        drew = False
        for key in strategies:
            sel = sorted((r for r in rows if r["strategy"] == key
                          and r["metric"] == metric),
                         key=lambda r: r["round"])
            xs = [r["round"] for r in sel]
            med = np.array([r["median"] for r in sel], dtype=float)
            if not xs or np.all(~np.isfinite(med)):
                continue
            drew = True
            q25 = np.array([r["q25"] for r in sel], dtype=float)
            q75 = np.array([r["q75"] for r in sel], dtype=float)
            lo = np.array([r["boot_ci_lo"] for r in sel], dtype=float)
            hi = np.array([r["boot_ci_hi"] for r in sel], dtype=float)
            c = STRAT_COLOR.get(key, None)
            ax.plot(xs, med, "o-", ms=4, lw=1.6, color=c, label=key)
            ax.fill_between(xs, q25, q75, color=c, alpha=0.18, lw=0)
            ax.errorbar(xs, med, yerr=[np.clip(med - lo, 0, None),
                                       np.clip(hi - med, 0, None)],
                        fmt="none", ecolor=c, alpha=0.75, capsize=2, lw=1.0)
            out_rows.extend([[scenario, key, metric, basis, r["round"],
                              r["n_total"], r["n_observed"],
                              r["n_in_summary"], r["n_faulted_cumulative"],
                              r["median"], r["q25"], r["q75"],
                              r["boot_ci_lo"], r["boot_ci_hi"]]
                             for r in sel])
        ax.set_xlabel("campaign round")
        ax.set_ylabel(lab)
        if not drew:
            ax.set_visible(False)
            continue
        if metric.endswith("pct") or metric.endswith("_M"):
            ax.set_yscale("log")
    # active-sample step on the first visible panel
    first = axes[0]
    ref = sorted((r for r in rows if r["strategy"] == strategies[0]
                  and r["metric"] == panels[0][0]), key=lambda r: r["round"])
    if ref:
        ax2 = first.twinx()
        ax2.step([r["round"] for r in ref], [r["n_in_summary"] for r in ref],
                 where="mid", color="0.45", lw=1.2, ls=":")
        ax2.set_ylabel(f"n active (of {ref[0]['n_total']})", color="0.45",
                       fontsize=8, labelpad=1)
        ax2.set_ylim(0, max(r["n_total"] for r in ref) * 1.15)
        ax2.tick_params(axis="y", colors="0.45", labelsize=7, pad=1)
    first.legend(fontsize=8, frameon=False)
    basis_note = ("last observation carried forward - constant n"
                  if basis == "locf"
                  else "observed campaigns only - n shrinks after a fault")
    fig.suptitle(f"{scenario}: median, IQR band and bootstrap 95% CI "
                 f"({basis_note})")
    # the first panel carries a twin axis; without extra horizontal padding
    # its labels collide with the next panel's y-axis
    fig.tight_layout(w_pad=2.6, rect=(0, 0, 1, 0.94))
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["scenario", "strategy", "metric", "basis", "round", "n_total",
          "n_observed", "n_in_summary", "n_faulted_cumulative", "median",
          "q25", "q75", "boot_ci_lo", "boot_ci_hi"], out_rows)


def figure_model_probability_reliability(prob_rows: List[Dict], scenario: str,
                                         path: str,
                                         truth_in_family: bool = True,
                                         tracked: str = "") -> None:
    """Model probability vs round with the UNRELIABLE-EVIDENCE rounds shaded.

    A Laplace evidence evaluated at a parameter resting on a box bound is
    not a valid evidence, so the probabilities derived from it are not
    valid probabilities.  They are still plotted - hiding them would be its
    own distortion - but every round where any candidate's evidence was
    flagged unreliable is shaded, and the legend says so.  Nothing inside a
    shaded span may be quoted as evidence for a model.

    When the truth is OUTSIDE the candidate family the tracked curve cannot
    be 'P(correct model)' - there is no correct model in the family.  The
    axis is then labelled by what is actually being tracked, so S4c reads
    'probability of the reversible candidate' rather than claiming a
    correctness the scenario is designed to deny."""
    rows = [r for r in prob_rows if r["scenario"] == scenario]
    if not rows:
        return
    strategies = sorted({r["strategy"] for r in rows})
    fig, axes = plt.subplots(1, max(len(strategies), 1),
                             figsize=(5.4 * max(len(strategies), 1), 4.2),
                             squeeze=False)
    out = []
    for si, strat in enumerate(strategies):
        ax = axes[0][si]
        srows = [r for r in rows if r["strategy"] == strat]
        models = sorted({r["model"] for r in srows})
        rounds = sorted({r["round"] for r in srows})
        # shade rounds where ANY seed reported unreliable evidence
        for rnd in rounds:
            rr = [r for r in srows if r["round"] == rnd]
            n_bad = sum(1 for r in rr if not int(r["probs_reliable_all_models"]))
            if n_bad:
                ax.axvspan(rnd - 0.5, rnd + 0.5, color="#c0504d",
                           alpha=0.10 + 0.14 * min(n_bad / max(len(rr), 1), 1.0),
                           lw=0)
        for mi, m in enumerate(models):
            xs, ys, ns = [], [], []
            for rnd in rounds:
                vals = [float(r["probability"]) for r in srows
                        if r["round"] == rnd and r["model"] == m]
                if vals:
                    xs.append(rnd)
                    ys.append(float(np.median(vals)))
                    ns.append(len(vals))
            if not xs:
                continue
            style = "-" if m == tracked else "--"
            ax.plot(xs, ys, style, marker="o", ms=4, lw=1.8 if m == tracked
                    else 1.2, label=m)
            out.extend([[scenario, strat, m, x, y, n]
                        for x, y, n in zip(xs, ys, ns)])
        ax.set_ylim(-0.02, 1.02)
        ax.set_xlabel("campaign round")
        ax.set_ylabel("posterior model probability (median over seeds)")
        ax.set_title(strat, fontsize=10)
        ax.axhline(1.0, color="0.7", lw=0.6, ls=":")
        handles, labels = ax.get_legend_handles_labels()
        handles.append(plt.Rectangle((0, 0), 1, 1, fc="#c0504d", alpha=0.2))
        labels.append("evidence flagged UNRELIABLE\n(bound-limited Laplace)")
        ax.legend(handles, labels, fontsize=7, frameon=False, loc="best")
    claim = (f"probability of the tracked candidate '{tracked}'"
             if not truth_in_family and tracked
             else "probability of the correct model")
    caveat = ("" if truth_in_family else
              "\nTRUTH IS OUTSIDE THE CANDIDATE FAMILY: probability 1 here "
              "means the best AVAILABLE model, not a correct one")
    fig.suptitle(f"{scenario}: {claim}{caveat}", fontsize=9.5)
    fig.tight_layout(rect=(0, 0, 1, 0.90 if caveat else 0.94))
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["scenario", "strategy", "model", "round", "median_probability",
          "n_seeds"], out)


def figure_nmr_examples(spectra, path: str,
                        ppm_window: Tuple[float, float] = (0.5, 5.5)) -> None:
    """Observed / fitted / residual with the fitted species components, for
    the three representative compositions (nmr_examples.py).

    The residual gets its own panel row at a shared scale: a deconvolution
    is only as trustworthy as its residual is structureless, and plotting it
    on the same axis as the spectrum would hide exactly the structure worth
    seeing."""
    n = len(spectra)
    if not n:
        return
    fig, axes = plt.subplots(2, n, figsize=(5.6 * n, 6.2), squeeze=False,
                             gridspec_kw={"height_ratios": [3, 1]},
                             sharex="col")
    for j, (name, ppm, obs, fit, resid, comps) in enumerate(spectra):
        top, bot = axes[0][j], axes[1][j]
        top.plot(ppm, obs, lw=1.0, color="0.25", label="observed")
        top.plot(ppm, fit, lw=1.2, color="#a23b2e", label="fitted")
        for sp, c in comps.items():
            if sp in ("baseline", "exchange_pool"):
                continue
            top.plot(ppm, c, lw=0.9, alpha=0.75, ls="--", label=sp)
        top.set_title(name.replace("_", " "), fontsize=10)
        top.set_ylabel("intensity / a.u.")
        top.invert_xaxis()
        top.legend(fontsize=7, frameon=False, ncol=2)
        bot.plot(ppm, resid, lw=0.9, color="#2a7f62")
        bot.axhline(0.0, color="0.6", lw=0.6)
        bot.set_ylabel("residual")
        bot.set_xlabel("chemical shift / ppm")
        bot.invert_xaxis()
        if ppm_window:
            top.set_xlim(ppm_window[1], ppm_window[0])
    fig.suptitle("Representative simulated 80 MHz spectra, deconvolution fit "
                 "and residual (fixed example seed, generated after the run)")
    _save(fig, path)


def figure_pareto_labeled(points: Dict[str, Dict[str, float]], path: str,
                          axes_keys=(("egda_mol", "EGDA consumed / mol"),
                                     ("time_s", "campaign time / s"),
                                     ("nmr_acquisitions", "NMR acquisitions"),
                                     ("energy_kJ", "energy proxy / kJ"))
                          ) -> None:
    """Resource frontier with a distinct marker AND an inline label per
    strategy - the S6 sweep puts six near-identical colours on one axis,
    where colour alone is not a usable encoding."""
    keys = list(points)
    fig, axs = plt.subplots(1, len(axes_keys),
                            figsize=(4.6 * len(axes_keys), 4.2))
    axs = np.atleast_1d(axs)
    rows = []
    for i, key in enumerate(keys):
        pt = points[key]
        mk = _PARETO_MARKERS[i % len(_PARETO_MARKERS)]
        for j, (rk, lab) in enumerate(axes_keys):
            if rk not in pt:
                continue
            axs[j].scatter(pt[rk], pt["blind_rmse_M"], s=110, marker=mk,
                           c=STRAT_COLOR.get(key, "#333333"),
                           edgecolors="white", linewidths=0.8,
                           zorder=3, label=key if j == 0 else None)
            axs[j].annotate(key, (pt[rk], pt["blind_rmse_M"]),
                            textcoords="offset points", xytext=(7, 4),
                            fontsize=7.5, color="0.25")
            axs[j].set_xlabel(lab)
            axs[j].set_yscale("log")
            axs[j].grid(alpha=0.25)
            axs[j].set_axisbelow(True)
        rows.append([key] + [pt.get(rk, float("nan")) for rk, _ in axes_keys]
                    + [pt["blind_rmse_M"]])
    axs[0].set_ylabel("blind RMSE / M  (lower is better)")
    axs[0].legend(fontsize=8, frameon=False, loc="best")
    fig.suptitle("Resource frontier - marker and label per strategy")
    _save(fig, path)
    _csv(path.replace(".png", ".csv"),
         ["strategy"] + [rk for rk, _ in axes_keys] + ["blind_rmse_M"], rows)
