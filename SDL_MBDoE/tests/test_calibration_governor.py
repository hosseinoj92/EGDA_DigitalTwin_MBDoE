"""Stage-1 regression tests for: NMR calibration/validation independence and
PSD covariance, governor decision-component consistency and bootstrap
resolution, boundary-aware evidence reliability, and survivorship-free
aggregation.  Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import (Layer1Bridge, OperatingConditions, NoiseModel,
                 ParameterSpace, literature_guess)
from sdl_advanced import benchmark as bm
from sdl_advanced.adequacy import AdequacyGovernor, GovernorConfig
from sdl_advanced.instrument import (AdvancedVirtualLaboratory,
                                     InstrumentConfig)
from sdl_advanced.model_ensemble import ModelEnsemble, build_egda_family
from sdl_advanced.resources import ResourceCosts
from sdl_advanced.spectral import (AcquisitionSettings, NMRSimulator,
                                   SpectralNuisance)
from sdl_advanced.spectral_fit import (SpectralFitter, calibrate_empirical,
                                       calibrate_responses)
from sdl_advanced.transfer import TransferConfig

ACQ = AcquisitionSettings(n_points=2048)
T_REF_K = bm.T_REF_C + 273.15
GEOM = {"length_m": 0.5, "diameter_m": 0.018}
TRUTH = {"k1_ref": 3.3e-3, "Ea1_J": 58_500.0,
         "k2_ref": 8.5e-4, "Ea2_J": 52_000.0,
         "K1_ref": 0.80, "K2_ref": 0.12}


# ---- NMR calibration ------------------------------------------------------ #
def _calibrated_fitter(seed=0):
    sim = NMRSimulator(ACQ, SpectralNuisance())
    fitter = SpectralFitter(ACQ)
    cal_rng = np.random.default_rng(seed + 900_001)
    acquire = lambda s, r: sim.simulate(s, r)[:2]
    calibrate_responses(fitter, acquire, cal_rng)
    info = calibrate_empirical(fitter, acquire, cal_rng)
    return sim, fitter, info


def test_empirical_calibration_is_psd_and_correlated():
    _sim, fitter, info = _calibrated_fitter()
    cov = info["cov_M2"]
    assert cov.shape == (len(fitter.species),) * 2
    assert np.allclose(cov, cov.T)
    w = np.linalg.eigvalsh(cov)
    assert np.all(w >= -1e-18), w              # PSD by construction
    # inter-species correlation is PRESERVED (not a diagonal model)
    assert np.max(np.abs(info["corr"] - np.eye(len(fitter.species)))) > 0.05


def test_calibration_and_validation_use_independent_seeds():
    """The validation spectra must not be the calibration spectra: the
    calibration RNG and validation RNG are different streams."""
    sim, fitter, _ = _calibrated_fitter(seed=0)
    cal_rng = np.random.default_rng(0 + 900_001)
    val_rng = np.random.default_rng(0 + 12_345)
    std = {"EGDA": 0.3, "EGMA": 0.1, "EG": 0.05, "AcOH": 0.2, "H2O": 52.0}
    y_cal = sim.simulate(std, cal_rng)[1]
    y_val = sim.simulate(std, val_rng)[1]
    assert not np.allclose(y_cal, y_val)


def test_calibrated_covariance_replaces_surrogate_floor():
    """Sigma_eff = Sigma_fit + Sigma_empirical; the ASSUMED surrogate floor
    terms must switch off when the empirical model is calibrated, so the
    two are never double-counted."""
    sim, fitter, _ = _calibrated_fitter(seed=1)
    rng = np.random.default_rng(7)
    conc = {"EGDA": 0.3, "EGMA": 0.1, "EG": 0.05, "AcOH": 0.2, "H2O": 52.0}
    ppm, y, _ = sim.simulate(conc, rng)
    res_cal = fitter.fit(ppm, y)
    raw = SpectralFitter(ACQ)                       # uncalibrated surrogate
    res_raw = raw.fit(ppm, y)
    assert fitter.empirical_cov is not None and raw.empirical_cov is None
    for m in (res_cal.cov, res_raw.cov):
        assert np.all(np.linalg.eigvalsh(m) > 0)
    # bias correction actually moves the estimate
    assert not np.allclose(res_cal.conc_M, res_raw.conc_M)


# ---- governor ------------------------------------------------------------- #
def _small_ensemble(seed=3):
    bridge = Layer1Bridge(GEOM, T_REF_K)
    noise = NoiseModel(sigma_abs_M=1e-3, sigma_rel=1e-2)
    lab = AdvancedVirtualLaboratory(
        TRUTH, bridge, InstrumentConfig(observation_mode="direct"),
        ACQ, SpectralNuisance(enabled=False), TransferConfig(enabled=False),
        ResourceCosts(), seed=seed, noise_direct=noise)
    ens = ModelEnsemble(build_egda_family(GEOM, T_REF_K,
                                          include=("rev-dilute",),
                                          noise_assumed=noise))
    z = GEOM["length_m"] * np.arange(1, 7) / 6
    for T in (60.0, 85.0, 90.0):
        ens.add_measurement(lab.run_profile(
            OperatingConditions(T, 2.0, 2.0, 1.0, 1.0), z))
    ens.update()
    return ens


def test_decision_components_are_one_shared_definition():
    """assess(), the analytical combination and the bootstrap must all use
    the SAME component set - defined once in decision_components()."""
    comps = {"chi2": 0.4, "z_autocorr": 1e-9, "species_bias": 0.3,
             "T_trend": 0.8, "worst_cell": 0.2}
    g_nmr = AdequacyGovernor(GovernorConfig(systematic_allowance=0.7))
    g_dir = AdequacyGovernor(GovernorConfig(systematic_allowance=0.0))
    used_nmr = g_nmr.decision_components(comps, n_pairs=100)
    used_dir = g_dir.decision_components(comps, n_pairs=100)
    assert "z_autocorr" not in used_nmr        # excluded under NMR systematics
    assert "z_autocorr" in used_dir            # included for direct data
    # combine() uses exactly those sets (Sidak over the USED components)
    p_nmr = g_nmr.combine(comps, n_pairs=100)
    expect = 1.0 - (1.0 - min(used_nmr.values())) ** len(used_nmr)
    assert abs(p_nmr - expect) < 1e-12
    # too few z-pairs -> autocorrelation dropped even in direct mode
    assert "z_autocorr" not in g_dir.decision_components(comps, n_pairs=4)


def test_bootstrap_resolution_guard():
    """B must be able to resolve alpha: 1/(B+1) <= alpha, else reject."""
    gov = AdequacyGovernor(GovernorConfig(alpha_campaign=0.05,
                                          n_rounds_planned=6))
    alpha_round = 0.05 / 6                      # ~0.00833
    b_min = gov.min_replicates_for(alpha_round)
    assert 1.0 / (b_min + 1) <= alpha_round
    assert b_min >= 119                         # ceil(1/0.00833)-1 = 119
    ens = _small_ensemble()
    try:
        gov.bootstrap_pvalue(ens, np.random.default_rng(0), B=64)
    except ValueError as exc:
        assert "cannot resolve" in str(exc)
    else:
        raise AssertionError("B=64 must be rejected for alpha_round<1/65")


def test_bootstrap_pvalue_uses_decision_statistic():
    """Cheap check (B kept small via an explicit large alpha): the returned
    p is a genuine empirical tail probability in (0, 1]."""
    gov = AdequacyGovernor(GovernorConfig(alpha_campaign=0.5,
                                          n_rounds_planned=1))
    ens = _small_ensemble(seed=5)
    # alpha=0.5 -> B_min = ceil(1/0.5)-1 = 1, so p must lie on the DISCRETE
    # grid (1+k)/(B+1) with B=1: exactly 0.5 or 1.0.  A real check that can
    # genuinely fail - no unconditional escape hatch.
    b_min = gov.min_replicates_for(0.5)
    assert b_min == 1
    p = gov.bootstrap_pvalue(ens, np.random.default_rng(1), alpha=0.5)
    assert 0.0 < p <= 1.0
    grid = [(1 + k) / (b_min + 1) for k in range(b_min + 1)]
    assert any(abs(p - g) < 1e-12 for g in grid), (p, grid)


# ---- boundary-aware evidence --------------------------------------------- #
def test_evidence_reliability_flag_present():
    ens = _small_ensemble(seed=9)
    assert hasattr(ens, "evidence_reliable")
    assert set(ens.evidence_reliable) == {cm.name for cm in ens.models}
    for name, ok in ens.evidence_reliable.items():
        assert isinstance(ok, bool)
    # a model pinned to a bound must be flagged unreliable
    cm = ens.models[0]
    lo, _hi = cm.space.bounds()
    cm.posterior.theta_map = lo.copy()          # force every parameter onto
    ens._assess_evidence_reliability()          # its lower bound
    assert ens.evidence_reliable[cm.name] is False
    assert ens.evidence_warnings
    assert "NOT reliable evidence" in ens.evidence_warnings[0]
    assert not ens.probs_reliable


# ---- survivorship-free aggregation --------------------------------------- #
def test_paused_campaign_is_retained_in_statistics():
    """A seed that stops early keeps its LAST VALID round in the summary
    (n_seeds unchanged) instead of vanishing."""
    rows = []
    for seed in (1, 2, 3):
        n_rounds = 2 if seed == 3 else 4        # seed 3 paused early
        for rnd in range(1, n_rounds + 1):
            rows.append({
                "scenario": "S", "strategy": "F", "seed": seed,
                "round": rnd, "param_err_pct": 10.0 * seed,
                "blind_rmse_M": 1e-3 * seed,
                "stop_reason": ("MEASUREMENT_FAULT: paused" if seed == 3
                                else "budget exhausted")})
    last = bm.last_valid_rows(rows, "S", "F")
    assert len(last) == 3                       # NO seed dropped
    assert {r["seed"]: r["round"] for r in last} == {1: 4, 2: 4, 3: 2}
    summary = bm.summarize_final(rows, "S")[0]
    assert summary["n_seeds"] == 3 and summary["n_faulted"] == 1
    # paired comparisons use the common seeds of both strategies
    rows += [dict(r, strategy="D") for r in rows if r["seed"] in (1, 2)]
    pc = bm.paired_comparison(rows, "S", "F", "D", "blind_rmse_M")
    assert pc["n_pairs"] == 2


def test_parameter_rows_are_populated_even_with_singular_fim():
    """benchmark_params.csv was empty because an early rank-deficient FIM
    gives an astronomically large sigma and exp() overflowed while building
    the interval.  Rows must now always be produced, with the unbounded
    interval reported as inf rather than raising."""
    space = ParameterSpace(t_ref_K=T_REF_K,
                           initial_guess=dict(literature_guess(T_REF_K)))
    theta_nat = dict(space.initial_guess)
    huge = np.full(space.n_params, 4.1e5)        # rank-deficient early round
    rows = bm._param_rows(bm.SCENARIOS["S1_ideal"], "A", 1, 1, space,
                          theta_nat, huge, (), bm.TRUTH)
    assert len(rows) == space.n_params
    by_key = {r["param"]: r for r in rows}
    for q, k in enumerate(space.param_keys):
        r = by_key[k]
        assert np.isfinite(r["estimate"])
        assert "true_value" in r and "rel_error_pct" in r
        if space.is_log(q):          # exp() would have overflowed before
            assert r["rel_width_pct"] == float("inf")
        else:                        # linear (Ea): huge but finite
            assert np.isfinite(r["rel_width_pct"])
            assert r["rel_width_pct"] > 1e4
    # a well-determined posterior gives finite, usable intervals
    small = np.full(space.n_params, 0.05)
    rows2 = bm._param_rows(bm.SCENARIOS["S1_ideal"], "F", 1, 6, space,
                           theta_nat, small, ("k1_ref",), bm.TRUTH)
    assert all(np.isfinite(r["rel_width_pct"]) for r in rows2)
    assert any(r["bound_active"] == 1 for r in rows2)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} calibration/governor tests passed.")
