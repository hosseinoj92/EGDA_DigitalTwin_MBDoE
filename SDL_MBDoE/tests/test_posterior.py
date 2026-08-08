"""Tests of the Laplace posterior and model ensemble
(sdl_advanced.posterior / model_ensemble).  Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import (Layer1Bridge, OperatingConditions, ParameterSpace,
                 NoiseModel, InferenceModel, literature_guess)
from sdl.observation import Measurement
from sdl_advanced.instrument import (AdvancedVirtualLaboratory,
                                     InstrumentConfig)
from sdl_advanced.model_ensemble import ModelEnsemble, build_egda_family
from sdl_advanced.posterior import GaussianPrior, LaplacePosterior
from sdl_advanced.resources import ResourceCosts
from sdl_advanced.spectral import AcquisitionSettings, SpectralNuisance
from sdl_advanced.transfer import TransferConfig

T_REF_K = 333.15
GEOM = {"length_m": 0.5, "diameter_m": 0.018}
TRUTH = {"k1_ref": 3.3e-3, "Ea1_J": 58_500.0,
         "k2_ref": 8.5e-4, "Ea2_J": 52_000.0,
         "K1_ref": 0.80, "K2_ref": 0.12}
SPECIES = ("EGDA", "EGMA", "EG", "AcOH")
CONDS = [OperatingConditions(T_C=t, Q1_mL_min=q / 2, Q2_mL_min=q / 2,
                             C_EGDA_M=1.0, C_cat_M=1.0)
         for t, q in ((60.0, 10.0), (85.0, 4.0), (90.0, 1.0))]
NOISE = NoiseModel(sigma_abs_M=5e-4, sigma_rel=5e-3)


def _measurements(seed=0):
    bridge = Layer1Bridge(GEOM, T_REF_K)
    lab = AdvancedVirtualLaboratory(
        TRUTH, bridge, InstrumentConfig(observation_mode="direct"),
        AcquisitionSettings(), SpectralNuisance(enabled=False),
        TransferConfig(enabled=False), ResourceCosts(), seed=seed,
        noise_direct=NOISE)
    z = GEOM["length_m"] * np.arange(1, 7) / 6
    return [lab.run_profile(u, z) for u in CONDS]


def test_map_matches_wls_under_weak_prior():
    bridge = Layer1Bridge(GEOM, T_REF_K)
    space = ParameterSpace(t_ref_K=T_REF_K,
                           initial_guess=literature_guess(T_REF_K))
    inf_wls = InferenceModel(space, bridge, NOISE)
    inf_map = InferenceModel(space, bridge, NOISE)
    for m in _measurements(1):
        inf_wls.add_measurement(m)
        inf_map.add_measurement(m)
    inf_wls.fit()
    post = LaplacePosterior(inf_map, GaussianPrior.from_space(space))
    post.fit_map()
    # informative low-noise data: the weak prior must barely move the MAP
    assert np.max(np.abs(post.theta_map - inf_wls.theta)) < 0.05
    assert np.all(np.isfinite(post.cov))
    assert np.isfinite(post.log_evidence)


def test_posterior_sampling_within_bounds():
    bridge = Layer1Bridge(GEOM, T_REF_K)
    space = ParameterSpace(t_ref_K=T_REF_K,
                           initial_guess=literature_guess(T_REF_K))
    inf = InferenceModel(space, bridge, NOISE)
    for m in _measurements(2):
        inf.add_measurement(m)
    post = LaplacePosterior(inf, GaussianPrior.from_space(space))
    post.fit_map()
    draws = post.sample(64, np.random.default_rng(0))
    lo, hi = space.bounds()
    assert draws.shape == (64, space.n_params)
    assert np.all(draws >= lo - 1e-12) and np.all(draws <= hi + 1e-12)


def test_evidence_prefers_correct_structure():
    """Scenario-4 miniature: reversible truth -> the reversible candidate
    must beat the irreversible one on model probability."""
    family = build_egda_family(GEOM, T_REF_K,
                               include=("rev-dilute", "irreversible"),
                               noise_assumed=NOISE)
    ens = ModelEnsemble(family)
    for m in _measurements(3):
        ens.add_measurement(m)
    ens.update()
    assert ens.prob_of("rev-dilute") > 0.95, dict(
        zip([cm.name for cm in ens.models], ens.probs))
    assert ens.best.name == "rev-dilute"


def test_measurement_with_own_covariance_is_respected():
    """Backward-compatibility contract of Measurement.cov_y."""
    bridge = Layer1Bridge(GEOM, T_REF_K)
    space = ParameterSpace(t_ref_K=T_REF_K,
                           initial_guess=literature_guess(T_REF_K))
    inf = InferenceModel(space, bridge, NOISE)
    u = CONDS[0]
    y = np.full(4, 0.3)
    m_legacy = Measurement(u=u, z_m=np.array([0.5]), species=SPECIES, y=y)
    m_own = Measurement(u=u, z_m=np.array([0.5]), species=SPECIES, y=y,
                        cov_y=np.eye(4) * 4.0)
    inf.add_measurement(m_legacy)
    inf.add_measurement(m_own)
    expected_legacy = np.linalg.cholesky(NOISE.covariance(y, SPECIES, 1))
    assert np.allclose(inf._chols[0], expected_legacy)   # NoiseModel fallback
    assert np.allclose(inf._chols[1], np.eye(4) * 2.0)   # supplied cov used


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} posterior tests passed.")
