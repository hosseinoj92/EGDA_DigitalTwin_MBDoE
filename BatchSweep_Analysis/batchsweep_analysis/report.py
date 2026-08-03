from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, float):
        if not math.isfinite(value):
            return "n/a"
        return f"{value:.{digits}g}"
    return str(value)


def build_report(
    path: Path,
    source_root: Path,
    rows: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    main_effects: list[dict[str, Any]],
    surrogate: list[dict[str, Any]],
    regimes: list[dict[str, Any]],
    pareto: list[dict[str, Any]],
    robust: list[dict[str, Any]],
    collapse: list[dict[str, Any]],
    top: list[dict[str, Any]],
    figures: list[str],
) -> None:
    study_rows = [row for row in coverage if row.get("record_type") == "study"]
    lines = [
        "# Comprehensive batch-sweep analysis",
        "",
        "## Executive summary",
        "",
        f"This report analyzes **{len(rows):,} loaded scenarios** directly from the saved `run_config.json` and `profiles.csv` files under `{source_root}`. The reactor simulations were not rerun and no source result was changed.",
        "",
    ]
    if excluded:
        lines.append(f"The loader excluded **{len(excluded)}** incomplete or unreadable scenario directories; details are in `excluded_or_invalid_scenarios.csv`.")
    else:
        lines.append("All discovered scenario configurations had readable, schema-complete axial profiles; no scenario was excluded during loading.")
    lines.extend([
        f"Configuration-level duplicate records found: **{len(duplicates)}**.",
        "",
        "The strongest conclusions are physics-first: temperature and residence time enter the kinetic exposure through the Damköhler numbers; catalyst/feed stoichiometry is additionally decisive for the consumed-NaOH route; and EGMA is an intermediate, so high conversion can reduce EGMA selectivity by pushing material onward to EG.",
        "",
        "## Coverage and comparability",
        "",
        "| Route | Geometry | Cases | Temperature levels (°C) | Feed concentration levels | Catalyst levels | Total-flow levels (mL/min) |",
        "|---|---:|---:|---|---|---|---|",
    ])
    for row in study_rows:
        lines.append(f"| {row['catalyst']} | {row['geometry']} | {row['loaded_scenarios']} | {row['temperature_levels']} | {row['EGDA_feed_levels']} | {row['catalyst_feed_levels']} | {row['total_flow_levels']} |")
    lines.extend([
        "",
        "Every individual study is a complete balanced factorial grid over its own observed levels, so the discrete functional-ANOVA decomposition is exact and descriptive. Geometry A covers 25–160 °C; geometry B covers only 25–80 °C. Therefore, raw whole-grid geometry averages are not like-for-like comparisons.",
        "",
        "Both stream flows are linked and equal in every loaded scenario. Consequently, the two individual flow effects cannot be identified separately: the analysis treats their sum as the flow factor and the mixed-stream dilution remains fixed at 1:1.",
        "",
        "## Main statistical patterns",
        "",
    ])
    unique_effects: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in main_effects:
        if row.get("method") == "exact_balanced_functional_anova":
            unique_effects[(row["catalyst"], row["geometry"], row["response"], row["factor"])] = row
    for catalyst, geometry in sorted({(row["catalyst"], row["geometry"]) for row in rows}):
        candidates = [value for key, value in unique_effects.items() if key[:3] == (catalyst, geometry, "Y_EGMA")]
        if candidates:
            ordered = sorted(candidates, key=lambda item: item["contribution_fraction"], reverse=True)
            summary = ", ".join(f"{item['factor']} ({100 * float(item['contribution_fraction']):.1f}%)" for item in ordered)
            lines.append(f"- **{catalyst}, geometry {geometry}:** Y_EGMA main-effect variance fractions are {summary}. Interaction and higher-order components are reported separately and the reconstruction residual is numerical round-off.")
    lines.extend([
        "",
        "These percentages describe variation over the chosen discrete grid; they are not universal causal importance scores and should not be interpreted as p-values.",
        "",
        "The polynomial response surfaces use linear, quadratic, and all two-factor interaction terms. Validation holds out one complete factor level at a time, which is a more demanding interpolation/extrapolation check than a random split.",
        "",
    ])
    for catalyst, geometry in sorted({(row["catalyst"], row["geometry"]) for row in rows}):
        checks = [row for row in surrogate if row["catalyst"] == catalyst and row["geometry"] == geometry and row["response"] == "Y_EGMA"]
        if checks:
            finite_r2 = [float(row["R2"]) for row in checks if math.isfinite(float(row["R2"]))]
            lines.append(f"- **{catalyst}, geometry {geometry}:** median held-level-out Y_EGMA RMSE = {_fmt(median(float(row['RMSE']) for row in checks))}; median R² = {_fmt(median(finite_r2)) if finite_r2 else 'n/a'} and worst R² = {_fmt(min(finite_r2)) if finite_r2 else 'n/a'}. Negative boundary-fold R² values mean that fold is worse than predicting its held-out mean; use the surrogate only where the fold-specific errors are acceptable.")

    lines.extend(["", "## EGMA peak behavior", ""])
    for catalyst, geometry in sorted({(row["catalyst"], row["geometry"]) for row in rows}):
        subset = [row for row in rows if row["catalyst"] == catalyst and row["geometry"] == geometry]
        interior = sum(bool(row["peak_is_interior"]) for row in subset)
        outlet = sum(bool(row["peak_is_at_outlet"]) for row in subset)
        increasing = sum(bool(row["EGMA_increasing_at_outlet"]) for row in subset)
        lines.append(f"- **{catalyst}, geometry {geometry}:** {interior}/{len(subset)} scenarios have an interior concentration peak, {outlet}/{len(subset)} peak at the outlet, and {increasing}/{len(subset)} are still increasing at the outlet. Interior peaks identify conditions where a shorter residence time can preserve more EGMA before the second cleavage step.")

    lines.extend(["", "## Route-specific physics", ""])
    naoh = [row for row in rows if row["catalyst"] == "NaOH"]
    acid = [row for row in rows if row["catalyst"] == "H2SO4"]
    if naoh:
        exhausted = sum(float(row["OH_residual_fraction"]) <= 0.01 for row in naoh)
        substoich = sum(float(row["R_OH"]) < 1.0 for row in naoh)
        lines.append(f"- **NaOH:** hydroxide is a consumed stoichiometric reagent, not a conserved catalyst. {substoich}/{len(naoh)} cases start below one OH equivalent per EGDA and {exhausted}/{len(naoh)} finish with ≤1% of inlet OH remaining. `R_OH`, residual OH, utilization, and stoichiometric ceilings should be considered alongside Damköhler numbers.")
    if acid:
        near_eq = sum(max(float(row["Q1_over_K1_out"]), float(row["Q2_over_K2_out"]), float(row["X_over_Xeq"])) >= 0.9 for row in acid)
        lines.append(f"- **H₂SO₄:** the saved model uses reversible hydrolysis/esterification and conserves acid as a catalyst. {near_eq}/{len(acid)} cases reach at least 90% on one outlet equilibrium-proximity indicator. Q/K values distinguish equilibrium limitation from insufficient kinetic exposure.")

    lines.extend(["", "## Pareto sets, top conditions, and robust windows", ""])
    pareto_counts = Counter((row["catalyst"], row["geometry"]) for row in pareto)
    robust_counts = Counter((row["catalyst"], row["geometry"]) for row in robust)
    for catalyst, geometry in sorted({(row["catalyst"], row["geometry"]) for row in rows}):
        first = next((row for row in top if row["catalyst"] == catalyst and row["geometry"] == geometry and int(row["rank"]) == 1), None)
        description = ""
        if first:
            pressure_note = " This point requires pressurization under the configured temperature screen." if bool(first["requires_pressurization"]) else ""
            description = f" The highest transparent screening score has T={_fmt(first['temp_C'])} °C, total flow={_fmt(first['Q_total_mL_min'])} mL/min, feed EGDA={_fmt(first['C_EGDA_feed_M'])} M, catalyst={_fmt(first['C_catalyst_feed_M'])} M, Y_EGMA={_fmt(first['Y_EGMA'])}, and STY={_fmt(first['STY_EGMA_mol_Lreactor_h'])} mol L-reactor⁻¹ h⁻¹.{pressure_note}"
        lines.append(f"- **{catalyst}, geometry {geometry}:** {pareto_counts[(catalyst, geometry)]} exact Pareto scenarios and {robust_counts[(catalyst, geometry)]} threshold/neighbor-robust scenarios.{description}")
    lines.extend([
        "",
        "The top-condition score is explicitly a screening preference, not a fitted optimum. The exact Pareto table is the appropriate output when objective weights are not agreed; because seven objectives are used, a large nondominated set is expected and should be narrowed only after priorities are chosen. Robust-window membership depends on the thresholds recorded in `analysis_config.json`.",
        "",
        "## Geometry-collapse assessment",
        "",
    ])
    if collapse:
        exact = sum(bool(row["exact_Da1_match"]) for row in collapse)
        distances = [float(row["absolute_log_Da1_distance"]) for row in collapse]
        yield_residuals = [abs(float(row["delta_Y_EGMA_B_minus_A"])) for row in collapse]
        lines.append(f"There are {len(collapse)} one-to-one cross-geometry matches at common route, temperature, and feed concentrations. Only {exact} are exact Da₁ matches; the median |log(Da₁,B/Da₁,A)| is {_fmt(median(distances))}, and the median absolute paired EGMA-yield difference is {_fmt(median(yield_residuals))}.")
        lines.append("")
        lines.append("Because the existing flow ranges do not generally give equal residence time or Da₁ in the two geometries, this is a nearest-dimensionless-exposure diagnostic, not proof of a geometry effect. A dedicated matched-Da experiment would be required for a clean collapse test.")
    else:
        lines.append("No shared route/temperature/feed conditions were available for a geometry-collapse comparison.")

    advisory_counts = Counter(row["pfr_advisory"] for row in rows)
    pressure_count = sum(bool(row["requires_pressurization"]) for row in rows)
    lines.extend([
        "",
        "## Model-validity and interpretation limits",
        "",
        f"Transport advisories across all scenarios: {', '.join(f'{key}={value}' for key, value in sorted(advisory_counts.items()))}. Conditions above the configured atmospheric-boiling screen occur in {pressure_count}/{len(rows)} cases.",
        "",
        "- The simulated reactor is an empty, ideal homogeneous tube. It is **not** a bead-packed bed; no porosity, tortuosity, pressure drop, external film transfer, or intraparticle diffusion is modeled.",
        "- Reynolds, radial-diffusion, Taylor–Aris, and Bodenstein diagnostics are applicability screens. They do not correct the ideal-PFR predictions.",
        "- Temperatures above 100 °C require a suitable pressurized liquid-phase setup under the default screen. The analysis flags them and does not assume such hardware exists.",
        "- H₂SO₄ Ka₂ temperature/activity behavior is whatever was encoded in each saved run configuration and current simulator kinetics. This analysis does not refit Ka₂ or kinetic parameters.",
        "- The H₂SO₄ route is reversible in these configurations. The NaOH route is intentionally irreversible because saponification consumes OH and is pulled toward carboxylate products.",
        "- No experimental uncertainty, parameter uncertainty, replicate noise, or statistical sampling process is present. Therefore no significance tests, confidence intervals, or causal claims are made.",
        "- Local elasticities are finite differences on the available grid. Temperature derivatives use 1/T as requested; boundary estimates are one-sided and can be less stable.",
        "- The surrogate is an interpretable response surface, not a replacement for the mechanistic simulator and not evidence outside the swept domain.",
        "",
        "## Output guide",
        "",
        "The root CSV files contain the auditable scenario table, derivations, exclusions, factorial effects, elasticities, validation, regimes, peaks, geometry matching, Pareto sets, top conditions, and robust windows. Each PNG in `figures/` has a same-named CSV containing exactly the plotted data.",
        "",
        f"Generated figures: {', '.join(figures)}.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
