"""
Experiment design: fixed (conventional) designs and autonomous MBDoE.

Fixed design    : a predefined list of operating conditions (temperature
                  ladder at nominal flow/acid) executed in order, exactly as
                  a conventional kinetics campaign would.
MBDoE selection : D-optimal - among a feasible candidate grid, choose the
                  experiment maximizing  log det(F_current + F_candidate),
                  i.e. the largest expected shrinkage of the joint parameter
                  uncertainty ellipsoid.  Candidate FIMs are evaluated at the
                  current estimate with the assumed noise model.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np

from .inference import InferenceModel
from .layer1_bridge import OperatingConditions


def build_candidates(cfg: Dict) -> List[OperatingConditions]:
    """Full-factorial candidate grid over the feasible design space."""
    cands = []
    for t, q, cat in itertools.product(cfg["T_C_levels"],
                                       cfg["Q_total_mL_min_levels"],
                                       cfg["C_cat_M_levels"]):
        cands.append(OperatingConditions(
            T_C=float(t), Q1_mL_min=float(q) / 2.0, Q2_mL_min=float(q) / 2.0,
            C_EGDA_M=float(cfg["C_EGDA_M"]), C_cat_M=float(cat)))
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

    def select(self) -> OperatingConditions:
        F0 = self.inference.fisher_information()
        z = self.ports_z_m if self.spatial else self.outlet_z_m
        best_u, best_score = None, -np.inf
        for u in self.candidates:
            F = F0 + self.inference.candidate_information(u, z, self.species)
            score = self._score(F)
            if score > best_score:
                best_u, best_score = u, score
        return best_u

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
