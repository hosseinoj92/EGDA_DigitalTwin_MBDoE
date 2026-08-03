from __future__ import annotations

import itertools
import math
from collections import Counter, defaultdict
from typing import Any, Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment


FACTORS = ["temp_C", "C_catalyst_feed_M", "C_EGDA_feed_M", "Q_total_mL_min"]
RESPONSES = ["X_EGDA", "Y_EGMA", "S_EGMA", "Y_EG", "STY_EGMA_mol_Lreactor_h"]


def study_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["catalyst"]), str(row["geometry"])


def _groups(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[study_key(row)].append(row)
    return dict(groups)


def functional_anova(rows: list[dict[str, Any]], responses: list[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Exact discrete Hoeffding/functional-ANOVA decomposition on balanced grids."""
    responses = responses or RESPONSES[:4]
    main_rows: list[dict[str, Any]] = []
    interaction_rows: list[dict[str, Any]] = []
    for (catalyst, geometry), group in sorted(_groups(rows).items()):
        levels = {factor: sorted({row[factor] for row in group}) for factor in FACTORS}
        combinations_expected = math.prod(len(levels[factor]) for factor in FACTORS)
        cells = Counter(tuple(row[factor] for factor in FACTORS) for row in group)
        balanced = len(group) == combinations_expected and len(cells) == combinations_expected and all(count == 1 for count in cells.values())
        for response in responses:
            values = np.array([float(row[response]) for row in group], dtype=float)
            total_variance = float(np.mean((values - np.mean(values)) ** 2))
            common = {
                "catalyst": catalyst,
                "geometry": geometry,
                "response": response,
                "n_scenarios": len(group),
                "balanced_grid": balanced,
                "total_variance": total_variance,
            }
            if not balanced:
                main_rows.append({**common, "method": "skipped_unbalanced", "factor": "", "level": "", "effect": math.nan, "component_variance": math.nan, "contribution_fraction": math.nan, "reconstruction_residual": math.nan})
                continue

            grand = float(np.mean(values))
            effects: dict[tuple[str, ...], dict[tuple[Any, ...], float]] = {}
            components: dict[tuple[str, ...], float] = {}
            for order in range(1, len(FACTORS) + 1):
                for subset in itertools.combinations(FACTORS, order):
                    subset_indices = [FACTORS.index(factor) for factor in subset]
                    effect_map: dict[tuple[Any, ...], float] = {}
                    for cell in itertools.product(*(levels[factor] for factor in subset)):
                        selected = [float(row[response]) for row in group if all(row[factor] == value for factor, value in zip(subset, cell))]
                        effect = float(np.mean(selected)) - grand
                        for proper_order in range(1, order):
                            for proper in itertools.combinations(subset, proper_order):
                                proper_cell = tuple(cell[subset.index(factor)] for factor in proper)
                                effect -= effects[proper][proper_cell]
                        effect_map[cell] = effect
                    effects[subset] = effect_map
                    component = float(np.mean(np.square(list(effect_map.values()))))
                    components[subset] = component
            reconstructed = sum(components.values())
            residual = total_variance - reconstructed
            for subset, effect_map in effects.items():
                component = components[subset]
                destination = main_rows if len(subset) == 1 else interaction_rows
                for cell, effect in effect_map.items():
                    record = {
                        **common,
                        "method": "exact_balanced_functional_anova",
                        "interaction_order": len(subset),
                        "factor": "*".join(subset),
                        "level": "|".join(str(value) for value in cell),
                        "effect": effect,
                        "component_variance": component,
                        "contribution_fraction": component / total_variance if total_variance > 0.0 else 0.0,
                        "reconstruction_residual": residual,
                    }
                    destination.append(record)
    return main_rows, interaction_rows


def local_elasticities(rows: list[dict[str, Any]], responses: list[str] | None = None) -> list[dict[str, Any]]:
    responses = responses or RESPONSES[:4]
    output: list[dict[str, Any]] = []
    for (catalyst, geometry), study in sorted(_groups(rows).items()):
        for factor in FACTORS:
            other_factors = [name for name in FACTORS if name != factor]
            slices: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
            for row in study:
                slices[tuple(row[name] for name in other_factors)].append(row)
            for fixed_values, slice_rows in slices.items():
                if len(slice_rows) < 2:
                    continue
                if factor == "temp_C":
                    ordered = sorted(slice_rows, key=lambda item: 1.0 / float(item["temperature_K"]))
                    x = np.array([1.0 / float(item["temperature_K"]) for item in ordered])
                    coordinate = "inverse_temperature_K_inv"
                else:
                    ordered = sorted(slice_rows, key=lambda item: float(item[factor]))
                    x = np.array([float(item[factor]) for item in ordered])
                    coordinate = factor
                if len(np.unique(x)) != len(x):
                    continue
                for response in responses:
                    y = np.array([float(item[response]) for item in ordered])
                    derivatives = np.gradient(y, x, edge_order=2 if len(x) >= 3 else 1)
                    for item, x_value, y_value, derivative in zip(ordered, x, y, derivatives):
                        elasticity = x_value / y_value * derivative if abs(y_value) > 1e-14 else math.nan
                        record = {
                            "scenario_id": item["scenario_id"],
                            "catalyst": catalyst,
                            "geometry": geometry,
                            "response": response,
                            "varied_factor": factor,
                            "derivative_coordinate": coordinate,
                            "coordinate_value": float(x_value),
                            "response_value": float(y_value),
                            "local_derivative": float(derivative),
                            "local_elasticity": float(elasticity),
                        }
                        record.update({f"fixed_{name}": value for name, value in zip(other_factors, fixed_values)})
                        output.append(record)
    return output


def _polynomial_design(matrix: np.ndarray) -> np.ndarray:
    columns = [np.ones(matrix.shape[0])]
    columns.extend(matrix[:, index] for index in range(matrix.shape[1]))
    columns.extend(matrix[:, index] ** 2 for index in range(matrix.shape[1]))
    columns.extend(matrix[:, left] * matrix[:, right] for left, right in itertools.combinations(range(matrix.shape[1]), 2))
    return np.column_stack(columns)


def _error_metrics(actual: np.ndarray, predicted: np.ndarray) -> tuple[float, float, float, float]:
    errors = predicted - actual
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    mae = float(np.mean(np.abs(errors)))
    denominator = float(np.sum((actual - np.mean(actual)) ** 2))
    r2 = 1.0 - float(np.sum(errors ** 2)) / denominator if denominator > 0.0 else math.nan
    return rmse, mae, r2, float(np.max(np.abs(errors)))


def surrogate_validation(rows: list[dict[str, Any]], responses: list[str] | None = None) -> list[dict[str, Any]]:
    responses = responses or RESPONSES[:4]
    output: list[dict[str, Any]] = []
    for (catalyst, geometry), group in sorted(_groups(rows).items()):
        raw = np.array([[float(row[factor]) for factor in FACTORS] for row in group])
        for response in responses:
            target = np.array([float(row[response]) for row in group])
            for held_factor_index, held_factor in enumerate(FACTORS):
                for held_level in sorted(set(raw[:, held_factor_index])):
                    test_mask = raw[:, held_factor_index] == held_level
                    train_mask = ~test_mask
                    train_x, test_x = raw[train_mask], raw[test_mask]
                    means = np.mean(train_x, axis=0)
                    scales = np.std(train_x, axis=0)
                    scales[scales == 0.0] = 1.0
                    train_design = _polynomial_design((train_x - means) / scales)
                    test_design = _polynomial_design((test_x - means) / scales)
                    coefficients, _, rank, _ = np.linalg.lstsq(train_design, target[train_mask], rcond=None)
                    predicted = test_design @ coefficients
                    rmse, mae, r2, maximum = _error_metrics(target[test_mask], predicted)
                    output.append({
                        "catalyst": catalyst,
                        "geometry": geometry,
                        "response": response,
                        "validation": "leave_one_factor_level_out",
                        "held_out_factor": held_factor,
                        "held_out_level": float(held_level),
                        "n_train": int(np.sum(train_mask)),
                        "n_test": int(np.sum(test_mask)),
                        "design_rank": int(rank),
                        "n_coefficients": train_design.shape[1],
                        "RMSE": rmse,
                        "MAE": mae,
                        "R2": r2,
                        "max_absolute_error": maximum,
                    })
    return output


def pareto_front(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    maximize = list(config["pareto_objectives"]["maximize"])
    minimize = list(config["pareto_objectives"]["minimize"])
    output: list[dict[str, Any]] = []
    for (catalyst, geometry), group in sorted(_groups(rows).items()):
        names = maximize + minimize
        transformed = np.array([
            [float(row[name]) for name in maximize] + [-float(row[name]) for name in minimize]
            for row in group
        ])
        for index, vector in enumerate(transformed):
            weakly_better = np.all(transformed >= vector - 1e-14, axis=1)
            strictly_better = np.any(transformed > vector + 1e-14, axis=1)
            weakly_better[index] = False
            if not np.any(weakly_better & strictly_better):
                row = group[index]
                output.append({
                    "scenario_id": row["scenario_id"],
                    "catalyst": catalyst,
                    "geometry": geometry,
                    "is_pareto_optimal": True,
                    **{name: row[name] for name in names},
                    **{factor: row[factor] for factor in FACTORS},
                    "C_EGDA_feed_M": row["C_EGDA_feed_M"],
                    "C_catalyst_feed_M": row["C_catalyst_feed_M"],
                })
    return output


def top_conditions(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    score_fields = [("Y_EGMA", 0.40, True), ("STY_EGMA_mol_Lreactor_h", 0.30, True), ("S_EGMA", 0.20, True), ("Y_EG", 0.10, False)]
    for (catalyst, geometry), group in sorted(_groups(rows).items()):
        scores = np.zeros(len(group))
        for name, weight, maximize in score_fields:
            values = np.array([float(row[name]) for row in group])
            span = float(np.max(values) - np.min(values))
            normalized = (values - np.min(values)) / span if span > 0.0 else np.ones(len(values))
            scores += weight * (normalized if maximize else 1.0 - normalized)
        order = np.argsort(-scores, kind="stable")[:count]
        for rank, index in enumerate(order, 1):
            row = group[int(index)]
            output.append({
                "rank": rank,
                "utility_score": float(scores[index]),
                "score_definition": "0.40*Y_EGMA + 0.30*STY + 0.20*S_EGMA + 0.10*(low Y_EG), each min-max scaled within study",
                **{name: row[name] for name in ["scenario_id", "catalyst", "geometry", *FACTORS, "C_EGDA_feed_M", "X_EGDA", "Y_EGMA", "S_EGMA", "Y_EG", "STY_EGMA_mol_Lreactor_h", "requires_pressurization", "physical_valid", "pfr_advisory"]},
            })
    return output


def robust_windows(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    limits = config["robust_window"]
    output: list[dict[str, Any]] = []
    for (catalyst, geometry), group in sorted(_groups(rows).items()):
        def base_feasible(row: dict[str, Any]) -> bool:
            return (
                float(row["X_EGDA"]) >= float(limits["min_X_EGDA"])
                and float(row["Y_EGMA"]) >= float(limits["min_Y_EGMA"])
                and float(row["S_EGMA"]) >= float(limits["min_S_EGMA"])
                and float(row["Y_EG"]) <= float(limits["max_Y_EG"])
                and float(row["temp_C"]) <= float(limits["max_temp_C"])
                and (not bool(limits["require_physical_validity"]) or bool(row["physical_valid"]))
            )

        feasible = {row["scenario_id"]: base_feasible(row) for row in group}
        max_yield = max((float(row["Y_EGMA"]) for row in group if feasible[row["scenario_id"]]), default=math.nan)
        levels = {factor: sorted({row[factor] for row in group}) for factor in FACTORS}
        lookup = {tuple(row[factor] for factor in FACTORS): row for row in group}
        for row in group:
            if not feasible[row["scenario_id"]] or not math.isfinite(max_yield):
                continue
            if float(row["Y_EGMA"]) < float(limits["near_optimal_fraction"]) * max_yield:
                continue
            key = [row[factor] for factor in FACTORS]
            neighbor_ids: list[str] = []
            for factor_index, factor in enumerate(FACTORS):
                level_index = levels[factor].index(row[factor])
                for offset in (-1, 1):
                    adjacent = level_index + offset
                    if 0 <= adjacent < len(levels[factor]):
                        neighbor_key = list(key)
                        neighbor_key[factor_index] = levels[factor][adjacent]
                        neighbor = lookup.get(tuple(neighbor_key))
                        if neighbor:
                            neighbor_ids.append(neighbor["scenario_id"])
            feasible_neighbors = sum(feasible[identifier] for identifier in neighbor_ids)
            fraction = feasible_neighbors / len(neighbor_ids) if neighbor_ids else 0.0
            if fraction >= float(limits["min_feasible_neighbor_fraction"]):
                output.append({
                    **{name: row[name] for name in ["scenario_id", "catalyst", "geometry", *FACTORS, "C_EGDA_feed_M", "X_EGDA", "Y_EGMA", "S_EGMA", "Y_EG", "STY_EGMA_mol_Lreactor_h", "physical_valid"]},
                    "study_max_feasible_Y_EGMA": max_yield,
                    "near_optimal_fraction_of_max": float(row["Y_EGMA"]) / max_yield,
                    "available_one_step_neighbors": len(neighbor_ids),
                    "feasible_one_step_neighbors": feasible_neighbors,
                    "feasible_neighbor_fraction": fraction,
                })
    return output


def geometry_collapse(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_route_geometry = _groups(rows)
    output: list[dict[str, Any]] = []
    matching_factors = ["temp_C", "C_catalyst_feed_M", "C_EGDA_feed_M"]
    for catalyst in sorted({row["catalyst"] for row in rows}):
        group_a = by_route_geometry.get((catalyst, "A"), [])
        group_b = by_route_geometry.get((catalyst, "B"), [])
        buckets_a: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        buckets_b: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in group_a:
            buckets_a[tuple(row[factor] for factor in matching_factors)].append(row)
        for row in group_b:
            buckets_b[tuple(row[factor] for factor in matching_factors)].append(row)
        for condition in sorted(set(buckets_a) & set(buckets_b)):
            left, right = buckets_a[condition], buckets_b[condition]
            costs = np.array([[abs(math.log(max(a["Da1"], 1e-300) / max(b["Da1"], 1e-300))) for b in right] for a in left])
            left_indices, right_indices = linear_sum_assignment(costs)
            for left_index, right_index in zip(left_indices, right_indices):
                a, b = left[int(left_index)], right[int(right_index)]
                output.append({
                    "catalyst": catalyst,
                    **{factor: value for factor, value in zip(matching_factors, condition)},
                    "scenario_id_A": a["scenario_id"],
                    "scenario_id_B": b["scenario_id"],
                    "Da1_A": a["Da1"],
                    "Da1_B": b["Da1"],
                    "absolute_log_Da1_distance": float(costs[left_index, right_index]),
                    "exact_Da1_match": math.isclose(float(a["Da1"]), float(b["Da1"]), rel_tol=1e-9, abs_tol=1e-12),
                    "tau_A_s": a["tau_s"],
                    "tau_B_s": b["tau_s"],
                    "X_EGDA_A": a["X_EGDA"],
                    "X_EGDA_B": b["X_EGDA"],
                    "delta_X_EGDA_B_minus_A": float(b["X_EGDA"]) - float(a["X_EGDA"]),
                    "Y_EGMA_A": a["Y_EGMA"],
                    "Y_EGMA_B": b["Y_EGMA"],
                    "delta_Y_EGMA_B_minus_A": float(b["Y_EGMA"]) - float(a["Y_EGMA"]),
                    "S_EGMA_A": a["S_EGMA"],
                    "S_EGMA_B": b["S_EGMA"],
                    "delta_S_EGMA_B_minus_A": float(b["S_EGMA"]) - float(a["S_EGMA"]),
                    "matching_method": "minimum_cost_one_to_one_on_log_Da1_within_shared_feed_and_temperature",
                })
    return output


def regime_summary(assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter((row["catalyst"], row["geometry"], row["primary_regime"]) for row in assignments)
    totals = Counter((row["catalyst"], row["geometry"]) for row in assignments)
    return [
        {
            "catalyst": catalyst,
            "geometry": geometry,
            "primary_regime": regime,
            "scenario_count": count,
            "study_count": totals[(catalyst, geometry)],
            "study_fraction": count / totals[(catalyst, geometry)],
        }
        for (catalyst, geometry, regime), count in sorted(counts.items())
    ]
