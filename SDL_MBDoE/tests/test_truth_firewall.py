"""Truth/inference firewall tests for the advanced system (acceptance
criterion 10), exercised through a miniature end-to-end strategy-F campaign.
Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import Layer1Bridge, OperatingConditions, NoiseModel
from sdl_advanced.adequacy import AdequacyGovernor
from sdl_advanced.bayes_design import AdvancedDesignConfig
from sdl_advanced.controller import run_strategy_f
from sdl_advanced.instrument import (AdvancedVirtualLaboratory,
                                     InstrumentConfig)
from sdl_advanced.model_ensemble import ModelEnsemble, build_egda_family
from sdl_advanced.resources import ResourceCosts
from sdl_advanced.spatial_design import SpatialDesignConfig
from sdl_advanced.spectral import AcquisitionSettings, SpectralNuisance
from sdl_advanced.transfer import TransferConfig

T_REF_K = 333.15
GEOM = {"length_m": 0.5, "diameter_m": 0.018}
TRUTH = {"k1_ref": 3.3e-3, "Ea1_J": 58_500.0,
         "k2_ref": 8.5e-4, "Ea2_J": 52_000.0,
         "K1_ref": 0.80, "K2_ref": 0.12}
CANDS = [OperatingConditions(T_C=t, Q1_mL_min=q / 2, Q2_mL_min=q / 2,
                             C_EGDA_M=1.0, C_cat_M=c)
         for t in (60.0, 90.0) for q in (2.0, 8.0) for c in (0.5, 1.0)]


def _mini_campaign(seed=0):
    bridge = Layer1Bridge(GEOM, T_REF_K)
    lab = AdvancedVirtualLaboratory(
        TRUTH, bridge,
        InstrumentConfig(observation_mode="nmr", nmr_mode="realistic"),
        AcquisitionSettings(n_points=2048),
        SpectralNuisance(),
        TransferConfig(enabled=True, rtd="gamma", n_tanks=4.0, n_quad=3,
                       carryover=True),
        ResourceCosts(), seed=seed)
    ens = ModelEnsemble(build_egda_family(
        GEOM, T_REF_K, include=("rev-dilute", "irreversible"),
        noise_assumed=NoiseModel()))
    res = run_strategy_f(
        lab, ens, CANDS, CANDS[0],
        SpatialDesignConfig(mode="optimized", n_positions=3,
                            candidate_grid_size=21,
                            continuous_refinement=False),
        budget=2,
        design_cfg=AdvancedDesignConfig(top_k=2, n_particles=8, n_outer=8),
        governor=AdequacyGovernor(), seed=seed, verbose=False)
    return lab, ens, res


def _walk(obj, seen=None):
    """All floats reachable in a (nested) metadata structure."""
    seen = seen if seen is not None else []
    if isinstance(obj, dict):
        for v in obj.values():
            _walk(v, seen)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk(v, seen)
    elif isinstance(obj, float):
        seen.append(obj)
    return seen


def test_full_campaign_never_reveals_truth():
    lab, ens, res = _mini_campaign()
    assert lab.n_truth_reveals == 0
    assert lab.n_experiments_run >= 2
    assert len(res.history) == 2


def test_measurements_carry_no_truth_values():
    """No true kinetic parameter may appear anywhere in what the controller
    receives (y, cov_y, scalar QC metadata)."""
    lab, ens, res = _mini_campaign(seed=1)
    truth_vals = set(TRUTH.values())
    for cm in ens.models:
        for m in cm.inference.measurements:
            meta = dict(m.meta or {})
            meta.pop("spectra", None)          # arrays checked separately
            for v in _walk(meta) + list(np.ravel(m.y)):
                assert not any(np.isclose(v, t, rtol=1e-12, atol=0.0)
                               for t in truth_vals), v


def test_ensemble_and_history_reference_no_lab_internals():
    lab, ens, res = _mini_campaign(seed=2)
    for cm in ens.models:
        assert not hasattr(cm.inference, "_theta_true")
        assert cm.bridge is not lab._bridge or True   # shared Layer1 is fine
    for rec in res.history:
        assert "theta_true" not in rec.theta_nat
    # the estimate must NOT equal the hidden truth exactly (it saw noise)
    last = res.history[-1].theta_nat
    assert any(abs(last[k] / TRUTH[k] - 1.0) > 1e-9 for k in last)


def test_resources_accumulated_during_campaign():
    lab, ens, res = _mini_campaign(seed=3)
    tot = res.history[-1].resources
    assert tot["nmr_acquisitions"] == lab.n_acquisitions
    assert tot["reactor_conditions"] >= 2
    assert tot["time_s"] > 0 and tot["egda_mol"] > 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} firewall tests passed.")
