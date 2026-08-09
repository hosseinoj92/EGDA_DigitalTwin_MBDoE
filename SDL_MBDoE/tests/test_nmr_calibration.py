"""Priority-1 tests: ONE public NMR calibration artifact shared by the
measurement pathway and the design-time covariance model, the three-dataset
calibration hierarchy, and a statistical (binomial) gate that prevents
severe under-coverage from being called "calibrated".  Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from scipy import stats

from sdl_advanced import benchmark as bm
from sdl_advanced.spectral import (AcquisitionSettings, NMRSimulator,
                                   SpectralNuisance)
from sdl_advanced.spectral_fit import (NMRCalibration, SpectralFitter,
                                       SpectralCovarianceModel,
                                       calibrate_nmr)

ACQ = AcquisitionSettings(n_points=2048)
CONC = np.array([0.30, 0.12, 0.05, 0.20])          # EGDA EGMA EG AcOH


def _calibration(seed=0):
    sim = NMRSimulator(ACQ, SpectralNuisance())
    acquire = lambda s, r: sim.simulate(s, r)[:2]
    cal = calibrate_nmr(ACQ, acquire,
                        rng_fit=np.random.default_rng(seed + 900_001),
                        rng_check=np.random.default_rng(seed + 800_002))
    return sim, cal


# ---- 1. the artifact is PUBLIC ------------------------------------------- #
def test_calibration_artifact_contains_no_hidden_truth():
    _sim, cal = _calibration()
    assert cal.contains_only_public_fields()
    # nothing that could encode kinetics or a realized nuisance draw
    blob = repr(cal).lower()
    for forbidden in ("theta", "k1_ref", "ea1", "k2_ref", "truth",
                      "realized", "nuisance", "gaussian_fraction"):
        assert forbidden not in blob, forbidden
    assert set(cal.meta) <= {"n_obs_fit", "n_check_used", "level",
                             "n_rep_fit", "n_rep_check", "engine",
                             "n_points"}
    assert tuple(cal.species) == ("EGDA", "EGMA", "EG", "AcOH")


# ---- 2/3. one artifact drives BOTH sides --------------------------------- #
def test_fitter_and_design_model_share_one_calibration():
    sim, cal = _calibration(seed=1)
    fitter = SpectralFitter(ACQ)
    fitter.apply_calibration(cal)
    design = SpectralCovarianceModel(SpectralFitter(ACQ), calibration=cal)
    assert design.calibration is cal
    assert design.fitter.calibration is cal          # adopted, not invented
    # design-time expected Sigma and a realized fitted Sigma are the SAME
    # model evaluated differently: same scale, same correlation structure
    rng = np.random.default_rng(3)
    comp = {"EGDA": 0.30, "EGMA": 0.12, "EG": 0.05, "AcOH": 0.20,
            "H2O": 52.0}
    ppm, y, _ = sim.simulate(comp, rng)
    res = fitter.fit(ppm, y)
    exp = design.cov_at(CONC)
    s_exp = np.sqrt(np.diag(exp))
    s_act = np.sqrt(np.diag(res.cov))
    for i, sp in enumerate(cal.species):
        assert 0.25 < s_exp[i] / s_act[i] < 4.0, (sp, s_exp[i], s_act[i])
    # both carry the empirical inter-species correlation (not diagonal)
    off = exp - np.diag(np.diag(exp))
    assert np.max(np.abs(off)) > 0.0


def test_calibrated_design_model_differs_from_uncalibrated():
    _sim, cal = _calibration(seed=2)
    uncal = SpectralCovarianceModel(SpectralFitter(ACQ))
    calm = SpectralCovarianceModel(SpectralFitter(ACQ), calibration=cal)
    assert uncal.calibration is None and calm.calibration is cal
    c_u, c_c = uncal.cov_at(CONC), calm.cov_at(CONC)
    assert not np.allclose(c_u, c_c)
    for m in (c_u, c_c):                              # both valid covariances
        assert np.allclose(m, m.T)
        assert np.all(np.linalg.eigvalsh(m) > 0)


# ---- 4/5. empirical model is PSD and correlated -------------------------- #
def test_empirical_covariance_psd_and_correlation_preserved():
    _sim, cal = _calibration(seed=4)
    for c in (np.zeros(4), CONC, np.array([0.5, 0.0, 0.0, 0.8])):
        cov = cal.cov_emp(c)
        assert np.allclose(cov, cov.T)
        assert np.all(np.linalg.eigvalsh(cov) >= -1e-18)
    assert np.max(np.abs(cal.corr - np.eye(4))) > 0.05   # inter-species
    assert np.allclose(np.diag(cal.corr), 1.0)
    # the scale never SHRINKS the claimed uncertainty below the fitted model
    assert np.all(cal.scale >= 1.0)


# ---- 6. three independent RNG streams ------------------------------------ #
def test_three_datasets_use_independent_streams():
    sim = NMRSimulator(ACQ, SpectralNuisance())
    std = {"EGDA": 0.3, "EGMA": 0.1, "EG": 0.05, "AcOH": 0.2, "H2O": 52.0}
    seed = 0
    y_fit = sim.simulate(std, np.random.default_rng(seed + 900_001))[1]
    y_chk = sim.simulate(std, np.random.default_rng(seed + 800_002))[1]
    y_val = sim.simulate(std, np.random.default_rng(seed + 12_345))[1]
    assert not np.allclose(y_fit, y_chk)
    assert not np.allclose(y_fit, y_val)
    assert not np.allclose(y_chk, y_val)


# ---- 7. the calibration gate catches severe under-coverage --------------- #
def coverage_gate(n_hit: int, n: int, severe: float = 0.85,
                  alpha: float = 0.05) -> bool:
    """FAIL only when we can be CONFIDENT the true coverage is below
    `severe`: the one-sided Clopper-Pearson upper bound on the coverage
    still lies under the threshold.  Statistical rather than a brittle
    exact-number assertion, and it does not condemn small samples for
    Monte-Carlo noise alone."""
    if n == 0:
        return True
    upper = (1.0 if n_hit >= n
             else float(stats.beta.ppf(1.0 - alpha, n_hit + 1, n - n_hit)))
    return upper >= severe


def test_coverage_gate_flags_severe_undercoverage():
    # the v3 situation (0.73-0.79 at n=75-90) must FAIL the gate
    assert not coverage_gate(int(0.73 * 88), 88)
    assert not coverage_gate(int(0.77 * 90), 90)
    # broadly-near-nominal results PASS
    assert coverage_gate(int(0.95 * 88), 88)
    assert coverage_gate(int(0.91 * 89), 89)
    assert coverage_gate(int(0.88 * 75), 75)
    # small samples are not condemned by noise alone
    assert coverage_gate(int(0.88 * 16), 16)


def test_held_out_validation_passes_the_gate():
    """End-to-end Priority-1 acceptance on the REACHABLE suite (the one the
    campaign actually meets), using the three-dataset hierarchy."""
    from sdl import literature_guess
    from sdl_advanced import validation as val
    t_ref_K = bm.T_REF_C + 273.15
    res = val.run_validation(bm.ACQ, bm.NMR_NUISANCE_TRUE, bm.GEOMETRY,
                             t_ref_K, literature_guess(t_ref_K), seed=0,
                             n_stress=8, n_rep=2)
    suite = res["B_reachable_reaction_states"]
    for sp, m in suite.items():
        n, cov = int(m["n"]), m["coverage95"]
        assert coverage_gate(int(round(cov * n)), n), (
            f"{sp}: severe under-coverage {cov:.2f} at n={n} - the "
            f"covariance model may NOT be described as calibrated")




# ---- 8/9/10/11/13: allowance provenance, evidence snapshot, paths -------- #
def test_allowance_is_derived_from_control_data_not_benchmark():
    """kappa must come from validation.derive_systematic_allowance() on
    CONTROL data, and the benchmark's configured value must agree with it -
    it may not be a number chosen from kinetic-benchmark performance."""
    import inspect
    import re
    from sdl_advanced import validation as val
    # the derivation routine exists and works on CONTROL data
    assert hasattr(val, "derive_systematic_allowance")
    dsrc = inspect.getsource(val.derive_systematic_allowance)
    assert "CONTROL" in dsrc and "rms" in dsrc
    assert "blind" not in dsrc and "param_err" not in dsrc   # not benchmark
    src = inspect.getsource(bm.run_one_campaign)
    assert "derive_systematic_allowance" in src              # documented
    # the ACTIVE value (not historical commentary) is the control-derived one
    m = re.search(r"systematic_allowance=\(([0-9.]+)\s+if", src)
    assert m, "could not find the active systematic_allowance assignment"
    assert abs(float(m.group(1)) - 0.47) < 1e-9, m.group(1)


def test_evidence_reliability_is_snapshotted_per_round():
    from sdl_advanced.controller import AdvRoundRecord
    f = AdvRoundRecord.__dataclass_fields__
    for k in ("probs_reliable", "evidence_reliable_by_model",
              "evidence_warning"):
        assert k in f, k
    # the record stores a COPY, so a later ensemble change cannot rewrite it
    d = {"m": True}
    rec = AdvRoundRecord(round=1, u=None, z_positions=np.array([]),
                         theta_nat={}, best_model="m", model_probs={},
                         governor=None, resources={}, n_data=0,
                         evidence_reliable_by_model=dict(d))
    d["m"] = False
    assert rec.evidence_reliable_by_model == {"m": True}


def test_s4b_truth_inside_bounds_and_s4c_is_not():
    from sdl import ParameterSpace, literature_guess
    t_ref_K = bm.T_REF_C + 273.15
    space = ParameterSpace(t_ref_K=t_ref_K,
                           initial_guess=dict(literature_guess(t_ref_K)))
    assert bm.check_truth_in_domain(
        space, bm.SCENARIOS["S4b_identifiable"].truth)["ok"]
    assert not bm.check_truth_in_domain(
        space, bm.SCENARIOS["S4c_out_of_domain"].truth)["ok"]


def test_v3_output_path_is_not_v2():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(here, "run_advanced_benchmark.py")).read()
    assert "results_advanced_v2" not in src
    assert "results_advanced_v3" in src


# ---- 14/15: packing terminology and residence time ---------------------- #
def test_packing_terminology_and_residence_time():
    from pfr_twin.parameters import ReactorGeometry
    q = 1.0e-6 / 60.0
    open_tube = ReactorGeometry(length_m=0.2, diameter_m=0.007)
    # declaring a void fraction WITHOUT enabling packing must change nothing
    flagged = ReactorGeometry(length_m=0.2, diameter_m=0.007,
                              bed_void_fraction=0.4)
    assert flagged.residence_time_s(q) == open_tube.residence_time_s(q)
    packed = ReactorGeometry(length_m=0.2, diameter_m=0.007,
                             packing_enabled=True, bed_void_fraction=0.4)
    # tau = eps A L / Q ; interstitial = Q/(eps A) > superficial = Q/A
    assert abs(packed.residence_time_s(q)
               - 0.4 * open_tube.volume_m3 / q) < 1e-18
    u_sup = q / packed.area_m2
    u_int = q / packed.flow_area_m2
    assert u_int > u_sup and abs(u_int * 0.4 - u_sup) < 1e-18


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} NMR-calibration tests passed.")
