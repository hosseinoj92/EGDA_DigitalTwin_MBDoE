"""
Styled matplotlib figures for the PFR twin.

Every plotting function writes TWO files: the figure (`path`, .png) and a
sibling CSV with the same basename holding exactly the plotted data, so any
figure can be re-drawn or re-analyzed without re-running the simulation.
Each function returns the CSV path.

Design rules applied throughout (single y-axis per chart, fixed series-color
assignment, recessive grid, direct end-labels in text ink plus a frameless
legend, thin 2 px lines):

    EGDA -> blue   #2a78d6        EG   -> aqua   #1baf7a
    EGMA -> orange #eb6834        AcOH -> yellow #eda100
    OH-  -> violet #8a5cd6

Temperature-ordered overlays use a single-hue ordinal blue ramp (light to
dark = cold to hot), never a rainbow.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .reactor import PFRResult
from .runio import csv_beside, write_columns_csv

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

SERIES = {"EGDA": "#2a78d6", "EGMA": "#eb6834", "EG": "#1baf7a",
          "AcOH": "#eda100", "OH": "#8a5cd6"}
METRIC_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]          # X, Y_EGMA, Y_EG
ORDINAL_BLUES = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # cold -> hot


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


def _legend(ax):
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9, loc="best")


def _end_label(ax, x: float, y: float, text: str):
    ax.annotate(text, xy=(x, y), xytext=(5, 0), textcoords="offset points",
                va="center", ha="left", color=INK2, fontsize=9)


def _save(fig, path: str, data: Dict[str, Sequence[float]] = None) -> str:
    """Save the figure and, alongside it, the CSV of the plotted data."""
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    if data is None:
        return ""
    return write_columns_csv(csv_beside(path), data)


# ----------------------------------------------------------------------------
# Base-case figures
# ----------------------------------------------------------------------------
def plot_concentration_profiles(result: PFRResult, path: str) -> str:
    """Organic species along the reactor (water omitted: ~50 M, off-scale).
    For the reversible model, thin dashed guides mark the t->inf chemical
    equilibrium level of each species."""
    title = (f"Axial concentration profiles  -  {result.T_K - 273.15:.0f} °C, "
             f"τ = {result.residence_time_s:.0f} s")
    if result.eq_conc is not None:
        title += "  (dashed: equilibrium)"
    fig, ax = _new_axes(title, "reactor position x (m)", "concentration (mol/L)")
    x = result.x_m
    species = ["EGDA", "EGMA", "EG", "AcOH"]
    if result.catalyst == "NaOH":
        species.append("OH")        # the depleting reagent is the story here
    data = {"x_m": x, "tau_s": result.tau_s}
    for sp in species:
        y = result.conc[sp]
        label = "OH⁻" if sp == "OH" else sp
        ax.plot(x, y, color=SERIES[sp], linewidth=2, label=label)
        _end_label(ax, x[-1], y[-1], label)
        data[f"C_{sp}_mol_L"] = y
        if result.eq_conc is not None and sp != "OH":
            ax.axhline(result.eq_conc[sp], color=SERIES[sp], linewidth=1.0,
                       linestyle=(0, (4, 4)), alpha=0.45, zorder=1)
            data[f"C_{sp}_eq_mol_L"] = np.full_like(x, result.eq_conc[sp])
    ax.set_xlim(0.0, x[-1] * 1.14)
    ax.set_ylim(bottom=0.0)
    _legend(ax)
    return _save(fig, path, data)


def plot_conversion_yield(result: PFRResult, path: str) -> str:
    fig, ax = _new_axes(
        "EGDA conversion and product yields along the reactor",
        "reactor position x (m)", "fraction of fed EGDA (–)")
    x = result.x_m
    curves = [("X EGDA", result.conversion),
              ("Y EGMA", result.yield_of("EGMA")),
              ("Y EG", result.yield_of("EG"))]
    for (label, y), color in zip(curves, METRIC_COLORS):
        ax.plot(x, y, color=color, linewidth=2, label=label)
        _end_label(ax, x[-1], y[-1], label)
    ax.set_xlim(0.0, x[-1] * 1.16)
    ax.set_ylim(0.0, min(1.0, max(c[1].max() for c in curves) * 1.25 + 0.02))
    _legend(ax)
    return _save(fig, path, {"x_m": x, "tau_s": result.tau_s,
                             "X_EGDA": curves[0][1], "Y_EGMA": curves[1][1],
                             "Y_EG": curves[2][1]})


def plot_validation(result: PFRResult, analytical: Dict[str, np.ndarray],
                    path: str) -> str:
    """Numerical solution (lines) vs reference solution (hollow markers).
    The reference is the closed form on the acid route, an independent stiff
    integrator on the NaOH route."""
    ref = ("analytical" if result.catalyst == "H2SO4" else "Radau cross-check")
    fig, ax = _new_axes(
        f"Solver verification - lines: LSODA integration, markers: {ref}",
        "residence time τ (s)", "concentration (mol/L)")
    tau = result.tau_s
    every = max(1, len(tau) // 12)
    data = {"tau_s": tau}
    for sp in ("EGDA", "EGMA", "EG", "AcOH"):
        ax.plot(tau, result.conc[sp], color=SERIES[sp], linewidth=2, label=sp)
        ax.plot(tau[::every], analytical[sp][::every], linestyle="none",
                marker="o", markersize=7, markerfacecolor=SURFACE,
                markeredgecolor=SERIES[sp], markeredgewidth=1.5)
        _end_label(ax, tau[-1], result.conc[sp][-1], sp)
        data[f"C_{sp}_numerical"] = result.conc[sp]
        data[f"C_{sp}_reference"] = analytical[sp]
    ax.set_xlim(0.0, tau[-1] * 1.14)
    ax.set_ylim(bottom=0.0)
    _legend(ax)
    return _save(fig, path, data)


# ----------------------------------------------------------------------------
# Temperature-study figures
# ----------------------------------------------------------------------------
def plot_temperature_sweep(T_C: np.ndarray, X: np.ndarray,
                           Y_egma: np.ndarray, Y_eg: np.ndarray,
                           path: str) -> str:
    fig, ax = _new_axes(
        "Outlet performance vs reactor temperature",
        "temperature (°C)", "fraction of fed EGDA (–)")
    curves = [("X EGDA", X), ("Y EGMA", Y_egma), ("Y EG", Y_eg)]
    for (label, y), color in zip(curves, METRIC_COLORS):
        ax.plot(T_C, y, color=color, linewidth=2, label=label)
        _end_label(ax, T_C[-1], y[-1], label)

    i_max = int(np.argmax(Y_egma))
    if 0 < i_max < len(T_C) - 1:      # interior optimum -> annotate it
        ax.plot(T_C[i_max], Y_egma[i_max], marker="o", markersize=7,
                markerfacecolor=SURFACE, markeredgecolor=METRIC_COLORS[1],
                markeredgewidth=1.5)
        ax.annotate(f"EGMA max\n{Y_egma[i_max]:.1%} @ {T_C[i_max]:.0f} °C",
                    xy=(T_C[i_max], Y_egma[i_max]), xytext=(0, 14),
                    textcoords="offset points", ha="center",
                    color=INK2, fontsize=9)
    ax.set_xlim(T_C[0], T_C[0] + (T_C[-1] - T_C[0]) * 1.14)
    ax.set_ylim(0.0, 1.0)
    _legend(ax)
    return _save(fig, path, {"T_C": T_C, "X_EGDA": X,
                             "Y_EGMA": Y_egma, "Y_EG": Y_eg})


def plot_profile_overlay(results: Sequence[PFRResult], species: str,
                         path: str) -> str:
    """One species' axial profile at several temperatures (ordinal blue ramp).

    The paired CSV holds one column per temperature; profiles are interpolated
    onto the first result's axial grid so the columns share an x axis (all
    runs use the same geometry, so this is exact unless n_points differs)."""
    fig, ax = _new_axes(
        f"{species} axial profile - effect of temperature",
        "reactor position x (m)", f"C {species} (mol/L)")
    n = len(results)
    colors = [ORDINAL_BLUES[int(round(i * (len(ORDINAL_BLUES) - 1) / max(n - 1, 1)))]
              for i in range(n)]
    x_ref = results[0].x_m
    data = {"x_m": x_ref}
    for res, color in zip(results, colors):
        label = f"{res.T_K - 273.15:.0f} °C"
        ax.plot(res.x_m, res.conc[species], color=color, linewidth=2, label=label)
        _end_label(ax, res.x_m[-1], res.conc[species][-1], label)
        col = f"C_{species}_T{res.T_K - 273.15:.0f}C"
        data[col] = (res.conc[species] if np.array_equal(res.x_m, x_ref)
                     else np.interp(x_ref, res.x_m, res.conc[species]))
    ax.set_xlim(0.0, results[0].x_m[-1] * 1.14)
    ax.set_ylim(bottom=0.0)
    _legend(ax)
    return _save(fig, path, data)


# ----------------------------------------------------------------------------
# Batch-study figures (scenario comparison)
# ----------------------------------------------------------------------------
def plot_scenario_bars(labels: Sequence[str], metrics: Dict[str, Sequence[float]],
                       path: str, title: str = "Scenario comparison - outlet KPIs",
                       ylabel: str = "fraction of fed EGDA (–)") -> str:
    """Grouped bars: one group per scenario, one bar per metric."""
    names = list(metrics)
    n_s, n_m = len(labels), len(names)
    fig, ax = _new_axes(title, "", ylabel,
                        figsize=(max(8.0, 1.5 * n_s + 2.0), 5.2))
    width = 0.8 / max(n_m, 1)
    xpos = np.arange(n_s)
    for j, name in enumerate(names):
        ax.bar(xpos + (j - (n_m - 1) / 2) * width,
               np.asarray(metrics[name], dtype=float), width=width * 0.92,
               color=METRIC_COLORS[j % len(METRIC_COLORS)], label=name)
    ax.set_xticks(xpos)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylim(bottom=0.0)
    _legend(ax)
    data = {"scenario_index": xpos.astype(float)}
    data.update({name: np.asarray(metrics[name], dtype=float) for name in names})
    return _save(fig, path, data)


def plot_scenario_curves(labels: Sequence[str], x_values: Sequence[np.ndarray],
                         y_values: Sequence[np.ndarray], path: str,
                         title: str, xlabel: str, ylabel: str) -> str:
    """One curve per scenario on shared axes (ordinal blue ramp).

    Scenarios may have different x grids; the CSV therefore carries an
    explicit x column per scenario."""
    fig, ax = _new_axes(title, xlabel, ylabel, figsize=(8.6, 5.2))
    n = len(labels)
    colors = [ORDINAL_BLUES[int(round(i * (len(ORDINAL_BLUES) - 1) / max(n - 1, 1)))]
              for i in range(n)]
    data, longest = {}, max(len(np.atleast_1d(x)) for x in x_values)
    for i, (label, xs, ys) in enumerate(zip(labels, x_values, y_values)):
        xs, ys = np.atleast_1d(xs), np.atleast_1d(ys)
        ax.plot(xs, ys, color=colors[i], linewidth=2, label=label)
        pad = np.full(longest - len(xs), np.nan)
        data[f"x__{label}"] = np.concatenate([xs, pad])
        data[f"y__{label}"] = np.concatenate([ys, pad])
    ax.set_ylim(bottom=0.0)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=8, loc="best")
    return _save(fig, path, data)
