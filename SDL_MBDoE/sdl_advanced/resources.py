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

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

import numpy as np


@dataclass(frozen=True)
class ResourceCosts:
    """Assumed cost/rate parameters (simulation proxies; CAL where the real
    plant will provide numbers)."""
    stabilization_volumes: float = 3.0     # reactor volumes to steady state
    temp_change_s_per_K: float = 20.0      # CAL: thermostat ramp rate
    temp_ambient_C: float = 25.0
    # ---- NMR measurement time, decomposed ------------------------------ #
    # Previously ONE lumped `nmr_acquisition_s = 60 s` per spectrum, which
    # was independent of acquisition_time_s / repetition_time_s / n_scans -
    # so an archive could report an acquisition setting that had no effect
    # on the campaign clock.  The duration is now
    #
    #   t_spectrum = fixed_overhead + n_scans * (recycle + acquisition)
    #
    # The physical terms are SYNCHRONIZED from AcquisitionSettings (see
    # `from_acquisition`), so the spectrometer settings and the campaign
    # clock cannot disagree.  The overhead is everything the pulse program
    # does not cover - sample settling in the flow cell, lock/shim, transfer
    # to the console, processing - and is a CAL assumption: its default is
    # the residue of the old lumped 60 s at the shipped acquisition
    # (60 - 1 x (15 + 4.0956) = 40.9 s), so the shipped campaign clock is
    # unchanged while its composition is now explicit.
    nmr_fixed_overhead_s: float = 40.9
    nmr_recycle_s: float = 15.0            # recycle delay between scans
    nmr_n_scans: int = 1
    nmr_acquisition_time_s: float = 4.0956  # ACTUAL, from AcquisitionSettings
    #: LEGACY COMPATIBILITY, clearly labelled: when set, this fixed
    #: per-spectrum duration is used verbatim and the decomposition above is
    #: ignored.  Provided only to reproduce archives produced before the
    #: decomposition existed; it is never the default.
    legacy_fixed_nmr_time_s: Optional[float] = None
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


    @property
    def nmr_spectrum_time_s(self) -> float:
        """Wall-clock time for ONE spectrum, decomposed as documented."""
        if self.legacy_fixed_nmr_time_s is not None:
            return float(self.legacy_fixed_nmr_time_s)
        return (float(self.nmr_fixed_overhead_s)
                + max(int(self.nmr_n_scans), 1)
                * (float(self.nmr_recycle_s)
                   + float(self.nmr_acquisition_time_s)))

    def nmr_time_report(self) -> Dict[str, float]:
        """The decomposition, for the run record."""
        return {"nmr_spectrum_time_s": self.nmr_spectrum_time_s,
                "nmr_fixed_overhead_s": float(self.nmr_fixed_overhead_s),
                "nmr_recycle_s": float(self.nmr_recycle_s),
                "nmr_n_scans": int(self.nmr_n_scans),
                "nmr_acquisition_time_s": float(self.nmr_acquisition_time_s),
                "legacy_fixed_nmr_time_s": self.legacy_fixed_nmr_time_s,
                "model": ("LEGACY fixed per-spectrum time"
                          if self.legacy_fixed_nmr_time_s is not None
                          else "overhead + n_scans x (recycle + acquisition)")}

    def with_acquisition(self, acq) -> "ResourceCosts":
        """Synchronize the physical timing terms with the spectrometer
        settings, so the campaign clock and the acquisition contract can
        never drift apart.  `acq` is an AcquisitionSettings; only its
        ACTUAL acquisition time is used (the requested value differs by up
        to one dwell period)."""
        return replace(self,
                       nmr_recycle_s=float(acq.repetition_time_s),
                       nmr_n_scans=int(acq.n_scans),
                       nmr_acquisition_time_s=float(
                           acq.actual_acquisition_time_s))


@dataclass
class ResourceEvent:
    kind: str                              # condition_change | stabilize |
    #                                        acquisition | move | flush
    quantities: Dict[str, float] = field(default_factory=dict)


class ResourceMeter:
    """Accumulates the campaign's physical cost from logged events."""

    TOTAL_KEYS = ("time_s", "egda_mol", "acid_mol", "liquid_mL", "waste_mL",
                  "sample_mL", "nmr_acquisitions", "nmr_reacquisitions",
                  "qc_rejected", "capillary_travel_m",
                  "condition_changes", "temperature_changes", "energy_kJ",
                  "reactor_conditions", "spatial_samples")

    #: relative tolerance when deciding whether a condition actually changed
    _COND_RTOL = 1e-9

    def __init__(self, costs: ResourceCosts, reactor_volume_mL: float):
        self.costs = costs
        self.reactor_volume_mL = float(reactor_volume_mL)
        self.events: List[ResourceEvent] = []
        #: FULL last condition (T, Q_total, C_EGDA, C_cat) - a change in ANY
        #: of them is a condition change; z-moves alone never re-stabilize
        self._last_cond: Optional[tuple] = None
        self._last_z_m: Optional[float] = None

    # ------------------------------------------------------------------ #
    def _cond_changed(self, cond: tuple) -> bool:
        if self._last_cond is None:
            return True
        return any(abs(a - b) > self._COND_RTOL * max(abs(a), abs(b), 1.0)
                   for a, b in zip(cond, self._last_cond))

    def log_condition(self, T_C: float, Q_total_mL_min: float,
                      C_EGDA_M: float, C_cat_M: float) -> None:
        """Reactor condition set + stabilization to steady state.

        Idempotent for an UNCHANGED condition: re-sampling positions at the
        same (T, Q, C_EGDA, C_cat) logs a zero-cost 'condition_hold' event
        (audit trail) and NO new stabilization - moving the capillary does
        not perturb the reactor."""
        cond = (float(T_C), float(Q_total_mL_min), float(C_EGDA_M),
                float(C_cat_M))
        if not self._cond_changed(cond):
            self.events.append(ResourceEvent("condition_hold", {}))
            return
        c = self.costs
        dT = (abs(T_C - self._last_cond[0])
              if self._last_cond is not None else 0.0)
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
            "condition_changes": 1.0 if self._last_cond is not None else 0.0,
            "temperature_changes": 1.0 if dT > 1e-9 else 0.0,
            "reactor_conditions": 1.0,
        }))
        self._last_cond = cond

    def log_acquisition(self, z_m: float, u_T_C: float,
                        Q_total_mL_min: float, C_EGDA_M: float,
                        C_cat_M: float, retry: bool = False) -> None:
        """Capillary move + flush + one NMR acquisition at position z.
        retry=True marks a QC-triggered reacquisition (separately counted)."""
        c = self.costs
        travel = (abs(z_m - self._last_z_m)
                  if self._last_z_m is not None else 0.0)
        move_s = travel / max(c.capillary_speed_m_s, 1e-12)
        acq_s = c.nmr_spectrum_time_s + c.flush_time_s + move_s
        feed_mL = Q_total_mL_min / 60.0 * acq_s
        self.events.append(ResourceEvent(
            "reacquisition" if retry else "acquisition", {
                "time_s": acq_s,
                "egda_mol": C_EGDA_M * 0.5 * feed_mL / 1e3,
                "acid_mol": C_cat_M * 0.5 * feed_mL / 1e3,
                "liquid_mL": feed_mL,
                "waste_mL": feed_mL + c.sample_volume_mL + c.flush_volume_mL,
                "sample_mL": c.sample_volume_mL + c.flush_volume_mL,
                "nmr_acquisitions": 1.0,
                "nmr_reacquisitions": 1.0 if retry else 0.0,
                "capillary_travel_m": travel,
                "spatial_samples": 0.0 if retry else 1.0,
                "energy_kJ": (Q_total_mL_min / 60.0 * acq_s
                              * c.rho_cp_J_per_mL_K
                              * max(u_T_C - c.temp_ambient_C, 0.0)) / 1e3,
            }))
        self._last_z_m = z_m

    def log_qc_reject(self, z_m: float) -> None:
        """A position whose data was rejected by the QC gate (not
        assimilated); auditable, no physical cost beyond the acquisitions
        already logged."""
        self.events.append(ResourceEvent("qc_reject", {"qc_rejected": 1.0}))

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
        weights; returns 0 when all weights are zero.  Uses the SAME
        assumptions as the realized event accounting: an unchanged full
        condition incurs NO stabilization/ramp/switch cost."""
        c = self.costs
        cond = (float(T_C), float(Q_total_mL_min), float(C_EGDA_M),
                float(C_cat_M))
        changed = self._cond_changed(cond)
        dT = (abs(T_C - self._last_cond[0])
              if (changed and self._last_cond is not None) else 0.0)
        ramp_s = dT * c.temp_change_s_per_K if changed else 0.0
        stab_s = ((c.stabilization_volumes * self.reactor_volume_mL)
                  / max(Q_total_mL_min, 1e-9) * 60.0 if changed else 0.0)
        z_sorted = np.sort(np.asarray(z_positions, dtype=float))
        z_start = self._last_z_m if self._last_z_m is not None else z_sorted[0]
        travel = float(abs(z_sorted[0] - z_start)
                       + np.sum(np.abs(np.diff(z_sorted))))
        n_acq = len(z_sorted)
        acq_s = n_acq * (c.nmr_spectrum_time_s + c.flush_time_s) \
            + travel / max(c.capillary_speed_m_s, 1e-12)
        time_s = ramp_s + stab_s + acq_s
        feed_mL = Q_total_mL_min / 60.0 * time_s
        egda = C_EGDA_M * 0.5 * feed_mL / 1e3
        waste = feed_mL + n_acq * (c.sample_volume_mL + c.flush_volume_mL)
        energy_kJ = (feed_mL * c.rho_cp_J_per_mL_K
                     * max(T_C - c.temp_ambient_C, 0.0)
                     + c.energy_ramp_J_per_K * dT) / 1e3
        switches = 1.0 if (changed and self._last_cond is not None) else 0.0
        return (c.lambda_time_per_s * time_s
                + c.lambda_material_per_mol * egda
                + c.lambda_waste_per_mL * waste
                + c.lambda_energy_per_kJ * energy_kJ
                + c.lambda_switch * switches
                + c.lambda_motion_per_m * travel)
