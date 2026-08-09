"""Tests for the process-parallel benchmark execution.

The contract being pinned down is not "it is faster" but "it changes
nothing": the saved results of an N-worker run must be identical to those of
a one-core run, for every N.  That rests on three properties, one test each:

  * a campaign is a PURE function of (scenario, strategy, seed, budget);
  * `ordered_map` returns results in SUBMISSION order, never completion
    order, so CSV rows land in the same positions;
  * the numerical-thread pinning that keeps the floating-point arithmetic
    identical is actually applied, in the parent and in the workers.

Runnable standalone (it really does spawn worker processes, so the module
guard at the bottom matters on macOS and Windows)."""

from __future__ import annotations

import multiprocessing as mp
import os
import pickle
import re
import sys
import time

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced import benchmark as bm
from sdl_advanced import parallel as par

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUNNER = os.path.join(_HERE, "..", "run_advanced_benchmark.py")


# ---- worker-count resolution --------------------------------------------- #
def test_worker_count_resolution():
    cpus = os.cpu_count() or 1
    assert par.resolve_workers(None) == max(1, cpus - 1)   # auto: leave one
    assert par.resolve_workers("auto") == max(1, cpus - 1)
    assert par.resolve_workers(0) == max(1, cpus)          # every core
    assert par.resolve_workers(1) == 1                     # serial
    assert par.resolve_workers(4) == 4                     # exact
    assert par.resolve_workers(-3) == 1                    # never below one
    # a single worker must build NO pool at all, so the serial path is the
    # original code path rather than a one-process pool
    assert par.make_executor(1) is None


def test_start_method_is_spawn_everywhere():
    """macOS (incl. Apple Silicon) and Windows default to spawn; forcing it
    on Linux too means one behaviour on all three platforms."""
    ex = par.make_executor(2)
    assert ex is not None
    try:
        assert ex._mp_context.get_start_method() == "spawn"
    finally:
        ex.shutdown(wait=True)


# ---- thread pinning ------------------------------------------------------- #
def test_pin_numerical_threads_sets_every_backend():
    before = {v: os.environ.get(v) for v in par.THREAD_ENV_VARS}
    try:
        par.pin_numerical_threads(1)
        for v in par.THREAD_ENV_VARS:
            assert os.environ[v] == "1", v
        par.pin_numerical_threads(3)
        assert all(os.environ[v] == "3" for v in par.THREAD_ENV_VARS)
        par.pin_numerical_threads(0)              # never below one thread
        assert all(os.environ[v] == "1" for v in par.THREAD_ENV_VARS)
    finally:
        for v, old in before.items():
            if old is None:
                os.environ.pop(v, None)
            else:
                os.environ[v] = old


def test_runner_pins_threads_before_importing_numpy():
    """The runner spells the variable list out inline because importing it
    from the package would already have imported numpy.  Guard against the
    two lists drifting apart, and against the block being moved below the
    numpy import (where it would silently do nothing)."""
    src = open(_RUNNER, encoding="utf-8").read()
    head = src.split("import numpy")[0]
    for v in par.THREAD_ENV_VARS:
        assert v in head, f"{v} not pinned before numpy is imported"
    assert re.search(r'os\.environ\[_var\]\s*=\s*"1"', head)


# ---- ordered_map: submission order, not completion order ------------------ #
def _slow_square(x, delay):
    time.sleep(delay)
    return x * x


def test_ordered_map_returns_submission_order():
    """Deliberately invert the completion order: the FIRST task sleeps
    longest.  A naive as-completed collector would return it last."""
    args = [(i, 0.30 - 0.05 * i) for i in range(5)]
    expect = [i * i for i in range(5)]
    assert par.ordered_map(_slow_square, args) == expect          # serial
    ex = par.make_executor(5)
    try:
        got = par.ordered_map(_slow_square, args, executor=ex)
    finally:
        ex.shutdown(wait=True)
    assert got == expect


def test_ordered_map_callback_sees_every_task_once():
    seen = []
    args = [(i, 0.0) for i in range(6)]
    par.ordered_map(_slow_square, args, on_result=lambda i, a, r: seen.append(i))
    assert sorted(seen) == list(range(6))


def test_worker_exception_propagates():
    ex = par.make_executor(2)
    try:
        par.ordered_map(_slow_square, [(1, "not-a-number")], executor=ex)
    except TypeError:
        pass
    else:
        raise AssertionError("a failing task must not be swallowed")
    finally:
        ex.shutdown(wait=True)


# ---- the campaign task is pure and picklable ----------------------------- #
def _strip_wall_clock(status):
    """runtime_s measures the RUN, not the chemistry: it is the one field a
    worker count is allowed to change."""
    return {k: v for k, v in status.items() if k != "runtime_s"}


def _val_equal(x, y) -> bool:
    """Plain `==` is unusable here: legitimate NaNs (p_correct for a
    non-Bayesian strategy, an unbounded CI) never compare equal to
    themselves, so a dict comparison would report a difference in runs that
    are in fact identical.  NaN is treated as equal to NaN; everything else
    is exact - no tolerance, because the claim under test is bit-identity."""
    try:
        fx, fy = float(x), float(y)
    except (TypeError, ValueError):
        return x == y
    if np.isnan(fx) and np.isnan(fy):
        return True
    return fx == fy


def _rows_equal(a, b) -> bool:
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if set(ra) != set(rb):
            return False
        if any(not _val_equal(ra[k], rb[k]) for k in ra):
            return False
    return True


def test_nan_aware_comparison_still_detects_a_real_difference():
    """Guard the guard: the NaN-tolerant comparator must not be so
    forgiving that the determinism tests below can no longer fail."""
    assert _rows_equal([{"a": float("nan"), "b": 1.0}],
                       [{"a": float("nan"), "b": 1.0}])
    assert not _rows_equal([{"a": 1.0}], [{"a": 1.0 + 1e-15}])
    assert not _rows_equal([{"a": float("nan")}], [{"a": 0.0}])
    assert not _rows_equal([{"a": 1.0}], [{"b": 1.0}])
    assert not _rows_equal([{"a": "x"}], [{"a": "y"}])
    assert not _rows_equal([{"a": 1.0}], [])


def test_campaign_task_is_a_pure_function_of_its_labels():
    a = bm.campaign_task("S1_ideal", "A", 3, 3)
    b = bm.campaign_task("S1_ideal", "A", 3, 3)
    assert _rows_equal(a["rows"], b["rows"])
    assert _rows_equal(a["prows"], b["prows"])
    assert _rows_equal([_strip_wall_clock(a["status"])],
                       [_strip_wall_clock(b["status"])])
    # a different seed really does give a different campaign (so the test
    # above is not comparing two constants)
    c = bm.campaign_task("S1_ideal", "A", 4, 3)
    assert not _rows_equal(c["rows"], a["rows"])


def test_campaign_payload_is_picklable_both_ways():
    """Only primitives may cross the process boundary - never a laboratory,
    a posterior or a ScenarioSpec."""
    args = ("S1_ideal", "A", 3, 3, False)
    assert pickle.loads(pickle.dumps(args)) == args
    out = bm.campaign_task(*args)
    back = pickle.loads(pickle.dumps(out))
    assert _rows_equal(back["rows"], out["rows"])
    assert set(back) == {"rows", "prows", "status", "audit"}
    # the audit trail is opt-in: an un-audited task carries no payload, so
    # the default parallel run sends exactly what it always did
    assert out["audit"] is None


# ---- the headline guarantee ---------------------------------------------- #
def test_parallel_run_scenario_matches_serial_exactly():
    """The whole point, end to end: a real registered scenario with all six
    of its strategies, run once serially and once over a pool, must produce
    the same rows in the same order.  Budget 3 and two seeds keep it to
    about half a minute; nothing about the comparison depends on the size."""
    spec = bm.SCENARIOS["S1_ideal"]
    seeds = [1, 2]
    rows_s, prows_s, status_s, _a = bm.run_scenario(spec, seeds, 3)
    ex = par.make_executor(4, initializer=bm.worker_init, initargs=(3,))
    assert ex is not None
    try:
        rows_p, prows_p, status_p, _b = bm.run_scenario(spec, seeds, 3,
                                                        executor=ex)
    finally:
        ex.shutdown(wait=True)

    assert _rows_equal(rows_p, rows_s), \
        "round rows differ between serial and parallel"
    assert _rows_equal(prows_p, prows_s), "parameter rows differ"
    assert _rows_equal([_strip_wall_clock(x) for x in status_p],
                       [_strip_wall_clock(x) for x in status_s])
    # ORDER too, not just contents: the CSVs must land row for row
    assert [(r["strategy"], r["seed"], r["round"]) for r in rows_p] == \
           [(r["strategy"], r["seed"], r["round"]) for r in rows_s]
    # strategy-major then seed, exactly as the serial double loop emitted it
    assert [(s["strategy"], s["seed"]) for s in status_p] == \
           [(st, sd) for st in spec.strategies for sd in seeds]


def test_unregistered_spec_falls_back_to_serial():
    """A scenario object that is not the one in SCENARIOS cannot be sent to
    a worker (only its NAME travels), so it must be run in-process rather
    than silently replaced by the registered definition."""
    import dataclasses
    ghost = dataclasses.replace(bm.SCENARIOS["S1_ideal"], strategies=("A",))
    assert bm.SCENARIOS.get(ghost.name) is not ghost
    ex = par.make_executor(2, initializer=bm.worker_init, initargs=(3,))
    try:
        rows, _p, _s, _a = bm.run_scenario(ghost, [1], 3, executor=ex)
    finally:
        ex.shutdown(wait=True)
    assert _rows_equal(rows, bm.run_scenario(ghost, [1], 3)[0])


def test_governor_validation_order_is_seed_order():
    """detection_rounds is a list the report reads positionally, so it must
    come back in seed order however the pool schedules the work."""
    seeds = [1, 2, 3, 4]
    tasks = [("S1_ideal", s, 3) for s in seeds]
    ex = par.make_executor(4, initializer=bm.worker_init, initargs=(3,))
    try:
        got = par.ordered_map(bm.governor_task, tasks, executor=ex)
    finally:
        ex.shutdown(wait=True)
    exp = [bm.governor_task(*t) for t in tasks]
    assert got == exp


if __name__ == "__main__":
    mp.freeze_support()                 # Windows-safe when frozen
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        t = time.time()
        fn()
        print(f"PASS  {fn.__name__}  ({time.time() - t:.1f} s)")
    print(f"\n{len(fns)}/{len(fns)} parallel-execution tests passed.")
