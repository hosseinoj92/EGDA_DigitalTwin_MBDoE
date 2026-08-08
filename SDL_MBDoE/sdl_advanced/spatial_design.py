"""
Spatial measurement design for the moving-capillary CPR.

The sampling position z is a CONTINUOUS controllable variable (one moving
capillary; no fixed ports, no selector valve).  This module chooses WHERE
along the reactor to measure.

Criterion (documented for the paper):

    For operating condition u and current parameter estimate theta, the local
    sensitivity at position z is  S(z,u) = dy(z,u)/dtheta  (n_species x p,
    scaled parameter space), and the information of ONE acquisition at z is

        F_z = S(z,u)' Sigma_y(z,u)^{-1} S(z,u).

    Positions are selected GREEDILY by incremental D-optimality: with
    F_current the accumulated campaign information and Z the already-chosen
    positions,

        z_{k+1} = argmax_z  log det( F_current + sum_{z' in Z} F_z' + F_z )

    subject to z in [z_min, z_max], pairwise spacing >= min_spacing, no
    duplicates, optional forced outlet.  Eigenvalues are floored so the
    criterion ranks candidates even while F is rank-deficient (same fix as
    sdl.design._score).  Greedy conditioning is what prevents the K
    individually best - but mutually redundant - neighbours being picked.

Modes:
    fixed_equal          z_i = i L / N  (exact legacy behaviour)
    optimized            greedy incremental D-optimal profile, optionally
                         followed by continuous coordinate refinement on the
                         interpolated sensitivity field
    adaptive_sequential  one position at a time; `next_position` returns the
                         best next z AND its marginal information gain so the
                         controller can stop when the gain per acquisition
                         falls below `marginal_information_threshold`.

Everything is expressed in z/L fractions internally, so changing the reactor
length automatically rescales all designs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

_EIG_FLOOR = 1e-12


def _logdet_floored(F: np.ndarray) -> float:
    return float(np.sum(np.log(np.maximum(np.linalg.eigvalsh(F),
                                          _EIG_FLOOR))))


def fixed_equal_positions(length_m: float, n_positions: int) -> np.ndarray:
    """Exact legacy layout of run_sdl_campaign.py:  z_i = i L/N, i=1..N."""
    return length_m * np.arange(1, n_positions + 1) / n_positions


@dataclass(frozen=True)
class SpatialDesignConfig:
    mode: str = "fixed_equal"     # fixed_equal | optimized | adaptive_sequential
    n_positions: int = 10
    candidate_grid_size: int = 101
    z_min_fraction: float = 0.02
    z_max_fraction: float = 1.0
    min_spacing_fraction: float = 0.02
    force_outlet: bool = False
    continuous_refinement: bool = True
    allow_profile_early_stop: bool = False
    marginal_information_threshold: float = 0.05   # nats per acquisition

    def __post_init__(self):
        if self.mode not in ("fixed_equal", "optimized",
                             "adaptive_sequential"):
            raise ValueError(f"Unknown sampling mode '{self.mode}'.")
        if not (0.0 <= self.z_min_fraction < self.z_max_fraction <= 1.0):
            raise ValueError("Need 0 <= z_min_fraction < z_max_fraction <= 1.")


class SensitivityField:
    """S(z) and y(z) on a dense grid for ONE operating condition, built from
    a species-major predictor, with linear interpolation to arbitrary z.
    One finite-difference sweep serves grid search AND continuous refinement."""

    def __init__(self, predict: Callable[[np.ndarray, np.ndarray], np.ndarray],
                 theta: np.ndarray, fd_steps: Sequence[float],
                 z_grid: np.ndarray, n_species: int):
        self.z_grid = np.asarray(z_grid, dtype=float)
        nz, p = len(self.z_grid), len(theta)
        y0 = predict(theta, self.z_grid)
        S = np.empty((len(y0), p))
        for q in range(p):
            h = fd_steps[q]
            tp = np.asarray(theta, dtype=float).copy()
            tp[q] += h
            S[:, q] = (predict(tp, self.z_grid) - y0) / h
        # reshape species-major vectors to (n_species, nz, .)
        self._y = y0.reshape(n_species, nz)
        self._S = S.reshape(n_species, nz, p)
        self.n_species, self.p = n_species, p

    def at(self, z: float) -> Tuple[np.ndarray, np.ndarray]:
        """(y (n_species,), S (n_species x p)) linearly interpolated at z."""
        y = np.array([np.interp(z, self.z_grid, self._y[i])
                      for i in range(self.n_species)])
        S = np.stack([np.array([np.interp(z, self.z_grid, self._S[i, :, q])
                                for q in range(self.p)])
                      for i in range(self.n_species)])
        return y, S


class SpatialDesigner:
    """Chooses sampling positions for one operating condition.

    cov_builder(y_at_z) -> Sigma_y (n_species x n_species) is the EXPECTED
    per-acquisition covariance model of the controller (assumed NoiseModel
    for the baseline, or a surrogate learned from past deconvolution
    covariances for the advanced controller).  It must never be the truth."""

    def __init__(self, cfg: SpatialDesignConfig, length_m: float,
                 cov_builder: Callable[[np.ndarray], np.ndarray]):
        self.cfg = cfg
        self.length_m = float(length_m)
        self.cov_builder = cov_builder

    # ------------------------------------------------------------------ #
    @property
    def z_bounds(self) -> Tuple[float, float]:
        return (self.cfg.z_min_fraction * self.length_m,
                self.cfg.z_max_fraction * self.length_m)

    @property
    def min_spacing_m(self) -> float:
        return self.cfg.min_spacing_fraction * self.length_m

    def candidate_grid(self) -> np.ndarray:
        lo, hi = self.z_bounds
        return np.linspace(lo, hi, self.cfg.candidate_grid_size)

    # ------------------------------------------------------------------ #
    def _fim_at(self, field: SensitivityField, z: float) -> np.ndarray:
        y, S = field.at(z)
        cov = self.cov_builder(y)
        L = np.linalg.cholesky(cov)
        Sw = np.linalg.solve(L, S)
        return Sw.T @ Sw

    def positions(self, field: SensitivityField, F0: np.ndarray
                  ) -> np.ndarray:
        """Full profile for one condition, according to cfg.mode."""
        cfg = self.cfg
        if cfg.mode == "fixed_equal":
            return fixed_equal_positions(self.length_m, cfg.n_positions)
        zs, _gains = self._greedy(field, F0, cfg.n_positions,
                                  early_stop=cfg.allow_profile_early_stop)
        if cfg.continuous_refinement:
            zs = self._refine(field, F0, zs)
        return np.sort(np.asarray(zs))

    def next_position(self, field: SensitivityField, F0: np.ndarray,
                      chosen: Sequence[float]) -> Tuple[Optional[float], float]:
        """Adaptive-sequential step: best next z given positions already
        measured at this condition, and its marginal log-det gain (nats).
        Returns (None, 0) when no feasible candidate remains."""
        zs, gains = self._greedy(field, F0, 1, preselected=list(chosen))
        if not zs:
            return None, 0.0
        return zs[0], gains[0]

    # ------------------------------------------------------------------ #
    def _greedy(self, field: SensitivityField, F0: np.ndarray, k: int,
                preselected: Optional[List[float]] = None,
                early_stop: bool = False
                ) -> Tuple[List[float], List[float]]:
        grid = self.candidate_grid()
        fims = [self._fim_at(field, z) for z in grid]
        chosen_z: List[float] = []
        gains: List[float] = []
        occupied = [float(z) for z in (preselected or [])]
        F = F0.copy()
        for z in occupied:
            F = F + self._fim_at(field, z)
        current_ld = _logdet_floored(F)
        if self.cfg.force_outlet and not occupied and k > 0:
            z_out = self.z_bounds[1]           # forced, counts toward k
            F = F + self._fim_at(field, z_out)
            chosen_z.append(z_out)
            new_ld = _logdet_floored(F)
            gains.append(new_ld - current_ld)  # actual gain of the forced pick
            occupied.append(z_out)
            current_ld = new_ld
        while len(chosen_z) < k:
            feasible = [j for j, z in enumerate(grid)
                        if all(abs(z - zo) >= self.min_spacing_m
                               for zo in occupied)]
            if not feasible:
                break
            scores = np.array([_logdet_floored(F + fims[j])
                               for j in feasible])
            jbest = feasible[int(np.argmax(scores))]
            gain = float(np.max(scores) - current_ld)
            if early_stop and chosen_z \
                    and gain < self.cfg.marginal_information_threshold:
                break
            z_new = float(grid[jbest])
            chosen_z.append(z_new)
            gains.append(gain)
            occupied.append(z_new)
            F = F + fims[jbest]
            current_ld = _logdet_floored(F)
        return chosen_z, gains

    def _refine(self, field: SensitivityField, F0: np.ndarray,
                zs: Sequence[float]) -> List[float]:
        """Deterministic cyclic coordinate polish of the selected positions
        on the interpolated sensitivity field (no rng; grid-free)."""
        lo, hi = self.z_bounds
        zs = [float(z) for z in zs]
        fims = [self._fim_at(field, z) for z in zs]
        for _ in range(2):                              # two sweeps suffice
            for i in range(len(zs)):
                F_rest = F0.copy()
                for j, Fj in enumerate(fims):
                    if j != i:
                        F_rest = F_rest + Fj
                others = [zs[j] for j in range(len(zs)) if j != i]

                def neg_score(z: float) -> float:
                    if not (lo <= z <= hi):
                        return np.inf
                    if any(abs(z - zo) < self.min_spacing_m for zo in others):
                        return np.inf
                    return -_logdet_floored(F_rest + self._fim_at(field, z))

                # golden-section around the current point, +/- one grid step
                step = (hi - lo) / max(self.cfg.candidate_grid_size - 1, 1)
                cands = np.clip(zs[i] + step * np.linspace(-1, 1, 11), lo, hi)
                vals = [neg_score(z) for z in cands]
                best = int(np.argmin(vals))
                if np.isfinite(vals[best]) and vals[best] < neg_score(zs[i]):
                    zs[i] = float(cands[best])
                    fims[i] = self._fim_at(field, zs[i])
        return zs

    # ------------------------------------------------------------------ #
    def information_density(self, field: SensitivityField, F0: np.ndarray
                            ) -> Tuple[np.ndarray, np.ndarray]:
        """(z_grid, marginal log-det gain of one acquisition at each z) -
        the information-density curve of Figure A."""
        grid = self.candidate_grid()
        base = _logdet_floored(F0)
        gains = np.array([_logdet_floored(F0 + self._fim_at(field, z)) - base
                          for z in grid])
        return grid, gains
