"""Regression guard for the per-campaign scientific record.

THE CLAIM UNDER TEST, in two halves.

FIRST: the record cannot change the campaign.  Producing it turns on three
things that touch live code paths - the passive audit recorder, the
laboratory's spectrum log and its truth-side transfer log - and every one of
them could have gone wrong in the same specific way, by consuming a random
number or by re-evaluating something the controller had already decided.
The tests below run the same seed with all three off and with all three on
and require every round metric, every parameter row, every metered resource
total and the stop reason to be IDENTICAL.  Not close: identical.

SECOND: the record is actually a record.  A table that exists but is empty,
or one whose numbers disagree with the campaign they claim to describe, is
worse than no table, so the tables are checked against the campaign objects
they were derived from and against each other.

The ground-truth firewall is tested too: truth-side quantities must appear
ONLY in the post-campaign report, and the laboratory must not have been
asked to reveal anything until the campaign was over.

Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced import audit_export as aex
from sdl_advanced import benchmark as bm
from sdl_advanced import campaign_export as cex
from sdl_advanced.audit import AuditRecorder

SCENARIO, SEED, BUDGET = "S3_transport", 3, 2


# ------------------------------------------------------------------------- #
def _run(strategy: str, record: bool):
    """One campaign, with the reporting sinks either all on or all off."""
    spec = bm.SCENARIOS[SCENARIO]
    z_val = np.array([bm.GEOMETRY["length_m"] / 3.0, bm.GEOMETRY["length_m"]])
    y_true = bm._truth_prediction(spec.truth, z_val, geometry=bm.GEOMETRY)
    recorder = (AuditRecorder(spec.name, strategy, SEED, bm.SPECIES)
                if record else None)
    res, lab, extra = bm.run_one_campaign(
        spec, strategy, SEED, BUDGET, verbose=False,
        store_spectra=record and spec.observation_mode == "nmr",
        recorder=recorder, store_transfer_log=record)
    rows, prows = bm._round_metrics(spec, strategy, res, lab, extra,
                                    z_val, y_true)
    return {"spec": spec, "res": res, "lab": lab, "extra": extra,
            "recorder": recorder, "rows": rows, "prows": prows,
            "totals": lab.meter.totals(),
            "stop": getattr(res, "stop_reason", ""),
            "z_val": z_val, "y_true": y_true}


def _record(out, strategy: str) -> cex.CampaignRecord:
    spec = out["spec"]
    audit = aex.collect_campaign(
        spec, strategy, SEED, out["res"], out["lab"], out["extra"],
        out["recorder"], out["z_val"], out["y_true"], bm.VALIDATION_CONDS,
        bm.SPECIES, "optimized", scoring_bridge=bm._scoring_bridge)
    return cex.CampaignRecord(
        scenario=spec.name, strategy=strategy, seed=SEED, spec=spec,
        res=out["res"], lab=out["lab"], extra=out["extra"],
        recorder=out["recorder"], audit=audit,
        metric_rows=out["rows"], param_rows=out["prows"],
        species=tuple(bm.SPECIES), length_m=float(out["lab"].length_m),
        spatial_mode="optimized", budget=BUDGET,
        observation_mode=spec.observation_mode, truth=dict(spec.truth))


def _same(a, b) -> bool:
    """NaN == NaN; everything else compared exactly."""
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if set(ra) != set(rb):
            return False
        for k in ra:
            x, y = ra[k], rb[k]
            try:
                fx, fy = float(x), float(y)
                if np.isnan(fx) and np.isnan(fy):
                    continue
                if fx != fy:
                    return False
            except (TypeError, ValueError):
                if x != y:
                    return False
    return True


# ---- half one: the record cannot move a number --------------------------- #
def test_recording_does_not_change_the_bayesian_campaign():
    """F is the one that matters: it exercises the EIG selector's RNG, the
    QC gate and the governor.  A single random number consumed by the
    spatial-curve capture or the spectrum log would move every later design
    decision, and these rows would not match."""
    off, on = _run("F", False), _run("F", True)
    assert _same(off["rows"], on["rows"]), "RECORDING CHANGED THE ROUND ROWS"
    assert _same(off["prows"], on["prows"]), "RECORDING CHANGED THE PARAMETERS"
    assert off["totals"] == on["totals"], "RECORDING CHANGED THE RESOURCES"
    assert off["stop"] == on["stop"]


def test_recording_does_not_change_a_baseline_campaign():
    """The control: D runs unchanged sdl.campaign code, so this must pass
    trivially - and if it does not, the comparison itself is broken."""
    off, on = _run("D", False), _run("D", True)
    assert _same(off["rows"], on["rows"])
    assert off["totals"] == on["totals"]


def test_spatial_capture_reports_only_what_the_designer_evaluated():
    """The information curve is KEPT from the greedy step, not recomputed.
    Its marginal gains must therefore be exactly the gains that chose the
    positions: the best candidate on the curve is the first pick."""
    out = _run("F", True)
    rows = out["recorder"].payload()["spatial_candidate_scores"]
    assert rows, "no spatial curve was recorded"
    sel = [r for r in rows if r["candidate_selected"] == 1
           and r["round"] == rows[0]["round"]
           and r["candidate_rank"] == 1]
    grid = [r for r in sel if r["row_kind"] == "candidate_z"
            and np.isfinite(r["marginal_gain_nats"])]
    first = [r for r in sel if r["row_kind"] == "selected_z"
             and r["selection_order"] == 1]
    if not grid or not first:
        return                       # fixed_equal mode records no curve
    best = max(grid, key=lambda r: r["marginal_gain_nats"])
    assert abs(best["z_m"] - first[0]["z_m"]) < 1e-9, (
        "the curve's maximum is not the position the designer took - the "
        "recorded curve is not the one the decision was made on")
    assert abs(best["marginal_gain_nats"]
               - first[0]["realized_gain_nats"]) < 1e-9


# ---- half two: the record is a record ------------------------------------ #
def test_every_table_is_populated_and_consistent():
    out = _run("F", True)
    rec = _record(out, "F")
    rounds = cex.round_rows([rec])
    meas = cex.measurement_rows([rec])
    conc = cex.concentration_rows([rec])
    params = cex.parameter_rows([rec])
    qc = cex.qc_rows([rec], meas)
    res_rows = cex.resource_round_rows([rec])
    trans = cex.transfer_rows([rec])
    summary = cex.strategy_summary_rows([rec])
    for name, rows in (("campaign_rounds", rounds), ("measurements", meas),
                       ("concentrations", conc),
                       ("kinetic_parameters", params), ("qc_history", qc),
                       ("resource_history", res_rows),
                       ("transfer_history", trans),
                       ("strategy_comparison", summary)):
        assert rows, f"{name} is empty"
        assert all(r["scenario"] == SCENARIO and r["seed"] == SEED
                   for r in rows), f"{name} is not tagged with its campaign"
    # one row per round, and they are the campaign's rounds
    assert [r["round"] for r in rounds] == [int(x.round)
                                            for x in out["res"].history]
    # the accuracy columns are the benchmark's own numbers, not a re-derivation
    for r, m in zip(rounds, out["rows"]):
        assert r["param_err_pct_vs_truth"] == m["param_err_pct"]
        assert r["blind_rmse_M_vs_truth"] == m["blind_rmse_M"]
    # the accepted concentrations are exactly the assimilated measurements
    n_acc = sum(m.size for m in
                out["res"].ensemble.best.inference.measurements)
    assert len(conc) == n_acc
    # every rejected acquisition survives in the measurement table only
    assert {r["disposition"] for r in meas} <= {
        "accepted", "accepted_after_reacquisition", "rejected",
        "failed_qc", "failed_qc_reacquiring"}
    # the summary's resource totals are the meter's
    tot = out["lab"].meter.totals()
    assert summary[0]["time_s"] == tot["time_s"]
    assert summary[0]["n_nmr_acquisitions"] == tot["nmr_acquisitions"]


def test_transfer_table_separates_transport_from_quantification():
    """The decomposition must ADD UP: reactor -> cell -> reported."""
    out = _run("F", True)
    rows = cex.transfer_rows([_record(out, "F")])
    assert rows
    for r in rows[:200]:
        assert abs((r["transport_delta_M"] + r["quantification_delta_M"])
                   - r["total_delta_M"]) < 1e-12
        assert abs((r["c_measured_M"] - r["c_reactor_true_M"])
                   - r["total_delta_M"]) < 1e-12


def test_truth_is_revealed_only_after_the_campaign():
    """The firewall: nothing may ask the laboratory for truth while it is
    still running.  The transfer log is written during the campaign but is
    private; reading it is a post-campaign act and is counted as one."""
    out = _run("F", True)
    assert out["lab"].n_truth_reveals == 0, (
        "the campaign revealed truth while it was running")
    out["lab"].reveal_transfer_log()
    assert out["lab"].n_truth_reveals == 1, (
        "reading the transfer log was not counted as a truth reveal")


def test_a_record_without_truth_omits_every_truth_column():
    """A campaign on real hardware has no hidden truth.  The reporting layer
    must then produce the SAME tables minus the validation columns, rather
    than failing or inventing a comparison."""
    out = _run("F", True)
    rec = _record(out, "F")
    rec.truth = None                       # as if this were a real lab
    rounds = cex.round_rows([rec])
    params = cex.parameter_rows([rec])
    summary = cex.strategy_summary_rows([rec])
    assert rounds and params and summary
    banned = ("param_err_pct_vs_truth", "blind_rmse_M_vs_truth",
              "true_value_natural", "rel_error_pct_vs_truth",
              "param_err_pct_final_vs_truth")
    for rows in (rounds, params, summary):
        for r in rows:
            assert not any(k in r for k in banned), (
                "a truth column survived into a record with no truth source")
    assert not cex.transfer_rows([rec])


# ---- the campaign runner's own parallelism ------------------------------- #
def test_parallel_campaigns_reproduce_the_serial_run_exactly():
    """THE CLAIM: turning workers on changes speed and nothing else.

    Two failure modes are being excluded at once.  The first is a WRONG
    RESULT - a worker running a different configuration from the parent, or
    a campaign whose RNG depends on how many others are running.  The second
    is a WRONG ORDER - results reassembled as they finish rather than as
    they were submitted, which would silently permute every CSV row and
    every figure series while leaving each individual number correct.  The
    second is the more dangerous of the two, because nothing looks broken.

    The strategies are compared by their DERIVED metric rows rather than by
    the returned objects, because that is what actually reaches the saved
    files."""
    import run_advanced_campaign as rc
    from sdl_advanced import parallel as par

    # The runner's `main()` applies its KNOBS to the benchmark module before
    # anything runs, and `bm.worker_init` replays them inside each worker.
    # A test that skips the first half would compare a default-configured
    # parent against campaign-configured workers and "discover" a
    # difference that the runner does not have - so it is done here too,
    # and undone afterwards so the rest of the suite is unaffected.
    before = bm.resolved_config()
    bm.apply_config(dict(rc.KNOBS))
    try:
        _parallel_body(rc, par)
    finally:
        bm.apply_config(before)
        bm._GEOMETRY_CACHE.clear()


def _parallel_body(rc, par):
    spec = bm.SCENARIOS[SCENARIO]
    strategies = ["A", "D"]          # two cheap ones; the contract is generic
    z_val = np.array([bm.GEOMETRY["length_m"] / 3.0, bm.GEOMETRY["length_m"]])
    y_true = bm._truth_prediction(spec.truth, z_val, geometry=bm.GEOMETRY)
    tasks = [(spec.name, st, SEED, BUDGET, False, False)
             for st in strategies]

    def _derive(outputs):
        out = []
        for st, (res, lab, extra, _rec) in zip(strategies, outputs):
            rows, prows = bm._round_metrics(spec, st, res, lab, extra,
                                            z_val, y_true)
            out.append((st, rows, prows, lab.meter.totals()))
        return out

    serial = _derive(par.ordered_map(rc._campaign_task, tasks,
                                     executor=None))
    ex = par.make_executor(2, initializer=bm.worker_init,
                           initargs=(BUDGET, dict(rc.KNOBS)))
    assert ex is not None, "a 2-worker pool was not created"
    try:
        parallel = _derive(par.ordered_map(rc._campaign_task, tasks,
                                           executor=ex))
    finally:
        ex.shutdown(wait=True)

    # ORDER: outputs line up with the submitted strategy list, not with
    # whichever worker finished first
    assert [x[0] for x in parallel] == strategies
    assert [x[0] for x in serial] == strategies
    # VALUES: identical, to the bit
    for (st_a, rows_a, prows_a, tot_a), (st_b, rows_b, prows_b, tot_b) \
            in zip(serial, parallel):
        assert st_a == st_b
        assert _same(rows_a, rows_b), (
            f"{st_a}: PARALLEL CHANGED THE ROUND METRICS")
        assert _same(prows_a, prows_b), (
            f"{st_a}: PARALLEL CHANGED THE PARAMETER ROWS")
        assert tot_a == tot_b, f"{st_a}: parallel changed the resource totals"


def test_worker_count_never_changes_which_strategy_owns_a_result():
    """A cheap, direct guard on the zip that pairs strategies with outputs:
    if `ordered_map` ever returned completion order, this alignment would
    silently attribute one strategy's campaign to another."""
    import run_advanced_campaign as rc
    from sdl_advanced import parallel as par

    # a deliberately uneven workload: the LAST task is the fastest, so a
    # completion-ordered implementation would put it first
    tasks = [(0, 0.30), (1, 0.20), (2, 0.01)]
    ex = par.make_executor(3)
    try:
        got = par.ordered_map(_slow_module_level, tasks, executor=ex)
    finally:
        if ex is not None:
            ex.shutdown(wait=True)
    assert got == [0, 1, 2], f"reassembly was not in submission order: {got}"
    # NOTE: the value of CONFIG["n_workers"] is deliberately NOT asserted.
    # It is a user preference, not a contract - the contract is that any
    # value produces the same results, which is what the test above pins.
    assert par.resolve_workers(rc.CONFIG["n_workers"]) >= 1


def _slow_module_level(i, delay):
    """Module level so a spawned worker can find it by qualified name."""
    import time as _t
    _t.sleep(delay)
    return i


if __name__ == "__main__":
    import time
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        t = time.time()
        fn()
        print(f"PASS  {fn.__name__}  ({time.time() - t:.1f} s)")
    print(f"\n{len(fns)}/{len(fns)} campaign-record tests passed.")
