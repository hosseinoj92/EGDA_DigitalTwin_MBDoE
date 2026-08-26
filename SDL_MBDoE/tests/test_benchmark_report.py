"""Regression guard for the benchmark's run-level summary.

THE CLAIM UNDER TEST, in three parts.

FIRST: the summary layer is PURE.  Every table in `benchmark_export` is a
function of rows that already exist on disk, so calling it twice on the same
input must give the same output, byte for byte, in any process.  That is not
automatic: the confidence intervals come from a bootstrap, and a bootstrap
seeded from Python's `hash()` moves between runs because CPython randomizes
string hashing per process.  `efficiency.stable_seed` exists for exactly
that reason and the first test pins it.

SECOND: the aggregates AGREE with the raw tables they aggregate.  A summary
that quietly disagrees with `benchmark_rounds.csv` would be worse than no
summary, so the master row's completion counts, resource medians and
accuracy are checked against the campaign status and round rows directly.

THIRD: the summary DEGRADES GRACEFULLY.  A scenario with one candidate model
has no discrimination row, a direct-observation scenario has no NMR rows,
and a run without a transfer log has no decomposition - each must produce an
empty table rather than a wrong one or an exception.

Runnable standalone."""

from __future__ import annotations

import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced import benchmark as bm
from sdl_advanced import benchmark_export as bex
from sdl_advanced.efficiency import stable_seed

BUDGET = 2


def _val_equal(x, y) -> bool:
    """NaN == NaN.  These tables are full of legitimate NaNs (a metric a
    strategy cannot have), and `float('nan') != float('nan')` would make
    every purity check fail for the wrong reason."""
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


def _first_difference(a, b) -> str:
    if len(a) != len(b):
        return f"row count {len(a)} vs {len(b)}"
    for i, (ra, rb) in enumerate(zip(a, b)):
        for k in sorted(set(ra) | set(rb)):
            if k not in ra or k not in rb:
                return f"row {i}: key {k!r} in only one result"
            if not _val_equal(ra[k], rb[k]):
                return f"row {i}: {k!r} {ra[k]!r} vs {rb[k]!r}"
    return "no difference"


def _run(scenario: str, strategies, seeds=(1, 2)):
    """A handful of real campaigns, with the audit trail on."""
    rows, prows, status, audit = [], [], [], {}
    for strat in strategies:
        for seed in seeds:
            out = bm.campaign_task(scenario, strat, seed, BUDGET,
                                   audit=True, transfer_audit=True)
            rows += [dict(r, seed=seed) for r in out["rows"]]
            prows += [dict(r, seed=seed) for r in out["prows"]]
            status.append(out["status"])
            for k, v in (out["audit"] or {}).items():
                audit.setdefault(k, []).extend(v)
    return rows, prows, status, audit


# ---- part one: the summary layer is pure and reproducible ---------------- #
def test_bootstrap_seed_survives_hash_randomization():
    """A seed derived from `hash()` differs between processes; this one must
    not, or every reported confidence interval moves between two runs of the
    same configuration."""
    code = ("import sys; sys.path.insert(0, %r);"
            "from sdl_advanced.efficiency import stable_seed;"
            "print(stable_seed(('S1_ideal', 'F', 'param_err_pct')))"
            % os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    want = str(stable_seed(("S1_ideal", "F", "param_err_pct")))
    for hs in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        got = subprocess.run([sys.executable, "-c", code], env=env,
                             capture_output=True, text=True).stdout.strip()
        assert got == want, (f"the bootstrap seed changed with "
                             f"PYTHONHASHSEED={hs}: {got} vs {want}")


def test_every_summary_table_is_a_pure_function_of_its_rows():
    # the scenario's own reference strategy is included, because the paired
    # table has nothing to pair against without it
    rows, prows, status, audit = _run(
        "S1_ideal", (bm.reference_strategy("S1_ideal"), "F"))
    builders = (
        ("master", lambda: bex.master_summary_rows(
            rows, status, prows, audit.get("model_probabilities_long", []),
            audit.get("governor_diagnostics_long", []), bm.SCENARIOS)),
        ("parameters", lambda: bex.parameter_performance_rows(
            prows, audit.get("identifiability_summary", []),
            audit.get("posterior_covariance_long", []))),
        ("design", lambda: bex.design_selection_rows(
            audit.get("design_history", []))),
        ("paired", lambda: bex.paired_summary_rows(
            bex.paired_seed_rows(rows, bm.SCENARIOS))),
        ("robustness", lambda: bex.robustness_rows(
            rows, status, prows, audit.get("governor_diagnostics_long", []),
            audit.get("nmr_measurements_long", []),
            audit.get("model_probabilities_long", []), bm.SCENARIOS)),
        ("resources", lambda: bex.resource_summary_rows(
            rows, audit.get("resource_events_long", []))),
    )
    for name, fn in builders:
        a, b = fn(), fn()
        assert a, f"{name} produced no rows"
        assert _rows_equal(a, b), (
            f"{name} is not a pure function of its input rows: "
            + _first_difference(a, b))


# ---- part two: the aggregates agree with the raw tables ------------------ #
def test_master_summary_agrees_with_the_raw_tables():
    rows, prows, status, audit = _run("S1_ideal", ("D", "F"))
    assert len({r["strategy"] for r in rows}) == 2
    master = bex.master_summary_rows(
        rows, status, prows, audit.get("model_probabilities_long", []),
        audit.get("governor_diagnostics_long", []), bm.SCENARIOS)
    assert len(master) == 2
    for r in master:
        st = [s for s in status if s["scenario"] == r["scenario"]
              and s["strategy"] == r["strategy"]]
        assert r["n_campaigns"] == len(st)
        assert r["n_completed"] == sum(int(s["completed"]) for s in st)
        assert r["n_faulted"] == sum(int(s["faulted"]) for s in st)
        # the accuracy is the median over each seed's LAST VALID round
        fin = bm.last_valid_rows(rows, r["scenario"], r["strategy"])
        want = float(np.median([x["param_err_pct"] for x in fin
                                if np.isfinite(x["param_err_pct"])]))
        assert abs(r["param_err_pct_median"] - want) < 1e-12
        # resources come from those same rows
        want_t = float(np.median([x["time_s"] for x in fin]))
        assert abs(r["median_time_s_s"] - want_t) < 1e-9


def test_paired_differences_are_per_seed_and_use_common_seeds_only():
    rows, _prows, _status, _audit = _run(
        "S1_ideal", (bm.reference_strategy("S1_ideal"), "F"))
    paired = bex.paired_seed_rows(rows, bm.SCENARIOS)
    assert paired
    ref = bm.reference_strategy("S1_ideal")
    for r in paired:
        assert r["reference_strategy"] == ref
        assert r["strategy"] != ref
        assert abs((r["value_strategy"] - r["value_reference"])
                   - r["difference"]) < 1e-12
        want_better = ((r["difference"] < 0) if r["lower_is_better"]
                       else (r["difference"] > 0))
        assert bool(r["strategy_better"]) == want_better
    summary = bex.paired_summary_rows(paired)
    for r in summary:
        # a single pair is not a confidence interval and must not claim one
        if int(r["n_pairs"]) < 2:
            assert not np.isfinite(r["difference_ci_lo"])
            assert int(r["ci_excludes_zero"]) == 0


def test_design_distribution_counts_conditions_not_acquisitions():
    """A ten-position profile chooses ONE operating condition, not ten, and
    weighting it ten times would misrepresent where the method goes."""
    rows, _p, _s, audit = _run("S1_ideal", ("D",))
    hist = audit.get("design_history", [])
    assert hist
    dist = bex.design_selection_rows(hist)
    cond = {(r["scenario"], r["strategy"], r["seed"], r["round"])
            for r in hist}
    for r in dist:
        if r["variable"] == "T_C":
            assert r["weighting"] == "per_reactor_condition"
            assert r["n_total"] == len(cond)
        if r["variable"] == "z_over_L":
            assert r["weighting"] == "per_acquisition"
            assert r["n_total"] == len(hist)


# ---- part three: graceful degradation ------------------------------------ #
def test_tables_that_do_not_apply_come_back_empty_not_wrong():
    rows, prows, status, audit = _run("S1_ideal", ("D",))
    # S1 observes concentrations directly: no spectra, so no NMR performance
    assert not bex.nmr_performance_rows(
        audit.get("nmr_measurements_long", []))
    # one candidate model: nothing to discriminate
    assert not bex.model_discrimination_rows(
        audit.get("model_probabilities_long", []), rows, bm.SCENARIOS)
    # no transfer line: no decomposition
    assert not bex.transfer_decomposition_summary_rows(
        audit.get("transfer_decomposition_long", []))
    # and the tables that DO apply are still produced
    assert bex.master_summary_rows(rows, status, prows, [], [], bm.SCENARIOS)
    assert bex.robustness_rows(rows, status, prows, [], [], [], bm.SCENARIOS)


def test_empty_input_never_raises():
    for fn in (lambda: bex.master_summary_rows([], [], [], [], [],
                                               bm.SCENARIOS),
               lambda: bex.parameter_performance_rows([], [], []),
               lambda: bex.design_selection_rows([]),
               lambda: bex.design_by_round_rows([]),
               lambda: bex.paired_seed_rows([], bm.SCENARIOS),
               lambda: bex.paired_summary_rows([]),
               lambda: bex.robustness_rows([], [], [], [], [], [],
                                           bm.SCENARIOS),
               lambda: bex.model_discrimination_rows([], [], bm.SCENARIOS),
               lambda: bex.nmr_performance_rows([]),
               lambda: bex.transfer_effect_rows([], (), bm.SCENARIOS),
               lambda: bex.transfer_decomposition_summary_rows([]),
               lambda: bex.resource_summary_rows([], []),
               lambda: bex.matrix_rows([])):
        assert fn() == []


def test_transport_scenario_produces_the_truth_side_decomposition():
    """The decomposition must ADD UP and must name the dominant stage."""
    _rows, _p, _s, audit = _run("S3_transport", ("F",), seeds=(1,))
    long = audit.get("transfer_decomposition_long", [])
    assert long, "the transport scenario kept no transfer log"
    for r in long[:200]:
        assert abs((r["transport_delta_M"] + r["quantification_delta_M"])
                   - r["total_delta_M"]) < 1e-12
    summary = bex.transfer_decomposition_summary_rows(long)
    assert summary
    for r in summary:
        assert r["dominant_error_stage"] in ("transport", "quantification")
        assert 0.0 <= r["transport_share_of_total_error"] <= 1.0


if __name__ == "__main__":
    import time
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        t = time.time()
        fn()
        print(f"PASS  {fn.__name__}  ({time.time() - t:.1f} s)")
    print(f"\n{len(fns)}/{len(fns)} benchmark-summary tests passed.")
