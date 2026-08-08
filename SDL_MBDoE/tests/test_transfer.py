"""Tests of the capillary transfer model (sdl_advanced.transfer) and its
integration in the instrument.  Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import Layer1Bridge, OperatingConditions, NoiseModel
from sdl_advanced.instrument import (AdvancedVirtualLaboratory,
                                     InstrumentConfig)
from sdl_advanced.resources import ResourceCosts
from sdl_advanced.spectral import AcquisitionSettings, SpectralNuisance
from sdl_advanced.transfer import TransferConfig, TransferLine

T_REF_K = 333.15
GEOM = {"length_m": 0.5, "diameter_m": 0.018}
TRUTH = {"k1_ref": 3.3e-3, "Ea1_J": 58_500.0,
         "k2_ref": 8.5e-4, "Ea2_J": 52_000.0,
         "K1_ref": 0.80, "K2_ref": 0.12}
U0 = OperatingConditions(T_C=80.0, Q1_mL_min=1.0, Q2_mL_min=1.0,
                         C_EGDA_M=1.0, C_cat_M=1.0)
SPECIES = ("EGDA", "EGMA", "EG", "AcOH")


def _lab(transfer: TransferConfig, seed=0) -> AdvancedVirtualLaboratory:
    bridge = Layer1Bridge(GEOM, T_REF_K)
    return AdvancedVirtualLaboratory(
        TRUTH, bridge, InstrumentConfig(observation_mode="direct"),
        AcquisitionSettings(), SpectralNuisance(enabled=False),
        transfer, ResourceCosts(), seed=seed,
        noise_direct=NoiseModel(sigma_abs_M=0.0, sigma_rel=0.0))


def test_disabled_transfer_reproduces_legacy_observation():
    """Acceptance criterion 8: all transport effects off -> the advanced
    direct observation equals the existing concentration observation."""
    lab = _lab(TransferConfig(enabled=False))
    z = np.array([0.1, 0.3, 0.5])
    m = lab.run_profile(U0, z)
    bridge = Layer1Bridge(GEOM, T_REF_K)
    legacy = bridge.concentrations_at(TRUTH, U0, z, SPECIES)
    assert np.max(np.abs(m.y - legacy)) < 1e-12


def test_delta_rtd_reproduces_legacy_transfer_time():
    """Acceptance criterion 9: plug-flow (delta) RTD with tau = V/Q must
    equal the legacy extra_tau_s batch-advance limit."""
    tau_s = 45.0
    q = 0.6                                   # mL/min -> 0.01 mL/s
    v = tau_s * q / 60.0                      # mL, so tau = V/Q = 45 s
    lab = _lab(TransferConfig(enabled=True, Q_sample_mL_min=q, V_fixed_mL=v,
                              rtd="delta", carryover=False))
    z = np.array([0.2, 0.5])
    m = lab.run_profile(U0, z)
    bridge = Layer1Bridge(GEOM, T_REF_K)
    legacy = bridge.concentrations_at(TRUTH, U0, z, SPECIES,
                                      extra_tau_s=tau_s)
    assert np.max(np.abs(m.y - legacy)) < 1e-8


def test_gamma_rtd_converges_to_delta_for_many_tanks():
    tau_s, q = 45.0, 0.6
    v = tau_s * q / 60.0
    m_delta = _lab(TransferConfig(enabled=True, Q_sample_mL_min=q,
                                  V_fixed_mL=v, rtd="delta")
                   ).run_profile(U0, [0.4])
    m_gam = _lab(TransferConfig(enabled=True, Q_sample_mL_min=q,
                                V_fixed_mL=v, rtd="gamma", n_tanks=400.0,
                                n_quad=9)).run_profile(U0, [0.4])
    assert np.max(np.abs(m_delta.y - m_gam.y)) < 1e-4
    # moderate dispersion must differ measurably from plug flow
    m_disp = _lab(TransferConfig(enabled=True, Q_sample_mL_min=q,
                                 V_fixed_mL=v, rtd="gamma", n_tanks=2.0,
                                 n_quad=9)).run_profile(U0, [0.4])
    assert np.max(np.abs(m_delta.y - m_disp.y)) > 1e-6


def test_position_dependent_volume():
    cfg = TransferConfig(enabled=True, geometry="linear", V_fixed_mL=0.1,
                         v_per_m_mL=0.4, Q_sample_mL_min=0.6)
    L = GEOM["length_m"]
    assert cfg.V_transfer_mL(L, L) == 0.1                 # outlet: fixed only
    assert cfg.V_transfer_mL(0.0, L) == 0.1 + 0.4 * L     # inlet: longest path
    assert cfg.mean_tau_s(0.0, L) > cfg.mean_tau_s(L, L)


def test_carryover_mixes_previous_position():
    """After moving the capillary, an unflushed line must still contain the
    previous sample; heavy flushing must remove it."""
    tau_s, q = 30.0, 0.6
    v = tau_s * q / 60.0
    base = dict(enabled=True, Q_sample_mL_min=q, V_fixed_mL=v, rtd="delta",
                carryover=True)
    lab_no_flush = _lab(TransferConfig(**base, flush_volumes=0.0))
    lab_flushed = _lab(TransferConfig(**base, flush_volumes=8.0))
    z = np.array([0.05, 0.5])                 # inlet-ish then outlet
    m0 = lab_no_flush.run_profile(U0, z)
    m1 = lab_flushed.run_profile(U0, z)
    n_z = len(z)
    # flushed outlet sample ~ pure; unflushed outlet contaminated by z=0.05
    egda_out_noflush = m0.y[0 * n_z + 1]
    egda_out_flushed = m1.y[0 * n_z + 1]
    assert egda_out_noflush > egda_out_flushed + 1e-3     # EGDA higher at inlet
    # with flush_volumes=0, carryover fraction = 1: sample IS the old content
    lab_ref = _lab(TransferConfig(**base, flush_volumes=8.0))
    m_ref = lab_ref.run_profile(U0, np.array([0.05]))
    assert abs(egda_out_noflush - m_ref.y[0]) < 1e-8


def test_transfer_line_state_resets_between_conditions():
    line = TransferLine(TransferConfig(enabled=True, carryover=True,
                                       flush_volumes=0.0), 0.5)
    ident = lambda c, tau: dict(c)
    a = line.sample({"EGDA": 1.0}, 0.1, ident)
    line.reset()
    b = line.sample({"EGDA": 0.5}, 0.4, ident)
    assert b["EGDA"] == 0.5                    # no carryover after reset


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} transfer tests passed.")
