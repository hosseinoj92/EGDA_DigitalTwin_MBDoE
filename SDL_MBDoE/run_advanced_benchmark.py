"""
Main EGDA advanced benchmark (corrected framework, v3 outputs).

Runs the scenario suite of sdl_advanced.benchmark in one of three modes
("smoke" seconds / "demo" default / "publication" many seeds), with
common-random-number seed lists shared across strategies, and writes a NEW
results directory (never silently overwriting the previous reference run).

THE OUTPUT TREE.  One root - <results_root>/<run_kind>/<run_label>, or an
explicit CONFIG["outdir"] - organized as:

  config/    run_manifest.json, benchmark_config.json, features_resolved.json,
             reactor_validity.csv/.txt, geometry_sizing.csv,
             equilibrium_observability.csv   - what the run was asked to do
  data/      the RESULT tables: benchmark_rounds.csv, benchmark_params.csv,
             campaign_status.csv, strategy_table.csv/.txt,
             paired_comparisons.csv, quantification_validation.csv,
             governor_validation.json, convergence_summary.csv,
             run_integrity_report.json, plus the run-level summaries
             (benchmark_master_summary, parameter_performance_summary,
             design_selection_distribution, paired_seed_differences,
             robustness_summary, model_discrimination_summary,
             nmr_performance_summary, transfer_effect_summary,
             resource_summary, scenario_strategy_matrix) and
             data/comparison/ (budget-to-target, matched resource,
             design trajectories, headline comparison)
  figures/   overview/ scenarios/ parameters/ design/ measurement/
             robustness/ resources/
  audit/     the RAW per-campaign audit trail (design/, inference/,
             governor/, measurement/, resources/, validation/), the NMR
             examples and the reproducibility manifest
  report/    benchmark_report.html - the readable account, generated
             entirely from the files above

RAW BEATS SUMMARY.  Everything under audit/ and the per-round tables in
data/ are authoritative; every summary is an aggregate of them, produced
after the compute phase by pure functions of saved rows.  The reporting
layer draws no random number beyond the fixed-seed bootstraps the benchmark
already uses for its own confidence intervals, so it cannot move a
scientific result - tests/test_audit_regression.py asserts that for matched
seeds.

Parallelism: set CONFIG["n_workers"].  Campaigns are independent and each is
a pure function of (scenario, strategy, seed, budget), so they are spread
over processes and reassembled in submission order - every saved file is
identical to a one-core run except the wall-clock telemetry (per-campaign
`runtime_s`, per-scenario `runtimes_s`), which is what more cores are meant
to change.  Verified end to end by tests/test_parallel.py.  Works the same
on macOS (Apple Silicon included), Windows and Linux; see
sdl_advanced/parallel.py for how the identity is maintained.

IDE workflow: edit CONFIG and press Run.
"""

from __future__ import annotations

import os

# --------------------------------------------------------------------- #
# Numerical threads are pinned BEFORE numpy/scipy are imported, because a
# BLAS backend reads these at import time and cannot be reconfigured
# afterwards.  One thread per process is what makes an N-worker run
# reproduce a one-core run digit for digit (a threaded BLAS reduction sums
# in a nondeterministic order), and it costs nothing here: the linear
# algebra is 6x6 parameter blocks.  Raising it is a deliberate,
# determinism-losing choice - see CONFIG["threads_per_worker"].
#
# The variable list is spelled out rather than imported from
# sdl_advanced.parallel because importing anything from that PACKAGE runs
# sdl_advanced/__init__.py, which imports numpy - too late.  The two lists
# are pinned equal by tests/test_parallel.py.
# --------------------------------------------------------------------- #
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import csv                                                       # noqa: E402
import dataclasses                                               # noqa: E402
import json                                                      # noqa: E402
import multiprocessing                                           # noqa: E402
import os                                                        # noqa: E402
import sys                                                       # noqa: E402
import time                                                      # noqa: E402

import numpy as np                                               # noqa: E402

try:                                    # progress bar (optional dependency)
    from tqdm.auto import tqdm
except ImportError:                     # pragma: no cover - fallback
    tqdm = None

from sdl_advanced import audit_export as aex                      # noqa: E402
from sdl_advanced import audit_summary as asum                   # noqa: E402
from sdl_advanced import benchmark as bm                         # noqa: E402
from sdl_advanced import benchmark_export as bex                 # noqa: E402
from sdl_advanced import benchmark_figures as bfig               # noqa: E402
from sdl_advanced import benchmark_html as bhtml                 # noqa: E402
from sdl_advanced import efficiency as eff                       # noqa: E402
from sdl_advanced import nmr_examples as nex                     # noqa: E402
from sdl_advanced import parallel as par                         # noqa: E402
from sdl_advanced import reporting as rep                        # noqa: E402
from sdl_advanced import validation as val                       # noqa: E402
from sdl_advanced import observability as obs                    # noqa: E402

CONFIG = {
    "mode": "smoke",                       # "smoke" | "demo" | "publication"
    # NEW DIRECTORY PER CONFIGURATION CHANGE.  results_advanced_v5 is a
    # COMPLETED ARCHIVE of the V5 framework and must never be written to
    # again: its numbers were produced by different physics (an open tube
    # that fails the plug-flow criterion at every design flow), a stale
    # measurement-systematic allowance, and a QC rule that paused every
    # adaptive campaign.  They are not V6 validation and must not be
    # presented as such.
    #
    # `run_kind` separates CODE VALIDATION from PUBLICATION RESULTS.  It is
    # written into the run manifest and into the directory layout, so a
    # smoke or demo run can never be mistaken for the publication run:
    #     validation/   fast runs that prove the code works
    #     publication/  the run whose numbers are reported
    "results_root": "results_advanced_v6",
    "run_kind": "validation",              # "validation" | "publication"
    "run_label": "smoke",         # names the subdirectory; one per run
    # Set explicitly to override the derived
    # <results_root>/<run_kind>/<run_label> path.
    "outdir": None,
    # Refuse to write into a directory that already holds a run.  Set True
    # only when you intend to replace your OWN previous run.
    "allow_overwrite": False,
    # optional overrides of the mode defaults (None -> use MODES[mode]):
    "seeds": None,
    "budget": None,
    "scenarios": None,
    "governor_mc_seeds": None,      # default: seeds of the mode, min 12
    "run_quant_validation": True,
    "progress": True,          # overall tqdm bar with % done + ETA
    "verbose_rounds": False,   # per-round campaign lines (noisy under the bar)

    # ---- parallelism (identical results at any setting) ---------------- #
    # One campaign = one task.  Choose the number of PROCESSES:
    #   None / "auto" -> every core but one (recommended: keeps the laptop
    #                    responsive, and the OS still schedules the pool)
    #   0             -> every core
    #   1             -> serial, no multiprocessing machinery at all
    #   n             -> exactly n processes
    # On Apple Silicon os.cpu_count() counts performance + efficiency cores;
    # the pool is dynamically load-balanced, so the slower cores simply take
    # fewer campaigns.
    "n_workers": "auto",
    # BLAS threads INSIDE each worker.  Keep at 1: it prevents oversubscription
    # (n_workers x threads > cores, which is slower, not faster) and it is the
    # setting under which parallel output is bit-identical to serial output.
    "threads_per_worker": 1,

    # ---- publication audit trail --------------------------------------- #
    # Adds the long-form audit tables (design history, candidate scores,
    # model probabilities, governor diagnostics, blind predictions,
    # posterior covariances, per-acquisition NMR records, resource events,
    # timings) under audit/ in the output directory, plus the run-level
    # reports and the representative NMR examples.
    #
    # It is PURE REPORTING: recording draws no random numbers and evaluates
    # no objective, so the scientific results are identical with it on or
    # off - tests/test_audit_regression.py proves that for matched seeds.
    # It does cost disk: expect a few hundred MB for a 40-seed run, mostly
    # nmr_measurements_long.csv and posterior_covariance_long.csv.
    "audit": True,
    "audit_examples": True,     # the three representative NMR spectra
    # TRUTH-SIDE transfer record for the transport scenarios, which is what
    # lets the report separate TRANSPORT distortion from NMR QUANTIFICATION
    # error after the run.  It is a passive, private log read only by the
    # post-campaign export (`reveal_transfer_log`, counted exactly like
    # `reveal_truth`), so it changes no result - only memory and disk, and
    # only for scenarios that actually have a transfer line.
    "transfer_audit": True,
}

# ========================================================================= #
# EVERY SCIENTIFIC KNOB, in one place
# ========================================================================= #
# These are applied to sdl_advanced.benchmark by `apply_config` at start-up
# and replayed inside every worker process, so CONFIG is the authority for a
# run and the module constants are only library defaults.  An unknown block
# or field RAISES rather than being ignored - a silently-dropped knob is
# indistinguishable from one that had no effect.
#
# Delete a key to keep the library default; the resolved values of ALL of
# them are written to benchmark_config.json regardless.
KNOBS = {
    # ===================================================================== #
    # (1) FEATURE SWITCHES - WHAT IS SIMULATED AT ALL
    # ===================================================================== #
    # ONE True/False per optional effect, for the whole framework.  These
    # decide WHETHER something happens; every block after this one decides
    # HOW MUCH.  False is a genuine bypass - the code path is skipped and
    # the idealized behaviour is recovered exactly - never a tiny parameter
    # with the machinery still running.  Every switch applies to the TRUTH
    # and to the INFERENCE alike; deliberate divergence lives in the clearly
    # separated MODEL_MISMATCH block at the end, which is off by default.
    #
    # sdl_advanced/features.py holds the catalogue, the routing and the
    # dependency checks; the fully resolved state (every switch, its value
    # and its explanation) is written to features_resolved.json with every
    # run, so an archived result has no hidden defaults.
    "FEATURES": {
        # ---- chemistry -------------------------------------------------- #
        # Equilibrium ester hydrolysis with K1, K2 and consistent reverse
        # rates.  True: reverse rates act, K1_ref/K2_ref are estimated.
        # False: irreversible A->B->C, no K parameters anywhere, monotone
        # conversion to completion.
        "reversible_chemistry": True,
        # Arrhenius k(T).  True: Ea acts and is estimated, temperature is an
        # informative design axis.  False: Ea = 0 in the forward model and
        # Ea1/Ea2 held fixed - isothermal rate constants.
        "temperature_dependent_kinetics": True,
        # van 't Hoff K(T).  True: literature dH shifts the equilibrium with
        # temperature.  False: dH = 0, K(T) = K_ref.
        "temperature_dependent_equilibrium": True,
        # Pitzer activity of the catalytic proton.  True: rates respond to
        # ionic strength as well as to acid concentration.  False: dilute
        # ideality, gamma = 1.
        "nonideal_acid_activity": True,
        # H2SO4 second dissociation.  True: [H+] solved from the Ka2
        # equilibrium.  False: stoichiometric [H+] = n_eff [H2SO4].
        "acid_speciation_equilibrium": True,
        # Ka2(T).  True: speciation follows the LOCAL temperature (reactor
        # vs cooled line).  False: Ka2 frozen at its reference value.
        "temperature_dependent_ka2": True,

        # ---- reactor ---------------------------------------------------- #
        # Inert packing.  True: tau = eps V/Q and the bed's mechanical
        # dispersion replaces molecular diffusion, which is what makes the
        # reactor plug-flow valid at the design flows.  False: an OPEN tube
        # - which at these flows is a radially segregated laminar tube and
        # will be REFUSED by the validity check (with guidance).
        "packed_bed_reactor": True,
        # True: the plug-flow criterion is a CONSTRAINT - checked at every
        # permitted flow, and an inadmissible reactor stops the run.
        # False: checked and archived, never blocking (a declared non-ideal
        # study).
        "reactor_validity_enforcement": True,
        # True: Bo = uL/D_ax >= 100 is enforced alongside radial mixing.
        # False: only the radial criterion decides; Bo is still reported.
        "axial_dispersion_criterion": True,
        # True: the reactor geometry is a design variable, sized once from
        # the prior.  False: the declared GEOMETRY is used unchanged.
        "geometry_optimization": True,

        # ---- transfer line ---------------------------------------------- #
        # True: samples travel a finite line to the flow cell.  False:
        # identity transform - the NMR sees the reactor composition at z.
        "transfer_line": True,
        # True: the sample keeps reacting in the line.  False: frozen at
        # withdrawal - delayed but chemically unchanged.
        "transfer_line_reaction": True,
        # True: the line is COOLED (25 C), so in-line reaction and catalyst
        # speciation are evaluated there.  False: the sample stays at
        # REACTOR temperature - the legacy assumption, which over-states
        # in-line conversion badly at 160 C.
        "transfer_line_temperature_correction": True,
        # True: gamma / tanks-in-series RTD - the cell sees a MIXTURE of
        # ages.  False: plug (delta) RTD, one sharp delay.
        "transfer_line_rtd_dispersion": True,
        # True: incomplete flushing mixes in the previous sample, so a
        # measurement depends on the previous position.  False: every
        # acquisition sees only its own sample.
        "transfer_line_carryover": True,
        # True: the controller corrects predictions for the COMMANDED mean
        # delay (never for the truth's RTD or carryover).  False: the
        # F-uncorr ablation - the model is compared against the reactor
        # state as if the line did not exist.
        "transfer_correction_in_inference": True,

        # ---- NMR spectrum ----------------------------------------------- #
        # True: time-domain FID -> T2* -> noise -> phase -> FFT; the
        # acquisition time is physical.  False: the ANALYTIC frequency-
        # domain lineshape - no acquisition time, and fast enough for
        # 40-seed Monte Carlo.  (The FID engine is used as an independent
        # TRUTH pathway in the quantification validation regardless.)
        "nmr_fid_engine": False,
        # True: additive receiver noise.  False: noiseless spectra -
        # repeated acquisitions are bit-identical.
        "nmr_white_noise": True,
        # True: AR(1) COLOURED noise, which the white-noise fitter does not
        # model, so its covariance understates the true uncertainty.
        # False: white noise - the fitter's assumption is exactly right.
        "nmr_correlated_noise": True,
        # True: lognormal linewidth variation per acquisition.  False:
        # every acquisition has exactly the nominal linewidth.
        "nmr_line_broadening": True,
        # True: offset + curvature + a CUBIC term outside the fitter's
        # quadratic baseline model.  False: a flat, zero baseline.
        "nmr_baseline_distortion": True,
        # True: reference drift, per-group jitter and a per-campaign STATIC
        # shift miscalibration - which reapportions area in the 7 Hz
        # EGDA/EGMA overlap.  False: every peak exactly at its database
        # shift.
        "nmr_chemical_shift_drift": True,
        # True: zero-order phase error mixing in dispersion lineshape.
        # False: perfectly phased spectra.
        "nmr_phase_error": True,
        # True: receiver-gain drift, entering the covariance as a rank-one
        # CORRELATED term.  False: constant, exactly calibrated gain.
        "nmr_gain_drift": True,
        # ANTI-INVERSE-CRIME.  True: the truth lineshape is pseudo-Voigt and
        # the true J differs from the database, so the fitter never fits its
        # own physics.  False: pure Lorentzian truth with the database J -
        # the fitter's model is EXACTLY right, which is an inverse crime and
        # useful only as a control.
        "nmr_lineshape_mismatch": True,
        # True: pre-campaign response calibration against prepared
        # standards, as the real workflow does.  False: nominal response
        # assumed - any true response error passes straight through.
        "nmr_response_calibration": True,

        # ---- quantification --------------------------------------------- #
        # True: correlated error between overlapping species (EGDA/EGMA).
        # False: independent per-species errors.
        "overlap_correlated_errors": True,
        # True: Sigma_y includes the reproducibility floor, the coherent
        # gain term, shift-jitter propagation and the standards-calibrated
        # residual covariance - the covariance the design layer also uses.
        # False: the pure within-spectrum Jacobian covariance (optimistic
        # by construction; useful to see how much of the reported
        # uncertainty comes from the error model rather than the spectra).
        "quantification_uncertainty": True,

        # ---- faults and QC ---------------------------------------------- #
        # True: injects gross, QC-DETECTABLE hardware failures (lost lock,
        # bubble, failed shim).  False: the only QC failures are genuine
        # spectral-fit failures on hard compositions - which still occur and
        # are still caught.  OFF by default: this is additional physics.
        "instrument_faults": False,
        # True: injects UNDETECTABLE quantification outliers (many claimed
        # sigmas off, normal residual) to test inference robustness.
        # False: quantification error stays within its calibrated
        # distribution.  OFF by default.
        "measurement_outliers": False,
        # True: a spectrum with FAIL flags is NEVER assimilated, and
        # persistent failure pauses the campaign.  False: everything is
        # assimilated, flags and all.
        "qc_rejection": True,
        # True: a failing position is re-acquired (costing instrument time)
        # before being dropped.  False: dropped immediately.
        "qc_retry_on_failure": True,

        # ---- design ------------------------------------------------------ #
        # True: any point inside the declared bounds, snapped to the
        # hardware resolution and accepted only when it beats the best grid
        # point.  False: the classical discrete factorial grid.
        "continuous_design_space": False,
        # True: axial positions chosen by incremental D-optimality.
        # False: fixed, equally spaced ports - the classical profile.
        "spatial_optimization": True,
        # True: one acquisition at a time, full posterior update between
        # positions, so the realized measurement moves the next one.
        # False: a round's positions are chosen as a BATCH up front.
        "adaptive_single_measurement": True,
        # True: the acquisition also maximizes model-discrimination EIG.
        # False: pure parameter information; model probabilities are
        # tracked but never steer an experiment.
        "bayesian_model_discrimination": True,

        # ---- inference --------------------------------------------------- #
        # True: the lack-of-fit governor may stop the controller exploiting
        # a model it no longer trusts.  False: the model is always
        # exploited (the F-noGovernor ablation).
        "model_inadequacy_governor": True,
        # True: the governor's decision is invariant to a uniform
        # mis-scaling of Sigma_y (dispersion-standardized structural tests;
        # the chi2 MAGNITUDE stops being a decision component under a
        # declared measurement systematic, the gross-misfit override
        # stays).  False: the historical behaviour, in which any residual
        # covariance error eventually reads as model inadequacy.
        "governor_dispersion_robust": True,
        # True: parameters the design space cannot identify are held at
        # their literature values.  False: everything is estimated.
        "identifiability_screen": True,

        # ---- resources ---------------------------------------------------- #
        # True: time, material, waste, energy and travel are metered from an
        # event log.  False: nothing is metered (all totals zero).
        "resource_accounting": True,
        # True: the design objective trades information against cost.
        # False: pure information maximization - cost is reported but never
        # influences a decision.
        "resource_aware_design": True,
        # True: the per-spectrum clock follows the acquisition settings.
        # False: a LEGACY fixed per-spectrum duration, independent of them.
        "acquisition_time_accounting": True,
    },

    # ===================================================================== #
    # (2) MODEL MISMATCH - the ONLY place truth and inference may differ
    # ===================================================================== #
    # Everything above applies to truth and inference alike.  This block is
    # for validation experiments that deliberately hand the learner a
    # different world model from the world ("what does the framework do when
    # its structural assumption is wrong?").  OFF BY DEFAULT, and declaring
    # any divergence without enabling it RAISES - a mismatch that is
    # configured but not declared is exactly the silent inverse-crime risk
    # this section exists to prevent.
    "MODEL_MISMATCH": {
        "enabled": False,
        "inference_reversible": None,        # True/False, None = same as truth
        "inference_activity_model": None,    # "pitzer"/"dilute", None = same
        "inference_arrhenius": None,
        "inference_van_t_hoff": None,
        "inference_noise_scale": 1.0,        # >1: learner believes its data
                                             # are worse than they are
        "truth_parameter_bias": {},          # e.g. {"k2_ref": 1.5}
    },

    # ===================================================================== #
    # (3) MAGNITUDES - how much, given what is switched on above
    # ===================================================================== #
    # ---- reactor ------------------------------------------------------- #
    # packing_enabled / bed_void_fraction are NOT set here: they are
    # derived from FEATURES["packed_bed_reactor"] and the void fraction
    # declared in GEOMETRY_DESIGN, so there is exactly one place that
    # decides whether this reactor is packed.
    "GEOMETRY": {
        "length_m": 0.20,
        "diameter_m": 0.007,
    },
    "T_REF_C": 60.0,                  # Arrhenius reference temperature
    "N_PORTS": 10,                    # axial samples per profile

    # ---- hidden truth (benchmark scoring only) -------------------------- #
    "TRUTH": {"k1_ref": 1.00e-3, "Ea1_J": 40_000.0,
              "k2_ref": 6.50e-4, "Ea2_J": 48_000.0,
              "K1_ref": 0.90, "K2_ref": 0.07},

    # ---- design space --------------------------------------------------- #
    # The factorial grid the classical campaign walks, and the bounds the
    # continuous optimizer is allowed to roam inside.
    "DESIGN": {
        "T_C_levels": [40, 60, 80, 100, 120, 140, 160],
        "Q_total_mL_min_levels": [0.5, 2.0, 8.0],
        "C_cat_M_levels": [0.1, 0.5, 1.0, 2.0],
        "C_EGDA_M_levels": [0.1, 0.5, 1.0, 2.0],
        "C_EGDA_M": 1.0,                                    # For the fixed-design baseline, the optimizer is not allowed to change it.
        "fixed_design_T_C": [40, 60, 80, 100, 120, 140, 160],
        "nominal_Q_total_mL_min": 1.0,
        "nominal_C_cat_M": 0.5,
        "continuous_bounds": {"T_C": [40.0, 160.0],
                              "Q_total_mL_min": [0.5, 8.0],
                              "C_cat_M": [0.1, 2.0],
                              "C_EGDA_M": [0.1, 2.0]},   # lo == hi -> fixed
    },
    # CONTINUOUS vs DISCRETE design.  False = the classical grid-only
    # campaign (the published v3 behaviour).  True = the optimizer may
    # propose any point inside continuous_bounds, snapped to the resolution
    # the hardware can actually command, and accepted only when it strictly
    # beats the best grid point - so it can never do worse.
    # `continuous` lives in FEATURES["continuous_design_space"].
    "DESIGN_SPACE": {
        "resolution": {"T_C": 0.1,             # deg C
                       "Q_total_mL_min": 0.1,   # mL/min
                       "C_cat_M": 1.0e-4,       # 0.1 mM
                       "C_EGDA_M": 1.0e-4},     # 0.1 mM
        "continuous_maxiter": 40,
        "continuous_restarts": 2,
    },

    # ---- reactor geometry as a DESIGN VARIABLE (optional) --------------- #
    # enabled=False -> "I have this reactor, what experiments?"  (default)
    # enabled=True  -> "I am building a reactor for this chemistry, what
    #                   geometry AND what experiments?"  The reactor is
    #                   sized once from the PRIOR before round 1, honouring
    #                   DESIGN_SPACE["continuous"] for the refinement.
    # Blind RMSE stays comparable even with this on: scoring is always done
    # in the DECLARED reference reactor (the learned parameters are
    # intrinsic - geometry changes tau(z), never the constants).
    # `enabled` lives in FEATURES["geometry_optimization"]; `packing`
    # follows FEATURES["packed_bed_reactor"].
    "GEOMETRY_DESIGN": {
        "mode": "per_campaign",       # "per_experiment" raises: not implemented
        "bounds": {"length_m": [0.06, 0.60],
                   "diameter_m": [0.004, 0.008]},
        "levels": {"length_m": [0.06,0.10, 0.20, 0.40, 0.60],
                   "diameter_m": [0.004, 0.006, 0.008]},
        "resolution": {"length_m": 0.005, "diameter_m": 0.0005},
        "switch_cost_s": 1800.0,
        # Feasibility is judged by sdl_advanced/reactor_validity.py at
        # EVERY permitted flow, never at a nominal one - a reactor that is
        # admissible at 1 mL/min and segregated at 8 mL/min is not
        # admissible, because the optimizer is free to command 8.  The
        # criteria themselves live in VALIDITY["criteria"] below;
        # `packing` follows FEATURES["packed_bed_reactor"].
        "bed_void_fraction": 0.40,   # eps of a random-packed bed
        # sizing objective = logdet F(reference design) - resource penalty
        # of that campaign in that reactor; the weights are S6's 1x vector
        # (one information-resource exchange rate for the whole framework).
        # All zeros -> pure information ("bigger is better" warning applies).
        "objective_lambdas": {"lambda_time_per_s": 2e-3,
                              "lambda_material_per_mol": 50.0,
                              "lambda_waste_per_mL": 5e-3,
                              "lambda_energy_per_kJ": 0.05},
    },

    # ---- plug-flow validity of the reactor IN USE ------------------------ #
    # ONE criterion, applied to every reactor the framework touches - the
    # geometry candidates, the reactor a campaign runs in, and the declared
    # reference reactor - at EVERY flow the design space can command.
    # Whether it BLOCKS is FEATURES["reactor_validity_enforcement"]; these
    # are the numbers it blocks on.
    #
    # NOTE ON THE V6 PHYSICS CHANGE.  The shipped 20 cm OPEN tube fails this
    # at every design flow (t_rad/tau = 13-212 against a limit of 10, and Bo
    # far below 100), and so does every open tube in the geometry bounds at
    # the higher flows: at 8 mL/min a 60 cm open tube sits at t_rad/tau = 71.
    # No open tube of any practical length is admissible over this flow
    # envelope - the closed form is Q <= max_radial_ratio * pi * D_m * L, so
    # 8 mL/min would need an 88 m tube.  PACKING is the engineering fix and
    # is now the default (FEATURES["packed_bed_reactor"]).  It shortens tau
    # by eps and therefore changes every conversion, so V6 numbers are NOT
    # comparable to the v5 archive - a deliberate, declared physics change.
    "VALIDITY": {
        "criteria": {
            "max_radial_ratio": 10.0,   # t_rad/tau (Layer 1's boundary)
            "min_bodenstein": 100.0,    # Bo = uL/D_ax, "<1% from plug flow"
            "bed_to_particle_ratio": 10.0,   # d/d_p, wall channelling
            "min_bed_aspect": 100.0,         # L/d_p, entrance/exit
            "packed_peclet_axial": 0.5,      # low-Re liquid asymptote
            "packed_peclet_radial": 10.0,
            "tortuosity": 1.4,
            # True would declare packed beds valid WITHOUT checking them,
            # which is what the framework used to do implicitly.
            "packed_plug_flow_assumed": False,
        },
    },

    # ---- conventional-vs-optimized comparison ---------------------------- #
    # Which strategy plays "the conventional method" the methodology must
    # beat, and the accuracy ladders used for the budget-to-target analysis.
    "COMPARISON": {
        "reference_strategy": {"S1_ideal": "A", "S2_nmr": "B",
                               "S3_transport": "D", "S3ab_delay": "D",
                               "S3ab_rtd": "D", "S4a_ambiguity": "D",
                               "S4b_identifiable": "D",
                               "S4c_out_of_domain": "F",
                               "S5_inadequacy": "D", "S6_resources": "D",
                               "S7_spatial_modes": "F-zfixed"},
        "default_reference": "A",
        "targets": {"param_err_pct": [50.0, 30.0, 20.0, 10.0, 5.0],
                    "blind_rmse_M": [1.0e-2, 5.0e-3, 2.0e-3, 1.0e-3]},
        "trajectory_seed": 1,
    },

    # ---- sample transfer line ------------------------------------------- #
    # The line is COOLED before the NMR flow cell: T_line_C is the commanded
    # line temperature, NOT the reactor's.  It is a large effect - a sample
    # leaving a 160 C reactor into a 25 C line barely reacts on the way,
    # whereas at reactor temperature it keeps converting.  None means "stays
    # at reactor temperature" (the old assumption).
    # enabled / react_in_line / rtd / carryover and whether the line is
    # cooled at all are FEATURES; these are the magnitudes.
    "TRANSFER_TRUE": {
        "Q_sample_mL_min": 0.5,
        "V_fixed_mL": 0.15,
        "geometry": "constant",        # "constant" | "linear"
        "v_per_m_mL": 0.0,
        "n_tanks": 4.0,                # gamma RTD shape
        "n_quad": 5,
        "flush_volumes": 3.0,
    },
    # commanded line temperature used when
    # FEATURES["transfer_line_temperature_correction"] is True
    "TRANSFER_LINE_T_C": 25.0,

    # ---- NMR instrument -------------------------------------------------- #
    "ACQ": {
        "spectrometer_MHz": 80.168,
        "nmr_temperature_C": 27.0,
        "n_points": 2048,
        # REQUESTED FID duration.  The spectral width is fixed by the ppm
        # window x spectrometer frequency, so the acquired complex-point
        # count is round(acquisition_time_s x SW) and the ACTUAL duration
        # differs by at most one dwell period.  Both are recorded in
        # benchmark_config.json.  Affects the "fid" engine only - the
        # analytic engine builds the frequency-domain lineshape directly and
        # has no acquisition time.
        "acquisition_time_s": 4.096,
        # None -> derived from acquisition_time_s (recommended).  Setting it
        # explicitly is validated against the requested time.
        "n_acquired_complex": None,
        # None -> next power of two >= acquired points.  Zero filling adds
        # no time, no signal and no noise.
        "fft_points": None,
        "repetition_time_s": 15.0,
        "n_scans": 1,
        # engine is FEATURES["nmr_fid_engine"]
    },
    # ASSUMED nuisances of the synthetic spectrum - not measured Fourier-80
    # properties.  These are the truth side; the fitter never sees them.
    # Which of these effects is simulated is decided by the nmr_* FEATURES;
    # these are their magnitudes.
    "NMR_NUISANCE_TRUE": {
        "noise_sigma": 0.10,
        "shift_drift_ppm": 0.004,
        "shift_jitter_ppm": 0.001,
        "linewidth_rel_sigma": 0.08,
        "baseline_offset": 0.02,
        "baseline_curve": 0.03,
        "phase_error_deg": 2.0,
        "gain_drift_rel_sigma": 0.01,
    },
    # assumed direct-observation noise for the A-E baselines
    "NOISE_DIRECT": {"sigma_abs_M": 0.004, "sigma_rel": 0.02,
                     "rho_overlap": 0.3},

    # ---- quantification error model (magnitudes) -------------------------- #
    # WHETHER these terms enter Sigma_y is
    # FEATURES["quantification_uncertainty"]; these are their sizes.  All
    # four are ASSUMED (CAL: measure from replicate standards).
    "QUANTIFICATION": {
        "sigma_floor_abs_M": 0.002,   # instrument reproducibility floor
        "sigma_floor_rel": 0.03,      # ~3 %, the classic qNMR accuracy scale
        "gain_drift_rel": 0.01,       # coherent, rank-one covariance term
        "shift_jitter_ppm": 0.001,    # propagated through the overlap solve
    },

    # ---- truth-side fault magnitudes -------------------------------------- #
    # WHETHER faults happen is FEATURES["instrument_faults"] /
    # FEATURES["measurement_outliers"]; these are their rates and sizes.
    "FAULT_MODEL": {
        "spectrum_fault_prob": 0.02,           # per acquisition
        "spectrum_fault_amplitude_sigma": 400.0,   # in noise sigmas
        "outlier_prob": 0.01,                  # per acquisition per species
        "outlier_scale_sigma": 8.0,            # in CLAIMED sigmas
    },
    # the lumped per-spectrum duration used when
    # FEATURES["acquisition_time_accounting"] is False
    "LEGACY_NMR_TIME_S": 60.0,

    # ---- spatial sampling ------------------------------------------------ #
    "SPATIAL": {
        "candidate_grid_size": 41,
        "z_min_fraction": 0.02,
        "z_max_fraction": 1.0,
        "min_spacing_fraction": 0.02,
        "continuous_refinement": False,
    },

    # ---- Bayesian design (strategy F) ------------------------------------ #
    "ADVANCED_DESIGN": {
        "top_k": 3,                    # candidates surviving the FIM screen
        "n_particles": 16,             # posterior particles per EIG estimate
        "n_outer": 24,                 # outer MC samples per EIG estimate
        "alpha_param": 1.0,            # weight on parameter EIG
        "beta_model": 1.0,             # weight on model-discrimination EIG
        "beta_model_discrimination": 4.0,
    },

    # ---- model-inadequacy governor --------------------------------------- #
    "GOVERNOR": {
        "alpha_campaign": 0.05,
        "discrimination_prob": 0.90,
        "qc_fail_fraction": 0.25,
        "chi2_dof_ratio_override": 25.0,
        # kappa: "auto" DERIVES the measurement-systematic allowance from
        # WELL-SPECIFIED CONTROL DATA under THIS configuration - the current
        # geometry, acquisition settings, nuisance model and DESIGN SPACE -
        # and records the derivation.  It is never tuned on benchmark
        # performance.  A hard-coded number is a value that was right once:
        # between v3 and v5 the design space widened, the prepared standards
        # stopped spanning it, and kappa stayed at the old value.  Pin a
        # float here only to reproduce an archived run exactly.
        "systematic_allowance_nmr": "auto",
        "systematic_allowance_direct": 0.0,
        # governor_dispersion_robust lives in FEATURES
        "allowance_seed": 0,
        "allowance_n_rep": 3,
        "allowance_n_control": 80,
        "allowance_stride": 3,
    },

    # ---- measurement-fault QC gate ---------------------------------------- #
    # WHEN QC REJECTION MEANS "THE INSTRUMENT IS BROKEN".  A per-round
    # rejection FRACTION is meaningless for a single-acquisition round: in
    # adaptive mode one rejected spectrum is 100 %, which paused 40 of 40
    # F-zadaptive campaigns in the v5 archive.  The fraction rule is
    # therefore applied only to batches large enough for it to mean
    # something, and PERSISTENCE rules (which work at any batch size) decide
    # the rest.
    "QC_GATE": {
        "max_retries": 1,              # reacquisitions per failing position
        "max_reject_fraction": 0.5,    # batch rule
        "min_batch_for_fraction": 4,   # below this, the fraction is ignored
        "max_consecutive_rejects": 3,  # persistence rule
        "rolling_window": 8,           # persistence rule
        "max_rejects_in_window": 4,
    },

    # ---- resource model ---------------------------------------------------- #
    # lambda_* = 0 recovers pure information maximization; S6 sweeps them.
    "RESOURCE_COSTS": {
        "stabilization_volumes": 3.0,
        "temp_change_s_per_K": 20.0,
        "temp_ambient_C": 25.0,
        # NMR measurement time is DECOMPOSED (see resources.py): the
        # spectrum duration is overhead + n_scans x (recycle + acquisition),
        # with the physical terms synchronized from ACQ automatically.  Only
        # the overhead is a free parameter here; its default is the residue
        # of the historical lumped 60 s at the shipped acquisition, so the
        # shipped campaign clock is unchanged but now explicit.
        "nmr_fixed_overhead_s": 40.9,
        # the LEGACY lumped per-spectrum duration is
        # FEATURES["acquisition_time_accounting"] = False
        "capillary_speed_m_s": 0.002,
        "flush_time_s": 30.0,
        "sample_volume_mL": 0.3,
        "flush_volume_mL": 0.45,
        "rho_cp_J_per_mL_K": 4.18,
        "energy_ramp_J_per_K": 500.0,
        "lambda_time_per_s": 0.0,
        "lambda_material_per_mol": 0.0,
        "lambda_waste_per_mL": 0.0,
        "lambda_energy_per_kJ": 0.0,
        "lambda_switch": 0.0,
        "lambda_motion_per_m": 0.0,
    },
}

#: audit tables grouped into subdirectories so the trail stays navigable.
#: These are the RAW, authoritative per-campaign records; everything the
#: summary layer produces is an aggregate of them and lives in data/.
AUDIT_LAYOUT = {
    "design": ("design_history", "design_candidate_scores",
               "spatial_candidate_scores"),
    "inference": ("model_probabilities_long", "posterior_covariance_long",
                  "identifiability_summary"),
    "governor": ("governor_diagnostics_long",),
    "measurement": ("nmr_measurements_long", "nmr_calibration_by_seed",
                    "transfer_decomposition_long"),
    "resources": ("resource_events_long", "controller_timing"),
    "validation": ("blind_predictions_long",),
}


#: the output tree.  ONE root (the existing results_root / run_kind /
#: run_label logic decides it); everything below is organized inside it, and
#: no file is written anywhere else.
LAYOUT = {
    "config": ("config",),
    "data": ("data",),
    "comparison": ("data", "comparison"),
    "fig_overview": ("figures", "overview"),
    "fig_scenarios": ("figures", "scenarios"),
    "fig_parameters": ("figures", "parameters"),
    "fig_design": ("figures", "design"),
    "fig_measurement": ("figures", "measurement"),
    "fig_robustness": ("figures", "robustness"),
    "fig_resources": ("figures", "resources"),
    "audit": ("audit",),
    "report": ("report",),
}


#: the transport ABLATION LADDER, in the order the effects are switched on.
#: Only the rungs a run actually contains are used, so a partial scenario
#: list still produces a meaningful ladder.
TRANSPORT_LADDER = ("S2_nmr", "S3ab_delay", "S3ab_rtd", "S3_transport")


def prepare_layout(outdir: str) -> dict:
    """Create the subdirectories and return {key: absolute path}."""
    paths = {"root": outdir}
    for key, parts in LAYOUT.items():
        p = os.path.join(outdir, *parts)
        os.makedirs(p, exist_ok=True)
        paths[key] = p
    return paths


#: files whose presence means "a run already lives here".  Both the current
#: layout and the flat layout earlier runs wrote are listed, so an archive
#: produced by any version of this runner is still protected.
_RUN_MARKERS = (os.path.join("config", "benchmark_config.json"),
                os.path.join("config", "run_manifest.json"),
                os.path.join("data", "benchmark_rounds.csv"),
                "benchmark_config.json", "run_manifest.json",
                "benchmark_rounds.csv")


def resolve_outdir(cfg: dict) -> str:
    """Where this run writes - and a refusal to overwrite anything else.

    A completed archive is evidence.  Silently writing over it (or, worse,
    half over it) destroys the ability to say which code produced which
    number, so a directory that already holds a run is refused unless the
    caller explicitly asked to replace it."""
    outdir = cfg.get("outdir")
    kind = str(cfg.get("run_kind", "validation")).lower()
    if kind not in ("validation", "publication"):
        raise ValueError("CONFIG['run_kind'] must be 'validation' (code "
                         "checks) or 'publication' (reported numbers); got "
                         f"{kind!r}.")
    if not outdir:
        outdir = os.path.join(str(cfg["results_root"]), kind,
                              str(cfg.get("run_label") or cfg["mode"]))
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              outdir)
    existing = [m for m in _RUN_MARKERS
                if os.path.exists(os.path.join(outdir, m))]
    if existing and not cfg.get("allow_overwrite", False):
        raise FileExistsError(
            f"{outdir} already contains a completed run ({', '.join(existing)}"
            ").  Refusing to overwrite it: an archived run is the only "
            "record of which code produced which numbers.  Choose a new "
            "run_label, or set CONFIG['allow_overwrite'] = True if you "
            "really mean to replace your own previous run.")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def git_provenance() -> dict:
    """Exact commit + working-tree state, so a result can be traced to code.

    A dirty tree is RECORDED, not refused: refusing would make the framework
    unusable while developing.  But a publication run says so loudly."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _git(*args):
        try:
            return subprocess.run(("git",) + args, cwd=root,
                                  capture_output=True, text=True,
                                  timeout=30).stdout.strip()
        except Exception:                            # pragma: no cover
            return ""
    status = _git("status", "--porcelain")
    return {"commit": _git("rev-parse", "HEAD"),
            "commit_short": _git("rev-parse", "--short", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "describe": _git("describe", "--always", "--dirty"),
            "dirty": bool(status),
            "dirty_files": [ln[3:] for ln in status.splitlines()][:200]}


def _write_rows(rows, path):
    """One CSV, returning the path it wrote (or None for an empty table).

    Columns are sorted, so two runs of the same configuration produce
    byte-comparable files; the return value is what lets the report link
    exactly the files that exist."""
    if not rows:
        return None
    keys = sorted({k for r in rows for k in r})
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, restval="")
        w.writeheader()
        w.writerows(rows)
    print(f"saved: {os.path.relpath(path)}")
    return path


def _mean_curves(rows, scenario, x_key="round"):
    out = {}
    sc_rows = [r for r in rows if r["scenario"] == scenario]
    metrics = ("param_err_pct", "max_rel_ci_pct", "p_correct",
               "model_entropy", "blind_rmse_M", "time_s", "egda_mol",
               "nmr_acquisitions", "energy_kJ", "capillary_travel_m",
               "spatial_samples")
    for strat in sorted({r["strategy"] for r in sc_rows}):
        s_rows = [r for r in sc_rows if r["strategy"] == strat]
        rounds = sorted({r["round"] for r in s_rows})
        cur = {x_key: []}
        for m in metrics:
            cur[m] = []
        for rnd in rounds:
            rr = [r for r in s_rows if r["round"] == rnd]
            cur[x_key].append(rnd)
            for m in metrics:
                vals = [r[m] for r in rr
                        if np.isfinite(r.get(m, np.nan))]
                cur[m].append(float(np.mean(vals)) if vals else float("nan"))
        out[strat] = cur
    return out


def _finals(rows, scenario):
    out = {}
    sc = [r for r in rows if r["scenario"] == scenario]
    for strat in sorted({r["strategy"] for r in sc}):
        fr = bm.last_valid_rows(rows, scenario, strat)   # keeps paused seeds
        agg = {}
        for k in fr[0]:
            vals = [r[k] for r in fr
                    if isinstance(r[k], (int, float)) and np.isfinite(r[k])]
            if vals:
                agg[k] = float(np.median(vals))
        agg["n_seeds"] = len(fr)
        out[strat] = agg
    return out


def main() -> None:
    cfg = dict(CONFIG)
    # CONFIG is the authority for this run: apply every knob to the
    # benchmark module BEFORE anything reads it (MODES, scenarios and the
    # observability scan all consume GEOMETRY/DESIGN).  Strict - an unknown
    # knob raises here rather than being silently ignored.
    knobs = dict(KNOBS)
    resolved_knobs = bm.apply_config(knobs)
    mode = bm.MODES[cfg["mode"]]
    seeds = cfg["seeds"] or mode["seeds"]
    budget = cfg["budget"] or mode["budget"]
    scenarios = cfg["scenarios"] or mode["scenarios"]
    outdir = resolve_outdir(cfg)
    paths = prepare_layout(outdir)
    t0 = time.time()

    # ---- derive the measurement-systematic allowance ONCE --------------- #
    # kappa is a pure function of the configuration, so every worker would
    # otherwise re-derive the same number - minutes of duplicated NMR fits
    # per process.  Deriving it here and PINNING the resolved float has a
    # second, better reason: it makes it a fact of the run rather than
    # something each process computes for itself, so the archive records the
    # value that was actually used everywhere and the workers cannot
    # silently disagree.
    allowance = None
    if isinstance(bm.GOVERNOR["systematic_allowance_nmr"], str):
        allowance = bm.derive_allowance(budget)
        resolved_knobs = bm.apply_config(
            {"GOVERNOR": {"systematic_allowance_nmr":
                          float(allowance["kappa"])}})
        knobs = {**knobs, "GOVERNOR": {**knobs.get("GOVERNOR", {}),
                                       "systematic_allowance_nmr":
                                       float(allowance["kappa"])}}
        print(f"systematic allowance kappa = {allowance['kappa']:.4f} "
              f"(derived: rms z = {allowance['rms_z']:.3f} over "
              f"{allowance['n_control_compositions']} control compositions "
              f"spanning the declared design space)")

    # ---- reproducibility record, written BEFORE anything runs ----------- #
    # Written first so that even a crashed or interrupted run leaves behind
    # the exact code and configuration it was attempting.
    prov = git_provenance()
    manifest = {
        "framework_version": "v6",
        "run_kind": cfg["run_kind"],
        "run_label": cfg.get("run_label"),
        "is_publication_run": cfg["run_kind"] == "publication",
        "mode": cfg["mode"],
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git": prov,
        "python": sys.version,
        "numpy": np.__version__,
        "seeds": list(seeds), "budget": budget,
        "scenarios": list(scenarios),
        "CONFIG": {k: v for k, v in cfg.items()},
        "knobs_requested": knobs,
        "knobs_resolved": resolved_knobs,
        "features_resolved": resolved_knobs["FEATURES_RESOLVED"],
        "systematic_allowance_derivation": allowance,
    }
    with open(os.path.join(paths["config"], "run_manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    with open(os.path.join(paths["config"], "features_resolved.json"), "w",
              encoding="utf-8") as fh:
        json.dump(resolved_knobs["FEATURES_RESOLVED"], fh, indent=2,
                  default=str)
    print(f"run kind: {cfg['run_kind'].upper()}"
          + ("  (code validation - NOT publication numbers)"
             if cfg["run_kind"] != "publication" else ""))
    print(f"commit: {prov.get('describe') or 'unknown'}"
          + ("   *** WORKING TREE DIRTY ***" if prov.get("dirty") else ""))
    if cfg["run_kind"] == "publication" and prov.get("dirty"):
        print("  WARNING: a publication run from a dirty working tree "
              "cannot be reproduced from the recorded commit alone.  The "
              "modified files are listed in run_manifest.json.")
    print(f"output: {outdir}")

    # ---- overall progress bar ------------------------------------------- #
    gov_seeds = cfg["governor_mc_seeds"] or list(seeds)
    if len(gov_seeds) < 12:
        gov_seeds = list(range(1, 13))
    total_units = bm.total_cost_units(scenarios, seeds, budget,
                                      len(gov_seeds))
    use_bar = bool(cfg.get("progress", True)) and tqdm is not None
    # float total, NOT round(): the updates are floats and their sum is
    # exactly total_units, so a rounded total lets the bar overshoot 100 %
    bar = (tqdm(total=float(total_units), unit="wu", dynamic_ncols=True,
                smoothing=0.05,
                bar_format="{l_bar}{bar}| {percentage:3.0f}% "
                           "[elapsed {elapsed} | remaining {remaining}]")
           if use_bar else None)
    say = (lambda msg: (tqdm.write(msg) if bar is not None else print(msg)))

    def _tick(scenario, strategy, seed, b):
        if bar is not None:
            # clamped to what is left: `sum()` and repeated `+=` over the
            # same floats can disagree in the last bits, and a bar that
            # ends at 100.0000001 % emits a warning instead of a result
            bar.update(min(bm.campaign_cost_units(strategy, b),
                           max(bar.total - bar.n, 0.0)))
            bar.set_description(f"{scenario}/{strategy} seed{seed}")

    # ---- parallel plan --------------------------------------------------- #
    # Children inherit the environment, so setting it here (before the pool
    # is created) configures every worker.  The parent was already pinned at
    # import time; they must agree for serial and parallel to match.
    threads = int(cfg.get("threads_per_worker", 1) or 1)
    par.pin_numerical_threads(threads)
    n_proc = par.resolve_workers(cfg.get("n_workers", "auto"))
    audit_on = bool(cfg.get("audit", False))

    say(f"=== advanced benchmark V6 | {cfg['run_kind']} | "
        f"mode={cfg['mode']} | {len(seeds)} seeds | budget {budget} ===")
    say("    FEATURES (full state in features_resolved.json):")
    for line in bm.feat.summary_lines(bm.FEATURES, bm.MODEL_MISMATCH):
        say(line)
    nd = resolved_knobs["FEATURES_RESOLVED"]["non_default"]
    say(f"    non-default switches: {', '.join(nd) if nd else 'none'}")
    say(f"    parallelism: {par.describe_workers(cfg.get('n_workers', 'auto'))}"
        f", {threads} BLAS thread(s) each")
    if threads != 1:
        say("    WARNING: threads_per_worker != 1 - a threaded BLAS reduction "
            "sums in a nondeterministic order, so bit-identical agreement "
            "with a serial run is no longer guaranteed.")
    say(f"    audit trail: {'ON -> ' + os.path.join(outdir, 'audit') if audit_on else 'off'}")
    ds = bm.DESIGN_SPACE
    if ds.get("continuous"):
        r = ds["resolution"]
        say(f"    design space: CONTINUOUS within bounds, snapped to "
            f"{r['T_C']} C / {r['Q_total_mL_min']} mL/min / "
            f"{r['C_cat_M'] * 1e3:.1f} mM cat / {r['C_EGDA_M'] * 1e3:.1f} mM EGDA")
    else:
        say("    design space: DISCRETE factorial grid (classical)")
    tl = bm.TRANSFER_TRUE.T_line_C
    if not bm.TRANSFER_TRUE.enabled:
        line_note = "disabled"
    elif tl is None:
        line_note = "sample stays at REACTOR temperature"
    else:
        line_note = f"cooled to T_line = {tl:.1f} C"
    say(f"    transfer line: {line_note}")

    # ---- (0B) equilibrium-observability diagnostic, BEFORE any campaign - #
    # uses ASSUMED (literature) parameters only: firewall-clean
    from sdl import Layer1Bridge, OperatingConditions, literature_guess
    t_ref_K = bm.T_REF_C + 273.15
    guess = literature_guess(t_ref_K)
    geom_scan = bm.active_geometry(budget)
    if bm.GEOMETRY_DESIGN.get("enabled", False):
        say(f"    geometry design ON: campaigns run in the sized reactor "
            f"(L={geom_scan['length_m'] * 100:.1f} cm, "
            f"ID={geom_scan['diameter_m'] * 1e3:.1f} mm, "
            f"{'packed' if geom_scan.get('packing_enabled') else 'open'}); "
            f"blind scoring stays in the declared "
            f"{bm.GEOMETRY['length_m'] * 100:.0f} cm reference reactor")
        _write_rows(bm.geometry_sizing_table(budget),
                    os.path.join(paths["config"], "geometry_sizing.csv"))
    # plug-flow validity of the reactor actually in use, at every design
    # flow - the same criterion the geometry optimizer enforces
    # Rows are ARCHIVED FIRST, then the policy is applied: a run that stops
    # because its reactor is inadmissible must still leave behind the table
    # that says why.
    validity_rows = bm.reactor_validity_rows(geom_scan)
    _write_rows(validity_rows,
                os.path.join(paths["config"], "reactor_validity.csv"))
    with open(os.path.join(paths["config"], "reactor_validity.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(bm.rv.explain(geom_scan, bm.permitted_flows(),
                               bm.validity_criteria()))
        fh.write(os.linesep)
    bm.assert_reactor_validity(geom_scan)
    diag_bridge = Layer1Bridge(geom_scan, t_ref_K, activity_model="pitzer")
    scan_conds = [OperatingConditions(T, q / 2, q / 2, 1.0, c)
                  for T in (40.0, 100.0, 160.0)
                  for q in (0.5, 2.0, 8.0) for c in (0.5, 1.0)]
    scan = obs.domain_scan(diag_bridge, guess, scan_conds)
    obs.write_scan_csv(scan, os.path.join(
        paths["config"], "equilibrium_observability.csv"))
    verdict = obs.verdict(scan)
    print("\nEquilibrium observability over the admissible domain "
          f"(geometry {geom_scan['length_m']*100:.0f} cm x "
          f"{geom_scan['diameter_m']*1e3:.0f} mm ID, "
          f"V_liq={diag_bridge.geometry.liquid_volume_mL:.2f} mL):")
    print(f"  max phi1={verdict['max_phi1']:.3g}  max phi2="
          f"{verdict['max_phi2']:.3g}  "
          f"|dC/dlnK1|={verdict['max_dC_dlnK1']*1e3:.1f} mM "
          f"({verdict['snr_K1']:.2f} sigma)  "
          f"|dC/dlnK2|={verdict['max_dC_dlnK2']*1e3:.1f} mM "
          f"({verdict['snr_K2']:.2f} sigma)")
    for msg in verdict["messages"]:
        print("  " + msg)
    obs.plot_phi_profiles(
        diag_bridge, guess,
        [OperatingConditions(160.0, 0.25, 0.25, 1.0, 1.0),
         OperatingConditions(100.0, 0.25, 0.25, 1.0, 1.0),
         OperatingConditions(160.0, 4.0, 4.0, 1.0, 1.0)],
        os.path.join(paths["fig_overview"],
                     "figure_equilibrium_observability.png"))

    # ---- well-specified scenarios: truth must lie inside the candidate box #
    for scen in scenarios:
        spec = bm.SCENARIOS[scen]
        if not getattr(spec, "well_specified", False):
            continue
        space = __import__("sdl").ParameterSpace(
            t_ref_K=t_ref_K, initial_guess=dict(guess))
        dom = bm.check_truth_in_domain(space, spec.truth)
        print(f"  domain check {scen}: ok={dom['ok']}  " +
              ", ".join(f"{k}:{'in' if v['inside'] else 'OUT'}"
                        f"/margin={v['margin_scaled']:.2f}"
                        for k, v in dom["detail"].items()))
        if not dom["ok"]:
            raise AssertionError(
                f"{scen} is declared well-specified but its truth is not "
                f"inside the candidate parameter domain: {dom['detail']}")

    # ==== COMPUTE PHASE (parallel) ======================================= #
    # Everything that runs campaigns happens here, under one pool; the
    # reporting phase below is serial and touches no laboratory.  The pool
    # is created once rather than per scenario so the process start-up cost
    # (a fresh interpreter importing numpy/scipy, under `spawn`) is paid a
    # single time.
    all_rows, all_prows, all_status, runtimes = [], [], [], {}
    audit_all = aex.empty_bundle() if audit_on else None
    # workers re-import the module and start from DEFAULTS, so the same
    # knobs are replayed inside every process (see bm.worker_init)
    executor = par.make_executor(cfg.get("n_workers", "auto"),
                                 initializer=bm.worker_init,
                                 initargs=(budget, knobs))
    try:
        for scen in scenarios:
            spec = bm.SCENARIOS[scen]
            say(f"\n=== {scen}: {spec.description}")
            t_s = time.time()
            rows, prows, status, bundle = bm.run_scenario(
                spec, seeds, budget,
                verbose=bool(cfg.get("verbose_rounds", False)),
                progress=_tick, executor=executor, audit=audit_on,
                transfer_audit=bool(cfg.get("transfer_audit", True)))
            runtimes[scen] = time.time() - t_s
            all_rows.extend(rows)
            all_prows.extend(prows)
            all_status.extend(status)
            if audit_on:
                aex.merge(audit_all, bundle)
            say(f"    {scen} done in {runtimes[scen]:.0f} s")

        say(f"\n=== governor Monte Carlo validation ({len(gov_seeds)} seeds)")
        t_g = time.time()
        gov = bm.governor_mc_validation(gov_seeds, budget=budget,
                                        progress=_tick, executor=executor)
        gov["runtime_s"] = time.time() - t_g
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    # ==== REPORTING PHASE (serial) ======================================= #
    # Everything below reads FINISHED results.  No campaign code runs, no
    # RNG is touched except the fixed-seed bootstraps the benchmark already
    # uses for its own confidence intervals, and nothing here can move a
    # scientific number.  The raw per-round and audit tables are written
    # first and stay authoritative; every summary after them is an
    # aggregate of those files and says so.

    # ---- (0) the raw record --------------------------------------------- #
    _write_rows(all_rows, os.path.join(paths["data"], "benchmark_rounds.csv"))
    _write_rows(all_prows, os.path.join(paths["data"],
                                        "benchmark_params.csv"))
    # campaign status: completion / fault / QC counts per strategy x seed,
    # so accuracy is always read next to completion rate (no survivorship)
    _write_rows(all_status, os.path.join(paths["data"],
                                         "campaign_status.csv"))
    for scen in scenarios:
        st = [s for s in all_status if s["scenario"] == scen]
        for strat in sorted({s["strategy"] for s in st}):
            ss = [s for s in st if s["strategy"] == strat]
            n_f = sum(s["faulted"] for s in ss)
            if n_f:
                print(f"    NOTE {scen}/{strat}: {n_f}/{len(ss)} campaigns "
                      f"paused on measurement fault (retained in stats via "
                      f"their last valid posterior)")

    # ---- (1) strategy table: distributional, no cherry-picking ---------- #
    table = []
    for scen in scenarios:
        table.extend(bm.summarize_final(all_rows, scen))
    text = rep.write_strategy_table(
        table, os.path.join(paths["data"], "strategy_table.csv"))
    print("\n" + text)

    # ---- (2) the audit trail, RAW ---------------------------------------- #
    # Written before any aggregate, because every aggregate below is derived
    # from these tables and a reader must be able to check one against the
    # other.
    audit_tables = (audit_all or {})
    if audit_on:
        for sub, tables_ in AUDIT_LAYOUT.items():
            os.makedirs(os.path.join(paths["audit"], sub), exist_ok=True)
            for t in tables_:
                _write_rows(audit_tables.get(t, []),
                            os.path.join(paths["audit"], sub, f"{t}.csv"))

    # ---- (3) run integrity ------------------------------------------------ #
    integrity = asum.run_integrity_report(all_rows, all_status, scenarios,
                                          seeds, budget, bm.SCENARIOS)
    with open(os.path.join(paths["data"], "run_integrity_report.json"),
              "w") as fh:
        json.dump(integrity, fh, indent=2, default=str)
    if not integrity["complete"]:
        print("  RUN INTEGRITY: " + "; ".join(integrity["problems"]))
    else:
        print(f"  run integrity OK: {integrity['n_campaigns']} campaigns, "
              f"{integrity['n_round_rows']} round rows, no gaps")

    # ---- (4) governor Monte-Carlo validation ------------------------------ #
    with open(os.path.join(paths["data"], "governor_validation.json"),
              "w") as fh:
        json.dump(gov, fh, indent=2)
    print(f"\ngovernor MC validation ({len(gov_seeds)} seeds): "
          f"false-inadequacy campaign rate = "
          f"{gov['false_inadequacy_campaign_rate']:.2f} "
          f"(target alpha = {gov['alpha_campaign_target']:g}), "
          f"detection prob = "
          f"{gov['detection_probability']:.2f}, median detection round = "
          f"{gov['median_detection_round']}")
    print(f"    kappa used = {gov['systematic_allowance_used']:.3f}; "
          f"median dispersion phi on well-specified campaigns = "
          f"{gov['median_dispersion_well_specified']}")
    print(f"    detection carried by: {gov['detection_drivers']}")
    if gov["false_alarm_drivers"]:
        print(f"    false alarms carried by: {gov['false_alarm_drivers']}")

    # ---- (5) quantification validation ------------------------------------ #
    qv_rows = []
    if cfg["run_quant_validation"]:
        t_v = time.time()
        results = val.run_validation(bm.ACQ, bm.NMR_NUISANCE_TRUE,
                                     bm.GEOMETRY, bm.T_REF_C + 273.15,
                                     __import__("sdl").literature_guess(
                                         bm.T_REF_C + 273.15), seed=0)
        qv_rows = val.validation_rows(results)
        _write_rows(qv_rows, os.path.join(paths["data"],
                                          "quantification_validation.csv"))
        print(f"quantification validation done in {time.time() - t_v:.0f} s")

    # ==== AGGREGATION ===================================================== #
    # One dict of row-lists, keyed by the CSV base name it is written to, so
    # the tables the report reads and the tables on disk cannot diverge.
    print("\n=== aggregating the run summary")
    conv = asum.convergence_summary_rows(all_rows, all_status, budget)
    paired_seed = bex.paired_seed_rows(all_rows, bm.SCENARIOS)
    paired_sum = bex.paired_summary_rows(paired_seed)
    master = bex.master_summary_rows(
        all_rows, all_status, all_prows,
        audit_tables.get("model_probabilities_long", []),
        audit_tables.get("governor_diagnostics_long", []), bm.SCENARIOS)
    design_hist = audit_tables.get("design_history", [])
    tables = {
        "benchmark_master_summary": master,
        "parameter_performance_summary": bex.parameter_performance_rows(
            all_prows, audit_tables.get("identifiability_summary", []),
            audit_tables.get("posterior_covariance_long", [])),
        "design_selection_distribution": bex.design_selection_rows(
            design_hist),
        "design_selection_by_round": bex.design_by_round_rows(design_hist),
        "paired_seed_differences": paired_seed,
        "paired_comparison_summary": paired_sum,
        "robustness_summary": bex.robustness_rows(
            all_rows, all_status, all_prows,
            audit_tables.get("governor_diagnostics_long", []),
            audit_tables.get("nmr_measurements_long", []),
            audit_tables.get("model_probabilities_long", []), bm.SCENARIOS),
        "model_discrimination_summary": bex.model_discrimination_rows(
            audit_tables.get("model_probabilities_long", []), all_rows,
            bm.SCENARIOS),
        "nmr_performance_summary": bex.nmr_performance_rows(
            audit_tables.get("nmr_measurements_long", [])),
        "nmr_by_round": bex.nmr_by_round_rows(
            audit_tables.get("nmr_measurements_long", [])),
        "transfer_effect_summary": bex.transfer_effect_rows(
            all_rows, TRANSPORT_LADDER, bm.SCENARIOS),
        "transfer_decomposition_summary":
            bex.transfer_decomposition_summary_rows(
                audit_tables.get("transfer_decomposition_long", [])),
        "resource_summary": bex.resource_summary_rows(
            all_rows, audit_tables.get("resource_events_long", [])),
        "scenario_strategy_matrix": bex.matrix_rows(master),
        "convergence_summary": conv,
        "quantification_validation": qv_rows,
        "strategy_table": table,
    }

    # ---- conventional vs optimized: budget-to-target and matched resource #
    # Generalized over WHATEVER strategies each scenario defines, compared
    # against that scenario's own declared reference - never a hard-coded
    # pair.
    btt_all, mr_all, traj_all = [], [], []
    for scen in scenarios:
        spec = bm.SCENARIOS[scen]
        ref = bm.reference_strategy(scen)
        strats = list(spec.strategies)
        btt_all += eff.budget_to_target_rows(all_rows, scen, strats, ref,
                                             seeds, bm.COMPARISON["targets"])
        mr_all += eff.matched_resource_rows(all_rows, scen, strats, ref,
                                            seeds)
        traj_all += eff.trajectory_rows(all_rows, design_hist, scen, ref)
    btt_sum = eff.summarize_budget_to_target(btt_all)
    mr_sum = eff.summarize_matched_resource(mr_all)
    tables["headline_comparison"] = eff.headline_rows(btt_sum, mr_sum)
    comparison_tables = {
        "budget_to_target": btt_all,
        "budget_to_target_summary": btt_sum,
        "accuracy_at_matched_resource": mr_all,
        "accuracy_at_matched_resource_summary": mr_sum,
        "design_trajectory": traj_all,
        "headline_comparison": tables["headline_comparison"],
    }

    # ---- the legacy paired-comparison table, now over every strategy ----- #
    pairs = []
    for scen in scenarios:
        ref = bm.reference_strategy(scen)
        for strat in bm.SCENARIOS[scen].strategies:
            if strat == ref:
                continue
            for metric in ("blind_rmse_M", "param_err_pct"):
                pc = bm.paired_comparison(all_rows, scen, strat, ref, metric)
                if pc:
                    pairs.append(pc)
    tables["paired_comparisons"] = pairs

    # ---- write every aggregate ------------------------------------------- #
    files = {}
    for name, rows_ in tables.items():
        files[name] = _write_rows(rows_,
                                  os.path.join(paths["data"], f"{name}.csv"))
    for name, rows_ in comparison_tables.items():
        files[name] = _write_rows(
            rows_, os.path.join(paths["comparison"], f"{name}.csv"))
    files.update({
        "run_manifest": os.path.join(paths["config"], "run_manifest.json"),
        "benchmark_config": os.path.join(paths["config"],
                                         "benchmark_config.json"),
        "features_resolved": os.path.join(paths["config"],
                                          "features_resolved.json"),
        "reactor_validity": os.path.join(paths["config"],
                                         "reactor_validity.csv"),
        "benchmark_rounds": os.path.join(paths["data"],
                                         "benchmark_rounds.csv"),
        "benchmark_params": os.path.join(paths["data"],
                                         "benchmark_params.csv"),
        "campaign_status": os.path.join(paths["data"],
                                        "campaign_status.csv"),
        "governor_validation": os.path.join(paths["data"],
                                            "governor_validation.json"),
        "run_integrity_report": os.path.join(paths["data"],
                                             "run_integrity_report.json"),
        "model_probabilities": os.path.join(paths["audit"], "inference",
                                            "model_probabilities_long.csv"),
    })

    # ==== FIGURES ========================================================== #
    print("=== drawing the figure set")
    figs: dict = {}

    def _put(key, path):
        if path:
            figs[key] = path

    # ---- overview -------------------------------------------------------- #
    _put("overview_accuracy", bfig.figure_overview_accuracy(
        master, os.path.join(paths["fig_overview"],
                             "figure_overview_accuracy.png")))
    for metric, _label, _lower in bex.MATRIX_METRICS:
        _put(f"matrix_{metric}", bfig.figure_matrix(
            tables["scenario_strategy_matrix"], metric,
            os.path.join(paths["fig_overview"], f"figure_matrix_{metric}.png"),
            log_scale=metric in ("blind_rmse_M_median", "median_time_s_s",
                                 "max_rel_ci_pct_median")))

    # ---- per-scenario ----------------------------------------------------- #
    for scen in scenarios:
        if scen not in {r["scenario"] for r in all_rows}:
            continue
        ref = bm.reference_strategy(scen)
        curves = _mean_curves(all_rows, scen)
        path = os.path.join(paths["fig_scenarios"],
                            f"figure_conv_{scen}_per_round.png")
        rep.figure_e_convergence(curves, "round", path)
        _put(f"conv_round_{scen}", path)
        for x_key, tag, key in (("nmr_acquisitions", "per_acquisition",
                                 "conv_acq"),
                                ("time_s", "per_time", "conv_time")):
            path = os.path.join(paths["fig_scenarios"],
                                f"figure_conv_{scen}_{tag}.png")
            rep.figure_e_convergence({s: dict(c) for s, c in curves.items()},
                                     x_key, path)
            _put(f"{key}_{scen}", path)
        for basis in ("locf", "observed"):
            path = os.path.join(paths["fig_scenarios"],
                                f"figure_band_{scen}_{basis}.png")
            rep.figure_convergence_band(conv, scen, path, basis=basis)
            _put(f"band_{basis}_{scen}", path)
        path = os.path.join(paths["fig_design"],
                            f"figure_efficiency_{scen}.png")
        rep.figure_efficiency(all_rows, btt_sum, mr_sum, scen, ref, path)
        _put(f"efficiency_{scen}", path)
        path = os.path.join(paths["fig_design"],
                            f"figure_trajectory_{scen}.png")
        rep.figure_design_trajectory(traj_all, scen,
                                     int(bm.COMPARISON["trajectory_seed"]),
                                     ref, path)
        _put(f"trajectory_{scen}", path)
        _put(f"paired_{scen}", bfig.figure_paired_seeds(
            paired_seed, paired_sum, scen,
            os.path.join(paths["fig_overview"], f"figure_paired_{scen}.png")))
        # design behaviour
        _put(f"design_distribution_{scen}", bfig.figure_design_distribution(
            tables["design_selection_distribution"], scen,
            os.path.join(paths["fig_design"],
                         f"figure_design_distribution_{scen}.png")))
        _put(f"design_joint_{scen}", bfig.figure_design_joint(
            design_hist, scen,
            os.path.join(paths["fig_design"],
                         f"figure_design_joint_{scen}.png")))
        _put(f"spatial_density_{scen}", bfig.figure_spatial_density(
            tables["design_selection_distribution"], scen,
            os.path.join(paths["fig_design"],
                         f"figure_spatial_density_{scen}.png")))
        _put(f"design_by_round_{scen}", bfig.figure_design_by_round(
            tables["design_selection_by_round"], scen,
            os.path.join(paths["fig_design"],
                         f"figure_design_by_round_{scen}.png")))
        # parameters
        _put(f"parameter_performance_{scen}", bfig.figure_parameter_performance(
            tables["parameter_performance_summary"], scen,
            os.path.join(paths["fig_parameters"],
                         f"figure_parameter_performance_{scen}.png")))
        # resources
        _put(f"resource_summary_{scen}", bfig.figure_resource_summary(
            tables["resource_summary"], scen,
            os.path.join(paths["fig_resources"],
                         f"figure_resource_summary_{scen}.png")))
        _put(f"resource_components_{scen}", bfig.figure_resource_components(
            all_rows, scen,
            os.path.join(paths["fig_resources"],
                         f"figure_resource_components_{scen}.png")))
        # model-probability reliability, where the scenario has an ensemble
        spec = bm.SCENARIOS[scen]
        if len(getattr(spec, "family", ()) or ()) > 1:
            path = os.path.join(paths["fig_scenarios"],
                                f"figure_model_probs_reliability_{scen}.png")
            rep.figure_model_probability_reliability(
                audit_tables.get("model_probabilities_long", []), scen, path,
                truth_in_family=bool(spec.well_specified),
                tracked=spec.track_correct_model or "")
            _put(f"model_probs_reliability_{scen}", path)
            path = os.path.join(paths["fig_scenarios"],
                                f"figure_model_probs_{scen}.png")
            rep.figure_e_convergence(
                curves, "round", path,
                panels=(("p_correct", "P(correct model)"),
                        ("model_entropy", "model entropy / nats"),
                        ("param_err_pct", "parameter error / %"),
                        ("blind_rmse_M", "blind RMSE / M")))
            _put(f"model_probs_{scen}", path)
        # per-parameter convergence bands, for every strategy that ran
        for strat in sorted({r["strategy"] for r in all_prows
                             if r["scenario"] == scen}):
            path = os.path.join(paths["fig_parameters"],
                                f"figure_params_{scen}_{strat}.png")
            rep.figure_param_evolution(all_prows, scen, strat, path)
            _put(f"param_evolution_{scen}_{strat}", path)
            for x_key, x_label, tag in (
                    ("round", "campaign round", "round"),
                    ("nmr_acquisitions", "NMR acquisitions", "acq"),
                    ("time_s", "campaign time / s", "time")):
                _put(f"param_band_{scen}_{strat}_{tag}",
                     bfig.figure_parameter_bands(
                         all_prows, scen, strat,
                         os.path.join(
                             paths["fig_parameters"],
                             f"figure_param_band_{scen}_{strat}_{tag}.png"),
                         x_key=x_key, x_label=x_label, rows=all_rows))

    # ---- cross-cutting ---------------------------------------------------- #
    _put("precision_vs_accuracy", bfig.figure_precision_vs_accuracy(
        tables["parameter_performance_summary"],
        os.path.join(paths["fig_parameters"],
                     "figure_precision_vs_accuracy.png")))
    _put("nmr_performance", bfig.figure_nmr_performance(
        tables["nmr_performance_summary"],
        os.path.join(paths["fig_measurement"],
                     "figure_nmr_performance.png")))
    _put("quantification_validation", bfig.figure_quantification_validation(
        qv_rows, os.path.join(paths["fig_measurement"],
                              "figure_quantification_validation.png")))
    _put("transfer_ablation", bfig.figure_transfer_ablation_ladder(
        tables["transfer_effect_summary"],
        os.path.join(paths["fig_measurement"],
                     "figure_transport_ablation.png")))
    _put("transfer_decomposition", bfig.figure_transfer_decomposition(
        tables["transfer_decomposition_summary"],
        os.path.join(paths["fig_measurement"],
                     "figure_transfer_decomposition.png")))
    _put("robustness_dashboard", bfig.figure_robustness_dashboard(
        tables["robustness_summary"],
        os.path.join(paths["fig_robustness"],
                     "figure_robustness_dashboard.png")))
    _put("governor_validation", bfig.figure_governor_validation(
        gov, os.path.join(paths["fig_robustness"],
                          "figure_governor_validation.png")))
    _put("model_discrimination", bfig.figure_model_discrimination(
        tables["model_discrimination_summary"],
        os.path.join(paths["fig_scenarios"],
                     "figure_model_discrimination.png")))

    # ---- scenario-specific figures the framework already had -------------- #
    if "S5_inadequacy" in scenarios:
        s5 = [r for r in all_rows if r["scenario"] == "S5_inadequacy"]
        seed0 = seeds[0]
        naive = [r for r in s5 if r["strategy"] == "D" and r["seed"] == seed0]
        govd = [r for r in s5 if r["strategy"] == "F" and r["seed"] == seed0]
        if naive and govd:
            trip = next((r["round"] for r in govd
                         if r["gov_state"] == "MODEL_INADEQUATE"), None)
            path = os.path.join(paths["fig_scenarios"],
                                "figure_governor_S5.png")
            rep.figure_f_inadequacy(
                [r["round"] for r in naive],
                [min(r["max_rel_ci_pct"], 1e4) for r in naive],
                [r["param_err_pct"] for r in naive],
                [g["gov_score"] for g in govd],
                [g["gov_state"] for g in govd], trip, path)
            _put("governor_S5", path)
    if "S6_resources" in scenarios:
        finals6 = _finals(all_rows, "S6_resources")
        pts = {k: v for k, v in finals6.items() if "blind_rmse_M" in v}
        path = os.path.join(paths["fig_resources"], "figure_pareto_S6.png")
        rep.figure_g_resources(pts, path)
        _put("pareto_S6", path)
        path = os.path.join(paths["fig_resources"],
                            "figure_pareto_S6_labeled.png")
        rep.figure_pareto_labeled(pts, path)
        _put("pareto_S6_labeled", path)
    if "S7_spatial_modes" in scenarios:
        curves = _mean_curves(all_rows, "S7_spatial_modes")
        path = os.path.join(paths["fig_scenarios"],
                            "figure_spatial_modes_S7.png")
        rep.figure_e_convergence(
            curves, "nmr_acquisitions", path,
            panels=(("param_err_pct", "parameter error / %"),
                    ("blind_rmse_M", "blind RMSE / M"),
                    ("spatial_samples", "axial samples used"),
                    ("time_s", "campaign time / s")))
        _put("spatial_S7", path)
        path = os.path.join(paths["fig_design"], "figure_spatial_value.png")
        rep.figure_spatial_value(all_rows, "S7_spatial_modes", path)
        _put("spatial_value", path)

    # ---- the audit trail's own extras ------------------------------------- #
    if audit_on:
        _write_rows(
            asum.parameter_domain_check_rows(
                lambda: __import__("sdl").ParameterSpace(
                    t_ref_K=t_ref_K, initial_guess=dict(guess)),
                scenarios, bm.SCENARIOS, bm.check_truth_in_domain),
            os.path.join(paths["data"], "parameter_domain_checks.csv"))
        if cfg.get("audit_examples", True):
            edir = os.path.join(paths["audit"], "nmr_examples")
            _write_rows(nex.generate(bm.ACQ, bm.NMR_NUISANCE_TRUE, edir),
                        os.path.join(edir, "nmr_examples_summary.csv"))
            path = os.path.join(paths["fig_measurement"],
                                "figure_nmr_examples.png")
            rep.figure_nmr_examples(
                nex.spectra_for_plot(bm.ACQ, bm.NMR_NUISANCE_TRUE), path)
            _put("nmr_examples", path)

    # ==== THE REPORT ======================================================= #
    tl = bm.TRANSFER_TRUE
    bhtml.build_report(
        os.path.join(paths["report"], "benchmark_report.html"),
        meta={
            "run_kind": cfg["run_kind"], "run_label": cfg.get("run_label"),
            "mode": cfg["mode"], "seeds": ", ".join(str(s) for s in seeds),
            "n_seeds": len(seeds), "budget": budget,
            "commit": prov.get("describe") or "unknown",
            "dirty": bool(prov.get("dirty")),
            "framework_version": "v6",
            "design_space": ("continuous within bounds, snapped to the "
                             "instrument resolution"
                             if bm.DESIGN_SPACE.get("continuous")
                             else "discrete factorial grid"),
            "reactor": (f"L = {geom_scan['length_m'] * 100:.1f} cm, "
                        f"ID = {geom_scan['diameter_m'] * 1e3:.1f} mm, "
                        + ("packed bed"
                           if geom_scan.get("packing_enabled")
                           else "open tube")
                        + (" (sized by the geometry optimizer)"
                           if bm.GEOMETRY_DESIGN.get("enabled", False)
                           else " (declared)")),
            "transfer": ("disabled" if not tl.enabled else
                         (f"T_line = {tl.T_line_C} degC, RTD {tl.rtd}, "
                          f"carryover {bool(tl.carryover)}, in-line reaction "
                          f"{bool(tl.react_in_line)}")),
            "kappa": (f"{allowance['kappa']:.4f} (derived from control data)"
                      if allowance is not None
                      else f"{bm.GOVERNOR['systematic_allowance_nmr']} "
                           f"(pinned in CONFIG)"),
            "non_default": ", ".join(nd) if nd else "none",
            "parallelism": par.describe_workers(cfg.get("n_workers", "auto")),
            "runtime": f"{(time.time() - t0) / 60.0:.1f} min so far",
        },
        tables=tables, figures=figs, files=files, gov=gov,
        integrity=integrity, specs=bm.SCENARIOS, scenarios=list(scenarios))

    # ---- reproducibility record ----------------------------------------- #
    fp_rows = [r for r in all_rows
               if r["scenario"] in ("S1_ideal", "S2_nmr")
               and r["strategy"] == "F"]
    n_fp = sum(1 for r in fp_rows if r["gov_state"] == "MODEL_INADEQUATE")
    with open(os.path.join(paths["config"], "benchmark_config.json"),
              "w") as fh:
        json.dump({
            "framework_version": "v6",
            "run_kind": cfg["run_kind"],
            "is_publication_run": cfg["run_kind"] == "publication",
            "git": prov,
            # EVERY switch, its value and its explanation - no hidden
            # defaults survive in an archived run
            "features_resolved": resolved_knobs["FEATURES_RESOLVED"],
            "systematic_allowance_derivation": (
                allowance if allowance is not None
                else {"kappa": bm.GOVERNOR["systematic_allowance_nmr"],
                      "source": "pinned in CONFIG"}),
            "plug_flow_criteria": dataclasses.asdict(
                bm.validity_criteria()),
            "permitted_flows_mL_min": bm.permitted_flows(),
            "CONFIG": {k: v for k, v in cfg.items()},
            "mode_resolved": {"seeds": list(seeds), "budget": budget,
                              "scenarios": list(scenarios)},
            # execution environment: affects WALL TIME only.  Every result
            # file is reassembled in submission order and every campaign is
            # seeded from its own (scenario, strategy, seed), so these
            # numbers do not enter any reported quantity.
            # every knob's RESOLVED value - what the run actually used,
            # not what the defaults happen to be today
            "knobs_resolved": resolved_knobs,
            "execution": {"n_workers_resolved": n_proc,
                          "threads_per_worker": threads,
                          "cpu_count": os.cpu_count(),
                          "start_method": "spawn" if n_proc > 1 else "none",
                          "platform": sys.platform},
            "runtimes_s": runtimes,
            "per_round_false_inadequacy_S1_S2":
                (n_fp / len(fp_rows)) if fp_rows else None,
            "governor_validation": gov,
            "truth": bm.TRUTH, "geometry": bm.GEOMETRY, "design": bm.DESIGN,
            # the spec plus its RESOLVED transfer line and RESOLVED
            # candidate family: the spec stores the ablation, the feature
            # switches decide the rest, and the archive must show the answer
            "scenarios": {k: {**dataclasses.asdict(v),
                              "transfer_resolved": dataclasses.asdict(
                                  v.transfer),
                              "family_resolved": list(
                                  bm.scenario_family(v))}
                          for k, v in bm.SCENARIOS.items()
                          if k in scenarios},
            "nmr_nuisance_true": dataclasses.asdict(bm.NMR_NUISANCE_TRUE),
            "acquisition": dataclasses.asdict(bm.ACQ),
            # REQUESTED **and** ACTUAL acquisition quantities: an archive
            # cannot claim one acquisition time while having simulated
            # another (spectral.AcquisitionSettings.acquisition_report)
            "acquisition_resolved": bm.ACQ.acquisition_report(),
            "reactor_validity": validity_rows,
            "reactor_validity_verdict": bm.rv.explain(
                geom_scan, bm.permitted_flows(), bm.validity_criteria()),
            "nmr_measurement_time": bm.RESOURCE_COSTS.with_acquisition(
                bm.ACQ).nmr_time_report(),
            "transfer_true": dataclasses.asdict(bm.TRANSFER_TRUE),
        }, fh, indent=2, default=str)
    if audit_on:
        # LAST, so the checksums cover every file the run produced
        manifest = asum.reproducibility_manifest(
            outdir, os.path.dirname(os.path.abspath(__file__)),
            cfg, {"seeds": list(seeds), "budget": budget,
                  "scenarios": list(scenarios),
                  "governor_mc_seeds": list(gov_seeds),
                  "n_workers_resolved": n_proc,
                  "threads_per_worker": threads,
                  "nmr_example_seed": nex.EXAMPLE_SEED},
            {"runtimes_s": runtimes})
        mp_path = os.path.join(paths["audit"],
                               "reproducibility_manifest.json")
        with open(mp_path, "w") as fh:
            json.dump(manifest, fh, indent=2, default=str)
        print(f"saved: {os.path.relpath(mp_path)}  "
              f"({len(manifest['checksums']['files'])} files checksummed)")

    if bar is not None:
        bar.n = bar.total          # snap to 100% (weights are estimates)
        bar.refresh()
        bar.close()
    print(f"\nBenchmark finished in {(time.time() - t0) / 60.0:.1f} min. "
          f"Outputs in: {os.path.relpath(outdir)}")


if __name__ == "__main__":
    # Required before any pool is created when this script is frozen into a
    # Windows executable; a no-op otherwise.  The __main__ guard itself is
    # what makes `spawn` safe on Windows and macOS.
    multiprocessing.freeze_support()
    main()
