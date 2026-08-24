"""Tests of the MEASUREMENT_FAULT control state: QC gating BEFORE
assimilation, reacquisition, and safe pause.  Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import Layer1Bridge, OperatingConditions, NoiseModel
from sdl_advanced.controller import (QCGateConfig, QCMonitor,
                                     measure_with_qc, qc_fault_verdict,
                                     run_strategy_f)
from sdl_advanced.instrument import (AdvancedVirtualLaboratory,
                                     InstrumentConfig)
from sdl_advanced.model_ensemble import ModelEnsemble, build_egda_family
from sdl_advanced.resources import ResourceCosts
from sdl_advanced.spatial_design import SpatialDesignConfig
from sdl_advanced.spectral import AcquisitionSettings, SpectralNuisance
from sdl_advanced.transfer import TransferConfig

T_REF_K = 333.15
GEOM = {"length_m": 0.5, "diameter_m": 0.018}
TRUTH = {"k1_ref": 3.3e-3, "Ea1_J": 58_500.0,
         "k2_ref": 8.5e-4, "Ea2_J": 52_000.0,
         "K1_ref": 0.80, "K2_ref": 0.12}
U0 = OperatingConditions(T_C=80.0, Q1_mL_min=1.0, Q2_mL_min=1.0,
                         C_EGDA_M=1.0, C_cat_M=1.0)


def _lab(seed=0):
    bridge = Layer1Bridge(GEOM, T_REF_K)
    return AdvancedVirtualLaboratory(
        TRUTH, bridge,
        InstrumentConfig(observation_mode="nmr", nmr_mode="realistic"),
        AcquisitionSettings(n_points=2048), SpectralNuisance(),
        TransferConfig(enabled=False), ResourceCosts(), seed=seed)


class _Corruptor:
    """Wraps the truth simulator: corrupts the spectrum for the first
    `n_bad` acquisitions (a structured artifact no lineshape model fits)."""

    def __init__(self, lab, n_bad):
        self._orig = lab._nmr.simulate
        self.n_bad = n_bad
        self.calls = 0
        lab._nmr.simulate = self._call

    def _call(self, conc, rng=None):
        ppm, y, rl = self._orig(conc, rng)
        self.calls += 1
        if self.calls <= self.n_bad:
            y = y + 60.0 * np.abs(np.sin(ppm * 3.0))
        return ppm, y, rl


def test_bad_spectrum_rejected_then_recovered_by_reacquisition():
    lab = _lab(seed=1)
    _Corruptor(lab, n_bad=1)                  # only the FIRST acquisition bad
    qc = QCGateConfig(enabled=True, max_retries=2)
    m, n_rej, n_re, fault = measure_with_qc(lab, U0, [0.2, 0.4], qc)
    assert not fault
    assert n_re >= 1                          # reacquisition attempted
    assert n_rej == 0                         # recovered, nothing dropped
    assert m is not None and m.n_z == 2       # both positions delivered
    assert lab.meter.totals()["nmr_reacquisitions"] >= 1


def test_persistent_failure_drops_position_and_counts_it():
    lab = _lab(seed=2)
    _Corruptor(lab, n_bad=100)                # every acquisition corrupted
    qc = QCGateConfig(enabled=True, max_retries=1, max_reject_fraction=0.6)
    m, n_rej, n_re, fault = measure_with_qc(lab, U0, [0.2, 0.4], qc)
    assert n_rej == 2 and m is None and fault
    tot = lab.meter.totals()
    assert tot["qc_rejected"] == 2
    assert tot["nmr_reacquisitions"] == 2     # one retry per position


def test_campaign_pauses_safely_and_posterior_untouched():
    """Persistent instrument failure must pause the campaign - never update
    the kinetic posterior with corrupted data, never design new chemistry
    experiments on top of it."""
    lab = _lab(seed=3)
    _Corruptor(lab, n_bad=1000)
    ens = ModelEnsemble(build_egda_family(GEOM, T_REF_K,
                                          include=("rev-dilute",),
                                          noise_assumed=NoiseModel()))
    cands = [U0]
    res = run_strategy_f(
        lab, ens, cands, U0,
        SpatialDesignConfig(mode="fixed_equal", n_positions=3),
        budget=3, qc=QCGateConfig(enabled=True, max_retries=1),
        verbose=False)
    assert "MEASUREMENT_FAULT" in res.stop_reason
    assert len(res.history) == 0              # no round completed
    # the posterior was never updated with corrupted data
    assert ens.models[0].posterior.theta_map is None
    assert len(ens.models[0].inference.measurements) == 0


def test_gate_disabled_passes_everything_through():
    lab = _lab(seed=4)
    _Corruptor(lab, n_bad=100)
    qc = QCGateConfig(enabled=False)
    m, n_rej, n_re, fault = measure_with_qc(lab, U0, [0.2, 0.4], qc)
    assert m is not None and m.n_z == 2 and n_rej == 0 and not fault


# --------------------------------------------------------------------------- #
# SINGLE-MEASUREMENT (adaptive) OPERATION
# --------------------------------------------------------------------------- #
# In adaptive_sequential mode a round contains ONE acquisition, so the
# per-round rejection FRACTION of a single rejected spectrum is 100 %.  In
# the archived v5 publication run that paused 40 of 40 F-zadaptive campaigns:
# the S7 spatial-policy comparison was measuring the QC gate, not the policy.
def test_single_rejection_is_not_a_fault():
    """One bad spectrum out of one is not evidence that the instrument is
    broken - it is evidence that this position is unusable."""
    qc = QCGateConfig(max_reject_fraction=0.5, min_batch_for_fraction=4)
    fault, why = qc_fault_verdict(1, 1, qc, None)
    assert not fault, why
    # ... and the batch rules still fire where they are meaningful
    assert qc_fault_verdict(10, 6, qc, None)[0]        # 60 % of a profile
    assert qc_fault_verdict(2, 2, qc, None)[0]         # total loss of a batch
    assert not qc_fault_verdict(10, 3, qc, None)[0]    # 30 % is tolerable


def test_persistent_single_measurement_failure_is_a_fault():
    """A genuinely broken instrument must still be caught in
    single-measurement mode - by PERSISTENCE, not by a fraction."""
    qc = QCGateConfig(max_consecutive_rejects=3, rolling_window=8,
                      max_rejects_in_window=4)
    mon = QCMonitor(qc)
    for i in range(2):
        mon.record(True)
        assert not qc_fault_verdict(1, 1, qc, mon)[0], i
    mon.record(True)                                   # third in a row
    fault, why = qc_fault_verdict(1, 1, qc, mon)
    assert fault and "consecutive" in why


def test_a_good_spectrum_resets_the_consecutive_counter():
    qc = QCGateConfig(max_consecutive_rejects=3, rolling_window=99,
                      max_rejects_in_window=98)
    mon = QCMonitor(qc)
    for pattern in (True, True, False, True, True, False, True, True):
        mon.record(pattern)
        assert not mon.tripped()
    assert mon.n_rejected == 6 and mon.n_accepted == 2


def test_rolling_window_catches_intermittent_failure():
    """Alternating pass/fail never trips the consecutive rule, but a
    degrading instrument still has to be caught."""
    qc = QCGateConfig(max_consecutive_rejects=3, rolling_window=8,
                      max_rejects_in_window=4)
    # strictly alternating: 4 of 8 rejected, never two in a row - tolerable
    steady = QCMonitor(qc)
    for i in range(8):
        steady.record(i % 2 == 0)
        assert not steady.tripped(), i
    # degrading: 5 of 8 rejected, longest run 2 - the consecutive rule
    # cannot see it, the window rule must
    bad = QCMonitor(qc)
    for i, rejected in enumerate((True, True, False, True, True,
                                  False, True, False)):
        bad.record(rejected)
        if i < 7:
            assert not bad.tripped(), i
    assert bad.tripped() and "last" in bad.trip_reason


def test_adaptive_campaign_survives_isolated_rejections():
    """END TO END: an adaptive campaign whose spectra fail intermittently
    must keep going.  With the old per-round fraction it paused on the first
    rejection of round 2."""
    from sdl_advanced.spatial_design import SpatialDesignConfig
    lab = _lab(seed=11)

    class _Intermittent(_Corruptor):
        def _call(self, conc, rng=None):
            ppm, y, rl = self._orig(conc, rng)
            self.calls += 1
            if self.calls % 5 == 0:          # 1 acquisition in 5 is ruined
                y = y + 60.0 * np.abs(np.sin(ppm * 3.0))
            return ppm, y, rl

    _Intermittent(lab, n_bad=0)
    ens = ModelEnsemble(build_egda_family(GEOM, T_REF_K,
                                          include=("rev-dilute",),
                                          noise_assumed=NoiseModel()))
    res = run_strategy_f(
        lab, ens, [U0], U0,
        SpatialDesignConfig(mode="adaptive_sequential", n_positions=4,
                            allow_profile_early_stop=True),
        budget=4, qc=QCGateConfig(enabled=True, max_retries=1),
        verbose=False)
    assert "MEASUREMENT_FAULT" not in res.stop_reason, res.stop_reason
    assert len(res.history) == 4
    tot = lab.meter.totals()
    # the gate DID fire - these rounds are not clean by accident
    assert tot["nmr_reacquisitions"] >= 1 or tot["qc_rejected"] >= 1


def test_adaptive_campaign_still_pauses_on_a_broken_instrument():
    """The other half of the contract: persistent failure must still stop
    an adaptive campaign, or the gate has been defanged."""
    from sdl_advanced.spatial_design import SpatialDesignConfig
    lab = _lab(seed=12)
    _Corruptor(lab, n_bad=10_000)                     # everything corrupted
    ens = ModelEnsemble(build_egda_family(GEOM, T_REF_K,
                                          include=("rev-dilute",),
                                          noise_assumed=NoiseModel()))
    res = run_strategy_f(
        lab, ens, [U0], U0,
        SpatialDesignConfig(mode="adaptive_sequential", n_positions=4),
        budget=4, qc=QCGateConfig(enabled=True, max_retries=1),
        verbose=False)
    assert "MEASUREMENT_FAULT" in res.stop_reason
    assert ens.models[0].posterior.theta_map is None  # never assimilated


def test_qc_gate_config_rejects_incoherent_settings():
    for bad in (dict(max_reject_fraction=1.5),
                dict(max_consecutive_rejects=0),
                dict(rolling_window=0),
                dict(max_rejects_in_window=-1)):
        try:
            QCGateConfig(**bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"QCGateConfig({bad}) should have raised")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} measurement-fault tests passed.")
