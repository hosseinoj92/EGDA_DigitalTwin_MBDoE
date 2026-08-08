"""Tests of the model-inadequacy governor (sdl_advanced.adequacy).
Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import Layer1Bridge, OperatingConditions, NoiseModel
from sdl_advanced.adequacy import (AdequacyGovernor, GovernorConfig,
                                   GovernorState)
from sdl_advanced.instrument import (AdvancedVirtualLaboratory,
                                     InstrumentConfig)
from sdl_advanced.model_ensemble import ModelEnsemble, build_egda_family
from sdl_advanced.resources import ResourceCosts
from sdl_advanced.spectral import AcquisitionSettings, SpectralNuisance
from sdl_advanced.transfer import TransferConfig

T_REF_K = 333.15
GEOM = {"length_m": 0.5, "diameter_m": 0.018}
TRUTH = {"k1_ref": 3.3e-3, "Ea1_J": 58_500.0,
         "k2_ref": 8.5e-4, "Ea2_J": 52_000.0,
         "K1_ref": 0.80, "K2_ref": 0.12}
CONDS = [OperatingConditions(T_C=t, Q1_mL_min=q / 2, Q2_mL_min=q / 2,
                             C_EGDA_M=1.0, C_cat_M=1.0)
         for t, q in ((60.0, 10.0), (85.0, 4.0), (90.0, 1.0))]
NOISE = NoiseModel(sigma_abs_M=1e-3, sigma_rel=1e-2)


def _ensemble(include, seed):
    bridge = Layer1Bridge(GEOM, T_REF_K)
    lab = AdvancedVirtualLaboratory(
        TRUTH, bridge, InstrumentConfig(observation_mode="direct"),
        AcquisitionSettings(), SpectralNuisance(enabled=False),
        TransferConfig(enabled=False), ResourceCosts(), seed=seed,
        noise_direct=NOISE)
    ens = ModelEnsemble(build_egda_family(GEOM, T_REF_K, include=include,
                                          noise_assumed=NOISE))
    z = GEOM["length_m"] * np.arange(1, 7) / 6
    for u in CONDS:
        ens.add_measurement(lab.run_profile(u, z))
    ens.update()
    return ens


def test_correct_model_not_flagged_inadequate():
    """Acceptance criterion 11 (spot check): with the correct structure in
    the candidate set, the governor must NOT declare inadequacy."""
    gov = AdequacyGovernor(GovernorConfig(alpha=0.01))
    hits = 0
    for seed in range(3):
        ens = _ensemble(("rev-dilute", "irreversible"), seed)
        rep = gov.assess(ens, round_no=1)
        if rep.state == GovernorState.MODEL_INADEQUATE:
            hits += 1
    assert hits == 0, f"false-positive inadequacy in {hits}/3 runs"


def test_misspecified_family_is_detected():
    """Acceptance criterion 12: remove the correct (reversible) model; the
    governor must detect systematic lack of fit."""
    gov = AdequacyGovernor(GovernorConfig(alpha=0.01))
    ens = _ensemble(("irreversible",), seed=5)
    rep = gov.assess(ens, round_no=2)
    assert rep.state == GovernorState.MODEL_INADEQUATE, (
        rep.state, rep.score, rep.p_values_all)
    assert rep.round_detected == 2
    assert rep.reasons


def test_mc_calibration_bounds_false_positives():
    """The MC-calibrated trip point must sit above the observed correct-model
    statistic (so calibration cannot make the governor MORE trigger-happy
    than alpha on well-specified data)."""
    gov = AdequacyGovernor(GovernorConfig(alpha=0.05))
    ens = _ensemble(("rev-dilute",), seed=7)
    rep0 = gov.assess(ens, round_no=1)
    q = gov.calibrate_thresholds(ens, np.random.default_rng(0), n_mc=20)
    assert q > 0.5
    rep1 = gov.assess(ens, round_no=1)
    assert rep1.state != GovernorState.MODEL_INADEQUATE
    assert gov.calibrated_quantile is not None
    assert np.isfinite(rep0.score)


def test_discrimination_state_when_models_tie():
    """With little data, several models stay plausible -> the governor must
    ask for model discrimination rather than parameter refinement."""
    bridge = Layer1Bridge(GEOM, T_REF_K)
    lab = AdvancedVirtualLaboratory(
        TRUTH, bridge, InstrumentConfig(observation_mode="direct"),
        AcquisitionSettings(), SpectralNuisance(enabled=False),
        TransferConfig(enabled=False), ResourceCosts(), seed=11,
        noise_direct=NoiseModel(sigma_abs_M=0.02, sigma_rel=0.1))
    ens = ModelEnsemble(build_egda_family(
        GEOM, T_REF_K, include=("rev-dilute", "rev-pitzer"),
        noise_assumed=NoiseModel(sigma_abs_M=0.02, sigma_rel=0.1)))
    # one noisy low-conversion measurement: the two activity models are
    # nearly indistinguishable there
    u = OperatingConditions(T_C=45.0, Q1_mL_min=5.0, Q2_mL_min=5.0,
                            C_EGDA_M=1.0, C_cat_M=0.2)
    ens.add_measurement(lab.run_profile(u, [GEOM["length_m"]]))
    ens.update()
    rep = AdequacyGovernor().assess(ens, round_no=1)
    assert rep.state == GovernorState.MODEL_DISCRIMINATION, (
        rep.state, dict(zip([c.name for c in ens.models], ens.probs)))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} adequacy tests passed.")
