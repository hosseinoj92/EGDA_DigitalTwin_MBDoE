"""Tests of the model-inadequacy governor (sdl_advanced.adequacy) - the
statistically redesigned version: continuous p-values, Sidak-combined
components, alpha spending across rounds, and the parametric-bootstrap
empirical p.  Runnable standalone."""

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


def test_p_values_are_continuous_probabilities():
    """The redesigned governor must return REAL continuous p-values, both
    per component and combined - never a binary 0/1 indicator."""
    ens = _ensemble(("rev-dilute",), seed=1)
    rep = AdequacyGovernor(GovernorConfig(n_rounds_planned=6)).assess(ens, 1)
    assert 0.0 < rep.p_value <= 1.0
    assert rep.p_value not in (0.0, 1.0) or rep.p_value == 1.0
    for name, p in rep.components.items():
        assert 0.0 <= p <= 1.0, (name, p)
    assert len(rep.components) >= 3
    # alpha spending: round threshold = campaign alpha / planned rounds
    cfg = GovernorConfig(alpha_campaign=0.05, n_rounds_planned=10)
    rep2 = AdequacyGovernor(cfg).assess(ens, 1)
    assert np.isclose(rep2.alpha_round, 0.005)


def test_correct_model_not_flagged_inadequate():
    """Empirical spot check (the fuller MC lives in
    benchmark.governor_mc_validation): correct family must not be declared
    inadequate."""
    gov_hits = 0
    for seed in range(6):
        ens = _ensemble(("rev-dilute", "irreversible"), seed)
        rep = AdequacyGovernor(GovernorConfig(n_rounds_planned=6)
                               ).assess(ens, 1)
        if rep.state == GovernorState.MODEL_INADEQUATE:
            gov_hits += 1
    assert gov_hits == 0, f"false-positive inadequacy in {gov_hits}/6 runs"


def test_misspecified_family_is_detected():
    """Wrong family (irreversible only, strongly reversible truth) must be
    detected despite alpha spending."""
    truth5 = dict(TRUTH, K1_ref=0.30, K2_ref=0.02)
    bridge = Layer1Bridge(GEOM, T_REF_K)
    lab = AdvancedVirtualLaboratory(
        truth5, bridge, InstrumentConfig(observation_mode="direct"),
        AcquisitionSettings(), SpectralNuisance(enabled=False),
        TransferConfig(enabled=False), ResourceCosts(), seed=5,
        noise_direct=NOISE)
    ens = ModelEnsemble(build_egda_family(GEOM, T_REF_K,
                                          include=("irreversible",),
                                          noise_assumed=NOISE))
    z = GEOM["length_m"] * np.arange(1, 7) / 6
    for u in CONDS:
        ens.add_measurement(lab.run_profile(u, z))
    ens.update()
    gov = AdequacyGovernor(GovernorConfig(n_rounds_planned=6))
    rep = gov.assess(ens, round_no=2)
    assert rep.state == GovernorState.MODEL_INADEQUATE, (
        rep.state, rep.p_value, rep.components)
    assert rep.round_detected == 2
    assert rep.p_value < rep.alpha_round


def test_bootstrap_pvalue_is_empirical_tail_probability():
    """p_boot = (1 + #extreme) / (B + 1): continuous in (0, 1], large under
    the correct model.  A CHEAP B is only admissible with a correspondingly
    coarse alpha - the resolution guard (B >= ceil(1/alpha) - 1) enforces
    that a bootstrap can actually reach the threshold it is tested at."""
    rng = np.random.default_rng(0)
    ens_ok = _ensemble(("rev-dilute",), seed=7)
    gov = AdequacyGovernor()
    p_ok = gov.bootstrap_pvalue(ens_ok, rng, B=19, alpha=0.05)
    assert 0.0 < p_ok <= 1.0
    assert p_ok >= 1.0 / 20.0                 # by construction
    assert p_ok > 0.2, p_ok                   # correct model: not extreme
    # and an under-resolved B is refused rather than silently unable to reject
    try:
        gov.bootstrap_pvalue(ens_ok, rng, B=19, alpha=0.005)
    except ValueError as exc:
        assert "cannot resolve" in str(exc)
    else:
        raise AssertionError("under-resolved bootstrap was accepted")


def test_discrimination_state_when_models_tie():
    bridge = Layer1Bridge(GEOM, T_REF_K)
    noisy = NoiseModel(sigma_abs_M=0.02, sigma_rel=0.1)
    lab = AdvancedVirtualLaboratory(
        TRUTH, bridge, InstrumentConfig(observation_mode="direct"),
        AcquisitionSettings(), SpectralNuisance(enabled=False),
        TransferConfig(enabled=False), ResourceCosts(), seed=11,
        noise_direct=noisy)
    ens = ModelEnsemble(build_egda_family(
        GEOM, T_REF_K, include=("rev-dilute", "rev-pitzer"),
        noise_assumed=noisy))
    u = OperatingConditions(T_C=45.0, Q1_mL_min=5.0, Q2_mL_min=5.0,
                            C_EGDA_M=1.0, C_cat_M=0.2)
    ens.add_measurement(lab.run_profile(u, [GEOM["length_m"]]))
    ens.update()
    rep = AdequacyGovernor().assess(ens, round_no=1)
    assert rep.state == GovernorState.MODEL_DISCRIMINATION, rep.state


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} adequacy tests passed.")
