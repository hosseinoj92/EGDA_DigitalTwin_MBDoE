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


#: eigenvalues of F below this fraction of the largest carry no information
EIG_FLOOR_REL = 1e-14


def covariance_from_fim(F: np.ndarray,
                        eig_floor_rel: float = EIG_FLOOR_REL) -> np.ndarray:
    """V ~ F^-1, with uninformative directions given HUGE variance.

    np.linalg.pinv is wrong here: it assigns ZERO variance to the null space,
    i.e. infinite confidence in exactly the directions the data never
    constrained.  Flooring the eigenvalues instead inverts to a large variance,
    which is the honest answer."""
    w, V = np.linalg.eigh(F)
    floor = max(float(w[-1]), 1e-300) * eig_floor_rel
    return V @ np.diag(1.0 / np.maximum(w, floor)) @ V.T


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
    active_bounds: tuple = ()     # keys resting on a box constraint
    rel_ci_pct: np.ndarray = None  # per-parameter 95% rel CI, inf where pinned


class InferenceModel:
    def __init__(self, space: ParameterSpace, bridge: Layer1Bridge,
                 noise_assumed: NoiseModel):
        self.space = space
        self.bridge = bridge
        self.noise = noise_assumed
        self.theta = space.to_vector(space.initial_guess)   # current estimate
        self.measurements: List[Measurement] = []
        self._chols: List[np.ndarray] = []                  # assumed cov factors
        self.active_bounds: tuple = ()      # set by fit(); see ParameterSpace

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
        self.active_bounds = self.space.active_bounds(self.theta)
        return {"cost": float(sol.cost), "nfev": int(sol.nfev),
                "success": bool(sol.success),
                "active_bounds": self.active_bounds}

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
        # Eigenvalue-floored inverse in BOTH branches: a rank-deficient F must
        # report huge variance along its null space, never the zero variance
        # np.linalg.pinv would hand back (see covariance_from_fim).
        V = np.linalg.inv(F) if well_posed else covariance_from_fim(F)
        logdet_F = float(logdet) if well_posed else float("-inf")
        sig = np.sqrt(np.maximum(np.diag(V), 0.0))
        denom = np.outer(sig, sig)
        with np.errstate(divide="ignore", invalid="ignore"):
            corr = np.where(denom > 0, V / denom, 0.0)
        d_crit = (float(np.exp(-logdet_F / (2 * self.space.n_params)))
                  if np.isfinite(logdet_F) else float("inf"))
        rel_ci = self.space.rel_ci_percent(self.theta, sig)
        # A component sitting on its box bound has no valid local interval;
        # report it as unbounded rather than quoting the curvature at a wall.
        for q, k in enumerate(self.space.param_keys):
            if k in self.active_bounds:
                rel_ci[q] = float("inf")
        return UncertaintyReport(sigma=sig, cov=V, corr=corr, eigvals=eig,
                                 logdet_F=logdet_F, d_criterion=d_crit,
                                 max_rel_ci_pct=float(np.max(rel_ci)),
                                 well_posed=well_posed,
                                 active_bounds=tuple(self.active_bounds),
                                 rel_ci_pct=rel_ci)

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
