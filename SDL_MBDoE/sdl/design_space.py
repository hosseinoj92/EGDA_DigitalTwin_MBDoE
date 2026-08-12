"""
Continuous design space: instrument resolution and bounded refinement.

WHY THIS EXISTS.  The classical campaign picks operating conditions from a
declared factorial grid (7 temperatures x 3 flows x 2 acid levels).  That is
a modelling convenience, not a hardware limit: a thermostat accepts 97.3 C
as readily as 100 C, and restricting the optimizer to grid corners throws
away information for nothing.  Continuous mode lets the design optimizer
propose any point inside the declared bounds - but a real platform cannot
set an arbitrary real number either, so every proposal is SNAPPED to the
instrument's actual resolution before it is scored or executed.

THE TWO PROPERTIES THAT MAKE THIS SAFE

1. **Snap before scoring, never after.**  If the optimizer is scored on a
   continuous point and only the executed condition is rounded, the reported
   utility belongs to an experiment the hardware never runs.  `refine`
   therefore evaluates the objective at the SNAPPED point, so the score that
   drives the decision is the score of the experiment that will actually
   happen.

2. **Never worse than the grid.**  The refined point is accepted only if its
   score BEATS the best discrete candidate's.  Continuous mode can therefore
   only match or improve on discrete mode by the design criterion - it can
   never lose to it because an optimizer wandered into a bad basin or a
   snapped point landed badly.  `refine` returns the discrete winner
   unchanged whenever refinement fails to improve it.

Resolutions are the instrument's, not the model's, and are configurable:

    temperature       0.1 C
    total flow        0.1 mL/min
    catalyst molarity 0.1 mM   (1e-4 M)
    EGDA molarity     0.1 mM   (1e-4 M)

A dimension whose bounds are degenerate (lo == hi, e.g. an EGDA feed fixed
at 1.0 M) is held FIXED rather than optimized - it is a declared constant of
the campaign, not a free variable, and handing it to the optimizer would
only add a dimension with no gradient.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize

from .layer1_bridge import OperatingConditions

#: the four controllable design variables, in the canonical vector order
DESIGN_VARIABLES = ("T_C", "Q_total_mL_min", "C_cat_M", "C_EGDA_M")


@dataclass(frozen=True)
class DesignResolution:
    """Smallest change the PLATFORM can actually command, per variable.

    Set a resolution to 0 to leave that variable unrounded (a mathematical
    idealization - useful for studying the effect of the grid itself, not
    for a design a machine has to execute)."""
    T_C: float = 0.1                 # deg C
    Q_total_mL_min: float = 0.1      # mL/min
    C_cat_M: float = 1e-4            # 0.1 mM
    C_EGDA_M: float = 1e-4           # 0.1 mM

    def as_vector(self) -> np.ndarray:
        return np.array([self.T_C, self.Q_total_mL_min,
                         self.C_cat_M, self.C_EGDA_M], dtype=float)

    def snap_vector(self, x: Sequence[float],
                    bounds: Optional[Sequence[Tuple[float, float]]] = None
                    ) -> np.ndarray:
        """Round to the resolution grid, then clamp back inside bounds.

        Clamping AFTER rounding matters: rounding 159.97 C at 0.1 C gives
        160.0 C, which is fine, but rounding 160.04 would give 160.0 too
        while rounding 8.04 mL/min at 0.1 could give 8.0 - and a proposal
        just outside a bound could round outside it.  The clamp guarantees
        the returned point is executable."""
        x = np.asarray(x, dtype=float).copy()
        res = self.as_vector()
        for i in range(len(x)):
            if res[i] > 0:
                x[i] = np.round(x[i] / res[i]) * res[i]
        if bounds is not None:
            for i, (lo, hi) in enumerate(bounds):
                x[i] = min(max(x[i], lo), hi)
                # a clamp can leave the value off-grid; re-snap INTO the
                # interval by moving to the nearest grid point that is still
                # inside it
                if res[i] > 0:
                    up = np.ceil(lo / res[i]) * res[i]
                    dn = np.floor(hi / res[i]) * res[i]
                    if up <= dn:
                        x[i] = min(max(np.round(x[i] / res[i]) * res[i],
                                       up), dn)
        return x

    def snap(self, u: OperatingConditions,
             bounds: Optional[Sequence[Tuple[float, float]]] = None
             ) -> OperatingConditions:
        return from_vector(self.snap_vector(to_vector(u), bounds))


#: resolution fine enough to be invisible - the historical behaviour, kept
#: available so a run can be compared against the unrounded ideal
IDEAL_RESOLUTION = DesignResolution(T_C=0.0, Q_total_mL_min=0.0,
                                    C_cat_M=0.0, C_EGDA_M=0.0)


def to_vector(u: OperatingConditions) -> np.ndarray:
    return np.array([u.T_C, u.Q1_mL_min + u.Q2_mL_min,
                     u.C_cat_M, u.C_EGDA_M], dtype=float)


def from_vector(x: Sequence[float]) -> OperatingConditions:
    t, q, cat, egda = (float(v) for v in x)
    return OperatingConditions(T_C=t, Q1_mL_min=q / 2.0, Q2_mL_min=q / 2.0,
                               C_EGDA_M=egda, C_cat_M=cat)


def bounds_vector(continuous_bounds: Dict[str, Sequence[float]]
                  ) -> Tuple[Tuple[float, float], ...]:
    """Validated (lo, hi) per design variable, in canonical order.

    Unlike a strict optimizer bound check this ACCEPTS lo == hi: a variable
    the campaign declares constant (EGDA fixed at 1.0 M) is a legitimate
    design space, and refusing it would make continuous mode unusable on the
    very configuration the benchmark ships with."""
    missing = [k for k in DESIGN_VARIABLES if k not in continuous_bounds]
    if missing:
        raise ValueError("continuous_bounds is missing: " + ", ".join(missing))
    out = []
    for key in DESIGN_VARIABLES:
        raw = continuous_bounds[key]
        if len(raw) != 2:
            raise ValueError(f"continuous_bounds['{key}'] must be [low, high].")
        lo, hi = float(raw[0]), float(raw[1])
        if not (np.isfinite(lo) and np.isfinite(hi)) or lo > hi:
            raise ValueError(f"Invalid continuous bounds for {key}: {raw}.")
        if key != "T_C" and lo <= 0.0:
            raise ValueError(f"The lower bound for {key} must be positive.")
        out.append((lo, hi))
    return tuple(out)


def free_indices(bounds: Sequence[Tuple[float, float]],
                 resolution: DesignResolution) -> Tuple[int, ...]:
    """Which variables are genuinely free to optimize.

    A dimension is fixed when its bounds coincide, and also when the whole
    interval is narrower than one resolution step - there is no second
    commandable setting inside it, so optimizing it is meaningless."""
    res = resolution.as_vector()
    out = []
    for i, (lo, hi) in enumerate(bounds):
        if hi <= lo:
            continue
        if res[i] > 0 and (hi - lo) < res[i]:
            continue
        out.append(i)
    return tuple(out)


def refine(score_of: Callable[[OperatingConditions], float],
           u_start: OperatingConditions,
           score_start: float,
           continuous_bounds: Dict[str, Sequence[float]],
           resolution: DesignResolution = DesignResolution(),
           maxiter: int = 40,
           n_restarts: int = 0,
           rng: Optional[np.random.Generator] = None
           ) -> Tuple[OperatingConditions, float, bool]:
    """Bounded continuous refinement of ONE operating point.

    `score_of` is maximized and must already include every penalty the caller
    cares about (cost, constraints); it is evaluated only at SNAPPED points,
    so the number it returns always belongs to an executable experiment.

    Returns (u, score, improved).  When refinement does not beat
    `score_start`, the ORIGINAL point and score come back with
    improved=False - continuous mode is then exactly discrete mode for that
    round, which is what makes it safe to enable unconditionally.

    `n_restarts` > 0 adds Latin-hypercube-style restarts drawn from `rng`.
    They consume the caller's generator, so a caller that must stay
    reproducible should pass its own seeded one (the selectors do).
    """
    bounds = bounds_vector(continuous_bounds)
    free = free_indices(bounds, resolution)
    if not free:
        return u_start, score_start, False

    x0_full = resolution.snap_vector(to_vector(u_start), bounds)

    def expand(x_free: Sequence[float]) -> np.ndarray:
        x = x0_full.copy()
        for k, i in enumerate(free):
            x[i] = x_free[k]
        return resolution.snap_vector(x, bounds)

    def objective(x_free: Sequence[float]) -> float:
        try:
            s = score_of(from_vector(expand(x_free)))
        except (ValueError, RuntimeError, FloatingPointError,
                np.linalg.LinAlgError):
            return 1e100
        return -s if np.isfinite(s) else 1e100

    sub_bounds = [bounds[i] for i in free]
    starts = [np.array([x0_full[i] for i in free], dtype=float)]
    if n_restarts > 0 and rng is not None:
        for _ in range(int(n_restarts)):
            starts.append(np.array([rng.uniform(lo, hi)
                                    for lo, hi in sub_bounds]))

    best_u, best_s, improved = u_start, score_start, False
    for x_start in starts:
        try:
            sol = minimize(objective, x_start, method="Powell",
                           bounds=sub_bounds,
                           options={"maxiter": int(maxiter),
                                    "xtol": 1e-3, "ftol": 1e-6})
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            continue
        u_ref = from_vector(expand(np.atleast_1d(sol.x)))
        try:
            s_ref = float(score_of(u_ref))
        except (ValueError, RuntimeError, FloatingPointError,
                np.linalg.LinAlgError):
            continue
        # STRICTLY better, so a numerically identical result never replaces
        # the grid point - discrete and continuous stay comparable
        if np.isfinite(s_ref) and s_ref > best_s:
            best_u, best_s, improved = u_ref, s_ref, True
    return best_u, best_s, improved
