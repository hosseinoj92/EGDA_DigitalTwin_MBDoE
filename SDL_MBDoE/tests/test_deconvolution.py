"""Tests of spectral quantification (sdl_advanced.spectral_fit).
Runnable standalone:  python tests/test_deconvolution.py"""

from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced.spectral import (AcquisitionSettings, NMRSimulator,
                                   SpectralNuisance)
from sdl_advanced.spectral_fit import SpectralFitter, bootstrap_coverage

ACQ = AcquisitionSettings(n_points=4096)
CONC = {"EGDA": 0.30, "EGMA": 0.15, "EG": 0.05, "AcOH": 0.20, "H2O": 52.0}


def test_zero_noise_recovery():
    """Acceptance criterion 6: an ideal spectrum must be deconvolved back to
    the supplied concentrations to numerical tolerance."""
    sim = NMRSimulator(ACQ, SpectralNuisance(enabled=False))
    ppm, y, _ = sim.simulate(CONC)
    res = SpectralFitter(ACQ).fit(ppm, y)
    for sp, c_hat in zip(res.species, res.conc_M):
        assert abs(c_hat - CONC[sp]) < 5e-4, (sp, c_hat, CONC[sp])
    assert res.residual_rms < 1e-6 * np.max(y)
    assert res.ok


def test_overlap_produces_correlated_errors():
    """EGDA (4.335) and EGMA ester triplet (4.245) are ~7 Hz apart at
    80 MHz: the fitted covariance must show a nonzero EGDA/EGMA error
    correlation WITHOUT any hand-set rho_overlap."""
    sim = NMRSimulator(ACQ, SpectralNuisance(enabled=False))
    ppm, y, _ = sim.simulate(CONC)
    res = SpectralFitter(ACQ).fit(ppm, y)
    ia = res.species.index("EGDA")
    ib = res.species.index("EGMA")
    assert abs(res.corr[ia, ib]) > 0.05
    # overlap makes the errors ANTI-correlated (area traded between peaks)
    assert res.corr[ia, ib] < 0.0


def test_noisy_recovery_and_coverage():
    """Acceptance criterion 7 (reduced-size): Monte Carlo intervals from the
    fitted covariance must achieve roughly their nominal 95% coverage."""
    nu = SpectralNuisance(noise_sigma=0.10, shift_drift_ppm=0.002,
                          shift_jitter_ppm=0.0, linewidth_rel_sigma=0.03,
                          baseline_offset=0.005, baseline_curve=0.01,
                          phase_error_deg=0.0, gain_drift_rel_sigma=0.0)
    sim = NMRSimulator(ACQ, nu)
    fitter = SpectralFitter(ACQ)
    t0 = time.time()
    out = bootstrap_coverage(fitter, sim, CONC, n_boot=30, seed=1)
    dt = time.time() - t0
    for sp, cov_p, rmse in zip(fitter.species, out["coverage"], out["rmse"]):
        assert cov_p >= 0.7, (sp, cov_p)      # loose: only 30 replicates
        assert rmse < 0.05, (sp, rmse)        # mol/L
    print(f"    (coverage {np.round(out['coverage'], 2)}, "
          f"rmse {np.round(out['rmse'], 4)} M, {dt:.1f} s / 30 fits)")


def test_qc_flags_on_garbage_spectrum():
    """A spectrum the lineshape model cannot explain must raise FAIL QC."""
    rng = np.random.default_rng(0)
    ppm = ACQ.ppm_grid()
    y = np.abs(np.sin(ppm * 3.0)) * 50.0 + rng.normal(0, 1.0, ppm.shape)
    res = SpectralFitter(ACQ).fit(ppm, y)
    assert not res.ok


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} deconvolution tests passed.")
