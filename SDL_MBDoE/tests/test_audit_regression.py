"""Regression guard for the publication audit trail.

THE CLAIM UNDER TEST: turning the audit trail on changes nothing scientific.
Not "changes little" - nothing.  Every pre-existing result row, parameter
row and campaign status field must be identical, for the same seed, with
`audit=True` and `audit=False`.

This matters because the audit trail touches live code paths: the selector
reports its candidate scores, the QC gate reports each acquisition's
disposition, the controllers time themselves and keep a reference to the
posterior covariance.  Any of those could have gone wrong in one specific
way - by consuming a random number.  The selector's EIG estimator draws
from `self._rng`; evaluating one extra candidate "just for the report" would
advance that stream and silently change every subsequent design decision in
the campaign.  The tests below would catch exactly that, because a shifted
RNG stream changes the selected conditions and therefore every downstream
number.

Wall-clock fields are excluded by name and only those: `runtime_s` measures
the run, not the chemistry, and differs between two identical serial runs.

Runnable standalone."""

from __future__ import annotations

import inspect
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl_advanced import audit_export as aex
from sdl_advanced import benchmark as bm
from sdl_advanced import nmr_examples as nex
from sdl_advanced.audit import AuditRecorder

#: fields whose value legitimately depends on wall-clock time
WALL_CLOCK = ("runtime_s",)


def _strip(d):
    return {k: v for k, v in d.items() if k not in WALL_CLOCK}


def _val_equal(x, y) -> bool:
    """NaN == NaN (legitimate NaNs are everywhere in these rows); everything
    else compared EXACTLY - the claim is bit-identity, not closeness."""
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
                return f"row {i}: key '{k}' present in only one run"
            if not _val_equal(ra[k], rb[k]):
                return (f"row {i} ({ra.get('scenario')}/{ra.get('strategy')}"
                        f"/seed{ra.get('seed')}/round{ra.get('round')}): "
                        f"'{k}' {ra[k]!r} vs {rb[k]!r}")
    return "no difference"


# ---- the headline regression --------------------------------------------- #
def _compare(scenario: str, strategy: str, seed: int, budget: int) -> None:
    off = bm.campaign_task(scenario, strategy, seed, budget, audit=False)
    on = bm.campaign_task(scenario, strategy, seed, budget, audit=True)
    assert _rows_equal(off["rows"], on["rows"]), (
        f"{scenario}/{strategy}: AUDIT CHANGED THE ROUND METRICS - "
        + _first_difference(off["rows"], on["rows"]))
    assert _rows_equal(off["prows"], on["prows"]), (
        f"{scenario}/{strategy}: AUDIT CHANGED THE PARAMETER ROWS - "
        + _first_difference(off["prows"], on["prows"]))
    assert _rows_equal([_strip(off["status"])], [_strip(on["status"])]), (
        f"{scenario}/{strategy}: AUDIT CHANGED THE CAMPAIGN STATUS - "
        + _first_difference([_strip(off["status"])], [_strip(on["status"])]))
    assert off["audit"] is None and on["audit"] is not None


def test_audit_does_not_change_a_baseline_campaign():
    """A-D run unchanged sdl.campaign code and are audited entirely
    post-campaign, so this is the easy case - and the control that says the
    comparison itself works."""
    _compare("S1_ideal", "A", 3, 3)


def test_audit_does_not_change_strategy_e():
    """E adds spatial optimization and per-round timing calls."""
    _compare("S1_ideal", "E", 3, 3)


def test_audit_does_not_change_the_full_bayesian_loop():
    """The one that matters: F exercises the EIG selector (RNG), the QC gate
    and the governor.  If recording consumed a single random number, the
    designed conditions would diverge and these rows would not match."""
    _compare("S1_ideal", "F", 3, 3)


def test_audit_does_not_change_the_nmr_and_transport_loop():
    """S3 turns on the NMR pathway, the transfer line and the QC gate, so
    the acquisition-level recording is live here."""
    _compare("S3_transport", "F", 2, 3)


def test_audit_does_not_change_a_governor_trip():
    """S5 removes the correct model, so the governor fires and the selector
    switches to diagnostic mode - a different recording path again."""
    _compare("S5_inadequacy", "F", 1, 4)


# ---- why it cannot change: structural guards ----------------------------- #
def test_recorder_never_touches_an_rng():
    """The sink must not contain the machinery to draw a random number.  A
    static check, so it fails on the line that introduces the problem rather
    than on a seed that happens to expose it."""
    import sdl_advanced.audit as audit_mod
    src = inspect.getsource(audit_mod)
    for forbidden in ("default_rng", "np.random", "random.", "shuffle",
                      "permutation", "standard_normal"):
        assert forbidden not in src, (
            f"sdl_advanced/audit.py must not reference {forbidden!r}: the "
            "recorder is a passive sink and drawing anything would shift "
            "every seeded decision after it")


def test_selector_records_only_already_evaluated_candidates():
    """The EIG is Monte-Carlo and consumes the selector's RNG.  The audit
    may report the candidates the selector evaluated for its own decision,
    and must leave the rest blank rather than evaluating them - hence the
    `eig_evaluated` flag."""
    from sdl_advanced import bayes_design
    src = inspect.getsource(bayes_design.AdvancedSelector._record)
    assert "expected_information_gain" not in src
    assert "self._rng" not in src
    rec = AuditRecorder("S", "F", 1, bm.SPECIES)
    out = bm.campaign_task("S1_ideal", "F", 3, 3, audit=True)["audit"]
    rows = out["design_candidate_scores"]
    assert rows, "no candidate scores recorded"
    assert any(int(r["eig_evaluated"]) == 1 for r in rows)
    for r in rows:
        if not int(r["eig_evaluated"]):
            assert not np.isfinite(float(r["eig_param"])), (
                "an unevaluated candidate reports an EIG - it must have been "
                "computed for the report, which would consume the RNG")
    # exactly one selected candidate per (round, mode)
    by_round = {}
    for r in rows:
        by_round.setdefault(r["round"], []).append(int(r["selected"]))
    for rnd, flags in by_round.items():
        assert sum(flags) == 1, f"round {rnd}: {sum(flags)} selected candidates"


def test_audit_payload_is_picklable_for_workers():
    out = bm.campaign_task("S1_ideal", "F", 3, 3, audit=True)
    back = pickle.loads(pickle.dumps(out))
    assert set(back["audit"]) == set(out["audit"])
    assert _rows_equal(back["rows"], out["rows"])


# ---- the tables say what they claim -------------------------------------- #
def test_audit_tables_are_populated_and_self_consistent():
    out = bm.campaign_task("S3_transport", "F", 2, 3, audit=True)["audit"]
    for t in ("design_history", "design_candidate_scores",
              "model_probabilities_long", "governor_diagnostics_long",
              "blind_predictions_long", "posterior_covariance_long",
              "identifiability_summary", "nmr_measurements_long",
              "nmr_calibration_by_seed", "resource_events_long",
              "controller_timing"):
        assert out[t], f"audit table '{t}' is empty"
    # model probabilities sum to one at every round
    by_round = {}
    for r in out["model_probabilities_long"]:
        by_round.setdefault(r["round"], []).append(float(r["probability"]))
    for rnd, ps in by_round.items():
        assert abs(sum(ps) - 1.0) < 1e-9, (rnd, sum(ps))
    # blind residuals reproduce the reported blind RMSE
    bp = out["blind_predictions_long"]
    rmse = float(np.sqrt(np.mean([r["squared_error_M2"] for r in bp])))
    rows = bm.campaign_task("S3_transport", "F", 2, 3)["rows"]
    assert abs(rmse - float(rows[-1]["blind_rmse_M"])) < 1e-9, (
        "blind_predictions_long must decompose the SAME number the "
        "benchmark reports, not a second estimate of it")


def test_rejected_acquisitions_are_recorded_not_just_counted():
    """A QC-rejected spectrum never reaches the posterior, so it exists in
    no posterior-derived table.  The acquisition log is the only place it
    can be audited; every row must declare its disposition."""
    out = bm.campaign_task("S3_transport", "F", 2, 3, audit=True)["audit"]
    acq = out["nmr_measurements_long"]
    assert acq
    dispositions = {r["disposition"] for r in acq}
    assert dispositions <= {"accepted", "accepted_after_reacquisition",
                            "failed_qc", "failed_qc_reacquiring", "rejected"}
    assert all(r["assimilated"] in (0, 1) for r in acq)
    # an assimilated acquisition must not carry a FAIL flag
    for r in acq:
        if int(r["assimilated"]):
            assert not int(r["qc_fail"]), (
                "a FAIL-flagged spectrum was marked assimilated - the QC "
                "gate is supposed to make that impossible")


def test_resource_events_reproduce_the_meter_totals():
    """The cumulative columns are re-derived from raw events, so they must
    land on the meter's own totals - the audit trail may not invent a second
    accounting."""
    out = bm.campaign_task("S1_ideal", "F", 3, 3, audit=True)
    ev = out["audit"]["resource_events_long"]
    assert ev
    last = ev[-1]
    rows = out["rows"]
    for key in ("time_s", "egda_mol", "energy_kJ", "nmr_acquisitions"):
        assert abs(float(last[f"cum_{key}"])
                   - float(rows[-1][key])) < 1e-6 * max(
                       1.0, abs(float(rows[-1][key]))), key


def test_identifiability_labels_which_matrix_it_used():
    """F is a Laplace posterior: its curvature includes the prior, so the
    eigenvalues are NOT Fisher information and must not be labelled as such."""
    f = bm.campaign_task("S1_ideal", "F", 3, 3, audit=True)["audit"]
    a = bm.campaign_task("S1_ideal", "A", 3, 3, audit=True)["audit"]
    assert {r["matrix_kind"] for r in f["identifiability_summary"]} == \
           {"posterior_precision"}
    assert {r["matrix_kind"] for r in a["identifiability_summary"]} == \
           {"fisher_information"}
    for r in f["identifiability_summary"]:
        assert r["effective_rank"] <= r["n_params"]


# ---- the representative NMR examples ------------------------------------- #
def test_nmr_examples_are_deterministic_and_decompose_the_fit():
    a = nex.spectra_for_plot(bm.ACQ, bm.NMR_NUISANCE_TRUE)
    b = nex.spectra_for_plot(bm.ACQ, bm.NMR_NUISANCE_TRUE)
    assert len(a) == 3
    for (n1, p1, o1, f1, r1, c1), (n2, _p2, o2, f2, _r2, _c2) in zip(a, b):
        assert n1 == n2
        assert np.array_equal(o1, o2) and np.array_equal(f1, f2)
        # the components add up to the fit
        assert np.max(np.abs(f1 - sum(c1.values()))) < 1e-9
    # and the example seed is independent of every campaign seed
    assert nex.EXAMPLE_SEED not in bm.MODES["publication"]["seeds"]


if __name__ == "__main__":
    import time
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        t = time.time()
        fn()
        print(f"PASS  {fn.__name__}  ({time.time() - t:.1f} s)")
    print(f"\n{len(fns)}/{len(fns)} audit-regression tests passed.")
