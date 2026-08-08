"""Tests of resource accounting (sdl_advanced.resources).
Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced.resources import ResourceCosts, ResourceMeter


def _meter():
    return ResourceMeter(ResourceCosts(), reactor_volume_mL=15.0)


def test_totals_nonnegative_and_auditable():
    """Acceptance criterion 13: totals are nonnegative and re-derivable from
    the event history."""
    m = _meter()
    m.log_condition(80.0, 2.0, 1.0, 0.5)
    for z in (0.1, 0.3, 0.5):
        m.log_acquisition(z, 80.0, 2.0, 1.0, 0.5)
    m.log_condition(60.0, 1.0, 0.5, 0.5)
    m.log_acquisition(0.5, 60.0, 1.0, 0.5, 0.5)
    tot = m.totals()
    for k, v in tot.items():
        assert v >= 0.0, (k, v)
    # audit: recompute every total from the raw events
    audit = {}
    for ev in m.events:
        for k, v in ev.quantities.items():
            audit[k] = audit.get(k, 0.0) + v
    for k, v in audit.items():
        assert np.isclose(tot[k], v), k
    assert tot["nmr_acquisitions"] == 4
    assert tot["reactor_conditions"] == 2
    assert tot["temperature_changes"] == 1


def test_capillary_travel_is_sum_of_moves():
    m = _meter()
    m.log_condition(80.0, 2.0, 1.0, 0.5)
    zs = [0.1, 0.5, 0.2, 0.45]
    for z in zs:
        m.log_acquisition(z, 80.0, 2.0, 1.0, 0.5)
    expected = sum(abs(b - a) for a, b in zip(zs[:-1], zs[1:]))
    assert np.isclose(m.totals()["capillary_travel_m"], expected)


def test_candidate_cost_penalizes_motion_and_switches():
    costs = ResourceCosts(lambda_motion_per_m=10.0, lambda_switch=5.0,
                          lambda_time_per_s=0.0)
    m = ResourceMeter(costs, reactor_volume_mL=15.0)
    m.log_condition(80.0, 2.0, 1.0, 0.5)
    m.log_acquisition(0.5, 80.0, 2.0, 1.0, 0.5)
    near = m.cost_of_candidate(80.0, 2.0, 1.0, 0.5, np.array([0.45]))
    far = m.cost_of_candidate(80.0, 2.0, 1.0, 0.5, np.array([0.05]))
    assert far > near                          # |z_next - z_current| matters
    hot = m.cost_of_candidate(120.0, 2.0, 1.0, 0.5, np.array([0.45]))
    assert hot > near                          # temperature switch penalty


def test_zero_lambdas_give_zero_cost():
    m = _meter()
    m.log_condition(80.0, 2.0, 1.0, 0.5)
    assert m.cost_of_candidate(120.0, 2.0, 1.0, 0.5,
                               np.array([0.1, 0.4])) == 0.0


def test_unchanged_condition_stabilizes_once():
    """Adaptive one-z-at-a-time sampling at the SAME (T,Q,C_EGDA,C_cat)
    must not re-stabilize the reactor for every acquisition."""
    m = _meter()
    for z in (0.1, 0.3, 0.5):
        m.log_condition(80.0, 2.0, 1.0, 0.5)   # identical condition 3x
        m.log_acquisition(z, 80.0, 2.0, 1.0, 0.5)
    tot = m.totals()
    assert tot["reactor_conditions"] == 1
    assert tot["condition_changes"] == 0
    changes = [e for e in m.events if e.kind == "condition_change"]
    holds = [e for e in m.events if e.kind == "condition_hold"]
    assert len(changes) == 1 and len(holds) == 2
    # any single element of the full condition changing IS a change
    m.log_condition(80.0, 2.0, 1.0, 0.8)       # catalyst conc changed
    assert m.totals()["reactor_conditions"] == 2
    m.log_condition(80.0, 4.0, 1.0, 0.8)       # flow changed
    assert m.totals()["reactor_conditions"] == 3
    # T stayed at 80 C throughout: no temperature change was ever logged
    assert m.totals()["temperature_changes"] == 0


def test_reacquisitions_counted_separately():
    m = _meter()
    m.log_condition(80.0, 2.0, 1.0, 0.5)
    m.log_acquisition(0.2, 80.0, 2.0, 1.0, 0.5)
    m.log_acquisition(0.2, 80.0, 2.0, 1.0, 0.5, retry=True)
    m.log_qc_reject(0.2)
    tot = m.totals()
    assert tot["nmr_acquisitions"] == 2        # a retry IS an acquisition
    assert tot["nmr_reacquisitions"] == 1
    assert tot["qc_rejected"] == 1
    assert tot["spatial_samples"] == 1         # retries are not new samples


def test_candidate_cost_consistent_with_realized_events():
    """Predicted candidate cost and realized event accounting must use the
    same assumptions (time-lambda only -> equal within tolerance)."""
    costs = ResourceCosts(lambda_time_per_s=1.0)
    m = ResourceMeter(costs, reactor_volume_mL=15.0)
    m.log_condition(80.0, 2.0, 1.0, 0.5)
    m.log_acquisition(0.3, 80.0, 2.0, 1.0, 0.5)
    zs = np.array([0.1, 0.4])
    predicted_time = m.cost_of_candidate(60.0, 2.0, 1.0, 0.5, zs)
    t_before = m.totals()["time_s"]
    m.log_condition(60.0, 2.0, 1.0, 0.5)
    for z in zs:
        m.log_acquisition(z, 60.0, 2.0, 1.0, 0.5)
    realized_time = m.totals()["time_s"] - t_before
    assert abs(predicted_time - realized_time) / realized_time < 1e-9
    # unchanged condition: prediction must also skip stabilization
    predicted_same = m.cost_of_candidate(60.0, 2.0, 1.0, 0.5,
                                         np.array([0.45]))
    t2 = m.totals()["time_s"]
    m.log_condition(60.0, 2.0, 1.0, 0.5)
    m.log_acquisition(0.45, 60.0, 2.0, 1.0, 0.5)
    realized_same = m.totals()["time_s"] - t2
    assert abs(predicted_same - realized_same) / realized_same < 1e-9


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} resource tests passed.")
