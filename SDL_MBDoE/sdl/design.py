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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize

from .design_space import (DESIGN_VARIABLES, DesignResolution,
                           bounds_vector, from_vector, refine, to_vector)
from .inference import InferenceModel
from .layer1_bridge import OperatingConditions

#: eigenvalue floor for the design criteria - keeps them finite and rankable
#: while the accumulated FIM is still rank deficient
_EIG_FLOOR = 1e-12


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


def build_fixed_design(cfg: Dict,
                       budget: Optional[int] = None) -> List[OperatingConditions]:
    """Conventional campaign: temperature ladder at nominal flow/catalyst.

    `budget` SUBSAMPLES the declared ladder evenly instead of truncating it.
    The campaign loop walks this list in order, so a 25-rung 40-160 C ladder
    consumed by a 10-experiment budget used to run only the coldest ten rungs
    (40-85 C) - a region where almost nothing converts and the FIM is rank
    deficient by construction.  That handicapped the conventional baseline and
    confounded "adaptive vs fixed" with "sees the whole box vs one cold edge".
    Spreading the same ten experiments over the same declared ladder drops the
    FIM condition number by ~6 orders of magnitude at zero extra cost."""
    ladder = [float(t) for t in cfg["fixed_design_T_C"]]
    if budget is not None and 0 < budget < len(ladder):
        idx = np.unique(np.linspace(0, len(ladder) - 1, budget).round()
                        .astype(int))
        ladder = [ladder[i] for i in idx]
    q = float(cfg["nominal_Q_total_mL_min"])
    return [OperatingConditions(
        T_C=t, Q1_mL_min=q / 2.0, Q2_mL_min=q / 2.0,
        C_EGDA_M=float(cfg["C_EGDA_M"]),
        C_cat_M=float(cfg["nominal_C_cat_M"]))
        for t in ladder]


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
    #: instrument resolution the refined point is SNAPPED to, so the design
    #: that is scored is the design the platform can actually command
    resolution: DesignResolution = field(default_factory=DesignResolution)

    _VARIABLES = DESIGN_VARIABLES

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
        # Refinement is scored at SNAPPED points and accepted only when it
        # strictly beats the grid winner, so continuous mode is never worse
        # than discrete mode by this criterion (sdl/design_space.py).
        u_ref, _score, _improved = refine(
            lambda u: self._score_candidate(F0, u, z),
            best_u, best_score, self.continuous_bounds,
            resolution=self.resolution,
            maxiter=int(self.continuous_maxiter))
        return u_ref

    def _score_candidate(self, F0: np.ndarray, u: OperatingConditions,
                         z: np.ndarray) -> float:
        F = F0 + self.inference.candidate_information(u, z, self.species)
        return self._score(F)

    _to_vector = staticmethod(to_vector)
    _from_vector = staticmethod(from_vector)

    def _validated_continuous_bounds(self) -> Tuple[Tuple[float, float], ...]:
        """Bounds in canonical order.

        A DEGENERATE dimension (lo == hi) is accepted and simply held fixed
        by the refiner: the shipped design space declares C_EGDA_M = [1, 1],
        and rejecting that would make continuous mode unusable on the very
        configuration the benchmark runs."""
        if self.continuous_bounds is None:
            raise ValueError(
                "continuous=True requires continuous_bounds for T_C, "
                "Q_total_mL_min, C_cat_M, and C_EGDA_M.")
        if self.continuous and int(self.continuous_maxiter) < 1:
            raise ValueError("continuous_maxiter must be at least 1.")
        return bounds_vector(self.continuous_bounds)

    def _score(self, F: np.ndarray) -> float:
        """Design score with FLOORED eigenvalues.

        `slogdet` returns -inf for any singular F, so while the accumulated
        information is still rank deficient - i.e. exactly the early rounds
        when the choice matters most - every candidate scored -inf and the
        selection loop below could not rank them at all.  It then kept its
        first arbitrary pick and the campaign locked onto one corner.
        Flooring the eigenvalues keeps the criterion finite and strictly
        increasing in information, so the greedy step still prefers the
        candidate that best fills the weakest direction."""
        w = np.maximum(np.linalg.eigvalsh(F), _EIG_FLOOR)
        if self.criterion == "D":
            return float(np.sum(np.log(w)))
        if self.criterion == "A":
            return -float(np.sum(1.0 / w))
        raise ValueError(f"Unknown design criterion '{self.criterion}'.")
