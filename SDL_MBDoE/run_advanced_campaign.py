"""
Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling
capillary) + Bruker Fourier 80 virtual instrument.

Runs ONE campaign per strategy listed in CONFIG["strategies"], on the
scenario named in CONFIG["scenario"], on the SAME virtual laboratory class,
and writes a complete, auditable scientific record of the run.

WHAT THE RUN PRODUCES, under CONFIG["outdir"]:

    config/     the fully resolved configuration, feature switches, scenario
                definition, reactor validity, NMR and transfer settings
    data/       the machine-readable record - one CSV per aspect of the
                campaign, with campaign_rounds.csv as the central per-round
                table.  THESE FILES ARE AUTHORITATIVE.
    figures/    the figure set: experimental trajectory, spatial sampling,
                measured profiles, parameter convergence and accuracy,
                uncertainty and identifiability, posterior correlation,
                model probabilities, design and spatial-design diagnostics,
                NMR deconvolutions, transfer-line decomposition, QC,
                governor, resources and the final strategy comparison
    spectra/    the deconvolutions the campaign actually acquired, as CSV
    report/     campaign_report.html - a readable account of the run that
                links everything above

REPORTING IS NOT ALLOWED TO CHANGE SCIENCE.  Every table and figure is
derived AFTER a campaign has returned, from what it retained (`res`,
`res.history`, the inference/ensemble objects, `lab.meter`, measurement
metadata and the passive audit recorder).  The reporting layer draws no
random number and re-evaluates nothing stochastic, so a run with reporting
on produces exactly the campaign a run without it would have produced -
tests/test_audit_regression.py asserts that bit-for-bit.

GROUND-TRUTH FIREWALL.  This is a simulation, so the true kinetics exist.
They are read ONLY after the campaign ends, through the same post-campaign
scoring the benchmark uses (`param_err_pct`, `blind_rmse_M`) plus
`lab.reveal_transfer_log()`, which is counted as a truth reveal exactly like
`reveal_truth()`.  Truth-derived quantities are labelled as validation
wherever they appear, and no controller-side object is ever handed one.

IDE workflow: edit CONFIG below and press Run.  Everything needed for exact
reproduction (CONFIG + seeds) is written to <outdir>/config/config_used.json.
"""

from __future__ import annotations

import os

# --------------------------------------------------------------------- #
# Numerical threads are pinned BEFORE numpy/scipy are imported, because a
# BLAS backend reads these at import time and cannot be reconfigured
# afterwards.  One thread per process is what makes an N-worker run
# reproduce a one-core run digit for digit (a threaded BLAS reduction sums
# in a nondeterministic order), and it costs nothing here: the linear
# algebra is 6x6 parameter blocks.  Spelled out rather than imported from
# sdl_advanced.parallel because importing anything from that PACKAGE runs
# sdl_advanced/__init__.py, which imports numpy - too late.
# --------------------------------------------------------------------- #
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import dataclasses                                              # noqa: E402
import json                                                     # noqa: E402
import multiprocessing                                          # noqa: E402
import time                                                     # noqa: E402

import numpy as np                                              # noqa: E402

try:                                    # progress bar (optional dependency)
    from tqdm.auto import tqdm
except ImportError:                     # pragma: no cover - fallback
    tqdm = None

from sdl import Layer1Bridge                                    # noqa: E402
from sdl_advanced import audit_export as aex                    # noqa: E402
from sdl_advanced import benchmark as bm                        # noqa: E402
from sdl_advanced import campaign_export as cex                 # noqa: E402
from sdl_advanced import campaign_figures as cfig               # noqa: E402
from sdl_advanced import campaign_html as chtml                 # noqa: E402
from sdl_advanced import features as feat                       # noqa: E402
from sdl_advanced import parallel as par                        # noqa: E402
from sdl_advanced import reporting as rep                       # noqa: E402
from sdl_advanced.audit import AuditRecorder                    # noqa: E402
from sdl_advanced.spatial_design import (SensitivityField,      # noqa: E402
                                         SpatialDesigner,
                                         fixed_equal_positions)
from sdl_advanced.spectral import NMRSimulator                  # noqa: E402
from sdl_advanced.spectral_fit import SpectralFitter            # noqa: E402

CONFIG = {
    "seed": 7,
    "budget": 8,                  # reactor conditions per strategy
    "scenario": "S3_transport",   # the full-physics demonstration
    "strategies": ["A", "B", "C", "D", "E", "F"],

    # V6 results live in their own tree; results_advanced_v5 is a COMPLETED
    # ARCHIVE of the previous framework and is never written to again.
    # "validation" marks this as a code/figure run, not publication numbers.
    "outdir": "results/campaign_v6/S3_transport/PFR_L200mm_D7mm",
    "allow_overwrite": False,
    # Monte-Carlo size of the instrument-level quantification-recovery
    # figure (its own generator, run after the campaign)
    "n_recovery_mc": 120,
    # Weighted progress bar over the strategies, with % done and an ETA.
    # One tick per COMPLETED campaign, weighted by
    # bm.campaign_cost_units(strategy, budget) - equal weights would look
    # stalled on F, which costs roughly seven times an A campaign.
    "progress": True,
    # Per-round campaign lines.  Left ON by default: this runner exists to
    # watch ONE campaign in detail, and the bar is drawn on stderr while
    # these go to stdout, so they coexist.  Turn it off for a clean bar.
    # Forced OFF when workers > 1, where six campaigns would interleave
    # their round lines into noise.
    "verbose_rounds": True,

    # ---- parallelism (identical results at any setting) ---------------- #
    # ONE STRATEGY = ONE TASK.  The strategies of a campaign are independent
    # (each seeds its own laboratory and selector from the same
    # scenario/strategy/seed), so they simply spread over processes:
    #   1             -> serial, no multiprocessing machinery at all
    #   None / "auto" -> every core but one
    #   0             -> every core
    #   n             -> exactly n processes
    # Results are reassembled in SUBMISSION order, never completion order,
    # so every saved file is identical to a one-core run at any setting -
    # see the note above `_campaign_task`.  The default is 1 because the
    # shipped two-strategy campaign gains little against the process
    # start-up cost; raise it when running the full A-F set.
    "n_workers": "auto",
    # BLAS threads INSIDE each worker.  Keep at 1: it prevents
    # oversubscription and it is the setting under which parallel output is
    # bit-identical to serial output.
    "threads_per_worker": 1,
}

# ========================================================================= #
# EVERY SCIENTIFIC KNOB for THIS campaign
# ========================================================================= #
# This runner owns its configuration outright - it does not import the
# benchmark's.  The demonstration campaign is often the thing you want to
# poke at (a different reactor, a hotter transfer line) without disturbing a
# publication benchmark, and a script importing another script to borrow its
# globals couples two entry points that have no reason to be coupled.
#
# The risk that buys back is DRIFT: figures produced here can end up
# describing a different system from the numbers in the benchmark.  That is
# handled by making divergence VISIBLE rather than impossible - the run
# prints every knob that differs from the library default, and the complete
# resolved configuration is written to <outdir>/config/config_used.json.
KNOBS = {
    # ===================================================================== #
    # (1) FEATURE SWITCHES - WHAT IS SIMULATED AT ALL
    # ===================================================================== #
    # One True/False per optional effect, exactly as in
    # the benchmark runner.  The catalogue, the three-part explanation
    # of every switch and the routing live in sdl_advanced/features.py, and
    # the fully resolved state is written to config/features_resolved.json
    # with every run.  Starting from `feat.defaults()` and listing only the
    # DELTAS here is deliberate: duplicating 40 explained switches in two
    # runners is the drift this refactor exists to remove, and the resolved
    # record shows every value regardless of where it came from.
    "FEATURES": {**feat.defaults(),
                 # this demonstration runs in the declared reactor
                 "geometry_optimization": False},
    # Deliberate truth/inference divergence, OFF by default (see the
    # benchmark runner for the full commentary).
    "MODEL_MISMATCH": feat.mismatch_defaults(),

    # ===================================================================== #
    # (2) MAGNITUDES
    # ===================================================================== #
    # ---- reactor ------------------------------------------------------- #
    # packing_enabled / bed_void_fraction are derived from
    # FEATURES["packed_bed_reactor"].
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
        "T_C_levels": [40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160],
        "Q_total_mL_min_levels": [0.5, 1.0, 2.0, 3.0, 4.0],
        "C_cat_M_levels": [0.1, 0.5, 1.0],
        "C_EGDA_M_levels": [0.1, 0.5, 1.0],
        "C_EGDA_M": 1.0,            # For the fixed-design baseline, the optimizer is not allowed to change it.
        "fixed_design_T_C": [40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160],
        "nominal_Q_total_mL_min": 1.0,
        "nominal_C_cat_M": 0.5,
        "continuous_bounds": {"T_C": [40.0, 160.0],
                              "Q_total_mL_min": [0.5, 4.0],
                              "C_cat_M": [0.1, 1.0],
                              "C_EGDA_M": [0.1, 1.0]},   # lo == hi -> fixed
    },
    # CONTINUOUS vs DISCRETE design.  False = the classical grid-only
    # campaign (the published v3 behaviour).  True = the optimizer may
    # propose any point inside continuous_bounds, snapped to the resolution
    # the hardware can actually command, and accepted only when it strictly
    # beats the best grid point - so it can never do worse.
    # `continuous` lives in FEATURES["continuous_design_space"].
    "DESIGN_SPACE": {
        "resolution": {
            "T_C": 0.1,
            "Q_total_mL_min": 0.1,
            "C_cat_M": 1e-4,
            "C_EGDA_M": 1e-4,
        },
        "continuous_maxiter": 80,
        "continuous_restarts": 4,
    },


    # ---- reactor geometry as a DESIGN VARIABLE (optional) --------------- #
    # enabled=False -> "I have this reactor, what experiments?"  (default)
    # enabled=True  -> "I am building a reactor for this chemistry, what
    #                   geometry AND what experiments?"  The reactor is
    #                   sized once from the PRIOR before round 1, honouring
    #                   DESIGN_SPACE["continuous"] for the refinement.
    # NOTE: with this on, blind RMSE is computed in the CHOSEN reactor, so
    # it stays comparable across strategies but not across runs with
    # different geometry settings - the prediction target itself moves.
    # `enabled` lives in FEATURES["geometry_optimization"]; `packing`
    # follows FEATURES["packed_bed_reactor"].
    "GEOMETRY_DESIGN": {
        "mode": "per_campaign",       # "per_experiment" raises: not implemented
        "bounds": {"length_m": [0.05, 0.60],
                   "diameter_m": [0.002, 0.012]},
        "levels": {"length_m": [0.10, 0.20, 0.40, 0.60],
                   "diameter_m": [0.004, 0.007, 0.010]},
        "resolution": {"length_m": 0.005, "diameter_m": 0.0005},
        "switch_cost_s": 1800.0,
        # Ideality: an open laminar tube violates plug flow when
        # t_rad/tau = Q/(pi D L eps) exceeds max_radial_ratio (Layer 1's own
        # advisory boundary; the bore cancels - only length/flow/holdup
        # help).  Infeasible candidates are rejected; "auto" also offers
        # every geometry as a PACKED bed (spherical beads, eps ~ 0.4), the
        # standard engineering fix, which is treated as plug-flow valid
        # under the documented d_p <= d/10, L/d_p >= 100 assumption.
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
    # The geometry optimizer rejects candidates above max_radial_ratio; this
    # applies the same standard to whichever reactor actually runs, so the
    # baseline is not exempt from the criterion the framework enforces
    # elsewhere.  "warn" | "error" | "ignore".
    #
    # NOTE: the shipped 20 cm OPEN tube FAILS this at every design flow
    # (t_rad/tau = 13-212 vs a threshold of 10).  Packing it
    # (GEOMETRY["packing_enabled"] = True, bed_void_fraction 0.4) is the
    # engineering fix and makes the flagship configuration satisfy its own
    # criterion; it also shortens tau by eps, which changes conversions and
    # therefore every published number - a deliberate decision, not a
    # silent default change.
    "VALIDITY": {
        "criteria": {
            "max_radial_ratio": 10.0,
            "min_bodenstein": 100.0,
            "bed_to_particle_ratio": 10.0,
            "min_bed_aspect": 100.0,
            "packed_peclet_axial": 0.5,
            "packed_peclet_radial": 10.0,
            "tortuosity": 1.4,
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
    "TRANSFER_TRUE": {
        "Q_sample_mL_min": 0.5,
        "V_fixed_mL": 0.15,
        "geometry": "constant",        # "constant" | "linear"
        "v_per_m_mL": 0.0,
        "n_tanks": 4.0,
        "n_quad": 5,
        "flush_volumes": 3.0,
    },
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

    # ---- spatial sampling ------------------------------------------------ #
    "SPATIAL": {
        "candidate_grid_size": 101,
        "z_min_fraction": 0.02,
        "z_max_fraction": 1.0,
        "min_spacing_fraction": 0.02,
        "continuous_refinement": True,
        "marginal_information_threshold": 0.05,
    },

    # ---- quantification error model (magnitudes) ------------------------- #
    "QUANTIFICATION": {
        "sigma_floor_abs_M": 0.002,
        "sigma_floor_rel": 0.03,
        "gain_drift_rel": 0.01,
        "shift_jitter_ppm": 0.001,
    },
    # ---- truth-side fault magnitudes (whether they happen is FEATURES) --- #
    "FAULT_MODEL": {
        "spectrum_fault_prob": 0.02,
        "spectrum_fault_amplitude_sigma": 400.0,
        "outlier_prob": 0.01,
        "outlier_scale_sigma": 8.0,
    },
    "LEGACY_NMR_TIME_S": 60.0,

    # ---- Bayesian design (strategy F) ------------------------------------ #
    "ADVANCED_DESIGN": {
        "top_k": 5,
        "n_particles": 64,
        "n_outer": 64,
        "alpha_param": 1.0,
        "beta_model": 1.0,
        "beta_model_discrimination": 4.0,
    },

    # ---- model-inadequacy governor --------------------------------------- #
    "GOVERNOR": {
        "alpha_campaign": 0.05,
        "discrimination_prob": 0.90,
        "qc_fail_fraction": 0.25,
        "chi2_dof_ratio_override": 25.0,
        # kappa: DERIVED FROM CONTROL DATA (validation.derive_systematic_
        # allowance), never tuned on benchmark performance.  Re-derive it
        # whenever the NMR calibration changes.
        "systematic_allowance_nmr": "auto",
        "systematic_allowance_direct": 0.0,
        "allowance_seed": 0,
        "allowance_n_rep": 3,
        "allowance_n_control": 80,
        "allowance_stride": 3,
    },

    # ---- measurement-fault QC gate ---------------------------------------- #
    "QC_GATE": {
        "max_retries": 1,              # reacquisitions per failing position
        "max_reject_fraction": 0.5,    # batch rule
        "min_batch_for_fraction": 4,   # below this, the fraction is ignored
        "max_consecutive_rejects": 3,  # persistence rule
        "rolling_window": 8,
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
        # the LEGACY lumped duration is
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


#: files whose presence means a completed run already lives in a directory.
#: Both the current layout (config/, data/) and the flat layout earlier runs
#: wrote are listed, so an archive produced by any version of this runner is
#: still protected.
_RUN_MARKERS = (os.path.join("config", "config_used.json"),
                os.path.join("data", "campaign_rounds.csv"),
                "config_used.json", "campaign_history.csv")


def resolve_outdir(outdir: str, allow_overwrite: bool = False) -> str:
    """Resolve the output directory, refusing to overwrite a completed run.

    An archived run is the only record of which code produced which figure;
    writing over it (or half over it) destroys that."""
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              outdir)
    existing = [m for m in _RUN_MARKERS
                if os.path.exists(os.path.join(outdir, m))]
    if existing and not allow_overwrite:
        raise FileExistsError(
            f"{outdir} already contains a completed run "
            f"({', '.join(existing)}).  Choose a different outdir, or set "
            f"CONFIG['allow_overwrite'] = True to replace your own "
            f"previous run.")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _figure_spatial_value(spec, outdir: str) -> str:
    """True profile + equal vs optimized positions + information density.

    A REFERENCE illustration of why axial positions are not equally
    valuable, drawn for the configured scenario's truth and reactor at a
    deliberately curved operating point.  It runs on its own fixed seed
    after the campaign and shares no RNG with it."""
    lab = bm.make_lab(spec, seed=0)
    from sdl import OperatingConditions
    u = OperatingConditions(T_C=160.0, Q1_mL_min=0.25, Q2_mL_min=0.25,
                            C_EGDA_M=1.0, C_cat_M=1.0)   # curved profile
    bridge = Layer1Bridge(bm.GEOMETRY, bm.T_REF_C + 273.15,
                          activity_model="pitzer")
    L = lab.length_m
    z_prof = np.linspace(0.002, L, 120)
    flat = bridge.concentrations_at(spec.truth, u, z_prof, bm.SPECIES)
    prof = {sp: flat[i * len(z_prof):(i + 1) * len(z_prof)]
            for i, sp in enumerate(bm.SPECIES)}

    from sdl import ParameterSpace, literature_guess
    space = ParameterSpace(t_ref_K=bm.T_REF_C + 273.15,
                           initial_guess=literature_guess(
                               bm.T_REF_C + 273.15))
    theta = space.to_vector(space.initial_guess)
    designer = SpatialDesigner(
        bm._spatial_cfg("optimized"), L,
        lambda y: bm.NOISE_DIRECT.covariance(y, bm.SPECIES, 1))

    def predict(th, z):
        return bridge.concentrations_at(space.to_natural(th), u, z,
                                        bm.SPECIES)

    field = SensitivityField(predict, theta, space.fd_steps,
                             designer.candidate_grid(), len(bm.SPECIES))
    p = space.n_params
    z_opt = designer.positions(field, np.zeros((p, p)))
    z_eq = fixed_equal_positions(L, bm.N_PORTS)
    info_z, info_g = designer.information_density(field, np.eye(p) * 1.0)
    path = os.path.join(outdir, "figure_spatial_value.png")
    rep.figure_a_spatial_value(z_prof, prof, z_eq, z_opt, info_z, info_g,
                               path)
    return path


def _figure_recovery(outdir: str, n_mc: int, seed: int) -> str:
    """Truth vs deconvolved concentration over random compositions.

    Instrument-level validation of the quantification pathway, on its own
    generator; it is not part of the campaign and consumes none of its
    randomness."""
    from sdl_advanced.spectral_fit import calibrate_responses
    rng = np.random.default_rng(seed)
    sim = NMRSimulator(bm.ACQ, bm.NMR_NUISANCE_TRUE)
    fitter = SpectralFitter(bm.ACQ)
    calibrate_responses(fitter, lambda s, r: sim.simulate(s, r)[:2], rng)
    truths, ests, sigs = [], [], []
    for _ in range(n_mc):
        c = {"EGDA": rng.uniform(0.0, 0.5), "EGMA": rng.uniform(0.0, 0.3),
             "EG": rng.uniform(0.0, 0.3), "AcOH": rng.uniform(0.0, 0.6),
             "H2O": rng.uniform(45.0, 55.0)}
        ppm, y, _ = sim.simulate(c, rng)
        res = fitter.fit(ppm, y)
        truths.append([c[sp] for sp in fitter.species])
        ests.append(res.conc_M)
        sigs.append(np.sqrt(np.diag(res.cov)))
    path = os.path.join(outdir, "figure_quantification_recovery.png")
    rep.figure_d_truth_vs_recovered(
        np.array(truths), np.array(ests), np.array(sigs), fitter.species,
        path)
    return path


# ========================================================================= #
# THE UNIT OF PARALLEL WORK
# ========================================================================= #
def _campaign_task(scenario_name: str, strategy: str, seed: int, budget: int,
                   store_spectra: bool, verbose: bool):
    """ONE strategy's campaign, as a picklable function of its labels.

    WHY THE OUTPUT IS THE SAME AT ANY WORKER COUNT.  Three things, none of
    them accidental:

      1. Each campaign is an INDEPENDENT, pure function of (scenario,
         strategy, seed, budget).  The laboratory seeds its own
         `default_rng(seed)` and the selector seeds `default_rng(seed +
         offset)`; nothing reads global RNG state, so no campaign can
         observe how many others are running.
      2. `par.ordered_map` reassembles results by SUBMISSION index, never by
         completion order, so `recs` is in `CONFIG["strategies"]` order
         whichever worker finishes first - and every CSV row, every figure
         and every report section is built by walking `recs`.
      3. BLAS threads are pinned to one (see the module header), so a
         floating-point reduction sums in the same order whether a campaign
         runs alone or beside five others.

    The scenario is looked up by NAME rather than passed in: a spawned
    worker re-imports the benchmark module and must use ITS definition
    rather than a pickled copy, and the knobs are replayed into that module
    by `bm.worker_init` before any task runs.

    Returns the retained campaign objects themselves rather than derived
    rows.  That is the opposite of the benchmark's `campaign_task`, and
    deliberately so: this runner's whole reporting layer reads `res`,
    `lab`, `extra` and the recorder directly, so deriving anything in the
    worker would mean shipping the objects back as well AND maintaining a
    second derivation path that could drift from the serial one.
    """
    spec = bm.SCENARIOS[scenario_name]
    recorder = AuditRecorder(spec.name, strategy, seed, bm.SPECIES)
    res, lab, extra = bm.run_one_campaign(
        spec, strategy, seed, budget, verbose=verbose,
        store_spectra=store_spectra, recorder=recorder,
        store_transfer_log=True)
    return res, lab, extra, recorder


# ========================================================================= #
# REPORTING.  Everything below runs AFTER every campaign has returned.
# ========================================================================= #
def _spatial_mode_of(spec, strategy: str) -> str:
    """The spatial policy this strategy actually ran, resolved the same way
    benchmark.campaign_task resolves it."""
    default = ("optimized" if strategy == "E" or strategy.startswith("F")
               else "fixed_equal")
    return str(spec.f_variants.get(strategy, {}).get("spatial_mode", default))


def _truth_predictor(spec, geometry):
    """(u, z, species) -> the hidden TRUE reactor composition.

    POST-CAMPAIGN ONLY.  It is the same truth-side forward model the
    benchmark already evaluates to score `blind_rmse_M`, built here so the
    report can draw measured points against the profile that produced them.
    It is handed to the reporting layer and to nothing else."""
    bridge = Layer1Bridge(geometry, bm.T_REF_C + 273.15, **bm.TRUTH_CHEMISTRY)

    def predict(u, z, species):
        return bridge.concentrations_at(spec.truth, u,
                                        np.asarray(z, dtype=float),
                                        tuple(species))
    return predict


def _write_tables(recs, paths) -> dict:
    """Every machine-readable table of the campaign, in `data/`.

    The audit tables come straight from `audit_export`/the passive recorder,
    concatenated across the strategies that ran; the campaign-centred ones
    are built by `campaign_export`.  Nothing is computed twice."""
    data = paths["data"]
    audit_all: dict = {}
    for rc in recs:
        for k, rows in (rc.audit or {}).items():
            audit_all.setdefault(k, []).extend(rows)

    measurements = cex.measurement_rows(recs)
    tables = {
        "campaign_rounds": cex.round_rows(recs),
        "measurements": measurements,
        "concentrations": cex.concentration_rows(recs),
        "kinetic_parameters": cex.parameter_rows(recs),
        "posterior_covariance": audit_all.get("posterior_covariance_long", []),
        "model_probabilities": audit_all.get("model_probabilities_long", []),
        "design_candidate_scores": audit_all.get("design_candidate_scores", []),
        "spatial_candidate_scores": audit_all.get("spatial_candidate_scores",
                                                  []),
        "qc_history": cex.qc_rows(recs, measurements),
        "governor_history": audit_all.get("governor_diagnostics_long", []),
        "resource_history": cex.resource_round_rows(recs),
        "resource_events": audit_all.get("resource_events_long", []),
        "transfer_history": cex.transfer_rows(recs),
        "controller_timing": audit_all.get("controller_timing", []),
        "design_history": audit_all.get("design_history", []),
        "identifiability": audit_all.get("identifiability_summary", []),
        "blind_predictions": audit_all.get("blind_predictions_long", []),
        "nmr_calibration": audit_all.get("nmr_calibration_by_seed", []),
        "strategy_comparison": cex.strategy_summary_rows(recs),
    }
    files = {name: cex.write_rows(rows, os.path.join(data, f"{name}.csv"))
             for name, rows in tables.items()}
    return {"tables": tables, "files": files}


def _write_figures(recs, tables, paths) -> dict:
    """Every figure of the campaign, in `figures/`.

    Each builder is handed the exported rows and returns None when this
    scenario/strategy has nothing to show, so a run omits the figures that
    would be meaningless rather than drawing empty axes."""
    fdir = paths["figures"]

    def at(name):
        return os.path.join(fdir, f"figure_{name}.png")

    figs = {
        "conditions": cfig.figure_conditions(tables["campaign_rounds"],
                                             at("conditions")),
        "positions": cfig.figure_positions(tables["campaign_rounds"],
                                           at("positions")),
        "parameters": cfig.figure_parameter_convergence(
            tables["kinetic_parameters"], at("parameter_convergence")),
        "param_error": cfig.figure_parameter_error(
            tables["kinetic_parameters"], at("parameter_error")),
        "uncertainty": cfig.figure_uncertainty(
            tables["campaign_rounds"], tables["kinetic_parameters"],
            tables["posterior_covariance"], at("uncertainty")),
        "model_probs": cfig.figure_model_probabilities(
            tables["model_probabilities"], at("model_probabilities")),
        "qc": cfig.figure_qc(tables["qc_history"], tables["measurements"],
                             at("qc_diagnostics")),
        "governor": cfig.figure_governor(tables["governor_history"],
                                         at("governor_diagnostics")),
        "resources": cfig.figure_resources(tables["resource_history"],
                                           at("resources")),
        "comparison": cfig.figure_strategy_comparison(
            tables["strategy_comparison"], at("strategy_comparison")),
    }
    for rc in recs:
        s = rc.strategy
        figs[f"profiles_{s}"] = cfig.figure_concentration_profiles(
            tables["concentrations"], s, at(f"concentration_profiles_{s}"))
        figs[f"design_{s}"] = cfig.figure_design_decisions(
            tables["design_candidate_scores"], s, at(f"design_decisions_{s}"))
        figs[f"spatial_{s}"] = cfig.figure_spatial_design(
            tables["spatial_candidate_scores"], s, at(f"spatial_design_{s}"))
        figs[f"nmr_{s}"] = cfig.figure_nmr_diagnostics(
            getattr(rc.lab, "spectrum_log", ()), s, at(f"nmr_diagnostics_{s}"))
        figs[f"transfer_{s}"] = cfig.figure_transfer_diagnostics(
            tables["transfer_history"], s, at(f"transfer_diagnostics_{s}"))
        figs[f"correlation_{s}"] = cfig.figure_correlation_matrices(
            tables["posterior_covariance"], s, at(f"posterior_correlation_{s}"))
    return {k: v for k, v in figs.items() if v}


def main() -> None:
    cfg = CONFIG
    # apply the shared knobs (plus any campaign-specific override) BEFORE
    # anything reads the benchmark module's configuration
    # announce anything that is not the library default, so a demo figure
    # can never quietly describe a different system from the benchmark
    defaults = bm.resolved_config()
    resolved_knobs = bm.apply_config(dict(KNOBS))
    drift = []
    for name, cur in resolved_knobs.items():
        base = defaults.get(name)
        if isinstance(cur, dict) and isinstance(base, dict):
            drift += [f"{name}.{k}={cur[k]!r}" for k in sorted(cur)
                      if base.get(k) != cur[k]]
        elif base != cur:
            drift.append(f"{name}={cur!r}")
    outdir = resolve_outdir(cfg["outdir"],
                            bool(cfg.get("allow_overwrite", False)))
    paths = cex.prepare_outdir(outdir)
    spec = bm.SCENARIOS[cfg["scenario"]]
    strategies = list(cfg["strategies"])
    budget = int(cfg["budget"])
    seed = int(cfg["seed"])
    t0 = time.time()

    print("=" * 74)
    print(f"Advanced campaign demo - scenario {spec.name}: "
          f"{spec.description}")
    print(f"  budget {budget} conditions | strategies "
          f"{strategies} | seed {seed}")
    if drift:
        print("  non-default knobs: " + "; ".join(drift))
    print("  FEATURES (full state in config/features_resolved.json):")
    for line in feat.summary_lines(bm.FEATURES, bm.MODEL_MISMATCH):
        print(line)
    nd = resolved_knobs["FEATURES_RESOLVED"]["non_default"]
    print(f"    non-default switches: {', '.join(nd) if nd else 'none'}")
    print(f"  design space: "
          f"{'CONTINUOUS (snapped)' if bm.DESIGN_SPACE['continuous'] else 'DISCRETE grid'}"
          f" | transfer line T: {bm.TRANSFER_TRUE.T_line_C}")
    print("=" * 74)

    # ---- the campaigns --------------------------------------------------- #
    # The BLIND validation set and its truth vector are the benchmark's own,
    # so `param_err_pct` and `blind_rmse_M` here mean exactly what they mean
    # there.  Both are used only after a campaign has returned.
    geom = bm.active_geometry(budget)
    z_val = np.array([bm.GEOMETRY["length_m"] / 3.0, bm.GEOMETRY["length_m"]])
    y_true = bm._truth_prediction(spec.truth, z_val, geometry=bm.GEOMETRY)
    truth_predict = _truth_predictor(spec, geom)
    store_spectra = spec.observation_mode == "nmr"

    # ---- progress bar ---------------------------------------------------- #
    # Weighted by the SAME per-strategy cost model the benchmark's bar uses,
    # so the percentage tracks work rather than campaign count.  It is pure
    # telemetry: it reads a clock and a counter and touches nothing else.
    # ---- parallel plan ---------------------------------------------------- #
    # Children inherit the environment, so pinning here (before the pool is
    # created) configures every worker; the parent was already pinned at
    # import time, and the two must agree for serial and parallel to match.
    threads = int(cfg.get("threads_per_worker", 1) or 1)
    par.pin_numerical_threads(threads)
    n_proc = par.resolve_workers(cfg.get("n_workers", 1))
    # Per-round lines from six campaigns racing each other are noise, not
    # detail, so they are forced off whenever more than one process runs.
    # Nothing about the results changes - `verbose` only prints.
    verbose_rounds = bool(cfg.get("verbose_rounds", True)) and n_proc == 1
    print(f"  parallelism: {par.describe_workers(cfg.get('n_workers', 1))}"
          f", {threads} BLAS thread(s) each")
    if threads != 1:
        print("    WARNING: threads_per_worker != 1 - a threaded BLAS "
              "reduction sums in a nondeterministic order, so bit-identical "
              "agreement with a serial run is no longer guaranteed.")
    if n_proc > 1 and bool(cfg.get("verbose_rounds", True)):
        print("    per-round lines suppressed while workers > 1 "
              "(set n_workers = 1 to watch a campaign round by round)")

    total_units = sum(bm.campaign_cost_units(s, budget) for s in strategies)
    # float total, NOT round(): the updates are floats and their sum is
    # exactly total_units, so a rounded total lets the bar overshoot 100 %
    bar = (tqdm(total=float(total_units), unit="wu", dynamic_ncols=True,
                smoothing=0.05,
                bar_format="{l_bar}{bar}| {percentage:3.0f}% "
                           "[elapsed {elapsed} | remaining {remaining}]")
           if bool(cfg.get("progress", True)) and tqdm is not None else None)
    say = (lambda msg: (tqdm.write(msg) if bar is not None else print(msg)))

    # ---- COMPUTE PHASE ---------------------------------------------------- #
    # ONE STRATEGY = ONE TASK.  A worker re-imports the benchmark module and
    # therefore starts from DEFAULTS, so the resolved knobs are replayed
    # inside every process by `bm.worker_init` - a worker running a different
    # configuration from the parent is the worst possible failure, because
    # the numbers would still look plausible.
    tasks = [(spec.name, strategy, seed, budget, store_spectra,
              verbose_rounds) for strategy in strategies]
    executor = par.make_executor(
        cfg.get("n_workers", 1), initializer=bm.worker_init,
        initargs=(budget, dict(KNOBS)))

    # WHAT THE BAR MUST NAME: the campaign that is RUNNING, never the one
    # that just finished.  Naming the finished one leaves the bar frozen on
    # the previous strategy for the whole of the next campaign - and since
    # F costs roughly ten times any other strategy here, that reads as
    # "stuck on E" for minutes while F is in fact running normally.
    pending = list(strategies)

    def _starting(strategy):
        """SERIAL path only - the parent runs the campaigns itself, so it
        knows which one is about to start."""
        if bar is not None:
            bar.set_description(f"{spec.name}/{strategy}")
        say(f"\nStrategy {strategy}:")

    def _landed(_i, args, _out):
        """PARENT-SIDE PROGRESS ONLY.  Fires in completion order when
        parallel, so nothing that is saved may depend on when it runs."""
        strategy = args[1]
        if strategy in pending:
            pending.remove(strategy)
        if bar is not None:
            # clamped to what is left: `sum()` and repeated `+=` over the
            # same floats can disagree in the last bits, and a bar that
            # ends at 100.0000001 % emits a warning instead of a result
            bar.update(min(bm.campaign_cost_units(strategy, budget),
                           max(bar.total - bar.n, 0.0)))
            if executor is not None:
                # in parallel nothing knows what STARTED, but what is still
                # outstanding is just as useful and IS knowable
                bar.set_description(
                    f"{spec.name} | running: "
                    + (",".join(pending) if pending else "done"))
        say(f"  finished {spec.name}/{strategy} "
            f"({len(strategies) - len(pending)}/{len(strategies)})")

    if executor is None:
        def _run_task(*args):
            _starting(args[1])
            return _campaign_task(*args)
    else:
        _run_task = _campaign_task          # must stay picklable by name
        say(f"  submitted {len(strategies)} campaigns to {n_proc} "
            f"workers: {', '.join(strategies)}")
        if bar is not None:
            bar.set_description(f"{spec.name} | running: "
                                + ",".join(pending))

    t_compute = time.time()
    try:
        # SUBMISSION-ORDER reassembly: `outputs[i]` is the campaign of
        # `strategies[i]` whichever worker happened to finish first, so
        # every table, figure and report section built below is identical
        # to a one-core run at any worker count.
        outputs = par.ordered_map(_run_task, tasks, executor=executor,
                                  on_result=_landed)
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    t_compute = time.time() - t_compute

    # ---- POST-CAMPAIGN derivation, in the PARENT, in strategy order ------- #
    # Deliberately serial and deliberately here: ONE derivation path serves
    # both the serial and the parallel run, so the two cannot drift apart.
    recs = []
    for strategy, (res, lab, extra, recorder) in zip(strategies, outputs):
        spatial_mode = _spatial_mode_of(spec, strategy)
        audit = aex.collect_campaign(
            spec, strategy, seed, res, lab, extra, recorder, z_val, y_true,
            bm.VALIDATION_CONDS, bm.SPECIES, spatial_mode,
            scoring_bridge=bm._scoring_bridge)
        metric_rows, param_rows = bm._round_metrics(
            spec, strategy, res, lab, extra, z_val, y_true)
        recs.append(cex.CampaignRecord(
            scenario=spec.name, strategy=strategy, seed=seed, spec=spec,
            res=res, lab=lab, extra=extra, recorder=recorder, audit=audit,
            metric_rows=[dict(r, seed=seed) for r in metric_rows],
            param_rows=[dict(r, seed=seed) for r in param_rows],
            species=tuple(bm.SPECIES), length_m=float(lab.length_m),
            spatial_mode=spatial_mode, budget=budget,
            observation_mode=spec.observation_mode,
            # SIMULATION campaign: the truth exists and is used for
            # post-campaign validation only (see _truth_predictor)
            truth=dict(spec.truth), truth_predict=truth_predict))

    # ---- machine-readable record ----------------------------------------- #
    # The bar closes HERE, not at the end of the run: everything after this
    # point is reporting, and a bar that sat at 100 % through ten seconds of
    # figure drawing would be measuring the wrong thing.
    if bar is not None:
        bar.n = bar.total          # snap to 100% (the weights are estimates)
        bar.refresh()
        bar.close()
        bar = None
    print("\n" + "-" * 74)
    print("Campaign record")
    out = _write_tables(recs, paths)
    tables, files = out["tables"], out["files"]
    spectra_index = []
    for rc in recs:
        spectra_index += cex.export_spectra(rc, paths["spectra"],
                                            verbose=False)
    files["spectra_index"] = cex.write_rows(
        spectra_index, os.path.join(paths["spectra"], "spectra_index.csv"))

    # ---- figures ---------------------------------------------------------- #
    figs = _write_figures(recs, tables, paths)
    # two REFERENCE figures: not products of this campaign, but the
    # instrument- and design-level context it is read against.  Both run on
    # their own fixed generators after the campaign.
    figs["spatial_value"] = _figure_spatial_value(spec, paths["figures"])
    if spec.observation_mode == "nmr":
        figs["recovery"] = _figure_recovery(paths["figures"],
                                            int(cfg["n_recovery_mc"]), seed)

    # ---- reproducibility record ------------------------------------------ #
    cfg_path = os.path.join(paths["config"], "config_used.json")
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump({"framework_version": "v6",
                   "run_kind": "validation",
                   "is_publication_run": False,
                   "CONFIG": cfg,
                   "knobs_resolved": resolved_knobs,
                   # every switch, its value and its explanation
                   "features_resolved": resolved_knobs["FEATURES_RESOLVED"],
                   "plug_flow_criteria": dataclasses.asdict(
                       bm.validity_criteria()),
                   "reactor_validity": bm.reactor_validity_rows(),
                   "reactor_validity_verdict": bm.rv.explain(
                       bm.GEOMETRY, bm.permitted_flows(),
                       bm.validity_criteria()),
                   "scenario": {**dataclasses.asdict(spec),
                                "transfer_resolved": dataclasses.asdict(
                                    spec.transfer),
                                "family_resolved": list(
                                    bm.scenario_family(spec))},
                   "truth": bm.TRUTH, "geometry": bm.GEOMETRY,
                   "active_geometry": geom,
                   "design": bm.DESIGN,
                   "nmr_nuisance_true": dataclasses.asdict(
                       bm.NMR_NUISANCE_TRUE),
                   "nmr_nuisance_active_gates":
                       bm.NMR_NUISANCE_TRUE.active_gates(),
                   "acquisition": dataclasses.asdict(bm.ACQ),
                   "spatial_modes": {rc.strategy: rc.spatial_mode
                                     for rc in recs},
                   "output_layout": {k: os.path.relpath(v, outdir)
                                     for k, v in paths.items()
                                     if k != "root"}},
                  fh, indent=2, default=str)
    print(f"saved: {os.path.relpath(cfg_path)}")
    feat_path = os.path.join(paths["config"], "features_resolved.json")
    with open(feat_path, "w", encoding="utf-8") as fh:
        json.dump(resolved_knobs["FEATURES_RESOLVED"], fh, indent=2,
                  default=str)
    print(f"saved: {os.path.relpath(feat_path)}")
    files["config_used"] = cfg_path
    files["features_resolved"] = feat_path

    # ---- the human-readable account -------------------------------------- #
    chtml.build_report(
        os.path.join(paths["report"], "campaign_report.html"),
        meta={"scenario": spec.name, "description": spec.description,
              "strategies": strategies, "seed": seed, "budget": budget,
              "observation_mode": spec.observation_mode,
              "spatial_modes": ", ".join(f"{rc.strategy}: {rc.spatial_mode}"
                                         for rc in recs),
              "design_space": ("continuous (snapped to instrument "
                               "resolution)" if bm.DESIGN_SPACE["continuous"]
                               else "discrete grid"),
              "reactor": (f"L = {geom['length_m'] * 100:.1f} cm, "
                          f"ID = {geom['diameter_m'] * 1e3:.1f} mm, "
                          + ("packed bed" if geom.get("packing_enabled")
                             else "open tube")),
              "transfer": (f"enabled, T_line = {spec.transfer.T_line_C} degC, "
                           f"RTD {spec.transfer.rtd}, carryover "
                           f"{bool(spec.transfer.carryover)}"
                           if spec.transfer.enabled else "not used"),
              "nmr": (f"{bm.ACQ.spectrometer_MHz:.1f} MHz, "
                      f"{bm.ACQ.n_scans} scan(s), {spec.nmr_mode} mode"
                      if spec.observation_mode == "nmr"
                      else "direct concentration observation"),
              "non_default": ", ".join(nd) if nd else "none",
              "framework_version": "v6", "run_kind": "validation"},
        tables=tables, figures=figs, files=files,
        has_truth=any(rc.has_truth for rc in recs))

    # ---- what the run produced -------------------------------------------- #
    print("-" * 74)
    for rc in recs:
        row = next((r for r in tables["strategy_comparison"]
                    if r["strategy"] == rc.strategy), {})
        print(f"  {rc.strategy:>8s}: "
              f"{int(row.get('rounds_completed', 0))}/{budget} rounds | "
              f"param err {row.get('param_err_pct_final_vs_truth', float('nan')):.1f}% | "
              f"blind RMSE {row.get('blind_rmse_M_final_vs_truth', float('nan')):.2e} M | "
              f"stop: {row.get('stop_reason', '')}")
    # The two phases are timed apart because only the FIRST one is
    # parallel: reporting is serial by design, so a single total would
    # understate what more workers bought.
    total = time.time() - t0
    print(f"\nDone in {total:.1f} s "
          f"({t_compute:.1f} s campaigns on {n_proc} process(es), "
          f"{total - t_compute:.1f} s reporting).  Outputs in: {outdir}")
    print(f"  report:  {os.path.join(outdir, 'report', 'campaign_report.html')}")


if __name__ == "__main__":
    # Required before any pool is created when this script is frozen into a
    # Windows executable; a no-op otherwise.  The __main__ guard itself is
    # what makes `spawn` safe on Windows and macOS.
    multiprocessing.freeze_support()
    main()
