"""Three corrections found by external review, each with the property that
made it a defect rather than a preference.

1. PLUG-FLOW VALIDITY.  The geometry optimizer refuses candidate reactors
   above t_rad/tau = 10, but the principal 20 cm open tube runs at 13-212.
   Holding designed reactors to a criterion the baseline fails is the
   inconsistency; the fix is to apply the same test to whichever reactor is
   actually in use and report it.

2. TRANSFER-LINE SPECIATION.  The post-withdrawal step evaluated rate
   constants at the LINE temperature but carried [H+] from the REACTOR
   temperature.  Ka2 is strongly temperature dependent - the framework
   ships ka2_model="tdep" precisely because of that - so the catalyst and
   the kinetics were being evaluated at different temperatures.

3. ACQUISITION TIME.  `acquisition_time_s` was documented as setting the
   dwell but never read: the FID engine used n_points at dwell 1/SW, so a
   configuration declaring 4.096 s simulated 2.129 s.  n_points was
   simultaneously the acquired-sample count, the FFT length and the display
   grid; the three are now separate.

Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import Layer1Bridge, OperatingConditions, literature_guess
from sdl_advanced import benchmark as bm
from sdl_advanced.resources import ResourceCosts
from sdl_advanced.spectral import (AcquisitionSettings, NMRSimulator,
                                   SpectralNuisance)

BENCH = AcquisitionSettings(n_points=2048)


def _quiet_nuisance(sigma=0.10, ar1=0.0):
    return SpectralNuisance(
        enabled=True, noise_sigma=sigma, noise_ar1=ar1, shift_drift_ppm=0,
        shift_jitter_ppm=0, linewidth_rel_sigma=0, baseline_offset=0,
        baseline_curve=0, phase_error_deg=0, gain_drift_rel_sigma=0,
        gaussian_fraction=0.0, j_mismatch_hz=0, static_shift_ppm=0,
        baseline_cubic=0)


def _noise_std(acq, sigma=0.10, n=40):
    sim = NMRSimulator(acq, _quiet_nuisance(sigma))
    empty = {"EGDA": 0.0, "EGMA": 0.0, "EG": 0.0, "AcOH": 0.0, "H2O": 0.0}
    return float(np.std(np.array(
        [sim.simulate(empty, np.random.default_rng(s))[1] for s in range(n)])))


# ---- 1. plug-flow validity ------------------------------------------------ #
def test_principal_reactor_is_checked_against_its_own_criterion():
    """The DEFAULT reactor must satisfy the criterion the framework
    enforces on designed geometries - it is now a packed bed for exactly
    that reason (FEATURES['packed_bed_reactor'])."""
    rows = bm.reactor_validity_rows()
    assert rows and all(r["threshold"] ==
                        bm.validity_criteria().max_radial_ratio
                        for r in rows)
    assert all(r["plug_flow_valid"] for r in rows), \
        "the shipped default reactor must pass its own criterion"
    assert all(r["packed"] for r in rows)
    # and the OPEN tube it replaced fails at every design flow, which is why
    assert all(not r["plug_flow_valid"] for r in bm.reactor_validity_rows(
        {"length_m": 0.20, "diameter_m": 0.007}))
    got = {r["Q_total_mL_min"]: round(r["t_rad_over_tau"], 1)
           for r in bm.reactor_validity_rows(
               {"length_m": 0.20, "diameter_m": 0.007},
               flows=[0.5, 2.0, 8.0])}
    assert got[0.5] == 13.3 and got[2.0] == 53.1 and got[8.0] == 212.2


def test_validity_ratio_scales_as_Q_over_L_eps():
    """t_rad/tau = Q/(pi D L eps) for an OPEN tube: linear in flow, inverse
    in length, independent of bore."""
    g = {"length_m": 0.2, "diameter_m": 0.007}
    r1 = bm._radial_ratio(g, 1.0)
    assert abs(bm._radial_ratio(g, 2.0) - 2.0 * r1) < 1e-9
    assert abs(bm._radial_ratio({**g, "length_m": 0.4}, 1.0) - r1 / 2) < 1e-9
    assert abs(bm._radial_ratio({**g, "diameter_m": 0.02}, 1.0) - r1) < 1e-12
    # A packed bed is CHECKED, not assumed: its ratio is small because the
    # bed disperses radially, but it is finite and it is computed.
    packed = {**g, "packing_enabled": True, "bed_void_fraction": 0.4}
    assert 0.0 < bm._radial_ratio(packed, 1.0) < 1.0
    assert all(r["plug_flow_valid"]
               for r in bm.reactor_validity_rows(packed))


def test_validity_policy_warns_by_default_and_can_refuse():
    before = bm.resolved_config()
    open_tube = {"length_m": 0.20, "diameter_m": 0.007}
    try:
        bm.apply_config({"VALIDITY": {"policy": "warn"}})
        bm.invalidate_caches()
        assert bm.assert_reactor_validity(open_tube)   # warns, returns rows
        bm.apply_config({"VALIDITY": {"policy": "error"}})
        bm.invalidate_caches()
        try:
            bm.assert_reactor_validity(open_tube)
        except ValueError as exc:
            assert "PACK the tube" in str(exc)
        else:
            raise AssertionError("policy='error' must refuse")
        # "ignore" is reached by DECLARING the non-ideal study through the
        # feature switch, not by quietly setting a policy string
        bm.apply_config({"FEATURES": {"reactor_validity_enforcement": False}})
        bm.invalidate_caches()
        assert bm.VALIDITY["policy"] == "ignore"
        bm.assert_reactor_validity(open_tube)          # silent
        # ... and claiming enforcement while ignoring the verdict is refused
        try:
            bm.apply_config({"FEATURES": {
                "reactor_validity_enforcement": True}})
        except ValueError as exc:
            assert "nothing is enforced" in str(exc)
        else:
            raise AssertionError("enforcement + policy 'ignore' must raise")
        bm.apply_config({"VALIDITY": {"policy": "error"},
                         "FEATURES": {"reactor_validity_enforcement": True}})
        bm.invalidate_caches()
        # packing the tube satisfies the criterion even under 'error'
        bm.apply_config({"VALIDITY": {"policy": "error"}})
        bm.invalidate_caches()
        bm.assert_reactor_validity({**open_tube, "packing_enabled": True,
                                    "bed_void_fraction": 0.4})
    finally:
        bm.apply_config(before)
        bm.invalidate_caches()


# ---- 2. transfer-line speciation ------------------------------------------ #
def _bridge():
    return Layer1Bridge(bm.GEOMETRY, bm.T_REF_C + 273.15,
                        activity_model="pitzer")


def test_h_plus_is_resolved_at_the_line_temperature():
    br = _bridge()
    g = literature_guess(bm.T_REF_C + 273.15)
    u = OperatingConditions(160.0, 0.25, 0.25, 1.0, 1.0)
    kin = br.kinetics_from_theta(g)
    inlet = br._inlet(u, kin)
    hot = br._h_plus_at(inlet, kin, 433.15)
    cold = br._h_plus_at(inlet, kin, 298.15)
    # bisulfate dissociates further as it cools -> MORE free protons
    assert cold > hot * 1.05, (hot, cold)
    # the reactor value is the one mix_streams already produced
    assert abs(hot - inlet.c_h_plus) < 1e-9
    # stoichiometric mode has no equilibrium and must be temperature-free
    br_s = Layer1Bridge(bm.GEOMETRY, bm.T_REF_C + 273.15,
                        h_plus_model="stoichiometric")
    kin_s = br_s.kinetics_from_theta(g)
    in_s = br_s._inlet(u, kin_s)
    assert br_s._h_plus_at(in_s, kin_s, 298.15) == \
        br_s._h_plus_at(in_s, kin_s, 433.15)


def test_cooled_line_uses_cooled_speciation_end_to_end():
    br = _bridge()
    g = literature_guess(bm.T_REF_C + 273.15)
    u = OperatingConditions(160.0, 0.25, 0.25, 1.0, 1.0)
    z = np.array([0.2])
    cool = br.concentrations_at(g, u, z, bm.SPECIES, extra_tau_s=18.0,
                                T_extra_K=298.15)
    hot = br.concentrations_at(g, u, z, bm.SPECIES, extra_tau_s=18.0)
    assert not np.allclose(cool, hot)
    # with no line delay the line temperature cannot matter
    assert np.allclose(
        br.concentrations_at(g, u, z, bm.SPECIES, extra_tau_s=0.0,
                             T_extra_K=298.15),
        br.concentrations_at(g, u, z, bm.SPECIES, extra_tau_s=0.0))


def test_truth_and_inference_use_the_same_speciation_rule():
    """Both sides must call the SAME helper - a correction applied to only
    one of them would create an artificial truth/model mismatch that looks
    like transport bias."""
    import inspect
    src = inspect.getsource(
        __import__("sdl_advanced.instrument", fromlist=["x"])
        .AdvancedVirtualLaboratory._propagator)
    assert "_h_plus_at" in src
    assert "inlet.c_h_plus" not in src


# ---- 3. acquisition contract ---------------------------------------------- #
def test_resolved_acquisition_matches_the_physical_contract():
    a = BENCH
    assert abs(a.spectral_width_hz - 962.016) < 1e-3
    assert abs(a.dwell_time_s - 1.0394837e-3) < 1e-9
    assert a.resolved_n_acquired_complex == 3940
    assert abs(a.actual_acquisition_time_s - 4.0956) < 1e-3
    assert a.resolved_fft_points >= a.resolved_n_acquired_complex
    assert a.resolved_fft_points == 4096
    # the three counts are INDEPENDENT
    assert a.n_points == 2048 != a.resolved_n_acquired_complex
    rep = a.acquisition_report()
    assert rep["requested_acquisition_time_s"] == 4.096
    assert abs(rep["actual_acquisition_time_s"] - 4.0956) < 1e-3
    assert rep["final_spectrum_points"] == 2048


def test_acquisition_settings_reject_nonsense():
    for kw in ({"spectrometer_MHz": 0.0}, {"ppm_max": 0.0},
               {"n_points": 1}, {"acquisition_time_s": 0.0},
               {"n_scans": 0}, {"repetition_time_s": -1.0},
               {"engine": "wavelet"}, {"n_acquired_complex": 0},
               {"fft_points": 10}):
        try:
            AcquisitionSettings(**{"n_points": 2048, **kw})
        except ValueError:
            pass
        else:
            raise AssertionError(f"{kw} should have been rejected")


def test_explicit_point_count_is_validated_against_requested_time():
    # consistent: 3940 points at this dwell IS 4.096 s
    AcquisitionSettings(n_points=2048, n_acquired_complex=3940)
    # inconsistent by far more than a dwell period -> must raise
    try:
        AcquisitionSettings(n_points=2048, n_acquired_complex=2048)
    except ValueError as exc:
        assert "acquisition_time_s" in str(exc)
    else:
        raise AssertionError("a 2.13 s point count declared as 4.096 s must "
                             "not be accepted silently")


def test_fid_engine_actually_uses_acquisition_time():
    """The defect: changing acquisition_time_s changed nothing."""
    nu = SpectralNuisance(enabled=False)
    comp = {"EGDA": 0.30, "EGMA": 0.12, "EG": 0.05, "AcOH": 0.20,
            "H2O": 52.0}
    short = AcquisitionSettings(n_points=2048, engine="fid",
                                acquisition_time_s=0.5)
    long_ = AcquisitionSettings(n_points=2048, engine="fid",
                                acquisition_time_s=4.096)
    ys = NMRSimulator(short, nu).simulate(comp, np.random.default_rng(0))[1]
    yl = NMRSimulator(long_, nu).simulate(comp, np.random.default_rng(0))[1]
    assert not np.allclose(ys, yl)
    # a truncated FID broadens the lines: the peak of the SAME sample is
    # lower and the wings heavier
    assert ys.max() < yl.max()


def test_zero_filling_adds_no_information_and_no_noise():
    """Enlarging fft_points interpolates the spectrum; it must not improve
    SNR, which would be free precision out of nothing."""
    base = AcquisitionSettings(n_points=2048, engine="fid")
    for n_fft in (4096, 8192, 16384):
        acq = AcquisitionSettings(n_points=2048, engine="fid",
                                  fft_points=n_fft)
        assert acq.resolved_n_acquired_complex == \
            base.resolved_n_acquired_complex
        assert acq.actual_acquisition_time_s == base.actual_acquisition_time_s
        assert abs(_noise_std(acq) / _noise_std(base) - 1.0) < 0.05, n_fft


def test_receiver_noise_honours_the_requested_sigma():
    """The returned spectrum must carry the declared receiver noise, on the
    same convention as the analytic engine - otherwise the FID-truth
    validation suite compares spectra at different effective SNR."""
    for sigma in (0.05, 0.10, 0.20):
        got = _noise_std(AcquisitionSettings(n_points=2048, engine="fid"),
                         sigma=sigma)
        assert abs(got / sigma - 1.0) < 0.05, (sigma, got)
    # and independent of acquisition length and display grid
    for acq in (AcquisitionSettings(n_points=2048, engine="fid",
                                    acquisition_time_s=1.024),
                AcquisitionSettings(n_points=4096, engine="fid")):
        assert abs(_noise_std(acq) / 0.10 - 1.0) < 0.05
    # the analytic engine defines the convention
    an = _noise_std(AcquisitionSettings(n_points=2048, engine="analytic"))
    assert abs(an / 0.10 - 1.0) < 0.05


def test_analytic_engine_is_untouched_by_acquisition_settings():
    """Acquisition time is a physical FID setting; the analytic engine
    builds the frequency-domain lineshape directly and must not pretend to
    simulate a finite acquisition."""
    nu = SpectralNuisance(enabled=False)
    comp = {"EGDA": 0.30, "EGMA": 0.12, "EG": 0.05, "AcOH": 0.20,
            "H2O": 52.0}
    ref = NMRSimulator(AcquisitionSettings(n_points=2048, engine="analytic"),
                       nu).simulate(comp, np.random.default_rng(0))[1]
    for kw in ({"acquisition_time_s": 0.5}, {"fft_points": 16384},
               {"n_acquired_complex": 3940}):
        y = NMRSimulator(
            AcquisitionSettings(n_points=2048, engine="analytic", **kw),
            nu).simulate(comp, np.random.default_rng(0))[1]
        assert np.array_equal(y, ref), kw
    assert BENCH.acquisition_report()[
        "acquisition_time_affects_spectrum"] is False


# ---- 3d. resource accounting ---------------------------------------------- #
def test_nmr_time_is_decomposed_and_responds_to_acquisition():
    c = ResourceCosts()
    # the shipped default reproduces the historical lumped 60 s
    assert abs(c.nmr_spectrum_time_s - 60.0) < 0.01
    synced = c.with_acquisition(BENCH)
    assert abs(synced.nmr_acquisition_time_s
               - BENCH.actual_acquisition_time_s) < 1e-9
    assert synced.nmr_n_scans == BENCH.n_scans
    # scans and acquisition length now MOVE the clock, which was the defect
    four = c.with_acquisition(AcquisitionSettings(n_points=2048, n_scans=4))
    assert four.nmr_spectrum_time_s > synced.nmr_spectrum_time_s
    assert abs(four.nmr_spectrum_time_s
               - (40.9 + 4 * (15.0 + BENCH.actual_acquisition_time_s))) < 1e-6
    # legacy compatibility is explicit and overrides the decomposition
    legacy = ResourceCosts(legacy_fixed_nmr_time_s=60.0,
                           nmr_n_scans=99)
    assert legacy.nmr_spectrum_time_s == 60.0
    assert "LEGACY" in legacy.nmr_time_report()["model"]


def test_laboratory_clock_is_synced_to_the_spectrometer():
    """A campaign must not meter a different acquisition from the one it
    simulates."""
    lab = bm.make_lab(bm.SCENARIOS["S2_nmr"], seed=1)
    assert abs(lab.meter.costs.nmr_acquisition_time_s
               - bm.ACQ.actual_acquisition_time_s) < 1e-9
    assert lab.meter.costs.nmr_n_scans == bm.ACQ.n_scans


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} acquisition/validity/speciation tests passed.")
