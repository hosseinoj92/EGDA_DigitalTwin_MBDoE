"""
Laplace-approximate Bayesian posterior for ONE kinetic-model hypothesis.

Composes (does not modify) the baseline sdl.InferenceModel: measurement
storage, prediction, whitening and sensitivities are reused; this module
adds a documented weak Gaussian prior in the SCALED parameter space,
MAP estimation, the local posterior covariance, and a Laplace estimate of
the model evidence

    log Z ~ log p(y|theta*) + log p(theta*) + (p/2) log 2pi - 1/2 log det H,

with H = F(theta*) + P the Gauss-Newton Hessian (F the Fisher information of
the accumulated data, P the prior precision).  The API is deliberately
minimal (fit_map / sample / log_evidence) so an SMC/MCMC backend can replace
the Laplace approximation later without touching the controller.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
from scipy.optimize import least_squares

from sdl.inference import InferenceModel, covariance_from_fim
from sdl.parameters import ParameterSpace


@dataclass(frozen=True)
class GaussianPrior:
    """Weak, documented prior in scaled space [ln k, Ea/kJ, ln K].

    Defaults (see from_space): sigma(ln k) = ln 10 - "the literature guess is
    right within a factor of 10"; sigma(Ea) = 20 kJ/mol; sigma(ln K) = ln 3.
    These encode the same provenance as sdl.layer1_bridge.literature_guess
    and are wide enough that a few informative experiments dominate them."""
    mean: np.ndarray
    sigma: np.ndarray

    @classmethod
    def from_space(cls, space: ParameterSpace,
                   ln_k_sigma: float = math.log(10.0),
                   ea_sigma_kJ: float = 20.0,
                   ln_K_sigma: float = math.log(3.0)) -> "GaussianPrior":
        mean = space.to_vector(space.initial_guess)
        sig = np.empty(space.n_params)
        for q, k in enumerate(space.param_keys):
            if k.startswith("K"):
                sig[q] = ln_K_sigma
            elif space.is_log(q):
                sig[q] = ln_k_sigma
            else:
                sig[q] = ea_sigma_kJ
        return cls(mean=mean, sigma=sig)

    def log_pdf(self, theta: np.ndarray) -> float:
        z = (theta - self.mean) / self.sigma
        return float(-0.5 * z @ z - np.sum(np.log(self.sigma))
                     - 0.5 * len(z) * math.log(2.0 * math.pi))


class LaplacePosterior:
    def __init__(self, inference: InferenceModel, prior: GaussianPrior):
        self.inference = inference
        self.prior = prior
        self.theta_map: Optional[np.ndarray] = None
        self.cov: Optional[np.ndarray] = None
        self.log_evidence: float = -np.inf

    # ------------------------------------------------------------------ #
    def _penalized_residuals(self, theta: np.ndarray) -> np.ndarray:
        r = self.inference._whitened_residuals(theta)
        rp = (theta - self.prior.mean) / self.prior.sigma
        return np.concatenate([r, rp])

    def fit_map(self) -> Dict[str, float]:
        inf = self.inference
        lo, hi = inf.space.bounds()
        x0 = np.clip(inf.theta, lo, hi)
        sol = least_squares(self._penalized_residuals, x0=x0,
                            bounds=(lo, hi),
                            x_scale=np.array(inf.space.x_scale), method="trf")
        inf.theta = sol.x
        self.theta_map = sol.x.copy()
        F = inf.fisher_information(self.theta_map)
        P = np.diag(1.0 / self.prior.sigma ** 2)
        H = F + P
        self.cov = covariance_from_fim(H)
        self.log_evidence = self._laplace_evidence(H)
        return {"cost": float(sol.cost), "success": bool(sol.success)}

    def _laplace_evidence(self, H: np.ndarray) -> float:
        inf = self.inference
        r = inf._whitened_residuals(self.theta_map)
        # log p(y | theta*): whitened Gaussian likelihood incl. normalization
        log_like = -0.5 * float(r @ r)
        n_total = 0
        for m, L in zip(inf.measurements, inf._chols):
            log_like -= float(np.sum(np.log(np.diag(L))))
            n_total += m.size
        log_like -= 0.5 * n_total * math.log(2.0 * math.pi)
        log_prior = self.prior.log_pdf(self.theta_map)
        sign, logdet_H = np.linalg.slogdet(H)
        if sign <= 0:
            return -np.inf
        p = inf.space.n_params
        return (log_like + log_prior + 0.5 * p * math.log(2.0 * math.pi)
                - 0.5 * float(logdet_H))

    # ------------------------------------------------------------------ #
    def sample(self, n: int, rng: np.random.Generator) -> np.ndarray:
        """n posterior draws (rows), truncated to the box by clipping.
        (Clipping is acceptable for the weakly-truncated posteriors here;
        an SMC backend would replace this.)"""
        if self.theta_map is None:
            raise RuntimeError("fit_map() before sampling.")
        L = np.linalg.cholesky(self.cov + 1e-12 * np.eye(len(self.theta_map)))
        lo, hi = self.inference.space.bounds()
        draws = self.theta_map[None, :] + rng.standard_normal(
            (n, len(self.theta_map))) @ L.T
        return np.clip(draws, lo, hi)

    def log_likelihood(self, theta: np.ndarray) -> float:
        r = self.inference._whitened_residuals(theta)
        return -0.5 * float(r @ r)      # constants identical across particles
