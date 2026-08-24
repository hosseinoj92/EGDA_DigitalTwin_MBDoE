"""Plug-flow validity over the WHOLE design envelope.

The defect these tests pin down: a geometry could pass the feasibility
screen at the nominal flow (1 mL/min) and then be used at 2, 4 or 8 mL/min,
where the same criterion fails by an order of magnitude.  The archived v5
publication run selected a 60 cm open tube on exactly that basis
(t_rad/tau = 8.8 at 1 mL/min, 70.7 at 8 mL/min).

Runnable standalone:  python tests/test_reactor_validity.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced import benchmark as bm
from sdl_advanced import reactor_validity as rv

OPEN_60 = {"length_m": 0.60, "diameter_m": 0.004}
OPEN_20 = {"length_m": 0.20, "diameter_m": 0.007}
PACKED_20 = {"length_m": 0.20, "diameter_m": 0.007,
             "packing_enabled": True, "bed_void_fraction": 0.40}
CRIT = rv.ValidityCriteria()


# ---- 1. the physics ------------------------------------------------------- #
def test_open_tube_ratio_is_linear_in_flow_and_bore_free():
    """t_rad/tau = Q/(pi D_m L eps): linear in flow, inverse in length,
    INDEPENDENT of bore - which is why a wider tube cannot rescue it."""
    r1 = rv.evaluate(OPEN_20, 1.0, CRIT)["t_rad_over_tau"]
    assert abs(rv.evaluate(OPEN_20, 2.0, CRIT)["t_rad_over_tau"]
               - 2.0 * r1) < 1e-9
    assert abs(rv.evaluate({**OPEN_20, "length_m": 0.4}, 1.0,
                           CRIT)["t_rad_over_tau"] - r1 / 2.0) < 1e-9
    assert abs(rv.evaluate({**OPEN_20, "diameter_m": 0.02}, 1.0,
                           CRIT)["t_rad_over_tau"] - r1) < 1e-12


def test_open_tube_bodenstein_approaches_48_over_the_radial_ratio():
    """Where the Taylor term dominates D_ax, Bo = uL/D_ax reduces to
    48/(t_rad/tau): the two criteria are ONE criterion, which is why no bore
    or length choice can satisfy the axial one while failing the radial one.

    The molecular term D_m only ever ADDS dispersion, so the product
    approaches 48 from below as the flow rises - it never exceeds it."""
    g = {"length_m": 0.20, "diameter_m": 0.006}
    prods = []
    for q in (0.002, 0.005, 0.010, 0.020, 0.035):
        row = rv.evaluate(g, q, CRIT)
        assert row["t_rad_over_tau"] <= 1.0      # Taylor-Aris applicable
        prods.append(row["bodenstein"] * row["t_rad_over_tau"])
    assert all(p <= 48.0 + 1e-9 for p in prods)
    assert prods == sorted(prods)                # monotone approach
    assert prods[-1] > 0.9 * 48.0                # and it does get there


def test_taylor_aris_bodenstein_is_not_reported_where_it_does_not_apply():
    """Outside the radially-mixed regime the Taylor-Aris D_ax is
    meaningless.  It must come back NaN and count as a FAILURE, never as a
    silent pass."""
    row = rv.evaluate(OPEN_20, 8.0, CRIT)
    assert not np.isfinite(row["bodenstein"])
    assert row["plug_flow_valid"] == 0
    assert "axial_dispersion" in row["failed_criteria"]


def test_packed_bed_is_checked_not_assumed():
    """REGRESSION: a packed bed used to return a radial ratio of exactly
    0.0, i.e. it was declared valid by fiat.  It must now be evaluated
    against the packed-bed dispersion criterion and get a FINITE ratio."""
    row = rv.evaluate(PACKED_20, 1.0, CRIT)
    assert row["t_rad_over_tau"] > 0.0
    assert np.isfinite(row["bodenstein"])
    assert row["plug_flow_valid"] == 1          # this bed IS admissible
    # ... and a bed that is too short for its beads is REFUSED
    short = {**PACKED_20, "length_m": 0.06, "diameter_m": 0.008}
    bad = rv.evaluate(short, 1.0, CRIT)
    assert bad["plug_flow_valid"] == 0
    assert "bed_aspect" in bad["failed_criteria"]


def test_declared_packed_ideality_is_labelled_as_an_assumption():
    crit = rv.ValidityCriteria(packed_plug_flow_assumed=True)
    row = rv.evaluate({**PACKED_20, "length_m": 0.01}, 8.0, crit)
    assert row["plug_flow_valid"] == 1
    assert "ASSUMED" in row["basis"]            # never presented as a check


# ---- 2. THE defect: nominal-flow feasibility is not feasibility ---------- #
def test_geometry_valid_at_nominal_flow_can_still_be_inadmissible():
    """The 60 cm open tube the v5 run selected: fine at 1 mL/min under the
    lenient radial threshold, badly outside it at 8 mL/min."""
    nominal = rv.evaluate(OPEN_60, 1.0, rv.ValidityCriteria(
        min_bodenstein=None))
    assert nominal["t_rad_over_tau"] < 10.0     # would have "passed"
    worst = rv.evaluate(OPEN_60, 8.0, CRIT)
    assert worst["t_rad_over_tau"] > 10.0       # but is segregated at 8
    assert not rv.is_feasible(OPEN_60, [0.5, 2.0, 8.0], CRIT)


def test_is_feasible_requires_every_flow():
    assert rv.is_feasible(PACKED_20, [0.5, 1.0, 2.0, 8.0], CRIT)
    assert rv.is_feasible(OPEN_60, [0.01], rv.ValidityCriteria(
        min_bodenstein=None))
    assert not rv.is_feasible(OPEN_60, [0.01, 8.0], rv.ValidityCriteria(
        min_bodenstein=None))


def test_worst_row_is_the_flow_that_decides():
    w = rv.worst_row(OPEN_60, [0.5, 2.0, 8.0], CRIT)
    assert w["Q_total_mL_min"] == 8.0


# ---- 3. guidance rather than a bare refusal ------------------------------ #
def test_explain_names_the_bounds_that_would_have_to_change():
    msg = rv.explain(OPEN_60, [0.5, 2.0, 8.0], CRIT)
    assert "FAILS" in msg
    for hint in ("flow bound", "reactor length", "PACK the tube"):
        assert hint in msg, hint
    assert "8" in msg                            # the worst flow is named
    ok = rv.explain(PACKED_20, [0.5, 2.0, 8.0], CRIT)
    assert "valid at all" in ok


def test_recommended_limits_are_self_consistent():
    """The numbers `explain` quotes must actually be admissible."""
    q_max = rv.max_admissible_flow_mL_min(OPEN_60, CRIT)
    assert rv.evaluate(OPEN_60, q_max * 0.99, CRIT)["plug_flow_valid"]
    assert not rv.evaluate(OPEN_60, q_max * 1.5, CRIT)["plug_flow_valid"]
    l_min = rv.min_admissible_length_m(OPEN_60, 8.0, CRIT)
    assert rv.evaluate({**OPEN_60, "length_m": l_min * 1.01}, 8.0,
                       CRIT)["plug_flow_valid"]


# ---- 4. the framework applies it everywhere ------------------------------ #
def _restore(before):
    bm.apply_config(before)
    bm.invalidate_caches()


def test_permitted_flows_cover_the_declared_design_space():
    before = bm.resolved_config()
    try:
        bm.apply_config({"DESIGN": {"Q_total_mL_min_levels": [0.5, 2.0, 8.0]},
                         "FEATURES": {"continuous_design_space": False}})
        assert set(bm.permitted_flows()) >= {0.5, 2.0, 8.0}
        # continuous mode may sit anywhere between the bounds, so the BOUNDS
        # have to be checked too - both criteria are monotone in Q
        bm.apply_config({"FEATURES": {"continuous_design_space": True},
                         "DESIGN": {"continuous_bounds":
                                    {"Q_total_mL_min": [0.2, 12.0]}}})
        assert min(bm.permitted_flows()) <= 0.2
        assert max(bm.permitted_flows()) >= 12.0
    finally:
        _restore(before)


def test_sizing_rejects_every_open_tube_over_the_flow_envelope():
    """The headline regression: with the criterion applied at every
    permitted flow, no OPEN tube in the declared bounds survives, and the
    optimizer must not fall back on one."""
    before = bm.resolved_config()
    try:
        bm.apply_config({"FEATURES": {"geometry_optimization": True,
                                      "packed_bed_reactor": True}})
        bm.invalidate_caches()
        rows = bm.geometry_sizing_table(6)
        assert rows
        assert all(not r["feasible"] for r in rows if not r["packed"]), \
            "an open tube was declared feasible over the full flow envelope"
        chosen = [r for r in rows if r["selected"]]
        assert len(chosen) == 1 and chosen[0]["feasible"]
        assert chosen[0]["packed"] == 1
        # and the selected reactor is valid at EVERY permitted flow
        g = bm.active_geometry(6)
        assert rv.is_feasible(g, bm.permitted_flows(), bm.validity_criteria())
    finally:
        _restore(before)


def test_a_geometry_cannot_pass_sizing_then_be_used_at_an_invalid_flow():
    """THE test the review asked for.  Pin the reactor to one that is
    admissible at the nominal flow only, then confirm the framework refuses
    to RUN it - the gate lives in active_geometry/make_lab, so no path
    reaches a campaign with an inadmissible reactor."""
    before = bm.resolved_config()
    try:
        # a 60 cm open tube: admissible at 1 mL/min under the lenient
        # radial-only criterion, and nowhere near admissible at 8
        bm.apply_config({
            "FEATURES": {"geometry_optimization": False,
                         "packed_bed_reactor": False,
                         "reactor_validity_enforcement": True,
                         "axial_dispersion_criterion": False},
            "GEOMETRY": {"length_m": 0.60, "diameter_m": 0.004},
            "DESIGN": {"Q_total_mL_min_levels": [1.0]}})
        bm.invalidate_caches()
        assert bm.active_geometry(4)["length_m"] == 0.60   # admissible at 1
        # now the design space is allowed to command 8 mL/min - the SAME
        # reactor must stop being admissible, and every entry point must say
        # so rather than quietly running it
        bm.apply_config({"DESIGN": {"Q_total_mL_min_levels": [1.0, 8.0]}})
        bm.invalidate_caches()
        for call in (lambda: bm.active_geometry(4),
                     lambda: bm.make_lab(bm.SCENARIOS["S1_ideal"], 0),
                     lambda: bm.assert_reactor_validity()):
            try:
                call()
            except ValueError as exc:
                assert "PLUG-FLOW VALIDITY" in str(exc)
                assert "flow bound" in str(exc)     # guidance, not a refusal
            else:
                raise AssertionError(
                    "an inadmissible reactor was accepted at 8 mL/min")
    finally:
        _restore(before)


def test_enforcement_can_be_declared_off_but_is_still_reported():
    before = bm.resolved_config()
    try:
        bm.apply_config({
            "FEATURES": {"geometry_optimization": False,
                         "packed_bed_reactor": False,
                         "reactor_validity_enforcement": False},
            "GEOMETRY": {"length_m": 0.20, "diameter_m": 0.007}})
        bm.invalidate_caches()
        rows = bm.assert_reactor_validity()          # must not raise
        assert rows and any(not r["plug_flow_valid"] for r in rows)
    finally:
        _restore(before)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} reactor-validity tests passed.")
