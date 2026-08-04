from __future__ import annotations

import itertools
import math
from collections import Counter, defaultdict
from typing import Any, Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment

from .progress import progress

try:
    from numba import njit
except ImportError:  # pragma: no cover - exercised only without optional numba
    njit = None


FACTORS = ["temp_C", "C_catalyst_feed_M", "C_EGDA_feed_M", "Q_total_mL_min"]
RESPONSES = ["X_EGDA", "Y_EGMA", "S_EGMA", "Y_EG", "STY_EGMA_mol_Lreactor_h"]


def study_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["catalyst"]), str(row["geometry"])


def _groups(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[study_key(row)].append(row)
    return dict(groups)


def functional_anova(
    rows: list[dict[str, Any]],
    responses: list[str] | None = None,
    *,
    show_progress: bool = False,
    detail_cell_limit: int = 100_000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Exact discrete functional ANOVA using dense marginal arrays.

    The former implementation filtered the full scenario list separately for
    every factorial cell, which is effectively quadratic on a large grid. Here
    each response is placed in one dense factorial array; every marginal is
    then a vectorized mean over complementary axes.
    """
    responses = responses or RESPONSES[:4]
    main_rows: list[dict[str, Any]] = []
    interaction_rows: list[dict[str, Any]] = []
    studies = sorted(_groups(rows).items())
    tasks = [
        (study_key_value, group, response)
        for study_key_value, group in studies
        for response in responses
    ]
    task_iterator = (
        progress(
            tasks,
            desc="Functional ANOVA",
            unit="response",
            position=1,
            leave=False,
        )
        if show_progress
        else tasks
    )
    for (catalyst, geometry), group, response in task_iterator:
        levels = {factor: sorted({row[factor] for row in group}) for factor in FACTORS}
        combinations_expected = math.prod(len(levels[factor]) for factor in FACTORS)
        cells = Counter(tuple(row[factor] for factor in FACTORS) for row in group)
        balanced = len(group) == combinations_expected and len(cells) == combinations_expected and all(count == 1 for count in cells.values())
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
            main_rows.append({**common, "method": "skipped_unbalanced", "factor": "", "level": "", "effect": math.nan, "component_variance": math.nan, "contribution_fraction": math.nan, "reconstruction_residual": math.nan, "detail_mode": "not_applicable"})
            continue

        level_index = {
            factor: {value: index for index, value in enumerate(levels[factor])}
            for factor in FACTORS
        }
        shape = tuple(len(levels[factor]) for factor in FACTORS)
        grid = np.empty(shape, dtype=float)
        for row in group:
            index = tuple(level_index[factor][row[factor]] for factor in FACTORS)
            grid[index] = float(row[response])

        grand = float(np.mean(grid))
        effects: dict[tuple[str, ...], np.ndarray] = {}
        components: dict[tuple[str, ...], float] = {}
        for order in range(1, len(FACTORS) + 1):
            for subset in itertools.combinations(FACTORS, order):
                complementary_axes = tuple(
                    index for index, factor in enumerate(FACTORS)
                    if factor not in subset
                )
                marginal = (
                    np.mean(grid, axis=complementary_axes)
                    if complementary_axes
                    else grid.copy()
                )
                effect_array = marginal - grand
                for proper_order in range(1, order):
                    for proper in itertools.combinations(subset, proper_order):
                        reshape = tuple(
                            len(levels[factor]) if factor in proper else 1
                            for factor in subset
                        )
                        effect_array = effect_array - effects[proper].reshape(reshape)
                effects[subset] = effect_array
                components[subset] = float(np.mean(np.square(effect_array)))

        reconstructed = sum(components.values())
        residual = total_variance - reconstructed
        estimated_interaction_cells = sum(
            effect_array.size
            for subset, effect_array in effects.items()
            if len(subset) >= 2
        ) * len(tasks)
        emit_interaction_cells = estimated_interaction_cells <= detail_cell_limit

        for subset, effect_array in effects.items():
            component = components[subset]
            base_record = {
                **common,
                "method": "exact_balanced_functional_anova",
                "interaction_order": len(subset),
                "factor": "*".join(subset),
                "component_variance": component,
                "contribution_fraction": component / total_variance if total_variance > 0.0 else 0.0,
                "reconstruction_residual": residual,
                "effect_cell_count": int(effect_array.size),
            }
            if len(subset) >= 2 and not emit_interaction_cells:
                interaction_rows.append({
                    **base_record,
                    "level": "",
                    "effect": math.nan,
                    "detail_mode": "component_summary_large_grid",
                })
                continue
            destination = main_rows if len(subset) == 1 else interaction_rows
            for array_index in np.ndindex(effect_array.shape):
                cell = tuple(
                    levels[factor][level_position]
                    for factor, level_position in zip(subset, array_index)
                )
                destination.append({
                    **base_record,
                    "level": "|".join(str(value) for value in cell),
                    "effect": float(effect_array[array_index]),
                    "detail_mode": "cell_effects",
                })
    return main_rows, interaction_rows


def local_elasticities(
    rows: list[dict[str, Any]],
    responses: list[str] | None = None,
    *,
    show_progress: bool = False,
    detail_row_limit: int = 200_000,
) -> list[dict[str, Any]]:
    responses = responses or RESPONSES[:4]
    output: list[dict[str, Any]] = []
    studies = sorted(_groups(rows).items())
    detailed = len(rows) * len(FACTORS) * len(responses) <= detail_row_limit
    dense_summary_cache: dict[
        tuple[str, str],
        tuple[dict[str, list[Any]], dict[str, np.ndarray], dict[float, float]],
    ] = {}
    if not detailed:
        for study_key_value, study in studies:
            levels = {
                factor: sorted({row[factor] for row in study})
                for factor in FACTORS
            }
            shape = tuple(len(levels[factor]) for factor in FACTORS)
            level_indices = {
                factor: {level: index for index, level in enumerate(levels[factor])}
                for factor in FACTORS
            }
            occupied = {
                tuple(row[factor] for factor in FACTORS)
                for row in study
            }
            if len(study) != math.prod(shape) or len(occupied) != len(study):
                continue
            response_grids = {
                response: np.empty(shape, dtype=float)
                for response in responses
            }
            temperature_coordinates: dict[float, float] = {}
            for row in study:
                index = tuple(
                    level_indices[factor][row[factor]]
                    for factor in FACTORS
                )
                for response in responses:
                    response_grids[response][index] = float(row[response])
                temperature_coordinates[float(row["temp_C"])] = (
                    1.0 / float(row["temperature_K"])
                )
            dense_summary_cache[study_key_value] = (
                levels,
                response_grids,
                temperature_coordinates,
            )

    def append_summary(
        catalyst: str,
        geometry: str,
        response: str,
        factor: str,
        coordinate: str,
        derivatives: np.ndarray,
        elasticities: np.ndarray,
    ) -> None:
        derivative_values = np.asarray(derivatives, dtype=float).ravel()
        derivative_values = derivative_values[np.isfinite(derivative_values)]
        elasticity_values = np.asarray(elasticities, dtype=float).ravel()
        elasticity_values = elasticity_values[np.isfinite(elasticity_values)]
        if derivative_values.size == 0:
            return
        output.append({
            "scenario_id": "",
            "catalyst": catalyst,
            "geometry": geometry,
            "response": response,
            "varied_factor": factor,
            "derivative_coordinate": coordinate,
            "coordinate_value": math.nan,
            "response_value": math.nan,
            "local_derivative": math.nan,
            "local_elasticity": math.nan,
            "detail_mode": "distribution_summary_large_grid",
            "n_derivatives": int(derivative_values.size),
            "derivative_mean": float(np.mean(derivative_values)),
            "derivative_median": float(np.median(derivative_values)),
            "derivative_p05": float(np.quantile(derivative_values, 0.05)),
            "derivative_p95": float(np.quantile(derivative_values, 0.95)),
            "n_elasticities": int(elasticity_values.size),
            "elasticity_mean": float(np.mean(elasticity_values)) if elasticity_values.size else math.nan,
            "elasticity_median": float(np.median(elasticity_values)) if elasticity_values.size else math.nan,
            "elasticity_abs_median": float(np.median(np.abs(elasticity_values))) if elasticity_values.size else math.nan,
            "elasticity_p05": float(np.quantile(elasticity_values, 0.05)) if elasticity_values.size else math.nan,
            "elasticity_p95": float(np.quantile(elasticity_values, 0.95)) if elasticity_values.size else math.nan,
        })

    tasks = [
        (study_key_value, study, factor)
        for study_key_value, study in studies
        for factor in FACTORS
    ]
    task_iterator = (
        progress(
            tasks,
            desc="Local elasticities",
            unit="factor",
            position=1,
            leave=False,
        )
        if show_progress
        else tasks
    )
    for (catalyst, geometry), study, factor in task_iterator:
        coordinate = "inverse_temperature_K_inv" if factor == "temp_C" else factor
        dense = dense_summary_cache.get((catalyst, geometry))
        if dense is not None:
            levels, response_grids, temperature_coordinates = dense
            factor_axis = FACTORS.index(factor)
            if factor == "temp_C":
                x = np.array([
                    temperature_coordinates[float(level)]
                    for level in levels[factor]
                ])
            else:
                x = np.asarray(levels[factor], dtype=float)
            if len(x) < 2 or len(np.unique(x)) != len(x):
                continue
            coordinate_shape = [1] * len(FACTORS)
            coordinate_shape[factor_axis] = len(x)
            coordinate_grid = x.reshape(coordinate_shape)
            for response in responses:
                response_grid = response_grids[response]
                derivatives = np.gradient(
                    response_grid,
                    x,
                    axis=factor_axis,
                    edge_order=2 if len(x) >= 3 else 1,
                )
                elasticities = np.divide(
                    coordinate_grid * derivatives,
                    response_grid,
                    out=np.full_like(response_grid, np.nan),
                    where=np.abs(response_grid) > 1e-14,
                )
                append_summary(
                    catalyst,
                    geometry,
                    response,
                    factor,
                    coordinate,
                    derivatives,
                    elasticities,
                )
            continue

        other_factors = [name for name in FACTORS if name != factor]
        slices: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in study:
            slices[tuple(row[name] for name in other_factors)].append(row)
        aggregate_derivatives: dict[str, list[float]] = defaultdict(list)
        aggregate_elasticities: dict[str, list[float]] = defaultdict(list)
        for fixed_values, slice_rows in slices.items():
            if len(slice_rows) < 2:
                continue
            if factor == "temp_C":
                ordered = sorted(slice_rows, key=lambda item: 1.0 / float(item["temperature_K"]))
                x = np.array([1.0 / float(item["temperature_K"]) for item in ordered])
            else:
                ordered = sorted(slice_rows, key=lambda item: float(item[factor]))
                x = np.array([float(item[factor]) for item in ordered])
            if len(np.unique(x)) != len(x):
                continue
            for response in responses:
                y = np.array([float(item[response]) for item in ordered])
                derivatives = np.gradient(y, x, edge_order=2 if len(x) >= 3 else 1)
                elasticities = np.divide(
                    x * derivatives,
                    y,
                    out=np.full_like(y, np.nan),
                    where=np.abs(y) > 1e-14,
                )
                if detailed:
                    for item, x_value, y_value, derivative, elasticity in zip(ordered, x, y, derivatives, elasticities):
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
                            "detail_mode": "scenario",
                        }
                        record.update({f"fixed_{name}": value for name, value in zip(other_factors, fixed_values)})
                        output.append(record)
                else:
                    aggregate_derivatives[response].extend(float(value) for value in derivatives if math.isfinite(float(value)))
                    aggregate_elasticities[response].extend(float(value) for value in elasticities if math.isfinite(float(value)))

        if not detailed:
            for response in responses:
                derivative_values = np.asarray(aggregate_derivatives[response], dtype=float)
                elasticity_values = np.asarray(aggregate_elasticities[response], dtype=float)
                append_summary(
                    catalyst,
                    geometry,
                    response,
                    factor,
                    coordinate,
                    derivative_values,
                    elasticity_values,
                )
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


def surrogate_validation(
    rows: list[dict[str, Any]],
    responses: list[str] | None = None,
    *,
    show_progress: bool = False,
) -> list[dict[str, Any]]:
    """Validate one quadratic response surface per study.

    All requested responses share the same design matrix, so each held-level
    fold is solved as one multi-output least-squares problem. This is
    mathematically equivalent to fitting every response separately but avoids
    repeating the expensive decomposition four times.
    """
    responses = responses or RESPONSES[:4]
    output: list[dict[str, Any]] = []
    studies = sorted(_groups(rows).items())
    total_folds = sum(
        sum(len({row[factor] for row in group}) for factor in FACTORS)
        for _, group in studies
    )
    fold_progress = progress(
        total=total_folds,
        desc="Surrogate validation",
        unit="fold",
        position=1,
        leave=False,
        disable=not show_progress,
    )
    for (catalyst, geometry), group in studies:
        raw = np.array([[float(row[factor]) for factor in FACTORS] for row in group])
        targets = np.column_stack([
            np.array([float(row[response]) for row in group])
            for response in responses
        ])
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
                coefficients, _, rank, _ = np.linalg.lstsq(
                    train_design,
                    targets[train_mask],
                    rcond=None,
                )
                predicted = test_design @ coefficients
                for response_index, response in enumerate(responses):
                    rmse, mae, r2, maximum = _error_metrics(
                        targets[test_mask, response_index],
                        predicted[:, response_index],
                    )
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
                fold_progress.update(1)
    fold_progress.close()
    return output


if njit is not None:
    @njit(cache=False)
    def _compiled_nondominated_indices(
        matrix: np.ndarray,
        order: np.ndarray,
        tolerance: float,
    ) -> np.ndarray:
        """Compiled incremental skyline scan for large exact fronts."""
        front_indices = np.empty(matrix.shape[0], dtype=np.int64)
        front_count = 0
        for position in range(order.size):
            original_index = order[position]
            dominated = False
            for front_position in range(front_count):
                other = matrix[front_indices[front_position]]
                weakly_better = True
                strictly_better = False
                for column in range(matrix.shape[1]):
                    if other[column] < matrix[original_index, column] - tolerance:
                        weakly_better = False
                        break
                    if other[column] > matrix[original_index, column] + tolerance:
                        strictly_better = True
                if weakly_better and strictly_better:
                    dominated = True
                    break
            if not dominated:
                front_indices[front_count] = original_index
                front_count += 1
        return front_indices[:front_count]
else:
    _compiled_nondominated_indices = None


def _nondominated_indices(
    matrix: np.ndarray,
    *,
    tolerance: float,
    show_progress: bool,
    description: str,
    use_compiled: bool = False,
) -> list[int]:
    """Return nondominated row indices for a maximization matrix.

    Lexicographic descending order guarantees that a later point cannot
    dominate an earlier point. Only the current front therefore needs to be
    checked, rather than comparing every point against the full input matrix.
    """
    if matrix.shape[0] == 0:
        return []
    keys = tuple(-matrix[:, index] for index in reversed(range(matrix.shape[1])))
    order = np.lexsort(keys)
    if use_compiled and _compiled_nondominated_indices is not None:
        compiled_progress = progress(
            total=1,
            desc=description,
            unit="study",
            position=1,
            leave=False,
            disable=not show_progress,
        )
        selected = _compiled_nondominated_indices(matrix, order, tolerance)
        compiled_progress.update(1)
        compiled_progress.close()
        return [int(index) for index in selected]

    front_vectors = np.empty_like(matrix)
    front_indices = np.empty(matrix.shape[0], dtype=int)
    front_count = 0
    iterator = progress(
        order,
        desc=description,
        unit="candidate",
        position=1,
        leave=False,
        disable=not show_progress,
    )
    for original_index in iterator:
        vector = matrix[int(original_index)]
        if front_count:
            current = front_vectors[:front_count]
            weakly_better = np.all(current >= vector - tolerance, axis=1)
            strictly_better = np.any(current > vector + tolerance, axis=1)
            if np.any(weakly_better & strictly_better):
                continue
        front_vectors[front_count] = vector
        front_indices[front_count] = int(original_index)
        front_count += 1
    return [int(index) for index in front_indices[:front_count]]


def pareto_front(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    show_progress: bool = False,
) -> list[dict[str, Any]]:
    """Find exact fronts for small studies and epsilon fronts for large ones.

    Exact dominance becomes quadratic when most points are nondominated, which
    is common with seven competing objectives. Above the configured threshold,
    normalized objective space is discretized into epsilon bins and dominance
    is evaluated between the unique bins. All scenarios in nondominated bins
    are retained, and the actual epsilon is recorded in every output row.
    """
    maximize = list(config["pareto_objectives"]["maximize"])
    minimize = list(config["pareto_objectives"]["minimize"])
    exact_limit = int(config.get("pareto_exact_scenario_limit", 50_000))
    python_exact_limit = int(config.get("pareto_python_exact_scenario_limit", 10_000))
    base_epsilon = float(config.get("pareto_epsilon", 0.02))
    max_unique_bins = int(config.get("pareto_max_unique_bins", 5_000))
    if exact_limit < 1:
        raise ValueError("pareto_exact_scenario_limit must be at least 1")
    if python_exact_limit < 1:
        raise ValueError("pareto_python_exact_scenario_limit must be at least 1")
    if not 0.0 < base_epsilon <= 1.0:
        raise ValueError("pareto_epsilon must be in (0, 1]")
    if max_unique_bins < 1:
        raise ValueError("pareto_max_unique_bins must be at least 1")
    output: list[dict[str, Any]] = []
    for (catalyst, geometry), group in sorted(_groups(rows).items()):
        names = maximize + minimize
        transformed = np.array([
            [float(row[name]) for name in maximize] + [-float(row[name]) for name in minimize]
            for row in group
        ])
        compiled_exact = (
            len(group) > python_exact_limit
            and _compiled_nondominated_indices is not None
        )
        use_exact = (
            len(group) <= exact_limit
            and (len(group) <= python_exact_limit or compiled_exact)
        )
        if use_exact:
            selected = _nondominated_indices(
                transformed,
                tolerance=1e-14,
                show_progress=show_progress,
                description=f"Exact Pareto {catalyst}/{geometry}",
                use_compiled=compiled_exact,
            )
            method = (
                "exact_compiled_incremental_dominance"
                if compiled_exact
                else "exact_incremental_dominance"
            )
            effective_epsilon = 0.0
            unique_bin_count = len(group)
            front_bin_count = len(selected)
        else:
            minima = np.min(transformed, axis=0)
            spans = np.max(transformed, axis=0) - minima
            spans[spans == 0.0] = 1.0
            normalized = (transformed - minima) / spans
            effective_epsilon = base_epsilon
            while True:
                bins = np.floor(normalized / effective_epsilon + 1e-12).astype(np.int64)
                unique_bins, inverse = np.unique(bins, axis=0, return_inverse=True)
                if len(unique_bins) <= max_unique_bins or effective_epsilon >= 1.0:
                    break
                effective_epsilon = min(1.0, effective_epsilon * 1.5)
            nondominated_bins = _nondominated_indices(
                unique_bins,
                tolerance=0.0,
                show_progress=show_progress,
                description=f"Epsilon Pareto {catalyst}/{geometry}",
            )
            selected_bin_mask = np.zeros(len(unique_bins), dtype=bool)
            selected_bin_mask[nondominated_bins] = True
            selected = [
                index for index, bin_index in enumerate(inverse)
                if selected_bin_mask[int(bin_index)]
            ]
            method = "epsilon_grid_dominance_large_study"
            unique_bin_count = len(unique_bins)
            front_bin_count = len(nondominated_bins)

        for index in selected:
            row = group[index]
            output.append({
                "scenario_id": row["scenario_id"],
                "catalyst": catalyst,
                "geometry": geometry,
                "pareto_method": method,
                "is_pareto_optimal": True if effective_epsilon == 0.0 else "",
                # An exact Pareto point is also the epsilon=0 special case.
                "is_epsilon_pareto_candidate": True,
                "pareto_epsilon_normalized": effective_epsilon,
                "study_scenario_count": len(group),
                "pareto_unique_bins": unique_bin_count,
                "pareto_front_bins": front_bin_count,
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
