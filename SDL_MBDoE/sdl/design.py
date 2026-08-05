"""
Experiment design: fixed (conventional) designs and autonomous MBDoE.

Fixed design    : a predefined list of operating conditions (temperature
                  ladder at nominal flow/acid) executed in order, exactly as
                  a conventional kinetics campaign would.
MBDoE selection : D- or A-optimal.  A coarse, feasible candidate grid is
                  always screened first.  Optional continuous refinement is
                  initialized from the best grid point and is constrained to
                  user-supplied bounds for every operating variable.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize

from .inference import InferenceModel
from .layer1_bridge import OperatingConditions


def build_candidates(cfg: Dict) -> List[OperatingConditions]:
    """Full-factorial candidate grid over the feasible design space."""
    egda_levels = (cfg["C_EGDA_M_levels"] if "C_EGDA_M_levels" in cfg
                   else [cfg["C_EGDA_M"]])
    cands = []
    for t, q, cat, egda in itertools.product(
            cfg["T_C_levels"], cfg["Q_total_mL_min_levels"],
            cfg["C_cat_M_levels"], egda_levels):
        cands.append(OperatingConditions(
            T_C=float(t), Q1_mL_min=float(q) / 2.0, Q2_mL_min=float(q) / 2.0,
            C_EGDA_M=float(egda), C_cat_M=float(cat)))
    return cands


def build_fixed_design(cfg: Dict) -> List[OperatingConditions]:
    """Conventional campaign: temperature ladder at nominal flow/catalyst."""
    q = float(cfg["nominal_Q_total_mL_min"])
    return [OperatingConditions(
        T_C=float(t), Q1_mL_min=q / 2.0, Q2_mL_min=q / 2.0,
        C_EGDA_M=float(cfg["C_EGDA_M"]),
        C_cat_M=float(cfg["nominal_C_cat_M"]))
        for t in cfg["fixed_design_T_C"]]


@dataclass
class MBDoESelector:
    inference: InferenceModel
    candidates: List[OperatingConditions]
    spatial: bool
    ports_z_m: np.ndarray
    outlet_z_m: np.ndarray
    species: Sequence[str]
    criterion: str = "D"          # "D" (log det) | "A" (-trace of covariance)
    continuous: bool = False
    continuous_bounds: Optional[Dict[str, Sequence[float]]] = None
    continuous_maxiter: int = 30

    _VARIABLES = ("T_C", "Q_total_mL_min", "C_cat_M", "C_EGDA_M")

    def __post_init__(self) -> None:
        if not self.candidates:
            raise ValueError("MBDoE requires at least one coarse candidate.")
        if self.criterion not in ("D", "A"):
            raise ValueError(f"Unknown design criterion '{self.criterion}'.")
        if self.continuous or self.continuous_bounds is not None:
            bounds = self._validated_continuous_bounds()
            for u in self.candidates:
                x = self._to_vector(u)
                if any(value < lo or value > hi
                       for value, (lo, hi) in zip(x, bounds)):
                    raise ValueError(
                        "Every coarse candidate must lie inside continuous_bounds; "
                        f"candidate {u.label()} does not.")

    def select(self) -> OperatingConditions:
        F0 = self.inference.fisher_information()
        z = self.ports_z_m if self.spatial else self.outlet_z_m
        best_u, best_score = None, -np.inf
        for u in self.candidates:
            score = self._score_candidate(F0, u, z)
            if score > best_score:
                best_u, best_score = u, score
        if best_u is None:
            raise RuntimeError("No feasible MBDoE candidate produced a finite score.")
        if not self.continuous:
            return best_u

        bounds = self._validated_continuous_bounds()

        def objective(x: np.ndarray) -> float:
            try:
                score = self._score_candidate(F0, self._from_vector(x), z)
            except (ValueError, RuntimeError, FloatingPointError,
                    np.linalg.LinAlgError):
                return 1e100
            return -score if np.isfinite(score) else 1e100

        refined = minimize(
            objective, self._to_vector(best_u), method="Powell", bounds=bounds,
            options={"maxiter": int(self.continuous_maxiter),
                     "xtol": 1e-4, "ftol": 1e-6})
        refined_u = self._from_vector(refined.x)
        refined_score = self._score_candidate(F0, refined_u, z)
        if np.isfinite(refined_score) and refined_score > best_score:
            return refined_u
        return best_u

    def _score_candidate(self, F0: np.ndarray, u: OperatingConditions,
                         z: np.ndarray) -> float:
        F = F0 + self.inference.candidate_information(u, z, self.species)
        return self._score(F)

    @staticmethod
    def _to_vector(u: OperatingConditions) -> np.ndarray:
        return np.array([u.T_C, u.Q1_mL_min + u.Q2_mL_min,
                         u.C_cat_M, u.C_EGDA_M], dtype=float)

    @staticmethod
    def _from_vector(x: Sequence[float]) -> OperatingConditions:
        t, q, cat, egda = (float(v) for v in x)
        return OperatingConditions(
            T_C=t, Q1_mL_min=q / 2.0, Q2_mL_min=q / 2.0,
            C_EGDA_M=egda, C_cat_M=cat)

    def _validated_continuous_bounds(self) -> Tuple[Tuple[float, float], ...]:
        if self.continuous_bounds is None:
            raise ValueError(
                "continuous=True requires continuous_bounds for T_C, "
                "Q_total_mL_min, C_cat_M, and C_EGDA_M.")
        missing = [key for key in self._VARIABLES
                   if key not in self.continuous_bounds]
        if missing:
            raise ValueError("continuous_bounds is missing: " + ", ".join(missing))
        out = []
        for key in self._VARIABLES:
            raw = self.continuous_bounds[key]
            if len(raw) != 2:
                raise ValueError(f"continuous_bounds['{key}'] must have [low, high].")
            lo, hi = float(raw[0]), float(raw[1])
            if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
                raise ValueError(f"Invalid continuous bounds for {key}: {raw}.")
            if key != "T_C" and lo <= 0.0:
                raise ValueError(f"The lower bound for {key} must be positive.")
            out.append((lo, hi))
        if self.continuous and int(self.continuous_maxiter) < 1:
            raise ValueError("continuous_maxiter must be at least 1.")
        return tuple(out)

    def _score(self, F: np.ndarray) -> float:
        if self.criterion == "D":
            sign, logdet = np.linalg.slogdet(F)
            return logdet if sign > 0 else -np.inf
        if self.criterion == "A":
            try:
                return -float(np.trace(np.linalg.inv(F)))
            except np.linalg.LinAlgError:
                return -np.inf
        raise ValueError(f"Unknown design criterion '{self.criterion}'.")
