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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} resource tests passed.")
