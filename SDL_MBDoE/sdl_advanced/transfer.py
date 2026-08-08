"""
Sample-transfer model for the single moving CPR capillary.

Hardware represented (Reacnostics CPR + Fourier 80):

    one axially moving sampling capillary (orifice at position z)
    -> one fixed transfer line -> NMR flow cell.

There are NO fixed ports and NO selector valve; z is continuous.

Effects modelled (all optional; every one disabled -> identity transform):

  * mean transfer delay        tau(z) = V_transfer(z) / Q_sample
  * position-dependent volume  V(z) = V_fixed  (constant), or
                               V(z) = V_fixed + v_per_m * (L - z)  ("linear":
                               the capillary's internal path lengthens as the
                               orifice moves toward the inlet; the geometry
                               is NOT frozen yet, hence configurable)
  * RTD dispersion             gamma / tanks-in-series distribution with
                               shape n_tanks; n_tanks -> inf or rtd="delta"
                               recovers plug flow (the legacy
                               `transfer_time_s` limit)
  * continued reaction         each residence-time quadrature node is
                               propagated with the TRUE kinetics at the
                               transfer-LINE temperature (not the reactor's)
  * carryover                  after the capillary moves, the line initially
                               holds the previous sample; an exponential
                               flushing model mixes old and new:
                               f_carry = exp(-V_flush / V_line)

The kinetic propagator is INJECTED by the instrument (it closes over the
hidden true parameters); this module itself holds no truth.

All volumes/flows are ASSUMED plausible values until the physical geometry
is frozen - marked CAL where hardware calibration will replace them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import numpy as np
from scipy.stats import gamma as gamma_dist

#: propagator signature: (conc: Dict[str,float], tau_s: float) -> Dict[str,float]
Propagator = Callable[[Dict[str, float], float], Dict[str, float]]


@dataclass(frozen=True)
class TransferConfig:
    enabled: bool = False
    Q_sample_mL_min: float = 0.5        # CAL: analytical withdrawal flow
    V_fixed_mL: float = 0.15            # CAL: fixed line volume to the cell
    geometry: str = "constant"          # "constant" | "linear"
    v_per_m_mL: float = 0.0             # CAL: extra volume per m of capillary
    rtd: str = "delta"                  # "delta" | "gamma"
    n_tanks: float = 4.0                # gamma shape (tanks-in-series)
    n_quad: int = 5                     # quadrature nodes over the RTD
    T_line_C: Optional[float] = None    # None -> sample keeps the reactor T
    react_in_line: bool = True          # continued reaction during transfer
    carryover: bool = False
    flush_volumes: float = 3.0          # line volumes pumped after a move

    def V_transfer_mL(self, z_m: float, length_m: float) -> float:
        if self.geometry == "linear":
            return self.V_fixed_mL + self.v_per_m_mL * max(length_m - z_m, 0.0)
        return self.V_fixed_mL

    def mean_tau_s(self, z_m: float, length_m: float) -> float:
        q = max(self.Q_sample_mL_min, 1e-9) / 60.0          # mL/s
        return self.V_transfer_mL(z_m, length_m) / q


class TransferLine:
    """Stateful virtual transfer line (owned by the instrument).

    Remembers the composition left in the line by the PREVIOUS sample so a
    capillary move causes realistic carryover until the line is flushed."""

    def __init__(self, cfg: TransferConfig, length_m: float):
        self.cfg = cfg
        self.length_m = float(length_m)
        self._prev_conc: Optional[Dict[str, float]] = None
        self._prev_z: Optional[float] = None

    # ------------------------------------------------------------------ #
    def _rtd_nodes(self, tau_mean: float):
        """(taus, weights) of the residence-time quadrature."""
        cfg = self.cfg
        if cfg.rtd == "delta" or tau_mean <= 0.0:
            return np.array([tau_mean]), np.array([1.0])
        shape = max(cfg.n_tanks, 1.0)
        scale = tau_mean / shape
        # midpoint rule on equal-probability slices of the gamma CDF:
        # deterministic, positive weights, exact mean as n_quad -> inf
        n = max(cfg.n_quad, 1)
        probs = (np.arange(n) + 0.5) / n
        taus = gamma_dist.ppf(probs, a=shape, scale=scale)
        return taus, np.full(n, 1.0 / n)

    def _through_line(self, conc: Dict[str, float], z_m: float,
                      propagate: Propagator) -> Dict[str, float]:
        cfg = self.cfg
        tau_mean = cfg.mean_tau_s(z_m, self.length_m)
        if tau_mean <= 0.0 or not cfg.react_in_line:
            return dict(conc)
        taus, wts = self._rtd_nodes(tau_mean)
        out = {sp: 0.0 for sp in conc}
        for tau, w in zip(taus, wts):
            prop = propagate(conc, float(tau))
            for sp in out:
                out[sp] += w * prop[sp]
        return out

    # ------------------------------------------------------------------ #
    def sample(self, conc_at_z: Dict[str, float], z_m: float,
               propagate: Propagator) -> Dict[str, float]:
        """Composition arriving at the NMR cell for a sample drawn at z.
        Applies (in order): line reaction/dispersion, then carryover from
        the previous position, then updates the line state."""
        if not self.cfg.enabled:
            self._prev_conc = dict(conc_at_z)
            self._prev_z = z_m
            return dict(conc_at_z)
        seen = self._through_line(conc_at_z, z_m, propagate)
        # explicit None handling: z = 0.0 is a legitimate previous position
        # and must NOT be treated as "no previous position" (falsy-zero bug)
        moved = (self._prev_z is not None
                 and abs(z_m - self._prev_z) > 0.0)
        if self.cfg.carryover and self._prev_conc is not None and moved:
            f = float(np.exp(-max(self.cfg.flush_volumes, 0.0)))
            mixed = {sp: (1.0 - f) * seen[sp]
                     + f * self._prev_conc.get(sp, 0.0) for sp in seen}
        else:
            mixed = seen
        self._prev_conc = dict(seen)      # the line ends filled with NEW sample
        self._prev_z = z_m
        return mixed

    def reset(self) -> None:
        self._prev_conc = None
        self._prev_z = None
