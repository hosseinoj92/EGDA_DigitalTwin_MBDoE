"""Tests of the MEASUREMENT_FAULT control state: QC gating BEFORE
assimilation, reacquisition, and safe pause.  Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import Layer1Bridge, OperatingConditions, NoiseModel
from sdl_advanced.controller import (QCGateConfig, measure_with_qc,
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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} measurement-fault tests passed.")
