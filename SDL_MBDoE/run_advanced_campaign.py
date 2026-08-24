"""
Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling
capillary) + Bruker Fourier 80 virtual instrument.

Runs a single-seed strategy-F campaign under realistic NMR + transport
physics next to a strategy-D baseline on the SAME virtual laboratory class,
and produces Figures A-D (spatial value, position decisions, spectra,
concentration recovery) plus the campaign history CSV.

IDE workflow: edit CONFIG below and press Run.  Everything needed for exact
reproduction (CONFIG + seeds) is written to <outdir>/config_used.json.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time

import numpy as np

from sdl import Layer1Bridge, build_candidates, build_fixed_design
from sdl_advanced import benchmark as bm
from sdl_advanced import features as feat
from sdl_advanced import reporting as rep
from sdl_advanced.bayes_design import NoiseSurrogate
from sdl_advanced.instrument import InstrumentConfig
from sdl_advanced.spatial_design import (SensitivityField, SpatialDesigner,
                                         fixed_equal_positions)
from sdl_advanced.spectral import NMRSimulator, SpectralNuisance
from sdl_advanced.spectral_fit import SpectralFitter

CONFIG = {
    "seed": 7,
    "budget": 6,                  # reactor conditions per strategy
    "scenario": "S3_transport",   # the full-physics demonstration
    "strategies": ["D", "F"],
    # V6 results live in their own tree; results_advanced_v5 is a COMPLETED
    # ARCHIVE of the previous framework and is never written to again.
    # "validation" marks this as a code/figure run, not publication numbers.
    "outdir": "results_advanced_v6/validation/campaign",
    "allow_overwrite": False,
    "n_recovery_mc": 120,         # Figure D Monte Carlo size
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
# resolved configuration is written to <outdir>/config_used.json.
KNOBS = {
    # ===================================================================== #
    # (1) FEATURE SWITCHES - WHAT IS SIMULATED AT ALL
    # ===================================================================== #
    # One True/False per optional effect, exactly as in
    # the benchmark runner.  The catalogue, the three-part explanation
    # of every switch and the routing live in sdl_advanced/features.py, and
    # the fully resolved state is written to <outdir>/features_resolved.json
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
        "T_C_levels": [40, 60, 80, 100, 120, 140, 160],
        "Q_total_mL_min_levels": [0.5, 2.0, 8.0],
        "C_cat_M_levels": [0.5, 1.0],
        "C_EGDA_M_levels": [1.0],
        "C_EGDA_M": 1.0,            # For the fixed-design baseline, the optimizer is not allowed to change it.
        "fixed_design_T_C": [40, 60, 80, 100, 120, 140, 160],
        "nominal_Q_total_mL_min": 1.0,
        "nominal_C_cat_M": 0.5,
        "continuous_bounds": {"T_C": [40.0, 160.0],
                              "Q_total_mL_min": [0.5, 8.0],
                              "C_cat_M": [0.5, 1.0],
                              "C_EGDA_M": [1.0, 1.0]},   # lo == hi -> fixed
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
        "candidate_grid_size": 41,
        "z_min_fraction": 0.02,
        "z_max_fraction": 1.0,
        "min_spacing_fraction": 0.02,
        "continuous_refinement": False,
        "marginal_information_threshold": None,
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


def resolve_outdir(outdir: str, allow_overwrite: bool = False) -> str:
    """Resolve the output directory, refusing to overwrite a completed run.

    An archived run is the only record of which code produced which figure;
    writing over it (or half over it) destroys that."""
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              outdir)
    existing = [m for m in ("config_used.json", "campaign_history.csv")
                if os.path.exists(os.path.join(outdir, m))]
    if existing and not allow_overwrite:
        raise FileExistsError(
            f"{outdir} already contains a completed run "
            f"({', '.join(existing)}).  Choose a different outdir, or set "
            f"CONFIG['allow_overwrite'] = True to replace your own "
            f"previous run.")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _figure_a(outdir: str) -> None:
    """True profile + equal vs optimized positions + information density."""
    spec = bm.SCENARIOS["S1_ideal"]
    lab = bm.make_lab(spec, seed=0)
    from sdl import OperatingConditions
    u = OperatingConditions(T_C=160.0, Q1_mL_min=0.25, Q2_mL_min=0.25,
                            C_EGDA_M=1.0, C_cat_M=1.0)   # curved profile
    bridge = Layer1Bridge(bm.GEOMETRY, bm.T_REF_C + 273.15,
                          activity_model="pitzer")
    L = lab.length_m
    z_prof = np.linspace(0.002, L, 120)
    flat = bridge.concentrations_at(bm.TRUTH, u, z_prof, bm.SPECIES)
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
    rep.figure_a_spatial_value(z_prof, prof, z_eq, z_opt, info_z, info_g,
                               os.path.join(outdir, "figure_A_spatial.png"))


def _figure_d(outdir: str, n_mc: int, seed: int) -> None:
    """Truth vs deconvolved concentration over random compositions."""
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
    rep.figure_d_truth_vs_recovered(
        np.array(truths), np.array(ests), np.array(sigs), fitter.species,
        os.path.join(outdir, "figure_D_recovery.png"))


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
    spec = bm.SCENARIOS[cfg["scenario"]]
    t0 = time.time()

    print("=" * 74)
    print(f"Advanced campaign demo - scenario {spec.name}: "
          f"{spec.description}")
    print(f"  budget {cfg['budget']} conditions | strategies "
          f"{cfg['strategies']} | seed {cfg['seed']}")
    if drift:
        print("  non-default knobs: " + "; ".join(drift))
    print("  FEATURES (full state in features_resolved.json):")
    for line in feat.summary_lines(bm.FEATURES, bm.MODEL_MISMATCH):
        print(line)
    nd = resolved_knobs["FEATURES_RESOLVED"]["non_default"]
    print(f"    non-default switches: {', '.join(nd) if nd else 'none'}")
    print(f"  design space: "
          f"{'CONTINUOUS (snapped)' if bm.DESIGN_SPACE['continuous'] else 'DISCRETE grid'}"
          f" | transfer line T: {bm.TRANSFER_TRUE.T_line_C}")
    print("=" * 74)

    histories, results, labs = {}, {}, {}
    for strategy in cfg["strategies"]:
        print(f"\nStrategy {strategy}:")
        store = strategy.startswith("F")
        res, lab, extra = bm.run_one_campaign(
            spec, strategy, cfg["seed"], cfg["budget"], verbose=True,
            store_spectra=store)
        results[strategy], labs[strategy] = res, lab
        if hasattr(res, "history") and res.history and \
                hasattr(res.history[0], "z_positions"):
            histories[strategy] = res.history

    # ---- figures -------------------------------------------------------- #
    _figure_a(outdir)
    if histories:
        rep.figure_b_position_rounds(
            histories, labs[cfg["strategies"][0]].length_m,
            os.path.join(outdir, "figure_B_positions.png"))
    # Figure C from the first stored F-spectra
    for strategy in cfg["strategies"]:
        if not strategy.startswith("F"):
            continue
        for cm_meas in (results[strategy].ensemble.best.inference
                        .measurements):
            spectra = (cm_meas.meta or {}).get("spectra")
            if spectra:
                qc = cm_meas.meta["qc"]
                pick = list(range(min(3, len(spectra))))
                rep.figure_c_spectrum(
                    [spectra[i] for i in pick], [qc[i] for i in pick],
                    [cm_meas.z_m[i] for i in pick],
                    labs[strategy].length_m,
                    os.path.join(outdir, "figure_C_spectra.png"))
                break
        break
    _figure_d(outdir, cfg["n_recovery_mc"], cfg["seed"])

    # ---- reproducibility record ----------------------------------------- #
    with open(os.path.join(outdir, "config_used.json"), "w",
              encoding="utf-8") as fh:
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
                   "design": bm.DESIGN,
                   "nmr_nuisance_true": dataclasses.asdict(
                       bm.NMR_NUISANCE_TRUE),
                   "nmr_nuisance_active_gates":
                       bm.NMR_NUISANCE_TRUE.active_gates(),
                   "acquisition": dataclasses.asdict(bm.ACQ)},
                  fh, indent=2, default=str)
    with open(os.path.join(outdir, "features_resolved.json"), "w",
              encoding="utf-8") as fh:
        json.dump(resolved_knobs["FEATURES_RESOLVED"], fh, indent=2,
                  default=str)
    print(f"\nDone in {time.time() - t0:.1f} s.  Outputs in: {outdir}")


if __name__ == "__main__":
    main()
