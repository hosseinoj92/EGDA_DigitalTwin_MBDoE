"""Central Boolean feature control.

The contract these tests defend:

  * ONE switch per optional effect, and every switch reaches real code;
  * False is a BYPASS - the idealized behaviour is recovered exactly, not
    approximated by a small parameter with the machinery still running;
  * a switch declared ON whose magnitude is zero is rejected (the inverse
    failure: the run record would claim an effect that is not simulated);
  * switches apply to TRUTH and INFERENCE alike, and deliberate divergence
    is impossible without enabling the MODEL_MISMATCH section explicitly;
  * the resolved state is complete - no hidden defaults survive into an
    archived run.

Runnable standalone:  python tests/test_features.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import Layer1Bridge, OperatingConditions, literature_guess
from sdl_advanced import benchmark as bm
from sdl_advanced import features as feat
from sdl_advanced.spectral import AcquisitionSettings, NMRSimulator, \
    SpectralNuisance

T_REF_K = bm.T_REF_C + 273.15
GUESS = literature_guess(T_REF_K)
U0 = OperatingConditions(120.0, 0.5, 0.5, 1.0, 1.0)
GEOM = {"length_m": 0.2, "diameter_m": 0.007}
COMP = {"EGDA": 0.30, "EGMA": 0.12, "EG": 0.05, "AcOH": 0.20, "H2O": 53.0}


def _with(**features):
    """Context helper: apply feature overrides, restore afterwards."""
    class _Ctx:
        def __enter__(self):
            self.before = bm.resolved_config()
            bm.apply_config({"FEATURES": dict(features)})
            bm.invalidate_caches()
            return bm

        def __exit__(self, *exc):
            bm.apply_config(self.before)
            bm.invalidate_caches()
            return False
    return _Ctx()


# ---- 1. the catalogue is complete and self-describing --------------------- #
def test_every_feature_has_a_handler_and_three_explanations():
    for f in feat.FEATURES_SPEC:
        assert f.name in feat._HANDLERS, f.name
        for field in ("represents", "when_true", "when_false"):
            text = getattr(f, field)
            assert isinstance(text, str) and len(text) > 30, (f.name, field)
        assert f.section in feat.SECTIONS, (f.name, f.section)


def test_the_review_checklist_is_covered():
    """Every item the review asked to be switchable has a switch."""
    names = set(feat.FEATURES_BY_NAME)
    required = {
        "reversible_chemistry", "temperature_dependent_kinetics",
        "temperature_dependent_equilibrium", "nonideal_acid_activity",
        "acid_speciation_equilibrium", "transfer_line_reaction",
        "transfer_line_temperature_correction", "packed_bed_reactor",
        "axial_dispersion_criterion", "reactor_validity_enforcement",
        "geometry_optimization", "nmr_fid_engine",
        "overlap_correlated_errors", "nmr_line_broadening",
        "nmr_baseline_distortion", "nmr_chemical_shift_drift",
        "nmr_white_noise", "nmr_correlated_noise",
        "quantification_uncertainty", "measurement_outliers",
        "instrument_faults", "qc_rejection", "resource_accounting",
        "acquisition_time_accounting", "continuous_design_space",
        "adaptive_single_measurement",
    }
    assert required <= names, sorted(required - names)


def test_unknown_switch_and_non_boolean_are_refused():
    for bad in ({"not_a_feature": True}, {"reversible_chemistry": 1}):
        try:
            feat.validate(bad, None)
        except (KeyError, TypeError):
            pass
        else:
            raise AssertionError(f"{bad} should have been refused")


def test_dependencies_are_enforced():
    try:
        feat.validate({"transfer_line": False,
                       "transfer_line_reaction": True}, None)
    except ValueError as exc:
        assert "prerequisite" in str(exc)
    else:
        raise AssertionError("unmet dependency must raise")


def test_feature_on_with_zero_magnitude_is_refused():
    """The inverse of 'off means a tiny number': a switch that is ON must
    actually do something, or the run record lies about what was simulated."""
    before = bm.resolved_config()
    try:
        bm.apply_config({"NMR_NUISANCE_TRUE": {"noise_sigma": 0.0}})
    except ValueError as exc:
        assert "does nothing" in str(exc)
    else:
        raise AssertionError("noise_sigma = 0 with the switch ON must raise")
    finally:
        bm.apply_config(before)
        bm.invalidate_caches()


# ---- 2. False is a genuine bypass ---------------------------------------- #
def test_noise_off_makes_acquisitions_bit_identical():
    """With the noise gate off (and nothing else random left on), repeated
    acquisitions of one composition are IDENTICAL - the strongest possible
    statement that the noise path did not run."""
    acq = AcquisitionSettings(n_points=1024)
    quiet = dict(line_broadening=False, baseline_distortion=False,
                 chemical_shift_drift=False, phase_error=False,
                 gain_drift=False)
    off = NMRSimulator(acq, SpectralNuisance(white_noise=False,
                                             correlated_noise=False,
                                             **quiet))
    a = off.simulate(COMP, np.random.default_rng(1))[1]
    b = off.simulate(COMP, np.random.default_rng(2))[1]
    assert np.array_equal(a, b), "noise off must be deterministic"
    # ... and with it on, two draws differ
    on = NMRSimulator(acq, SpectralNuisance(correlated_noise=False, **quiet))
    c = on.simulate(COMP, np.random.default_rng(1))[1]
    d = on.simulate(COMP, np.random.default_rng(2))[1]
    assert not np.array_equal(c, d)
    assert not np.array_equal(a, c)
    # the fully ideal instrument is deterministic too
    ideal = NMRSimulator(acq, SpectralNuisance().ideal())
    assert np.array_equal(ideal.simulate(COMP, np.random.default_rng(3))[1],
                          ideal.simulate(COMP, np.random.default_rng(4))[1])


def test_each_nmr_gate_off_reproduces_the_ideal_limit_exactly():
    """Gate off == that effect absent, bit for bit.  Compared against a
    nuisance whose MAGNITUDE is also zero: the two must agree exactly, which
    is what makes 'bypassed' and 'ideal' the same statement."""
    acq = AcquisitionSettings(n_points=1024)
    cases = {
        "baseline_distortion": dict(baseline_offset=0.0, baseline_curve=0.0,
                                    baseline_cubic=0.0),
        "chemical_shift_drift": dict(shift_drift_ppm=0.0,
                                     shift_jitter_ppm=0.0,
                                     static_shift_ppm=0.0),
        "line_broadening": dict(linewidth_rel_sigma=0.0),
        "phase_error": dict(phase_error_deg=0.0),
        "gain_drift": dict(gain_drift_rel_sigma=0.0),
        "lineshape_mismatch": dict(gaussian_fraction=0.0, j_mismatch_hz=0.0),
        "response_error": dict(response_factors={}),
    }
    for gate, zeros in cases.items():
        # everything else off so ONLY this effect distinguishes the two
        base = dict(white_noise=False, correlated_noise=False,
                    line_broadening=False, baseline_distortion=False,
                    chemical_shift_drift=False, phase_error=False,
                    gain_drift=False, lineshape_mismatch=False,
                    response_error=False)
        gated = SpectralNuisance(**base)
        zeroed = SpectralNuisance(**{**base, gate: True}, **zeros)
        y_gate = NMRSimulator(acq, gated).simulate(
            COMP, np.random.default_rng(7))[1]
        y_zero = NMRSimulator(acq, zeroed).simulate(
            COMP, np.random.default_rng(7))[1]
        assert np.allclose(y_gate, y_zero, atol=1e-12), gate


def test_reversible_chemistry_off_removes_the_equilibrium_everywhere():
    with _with(reversible_chemistry=False,
               temperature_dependent_equilibrium=False):
        assert bm.TRUTH_CHEMISTRY["reversible"] is False
        assert bm.INFERENCE_CHEMISTRY["reversible"] is False
        # no candidate model carries K parameters any more
        for name in ("S1_ideal", "S4a_ambiguity", "S4b_identifiable"):
            fam = bm.scenario_family(bm.SCENARIOS[name])
            assert fam == ("irreversible",), (name, fam)
        # and the forward model is genuinely irreversible: conversion at a
        # long residence time is complete rather than equilibrium-limited
        b_irr = Layer1Bridge(GEOM, T_REF_K, **bm.TRUTH_CHEMISTRY)
        y = b_irr.concentrations_at(GUESS, OperatingConditions(
            160.0, 0.05, 0.05, 1.0, 2.0), np.array([0.2]), ("EGDA",))
        assert y[0] < 1e-3


def test_temperature_dependence_gates_are_real_bypasses():
    hot = OperatingConditions(160.0, 0.5, 0.5, 1.0, 1.0)
    cold = OperatingConditions(40.0, 0.5, 0.5, 1.0, 1.0)
    z = np.array([0.2])
    on = Layer1Bridge(GEOM, T_REF_K, activity_model="pitzer")
    off = Layer1Bridge(GEOM, T_REF_K, activity_model="pitzer",
                       arrhenius=False)
    assert (on.concentrations_at(GUESS, hot, z, ("EGDA",))[0]
            != on.concentrations_at(GUESS, cold, z, ("EGDA",))[0])
    # with Arrhenius off the rate constants no longer depend on T; the
    # remaining T dependence is the acid speciation, so switch it off too
    off2 = Layer1Bridge(GEOM, T_REF_K, activity_model="pitzer",
                        arrhenius=False, van_t_hoff=False,
                        ka2_model="constant")
    k_hot = off2.kinetics_from_theta(GUESS).step1.k(433.15)
    k_cold = off2.kinetics_from_theta(GUESS).step1.k(313.15)
    assert abs(k_hot - k_cold) < 1e-15
    assert off2.kinetics_from_theta(GUESS).eq1.K(433.15) == \
        off2.kinetics_from_theta(GUESS).eq1.K(313.15)
    assert off.kinetics_from_theta(GUESS).step1.Ea == 0.0


def test_transfer_line_gates_reach_every_scenario():
    """REGRESSION: the scenarios used to CAPTURE a TransferConfig at import,
    so a runner override or a feature switch never reached them."""
    with _with(transfer_line=False):
        for name in ("S3_transport", "S3ab_delay", "S3ab_rtd"):
            assert not bm.SCENARIOS[name].transfer.enabled, name
    with _with(transfer_line_carryover=False):
        assert bm.SCENARIOS["S3_transport"].transfer.enabled
        assert not bm.SCENARIOS["S3_transport"].transfer.carryover
    with _with(transfer_line_temperature_correction=False):
        # None means "the sample stays at REACTOR temperature"
        assert bm.SCENARIOS["S3_transport"].transfer.T_line_C is None
    with _with(transfer_line_rtd_dispersion=False):
        assert bm.SCENARIOS["S3_transport"].transfer.rtd == "delta"


def test_quantification_uncertainty_off_leaves_only_the_fit_covariance():
    with _with(quantification_uncertainty=False):
        kw = bm.fitter_kwargs()
        assert kw["sigma_floor_abs_M"] == 0.0
        assert kw["sigma_floor_rel"] == 0.0
        assert kw["gain_drift_rel"] == 0.0
        assert kw["shift_jitter_ppm"] == 0.0
        assert kw["empirical_error_model"] is False


def test_resource_accounting_off_meters_nothing():
    from sdl_advanced.resources import ResourceCosts, ResourceMeter
    m = ResourceMeter(ResourceCosts(), 5.0, enabled=False)
    m.log_condition(120.0, 1.0, 1.0, 1.0)
    m.log_acquisition(0.1, 120.0, 1.0, 1.0, 1.0)
    m.log_qc_reject(0.1)
    assert m.events == []
    assert all(v == 0 for v in m.totals().values())


def test_faults_off_means_no_injection_code_runs():
    from sdl_advanced.instrument import FaultModel
    off = FaultModel(enabled=False, spectrum_fault_prob=0.9,
                     outlier_prob=0.9)
    assert not off.spectrum_faults_active and not off.outliers_active
    zero = FaultModel(enabled=True, spectrum_fault_prob=0.0)
    assert not zero.spectrum_faults_active


def test_switching_a_feature_off_changes_the_configuration_it_gates():
    """Every switch must move SOMETHING: compare the resolved configuration
    with the switch on and off, and require a difference."""
    import json
    base = json.dumps(bm.resolved_config(), sort_keys=True, default=str)
    unchanged = []
    for f in feat.FEATURES_SPEC:
        flip = {f.name: not f.default}
        if not f.default:
            # turning something ON may need its prerequisites on too
            flip.update({dep: True for dep in f.requires})
        else:
            # turning something OFF must take its dependants with it
            flip.update({g.name: False for g in feat.FEATURES_SPEC
                         if f.name in g.requires})
        with _with(**flip):
            now = json.dumps(bm.resolved_config(), sort_keys=True,
                             default=str)
            if now == base:
                unchanged.append(f.name)
    assert not unchanged, f"switches with no effect: {unchanged}"


# ---- 3. truth and inference move together unless told otherwise ---------- #
def test_switches_apply_to_truth_and_inference_alike():
    for name, extra in (
            ("nonideal_acid_activity", {}),
            # Ka2(T) is meaningless without the speciation equilibrium, so
            # the dependency check requires them to move together
            ("acid_speciation_equilibrium",
             {"temperature_dependent_ka2": False}),
            ("temperature_dependent_kinetics", {}),
            ("reversible_chemistry",
             {"temperature_dependent_equilibrium": False})):
        with _with(**{name: False}, **extra):
            assert bm.TRUTH_CHEMISTRY == bm.INFERENCE_CHEMISTRY, name


def test_model_mismatch_is_off_by_default_and_cannot_be_silent():
    assert bm.MODEL_MISMATCH["enabled"] is False
    assert bm.MODEL_MISMATCH_ACTIVE is False
    assert bm.TRUTH_PARAMETER_BIAS == {}
    try:
        feat.validate({}, {"enabled": False, "inference_reversible": False})
    except ValueError as exc:
        assert "not enabled" in str(exc)
    else:
        raise AssertionError("a configured but undeclared mismatch must "
                             "raise")


def test_model_mismatch_when_enabled_splits_the_two_sides():
    before = bm.resolved_config()
    try:
        bm.apply_config({"MODEL_MISMATCH": {
            "enabled": True, "inference_activity_model": "dilute",
            "truth_parameter_bias": {"k2_ref": 2.0}}})
        assert bm.MODEL_MISMATCH_ACTIVE
        assert bm.TRUTH_CHEMISTRY["activity_model"] == "pitzer"
        assert bm.INFERENCE_CHEMISTRY["activity_model"] == "dilute"
        assert abs(bm.SCENARIOS["S1_ideal"].truth["k2_ref"]
                   - 2.0 * bm.TRUTH["k2_ref"]) < 1e-18
    finally:
        bm.apply_config(before)
        bm.invalidate_caches()
        assert not bm.MODEL_MISMATCH_ACTIVE
        assert bm.SCENARIOS["S1_ideal"].truth["k2_ref"] == bm.TRUTH["k2_ref"]


# ---- 4. the record is complete ------------------------------------------- #
def test_resolved_record_has_every_switch_and_its_explanation():
    rec = bm.resolved_config()["FEATURES_RESOLVED"]
    assert set(rec["features"]) == set(feat.FEATURES_BY_NAME)
    assert set(rec["explanations"]) == set(feat.FEATURES_BY_NAME)
    for name, exp in rec["explanations"].items():
        assert exp["represents"] and exp["when_true"] and exp["when_false"]
    assert "model_mismatch" in rec and rec["model_mismatch"]["ACTIVE"] in (
        True, False)
    assert "truth_chemistry" in rec["derived"]


def test_runner_config_resolves_and_records_no_hidden_defaults():
    import run_advanced_benchmark as R
    before = bm.resolved_config()
    try:
        resolved = bm.apply_config(dict(R.KNOBS))
        assert set(resolved["FEATURES_RESOLVED"]["features"]) == \
            set(feat.FEATURES_BY_NAME)
        # the runner declares every switch explicitly - nothing is left to
        # a library default the archive would not show
        assert set(R.KNOBS["FEATURES"]) == set(feat.FEATURES_BY_NAME), \
            sorted(set(feat.FEATURES_BY_NAME) ^ set(R.KNOBS["FEATURES"]))
    finally:
        bm.apply_config(before)
        bm.invalidate_caches()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} feature-control tests passed.")
