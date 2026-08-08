"""Tests of the NMR forward model (sdl_advanced.spectral).
Runnable standalone:  python tests/test_spectral.py"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced.spectral import (AcquisitionSettings, NMRSimulator,
                                   SpectralNuisance, flow_response,
                                   water_shift, LAYER1_TO_NMR, NMR_TO_LAYER1)

ACQ = AcquisitionSettings(n_points=4096)
CONC = {"EGDA": 0.30, "EGMA": 0.15, "EG": 0.05, "AcOH": 0.20, "H2O": 52.0}


def _ideal_sim(acq=ACQ):
    return NMRSimulator(acq, SpectralNuisance(enabled=False))


def test_species_map_is_bijective():
    assert set(LAYER1_TO_NMR) == {"EGDA", "EGMA", "EG", "AcOH", "H2O"}
    for k, v in LAYER1_TO_NMR.items():
        assert NMR_TO_LAYER1[v] == k


def test_ideal_mode_is_deterministic():
    sim = _ideal_sim()
    _, y1, _ = sim.simulate(CONC, np.random.default_rng(0))
    _, y2, _ = sim.simulate(CONC, np.random.default_rng(99))
    assert np.array_equal(y1, y2)


def test_area_proportional_to_concentration():
    """Doubling [EGDA] must exactly double the EGDA-only spectral area."""
    sim = _ideal_sim()
    ppm = ACQ.ppm_grid()
    y1 = sim.basis_spectrum("EGDA")
    # integral of the unit-concentration basis = total proton count (10)
    area = np.trapezoid(y1, ppm)
    assert abs(area - 10.0) < 0.15 * 10.0     # Lorentzian tails leave window
    c1 = {"EGDA": 0.2, "H2O": 0.0}
    c2 = {"EGDA": 0.4, "H2O": 0.0}
    _, s1, _ = sim.simulate(c1)
    _, s2, _ = sim.simulate(c2)
    assert np.allclose(s2, 2.0 * s1, rtol=1e-12, atol=1e-14)


def test_fid_engine_matches_analytic():
    """FFT of the simulated FID must reproduce the analytic Lorentzian
    spectrum (ideal conditions, no noise)."""
    acq_a = AcquisitionSettings(n_points=8192)
    acq_f = AcquisitionSettings(n_points=8192, engine="fid")
    ya = _ideal_sim(acq_a).simulate(CONC)[1]
    yf = _ideal_sim(acq_f).simulate(CONC)[1]
    scale = float(np.max(ya))
    err = np.max(np.abs(ya - yf)) / scale
    assert err < 0.05, f"FID/analytic mismatch {err:.3%}"


def test_water_peak_follows_nmr_cell_temperature():
    """The exchange-pool position must track the NMR-CELL temperature, not
    any reactor temperature."""
    conc = {"H2O": 50.0, "EGDA": 0.0, "EGMA": 0.0, "EG": 0.0, "AcOH": 0.0}
    for t_cell in (25.0, 70.0):
        acq = AcquisitionSettings(nmr_temperature_C=t_cell, n_points=4096)
        sim = _ideal_sim(acq)
        line = sim.exchange_line(conc, __import__(
            "sdl_advanced.spectral", fromlist=["RealizedNuisance"]
        ).RealizedNuisance())
        assert abs(line.ppm - water_shift(t_cell)) < 1e-9
    assert water_shift(70.0) < water_shift(25.0)   # upfield when hotter


def test_flow_response_unity_when_disabled():
    acq_off = AcquisitionSettings(flow_response_enabled=False)
    assert flow_response(acq_off, t1_s=3.0) == 1.0
    acq_on = AcquisitionSettings(flow_response_enabled=True,
                                 repetition_time_s=2.0,
                                 analytical_flow_mL_min=2.0,
                                 premag_volume_mL=0.1)
    e = flow_response(acq_on, t1_s=4.0)
    assert 0.0 < e < 1.0
    # longer T1 -> less complete relaxation -> smaller response
    assert flow_response(acq_on, t1_s=8.0) < e


def test_realistic_mode_adds_configured_imperfections():
    rng = np.random.default_rng(3)
    sim = NMRSimulator(ACQ, SpectralNuisance())
    _, y_r, rl = sim.simulate(CONC, rng)
    y_i = _ideal_sim().simulate(CONC)[1]
    assert not np.allclose(y_r, y_i)
    assert rl.gain != 1.0 and rl.linewidth_factor != 1.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} spectral tests passed.")
