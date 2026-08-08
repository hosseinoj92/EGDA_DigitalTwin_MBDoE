"""
Campaign resource accounting and the resource-aware utility terms.

Every quantity is accumulated from an auditable EVENT LOG (one event per
physical action), so tests can re-derive the totals.  All rate/cost numbers
are configurable CAMPAIGN-COST PROXIES, not validated hardware calorimetry -
in particular `energy_proxy` is a heating-power surrogate
(Q rho cp dT + ramp penalty), useful for ranking designs only.

Safety/equipment limits are HARD constraints enforced in bayes_design (a
candidate outside the admissible box is rejected, never merely penalized).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


@dataclass(frozen=True)
class ResourceCosts:
    """Assumed cost/rate parameters (simulation proxies; CAL where the real
    plant will provide numbers)."""
    stabilization_volumes: float = 3.0     # reactor volumes to steady state
    temp_change_s_per_K: float = 20.0      # CAL: thermostat ramp rate
    temp_ambient_C: float = 25.0
    nmr_acquisition_s: float = 60.0        # per spectrum (n_scans folded in)
    capillary_speed_m_s: float = 0.002     # CAL: capillary drive speed
    flush_time_s: float = 30.0             # per position change
    sample_volume_mL: float = 0.3          # withdrawn per acquisition
    flush_volume_mL: float = 0.45          # line volume x flush_volumes
    rho_cp_J_per_mL_K: float = 4.18        # water-like heat capacity
    energy_ramp_J_per_K: float = 500.0     # thermostat ramp surrogate

    # utility weights (lambda_* of the resource-aware objective)
    lambda_time_per_s: float = 0.0
    lambda_material_per_mol: float = 0.0
    lambda_waste_per_mL: float = 0.0
    lambda_energy_per_kJ: float = 0.0
    lambda_switch: float = 0.0             # per operating-condition change
    lambda_motion_per_m: float = 0.0       # per m of capillary travel


@dataclass
class ResourceEvent:
    kind: str                              # condition_change | stabilize |
    #                                        acquisition | move | flush
    quantities: Dict[str, float] = field(default_factory=dict)


class ResourceMeter:
    """Accumulates the campaign's physical cost from logged events."""

    TOTAL_KEYS = ("time_s", "egda_mol", "acid_mol", "liquid_mL", "waste_mL",
                  "sample_mL", "nmr_acquisitions", "capillary_travel_m",
                  "condition_changes", "temperature_changes", "energy_kJ",
                  "reactor_conditions", "spatial_samples")

    def __init__(self, costs: ResourceCosts, reactor_volume_mL: float):
        self.costs = costs
        self.reactor_volume_mL = float(reactor_volume_mL)
        self.events: List[ResourceEvent] = []
        self._last_T_C: Optional[float] = None
        self._last_z_m: Optional[float] = None

    # ------------------------------------------------------------------ #
    def log_condition(self, T_C: float, Q_total_mL_min: float,
                      C_EGDA_M: float, C_cat_M: float) -> None:
        """Reactor condition set + stabilization to steady state."""
        c = self.costs
        dT = abs(T_C - self._last_T_C) if self._last_T_C is not None else 0.0
        ramp_s = dT * c.temp_change_s_per_K
        stab_mL = c.stabilization_volumes * self.reactor_volume_mL
        stab_s = stab_mL / max(Q_total_mL_min, 1e-9) * 60.0
        heat_kJ = (Q_total_mL_min / 60.0 * (ramp_s + stab_s)
                   * c.rho_cp_J_per_mL_K
                   * max(T_C - c.temp_ambient_C, 0.0)
                   + c.energy_ramp_J_per_K * dT) / 1e3
        q_frac = 0.5                       # streams mixed 1:1 (Q1 = Q2)
        self.events.append(ResourceEvent("condition_change", {
            "time_s": ramp_s + stab_s,
            "egda_mol": C_EGDA_M * q_frac * Q_total_mL_min / 60.0
                        * (ramp_s + stab_s) / 1e3,
            "acid_mol": C_cat_M * q_frac * Q_total_mL_min / 60.0
                        * (ramp_s + stab_s) / 1e3,
            "liquid_mL": Q_total_mL_min / 60.0 * (ramp_s + stab_s),
            "waste_mL": Q_total_mL_min / 60.0 * (ramp_s + stab_s),
            "energy_kJ": heat_kJ,
            "condition_changes": 1.0 if self._last_T_C is not None else 0.0,
            "temperature_changes": 1.0 if dT > 1e-9 else 0.0,
            "reactor_conditions": 1.0,
        }))
        self._last_T_C = T_C

    def log_acquisition(self, z_m: float, u_T_C: float,
                        Q_total_mL_min: float, C_EGDA_M: float,
                        C_cat_M: float) -> None:
        """Capillary move + flush + one NMR acquisition at position z."""
        c = self.costs
        travel = (abs(z_m - self._last_z_m)
                  if self._last_z_m is not None else 0.0)
        move_s = travel / max(c.capillary_speed_m_s, 1e-12)
        acq_s = c.nmr_acquisition_s + c.flush_time_s + move_s
        feed_mL = Q_total_mL_min / 60.0 * acq_s
        self.events.append(ResourceEvent("acquisition", {
            "time_s": acq_s,
            "egda_mol": C_EGDA_M * 0.5 * feed_mL / 1e3,
            "acid_mol": C_cat_M * 0.5 * feed_mL / 1e3,
            "liquid_mL": feed_mL,
            "waste_mL": feed_mL + c.sample_volume_mL + c.flush_volume_mL,
            "sample_mL": c.sample_volume_mL + c.flush_volume_mL,
            "nmr_acquisitions": 1.0,
            "capillary_travel_m": travel,
            "spatial_samples": 1.0,
            "energy_kJ": (Q_total_mL_min / 60.0 * acq_s
                          * c.rho_cp_J_per_mL_K
                          * max(u_T_C - c.temp_ambient_C, 0.0)) / 1e3,
        }))
        self._last_z_m = z_m

    # ------------------------------------------------------------------ #
    def totals(self) -> Dict[str, float]:
        out = {k: 0.0 for k in self.TOTAL_KEYS}
        for ev in self.events:
            for k, v in ev.quantities.items():
                out[k] = out.get(k, 0.0) + v
        return out

    def cost_of_candidate(self, T_C: float, Q_total_mL_min: float,
                          C_EGDA_M: float, C_cat_M: float,
                          z_positions: np.ndarray) -> float:
        """Scalar penalty term of the resource-aware utility for a
        HYPOTHETICAL experiment (no events are logged).  Uses the lambda_*
        weights; returns 0 when all weights are zero."""
        c = self.costs
        dT = abs(T_C - self._last_T_C) if self._last_T_C is not None else 0.0
        ramp_s = dT * c.temp_change_s_per_K
        stab_mL = c.stabilization_volumes * self.reactor_volume_mL
        stab_s = stab_mL / max(Q_total_mL_min, 1e-9) * 60.0
        z_sorted = np.sort(np.asarray(z_positions, dtype=float))
        z_start = self._last_z_m if self._last_z_m is not None else z_sorted[0]
        travel = float(abs(z_sorted[0] - z_start)
                       + np.sum(np.abs(np.diff(z_sorted))))
        n_acq = len(z_sorted)
        acq_s = n_acq * (c.nmr_acquisition_s + c.flush_time_s) \
            + travel / max(c.capillary_speed_m_s, 1e-12)
        time_s = ramp_s + stab_s + acq_s
        feed_mL = Q_total_mL_min / 60.0 * time_s
        egda = C_EGDA_M * 0.5 * feed_mL / 1e3
        waste = feed_mL + n_acq * (c.sample_volume_mL + c.flush_volume_mL)
        energy_kJ = (feed_mL * c.rho_cp_J_per_mL_K
                     * max(T_C - c.temp_ambient_C, 0.0)
                     + c.energy_ramp_J_per_K * dT) / 1e3
        switches = 1.0 if (self._last_T_C is not None and dT > 1e-9) else 0.0
        return (c.lambda_time_per_s * time_s
                + c.lambda_material_per_mol * egda
                + c.lambda_waste_per_mL * waste
                + c.lambda_energy_per_kJ * energy_kJ
                + c.lambda_switch * switches
                + c.lambda_motion_per_m * travel)
