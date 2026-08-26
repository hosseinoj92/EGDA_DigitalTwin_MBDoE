"""
The human-readable half of the benchmark: one self-contained HTML report.

It is a NARRATIVE VIEW OF SAVED DATA, never a source of truth.  Every number
it prints is read from the exported row dictionaries (the same objects the
CSVs contain), every figure is referenced from `figures/`, and the page says
so - the CSV and JSON files remain authoritative.

NO CONCLUSION IS HARD-CODED.  `derive_findings` builds each statement from
the run's own tables and phrases it conditionally: a strategy is described
as better than its reference only where the paired per-seed comparison says
so, with the win fraction and the confidence interval attached, and where it
is not better the report says that instead.  A claim that would rest on an
unreliable model evidence, on a scenario that mostly failed to complete, or
on fewer paired seeds than the threshold is reported as unsupported rather
than quietly stated.

The section order follows the framework's own argument - validation, then
each layer of realism, then the cross-cutting analyses - and sections whose
data does not exist in a given run are omitted rather than rendered empty.
"""

from __future__ import annotations

import datetime
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .campaign_html import _CSS, _e, _figure, _files, _fmt, _num, _table

#: narrative titles for the shipped scenarios; anything else falls back to
#: the scenario's own description, so an added scenario still gets a section
SCENARIO_TITLES = {
    "S1_ideal": "Ideal mathematical validation",
    "S2_nmr": "The impact of realistic NMR",
    "S3_transport": "Full transport + NMR",
    "S3ab_delay": "Transport ablation - delay and in-line reaction",
    "S3ab_rtd": "Transport ablation - residence-time dispersion",
    "S4a_ambiguity": "Model discrimination - genuinely ambiguous",
    "S4b_identifiable": "Model discrimination - identifiable",
    "S4c_out_of_domain": "Model discrimination - truth outside the family",
    "S5_inadequacy": "Model inadequacy and the governor",
    "S6_resources": "Information vs resource trade-off",
    "S7_spatial_modes": "Spatial sampling strategy",
}

#: fewer paired seeds than this and a comparison is reported as unsupported
MIN_PAIRS = 5
#: win fraction at or above which a difference is called consistent
CONSISTENT_WIN = 0.75


def _pct(x) -> str:
    v = _num({"v": x}, "v")
    return "-" if not np.isfinite(v) else f"{100.0 * v:.0f}%"


def _sc_title(scen: str, specs: Dict) -> str:
    spec = specs.get(scen)
    return SCENARIO_TITLES.get(scen, getattr(spec, "description", scen))


# ------------------------------------------------------------------------- #
# findings, derived from the tables
# ------------------------------------------------------------------------- #
def derive_findings(tables: Dict[str, List[Dict]], gov: Optional[Dict],
                    integrity: Optional[Dict], specs: Dict) -> List[Dict]:
    """Statements this run's data supports, each with its evidence.

    Returns dicts with `topic`, `text` and `support` ("supported",
    "unsupported", "caution"), so the report can render the weak ones as
    weak instead of dropping them - a comparison that did not reach
    significance is itself a result."""
    out: List[Dict] = []
    master = tables.get("benchmark_master_summary", []) or []
    paired = tables.get("paired_comparison_summary", []) or []
    rob = tables.get("robustness_summary", []) or []
    pp = tables.get("parameter_performance_summary", []) or []
    md = tables.get("model_discrimination_summary", []) or []

    # ---- 1. did the run complete? ------------------------------------- #
    if integrity is not None:
        if integrity.get("complete"):
            out.append({"topic": "run integrity", "support": "supported",
                        "text": f"The run produced every requested campaign: "
                                f"{integrity.get('n_campaigns', 0)} campaigns "
                                f"and {integrity.get('n_round_rows', 0)} "
                                f"per-round rows, with no missing seeds and "
                                f"no duplicate rows."})
        else:
            out.append({"topic": "run integrity", "support": "caution",
                        "text": "The run is INCOMPLETE: "
                                + "; ".join(integrity.get("problems", []))[:400]
                                + ". Every statement below is conditional on "
                                  "that."})
    worst = [r for r in master
             if np.isfinite(_num(r, "completion_rate"))
             and _num(r, "completion_rate") < 0.9]
    if worst:
        w = sorted(worst, key=lambda r: _num(r, "completion_rate"))[:4]
        out.append({
            "topic": "completion", "support": "caution",
            "text": "Some scenario/strategy combinations did not complete "
                    "every campaign, so their accuracy statistics rest on "
                    "the last valid posterior of paused runs: "
                    + ", ".join(f"{r['scenario']}/{r['strategy']} "
                                f"{_pct(_num(r, 'completion_rate'))}"
                                for r in w) + "."})

    # ---- 2. paired comparisons, per scenario --------------------------- #
    for r in sorted(paired, key=lambda q: (str(q["scenario"]),
                                           str(q["strategy"]))):
        if str(r["metric"]) != "param_err_pct":
            continue
        n = int(_num(r, "n_pairs", 0))
        win = _num(r, "win_fraction")
        med = _num(r, "difference_median")
        lo, hi = _num(r, "difference_ci_lo"), _num(r, "difference_ci_hi")
        scen, strat, ref = (str(r["scenario"]), str(r["strategy"]),
                            str(r["reference_strategy"]))
        if n < MIN_PAIRS:
            out.append({
                "topic": f"{scen}: {strat} vs {ref}", "support": "unsupported",
                "text": f"Only {n} paired seed(s) are available, which is "
                        f"below the {MIN_PAIRS} this report requires before "
                        f"describing a difference as consistent. The numbers "
                        f"are in the tables; no claim is made from them."})
            continue
        excl = bool(int(_num(r, "ci_excludes_zero", 0)))
        if excl and win >= CONSISTENT_WIN and med < 0:
            out.append({
                "topic": f"{scen}: {strat} vs {ref}", "support": "supported",
                "text": f"{strat} reached a lower final parameter error than "
                        f"{ref} on {_pct(win)} of {n} paired seeds (median "
                        f"difference {_fmt(med)} percentage points, bootstrap "
                        f"95% CI [{_fmt(lo)}, {_fmt(hi)}], which excludes "
                        f"zero). Because the seeds are common random numbers, "
                        f"the two campaigns saw identical noise, so the "
                        f"difference is attributable to the method."})
        elif excl and med > 0:
            out.append({
                "topic": f"{scen}: {strat} vs {ref}", "support": "supported",
                "text": f"{strat} was WORSE than {ref} on this scenario: "
                        f"median paired difference {_fmt(med)} percentage "
                        f"points (95% CI [{_fmt(lo)}, {_fmt(hi)}], excludes "
                        f"zero), winning on only {_pct(win)} of {n} seeds."})
        else:
            out.append({
                "topic": f"{scen}: {strat} vs {ref}", "support": "unsupported",
                "text": f"No consistent difference from {ref} on parameter "
                        f"error: median paired difference {_fmt(med)} "
                        f"percentage points with a 95% CI of [{_fmt(lo)}, "
                        f"{_fmt(hi)}] that includes zero, winning on "
                        f"{_pct(win)} of {n} seeds."})

    # ---- 3. per-parameter weak spots ----------------------------------- #
    weak = [r for r in pp
            if np.isfinite(_num(r, "abs_rel_error_pct_median"))
            and _num(r, "abs_rel_error_pct_median") > 50.0]
    if weak:
        worst_p = sorted(weak, key=lambda r:
                         -_num(r, "abs_rel_error_pct_median"))[:5]
        out.append({
            "topic": "parameter identifiability", "support": "caution",
            "text": "The aggregate parameter error hides at least one "
                    "poorly determined parameter. Worst cases: "
                    + ", ".join(f"{r['scenario']}/{r['strategy']} "
                                f"{r['param']} "
                                f"{_fmt(_num(r, 'abs_rel_error_pct_median'))}%"
                                for r in worst_p)
                    + ". See parameter_performance_summary.csv."})
    bad_cov = [r for r in pp
               if np.isfinite(_num(r, "ci95_coverage"))
               and int(_num(r, "n_coverage_evaluable", 0)) >= MIN_PAIRS
               and not int(_num(r, "coverage_is_vacuous", 0))
               and _num(r, "ci95_coverage") < 0.6]
    if bad_cov:
        out.append({
            "topic": "uncertainty calibration", "support": "caution",
            "text": "Some reported 95% intervals cover the true value far "
                    "less often than 95% of the time, i.e. the method is "
                    "more confident than it is right: "
                    + ", ".join(f"{r['scenario']}/{r['strategy']} "
                                f"{r['param']} {_pct(_num(r, 'ci95_coverage'))}"
                                for r in sorted(
                                    bad_cov,
                                    key=lambda q: _num(q, "ci95_coverage"))[:5])
                    + "."})
    vacuous = [r for r in pp if int(_num(r, "coverage_is_vacuous", 0))]
    if vacuous:
        out.append({
            "topic": "uncertainty calibration", "support": "caution",
            "text": f"{len(vacuous)} of {len(pp)} (scenario, strategy, "
                    f"parameter) combinations report a 95% interval wider "
                    f"than 1000% of the estimate. Their coverage is high "
                    f"only because the interval is unbounded - the parameter "
                    f"was not determined, and neither the coverage nor the "
                    f"interval should be quoted. Worst: "
                    + ", ".join(f"{r['scenario']}/{r['strategy']} {r['param']}"
                                for r in sorted(
                                    vacuous,
                                    key=lambda q: -_num(
                                        q, "rel_ci95_width_pct_median"))[:5])
                    + "."})
    good_cov = [r for r in pp
                if np.isfinite(_num(r, "ci95_coverage"))
                and not int(_num(r, "coverage_is_vacuous", 0))
                and int(_num(r, "n_coverage_evaluable", 0)) >= MIN_PAIRS]
    if good_cov and not bad_cov:
        cov = float(np.median([_num(r, "ci95_coverage") for r in good_cov]))
        out.append({
            "topic": "uncertainty calibration", "support": "supported",
            "text": f"Across every scenario, strategy and parameter, the "
                    f"median empirical coverage of the reported 95% interval "
                    f"is {_pct(cov)}, so the intervals are broadly "
                    f"consistent with the errors they accompany."})

    # ---- 4. governor calibration --------------------------------------- #
    if gov:
        fp = float(gov.get("false_inadequacy_campaign_rate", np.nan))
        alpha = float(gov.get("alpha_campaign_target", np.nan))
        det = float(gov.get("detection_probability", np.nan))
        n = gov.get("n_seeds", 0)
        if np.isfinite(fp) and np.isfinite(alpha):
            ok = fp <= alpha + 1e-12
            out.append({
                "topic": "governor calibration",
                "support": "supported" if ok else "caution",
                "text": (f"On well-specified campaigns the governor declared "
                         f"MODEL_INADEQUATE at a rate of {_pct(fp)} against a "
                         f"declared alpha of {alpha:g} over {n} seeds, so it "
                         f"is {'within' if ok else 'ABOVE'} its own false-"
                         f"alarm budget.")})
        if np.isfinite(det):
            out.append({
                "topic": "governor power",
                "support": "supported" if det >= 0.5 else "caution",
                "text": (f"On deliberately misspecified campaigns it detected "
                         f"the inadequacy in {_pct(det)} of {n} seeds"
                         + (f", first at round "
                            f"{_fmt(gov.get('median_detection_round'))} on "
                            f"average" if gov.get("median_detection_round")
                            else "") + ".")})

    # ---- 5. model discrimination --------------------------------------- #
    for r in md:
        scen, strat = str(r["scenario"]), str(r["strategy"])
        dec = _num(r, "decided_and_reliable_rate")
        unrel = _num(r, "apparent_certainty_unreliable_rate")
        und = _num(r, "undecided_rate")
        in_family = int(_num(r, "truth_in_candidate_family", 0))
        succ = _num(r, "selection_success_rate")
        if np.isfinite(unrel) and unrel > 0.1:
            out.append({
                "topic": f"{scen}: model evidence", "support": "caution",
                "text": f"{_pct(unrel)} of {strat} campaigns ended apparently "
                        f"certain about a model on a Laplace evidence flagged "
                        f"unreliable (a parameter resting on a box bound). "
                        f"Those probabilities must not be quoted."})
        if in_family and np.isfinite(succ):
            out.append({
                "topic": f"{scen}: model selection",
                "support": "supported" if succ >= 0.75 else "caution",
                "text": f"{strat} selected the tracked correct model in "
                        f"{_pct(succ)} of campaigns, with {_pct(dec)} decided "
                        f"on reliable evidence and {_pct(und)} ending "
                        f"undecided."})
        elif not in_family:
            out.append({
                "topic": f"{scen}: model selection", "support": "caution",
                "text": f"The hidden truth is OUTSIDE the candidate family in "
                        f"this scenario, so no selection can be correct; "
                        f"{_pct(und)} of {strat} campaigns ended undecided, "
                        f"which is the honest outcome here rather than a "
                        f"failure."})

    # ---- 6. robustness headline ---------------------------------------- #
    qc = [r for r in rob if np.isfinite(_num(r, "qc_rejection_rate"))]
    if qc:
        worst_qc = max(qc, key=lambda r: _num(r, "qc_rejection_rate"))
        out.append({
            "topic": "measurement QC", "support": "supported",
            "text": f"The QC gate rejected at most "
                    f"{_pct(_num(worst_qc, 'qc_rejection_rate'))} of "
                    f"acquisitions in any scenario/strategy "
                    f"({worst_qc['scenario']}/{worst_qc['strategy']}); "
                    f"rejected spectra never entered a posterior and are "
                    f"retained in the audit trail."})
    return out


# ------------------------------------------------------------------------- #
def build_report(path: str, *, meta: Dict, tables: Dict[str, List[Dict]],
                 figures: Dict[str, Optional[str]],
                 files: Dict[str, Optional[str]],
                 gov: Optional[Dict] = None,
                 integrity: Optional[Dict] = None,
                 specs: Optional[Dict] = None,
                 scenarios: Sequence[str] = ()) -> str:
    """Write the benchmark report.  Missing figures/files are skipped."""
    specs = specs or {}
    report_dir = os.path.dirname(os.path.abspath(path))
    master = tables.get("benchmark_master_summary", []) or []
    P: List[str] = []

    def add(s: str) -> None:
        if s:
            P.append(s)

    def fig(key: str, caption: str) -> None:
        add(_figure(figures.get(key), caption, report_dir))

    findings = derive_findings(tables, gov, integrity, specs)

    # ---- header --------------------------------------------------------- #
    add(f"<h1>EGDA advanced benchmark - {_e(meta.get('run_kind', ''))} run"
        f"</h1>")
    add('<p class="sub">'
        + " ".join(f'<span class="tag">{_e(t)}</span>' for t in
                   [f"mode {meta.get('mode', '')}",
                    f"{meta.get('n_seeds', '?')} seeds",
                    f"budget {meta.get('budget', '?')}",
                    f"{len(scenarios)} scenarios",
                    f"commit {meta.get('commit', 'unknown')}"])
        + "</p>")
    add('<div class="note">This page summarizes the run. The CSV and JSON '
        'files it links are the authoritative record: every figure and every '
        'number here is derived from them after the compute phase finished, '
        'and none of it influenced any scientific result.</div>')
    if str(meta.get("run_kind", "")) != "publication":
        add('<div class="note"><strong>This is a CODE-VALIDATION run, not '
            'publication numbers.</strong> It exists to show the framework '
            'executes and the reporting is coherent; seed counts and budgets '
            'are not those of the reported benchmark.</div>')
    add('<div class="firewall">Ground-truth firewall: the hidden kinetics '
        'exist because this is a simulation. Every quantity compared against '
        'them - parameter error, blind RMSE, interval coverage, the transport '
        'decomposition - is computed after a campaign has ended and is '
        'labelled as validation. No controller-side code can reach any of '
        'it.</div>')

    # ---- 1. configuration ------------------------------------------------ #
    add("<h2>1. Run identity and configuration</h2>")
    add(_table(["setting", "value"], [
        ["run kind", _e(meta.get("run_kind", ""))],
        ["run label", _e(meta.get("run_label", ""))],
        ["mode", _e(meta.get("mode", ""))],
        ["seeds", _e(meta.get("seeds", ""))],
        ["budget (reactor conditions per campaign)",
         _e(meta.get("budget", ""))],
        ["scenarios", _e(", ".join(scenarios))],
        ["git commit", _e(meta.get("commit", "")) +
         (" <strong>(working tree DIRTY)</strong>" if meta.get("dirty")
          else "")],
        ["framework version", _e(meta.get("framework_version", "v6"))],
        ["design space", _e(meta.get("design_space", ""))],
        ["reactor", _e(meta.get("reactor", ""))],
        ["transfer line", _e(meta.get("transfer", ""))],
        ["systematic allowance kappa", _e(meta.get("kappa", ""))],
        ["non-default feature switches", _e(meta.get("non_default", "none"))],
        ["parallelism", _e(meta.get("parallelism", ""))],
        ["total runtime", _e(meta.get("runtime", ""))],
    ]))
    add(_files([files.get("run_manifest"), files.get("benchmark_config"),
                files.get("features_resolved"),
                files.get("reactor_validity")], report_dir))

    # ---- 2. integrity ---------------------------------------------------- #
    add("<h2>2. Run integrity and completion</h2>")
    if integrity is not None:
        add(f"<p>{'The run is COMPLETE.' if integrity.get('complete') else 'The run is INCOMPLETE.'} "
            f"{integrity.get('n_campaigns', 0)} campaigns produced "
            f"{integrity.get('n_round_rows', 0)} per-round rows; "
            f"{integrity.get('n_duplicate_round_rows', 0)} duplicate rows and "
            f"{integrity.get('n_rows_with_nonfinite_param_err', 0)} rows with "
            f"a non-finite parameter error.</p>")
        if integrity.get("problems"):
            add('<div class="note">' + _e("; ".join(integrity["problems"]))
                + "</div>")
    if master:
        add(_table(["scenario", "strategy", "campaigns", "completed",
                    "faulted", "completion", "median rounds", "stop reasons"],
                   [[_e(r["scenario"]), _e(r["strategy"]),
                     _fmt(r.get("n_campaigns")), _fmt(r.get("n_completed")),
                     _fmt(r.get("n_faulted")),
                     _pct(_num(r, "completion_rate")),
                     _fmt(r.get("median_rounds_completed")),
                     _e(str(r.get("stop_reason_distribution", ""))[:80])]
                    for r in master]))
    add(_files([files.get("campaign_status"),
                files.get("run_integrity_report")], report_dir))

    # ---- 3. overall comparison ------------------------------------------- #
    add("<h2>3. Overall strategy comparison</h2>")
    fig("overview_accuracy",
        "Final accuracy (median and IQR across seeds) and campaign "
        "completion, by scenario and strategy.")
    for key, label in (("matrix_param_err_pct_median",
                        "Median final parameter error / % across the whole "
                        "scenario x strategy grid."),
                       ("matrix_blind_rmse_M_median",
                        "Median blind predictive RMSE / M."),
                       ("matrix_completion_rate",
                        "Campaign completion rate."),
                       ("matrix_max_rel_ci_pct_median",
                        "Median worst 95% relative confidence interval / %."),
                       ("matrix_median_time_s_s",
                        "Median campaign time / s."),
                       ("matrix_median_egda_mol_mol",
                        "Median EGDA consumed / mol."),
                       ("matrix_model_selection_success_rate",
                        "Model-selection success rate, where the scenario "
                        "defines a correct model.")):
        fig(key, label)
    if master:
        hdr = ["scenario", "strategy", "n", "param err / %", "IQR",
               "blind RMSE / M", "worst CI / %", "completion", "time / s",
               "EGDA / mol", "acquisitions"]
        body = [[_e(r["scenario"]), _e(r["strategy"]),
                 _fmt(r.get("n_campaigns")),
                 _fmt(r.get("param_err_pct_median")),
                 f"{_fmt(r.get('param_err_pct_q25'))}-"
                 f"{_fmt(r.get('param_err_pct_q75'))}",
                 _fmt(r.get("blind_rmse_M_median")),
                 _fmt(r.get("max_rel_ci_pct_median")),
                 _pct(_num(r, "completion_rate")),
                 _fmt(r.get("median_time_s_s")),
                 _fmt(r.get("median_egda_mol_mol")),
                 _fmt(r.get("median_nmr_acquisitions_count"))]
                for r in master]
        add(_table(hdr, body))
    add(_files([files.get("benchmark_master_summary"),
                files.get("strategy_table"),
                files.get("scenario_strategy_matrix")], report_dir))

    # ---- 4..N. one section per scenario that ran -------------------------- #
    n_sec = 3
    for scen in scenarios:
        rows_here = [r for r in master if r["scenario"] == scen]
        if not rows_here:
            continue
        n_sec += 1
        spec = specs.get(scen)
        add(f"<h2>{n_sec}. {_e(scen)} - {_e(_sc_title(scen, specs))}</h2>")
        add(f"<p>{_e(getattr(spec, 'description', ''))}</p>")
        add(_table(["strategy", "n", "param err / %", "blind RMSE / M",
                    "worst CI / %", "completion", "MODEL_INADEQUATE rate",
                    "QC rejection"],
                   [[_e(r["strategy"]), _fmt(r.get("n_campaigns")),
                     _fmt(r.get("param_err_pct_median")),
                     _fmt(r.get("blind_rmse_M_median")),
                     _fmt(r.get("max_rel_ci_pct_median")),
                     _pct(_num(r, "completion_rate")),
                     _pct(_num(r, "governor_inadequate_campaign_rate")),
                     _pct(_num(r, "qc_rejection_rate"))]
                    for r in rows_here]))
        for suffix, caption in (
                ("band_locf", "Median with IQR band across seeds "
                              "(last-observation-carried-forward, so paused "
                              "campaigns stay in the sample)."),
                ("conv_round", "Convergence against campaign round."),
                ("conv_acq", "Convergence against NMR acquisitions."),
                ("conv_time", "Convergence against campaign time."),
                ("efficiency", "Accuracy against cumulative resource, with "
                               "the reference strategy's final accuracy "
                               "marked."),
                ("trajectory", "What each method actually did, round by "
                               "round, for one seed."),
                ("paired", "Per-seed paired differences against the "
                           "reference strategy (common random numbers).")):
            fig(f"{suffix}_{scen}", caption)
        # figures that exist only for one particular scenario, keyed by the
        # scenario they belong to rather than by a name match
        for owner, key, caption in (
                ("S5_inadequacy", "governor_S5",
                 "Naive vs governed campaign on the misspecified scenario."),
                ("S6_resources", "pareto_S6",
                 "Information/resource Pareto front."),
                ("S6_resources", "pareto_S6_labeled",
                 "The same front with every strategy labelled."),
                ("S7_spatial_modes", "spatial_S7",
                 "Spatial sampling modes at equal acquisition budget."),
                ("S7_spatial_modes", "spatial_value",
                 "What choosing the sampling positions buys over equal "
                 "spacing.")):
            if owner == scen:
                fig(key, caption)
        fig(f"model_probs_{scen}",
            "Model probability, entropy and accuracy against round.")
        # findings that name this scenario
        fs = [f for f in findings if str(f["topic"]).startswith(scen)]
        if fs:
            add("<ul>" + "".join(
                f'<li><em>{_e(f["support"])}</em> - {_e(f["text"])}</li>'
                for f in fs) + "</ul>")

    # ---- cross-cutting analyses ------------------------------------------ #
    n_sec += 1
    add(f"<h2>{n_sec}. Parameter-by-parameter performance</h2>")
    add("<p>The aggregate parameter error is a geometric mean over the "
        "estimated parameters, so it can stay small while one parameter is "
        "never identified. These tables and figures separate them.</p>")
    for scen in scenarios:
        fig(f"parameter_performance_{scen}",
            f"Per-parameter accuracy, interval width, empirical coverage and "
            f"bound-hit rate - {scen}.")
    fig("precision_vs_accuracy",
        "Reported interval width against realized error. Points far above "
        "the diagonal report intervals smaller than their own error.")
    for key in list(figures):
        if key.startswith("param_band_"):
            fig(key, "Across-seed parameter convergence: the spread of the "
                     "estimates next to the interval the method reported.")
    pp = tables.get("parameter_performance_summary", []) or []
    if pp:
        add(_table(["scenario", "strategy", "parameter", "median |err| / %",
                    "median CI width / %", "coverage", "on bound",
                    "median |corr|", "most correlated with"],
                   [[_e(r["scenario"]), _e(r["strategy"]), _e(r["param"]),
                     _fmt(r.get("abs_rel_error_pct_median")),
                     _fmt(r.get("rel_ci95_width_pct_median")),
                     (_pct(_num(r, "ci95_coverage"))
                      + (" (vacuous)"
                         if int(_num(r, "coverage_is_vacuous", 0)) else "")),
                     _pct(_num(r, "frac_bound_active")),
                     _fmt(r.get("median_max_abs_correlation")),
                     _e(r.get("most_correlated_with", ""))]
                    for r in pp]))
        add('<div class="note">"vacuous" marks a coverage that is high only '
            'because the reported interval is wider than 1000% of the '
            'estimate: the parameter was not determined, so neither the '
            'interval nor its coverage is a result.</div>')
    add(_files([files.get("parameter_performance_summary"),
                files.get("benchmark_params")], report_dir))

    n_sec += 1
    add(f"<h2>{n_sec}. Experimental-design behaviour</h2>")
    add("<p>Where each method repeatedly chooses to collect information. "
        "Operating conditions are counted once per reactor condition and "
        "axial positions once per acquisition, so a ten-position profile "
        "does not outvote an adaptive single measurement.</p>")
    for scen in scenarios:
        for prefix, caption in (
                ("design_distribution", "Marginal distribution of every "
                                        "selected design variable."),
                ("design_joint", "Joint design-space occupancy, coloured by "
                                 "round."),
                ("spatial_density", "Axial sampling density along the "
                                    "reactor."),
                ("design_by_round", "Selected design against round (median "
                                    "and IQR across seeds).")):
            fig(f"{prefix}_{scen}", f"{caption} - {scen}")
    add(_files([files.get("design_selection_distribution"),
                files.get("design_selection_by_round"),
                files.get("design_trajectory")], report_dir))

    n_sec += 1
    add(f"<h2>{n_sec}. NMR and quantification performance</h2>")
    fig("quantification_validation",
        "Bias, RMSE and interval coverage of the NMR pathway against "
        "prepared standards - the measurement system's own validation, run "
        "outside any campaign.")
    fig("nmr_performance",
        "Reported uncertainty, QC failure and censoring by species and "
        "concentration regime, pooled over the campaigns.")
    fig("nmr_examples",
        "Representative simulated spectra with their deconvolution fit, "
        "components and residual (fixed example seed, generated after the "
        "run).")
    add('<div class="note">A campaign spectrum has no truth attached to it, '
        'so bias and coverage cannot be measured from campaign data. They '
        'come from the prepared-standard validation; the campaign tables '
        'report the uncertainty the pathway claimed and the QC outcomes it '
        'produced.</div>')
    add(_files([files.get("nmr_performance_summary"),
                files.get("quantification_validation"),
                files.get("nmr_by_round")], report_dir))

    trans = tables.get("transfer_effect_summary", []) or []
    if trans:
        n_sec += 1
        add(f"<h2>{n_sec}. Transfer-line effects</h2>")
        fig("transfer_ablation",
            "The ablation ladder: accuracy as delay, dispersion and "
            "carryover are switched on one at a time.")
        fig("transfer_decomposition",
            "Reactor sampling point -> NMR cell -> reported concentration, "
            "so transport distortion and quantification error can be told "
            "apart. Post-campaign validation only.")
        add(_table(["scenario", "strategy", "RTD", "in-line reaction",
                    "carryover", "T line / degC", "param err / %",
                    "blind RMSE / M"],
                   [[_e(r["scenario"]), _e(r["strategy"]),
                     _e(r.get("transfer_rtd", "")),
                     "yes" if int(_num(r, "transfer_react_in_line", 0))
                     else "no",
                     "yes" if int(_num(r, "transfer_carryover", 0)) else "no",
                     _fmt(r.get("transfer_T_line_C")),
                     _fmt(r.get("median_param_err_pct")),
                     _fmt(r.get("median_blind_rmse_M"))]
                    for r in trans]))
        add(_files([files.get("transfer_effect_summary"),
                    files.get("transfer_decomposition_summary")], report_dir))

    md = tables.get("model_discrimination_summary", []) or []
    if md:
        n_sec += 1
        add(f"<h2>{n_sec}. Model discrimination</h2>")
        fig("model_discrimination",
            "Decided on reliable evidence, decided on unreliable evidence, "
            "or undecided - three outcomes that must not be collapsed.")
        for scen in scenarios:
            fig(f"model_probs_reliability_{scen}",
                f"Model probability against round with the rounds of "
                f"unreliable evidence shaded - {scen}.")
        add(_table(["scenario", "strategy", "models", "tracked",
                    "truth in family", "decided+reliable", "unreliable",
                    "undecided", "selection success", "median entropy"],
                   [[_e(r["scenario"]), _e(r["strategy"]),
                     _fmt(r.get("n_candidate_models")),
                     _e(r.get("tracked_correct_model", "") or "-"),
                     "yes" if int(_num(r, "truth_in_candidate_family", 0))
                     else "NO",
                     _pct(_num(r, "decided_and_reliable_rate")),
                     _pct(_num(r, "apparent_certainty_unreliable_rate")),
                     _pct(_num(r, "undecided_rate")),
                     _pct(_num(r, "selection_success_rate")),
                     _fmt(r.get("median_final_model_entropy_nats"))]
                    for r in md]))
        add('<div class="note">A Laplace evidence computed at a parameter '
            'resting on a box bound is not valid evidence. Campaigns that '
            'ended apparently certain on such an evidence are counted '
            'separately and no model claim is made from them.</div>')
        add(_files([files.get("model_discrimination_summary"),
                    files.get("model_probabilities")], report_dir))

    n_sec += 1
    add(f"<h2>{n_sec}. QC, robustness and failure modes</h2>")
    fig("robustness_dashboard",
        "Completion, measurement-fault stops, QC rejection, reacquisition, "
        "governor declarations, bound hits, unreliable evidence and "
        "undecided campaigns.")
    rob = tables.get("robustness_summary", []) or []
    if rob:
        add(_table(["scenario", "strategy", "completion", "fault stops",
                    "QC rejection", "reacquisition", "bound hits",
                    "unreliable evidence", "top QC failure"],
                   [[_e(r["scenario"]), _e(r["strategy"]),
                     _pct(_num(r, "completion_rate")),
                     _fmt(r.get("n_measurement_fault_stops")),
                     _pct(_num(r, "qc_rejection_rate")),
                     _pct(_num(r, "reacquisition_rate")),
                     _pct(_num(r, "bound_hit_rate")),
                     _pct(_num(r, "unreliable_evidence_round_rate")),
                     _e(str(r.get("top_qc_failure_reason", ""))[:60])]
                    for r in rob]))
    add(_files([files.get("robustness_summary")], report_dir))

    n_sec += 1
    add(f"<h2>{n_sec}. Governor performance</h2>")
    fig("governor_validation",
        "False-alarm rate against the declared alpha, detection probability "
        "on misspecified campaigns, and when detection happened.")
    if gov:
        add(_table(["quantity", "value"], [
            ["seeds", _fmt(gov.get("n_seeds"))],
            ["false-inadequacy campaign rate",
             _pct(gov.get("false_inadequacy_campaign_rate"))],
            ["declared alpha", _fmt(gov.get("alpha_campaign_target"))],
            ["detection probability",
             _pct(gov.get("detection_probability"))],
            ["median detection round",
             _fmt(gov.get("median_detection_round"))],
            ["systematic allowance kappa used",
             _fmt(gov.get("systematic_allowance_used"))],
            ["median dispersion phi (well-specified)",
             _fmt(gov.get("median_dispersion_well_specified"))],
            ["detection carried by",
             _e(str(gov.get("detection_drivers", "")))],
            ["false alarms carried by",
             _e(str(gov.get("false_alarm_drivers", "")) or "none")],
        ]))
    add(_files([files.get("governor_validation")], report_dir))

    n_sec += 1
    add(f"<h2>{n_sec}. Resource efficiency</h2>")
    add("<p>Strategies are compared three ways, because a single comparison "
        "at equal round count assumes a round costs the same for every "
        "method - which is the assumption under test.</p>")
    for scen in scenarios:
        fig(f"resource_summary_{scen}",
            f"What one campaign cost, per strategy - {scen}.")
        fig(f"resource_components_{scen}",
            f"Accuracy against each resource separately - {scen}.")
    add(_files([files.get("resource_summary"),
                files.get("budget_to_target_summary"),
                files.get("accuracy_at_matched_resource_summary"),
                files.get("headline_comparison")], report_dir))
    head = tables.get("headline_comparison", []) or []
    if head:
        add("<h3>Budget to target and accuracy at matched resource</h3>")
        add(_table(["scenario", "strategy", "vs", "tightest target reached "
                    "by half the seeds", "material ratio", "time ratio",
                    "accuracy gain at equal material",
                    "P(better at equal material)"],
                   [[_e(r["scenario"]), _e(r["strategy"]),
                     _e(r.get("reference_strategy", "")),
                     _fmt(r.get("tightest_target_reached_by_half")),
                     _fmt(r.get("resource_ratio_egda_mol")),
                     _fmt(r.get("resource_ratio_time_s")),
                     _fmt(r.get("accuracy_gain_at_equal_material")),
                     _pct(_num(r, "p_better_at_equal_material"))]
                    for r in head]))

    n_sec += 1
    add(f"<h2>{n_sec}. Paired statistical comparisons</h2>")
    add("<p>The benchmark runs common random numbers, so the same seed gives "
        "both strategies identical measurement noise, fault draws and design "
        "randomness. The per-seed difference is therefore a genuine paired "
        "observation, and the win fraction is reported next to the median "
        "because they can disagree.</p>")
    ps = tables.get("paired_comparison_summary", []) or []
    if ps:
        add(_table(["scenario", "strategy", "vs", "metric", "n pairs",
                    "median difference", "95% CI", "CI excludes 0",
                    "win fraction"],
                   [[_e(r["scenario"]), _e(r["strategy"]),
                     _e(r.get("reference_strategy", "")), _e(r["metric"]),
                     _fmt(r.get("n_pairs")),
                     _fmt(r.get("difference_median")),
                     f"[{_fmt(r.get('difference_ci_lo'))}, "
                     f"{_fmt(r.get('difference_ci_hi'))}]",
                     "yes" if int(_num(r, "ci_excludes_zero", 0)) else "no",
                     _pct(_num(r, "win_fraction"))]
                    for r in ps]))
    add(_files([files.get("paired_seed_differences"),
                files.get("paired_comparison_summary"),
                files.get("paired_comparisons")], report_dir))

    # ---- conclusions ------------------------------------------------------ #
    n_sec += 1
    add(f"<h2>{n_sec}. What this run supports</h2>")
    add('<div class="note">Each statement below was generated from this '
        'run\'s own tables, with the evidence attached. Statements marked '
        '<em>unsupported</em> are results too: they say the data does not '
        'establish the claim.</div>')
    for support, heading in (("supported", "Supported by this run"),
                             ("caution", "Qualified - read with care"),
                             ("unsupported", "Not established by this run")):
        fs = [f for f in findings if f["support"] == support]
        if not fs:
            continue
        add(f"<h3>{_e(heading)}</h3>")
        add("<ul>" + "".join(f'<li><strong>{_e(f["topic"])}</strong> - '
                             f'{_e(f["text"])}</li>' for f in fs) + "</ul>")

    add(f"<footer>Generated "
        f"{_e(datetime.datetime.now().isoformat(timespec='seconds'))} by "
        f"run_advanced_benchmark.py - reporting only, after the compute "
        f"phase finished. The CSV and JSON files in <code>data/</code>, "
        f"<code>config/</code> and <code>audit/</code> are the authoritative "
        f"record; wall-clock fields are the only ones that differ between "
        f"two runs of the same configuration.</footer>")

    doc = (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           f"<meta name=\"viewport\" content=\"width=device-width, "
           f"initial-scale=1\">"
           f"<title>Benchmark report - {_e(meta.get('run_label', 'run'))}"
           f"</title><style>{_CSS}</style></head><body><main>"
           + "".join(P) + "</main></body></html>")
    os.makedirs(report_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"saved: {path}")
    return path
