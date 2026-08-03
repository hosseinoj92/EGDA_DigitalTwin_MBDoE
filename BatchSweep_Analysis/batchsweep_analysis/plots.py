from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .io import write_csv


COLORS = {"H2SO4": "#1f77b4", "NaOH": "#d95f02"}
MARKERS = {"A": "o", "B": "s"}


def _finish(fig: plt.Figure, directory: Path, name: str, data: list[dict[str, Any]], *, tight: bool = True) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    write_csv(directory / f"{name}.csv", data)
    if tight:
        fig.tight_layout()
    fig.savefig(directory / f"{name}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def create_figures(
    rows: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    main_effects: list[dict[str, Any]],
    pareto: list[dict[str, Any]],
    peaks: list[dict[str, Any]],
    regime_summary: list[dict[str, Any]],
    directory: Path,
) -> list[str]:
    created: list[str] = []

    study_coverage = [row for row in coverage if row.get("record_type") == "study"]
    fig, ax = plt.subplots(figsize=(7, 4))
    labels = [f"{row['catalyst']} / {row['geometry']}" for row in study_coverage]
    counts = [int(row["loaded_scenarios"]) for row in study_coverage]
    bars = ax.bar(labels, counts, color=[COLORS[row["catalyst"]] for row in study_coverage])
    ax.bar_label(bars)
    ax.set_ylabel("Loaded scenarios")
    ax.set_title("Batch-sweep coverage")
    ax.tick_params(axis="x", rotation=20)
    _finish(fig, directory, "coverage_by_study", study_coverage)
    created.append("coverage_by_study")

    collapse_data = [
        {name: row[name] for name in ("scenario_id", "catalyst", "geometry", "Da1", "X_EGDA", "Y_EGMA", "Y_EG", "S_EGMA")}
        for row in rows
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    for ax, response in zip(axes.ravel(), ("X_EGDA", "Y_EGMA", "S_EGMA", "Y_EG")):
        for catalyst in ("H2SO4", "NaOH"):
            for geometry in ("A", "B"):
                subset = [row for row in collapse_data if row["catalyst"] == catalyst and row["geometry"] == geometry]
                ax.scatter([row["Da1"] for row in subset], [row[response] for row in subset], s=8, alpha=0.32,
                           c=COLORS[catalyst], marker=MARKERS[geometry], label=f"{catalyst} / {geometry}")
        ax.set_xscale("log")
        ax.set_xlabel("Da₁")
        ax.set_ylabel(response)
        ax.grid(alpha=0.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.01), ncol=4, fontsize=8)
    fig.suptitle("Dimensionless response and geometry-collapse diagnostic", y=1.07)
    _finish(fig, directory, "dimensionless_response_collapse", collapse_data)
    created.append("dimensionless_response_collapse")

    unique_components: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in main_effects:
        if row.get("method") == "exact_balanced_functional_anova" and row.get("response") == "Y_EGMA":
            key = (row["catalyst"], row["geometry"], row["response"], row["factor"])
            unique_components[key] = row
    effects_data = [
        {
            "catalyst": key[0], "geometry": key[1], "response": key[2], "factor": key[3],
            "contribution_fraction": value["contribution_fraction"], "component_variance": value["component_variance"],
        }
        for key, value in sorted(unique_components.items())
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharey=True)
    for ax, ((catalyst, geometry), group) in zip(axes.ravel(), sorted(_study_groups(effects_data).items())):
        group = sorted(group, key=lambda item: item["contribution_fraction"], reverse=True)
        ax.barh([item["factor"] for item in group][::-1], [item["contribution_fraction"] for item in group][::-1], color=COLORS[catalyst])
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("Fraction of Y_EGMA variance")
        ax.grid(axis="x", alpha=0.2)
    fig.suptitle("Exact functional-ANOVA main effects")
    _finish(fig, directory, "main_effects_yegma", effects_data)
    created.append("main_effects_yegma")

    fig, ax = plt.subplots(figsize=(7, 5))
    for catalyst in ("H2SO4", "NaOH"):
        for geometry in ("A", "B"):
            subset = [row for row in pareto if row["catalyst"] == catalyst and row["geometry"] == geometry]
            ax.scatter([row["Y_EGMA"] for row in subset], [row["STY_EGMA_mol_Lreactor_h"] for row in subset],
                       s=22, alpha=0.7, c=COLORS[catalyst], marker=MARKERS[geometry], label=f"{catalyst} / {geometry}")
    ax.set_xlabel("EGMA yield")
    ax.set_ylabel("EGMA STY [mol L-reactor⁻¹ h⁻¹]")
    ax.set_title("Exact multi-objective Pareto scenarios")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
    _finish(fig, directory, "pareto_yield_vs_sty", pareto)
    created.append("pareto_yield_vs_sty")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, catalyst in zip(axes, ("H2SO4", "NaOH")):
        for geometry in ("A", "B"):
            subset = [row for row in peaks if row["catalyst"] == catalyst and row["geometry"] == geometry]
            ax.scatter([row["x_peak_over_L"] for row in subset], [row["Y_EGMA_peak"] for row in subset],
                       s=8, alpha=0.35, marker=MARKERS[geometry], label=f"geometry {geometry}")
        ax.set_title(catalyst)
        ax.set_xlabel("Peak position x/L")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Peak EGMA yield")
    fig.suptitle("Axial EGMA peak location")
    _finish(fig, directory, "axial_egma_peak_location", peaks)
    created.append("axial_egma_peak_location")

    regimes = sorted({row["primary_regime"] for row in regime_summary})
    studies = sorted({(row["catalyst"], row["geometry"]) for row in regime_summary})
    fig, ax = plt.subplots(figsize=(9, 5))
    bottoms = np.zeros(len(studies))
    for regime in regimes:
        values = np.array([next((row["scenario_count"] for row in regime_summary if (row["catalyst"], row["geometry"]) == study and row["primary_regime"] == regime), 0) for study in studies])
        ax.bar([f"{a}/{b}" for a, b in studies], values, bottom=bottoms, label=regime)
        bottoms += values
    ax.set_ylabel("Scenario count")
    ax.set_title("Rule-based operating regimes")
    ax.legend(fontsize=7, bbox_to_anchor=(1.02, 1), loc="upper left")
    _finish(fig, directory, "regime_counts", regime_summary)
    created.append("regime_counts")

    heatmap_data: list[dict[str, Any]] = []
    for (catalyst, geometry), group in sorted(_study_groups(rows).items()):
        buckets: dict[tuple[float, float], list[float]] = defaultdict(list)
        for row in group:
            buckets[(float(row["temp_C"]), float(row["Q_total_mL_min"]))].append(float(row["Y_EGMA"]))
        for (temperature, flow), values in sorted(buckets.items()):
            heatmap_data.append({"catalyst": catalyst, "geometry": geometry, "temp_C": temperature, "Q_total_mL_min": flow, "mean_Y_EGMA": float(np.mean(values)), "aggregation_count": len(values)})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for ax, ((catalyst, geometry), group) in zip(axes.ravel(), sorted(_study_groups(heatmap_data).items())):
        temperatures = sorted({row["temp_C"] for row in group})
        flows = sorted({row["Q_total_mL_min"] for row in group})
        matrix = np.array([[next(row["mean_Y_EGMA"] for row in group if row["temp_C"] == temperature and row["Q_total_mL_min"] == flow) for flow in flows] for temperature in temperatures])
        def edges(values: list[float]) -> np.ndarray:
            values_array = np.asarray(values, dtype=float)
            if len(values_array) == 1:
                return np.array([values_array[0] - 0.5, values_array[0] + 0.5])
            midpoints = (values_array[:-1] + values_array[1:]) / 2.0
            return np.concatenate(([values_array[0] - (midpoints[0] - values_array[0])], midpoints, [values_array[-1] + (values_array[-1] - midpoints[-1])]))
        image = ax.pcolormesh(edges(flows), edges(temperatures), matrix, shading="flat", cmap="viridis")
        ax.set_title(f"{catalyst} / geometry {geometry}")
        ax.set_xlabel("Total flow [mL min⁻¹]")
        ax.set_ylabel("Temperature [°C]")
        ax.set_xticks(flows)
        ax.set_yticks(temperatures)
        fig.colorbar(image, ax=ax, label="Mean EGMA yield")
    fig.suptitle("Mean EGMA yield over concentration combinations")
    _finish(fig, directory, "temperature_flow_response", heatmap_data, tight=False)
    created.append("temperature_flow_response")

    validity_data: list[dict[str, Any]] = []
    for (catalyst, geometry), group in sorted(_study_groups(rows).items()):
        counts = defaultdict(int)
        for row in group:
            counts[row["pfr_advisory"]] += 1
        for advisory, count in sorted(counts.items()):
            validity_data.append({"catalyst": catalyst, "geometry": geometry, "pfr_advisory": advisory, "scenario_count": count})
    advisories = sorted({row["pfr_advisory"] for row in validity_data})
    fig, ax = plt.subplots(figsize=(9, 5))
    studies = sorted({(row["catalyst"], row["geometry"]) for row in validity_data})
    bottoms = np.zeros(len(studies))
    for advisory in advisories:
        values = np.array([next((row["scenario_count"] for row in validity_data if (row["catalyst"], row["geometry"]) == study and row["pfr_advisory"] == advisory), 0) for study in studies])
        ax.bar([f"{a}/{b}" for a, b in studies], values, bottom=bottoms, label=advisory)
        bottoms += values
    ax.set_ylabel("Scenario count")
    ax.set_title("Ideal-PFR transport diagnostics")
    ax.legend(fontsize=7, bbox_to_anchor=(1.02, 1), loc="upper left")
    _finish(fig, directory, "pfr_validity_diagnostics", validity_data)
    created.append("pfr_validity_diagnostics")
    return created


def _study_groups(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["catalyst"]), str(row["geometry"]))].append(row)
    return dict(grouped)
