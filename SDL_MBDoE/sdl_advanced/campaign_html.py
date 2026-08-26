"""
The human-readable half of the campaign record: one self-contained HTML page.

It is a NARRATIVE VIEW, never a source of truth.  Every number it prints is
read from the exported row dictionaries (the same objects the CSVs contain),
every figure is referenced from `figures/`, and the page says so: the CSV and
JSON files remain authoritative, and anything summarized here can be checked
against them.

The page follows the campaign in the order it happened - configuration, the
experiments it chose, what it measured, what it inferred, how certain it
became, what it concluded about the model, what the QC gate and the governor
had to say, what it spent, and how the strategies compare at the end - so it
can be read as an account of the run rather than a pile of plots.

Sections whose data does not exist for a given scenario or strategy are
omitted entirely rather than rendered empty.
"""

from __future__ import annotations

import datetime
import html
import os
from typing import Dict, List, Optional, Sequence

import numpy as np

_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1.5rem 4rem; font-size: 15px;
       font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                    Helvetica, Arial, sans-serif;
       line-height: 1.55; color: #1c1c1c; background: #ffffff; }
main { max-width: 1100px; margin: 0 auto; }
h1 { font-size: 1.7rem; margin: 0 0 .3rem; letter-spacing: -.01em; }
h2 { font-size: 1.2rem; margin: 2.6rem 0 .6rem; padding-bottom: .3rem;
     border-bottom: 2px solid #1b3a5c; color: #1b3a5c; }
h3 { font-size: 1rem; margin: 1.6rem 0 .4rem; color: #333; }
p, li { margin: .4rem 0; }
.sub { color: #555; margin: 0 0 1.4rem; }
.tag { display: inline-block; padding: .12rem .5rem; margin-right: .35rem;
       border-radius: .5rem; background: #eef2f7; color: #1b3a5c;
       font-size: .8rem; font-weight: 600; }
.note { background: #fbf7ee; border-left: 4px solid #c98a3a;
        padding: .6rem .9rem; margin: 1rem 0; font-size: .87rem;
        color: #4a3a1c; }
.firewall { background: #f2f7f4; border-left: 4px solid #2a7f62;
            padding: .6rem .9rem; margin: 1rem 0; font-size: .87rem;
            color: #1e4636; }
table { border-collapse: collapse; width: 100%; margin: .8rem 0 1.2rem;
        font-size: .84rem; }
th, td { border-bottom: 1px solid #e3e6ea; padding: .35rem .5rem;
         text-align: right; white-space: nowrap; }
th { background: #f6f8fa; text-align: right; font-weight: 600;
     color: #333; }
th:first-child, td:first-child { text-align: left; }
figure { margin: 1.2rem 0 1.6rem; }
figure img { width: 100%; height: auto; border: 1px solid #e3e6ea;
             border-radius: 4px; background: #fff; }
figcaption { font-size: .82rem; color: #555; margin-top: .4rem; }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
              font-size: .84rem; }
.files a { display: inline-block; margin: .1rem .6rem .1rem 0;
           font-size: .82rem; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e3e6ea;
         color: #777; font-size: .8rem; }
@media (prefers-color-scheme: dark) {
  body { background: #14181d; color: #e6e6e6; }
  h2 { color: #9dc0e4; border-color: #9dc0e4; }
  h3 { color: #cfd6de; }
  .sub, figcaption, footer { color: #9aa4b0; }
  .tag { background: #1e2a38; color: #9dc0e4; }
  .note { background: #2a2318; border-color: #c98a3a; color: #e8d5b0; }
  .firewall { background: #17251f; border-color: #2a7f62; color: #bfe0d0; }
  th { background: #1b2027; color: #cfd6de; }
  th, td { border-color: #2a3038; }
  figure img { border-color: #2a3038; background: #1b2027; }
}
"""


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _fmt(v, digits: int = 4) -> str:
    """Numbers a reader can scan: significant digits, not float noise."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return _e(v)
    if not np.isfinite(f):
        return "-"
    if f == 0.0:
        return "0"
    a = abs(f)
    if a >= 1e5 or a < 1e-3:
        return f"{f:.{digits - 1}e}"
    if a >= 100:
        return f"{f:.1f}"
    return f"{f:.{digits}g}"


def _table(headers: Sequence[str], rows: Sequence[Sequence]) -> str:
    if not rows:
        return ""
    out = ["<table><thead><tr>"]
    out += [f"<th>{_e(h)}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{c if isinstance(c, str) else _fmt(c)}</td>"
                                    for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _figure(path: Optional[str], caption: str,
            report_dir: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    rel = os.path.relpath(path, report_dir).replace(os.sep, "/")
    return (f'<figure><img src="{_e(rel)}" alt="{_e(caption)}">'
            f'<figcaption>{_e(caption)}</figcaption></figure>')


def _files(paths: Sequence[Optional[str]], report_dir: str) -> str:
    links = []
    for p in paths:
        if not p or not os.path.exists(p):
            continue
        rel = os.path.relpath(p, report_dir).replace(os.sep, "/")
        links.append(f'<a href="{_e(rel)}"><code>{_e(os.path.basename(p))}'
                     f'</code></a>')
    if not links:
        return ""
    return ('<p class="files">authoritative data: ' + " ".join(links)
            + "</p>")


def _num(row: Dict, key: str, default=np.nan) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _last_per_strategy(rows: Sequence[Dict]) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for r in rows:
        s = str(r.get("strategy", ""))
        if s not in out or _num(r, "round") >= _num(out[s], "round"):
            out[s] = r
    return out


# ------------------------------------------------------------------------- #
def build_report(path: str, *, meta: Dict, tables: Dict[str, List[Dict]],
                 figures: Dict[str, Optional[str]],
                 files: Dict[str, Optional[str]],
                 has_truth: bool) -> str:
    """Write the campaign report.

    `meta`   scenario/strategy/seed/configuration facts to print at the top
    `tables` the exported row lists, keyed by their CSV base name
    `figures`/`files` paths on disk, keyed by a short name; missing or
             non-existent entries are silently skipped, which is how a
             scenario without (say) a transfer line ends up with no
             transport section rather than an empty one.
    """
    report_dir = os.path.dirname(os.path.abspath(path))
    rounds = tables.get("campaign_rounds", []) or []
    params = tables.get("kinetic_parameters", []) or []
    summary = tables.get("strategy_comparison", []) or []
    strategies = list(meta.get("strategies", []))
    P: List[str] = []

    def add(s: str) -> None:
        if s:
            P.append(s)

    # ---- header ---------------------------------------------------------- #
    add(f"<h1>Autonomous campaign record - {_e(meta.get('scenario', ''))}</h1>")
    add('<p class="sub">'
        + " ".join(f'<span class="tag">{_e(t)}</span>' for t in
                   [f"scenario {meta.get('scenario', '')}",
                    "strategies " + ", ".join(strategies),
                    f"seed {meta.get('seed', '')}",
                    f"budget {meta.get('budget', '')} conditions",
                    f"observation {meta.get('observation_mode', '')}"])
        + f"<br>{_e(meta.get('description', ''))}</p>")
    add('<div class="note">This page summarizes the run. The CSV and JSON '
        'files it links are the authoritative record - every figure and '
        'every number here is derived from them, after the campaign '
        'finished, and none of it influenced any decision the controller '
        'made.</div>')
    if has_truth:
        add('<div class="firewall">This is a SIMULATION campaign, so the '
            'true kinetics are known. Every quantity compared against them '
            '(parameter error, blind RMSE, the truth reference lines, the '
            'transfer-line decomposition) is computed after the campaign '
            'ended and is labelled as validation. No controller-side code '
            'can reach any of it.</div>')

    # ---- 1. configuration ------------------------------------------------ #
    add("<h2>1. Configuration</h2>")
    cfg_rows = [
        ["scenario", _e(meta.get("scenario", ""))],
        ["description", _e(meta.get("description", ""))],
        ["strategies", _e(", ".join(strategies))],
        ["seed", _e(meta.get("seed", ""))],
        ["budget (reactor conditions per strategy)", _e(meta.get("budget", ""))],
        ["observation mode", _e(meta.get("observation_mode", ""))],
        ["spatial sampling mode(s)", _e(meta.get("spatial_modes", ""))],
        ["design space", _e(meta.get("design_space", ""))],
        ["reactor", _e(meta.get("reactor", ""))],
        ["transfer line", _e(meta.get("transfer", ""))],
        ["NMR", _e(meta.get("nmr", ""))],
        ["non-default feature switches", _e(meta.get("non_default", "none"))],
        ["framework version", _e(meta.get("framework_version", ""))],
        ["run kind", _e(meta.get("run_kind", ""))],
    ]
    add(_table(["setting", "value"], cfg_rows))
    add(_files([files.get("config_used"), files.get("features_resolved")],
               report_dir))

    # ---- 2. experimental decisions --------------------------------------- #
    add("<h2>2. Experimental decisions</h2>")
    add("<p>What the controller chose to run, and why it chose it.</p>")
    add(_figure(figures.get("spatial_value"),
                "Reference: why axial positions are not equally valuable - "
                "the true profile at a curved operating point, equal vs "
                "optimized positions, and the information density over z. "
                "Generated after the campaign on its own fixed seed.",
                report_dir))
    add(_figure(figures.get("conditions"),
                "Conditions selected per round, by strategy.", report_dir))
    add(_figure(figures.get("positions"),
                "Axial sampling positions selected per round.", report_dir))
    for s in strategies:
        add(_figure(figures.get(f"design_{s}"),
                    f"Candidate ranking behind each decision - strategy {s}.",
                    report_dir))
        add(_figure(figures.get(f"spatial_{s}"),
                    f"Information over candidate positions - strategy {s}.",
                    report_dir))
    if rounds:
        hdr = ["strategy", "round", "T / degC", "Q / mL/min", "cat / M",
               "EGDA / M", "n z", "design mode", "utility",
               "objective terms", "term 1", "term 2"]
        body = [[_e(r["strategy"]), _fmt(r["round"]), _fmt(r.get("T_C")),
                 _fmt(r.get("Q_total_mL_min")), _fmt(r.get("C_cat_M")),
                 _fmt(r.get("C_EGDA_M")), _fmt(r.get("n_positions")),
                 _e(r.get("design_mode", "")),
                 _fmt(r.get("selected_utility")),
                 _e(str(r.get("design_objective_term_names", "")
                        or "-").replace(";", " / ")),
                 _fmt(r.get("design_objective_term_1")),
                 _fmt(r.get("design_objective_term_2"))]
                for r in rounds]
        add(_table(hdr, body))
        add('<div class="note">The selector\'s two objective terms are not '
            'the same quantity in every mode - in <code>eig</code> mode they '
            'are the parameter and model-discrimination expected information '
            'gains, in <code>diagnostic</code> mode the model disagreement '
            'and the exploration stress - so the column next to them names '
            'which pair is being shown. A round the controller did not '
            'design (a fixed design, or the seed experiment) has no '
            'objective at all.</div>')
    add(_files([files.get("campaign_rounds"),
                files.get("design_candidate_scores"),
                files.get("spatial_candidate_scores")], report_dir))

    # ---- 3. measurements -------------------------------------------------- #
    add("<h2>3. Measurements</h2>")
    meas = tables.get("measurements", []) or []
    conc = tables.get("concentrations", []) or []
    if meas or conc:
        n_attempt = len({(r.get("strategy"), r.get("round"),
                          r.get("acquisition_order"), r.get("attempt"))
                         for r in meas})
        n_acc = len({(r.get("strategy"), r.get("round"),
                      r.get("acquisition_order"))
                     for r in conc})
        add(f"<p>{n_attempt} acquisition attempts recorded across all "
            f"strategies, of which {n_acc} entered a posterior. Rejected and "
            f"re-acquired spectra are kept in <code>measurements.csv</code> "
            f"so the full measurement history can be reconstructed - the QC "
            f"gate drops them before assimilation, so they appear nowhere "
            f"else.</p>")
    for s in strategies:
        add(_figure(figures.get(f"profiles_{s}"),
                    f"Measured concentration profiles with 95% intervals and "
                    f"the model current at that round - strategy {s}.",
                    report_dir))
        add(_figure(figures.get(f"nmr_{s}"),
                    f"Representative deconvolutions from the campaign - "
                    f"strategy {s}.", report_dir))
        add(_figure(figures.get(f"transfer_{s}"),
                    f"Reactor point vs NMR cell vs reported concentration - "
                    f"strategy {s}.", report_dir))
    add(_figure(figures.get("recovery"),
                "Reference: quantification recovery of the NMR pathway over "
                "random compositions - truth vs deconvolved concentration "
                "with the reported uncertainty. Instrument-level validation "
                "on its own generator, not campaign data.", report_dir))
    add(_files([files.get("measurements"), files.get("concentrations"),
                files.get("transfer_history"), files.get("spectra_index")],
               report_dir))

    # ---- 4. kinetic inference -------------------------------------------- #
    add("<h2>4. Kinetic inference</h2>")
    add(_figure(figures.get("parameters"),
                "Parameter estimates and 95% intervals against round.",
                report_dir))
    if has_truth:
        add(_figure(figures.get("param_error"),
                    "Relative parameter error against round - post-campaign "
                    "validation only.", report_dir))
    finals = _last_per_strategy(params) if params else {}
    if params:
        by_strat: Dict[str, List[Dict]] = {}
        for r in params:
            by_strat.setdefault(str(r["strategy"]), []).append(r)
        hdr = ["strategy", "parameter", "unit", "estimate", "95% lo",
               "95% hi", "CI width / %", "bound active"]
        if has_truth:
            hdr += ["true value", "error / %", "covered"]
        body = []
        for s in strategies:
            rr = by_strat.get(s, [])
            if not rr:
                continue
            last = max(_num(r, "round") for r in rr)
            for r in [x for x in rr if _num(x, "round") == last]:
                row = [_e(s), _e(r["param"]), _e(r.get("unit", "")),
                       _fmt(r.get("estimate_natural")),
                       _fmt(r.get("ci95_lo_natural")),
                       _fmt(r.get("ci95_hi_natural")),
                       _fmt(r.get("rel_ci95_width_pct")),
                       "yes" if int(_num(r, "bound_active", 0)) else "no"]
                if has_truth:
                    row += [_fmt(r.get("true_value_natural")),
                            _fmt(r.get("rel_error_pct_vs_truth")),
                            "yes" if _num(r, "covered_by_ci95") == 1
                            else "no"]
                body.append(row)
        add("<h3>Final parameter estimates</h3>")
        add(_table(hdr, body))
    add(_files([files.get("kinetic_parameters")], report_dir))

    # ---- 5. uncertainty and identifiability ------------------------------- #
    add("<h2>5. Uncertainty and identifiability</h2>")
    add(_figure(figures.get("uncertainty"),
                "Interval widths, worst parameter correlation and the "
                "information accumulated in the posterior.", report_dir))
    for s in strategies:
        add(_figure(figures.get(f"correlation_{s}"),
                    f"Posterior correlation, early / middle / final - "
                    f"strategy {s}.", report_dir))
    last_round = _last_per_strategy(rounds)
    if last_round:
        hdr = ["strategy", "final round", "worst 95% CI / %",
               "worst |correlation|", "parameters on a bound"]
        body = [[_e(s), _fmt(r.get("round")),
                 _fmt(r.get("max_rel_ci_pct")),
                 _fmt(r.get("corr_max_offdiag")),
                 _e(r.get("bound_active_params", "") or "none")]
                for s, r in last_round.items()]
        add(_table(hdr, body))
    add(_files([files.get("posterior_covariance"),
                files.get("identifiability")], report_dir))

    # ---- 6. model discrimination ------------------------------------------ #
    probs = tables.get("model_probabilities", []) or []
    if probs:
        add("<h2>6. Model discrimination</h2>")
        add(_figure(figures.get("model_probs"),
                    "Candidate-model probability against round.", report_dir))
        add('<div class="note">A Laplace evidence computed at a parameter '
            'resting on a box bound is not valid evidence, and a probability '
            'derived from it must not be read as one. The '
            '<code>evidence_reliable</code> and '
            '<code>probs_reliable_all_models</code> columns travel with '
            'every probability for exactly that reason - filter on them '
            'before making a model claim.</div>')
        hdr = ["strategy", "final round", "selected model", "probability",
               "evidence reliable"]
        body = []
        for s in strategies:
            rr = [r for r in probs if r["strategy"] == s]
            if not rr:
                continue
            last = max(_num(r, "round") for r in rr)
            for r in rr:
                if _num(r, "round") == last and int(_num(r, "is_selected_model",
                                                         0)):
                    body.append([_e(s), _fmt(last), _e(r["model"]),
                                 _fmt(r.get("probability")),
                                 "yes" if int(_num(r, "evidence_reliable", 0))
                                 else "NO"])
        add(_table(hdr, body))
        add(_files([files.get("model_probabilities")], report_dir))

    # ---- 7. QC and governor ----------------------------------------------- #
    qc = tables.get("qc_history", []) or []
    gov = tables.get("governor_history", []) or []
    if qc or gov:
        add("<h2>7. Measurement QC and model-adequacy governor</h2>")
        add(_figure(figures.get("qc"),
                    "Acquisition dispositions, the gate's persistence "
                    "counters and the reasons spectra failed.", report_dir))
        add(_figure(figures.get("governor"),
                    "Realized misfit, the adequacy test and the declared "
                    "state.", report_dir))
        if qc:
            hdr = ["strategy", "rejected", "reacquired", "gate tripped",
                   "stop reason"]
            body = []
            for s in strategies:
                rr = [r for r in qc if r["strategy"] == s]
                if not rr:
                    continue
                body.append([_e(s),
                             _fmt(sum(_num(r, "n_rejected") for r in rr)),
                             _fmt(sum(_num(r, "n_reacquired") for r in rr)),
                             "YES" if int(_num(rr[-1],
                                               "gate_tripped_this_campaign",
                                               0)) else "no",
                             _e(rr[-1].get("stop_reason", "")
                                or "budget exhausted")])
            add(_table(hdr, body))
        add(_files([files.get("qc_history"), files.get("governor_history")],
                   report_dir))

    # ---- 8. resources ------------------------------------------------------ #
    add("<h2>8. Resource consumption</h2>")
    add(_figure(figures.get("resources"),
                "Cumulative simulated laboratory cost against round.",
                report_dir))
    if summary:
        hdr = ["strategy", "time / s", "EGDA / mol", "waste / mL",
               "energy / kJ", "NMR acquisitions", "reacquisitions",
               "spatial samples", "capillary travel / m"]
        body = [[_e(r["strategy"]), _fmt(r.get("time_s")),
                 _fmt(r.get("egda_mol")), _fmt(r.get("waste_mL")),
                 _fmt(r.get("energy_kJ")), _fmt(r.get("n_nmr_acquisitions")),
                 _fmt(r.get("n_nmr_reacquisitions")),
                 _fmt(r.get("n_spatial_samples")),
                 _fmt(r.get("capillary_travel_m"))] for r in summary]
        add(_table(hdr, body))
    add(_files([files.get("resource_history"), files.get("resource_events"),
                files.get("controller_timing")], report_dir))

    # ---- 9. final comparison ----------------------------------------------- #
    add("<h2>9. Final strategy comparison</h2>")
    add(_figure(figures.get("comparison"),
                "End-of-campaign scoreboard for the strategies that ran.",
                report_dir))
    if summary:
        hdr = ["strategy", "rounds", "conditions", "spatial samples"]
        if has_truth:
            hdr += ["parameter error / %", "blind RMSE / M"]
        hdr += ["worst 95% CI / %", "best model", "stop reason"]
        body = []
        for r in summary:
            row = [_e(r["strategy"]),
                   f"{int(_num(r, 'rounds_completed'))}/"
                   f"{int(_num(r, 'rounds_planned'))}",
                   _fmt(r.get("n_conditions_run")),
                   _fmt(r.get("n_spatial_samples"))]
            if has_truth:
                row += [_fmt(r.get("param_err_pct_final_vs_truth")),
                        _fmt(r.get("blind_rmse_M_final_vs_truth"))]
            row += [_fmt(r.get("max_rel_ci_pct_final")),
                    _e(r.get("best_model_final", "")),
                    _e(r.get("stop_reason", ""))]
            body.append(row)
        add(_table(hdr, body))
    add(_files([files.get("strategy_comparison"),
                files.get("blind_predictions")], report_dir))

    add(f"<footer>Generated {_e(datetime.datetime.now().isoformat(timespec='seconds'))}"
        f" by run_advanced_campaign.py - reporting only, after the campaign "
        f"finished. The CSV and JSON files in <code>data/</code>, "
        f"<code>config/</code> and <code>spectra/</code> are the "
        f"authoritative record. Every one of them is byte-reproducible for "
        f"this seed and configuration except the two wall-clock fields, "
        f"which measure the run rather than the chemistry: "
        f"<code>controller_timing.csv</code> and the "
        f"<code>runtime_s_wall_clock</code> column of "
        f"<code>strategy_comparison.csv</code>.</footer>")

    doc = (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           f"<meta name=\"viewport\" content=\"width=device-width, "
           f"initial-scale=1\">"
           f"<title>Campaign record - {_e(meta.get('scenario', ''))}</title>"
           f"<style>{_CSS}</style></head><body><main>"
           + "".join(P) + "</main></body></html>")
    os.makedirs(report_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"saved: {path}")
    return path
