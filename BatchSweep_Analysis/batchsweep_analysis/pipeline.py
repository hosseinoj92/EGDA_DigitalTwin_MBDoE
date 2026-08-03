from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .io import discover, write_csv, write_json
from .physics import assign_regime, enrich
from .plots import create_figures
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


def run_analysis(source_root: Path, output_root: Path, config: dict[str, Any]) -> dict[str, Any]:
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

    raw_rows, profiles, excluded, duplicates = discover(source_root)
    if not raw_rows:
        raise RuntimeError("No valid scenarios were discovered.")
    rows = [enrich(row, profiles[row["scenario_id"]], config) for row in raw_rows]
    rows.sort(key=lambda row: (row["catalyst"], row["geometry"], row["temp_C"], row["C_catalyst_feed_M"], row["C_EGDA_feed_M"], row["Q_total_mL_min"], row["scenario_id"]))

    coverage = _coverage(rows, excluded, duplicates)
    main_effects, interaction_effects = functional_anova(rows)
    elasticities = local_elasticities(rows)
    surrogate = surrogate_validation(rows)
    assignments = [assign_regime(row, config) for row in rows]
    regimes = regime_summary(assignments)
    collapse = geometry_collapse(rows)
    pareto = pareto_front(rows, config)
    top = top_conditions(rows, int(config["top_conditions_per_study"]))
    robust = robust_windows(rows, config)
    invalid = _invalid_records(rows, excluded)
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

    raw_fields = list(raw_rows[0].keys())
    for row in raw_rows[1:]:
        raw_fields.extend(key for key in row if key not in raw_fields)
    derived_exclude = set(raw_fields) - {"scenario_id", "catalyst", "geometry", "relative_path"}
    derived_rows = [{key: value for key, value in row.items() if key not in derived_exclude} for row in rows]
    write_csv(output_root / "consolidated_scenarios.csv", raw_rows, raw_fields)
    write_csv(output_root / "derived_metrics.csv", derived_rows)
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

    runtime_config = dict(config)
    runtime_config.update({
        "source_root": str(source_root),
        "output_root": str(output_root),
        "loaded_scenarios": len(rows),
        "excluded_scenarios": len(excluded),
        "source_results_are_read_only": True,
    })
    write_json(output_root / "analysis_config.json", runtime_config)
    figures = create_figures(rows, coverage, main_effects, pareto, peaks, regimes, output_root / "figures")
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
        "robust_window_scenarios": len(robust),
        "figures": figures,
    }
    write_json(output_root / "analysis_manifest.json", manifest)
    return manifest

