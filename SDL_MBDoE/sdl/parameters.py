"""
Estimation parameter space (catalyst-aware).

Natural parameters (dict keys, "natural units"):
    k1_ref, k2_ref   L/(mol s)  - rate constants at T_ref (catalytic on the
                                  H2SO4 route, saponification on NaOH)
    Ea1_J,  Ea2_J    J/mol      - activation energies
    K1_ref, K2_ref   (-)        - hydrolysis equilibrium constants at T_ref;
                                  H2SO4 route ONLY (saponification is
                                  irreversible, so no Keq exists to estimate).
                                  Van 't Hoff slopes dH are fixed at their
                                  small literature values: nearly athermal
                                  equilibria make dH unidentifiable over a
                                  30-90 C window.

Internal estimator vector (scaled, what the optimizer and the FIM see):
    H2SO4: theta = [ln k1_ref, Ea1/1000, ln k2_ref, Ea2/1000,
                    ln K1_ref, ln K2_ref]                       (p = 6)
    NaOH : theta = [ln k1_ref, Ea1/1000, ln k2_ref, Ea2/1000]   (p = 4)

ln k / ln K make the constants strictly positive and turn sigma(ln .) into a
relative uncertainty; Ea in kJ/mol keeps all components comparable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Sequence, Tuple

import numpy as np

ACID_PARAM_KEYS = ("k1_ref", "Ea1_J", "k2_ref", "Ea2_J", "K1_ref", "K2_ref")
BASE_PARAM_KEYS = ("k1_ref", "Ea1_J", "k2_ref", "Ea2_J")
PARAM_KEYS = ACID_PARAM_KEYS          # backward-compatible alias (acid route)
LOG_KEYS = ("k1_ref", "k2_ref", "K1_ref", "K2_ref")
PARAM_LABELS = {
    "k1_ref": "k1_ref (L mol-1 s-1)",
    "Ea1_J": "Ea1 (kJ/mol)",
    "k2_ref": "k2_ref (L mol-1 s-1)",
    "Ea2_J": "Ea2 (kJ/mol)",
    "K1_ref": "K1_ref (-)",
    "K2_ref": "K2_ref (-)",
}


def param_keys_for(catalyst: str) -> Tuple[str, ...]:
    """Estimated parameter keys of the chosen catalyst system."""
    return BASE_PARAM_KEYS if catalyst == "NaOH" else ACID_PARAM_KEYS


def theta_component_name(key: str) -> str:
    """Short name of the scaled theta component for a natural key."""
    if key in LOG_KEYS:
        return "ln " + key.replace("_ref", "")
    return key.replace("_J", "")


@dataclass
class ParameterSpace:
    t_ref_K: float
    initial_guess: Dict[str, float]              # natural units
    param_keys: Tuple[str, ...] = ACID_PARAM_KEYS
    ln_k_halfwidth: float = math.log(30.0)       # bounds: guess x/30 .. x*30
    ln_K_halfwidth: float = math.log(10.0)       # Keq is better known a priori
    ea_bounds_J: Tuple[float, float] = (20_000.0, 120_000.0)
    # Parameters HELD FIXED at a known value and excluded from theta (natural
    # units).  Structurally unidentifiable parameters belong here: estimating
    # them costs a flat FIM direction, an optimizer that walks to its box
    # bound, and a meaningless confidence interval.  Same treatment the
    # van 't Hoff slopes already get in layer1_bridge.
    fixed: Dict[str, float] = field(default_factory=dict)

    # ---- structure ----------------------------------------------------------
    @property
    def n_params(self) -> int:
        return len(self.param_keys)

    @property
    def fixed_keys(self) -> Tuple[str, ...]:
        return tuple(self.fixed)

    def holding_fixed(self, keys: Sequence[str]) -> "ParameterSpace":
        """Copy of this space with `keys` moved out of theta and pinned at
        their initial-guess values."""
        drop = set(keys)
        unknown = drop - set(self.param_keys)
        if unknown:
            raise ValueError(f"Not estimated parameters: {sorted(unknown)}.")
        kept = tuple(k for k in self.param_keys if k not in drop)
        if not kept:
            raise ValueError("Cannot fix every parameter - theta would be empty.")
        return ParameterSpace(
            t_ref_K=self.t_ref_K, initial_guess=dict(self.initial_guess),
            param_keys=kept, ln_k_halfwidth=self.ln_k_halfwidth,
            ln_K_halfwidth=self.ln_K_halfwidth, ea_bounds_J=self.ea_bounds_J,
            fixed={**self.fixed,
                   **{k: self.initial_guess[k] for k in keys}})

    def is_log(self, q: int) -> bool:
        return self.param_keys[q] in LOG_KEYS

    @property
    def x_scale(self) -> Tuple[float, ...]:
        return tuple(0.3 if self.is_log(q) else 3.0
                     for q in range(self.n_params))

    @property
    def fd_steps(self) -> Tuple[float, ...]:
        return tuple(1e-3 if self.is_log(q) else 0.05
                     for q in range(self.n_params))

    # ---- transforms ---------------------------------------------------------
    def to_vector(self, nat: Dict[str, float]) -> np.ndarray:
        return np.array([math.log(nat[k]) if k in LOG_KEYS else nat[k] / 1e3
                         for k in self.param_keys])

    def to_natural(self, vec: np.ndarray) -> Dict[str, float]:
        """Estimated components merged with the held-fixed ones, so the
        forward model always receives a complete parameter set."""
        nat = dict(self.fixed)
        nat.update({k: (math.exp(vec[q]) if k in LOG_KEYS else vec[q] * 1e3)
                    for q, k in enumerate(self.param_keys)})
        return nat

    # ---- bounds --------------------------------------------------------------
    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        g = self.to_vector(self.initial_guess)
        lo, hi = np.empty(self.n_params), np.empty(self.n_params)
        for q, k in enumerate(self.param_keys):
            if k.startswith("K"):
                lo[q], hi[q] = g[q] - self.ln_K_halfwidth, g[q] + self.ln_K_halfwidth
            elif k in LOG_KEYS:
                lo[q], hi[q] = g[q] - self.ln_k_halfwidth, g[q] + self.ln_k_halfwidth
            else:
                lo[q], hi[q] = self.ea_bounds_J[0] / 1e3, self.ea_bounds_J[1] / 1e3
        return lo, hi

    def active_bounds(self, vec: np.ndarray,
                      rtol: float = 1e-6) -> Tuple[str, ...]:
        """Keys whose estimate is resting on its box constraint.

        A bounded least-squares solution that stops on a bound is not an
        estimate - it is the constraint.  The FIM-based covariance below is an
        UNCONSTRAINED local approximation and knows nothing about an active
        constraint, so every interval reported for such a component is
        meaningless.  Callers must surface these instead of printing a CI."""
        lo, hi = self.bounds()
        span = np.maximum(hi - lo, 1e-30)
        on = (vec <= lo + rtol * span) | (vec >= hi - rtol * span)
        return tuple(self.param_keys[q] for q in range(self.n_params) if on[q])

    # ---- uncertainty interpretation -----------------------------------------
    def rel_ci_percent(self, vec: np.ndarray, sigma: np.ndarray) -> np.ndarray:
        """Approximate 95% relative confidence half-widths, %, per parameter.
        For ln-transformed components: exp(1.96 sigma) - 1;
        for Ea: 1.96 sigma / |Ea|."""
        out = np.empty(self.n_params)
        for q in range(self.n_params):
            if self.is_log(q):
                arg = 1.96 * sigma[q]
                # a rank-deficient FIM can give astronomically large sigma;
                # report the CI as unbounded instead of overflowing exp()
                out[q] = ((math.exp(arg) - 1.0) * 100.0 if arg < 500.0
                          else float("inf"))
            else:
                out[q] = 1.96 * sigma[q] / max(abs(vec[q]), 1e-12) * 100.0
        return out
