"""Build the static figures embedded in BatchSweep_Analysis/README.md.

This script only reads the already-generated CSV files in ``results`` and
writes documentation PNGs to ``docs/images``.  It does not alter simulation or
analysis results.
"""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
ANALYSIS_ROOT = HERE.parent
RESULTS = ANALYSIS_ROOT / "results"
IMAGES = HERE / "images"
COLORS = {"H2SO4": "#2878B5", "NaOH": "#E87500"}
MARKERS = {"A": "o", "B": "s"}


def read(name: str) -> list[dict[str, Any]]:
    with (RESULTS / name).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [{key: convert(value) for key, value in row.items()} for row in rows]


def convert(value: str) -> Any:
    if value == "":
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    try:
        return float(value)
    except ValueError:
        return value


def grouped(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    output: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("catalyst") and row.get("geometry"):
            output[(str(row["catalyst"]), str(row["geometry"]))].append(row)
    return dict(output)


def save(fig: plt.Figure, name: str, *, constrained: bool = False) -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    if not constrained:
        fig.tight_layout()
    fig.savefig(IMAGES / f"{name}.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def study_axes(title: str, *, sharey: bool = False) -> tuple[plt.Figure, np.ndarray]:
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), sharey=sharey)
    fig.suptitle(title, fontsize=16)
    return fig, axes.ravel()


def consolidated_scenarios() -> None:
    rows = read("consolidated_scenarios.csv")
    fig, axes = study_axes("Input design represented by consolidated_scenarios.csv")
    for ax, ((catalyst, geometry), study) in zip(axes, sorted(grouped(rows).items())):
        cells = Counter((row["temp_C"], row["Q1_mL_min"] + row["Q2_mL_min"]) for row in study)
        points = sorted(cells)
        sizes = [18 + 4 * cells[point] for point in points]
        ax.scatter([point[1] for point in points], [point[0] for point in points], s=sizes,
                   color=COLORS[catalyst], alpha=0.75, edgecolor="white", linewidth=0.6)
        ax.set_title(f"{catalyst} / geometry {geometry} ({len(study)} cases)")
        ax.set_xlabel("Total flow [mL min⁻¹]")
        ax.set_ylabel("Temperature [°C]")
        ax.grid(alpha=0.2)
    fig.text(0.5, 0.005, "Bubble area is proportional to the number of feed/catalyst concentration combinations at each temperature-flow cell.", ha="center", fontsize=9)
    save(fig, "consolidated_scenarios")


def derived_metrics() -> None:
    rows = read("derived_metrics.csv")
    original = {row["scenario_id"]: row for row in read("consolidated_scenarios.csv")}
    for row in rows:
        row["Y_EGMA"] = original[row["scenario_id"]]["Y_EGMA"]
        row["temp_C"] = original[row["scenario_id"]]["temp_C"]
    fig, axes = study_axes("Dimensionless kinetic exposure from derived_metrics.csv", sharey=True)
    for ax, ((catalyst, geometry), study) in zip(axes, sorted(grouped(rows).items())):
        scatter = ax.scatter([row["Da1"] for row in study], [row["Y_EGMA"] for row in study],
                             c=[row["R_OH"] if catalyst == "NaOH" else row["temp_C"] for row in study],
                             s=10, alpha=0.45, cmap="viridis")
        ax.set_xscale("log")
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("Da₁ = κ₁τ")
        ax.set_ylabel("Outlet EGMA yield")
        ax.grid(alpha=0.2)
        fig.colorbar(scatter, ax=ax, label="R_OH" if catalyst == "NaOH" else "Temperature [°C]")
    save(fig, "derived_metrics")


def excluded_or_invalid_scenarios() -> None:
    rows = read("excluded_or_invalid_scenarios.csv")
    counts = Counter(str(row["reason"]) for row in rows)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    labels = [label.replace(";", ";\n") for label, _ in counts.most_common()]
    values = [value for _, value in counts.most_common()]
    bars = ax.barh(labels[::-1], values[::-1], color="#B24C3A")
    ax.bar_label(bars, padding=4)
    ax.set_xlabel("Retained scenarios carrying the advisory")
    ax.set_title("Validity and applicability audit from excluded_or_invalid_scenarios.csv")
    ax.grid(axis="x", alpha=0.2)
    ax.text(0.99, 0.03, "Loader exclusions = 0; all rows shown here were retained.", transform=ax.transAxes, ha="right", fontsize=9)
    save(fig, "excluded_or_invalid_scenarios")


def data_coverage() -> None:
    rows = [row for row in read("data_coverage.csv") if row["record_type"] == "study"]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels = [f"{row['catalyst']} / {row['geometry']}" for row in rows]
    expected = [row["expected_factorial_cells"] for row in rows]
    loaded = [row["loaded_scenarios"] for row in rows]
    positions = np.arange(len(rows))
    ax.bar(positions, expected, width=0.72, color="#D7DEE7", label="Expected factorial cells")
    bars = ax.bar(positions, loaded, width=0.48, color=[COLORS[str(row["catalyst"])] for row in rows], label="Loaded")
    ax.bar_label(bars)
    ax.set_xticks(positions, labels, rotation=15)
    ax.set_ylabel("Scenario count")
    ax.set_title("Complete factorial coverage documented in data_coverage.csv")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    save(fig, "data_coverage")


def duplicate_configs() -> None:
    duplicates = read("duplicate_configs.csv")
    total = len(read("consolidated_scenarios.csv"))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(["Unique loaded configurations", "Duplicate records"], [total, len(duplicates)], color=["#3A8D5D", "#B24C3A"])
    ax.bar_label(bars)
    ax.set_ylabel("Record count")
    ax.set_title("Configuration identity audit from duplicate_configs.csv")
    ax.grid(axis="y", alpha=0.2)
    save(fig, "duplicate_configs")


def main_effects() -> None:
    rows = [row for row in read("main_effects.csv") if row["response"] == "Y_EGMA"]
    fig, axes = study_axes("Exact Y_EGMA main-effect variance components", sharey=True)
    for ax, ((catalyst, geometry), study) in zip(axes, sorted(grouped(rows).items())):
        unique = {}
        for row in study:
            unique[str(row["factor"])] = row["contribution_fraction"]
        ordered = sorted(unique.items(), key=lambda item: item[1])
        ax.barh([name for name, _ in ordered], [100.0 * value for _, value in ordered], color=COLORS[catalyst])
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("Fraction of Y_EGMA variance [%]")
        ax.grid(axis="x", alpha=0.2)
    save(fig, "main_effects")


def interaction_effects() -> None:
    rows = [row for row in read("interaction_effects.csv") if row["response"] == "Y_EGMA"]
    fig, axes = study_axes("Largest Y_EGMA interaction components", sharey=False)
    for ax, ((catalyst, geometry), study) in zip(axes, sorted(grouped(rows).items())):
        unique = {}
        for row in study:
            unique[str(row["factor"])] = row["contribution_fraction"]
        ordered = sorted(unique.items(), key=lambda item: item[1], reverse=True)[:6][::-1]
        labels = [name.replace("C_catalyst_feed_M", "Ccat").replace("C_EGDA_feed_M", "CEGDA").replace("Q_total_mL_min", "Q") for name, _ in ordered]
        ax.barh(labels, [100.0 * value for _, value in ordered], color=COLORS[catalyst], alpha=0.85)
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("Fraction of Y_EGMA variance [%]")
        ax.grid(axis="x", alpha=0.2)
    save(fig, "interaction_effects")


def local_elasticities() -> None:
    rows = [row for row in read("local_elasticities.csv") if row["response"] == "Y_EGMA" and row["local_elasticity"] is not None and math.isfinite(row["local_elasticity"])]
    fig, axes = study_axes("Median absolute local elasticity of EGMA yield", sharey=True)
    for ax, ((catalyst, geometry), study) in zip(axes, sorted(grouped(rows).items())):
        buckets: dict[str, list[float]] = defaultdict(list)
        for row in study:
            buckets[str(row["varied_factor"])].append(abs(row["local_elasticity"]))
        names = list(buckets)
        values = [median(buckets[name]) for name in names]
        ax.barh(names, values, color=COLORS[catalyst])
        ax.set_xscale("log")
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("median |(x/y)·dy/dx|")
        ax.grid(axis="x", alpha=0.2)
    save(fig, "local_elasticities")


def surrogate_validation() -> None:
    rows = [row for row in read("surrogate_validation.csv") if row["response"] == "Y_EGMA"]
    fig, axes = study_axes("Leave-one-level-out EGMA surrogate error", sharey=True)
    for ax, ((catalyst, geometry), study) in zip(axes, sorted(grouped(rows).items())):
        buckets: dict[str, list[float]] = defaultdict(list)
        for row in study:
            buckets[str(row["held_out_factor"])].append(row["RMSE"])
        names = list(buckets)
        values = [median(buckets[name]) for name in names]
        ax.barh(names, values, color=COLORS[catalyst])
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("Median held-level RMSE")
        ax.grid(axis="x", alpha=0.2)
    save(fig, "surrogate_validation")


def regime_assignments() -> None:
    rows = read("regime_assignments.csv")
    flags = [
        "flag_low_conversion", "flag_overreaction_to_EG", "flag_EGMA_selective",
        "flag_interior_EGMA_peak", "flag_NaOH_exhausted",
        "flag_NaOH_stoichiometric_limit", "flag_acid_equilibrium_limit",
        "flag_physical_validity_question",
    ]
    fig, axes = study_axes("Independent physical/chemical regime flags", sharey=True)
    for ax, ((catalyst, geometry), study) in zip(axes, sorted(grouped(rows).items())):
        prevalence = [(flag.replace("flag_", ""), 100.0 * sum(bool(row[flag]) for row in study) / len(study)) for flag in flags]
        prevalence = [item for item in prevalence if item[1] > 0.0]
        ax.barh([name for name, _ in prevalence], [value for _, value in prevalence], color=COLORS[catalyst])
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("Scenarios carrying flag [%]")
        ax.grid(axis="x", alpha=0.2)
    save(fig, "regime_assignments")


def regime_summary() -> None:
    rows = read("regime_summary.csv")
    studies = sorted({(row["catalyst"], row["geometry"]) for row in rows})
    regimes = sorted({str(row["primary_regime"]) for row in rows})
    fig, ax = plt.subplots(figsize=(11, 5.5))
    bottoms = np.zeros(len(studies))
    for regime in regimes:
        values = np.array([next((row["scenario_count"] for row in rows if (row["catalyst"], row["geometry"]) == study and row["primary_regime"] == regime), 0.0) for study in studies])
        ax.bar([f"{a}/{b}" for a, b in studies], values, bottom=bottoms, label=regime)
        bottoms += values
    ax.set_ylabel("Scenario count")
    ax.set_title("Mutually exclusive primary regimes from regime_summary.csv")
    ax.legend(fontsize=8, bbox_to_anchor=(1.01, 1), loc="upper left")
    ax.grid(axis="y", alpha=0.2)
    save(fig, "regime_summary")


def axial_egma_peaks() -> None:
    rows = read("axial_egma_peaks.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    for ax, catalyst in zip(axes, ("H2SO4", "NaOH")):
        for geometry in ("A", "B"):
            subset = [row for row in rows if row["catalyst"] == catalyst and row["geometry"] == geometry]
            ax.scatter([row["x_peak_over_L"] for row in subset], [row["Y_EGMA_peak"] for row in subset], s=10, alpha=0.4, marker=MARKERS[geometry], label=f"geometry {geometry}")
        ax.set_title(catalyst)
        ax.set_xlabel("Peak position x/L")
        ax.grid(alpha=0.2)
        ax.legend()
    axes[0].set_ylabel("Peak EGMA yield")
    fig.suptitle("Axial intermediate maxima from axial_egma_peaks.csv")
    save(fig, "axial_egma_peaks")


def geometry_collapse_metrics() -> None:
    rows = read("geometry_collapse_metrics.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for catalyst in ("H2SO4", "NaOH"):
        subset = [row for row in rows if row["catalyst"] == catalyst]
        axes[0].scatter([row["Da1_A"] for row in subset], [row["Da1_B"] for row in subset], s=10, alpha=0.45, color=COLORS[catalyst], label=catalyst)
        axes[1].scatter([row["absolute_log_Da1_distance"] for row in subset], [row["delta_Y_EGMA_B_minus_A"] for row in subset], s=10, alpha=0.4, color=COLORS[catalyst], label=catalyst)
    all_da = [row[key] for row in rows for key in ("Da1_A", "Da1_B")]
    low, high = min(all_da), max(all_da)
    axes[0].plot([low, high], [low, high], color="0.25", linewidth=1, label="exact match")
    axes[0].set_xscale("log"); axes[0].set_yscale("log")
    axes[0].set_xlabel("Da₁, geometry A"); axes[0].set_ylabel("Da₁, geometry B")
    axes[0].set_title("Dimensionless matching quality")
    axes[1].axhline(0.0, color="0.25", linewidth=1)
    axes[1].set_xlabel("|log(Da₁,B/Da₁,A)|"); axes[1].set_ylabel("Y_EGMA,B − Y_EGMA,A")
    axes[1].set_title("Yield residual versus match distance")
    for ax in axes:
        ax.grid(alpha=0.2); ax.legend()
    fig.suptitle("Nearest-exposure geometry comparison from geometry_collapse_metrics.csv")
    save(fig, "geometry_collapse_metrics")


def pareto_front() -> None:
    rows = read("pareto_front.csv")
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for catalyst in ("H2SO4", "NaOH"):
        for geometry in ("A", "B"):
            subset = [row for row in rows if row["catalyst"] == catalyst and row["geometry"] == geometry]
            ax.scatter([row["Y_EGMA"] for row in subset], [row["STY_EGMA_mol_Lreactor_h"] for row in subset], s=18, alpha=0.6, color=COLORS[catalyst], marker=MARKERS[geometry], label=f"{catalyst}/{geometry}")
    ax.set_xlabel("EGMA yield"); ax.set_ylabel("EGMA STY [mol L-reactor⁻¹ h⁻¹]")
    ax.set_yscale("log")
    ax.set_title("Nondominated scenarios retained in pareto_front.csv")
    ax.grid(alpha=0.2); ax.legend()
    save(fig, "pareto_front")


def top_conditions() -> None:
    rows = read("top_conditions.csv")
    fig, axes = study_axes("Ranked screening conditions from top_conditions.csv")
    for ax, ((catalyst, geometry), study) in zip(axes, sorted(grouped(rows).items())):
        scatter = ax.scatter([row["Y_EGMA"] for row in study], [row["STY_EGMA_mol_Lreactor_h"] for row in study], c=[row["rank"] for row in study], cmap="viridis_r", s=55)
        for row in study:
            ax.annotate(str(int(row["rank"])), (row["Y_EGMA"], row["STY_EGMA_mol_Lreactor_h"]), fontsize=7, xytext=(3, 2), textcoords="offset points")
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("EGMA yield"); ax.set_ylabel("STY [mol L-reactor⁻¹ h⁻¹]")
        ax.grid(alpha=0.2)
        fig.colorbar(scatter, ax=ax, label="rank")
    save(fig, "top_conditions")


def robust_operating_windows() -> None:
    rows = read("robust_operating_windows.csv")
    fig, axes = study_axes("Threshold- and neighbor-robust operating points")
    for ax, study_key in zip(axes, [("H2SO4", "A"), ("H2SO4", "B"), ("NaOH", "A"), ("NaOH", "B")]):
        catalyst, geometry = study_key
        study = [row for row in rows if row["catalyst"] == catalyst and row["geometry"] == geometry]
        if study:
            scatter = ax.scatter([row["Q_total_mL_min"] for row in study], [row["temp_C"] for row in study], c=[row["Y_EGMA"] for row in study], s=[30 + 90 * row["feasible_neighbor_fraction"] for row in study], cmap="viridis", alpha=0.8)
            fig.colorbar(scatter, ax=ax, label="Y_EGMA")
        else:
            ax.text(0.5, 0.5, "No points satisfy\nthe configured window", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"{catalyst} / geometry {geometry} ({len(study)})")
        ax.set_xlabel("Total flow [mL min⁻¹]"); ax.set_ylabel("Temperature [°C]")
        ax.grid(alpha=0.2)
    save(fig, "robust_operating_windows")


BUILDERS = {
    "consolidated_scenarios": consolidated_scenarios,
    "derived_metrics": derived_metrics,
    "excluded_or_invalid_scenarios": excluded_or_invalid_scenarios,
    "data_coverage": data_coverage,
    "duplicate_configs": duplicate_configs,
    "main_effects": main_effects,
    "interaction_effects": interaction_effects,
    "local_elasticities": local_elasticities,
    "surrogate_validation": surrogate_validation,
    "regime_assignments": regime_assignments,
    "regime_summary": regime_summary,
    "axial_egma_peaks": axial_egma_peaks,
    "geometry_collapse_metrics": geometry_collapse_metrics,
    "pareto_front": pareto_front,
    "top_conditions": top_conditions,
    "robust_operating_windows": robust_operating_windows,
}


def main() -> None:
    for name, builder in BUILDERS.items():
        builder()
        print(f"wrote docs/images/{name}.png")


if __name__ == "__main__":
    main()
