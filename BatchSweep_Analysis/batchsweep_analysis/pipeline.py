from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .io import discover, write_csv, write_json
from .physics import assign_regime, enrich
from .plots import create_figures
from .progress import progress
from .report import build_report
from .statistics import (
    FACTORS,
    functional_anova,
    geometry_collapse,
    local_elasticities,
    pareto_front,
    regime_summary,
    robust_windows,
    surrogate_validation,
    top_conditions,
)


def _coverage(rows: list[dict[str, Any]], excluded: list[dict[str, Any]], duplicates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = [{
        "record_type": "overall",
        "loaded_scenarios": len(rows),
        "excluded_scenarios": len(excluded),
        "duplicate_records": len(duplicates),
        "all_flows_linked_equal": all(bool(row["linked_equal_flows"]) for row in rows),
        "temperature_levels": "",
        "EGDA_feed_levels": "",
        "catalyst_feed_levels": "",
        "total_flow_levels": "",
        "expected_factorial_cells": "",
        "missing_factorial_cells": "",
    }]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["catalyst"], row["geometry"])].append(row)
    for (catalyst, geometry), group in sorted(grouped.items()):
        levels = {factor: sorted({row[factor] for row in group}) for factor in FACTORS}
        expected = math.prod(len(values) for values in levels.values())
        result.append({
            "record_type": "study",
            "catalyst": catalyst,
            "geometry": geometry,
            "loaded_scenarios": len(group),
            "excluded_scenarios": "",
            "duplicate_records": sum(item.get("scenario_id") in {row["scenario_id"] for row in group} for item in duplicates),
            "all_flows_linked_equal": all(bool(row["linked_equal_flows"]) for row in group),
            "temperature_levels": json.dumps(levels["temp_C"]),
            "EGDA_feed_levels": json.dumps(levels["C_EGDA_feed_M"]),
            "catalyst_feed_levels": json.dumps(levels["C_catalyst_feed_M"]),
            "total_flow_levels": json.dumps(levels["Q_total_mL_min"]),
            "expected_factorial_cells": expected,
            "missing_factorial_cells": expected - len(group),
        })
    return result


def _invalid_records(rows: list[dict[str, Any]], excluded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = [
        {**item, "scenario_id": "", "status": "excluded_from_loading", "retained_in_analysis": False}
        for item in excluded
    ]
    for row in rows:
        reasons = []
        if not row["numerically_valid"]:
            reasons.append("numerical_validation_failed")
        if row["requires_pressurization"]:
            reasons.append("requires_pressurization")
        if not row["ideal_pfr_supported"]:
            reasons.append(row["pfr_advisory"])
        if reasons:
            output.append({
                "relative_path": row["relative_path"],
                "scenario_id": row["scenario_id"],
                "reason": ";".join(reasons),
                "details": "Retained; flags are applicability/validity diagnostics, not loader failures.",
                "status": "retained_with_advisory",
                "retained_in_analysis": True,
                "catalyst": row["catalyst"],
                "geometry": row["geometry"],
            })
    return output


def run_analysis(
    source_root: Path,
    output_root: Path,
    config: dict[str, Any],
    *,
    show_progress: bool = True,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Batch-sweep root does not exist: {source_root}")
    try:
        output_root.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ValueError("Analysis output must not be placed inside the source results tree.")
    output_root.mkdir(parents=True, exist_ok=True)

    overall = progress(
        total=12,
        desc="Overall analysis",
        unit="phase",
        position=0,
        disable=not show_progress,
    )

    overall.set_description("Overall: loading and deriving metrics")
    rows: list[dict[str, Any]] = []

    def process_scenario(
        raw_row: dict[str, Any],
        profile: list[dict[str, float]],
    ) -> None:
        # Enrich immediately and let the profile fall out of scope. Retaining
        # all profiles for a 42k sweep would require millions of dictionaries
        # and several GB of memory.
        rows.append(enrich(raw_row, profile, config))

    raw_rows, profiles, excluded, duplicates = discover(
        source_root,
        show_progress=show_progress,
        on_scenario=process_scenario,
        retain_profiles=False,
    )
    if not raw_rows:
        overall.close()
        raise RuntimeError("No valid scenarios were discovered.")
    del profiles
    rows.sort(key=lambda row: (row["catalyst"], row["geometry"], row["temp_C"], row["C_catalyst_feed_M"], row["C_EGDA_feed_M"], row["Q_total_mL_min"], row["scenario_id"]))
    # Loading and physical derivation are two of the twelve reported phases.
    overall.update(2)

    raw_fields = list(raw_rows[0].keys())
    for raw_row in raw_rows[1:]:
        raw_fields.extend(key for key in raw_row if key not in raw_fields)
    del raw_rows

    overall.set_description("Overall: checking coverage")
    coverage = _coverage(rows, excluded, duplicates)
    overall.update(1)

    overall.set_description("Overall: functional ANOVA")
    main_effects, interaction_effects = functional_anova(
        rows,
        show_progress=show_progress,
        detail_cell_limit=int(config["anova_interaction_detail_row_limit"]),
    )
    overall.update(1)

    overall.set_description("Overall: local elasticities")
    elasticities = local_elasticities(
        rows,
        show_progress=show_progress,
        detail_row_limit=int(config["local_elasticity_detail_row_limit"]),
    )
    overall.update(1)

    overall.set_description("Overall: surrogate validation")
    surrogate = surrogate_validation(rows, show_progress=show_progress)
    overall.update(1)

    overall.set_description("Overall: regimes and decisions")
    assignments = [assign_regime(row, config) for row in rows]
    regimes = regime_summary(assignments)
    collapse = geometry_collapse(rows)
    pareto = pareto_front(rows, config, show_progress=show_progress)
    top = top_conditions(rows, int(config["top_conditions_per_study"]))
    robust = robust_windows(rows, config)
    invalid = _invalid_records(rows, excluded)
    overall.update(1)

    overall.set_description("Overall: preparing output tables")
    peaks = [
        {key: row[key] for key in [
            "scenario_id", "catalyst", "geometry", "temp_C", "C_EGDA_feed_M",
            "C_catalyst_feed_M", "Q_total_mL_min", "tau_s", "C_EGMA_peak_M",
            "Y_EGMA_peak", "x_peak_m", "tau_peak_s", "x_peak_over_L",
            "tau_peak_over_tau_out", "peak_is_interior", "peak_is_at_outlet",
            "remaining_length_after_peak_m", "remaining_time_after_peak_s",
            "EGMA_increasing_at_outlet", "peak95_start_x_m", "peak95_end_x_m",
            "peak95_width_m", "peak95_width_over_L", "peak95_start_tau_s",
            "peak95_end_tau_s", "peak95_width_s",
        ]}
        for row in rows
    ]

    derived_exclude = set(raw_fields) - {"scenario_id", "catalyst", "geometry", "relative_path"}
    derived_fields = [key for key in rows[0] if key not in derived_exclude]
    overall.update(1)

    overall.set_description("Overall: writing CSV files")
    write_csv(output_root / "consolidated_scenarios.csv", rows, raw_fields)
    write_csv(
        output_root / "derived_metrics.csv",
        (
            {key: row.get(key, "") for key in derived_fields}
            for row in rows
        ),
        derived_fields,
    )
    write_csv(output_root / "excluded_or_invalid_scenarios.csv", invalid, ["scenario_id", "relative_path", "catalyst", "geometry", "status", "reason", "details", "retained_in_analysis"])
    write_csv(output_root / "data_coverage.csv", coverage)
    write_csv(output_root / "duplicate_configs.csv", duplicates, ["duplicate_group", "scenario_id", "relative_path", "group_size"])
    write_csv(output_root / "main_effects.csv", main_effects)
    write_csv(output_root / "interaction_effects.csv", interaction_effects)
    write_csv(output_root / "local_elasticities.csv", elasticities)
    write_csv(output_root / "surrogate_validation.csv", surrogate)
    write_csv(output_root / "regime_assignments.csv", assignments)
    write_csv(output_root / "regime_summary.csv", regimes)
    write_csv(output_root / "axial_egma_peaks.csv", peaks)
    write_csv(output_root / "geometry_collapse_metrics.csv", collapse)
    write_csv(output_root / "pareto_front.csv", pareto)
    write_csv(output_root / "top_conditions.csv", top)
    write_csv(output_root / "robust_operating_windows.csv", robust)
    overall.update(1)

    overall.set_description("Overall: writing configuration")
    runtime_config = dict(config)
    runtime_config.update({
        "source_root": str(source_root),
        "output_root": str(output_root),
        "loaded_scenarios": len(rows),
        "excluded_scenarios": len(excluded),
        "source_results_are_read_only": True,
    })
    write_json(output_root / "analysis_config.json", runtime_config)
    overall.update(1)

    overall.set_description("Overall: generating figures")
    figures = create_figures(rows, coverage, main_effects, pareto, peaks, regimes, output_root / "figures")
    overall.update(1)

    overall.set_description("Overall: report and manifest")
    build_report(
        output_root / "analysis_report.md", source_root, rows, excluded, duplicates,
        coverage, main_effects, surrogate, regimes, pareto, robust, collapse, top, figures,
    )
    manifest = {
        "loaded_scenarios": len(rows),
        "excluded_loader_failures": len(excluded),
        "duplicate_configuration_records": len(duplicates),
        "physical_valid_scenarios": sum(bool(row["physical_valid"]) for row in rows),
        "pareto_scenarios": len(pareto),
        "pareto_methods": sorted({row["pareto_method"] for row in pareto}),
        "pareto_epsilon_by_study": {
            f"{catalyst}/{geometry}": max(
                float(row["pareto_epsilon_normalized"])
                for row in pareto
                if row["catalyst"] == catalyst and row["geometry"] == geometry
            )
            for catalyst, geometry in sorted({
                (row["catalyst"], row["geometry"]) for row in pareto
            })
        },
        "robust_window_scenarios": len(robust),
        "figures": figures,
    }
    write_json(output_root / "analysis_manifest.json", manifest)
    overall.update(1)
    overall.set_description("Overall: complete")
    overall.close()
    return manifest
