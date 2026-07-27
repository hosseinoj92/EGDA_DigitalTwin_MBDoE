"""
Virtual truth: the hidden ground-truth side of the self-driving laboratory.

VirtualLaboratory owns
  * the hidden true parameter vector (private attribute),
  * the Layer 1 simulator (via the bridge),
  * the observation model (sampling ports, measured species),
  * the synthetic NMR noise generator, and
  * optional systematic effects (transfer-line reaction, calibration bias).

FIREWALL: estimation and design code interacts with this class ONLY through
`run_experiment(u, spatial)`, which returns noisy Measurement objects.
`reveal_truth()` exists solely for post-campaign benchmarking/reporting and
counts its calls so tests can assert the loop never used it.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from .layer1_bridge import Layer1Bridge, OperatingConditions
from .observation import Measurement, NoiseModel


class VirtualLaboratory:
    def __init__(self,
                 theta_true: Dict[str, float],
                 bridge: Layer1Bridge,
                 noise: NoiseModel,
                 ports_z_m: Sequence[float],
                 species: Sequence[str],
                 seed: int = 0,
                 transfer_time_s: float = 0.0,
                 calibration_gain: Optional[Dict[str, float]] = None):
        self._theta_true = dict(theta_true)          # hidden
        self._bridge = bridge
        self._noise = noise
        self._rng = np.random.default_rng(seed)
        self.ports_z_m = np.asarray(ports_z_m, dtype=float)
        self.outlet_z_m = np.array([bridge.geometry.length_m])
        self.species = tuple(species)
        self.transfer_time_s = float(transfer_time_s)
        self.calibration_gain = calibration_gain or {}
        self.n_experiments_run = 0
        self.n_truth_reveals = 0

    # ------------------------------------------------------------------ #
    def run_experiment(self, u: OperatingConditions, spatial: bool) -> Measurement:
        """Run the hidden reactor at conditions u and return noisy CPR-NMR
        data: all ports if spatial, otherwise the outlet only."""
        z = self.ports_z_m if spatial else self.outlet_z_m
        clean = self._bridge.concentrations_at(
            self._theta_true, u, z, self.species,
            extra_tau_s=self.transfer_time_s)

        # optional per-species multiplicative calibration bias
        if self.calibration_gain:
            gains = np.concatenate([
                np.full(len(z), self.calibration_gain.get(sp, 1.0))
                for sp in self.species])
            clean = clean * gains

        cov = self._noise.covariance(clean, self.species, len(z))
        noise = np.linalg.cholesky(cov) @ self._rng.standard_normal(len(clean))
        self.n_experiments_run += 1
        return Measurement(u=u, z_m=z.copy(), species=self.species,
                           y=clean + noise)

    # ------------------------------------------------------------------ #
    def reveal_truth(self) -> Dict[str, float]:
        """POST-CAMPAIGN benchmarking only - never called inside the loop."""
        self.n_truth_reveals += 1
        return dict(self._theta_true)
