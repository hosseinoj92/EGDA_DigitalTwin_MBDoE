"""
Passive audit recorder for the publication workflow.

DESIGN RULE, and the whole reason this module is separate: recording must
never change what is computed.  The recorder therefore

  * draws NO random numbers - it never touches an RNG, so every downstream
    seeded decision is unaffected;
  * evaluates NO new objective - it stores numbers the controller had
    already computed for its own decision, never recomputing an EIG, a
    posterior or a candidate score (recomputing an EIG would consume the
    selector's RNG stream and silently change every later round);
  * takes NO branch - it is a sink with append-only methods and no return
    value that any caller reads.

Every instrumented call site is guarded by `if recorder is not None`, and
the default everywhere is None, so an un-audited run executes the original
code path exactly.  tests/test_audit_regression.py asserts that an audited
run and an un-audited run of the same seed agree to the bit.

What is recorded HERE is only what cannot be recovered afterwards: the
candidate alternatives the selector discards, and per-round wall-clock
timings.  Everything else in the audit trail (design history, model
probabilities, governor diagnostics, resource events, NMR fits, posterior
covariances, blind predictions) is derived post-campaign from the retained
result and laboratory objects - see audit_export.py.

A note on candidate coverage: the selector screens ALL candidates cheaply
and then evaluates the expensive Monte-Carlo EIG for only the top
`cfg.top_k` of them.  This recorder exports the top-N by screen score with
the EIG columns populated ONLY for the candidates that were genuinely
evaluated; the rest carry empty EIG fields.  Filling them in would mean
running the estimator on candidates the controller never considered, which
would consume RNG and change the campaign.  The `eig_evaluated` column
makes the distinction explicit in the CSV.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np


class AuditRecorder:
    """Append-only sink.  Holds plain Python/NumPy scalars so the payload is
    cheap to pickle back from a worker process."""

    #: how many screened candidates to keep per decision (selected + the
    #: best alternatives).  The publication spec asks for the selected
    #: candidate plus five alternatives.
    n_candidates_kept: int = 6

    def __init__(self, scenario: str, strategy: str, seed: int,
                 species: Sequence[str] = ()):
        self.scenario = scenario
        self.strategy = strategy
        self.seed = seed
        self.species = tuple(species)
        self.candidate_rows: List[Dict] = []
        self.timing_rows: List[Dict] = []
        self.acquisition_rows: List[Dict] = []
        #: round number the controller is CURRENTLY designing for; the
        #: selector does not know it, so the controller stamps it.
        self._round_for_decision: int = 0
        self._acq_order: int = 0

    # -- the controller stamps the round before asking the selector ------ #
    def set_decision_round(self, round_no: int) -> None:
        self._round_for_decision = int(round_no)

    # -- selector -------------------------------------------------------- #
    def record_candidates(self, governor_state: str, mode: str,
                          screened: Sequence,
                          evaluated: Dict[int, Dict],
                          chosen_index: Optional[int],
                          beta: float = float("nan")) -> None:
        """`screened` is the selector's own sorted list of
        (screen_score, u, z_positions, field); `evaluated` maps an index in
        that list to the EIG/cost/utility dict the selector computed for it;
        `chosen_index` is the index it selected.  Nothing is recomputed."""
        keep = min(self.n_candidates_kept, len(screened))
        for rank in range(keep):
            screen_score, u, zs, _field = screened[rank]
            ev = evaluated.get(rank, {})
            q_total = float(u.Q1_mL_min + u.Q2_mL_min)
            self.candidate_rows.append({
                "scenario": self.scenario, "strategy": self.strategy,
                "seed": self.seed, "round": self._round_for_decision,
                "rank": rank + 1,
                "selected": int(rank == chosen_index),
                "governor_state": governor_state,
                "design_mode": mode,
                "T_C": float(u.T_C),
                "Q1_mL_min": float(u.Q1_mL_min),
                "Q2_mL_min": float(u.Q2_mL_min),
                "Q_total_mL_min": q_total,
                "C_EGDA_M": float(u.C_EGDA_M),
                "C_cat_M": float(u.C_cat_M),
                "n_positions": int(len(zs)),
                "z_positions_m": ";".join(f"{float(z):.6g}" for z in zs),
                "screen_score": float(screen_score),
                # EIG columns are populated ONLY for candidates the
                # controller actually evaluated (top_k); see module docstring
                "eig_evaluated": int(bool(ev)),
                "eig_param": float(ev.get("eig_param", np.nan)),
                "eig_model": float(ev.get("eig_model", np.nan)),
                "resource_penalty": float(ev.get("cost", np.nan)),
                "utility_total": float(ev.get("utility", np.nan)),
                "beta_model_weight": float(beta),
            })

    # -- QC gate: one row per acquisition ATTEMPT, per species ----------- #
    def record_acquisition_part(self, round_no: int, u, part: Dict,
                                disposition: str, attempt: int) -> None:
        """`part` is the controller's per-position view of one acquisition:
        {"z", "y", "cov", "qc"}.  Recording a REJECTED acquisition here is
        the only way it survives at all - the QC gate drops it before
        assimilation, so it never appears in any posterior-derived table."""
        self._acq_order += 1
        qc = part.get("qc") or {}
        y = np.atleast_1d(np.asarray(part.get("y"), dtype=float))
        cov = part.get("cov")
        sig = (np.sqrt(np.maximum(np.diag(np.asarray(cov, dtype=float)), 0.0))
               if cov is not None else np.full(y.shape, np.nan))
        flags = list(qc.get("qc_flags", []))
        censored = set(qc.get("censored", []))
        names = self.species or tuple(f"y{i}" for i in range(len(y)))
        for i, sp in enumerate(names[:len(y)]):
            self.acquisition_rows.append({
                "scenario": self.scenario, "strategy": self.strategy,
                "seed": self.seed, "round": int(round_no),
                "acquisition_order": self._acq_order,
                "attempt": int(attempt),
                "disposition": disposition,
                "assimilated": int(disposition.startswith("accepted")),
                "z_m": float(part.get("z", np.nan)),
                "T_C": float(getattr(u, "T_C", np.nan)),
                "Q_total_mL_min": float(getattr(u, "Q1_mL_min", np.nan)
                                        + getattr(u, "Q2_mL_min", np.nan)),
                "C_EGDA_M": float(getattr(u, "C_EGDA_M", np.nan)),
                "C_cat_M": float(getattr(u, "C_cat_M", np.nan)),
                "species": sp,
                "conc_fitted_M": float(y[i]),
                "sigma_M": float(sig[i]) if i < len(sig) else float("nan"),
                "censored": int(sp in censored),
                "qc_flags": ";".join(str(f) for f in flags),
                "qc_fail": int(any(str(f).startswith("FAIL") for f in flags)),
                "residual_rms": float(qc.get("residual_rms", np.nan)),
                "fit_condition_number": float(
                    qc.get("condition_number", np.nan)),
                "observation_mode": str(qc.get("mode", "")),
            })

    def record_acquisitions(self, round_no: int, u, measurement,
                            disposition: str, attempt: int) -> None:
        """Whole-profile convenience for the ungated (direct-observation)
        path, where every position is accepted by construction."""
        if measurement is None:
            return
        n_s, n_z = len(measurement.species), measurement.n_z
        qc_all = (measurement.meta or {}).get("qc", [])
        for k in range(n_z):
            idx = [i * n_z + k for i in range(n_s)]
            cov = (measurement.cov_y[np.ix_(idx, idx)]
                   if measurement.cov_y is not None else None)
            self.record_acquisition_part(
                round_no, u,
                {"z": float(measurement.z_m[k]), "y": measurement.y[idx],
                 "cov": cov, "qc": qc_all[k] if k < len(qc_all) else {}},
                disposition, attempt)

    # -- controller ------------------------------------------------------ #
    def record_timing(self, round_no: int, **seconds: float) -> None:
        """Wall-clock only.  Reading a clock cannot change a result, and
        these columns are excluded from the regression comparison for the
        same reason per-campaign runtime_s is."""
        row = {"scenario": self.scenario, "strategy": self.strategy,
               "seed": self.seed, "round": int(round_no)}
        row.update({k: float(v) for k, v in seconds.items()})
        self.timing_rows.append(row)

    # -- payload --------------------------------------------------------- #
    def payload(self) -> Dict[str, List[Dict]]:
        """Picklable primitives only, for the trip back from a worker."""
        return {"design_candidate_scores": self.candidate_rows,
                "controller_timing": self.timing_rows,
                "nmr_measurements_long": self.acquisition_rows}
