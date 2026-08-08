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
