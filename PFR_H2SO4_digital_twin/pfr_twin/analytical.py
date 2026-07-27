"""
Algebraic reference solutions used to verify the numerical integrator.

1. Irreversible limit (reversible = False): the network is the linear
   pseudo-first-order series reaction A -> B -> C with the closed form

    C_A(tau) = C_A0 exp(-kappa1 tau)

    C_B(tau) = C_B0 exp(-kappa2 tau)
             + C_A0 kappa1/(kappa2 - kappa1) [exp(-kappa1 tau) - exp(-kappa2 tau)]
               (degenerate case kappa1 == kappa2 handled by the L'Hopital limit)

    C_C  from backbone balance :  C_A + C_B + C_C = const
    AcOH from acetate balance  :  2 C_A + C_B + C_AcOH = const
    H2O  from oxygen/water balance: C_H2O + C_AcOH = const

   (kappa1 = k1[H+], kappa2 = k2[H+], residence time tau = x/u).

2. Reversible model: no closed-form transient exists (the ODEs are bilinear),
   but the t -> infinity state is fixed by the two coupled equilibrium
   conditions Q1 = K1, Q2 = K2.  `equilibrium_state` solves them for the
   reaction extents (x1, x2); the integrator must (i) conserve the same three
   linear invariants as above and (ii) converge to this composition at long
   residence times, and the net rates must vanish there.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from scipy.optimize import brentq

from .mixer import InletState


def analytical_profiles(inlet: InletState, kappa1: float, kappa2: float,
                        tau_s: np.ndarray) -> Dict[str, np.ndarray]:
    ca0 = inlet.conc["EGDA"]
    cb0 = inlet.conc["EGMA"]
    cc0 = inlet.conc["EG"]
    cd0 = inlet.conc["AcOH"]
    cw0 = inlet.conc["H2O"]

    e1 = np.exp(-kappa1 * tau_s)
    e2 = np.exp(-kappa2 * tau_s)

    ca = ca0 * e1
    if abs(kappa2 - kappa1) > 1e-12 * max(kappa1, kappa2, 1e-30):
        cb = cb0 * e2 + ca0 * kappa1 / (kappa2 - kappa1) * (e1 - e2)
    else:  # kappa1 == kappa2
        cb = (cb0 + ca0 * kappa1 * tau_s) * e1

    cc = cc0 + (ca0 - ca) + (cb0 - cb)          # backbone balance
    cd = cd0 + 2.0 * (ca0 - ca) + (cb0 - cb)    # acetate-group balance
    cw = cw0 - (cd - cd0)                       # one water per acetate released

    # OH- is inert on the acid route (the only route with a closed form)
    c_oh = np.full_like(tau_s, float(inlet.conc.get("OH", 0.0)))
    return {"EGDA": ca, "EGMA": cb, "EG": cc, "AcOH": cd, "H2O": cw,
            "OH": c_oh}


def max_relative_error(numerical: Dict[str, np.ndarray],
                       analytical: Dict[str, np.ndarray],
                       scale: float) -> float:
    """Largest |numerical - analytical| across species, relative to `scale`."""
    err = 0.0
    for sp, ana in analytical.items():
        err = max(err, float(np.max(np.abs(numerical[sp] - ana))) / scale)
    return err


# ---------------------------------------------------------------------------
# Reversible model: coupled chemical equilibrium
# ---------------------------------------------------------------------------
def reaction_quotients(conc: Dict[str, float]) -> Tuple[float, float]:
    """Concentration-based reaction quotients (Q1, Q2) of the two steps;
    NaN where the denominator vanishes (e.g. ester already exhausted)."""
    d1 = conc["EGDA"] * conc["H2O"]
    d2 = conc["EGMA"] * conc["H2O"]
    q1 = conc["EGMA"] * conc["AcOH"] / d1 if d1 > 0.0 else float("nan")
    q2 = conc["EG"] * conc["AcOH"] / d2 if d2 > 0.0 else float("nan")
    return q1, q2


def _bracketed_root(f, lo: float, hi: float) -> float:
    """Root of a monotonically increasing f on [lo, hi] with f(lo) <= 0 <= f(hi)."""
    eps = 1e-15 * max(1.0, abs(lo), abs(hi))
    lo, hi = lo + eps, hi - eps
    if hi <= lo:
        return 0.5 * (lo + hi)
    flo, fhi = f(lo), f(hi)
    if flo >= 0.0:
        return lo
    if fhi <= 0.0:
        return hi
    return brentq(f, lo, hi, xtol=1e-15, rtol=8.881784197001252e-16)


def equilibrium_state(conc0: Dict[str, float], K1: float, K2: float,
                      tol: float = 1e-13, max_iter: int = 500) -> Dict[str, float]:
    """Composition at simultaneous chemical equilibrium of both steps.

    Solves for the reaction extents (x1, x2), mol/L, of

        EGDA + H2O <-> EGMA + AcOH        (extent x1)
        EGMA + H2O <-> EG   + AcOH        (extent x2)

    such that Q1 = K1 and Q2 = K2, by Gauss-Seidel alternation: each
    one-extent condition is monotone in its own extent, hence has a unique
    bracketed root (Brent).  Negative extents (esterification direction) are
    handled naturally.  Returns the equilibrium concentrations plus the
    extents under keys "x1", "x2".
    """
    if K1 <= 0.0 or K2 <= 0.0:
        raise ValueError("equilibrium_state requires positive K1, K2.")
    a0, b0, c0 = conc0["EGDA"], conc0["EGMA"], conc0["EG"]
    d0, w0 = conc0["AcOH"], conc0["H2O"]

    x1 = x2 = 0.0
    for _ in range(max_iter):
        x1_old, x2_old = x1, x2

        def f1(x1_, x2_=x2):
            return ((b0 + x1_ - x2_) * (d0 + x1_ + x2_)
                    - K1 * (a0 - x1_) * (w0 - x1_ - x2_))

        x1 = _bracketed_root(f1, max(x2 - b0, -d0 - x2), min(a0, w0 - x2))

        def f2(x2_, x1_=x1):
            return ((c0 + x2_) * (d0 + x1_ + x2_)
                    - K2 * (b0 + x1_ - x2_) * (w0 - x1_ - x2_))

        x2 = _bracketed_root(f2, max(-c0, -d0 - x1), min(b0 + x1, w0 - x1))

        scale = max(1.0, abs(x1), abs(x2))
        if max(abs(x1 - x1_old), abs(x2 - x2_old)) < tol * scale:
            break

    return {"EGDA": a0 - x1, "EGMA": b0 + x1 - x2, "EG": c0 + x2,
            "AcOH": d0 + x1 + x2, "H2O": w0 - x1 - x2,
            "OH": conc0.get("OH", 0.0), "x1": x1, "x2": x2}
