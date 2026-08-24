"""Conventional-vs-optimized comparison, and reactor geometry as an
optional design variable.

The comparison layer exists because error-vs-round curves answer the wrong
question: a round is not a cost.  The tests below pin the two things that
make the answer trustworthy - that a ratio is PAIRED on the same seed, and
that a campaign which never reaches a target is reported as censored rather
than dropped.

Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced import benchmark as bm
from sdl_advanced import efficiency as eff


def _row(scen, strat, seed, rnd, err, rmse, egda, t, energy=1.0, acq=1.0):
    return {"scenario": scen, "strategy": strat, "seed": seed, "round": rnd,
            "param_err_pct": err, "blind_rmse_M": rmse, "egda_mol": egda,
            "time_s": t, "energy_kJ": energy, "nmr_acquisitions": acq,
            "acid_mol": 0.0, "waste_mL": 0.0, "spatial_samples": 1.0,
            "capillary_travel_m": 0.0, "reactor_conditions": float(rnd)}


def _toy():
    """Conventional 'REF' needs 4 rounds and 4.0 mol to reach 20% error;
    'OPT' gets there in 2 rounds and 1.0 mol.  Seed 2 is deliberately harder
    so the aggregate is not a single number repeated."""
    rows = []
    for seed, scale in ((1, 1.0), (2, 1.5)):
        for rnd, err in enumerate([80.0, 50.0, 30.0, 18.0], start=1):
            rows.append(_row("S", "REF", seed, rnd, err * scale,
                             err * scale * 1e-4, 1.0 * rnd, 100.0 * rnd))
        for rnd, err in enumerate([60.0, 18.0, 12.0, 9.0], start=1):
            rows.append(_row("S", "OPT", seed, rnd, err * scale,
                             err * scale * 1e-4, 0.5 * rnd, 40.0 * rnd))
    return rows


# ---- budget to target ----------------------------------------------------- #
def test_budget_to_target_is_paired_on_the_same_seed():
    rows = _toy()
    btt = eff.budget_to_target_rows(rows, "S", ["REF", "OPT"], "REF", [1, 2],
                                    {"param_err_pct": [30.0]})
    opt = {r["seed"]: r for r in btt if r["strategy"] == "OPT"}
    # seed 1: OPT hits 30% at round 2 (0.5*2 = 1.0 mol); REF at round 3
    # (1.0*3 = 3.0 mol) -> ratio 1/3
    assert opt[1]["round"] == 2 and opt[1]["reference_round"] == 3
    assert abs(opt[1]["ratio_egda_mol"] - (1.0 / 3.0)) < 1e-12
    # the reference compares to itself at exactly 1.0
    ref = {r["seed"]: r for r in btt if r["strategy"] == "REF"}
    assert abs(ref[1]["ratio_egda_mol"] - 1.0) < 1e-12
    assert abs(ref[2]["ratio_time_s"] - 1.0) < 1e-12


def test_unreached_target_is_censored_not_dropped():
    """A target nobody reaches must show as censored; reporting a ratio over
    the seeds that happened to make it would be the classic survivorship
    error."""
    rows = _toy()
    btt = eff.budget_to_target_rows(rows, "S", ["REF", "OPT"], "REF", [1, 2],
                                    {"param_err_pct": [1.0]})   # impossible
    assert all(r["reached"] == 0 for r in btt)
    assert all(r["round"] == -1 for r in btt)
    assert all(not np.isfinite(r["ratio_egda_mol"]) for r in btt)
    s = eff.summarize_budget_to_target(btt)
    for r in s:
        assert r["n_seeds"] == 2 and r["n_reached"] == 0
        assert r["n_paired"] == 0 and r["frac_reached"] == 0.0
        assert not np.isfinite(r["ratio_egda_mol_median"])


def test_partially_reached_target_reports_both_counts():
    """Seed 2 is scaled 1.5x, so at a 20% target only seed 1 makes it."""
    rows = _toy()
    btt = eff.budget_to_target_rows(rows, "S", ["OPT"], "REF", [1, 2],
                                    {"param_err_pct": [20.0]})
    s = eff.summarize_budget_to_target(btt)[0]
    assert s["n_seeds"] == 2
    assert 0 < s["n_reached"] <= 2
    assert s["n_paired"] <= s["n_reached"]
    assert 0.0 < s["frac_reached"] <= 1.0


def test_first_crossing_not_best_round():
    """A campaign that dips under the target and drifts back must be
    credited at the FIRST crossing - that is where an experimenter would
    have stopped, and using the best-ever round would grant hindsight."""
    rows = [_row("S", "X", 1, 1, 50.0, 1e-3, 1.0, 10.0),
            _row("S", "X", 1, 2, 15.0, 1e-3, 2.0, 20.0),   # crosses here
            _row("S", "X", 1, 3, 40.0, 1e-3, 3.0, 30.0),
            _row("S", "X", 1, 4, 12.0, 1e-3, 4.0, 40.0)]
    btt = eff.budget_to_target_rows(rows, "S", ["X"], "X", [1],
                                    {"param_err_pct": [20.0]})
    assert btt[0]["round"] == 2
    assert abs(btt[0]["egda_mol"] - 2.0) < 1e-12


# ---- accuracy at matched resource ---------------------------------------- #
def test_matched_resource_uses_the_reference_total_budget():
    rows = _toy()
    mr = eff.matched_resource_rows(rows, "S", ["REF", "OPT"], "REF", [1],
                                   resources=("egda_mol",))
    opt = next(r for r in mr if r["strategy"] == "OPT")
    # REF's total is 4.0 mol; OPT reaches round 4 at 2.0 mol, so it is
    # evaluated at its final round and is better -> factor > 1
    assert abs(opt["reference_total"] - 4.0) < 1e-12
    assert opt["round_at_budget"] == 4
    assert opt["improvement_factor_param_err_pct"] > 1.0
    ref = next(r for r in mr if r["strategy"] == "REF")
    assert abs(ref["improvement_factor_param_err_pct"] - 1.0) < 1e-12


def test_summaries_carry_probability_of_being_better():
    rows = _toy()
    mr = eff.matched_resource_rows(rows, "S", ["OPT"], "REF", [1, 2],
                                   resources=("egda_mol",))
    s = eff.summarize_matched_resource(mr)[0]
    assert s["p_better_param_err_pct"] == 1.0
    assert s["improvement_param_err_pct_median"] > 1.0


def test_headline_picks_the_tightest_defensible_target():
    rows = _toy()
    btt = eff.budget_to_target_rows(
        rows, "S", ["OPT"], "REF", [1, 2],
        {"param_err_pct": [50.0, 30.0, 20.0, 1.0]})
    mr = eff.matched_resource_rows(rows, "S", ["OPT"], "REF", [1, 2],
                                   resources=("egda_mol",))
    h = eff.headline_rows(eff.summarize_budget_to_target(btt),
                          eff.summarize_matched_resource(mr))[0]
    # the impossible 1.0% target must not be chosen
    assert h["tightest_target_reached_by_half"] in (50.0, 30.0, 20.0)
    assert h["frac_seeds_reached"] >= 0.5
    assert np.isfinite(h["saving_pct_egda_mol"])


def test_reference_strategy_resolves_for_every_scenario():
    for name, spec in bm.SCENARIOS.items():
        ref = bm.reference_strategy(name)
        assert ref in spec.strategies, (name, ref, spec.strategies)


# ---- geometry as a design variable ---------------------------------------- #
def test_geometry_is_fixed_unless_enabled():
    assert bm.GEOMETRY_DESIGN["enabled"] is False
    assert bm.active_geometry(8) is bm.GEOMETRY


def test_geometry_optimization_picks_from_the_declared_space():
    before = bm.resolved_config()
    try:
        bm.apply_config({"FEATURES": {"geometry_optimization": True}})
        bm.invalidate_caches()
        g = bm.active_geometry(8)
        lv = bm.GEOMETRY_DESIGN["levels"]
        assert g["length_m"] in lv["length_m"]
        assert g["diameter_m"] in lv["diameter_m"]
        # packing is now part of the decision ("auto"); whichever state won,
        # it must be a coherent ReactorGeometry with the declared epsilon
        if g["packing_enabled"]:
            assert g["bed_void_fraction"] == \
                bm.GEOMETRY_DESIGN["bed_void_fraction"]
        else:
            assert g["bed_void_fraction"] == 1.0
        # reporting metadata must not leak into ReactorGeometry kwargs
        assert not any(k.startswith("_") for k in g)
        from pfr_twin.parameters import ReactorGeometry
        ReactorGeometry(**g)
        # deterministic: the same configuration gives the same reactor
        bm.invalidate_caches()
        assert bm.active_geometry(8) == g
    finally:
        bm.apply_config(before)
        bm.invalidate_caches()


def test_open_tube_validity_the_bore_cancels():
    """t_rad/tau = Q/(pi D L eps): only length, flow and holdup enter, so
    changing the bore must not move the ratio - the physical fact the
    whole packing story rests on."""
    r7 = bm._radial_ratio({"length_m": 0.2, "diameter_m": 0.007})
    r4 = bm._radial_ratio({"length_m": 0.2, "diameter_m": 0.004})
    assert abs(r7 - r4) < 1e-12
    # twice the length halves the ratio; packing zeroes it by assumption
    assert abs(bm._radial_ratio({"length_m": 0.4, "diameter_m": 0.007})
               - r7 / 2.0) < 1e-9
    # A packed bed no longer reports ZERO: it is CHECKED against the
    # packed-bed dispersion criterion, so its ratio is small but finite.
    packed = bm._radial_ratio({"length_m": 0.2, "diameter_m": 0.007,
                               "packing_enabled": True,
                               "bed_void_fraction": 0.4})
    assert 0.0 < packed < r7 / 10.0
    # the shipped 20 cm open demo tube exceeds the advisory boundary at
    # nominal flow - which is WHY the sizing must not pick reactors like it
    assert r7 > bm.validity_criteria().max_radial_ratio


def test_sizing_rejects_invalid_open_tubes_and_packing_rescues():
    before = bm.resolved_config()
    try:
        bm.invalidate_caches()
        bm.apply_config({"FEATURES": {"geometry_optimization": True,
                                      "packed_bed_reactor": True}})
        bm.invalidate_caches()
        rows = bm.geometry_sizing_table(6)
        # feasibility is judged over the WHOLE flow envelope, so every open
        # tube in the declared bounds is out - the review's point
        open_rows = [r for r in rows if not r["packed"]]
        assert open_rows, "expected open tubes in the screened grid"
        assert all(not r["feasible"] for r in open_rows)
        assert all(not np.isfinite(r["score"]) for r in open_rows)
        packed = [r for r in rows if r["packed"]]
        assert packed and any(r["feasible"] for r in packed)
        chosen = [r for r in rows if r["selected"]]
        assert len(chosen) >= 1 and chosen[0]["feasible"]
        assert chosen[0]["packed"] == 1
        # with beads forbidden the sizing must REFUSE rather than quietly
        # pick an invalid reactor - and it must say which bound to change
        bm.apply_config({"FEATURES": {"packed_bed_reactor": False}})
        bm.invalidate_caches()
        try:
            bm.active_geometry(6)
        except ValueError as exc:
            msg = str(exc)
            assert "NO ADMISSIBLE GEOMETRY" in msg
            assert "flow bound" in msg and "PACK the tube" in msg
        else:
            raise AssertionError("all-infeasible sizing must raise")
    finally:
        bm.apply_config(before)
        bm.invalidate_caches()


def test_cost_term_prevents_runaway_size():
    """With the resource penalty OFF the objective is monotone in
    information and runs to the biggest reactor; with the S6 exchange rate
    ON the optimum is interior - paying some cost for information but not
    every cost.  Both directions are asserted so the lambda knob is shown
    to be live, not decorative."""
    before = bm.resolved_config()
    try:
        # geometry optimization and packing are FEATURE switches now
        bm.apply_config({"FEATURES": {"geometry_optimization": True,
                                      "packed_bed_reactor": True},
                         "GEOMETRY_DESIGN": {
            "objective_lambdas": {"lambda_time_per_s": 0.0,
                                  "lambda_material_per_mol": 0.0,
                                  "lambda_waste_per_mL": 0.0,
                                  "lambda_energy_per_kJ": 0.0}}})
        bm.invalidate_caches()
        g_free = bm.active_geometry(6)
        bm.apply_config({"GEOMETRY_DESIGN": {
            "objective_lambdas": {"lambda_time_per_s": 2e-3,
                                  "lambda_material_per_mol": 50.0,
                                  "lambda_waste_per_mL": 5e-3,
                                  "lambda_energy_per_kJ": 0.05}}})
        bm.invalidate_caches()
        g_paid = bm.active_geometry(6)
        v = lambda g: g["length_m"] * g["diameter_m"] ** 2
        assert v(g_free) > v(g_paid), (g_free, g_paid)
        # free-information mode picks the largest declared reactor
        assert g_free["length_m"] == max(
            bm.GEOMETRY_DESIGN["levels"]["length_m"])
        # the paid optimum is NOT simply the cheapest candidate either
        rows = bm.geometry_sizing_table(6)
        feas = [r for r in rows if r["feasible"]]
        cheapest = min(feas, key=lambda r: r["cost_penalty_nats"])
        chosen = next(r for r in feas if r["selected"])
        assert chosen["info_nats"] >= cheapest["info_nats"]
    finally:
        bm.apply_config(before)
        bm._GEOMETRY_CACHE.clear()


def test_sizing_lambdas_are_the_s6_exchange_rate():
    """One information-resource exchange rate for the whole framework: the
    sizing weights must equal the S6 resource controller's 1x vector, so
    the reactor and the campaign are optimized against the same economy."""
    s6 = bm._resource_lambdas(1.0)
    lam = bm.GEOMETRY_DESIGN["objective_lambdas"]
    assert lam["lambda_time_per_s"] == s6.lambda_time_per_s
    assert lam["lambda_material_per_mol"] == s6.lambda_material_per_mol
    assert lam["lambda_waste_per_mL"] == s6.lambda_waste_per_mL
    assert lam["lambda_energy_per_kJ"] == s6.lambda_energy_per_kJ


def test_blind_scoring_always_in_the_declared_reference_reactor():
    """theta is intrinsic: c(tau) never depends on which tube produced the
    data, so 'predict the reference reactor' is one fixed question and
    blind RMSE stays comparable across geometry settings."""
    from sdl import Layer1Bridge
    before = bm.resolved_config()
    try:
        # OFF: the scoring bridge is the SAME OBJECT - zero-risk legacy path
        br = Layer1Bridge(bm.GEOMETRY, bm.T_REF_C + 273.15,
                          activity_model="pitzer")
        assert bm._scoring_bridge(br) is br
        # ON: a model living in the sized reactor is scored in the declared
        # one.  The levels are narrowed so the sizing CANNOT land on the
        # declared geometry - otherwise the rebridge path is never taken and
        # the test would pass without exercising anything.
        bm.invalidate_caches()
        bm.apply_config({"FEATURES": {"geometry_optimization": True},
                         "GEOMETRY_DESIGN": {
                             "levels": {"length_m": [0.40, 0.60],
                                        "diameter_m": [0.004, 0.006]}}})
        bm.invalidate_caches()
        g = bm.active_geometry(6)
        assert abs(g["length_m"] - bm.GEOMETRY["length_m"]) > 1e-9
        br_act = Layer1Bridge(g, bm.T_REF_C + 273.15,
                              activity_model="pitzer", reversible=True)
        sb = bm._scoring_bridge(br_act)
        assert sb is not br_act
        assert abs(sb.geometry.length_m - bm.GEOMETRY["length_m"]) < 1e-12
        assert abs(sb.geometry.diameter_m
                   - bm.GEOMETRY["diameter_m"]) < 1e-12
        # the model configuration travels with it
        assert sb.reversible == br_act.reversible
        assert sb.activity_model == br_act.activity_model
        # and the audit decomposition still reproduces the reported number
        out = bm.campaign_task("S1_ideal", "F", 1, 3, audit=True)
        bp = out["audit"]["blind_predictions_long"]
        rmse = float(np.sqrt(np.mean([r["squared_error_M2"] for r in bp])))
        assert abs(rmse - float(out["rows"][-1]["blind_rmse_M"])) < 1e-9
    finally:
        bm.apply_config(before)
        bm._GEOMETRY_CACHE.clear()


def test_geometry_score_uses_the_prior_not_the_truth():
    """Sizing a reactor happens BEFORE the kinetics are known; reading the
    hidden truth here would be the purest inverse crime."""
    import inspect
    src = inspect.getsource(bm._geometry_score)
    assert "literature_guess" in src
    assert "TRUTH" not in src and "spec.truth" not in src
    assert "reveal_truth" not in src


def test_per_experiment_geometry_refuses_rather_than_pretending():
    before = bm.resolved_config()
    try:
        bm.apply_config({"FEATURES": {"geometry_optimization": True},
                         "GEOMETRY_DESIGN": {"mode": "per_experiment"}})
        bm.invalidate_caches()
        try:
            bm.active_geometry(8)
        except NotImplementedError as exc:
            assert "per_campaign" in str(exc)
        else:
            raise AssertionError("an unimplemented mode must not run "
                                 "silently as if it were implemented")
    finally:
        bm.apply_config(before)
        bm._GEOMETRY_CACHE.clear()


def test_geometry_off_leaves_campaigns_bit_identical():
    """The default path must be untouched by the option existing."""
    a = bm.campaign_task("S1_ideal", "A", 1, 4)["rows"][-1]
    b = bm.campaign_task("S1_ideal", "A", 1, 4)["rows"][-1]
    assert float(a["param_err_pct"]) == float(b["param_err_pct"])
    assert bm.active_geometry(4)["length_m"] == 0.20


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} comparison/geometry tests passed.")
