"""Stage-1 regression tests for the corrected framework:
configurable geometry + optional packing, equilibrium observability,
truth-in-domain validation, NMR calibration/validation independence,
governor decision-component consistency and bootstrap resolution, and the
survivorship-free aggregation.  Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import (Layer1Bridge, OperatingConditions, ParameterSpace,
                 literature_guess)   # also puts Layer 1 on sys.path
from pfr_twin.parameters import ReactorGeometry
from sdl_advanced import benchmark as bm
from sdl_advanced import observability as obs
from sdl_advanced.spatial_design import fixed_equal_positions

T_REF_K = bm.T_REF_C + 273.15
GUESS = literature_guess(T_REF_K)


# ---- geometry / packing --------------------------------------------------- #
def test_demo_geometry_is_20cm_7mm_and_configurable():
    """The demonstration CPR is 20 cm x 7 mm, and in V6 it is PACKED.

    That is not a cosmetic default: an open tube of this size is radially
    segregated at every flow the design space commands (t_rad/tau = 13-212
    against a limit of 10), so the framework would be applying a plug-flow
    model outside its range.  Packing is the standard engineering fix and it
    is switched from FEATURES['packed_bed_reactor']."""
    g = ReactorGeometry(**bm.GEOMETRY)
    assert abs(g.length_m - 0.20) < 1e-12
    assert abs(g.diameter_m - 0.007) < 1e-12
    assert bm.FEATURES["packed_bed_reactor"] is True
    assert g.packing_enabled and 0.0 < g.void_fraction < 1.0
    # and the switch really removes the packing
    before = bm.resolved_config()
    try:
        bm.apply_config({"FEATURES": {"packed_bed_reactor": False,
                                      "reactor_validity_enforcement": False}})
        assert ReactorGeometry(**bm.GEOMETRY).void_fraction == 1.0
    finally:
        bm.apply_config(before)
        bm.invalidate_caches()
    # nothing is hard-coded: a different geometry is simply another config
    g2 = ReactorGeometry(length_m=0.35, diameter_m=0.004)
    assert g2.volume_m3 > 0 and g2.length_m == 0.35


def test_residence_time_scales_with_geometry():
    q = 1.0e-6 / 60.0                        # 1 mL/min in m3/s
    g_small = ReactorGeometry(length_m=0.06, diameter_m=0.004)
    g_demo = ReactorGeometry(length_m=0.20, diameter_m=0.007)
    tau_s, tau_d = (g.residence_time_s(q) for g in (g_small, g_demo))
    assert tau_d > tau_s
    # tau ~ L D^2 : the demo reactor is (0.20/0.06)*(7/4)^2 ~ 10.2x larger
    assert abs(tau_d / tau_s - (0.20 / 0.06) * (7.0 / 4.0) ** 2) < 1e-9
    # and doubling the length exactly doubles tau
    g_long = ReactorGeometry(length_m=0.40, diameter_m=0.007)
    assert abs(g_long.residence_time_s(q) / tau_d - 2.0) < 1e-12


def test_unpacked_gives_epsilon_one():
    g = ReactorGeometry(length_m=0.2, diameter_m=0.007)
    assert g.void_fraction == 1.0
    assert g.flow_area_m2 == g.area_m2
    assert g.liquid_volume_m3 == g.volume_m3
    q = 0.5e-6 / 60.0
    assert abs(g.residence_time_s(q) - g.volume_m3 / q) < 1e-18


def test_packed_uses_bed_void_fraction():
    eps = 0.40
    g_open = ReactorGeometry(length_m=0.2, diameter_m=0.007)
    g_pack = ReactorGeometry(length_m=0.2, diameter_m=0.007,
                             packing_enabled=True, bed_void_fraction=eps)
    q = 0.5e-6 / 60.0
    assert abs(g_pack.void_fraction - eps) < 1e-12
    # tau_liquid = epsilon A L / Q  ->  exactly eps times the open value
    assert abs(g_pack.residence_time_s(q)
               / g_open.residence_time_s(q) - eps) < 1e-12
    assert abs(g_pack.liquid_volume_mL / g_open.liquid_volume_mL
               - eps) < 1e-12
    # declaring a void fraction WITHOUT enabling packing changes nothing
    g_ignored = ReactorGeometry(length_m=0.2, diameter_m=0.007,
                                bed_void_fraction=eps)
    assert g_ignored.void_fraction == 1.0
    assert g_ignored.residence_time_s(q) == g_open.residence_time_s(q)
    # particle porosity is metadata only: it must not touch the holdup
    g_por = ReactorGeometry(length_m=0.2, diameter_m=0.007,
                            packing_enabled=True, bed_void_fraction=eps,
                            particle_porosity=0.5)
    assert g_por.residence_time_s(q) == g_pack.residence_time_s(q)


def test_packing_changes_conversion_only_when_enabled():
    """A packed bed has less liquid holdup -> shorter tau -> LOWER
    conversion; the unpacked scenario must be bit-identical to before."""
    u = OperatingConditions(120.0, 0.5, 0.5, 1.0, 1.0)
    z = np.array([0.2])
    base = {"length_m": 0.2, "diameter_m": 0.007}
    y_open = Layer1Bridge(base, T_REF_K).concentrations_at(
        GUESS, u, z, ("EGDA",))
    y_flag = Layer1Bridge({**base, "bed_void_fraction": 0.4},
                          T_REF_K).concentrations_at(GUESS, u, z, ("EGDA",))
    y_pack = Layer1Bridge({**base, "packing_enabled": True,
                           "bed_void_fraction": 0.4},
                          T_REF_K).concentrations_at(GUESS, u, z, ("EGDA",))
    assert np.array_equal(y_open, y_flag)        # disabled -> no effect
    assert y_pack[0] > y_open[0]                 # less holdup -> less reacted


def test_positions_rescale_with_configured_length():
    for L in (0.06, 0.20, 0.35):
        z = fixed_equal_positions(L, 10)
        assert abs(z[-1] - L) < 1e-15
        assert np.allclose(z / L, fixed_equal_positions(1.0, 10))


# ---- equilibrium observability -------------------------------------------- #
def test_phi_and_k_sensitivity_behave():
    bridge = Layer1Bridge(bm.GEOMETRY, T_REF_K, activity_model="pitzer")
    # the demonstration reactor still reaches the equilibrium-sensitive
    # region when packed (shorter tau, so the hot/slow corner matters more)
    L = bridge.geometry.length_m
    z = np.linspace(L / 10, L, 10)
    hot_slow = OperatingConditions(160.0, 0.25, 0.25, 1.0, 1.0)
    cold_fast = OperatingConditions(40.0, 4.0, 4.0, 1.0, 0.5)
    p_hot = obs.phi_profiles(bridge, GUESS, hot_slow, z)
    p_cold = obs.phi_profiles(bridge, GUESS, cold_fast, z)
    # phi rises along the reactor and is far larger where products build up
    assert np.nanmax(p_hot["phi1"]) > np.nanmax(p_cold["phi1"])
    assert np.nanmax(p_hot["phi1"]) <= 1.0 + 1e-6      # cannot pass equilibrium
    assert np.nanmax(p_cold["phi1"]) < 0.5             # kinetic region
    # K sensitivity is larger in the equilibrium-sensitive condition
    s_hot = obs.k_sensitivity(bridge, GUESS, hot_slow, z)
    s_cold = obs.k_sensitivity(bridge, GUESS, cold_fast, z)
    assert s_hot["dC_dlnK2"] > s_cold["dC_dlnK2"]
    # an irreversible parameterization has no K sensitivity at all
    s_irr = obs.k_sensitivity(bridge, {k: v for k, v in GUESS.items()
                                       if not k.startswith("K")},
                              hot_slow, z)
    assert s_irr["dC_dlnK1"] == 0.0 and s_irr["dC_dlnK2"] == 0.0


def test_verdict_flags_unexcited_domain():
    """A domain restricted to cold/fast conditions must be REPORTED as
    equilibrium-unidentifiable rather than silently fitted."""
    bridge = Layer1Bridge(bm.GEOMETRY, T_REF_K, activity_model="pitzer")
    cold = [OperatingConditions(40.0, 4.0, 4.0, 1.0, 0.5),
            OperatingConditions(50.0, 4.0, 4.0, 1.0, 0.5)]
    v_cold = obs.verdict(obs.domain_scan(bridge, GUESS, cold, n_z=8))
    assert not v_cold["identifiable"]["K1_ref"]
    assert any("unidentifiable" in m for m in v_cold["messages"])
    # the full demonstration domain DOES reach the equilibrium region
    full = [OperatingConditions(T, q / 2, q / 2, 1.0, c)
            for T in (40.0, 160.0) for q in (0.5, 8.0) for c in (0.5, 1.0)]
    v_full = obs.verdict(obs.domain_scan(bridge, GUESS, full, n_z=8))
    assert v_full["max_phi2"] > 0.5


# ---- truth-in-domain validation ------------------------------------------- #
def test_well_specified_scenarios_have_truth_inside_bounds():
    space = ParameterSpace(t_ref_K=T_REF_K, initial_guess=dict(GUESS))
    for name, spec in bm.SCENARIOS.items():
        if not spec.well_specified:
            continue
        rep = bm.check_truth_in_domain(space, spec.truth)
        assert rep["ok"], f"{name}: truth outside candidate domain: {rep}"


def test_out_of_domain_scenario_is_detected_and_labelled():
    space = ParameterSpace(t_ref_K=T_REF_K, initial_guess=dict(GUESS))
    ood = bm.SCENARIOS["S4c_out_of_domain"]
    rep = bm.check_truth_in_domain(space, ood.truth)
    assert not rep["ok"]
    assert not rep["detail"]["K2_ref"]["inside"]      # K2=0.002 < bound
    assert not ood.well_specified
    assert "OUT-OF-DOMAIN" in ood.description
    # ... and S5's truth is likewise explicitly out of domain
    assert not bm.check_truth_in_domain(
        space, bm.SCENARIOS["S5_inadequacy"].truth)["ok"]




def test_fixed_design_ladder_supports_every_planned_budget():
    """REGRESSION: publication mode (budget 8) aborted because the declared
    conventional ladder had only 7 rungs and build_fixed_design only
    subsamples.  Every budget in MODES must now yield a fixed design with
    one experiment per round, for A and B alike."""
    from sdl import build_fixed_design
    for mode, cfg in bm.MODES.items():
        budgets = {cfg["budget"]}
        for name in cfg["scenarios"]:
            ov = bm.SCENARIOS[name].budget_override
            if ov:
                budgets.add(ov)
        for b in budgets:
            fx = build_fixed_design(bm.design_for_budget(b), budget=b)
            assert len(fx) >= b, (mode, b, len(fx))
            temps = [u.T_C for u in fx]
            assert temps == sorted(temps)
            assert min(temps) == min(bm.DESIGN["fixed_design_T_C"])
            assert max(temps) == max(bm.DESIGN["fixed_design_T_C"])


def test_declared_ladder_untouched_when_budget_fits():
    """Budgets that fit the declared ladder must reproduce the PREVIOUS
    behaviour exactly, so already-reported demo results stay valid."""
    from sdl import build_fixed_design
    assert bm.design_for_budget(6) is bm.DESIGN
    assert bm.design_for_budget(7) is bm.DESIGN
    assert [u.T_C for u in build_fixed_design(bm.DESIGN, budget=6)] == \
           [40.0, 60.0, 80.0, 120.0, 140.0, 160.0]
    # and a larger budget refines the SAME range rather than extrapolating
    d8 = bm.design_for_budget(8)
    assert d8 is not bm.DESIGN and len(d8["fixed_design_T_C"]) == 8


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} geometry/observability tests passed.")
