"""
Observation model shared by truth and inference.

A measurement vector is species-major:  y[i*Nz + k] = C_{species i}(z_k),
matching  y = [C1(z1)...C1(zNz) ... CNs(z1)...CNs(zNz)]  of the theory.

NoiseModel builds the covariance Sigma_y:
  * heteroscedastic diagonal:      sigma = sigma_abs + sigma_rel * max(C, 0)
  * optional correlated errors between one pair of species at the SAME port
    (e.g. overlapping EGDA/EGMA acetyl resonances at 80 MHz), with
    correlation coefficient rho_overlap.

The truth model and the inference model each own their OWN NoiseModel
instance: by default identical (well-calibrated errors), but they can be
configured differently to study model-mismatch robustness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, Tuple

import numpy as np

from .layer1_bridge import OperatingConditions


@dataclass(frozen=True)
class NoiseModel:
    sigma_abs_M: float = 0.004        # absolute NMR noise floor, mol/L
    sigma_rel: float = 0.02           # relative (peak-integration) error
    rho_overlap: float = 0.0          # correlation of the overlap pair
    overlap_pair: Tuple[str, str] = ("EGDA", "EGMA")

    def sigmas(self, values: np.ndarray) -> np.ndarray:
        return self.sigma_abs_M + self.sigma_rel * np.maximum(values, 0.0)

    def covariance(self, values: np.ndarray, species: Sequence[str],
                   n_z: int) -> np.ndarray:
        sig = self.sigmas(np.asarray(values, dtype=float))
        cov = np.diag(sig ** 2)
        a, b = self.overlap_pair
        if self.rho_overlap != 0.0 and a in species and b in species:
            ia, ib = list(species).index(a), list(species).index(b)
            for k in range(n_z):
                p, q = ia * n_z + k, ib * n_z + k
                cov[p, q] = cov[q, p] = self.rho_overlap * sig[p] * sig[q]
        return cov


@dataclass
class Measurement:
    """One experiment's data as returned by the virtual laboratory.
    Contains NO information about the true parameters or the noise draw."""
    u: OperatingConditions
    z_m: np.ndarray                   # axial sampling positions, m
    species: Tuple[str, ...]
    y: np.ndarray                     # measured concentrations, species-major

    @property
    def n_z(self) -> int:
        return len(self.z_m)

    @property
    def size(self) -> int:
        return len(self.y)
