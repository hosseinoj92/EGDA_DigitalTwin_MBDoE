"""Truth/inference firewall tests for the advanced system, exercised
through a miniature end-to-end strategy-F campaign.  Every assertion here is
a REAL invariant (the earlier `... or True` tautology is gone):

  * the virtual laboratory's truth is never revealed inside the loop;
  * no true parameter value appears in anything the controller receives;
  * the lab object and its hidden attributes are UNREACHABLE from the
    controller-side object graph (ensemble, posteriors, inferences);
  * the observation operator carries only assumed/commanded transfer
    knowledge, never the truth-side transfer configuration.
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
from sdl_advanced.model_ensemble import (AssumedTransfer, ModelEnsemble,
                                         build_egda_family)
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
# truth transfer DIFFERS from what the inference side is told (assumed):
TRANSFER_TRUTH = TransferConfig(enabled=True, Q_sample_mL_min=0.5,
                                V_fixed_mL=0.30, rtd="gamma", n_tanks=4.0,
                                n_quad=3, carryover=True)
ASSUMED = AssumedTransfer(enabled=True, Q_sample_mL_min=0.5,
                          V_fixed_mL=0.20)      # deliberately not the truth


def _mini_campaign(seed=0):
    bridge = Layer1Bridge(GEOM, T_REF_K)
    lab = AdvancedVirtualLaboratory(
        TRUTH, bridge,
        InstrumentConfig(observation_mode="nmr", nmr_mode="realistic"),
        AcquisitionSettings(n_points=2048),
        SpectralNuisance(),
        TRANSFER_TRUTH,
        ResourceCosts(), seed=seed)
    ens = ModelEnsemble(build_egda_family(
        GEOM, T_REF_K, include=("rev-dilute", "irreversible"),
        noise_assumed=NoiseModel(), assumed_transfer=ASSUMED))
    res = run_strategy_f(
        lab, ens, CANDS, CANDS[0],
        SpatialDesignConfig(mode="optimized", n_positions=3,
                            candidate_grid_size=21,
                            continuous_refinement=False),
        budget=2,
        design_cfg=AdvancedDesignConfig(top_k=2, n_particles=8, n_outer=8),
        governor=AdequacyGovernor(), seed=seed, verbose=False)
    return lab, ens, res


def _walk_floats(obj, seen=None):
    seen = seen if seen is not None else []
    if isinstance(obj, dict):
        for v in obj.values():
            _walk_floats(v, seen)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_floats(v, seen)
    elif isinstance(obj, float):
        seen.append(obj)
    return seen


def _reachable_objects(roots, max_objects=200_000):
    """All Python objects reachable from `roots` via attributes and
    containers (id-deduplicated graph walk)."""
    import collections
    seen = {}
    stack = list(roots)
    while stack and len(seen) < max_objects:
        o = stack.pop()
        if id(o) in seen:
            continue
        seen[id(o)] = o
        if isinstance(o, dict):
            stack.extend(o.keys())
            stack.extend(o.values())
        elif isinstance(o, (list, tuple, set, frozenset,
                            collections.deque)):
            stack.extend(o)
        if hasattr(o, "__dict__"):
            stack.append(o.__dict__)
        if hasattr(o, "__slots__"):
            for s in o.__slots__:
                if hasattr(o, s):
                    stack.append(getattr(o, s))
    return seen


def test_full_campaign_never_reveals_truth():
    lab, ens, res = _mini_campaign()
    assert lab.n_truth_reveals == 0
    assert lab.n_experiments_run >= 2
    assert len(res.history) == 2


def test_measurements_carry_no_truth_values():
    lab, ens, res = _mini_campaign(seed=1)
    truth_vals = set(TRUTH.values())
    for cm in ens.models:
        for m in cm.inference.measurements:
            meta = dict(m.meta or {})
            meta.pop("spectra", None)
            for v in _walk_floats(meta) + list(np.ravel(m.y)):
                assert not any(np.isclose(v, t, rtol=1e-12, atol=0.0)
                               for t in truth_vals), v


def test_lab_unreachable_from_controller_object_graph():
    """STRONG invariant: starting from everything the controller owns
    (ensemble, models, inferences, posteriors, result records), a full
    attribute/container graph walk must never reach the virtual laboratory,
    its hidden truth dict, or its truth-side transfer/nuisance objects."""
    lab, ens, res = _mini_campaign(seed=2)
    reach = _reachable_objects([ens, res.history])
    forbidden = {id(lab): "lab", id(lab._theta_true): "theta_true",
                 id(lab._transfer): "truth transfer line",
                 id(lab._nmr): "truth NMR simulator",
                 id(lab._nmr.nuisance): "truth nuisance config"}
    hit = [name for oid, name in forbidden.items() if oid in reach]
    assert not hit, f"controller graph reaches truth objects: {hit}"


def test_operator_holds_assumed_not_true_transfer():
    """The observation operator must be built from COMMANDED/ASSUMED
    transfer knowledge; the truth-side TransferConfig (different volume,
    RTD, carryover) must not leak into it."""
    lab, ens, res = _mini_campaign(seed=3)
    for cm in ens.models:
        at = cm.inference.assumed_transfer
        assert at.V_fixed_mL == ASSUMED.V_fixed_mL
        assert at.V_fixed_mL != TRANSFER_TRUTH.V_fixed_mL
        assert not hasattr(at, "n_tanks")     # no RTD knowledge at all
        assert not hasattr(cm.inference, "_theta_true")
    # and the estimate is not the hidden truth (it saw noise + mismatch)
    last = res.history[-1].theta_nat
    assert any(abs(last[k] / TRUTH[k] - 1.0) > 1e-9 for k in last
               if k in TRUTH)


def test_resources_accumulated_during_campaign():
    lab, ens, res = _mini_campaign(seed=4)
    tot = res.history[-1].resources
    assert tot["nmr_acquisitions"] == lab.n_acquisitions
    assert tot["reactor_conditions"] >= 1
    assert tot["time_s"] > 0 and tot["egda_mol"] > 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} firewall tests passed.")
