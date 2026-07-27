"""
Inference model: everything the (virtual) experimenter is allowed to know.

Holds the accumulated measurements, the ASSUMED measurement covariance, the
current parameter estimate, and provides:

  * weighted least-squares estimation (residuals whitened per experiment
    with the Cholesky factor of the assumed covariance),
  * finite-difference sensitivity matrices  S = d y_hat / d theta  (in the
    scaled parameter space),
  * the Fisher Information Matrix  F = sum_e S_e' Sigma_e^-1 S_e,
  * parameter covariance V ~ F^-1, correlation matrix, eigen-analysis, and
    the D-criterion size measure  (det V)^(1/2p).

It never touches the true parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import least_squares

from .layer1_bridge import Layer1Bridge, OperatingConditions
from .observation import Measurement, NoiseModel
from .parameters import ParameterSpace


@dataclass
class UncertaintyReport:
    sigma: np.ndarray             # 1-sigma, scaled space [ln k, kJ]
    cov: np.ndarray               # V_theta, scaled space
    corr: np.ndarray              # correlation matrix
    eigvals: np.ndarray           # eigenvalues of F (ascending)
    logdet_F: float
    d_criterion: float            # (det V)^(1/2p) - geometric-mean sigma
    max_rel_ci_pct: float         # worst 95% relative CI half-width, %
    well_posed: bool


class InferenceModel:
    def __init__(self, space: ParameterSpace, bridge: Layer1Bridge,
                 noise_assumed: NoiseModel):
        self.space = space
        self.bridge = bridge
        self.noise = noise_assumed
        self.theta = space.to_vector(space.initial_guess)   # current estimate
        self.measurements: List[Measurement] = []
        self._chols: List[np.ndarray] = []                  # assumed cov factors

    # ------------------------------------------------------------------ #
    @property
    def n_data(self) -> int:
        return sum(m.size for m in self.measurements)

    def add_measurement(self, m: Measurement) -> None:
        cov = self.noise.covariance(m.y, m.species, m.n_z)
        self.measurements.append(m)
        self._chols.append(np.linalg.cholesky(cov))

    # ------------------------------------------------------------------ #
    def predict(self, theta_vec: np.ndarray, m: Measurement) -> np.ndarray:
        nat = self.space.to_natural(theta_vec)
        return self.bridge.concentrations_at(nat, m.u, m.z_m, m.species)

    def _whitened_residuals(self, theta_vec: np.ndarray) -> np.ndarray:
        parts = []
        for m, L in zip(self.measurements, self._chols):
            r = self.predict(theta_vec, m) - m.y
            parts.append(solve_triangular(L, r, lower=True))
        return np.concatenate(parts)

    def fit(self) -> Dict[str, float]:
        """Re-estimate theta from all accumulated data (warm start)."""
        lo, hi = self.space.bounds()
        x0 = np.clip(self.theta, lo, hi)
        sol = least_squares(self._whitened_residuals, x0=x0, bounds=(lo, hi),
                            x_scale=np.array(self.space.x_scale), method="trf")
        self.theta = sol.x
        return {"cost": float(sol.cost), "nfev": int(sol.nfev),
                "success": bool(sol.success)}

    # ------------------------------------------------------------------ #
    def sensitivity(self, m: Measurement,
                    theta_vec: Optional[np.ndarray] = None) -> np.ndarray:
        """Central-difference S (m.size x p) in scaled parameter space."""
        th = self.theta if theta_vec is None else theta_vec
        p = self.space.n_params
        S = np.empty((m.size, p))
        for q in range(p):
            h = self.space.fd_steps[q]
            tp, tm = th.copy(), th.copy()
            tp[q] += h
            tm[q] -= h
            S[:, q] = (self.predict(tp, m) - self.predict(tm, m)) / (2.0 * h)
        return S

    def fisher_information(self,
                           theta_vec: Optional[np.ndarray] = None) -> np.ndarray:
        p = self.space.n_params
        F = np.zeros((p, p))
        for m, L in zip(self.measurements, self._chols):
            Sw = solve_triangular(L, self.sensitivity(m, theta_vec), lower=True)
            F += Sw.T @ Sw
        return F

    def uncertainty(self, F: Optional[np.ndarray] = None) -> UncertaintyReport:
        if F is None:
            F = self.fisher_information()
        eig = np.linalg.eigvalsh(F)
        sign, logdet = np.linalg.slogdet(F)
        well_posed = bool(sign > 0 and eig[0] > 1e-10 * max(eig[-1], 1.0))
        if well_posed:
            V = np.linalg.inv(F)
            logdet_F = float(logdet)
        else:                       # rank-deficient: pseudo-inverse, flag it
            V = np.linalg.pinv(F, hermitian=True)
            logdet_F = float("-inf")
        sig = np.sqrt(np.maximum(np.diag(V), 0.0))
        denom = np.outer(sig, sig)
        with np.errstate(divide="ignore", invalid="ignore"):
            corr = np.where(denom > 0, V / denom, 0.0)
        d_crit = (float(np.exp(-logdet_F / (2 * self.space.n_params)))
                  if np.isfinite(logdet_F) else float("inf"))
        rel_ci = self.space.rel_ci_percent(self.theta, sig)
        return UncertaintyReport(sigma=sig, cov=V, corr=corr, eigvals=eig,
                                 logdet_F=logdet_F, d_criterion=d_crit,
                                 max_rel_ci_pct=float(np.max(rel_ci)),
                                 well_posed=well_posed)

    # ------------------------------------------------------------------ #
    def candidate_information(self, u: OperatingConditions, z_m: np.ndarray,
                              species) -> np.ndarray:
        """Expected FIM contribution of a candidate experiment, evaluated at
        the CURRENT estimate with the ASSUMED noise model (forward FD)."""
        m_hyp = Measurement(u=u, z_m=np.asarray(z_m, dtype=float),
                            species=tuple(species),
                            y=np.zeros(len(z_m) * len(species)))
        y0 = self.predict(self.theta, m_hyp)
        p = self.space.n_params
        S = np.empty((len(y0), p))
        for q in range(p):
            h = self.space.fd_steps[q]
            tp = self.theta.copy()
            tp[q] += h
            S[:, q] = (self.predict(tp, m_hyp) - y0) / h
        cov = self.noise.covariance(y0, m_hyp.species, m_hyp.n_z)
        Sw = solve_triangular(np.linalg.cholesky(cov), S, lower=True)
        return Sw.T @ Sw
