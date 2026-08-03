from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "analysis_version": "1.0.0",
    "diffusivity_m2_s": 1.0e-9,
    "pressure_threshold_C": 100.0,
    "allow_pressurized_operation": False,
    "verification_error_limit": 1.0e-6,
    "invariant_drift_limit": 1.0e-6,
    "peak_relative_threshold": 0.95,
    "pareto_objectives": {
        "maximize": ["Y_EGMA", "S_EGMA", "STY_EGMA_mol_Lreactor_h"],
        "minimize": ["temp_C", "C_catalyst_feed_M", "tau_s", "Y_EG"],
    },
    "robust_window": {
        "min_X_EGDA": 0.50,
        "min_Y_EGMA": 0.25,
        "min_S_EGMA": 0.50,
        "max_Y_EG": 0.40,
        "max_temp_C": 100.0,
        "near_optimal_fraction": 0.95,
        "require_physical_validity": False,
        "min_feasible_neighbor_fraction": 0.50,
    },
    "regimes": {
        "low_conversion_max": 0.10,
        "selective_min_selectivity": 0.70,
        "selective_min_yield": 0.20,
        "naoh_exhausted_fraction": 0.01,
        "acid_equilibrium_fraction": 0.90,
    },
    "top_conditions_per_study": 10,
    "random_seed": 1729,
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return copy.deepcopy(DEFAULT_CONFIG)
    with path.open("r", encoding="utf-8") as handle:
        supplied = json.load(handle)
    if not isinstance(supplied, dict):
        raise ValueError("Analysis configuration must be a JSON object.")
    return _merge(DEFAULT_CONFIG, supplied)

