# Graph Report - SDL_MBDoE  (2026-08-27)

## Corpus Check
- 72 files · ~530,072 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1757 nodes · 4715 edges · 85 communities (82 shown, 3 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 389 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `cf5bd374`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- benchmark.py
- AdvancedVirtualLaboratory
- Layer1Bridge
- campaign_figures.py
- audit_export.py
- SpatialDesigner
- OperatingConditions
- AcquisitionSettings
- QCGateConfig
- benchmark_figures.py
- benchmark_export.py
- test_comparison.py
- sdl_advanced/reporting.py
- ParameterSpace
- sdl/reporting.py
- InferenceModel
- SpectralNuisance
- NMRSimulator
- literature_guess
- apply_config
- run_advanced_campaign.py
- main
- SpectralFitter
- TransferConfig
- evaluate
- NMRCalibration
- self_test.py
- AdvancedSelector
- campaign_export.py
- NoiseModel
- features.py
- test_campaign_report.py
- test_audit_regression.py
- test_parallel.py
- run_one_campaign
- test_benchmark_report.py
- benchmark_html.py
- AuditRecorder
- test_features.py
- .run_profile
- apply
- test_reactor_validity.py
- test_spectral.py
- SDL-MBDoE: a virtual self-driving laboratory for kinetic identification
- validity_criteria
- ResourceMeter
- CampaignRecord
- campaign_task
- make_executor
- test_resource_accounting.py
- main
- _set_dc
- MBDoESelector
- _geometry_objective
- _nu
- campaign.py
- ordered_map
- Troubleshooting
- last_valid_rows
- ReactorGeometry
- The self-driving loop
- Limitations and responsible interpretation
- V6: what changed, and how to run it
- Outputs and how to read them
- Worked example: the included H2SO4 campaign
- _write_tables
- Configuration reference
- Physical and kinetic model
- FaultModel
- The four strategies
- Installation and use
- run_scenario
- ResourceEvent
- test_each_runner_owns_its_knobs_independently
- How MBDoE chooses the next experiment
- What constitutes an experiment?
- Uncertainty and Fisher information
- derive_allowance
- _scoring_bridge
- _refresh_faults
- test_lab_unreachable_from_controller_object_graph
- _check_magnitudes
- prepare_outdir
- Feature
- _h_validity

## God Nodes (most connected - your core abstractions)
1. `OperatingConditions` - 126 edges
2. `Layer1Bridge` - 111 edges
3. `main()` - 96 edges
4. `AcquisitionSettings` - 67 edges
5. `NoiseModel` - 66 edges
6. `ParameterSpace` - 66 edges
7. `ModelEnsemble` - 64 edges
8. `InferenceModel` - 60 edges
9. `NMRSimulator` - 60 edges
10. `AdvancedVirtualLaboratory` - 58 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `write_scan_csv()`  [EXTRACTED]
  run_advanced_benchmark.py → sdl_advanced/observability.py
- `BaselineLabAdapter` --uses--> `StrategyResult`  [INFERRED]
  sdl_advanced/benchmark.py → sdl/campaign.py
- `ScenarioSpec` --uses--> `StrategyResult`  [INFERRED]
  sdl_advanced/benchmark.py → sdl/campaign.py
- `CampaignRecord` --uses--> `StrategyResult`  [INFERRED]
  sdl_advanced/campaign_export.py → sdl/campaign.py
- `_UStub` --uses--> `StrategyResult`  [INFERRED]
  sdl_advanced/campaign_export.py → sdl/campaign.py

## Import Cycles
- None detected.

## Communities (85 total, 3 thin omitted)

### Community 0 - "benchmark.py"
Cohesion: 0.08
Nodes (46): Exception, AdequacyReport, GovernorState, Model-inadequacy governor: distinguishes "my parameters are uncertain" from "my…, AdvancedDesignConfig, DesignDecision, NoiseSurrogate, Bayesian expected-information-gain (EIG) active learning with a FIM pre-screen… (+38 more)

### Community 1 - "AdvancedVirtualLaboratory"
Cohesion: 0.07
Nodes (45): AdequacyGovernor, GovernorConfig, B must satisfy 1/(B+1) <= alpha or the bootstrap p-value can never reach the…, Parametric-bootstrap empirical p-value of the DECISION statistic (same…, make_lab(), The hidden truth for this scenario. MODEL_MISMATCH['truth_parameter_bias'] is…, The S6 lambda sweep: one base weight vector x a scale factor. The base values…, _resource_lambdas() (+37 more)

### Community 2 - "Layer1Bridge"
Cohesion: 0.06
Nodes (41): KineticModel, KineticParameters, domain_scan(), k_sensitivity(), phi_profiles(), plot_phi_profiles(), ndarray, Equilibrium observability of the reversible EGDA hydrolysis. The reversible… (+33 more)

### Community 3 - "campaign_figures.py"
Cohesion: 0.10
Nodes (49): Every figure of the campaign, in `figures/`. Each builder is handed the…, _write_figures(), _clip_ci(), figure_concentration_profiles(), figure_conditions(), figure_correlation_matrices(), figure_design_decisions(), figure_governor() (+41 more)

### Community 4 - "audit_export.py"
Cohesion: 0.07
Nodes (35): ndarray, phi = r_w' r_w / dof, the factor by which the residuals exceed the size the…, Max standardized mean residual over (experiment x species) CELLS, Sidak-…, (component p-values, combined Sidak min-p, species bias, chi2/dof score, pooled…, THE single definition of which diagnostics enter the decision. Used identically…, Sidak-combined min-p over the DECISION components., blind_prediction_rows(), calibration_rows() (+27 more)

### Community 5 - "SpatialDesigner"
Cohesion: 0.08
Nodes (31): _figure_spatial_value(), True profile + equal vs optimized positions + information density. A REFERENCE…, _field_for_model(), Sensitivity field of the model's EXPECTED OBSERVATION at u., ndarray, The candidate's expected-observation operator - the ONE way any controller-side…, Current MAP if fitted, else the initial guess (for pre-data design)., Particle prediction through the candidate's expected-observation operator (NOT… (+23 more)

### Community 6 - "OperatingConditions"
Cohesion: 0.09
Nodes (39): Experiment design: fixed (conventional) designs and autonomous MBDoE. Fixed…, bounds_vector(), DesignResolution, free_indices(), from_vector(), ndarray, Continuous design space: instrument resolution and bounded refinement. WHY THIS…, Validated (lo, hi) per design variable, in canonical order. Unlike a strict… (+31 more)

### Community 7 - "AcquisitionSettings"
Cohesion: 0.05
Nodes (34): AcquisitionSettings, SW = (ppm window) x (spectrometer frequency)., Complex dwell = 1 / SW., Number of COMPLEX FID points actually sampled., What the instrument really spends: N_acquired x dwell. Differs from…, FFT length >= acquired points; default is the next power of two (zero filling,…, Digital bin spacing of the zero-filled spectrum, SW / N_fft. The TRUE…, Requested AND actual acquisition quantities, for the run record. Serializing… (+26 more)

### Community 8 - "QCGateConfig"
Cohesion: 0.10
Nodes (37): _adaptive_profile_bayes(), measure_with_qc(), _qc_failed(), qc_fault_verdict(), QCGateConfig, QCMonitor, Per-campaign memory of acquisition dispositions (rules 3 and 4). Deliberately…, Apply the four gate rules (see QCGateConfig) and say WHICH one fired. Separated… (+29 more)

### Community 9 - "benchmark_figures.py"
Cohesion: 0.11
Nodes (44): figure_design_by_round(), figure_design_distribution(), figure_design_joint(), figure_matrix(), figure_model_discrimination(), figure_nmr_performance(), figure_overview_accuracy(), figure_paired_seeds() (+36 more)

### Community 10 - "benchmark_export.py"
Cohesion: 0.12
Nodes (41): _conc_bin_label(), _condition_rows(), design_by_round_rows(), design_selection_rows(), _f(), _final_per_seed(), _finite(), master_summary_rows() (+33 more)

### Community 11 - "test_comparison.py"
Cohesion: 0.08
Nodes (40): _agg(), _at_or_before(), budget_to_target_rows(), _first_reaching(), headline_rows(), matched_resource_rows(), Conventional-vs-optimized comparison: how much does the methodology actually…, One row per (strategy, seed, metric, target). The reference's own cost for the… (+32 more)

### Community 12 - "sdl_advanced/reporting.py"
Cohesion: 0.09
Nodes (40): _csv(), figure_a_spatial_value(), figure_b_position_rounds(), figure_c_spectrum(), figure_convergence_band(), figure_d_truth_vs_recovered(), figure_design_trajectory(), figure_e_convergence() (+32 more)

### Community 13 - "ParameterSpace"
Cohesion: 0.07
Nodes (27): check_truth_in_domain(), design_for_budget(), _geometry_score(), Is every hidden true parameter inside the candidate model's domain? Returns a…, DESIGN with a conventional temperature ladder long enough for the requested…, D-optimal information of a REFERENCE design in this reactor, under the PRIOR…, ParameterSpace, ndarray (+19 more)

### Community 14 - "sdl/reporting.py"
Cohesion: 0.10
Nodes (38): blind_rmse(), _entropy(), _param_rows(), ndarray, Blind predictive RMSE of the REACTOR state (transport correction is an…, Per-parameter posterior reporting (#identifiability): estimate, scaled sigma,…, Per-round metric rows + per-parameter rows for one campaign (hidden truth used…, _round_metrics() (+30 more)

### Community 15 - "InferenceModel"
Cohesion: 0.10
Nodes (19): LaplacePosterior, ndarray, Laplace-approximate Bayesian posterior for ONE kinetic-model hypothesis.…, Per-parameter Gaussian posterior mass lying OUTSIDE the box - the diagnostic…, n draws from the Laplace Gaussian PROPERLY truncated to the box. Strategy:…, covariance_from_fim(), InferenceModel, ndarray (+11 more)

### Community 16 - "SpectralNuisance"
Cohesion: 0.08
Nodes (31): DESIGN-TIME predictor of the deconvolution covariance for a CANDIDATE…, No-op: this model is analytic, not data-fitted (interface parity with…, SpectralCovarianceModel, _noise_grid_factor(), Reusable 1H NMR forward model of the EGDA hydrolysis mixture at 80 MHz.…, Std-dev change caused by RESAMPLING the FFT-bin noise onto the display grid,…, TRUE instrument imperfections (owned by the virtual instrument only). All…, What this instrument actually simulates - for the run record. (+23 more)

### Community 17 - "NMRSimulator"
Cohesion: 0.14
Nodes (20): first_order_multiplet(), Line, NMRSimulator, ndarray, Is this effect simulated? `enabled` is the master switch, the per-effect gate…, One acquisition's random draw of the nuisance parameters., One transition: unit-area Lorentzian x area., [(ppm, relative_area), ...]; binomial first-order multiplet (unchanged physics… (+12 more)

### Community 18 - "literature_guess"
Cohesion: 0.11
Nodes (29): main(), Layer 2 showcase: virtual self-driving laboratory around the Layer 1 PFR twin.…, resolve_outdir(), Pre-campaign identifiability screen (same code as run_sdl_campaign.py),…, screened_dropped_keys(), build_candidates(), Full-factorial candidate grid over the feasible design space., greedy_d_optimal() (+21 more)

### Community 19 - "apply_config"
Cohesion: 0.12
Nodes (33): active_geometry(), apply_config(), invalidate_caches(), The reactor this campaign runs in: the declared GEOMETRY, or the prior-optimal…, Initializer for a parallel worker process. Two jobs. First, silence the per-…, Refuse a direct assignment to a feature-derived field. `replay=True` (the call…, Apply a runner's CONFIG knobs to this module's configuration blocks. The…, Drop every configuration-derived cache. A cache keyed on the configuration is… (+25 more)

### Community 20 - "run_advanced_campaign.py"
Cohesion: 0.09
Nodes (28): _figure_recovery(), Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling…, # NOTE: with this on, blind RMSE is computed in the CHOSEN reactor, so, # NOTE: the shipped 20 cm OPEN tube FAILS this at every design flow, Truth vs deconvolved concentration over random compositions. Instrument-level…, calibrate_empirical(), calibrate_responses(), _check_standards() (+20 more)

### Community 21 - "main"
Cohesion: 0.09
Nodes (29): _finals(), git_provenance(), main(), _mean_curves(), prepare_layout(), Main EGDA advanced benchmark (corrected framework, v3 outputs). Runs the…, Create the subdirectories and return {key: absolute path}., Where this run writes - and a refusal to overwrite anything else. A completed… (+21 more)

### Community 22 - "SpectralFitter"
Cohesion: 0.11
Nodes (27): generate(), ndarray, Three deterministic representative NMR examples for the publication figures.…, (label, ppm, observed, fitted, residual, components) per example., Per-species (plus pool and baseline) contribution to the FITTED spectrum.…, Simulate, deconvolve and export the three examples. Returns one summary row per…, _species_components(), spectra_for_plot() (+19 more)

### Community 23 - "TransferConfig"
Cohesion: 0.12
Nodes (20): Propagator, The line THIS scenario runs, built from the CURRENT global configuration plus…, Composition arriving at the NMR cell for a sample drawn at z. Applies (in…, Stateful virtual transfer line (owned by the instrument). Remembers the…, (taus, weights) of the residence-time quadrature., TransferConfig, TransferLine, _lab() (+12 more)

### Community 24 - "evaluate"
Cohesion: 0.14
Nodes (27): evaluate(), explain(), _geom(), is_feasible(), max_admissible_flow_mL_min(), min_admissible_length_m(), Plug-flow validity of a reactor OVER ITS WHOLE OPERATING ENVELOPE. WHY THIS…, Full plug-flow diagnosis of ONE geometry at ONE total flow. Returns a flat dict… (+19 more)

### Community 25 - "NMRCalibration"
Cohesion: 0.11
Nodes (13): bootstrap_coverage(), NMRCalibration, ndarray, QuantificationResult, Adopt a PUBLIC calibration artifact. The design-time SpectralCovarianceModel…, REPORTING ONLY: the per-species (and pool/baseline) contributions to an…, B(eta): columns = phased species spectra, exchange pool, baseline., Water dominates the pool; start at the water shift at the commanded NMR-cell… (+5 more)

### Community 26 - "self_test.py"
Cohesion: 0.12
Nodes (25): run_strategy(), build_fixed_design(), Conventional campaign: temperature ladder at nominal flow/catalyst. `budget`…, Run the hidden reactor at conditions u and return noisy CPR-NMR data: all ports…, POST-CAMPAIGN benchmarking only - never called inside the loop., VirtualLaboratory, _make_loop(), _ports() (+17 more)

### Community 27 - "AdvancedSelector"
Cohesion: 0.13
Nodes (15): AdvancedSelector, expected_information_gain(), _logdet_floored(), ndarray, Sigma for ONE position's species vector., Species-major covariance for a whole profile (block per z)., (EIG_total, EIG_model) in nats, from cached particle predictions. preds: (N,…, Hierarchical (u, Z) selector for strategy F. (+7 more)

### Community 28 - "campaign_export.py"
Cohesion: 0.15
Nodes (24): _assimilated(), concentration_rows(), _corr_max_offdiag(), _f(), _join(), measurement_rows(), model_for_round(), natural_bounds() (+16 more)

### Community 29 - "NoiseModel"
Cohesion: 0.16
Nodes (20): AssumedTransfer, Particle, n joint (M, theta) posterior draws; model counts multinomial in the model…, INFERENCE-SIDE transfer knowledge: only COMMANDED / CALIBRATED quantities…, Back-compatible constructor for a plain mean-delay correction., InferenceModel whose expected-observation operator includes the…, TransportAwareInference, NoiseModel (+12 more)

### Community 30 - "features.py"
Cohesion: 0.10
Nodes (8): _chem(), _h_activity(), _h_ka2(), _h_reversible(), _h_speciation(), _h_tdep_equilibrium(), _h_tdep_kinetics(), CENTRAL BOOLEAN FEATURE CONTROL - the one place that says what is switched on.…

### Community 31 - "test_campaign_report.py"
Cohesion: 0.15
Nodes (21): Reactor sampling point -> NMR cell -> reported concentration, per acquisition…, transfer_rows(), Regression guard for the per-campaign scientific record. THE CLAIM UNDER TEST,…, F is the one that matters: it exercises the EIG selector's RNG, the QC gate and…, The control: D runs unchanged sdl.campaign code, so this must pass trivially -…, The information curve is KEPT from the greedy step, not recomputed. Its…, The decomposition must ADD UP: reactor -> cell -> reported., The firewall: nothing may ask the laboratory for truth while it is still… (+13 more)

### Community 32 - "test_audit_regression.py"
Cohesion: 0.14
Nodes (21): _compare(), _first_difference(), Regression guard for the publication audit trail. THE CLAIM UNDER TEST: turning…, A-D run unchanged sdl.campaign code and are audited entirely post-campaign, so…, E adds spatial optimization and per-round timing calls., The one that matters: F exercises the EIG selector (RNG), the QC gate and the…, S3 turns on the NMR pathway, the transfer line and the QC gate, so the…, S5 removes the correct model, so the governor fires and the selector switches… (+13 more)

### Community 33 - "test_parallel.py"
Cohesion: 0.14
Nodes (20): Tests for the process-parallel benchmark execution. The contract being pinned…, Deliberately invert the completion order: the FIRST task sleeps longest. A…, runtime_s measures the RUN, not the chemistry: it is the one field a worker…, Plain `==` is unusable here: legitimate NaNs (p_correct for a non-Bayesian…, Guard the guard: the NaN-tolerant comparator must not be so forgiving that the…, Only primitives may cross the process boundary - never a laboratory, a…, The whole point, end to end: a real registered scenario with all six of its…, The runner spells the variable list out inline because importing it from the… (+12 more)

### Community 34 - "run_one_campaign"
Cohesion: 0.11
Nodes (16): assumed_noise(), _assumed_transfer_from(), BaselineLabAdapter, continuous_kwargs(), design_resolution(), fitter_kwargs(), Keyword arguments for the BASELINE MBDoESelector (strategies C/D/E). Empty when…, Presents AdvancedVirtualLaboratory as the legacy VirtualLaboratory so… (+8 more)

### Community 35 - "test_benchmark_report.py"
Cohesion: 0.16
Nodes (19): paired_seed_rows(), EVERY seed's paired difference against its scenario's reference strategy, not…, reference_strategy(), _first_difference(), Regression guard for the benchmark's run-level summary. THE CLAIM UNDER TEST,…, A ten-position profile chooses ONE operating condition, not ten, and weighting…, The decomposition must ADD UP and must name the dominant stage., NaN == NaN. These tables are full of legitimate NaNs (a metric a strategy… (+11 more)

### Community 36 - "benchmark_html.py"
Cohesion: 0.27
Nodes (18): build_report(), derive_findings(), _pct(), The human-readable half of the benchmark: one self-contained HTML report. It is…, Write the benchmark report. Missing figures/files are skipped., Statements this run's data supports, each with its evidence. Returns dicts with…, _sc_title(), build_report() (+10 more)

### Community 37 - "AuditRecorder"
Cohesion: 0.12
Nodes (9): AuditRecorder, Passive audit recorder for the publication workflow. DESIGN RULE, and the whole…, `curve` is `SpatialDesigner.last_selection`: the marginal log-det gain the…, `part` is the controller's per-position view of one acquisition: {"z", "y",…, Whole-profile convenience for the ungated (direct-observation) path, where…, Wall-clock only. Reading a clock cannot change a result, and these columns are…, Picklable primitives only, for the trip back from a worker., Append-only sink. Holds plain Python/NumPy scalars so the payload is cheap to… (+1 more)

### Community 38 - "test_features.py"
Cohesion: 0.14
Nodes (16): This scenario's candidate family AFTER the feature switches. A feature that…, scenario_family(), Central Boolean feature control. The contract these tests defend: * ONE switch…, REGRESSION: the scenarios used to CAPTURE a TransferConfig at import, so a…, Every switch must move SOMETHING: compare the resolved configuration with the…, Context helper: apply feature overrides, restore afterwards., Every item the review asked to be switchable has a switch., test_quantification_uncertainty_off_leaves_only_the_fit_covariance() (+8 more)

### Community 39 - ".run_profile"
Cohesion: 0.14
Nodes (9): ndarray, Hidden true composition (ALL Layer-1 species) at each z., Batch-reaction propagator at the transfer-line temperature, closed over the…, Set condition u, sample the requested positions in the given order (one moving…, Legacy-style observation: concentrations + NoiseModel noise. cov_y stays None…, Gross, QC-DETECTABLE corruption of one acquisition. A rolling artifact spanning…, UNDETECTABLE quantification outliers: displace a species by many CLAIMED sigmas…, Spectrum -> deconvolution. The fitter sees only the spectrum. (+1 more)

### Community 40 - "apply"
Cohesion: 0.18
Nodes (17): Any, apply(), _apply_mismatch(), cascade(), mismatch_defaults(), Route the switches into the configuration blocks of `ns`. Called at the END of…, Split TRUTH_CHEMISTRY from INFERENCE_CHEMISTRY where asked to. Nothing here…, The COMPLETE feature state, for the run record. Every switch appears with its… (+9 more)

### Community 41 - "test_reactor_validity.py"
Cohesion: 0.15
Nodes (16): permitted_flows(), Every total flow the campaign may command, worst case included. Discrete mode:…, Plug-flow validity over the WHOLE design envelope. The defect these tests pin…, The headline regression: with the criterion applied at every permitted flow, no…, t_rad/tau = Q/(pi D_m L eps): linear in flow, inverse in length, INDEPENDENT of…, Where the Taylor term dominates D_ax, Bo = uL/D_ax reduces to 48/(t_rad/tau):…, Outside the radially-mixed regime the Taylor-Aris D_ax is meaningless. It must…, REGRESSION: a packed bed used to return a radial ratio of exactly 0.0, i.e. it… (+8 more)

### Community 42 - "test_spectral.py"
Cohesion: 0.17
Nodes (15): flow_response(), Phenomenological incomplete-relaxation / flow response factor in [0,1]. E = 1 -…, delta(H2O)/ppm ~ 5.051 - 0.0111*T(degC). Empirical aqueous relation inherited…, water_shift(), _ideal_sim(), Tests of the NMR forward model (sdl_advanced.spectral). Runnable standalone:…, Doubling [EGDA] must exactly double the EGDA-only spectral area., FFT of the simulated FID must reproduce the analytic Lorentzian spectrum (ideal… (+7 more)

### Community 43 - "SDL-MBDoE: a virtual self-driving laboratory for kinetic identification"
Cohesion: 0.13
Nodes (15): Advanced layer: `sdl_advanced` (CPR + Fourier 80 virtual instrument), Code map, Constraint activity is reported, never hidden, Contents, Hidden truth and the truth firewall, Identifiability screen (before any experiment is spent), It is, It is not (+7 more)

### Community 44 - "validity_criteria"
Cohesion: 0.17
Nodes (15): assert_reactor_validity(), _radial_ratio(), The single ValidityCriteria object every consumer must use.…, Radial-mixing ratio t_rad/tau of a geometry at one total flow. Open tube: t_rad…, Plug-flow validity of the reactor ACTUALLY IN USE, at every flow the design…, Apply VALIDITY['policy'] to the reactor in use, over the WHOLE design envelope.…, reactor_validity_rows(), _validity_cache_key() (+7 more)

### Community 45 - "ResourceMeter"
Cohesion: 0.15
Nodes (10): What the reference campaign would CONSUME in this reactor, replayed…, _reference_campaign_cost(), ndarray, Accumulates the campaign's physical cost from logged events., `enabled=False` is the FEATURE bypass for resource accounting…, Reactor condition set + stabilization to steady state. Idempotent for an…, Scalar penalty term of the resource-aware utility for a HYPOTHETICAL experiment…, ResourceMeter (+2 more)

### Community 46 - "CampaignRecord"
Cohesion: 0.16
Nodes (10): CampaignRecord, export_spectra(), Adapter so a spectrum-log entry can go through `_u_cols`., Cumulative and per-round metered cost. The cumulative values are the…, One row per strategy actually run: where it ended up, and what it spent getting…, Write the retained deconvolutions (spectrum, fit, residual, per-species…, Everything ONE finished campaign retained, in one place. Nothing here is…, resource_round_rows() (+2 more)

### Community 47 - "campaign_task"
Cohesion: 0.15
Nodes (13): campaign_task(), ONE campaign, as a picklable pure function of its four labels. This is the unit…, The EIG is Monte-Carlo and consumes the selector's RNG. The audit may report…, A QC-rejected spectrum never reaches the posterior, so it exists in no…, The cumulative columns are re-derived from raw events, so they must land on the…, F is a Laplace posterior: its curvature includes the prior, so the eigenvalues…, test_audit_tables_are_populated_and_self_consistent(), test_identifiability_labels_which_matrix_it_used() (+5 more)

### Community 48 - "make_executor"
Cohesion: 0.19
Nodes (12): describe_workers(), make_executor(), pin_numerical_threads(), Cross-platform, determinism-preserving process parallelism for the benchmark.…, Pin every numerical backend to `n_threads`. Call this BEFORE importing…, CONFIG value -> concrete process count. None / "auto" -> all cores but one…, A spawn-based pool, or None when the resolved count is 1. Returning None for a…, resolve_workers() (+4 more)

### Community 49 - "test_resource_accounting.py"
Cohesion: 0.24
Nodes (11): _meter(), Tests of resource accounting (sdl_advanced.resources). Runnable standalone., Predicted candidate cost and realized event accounting must use the same…, Acceptance criterion 13: totals are nonnegative and re-derivable from the event…, Adaptive one-z-at-a-time sampling at the SAME (T,Q,C_EGDA,C_cat) must not re-…, test_candidate_cost_consistent_with_realized_events(), test_capillary_travel_is_sum_of_moves(), test_reacquisitions_counted_separately() (+3 more)

### Community 50 - "main"
Cohesion: 0.18
Nodes (11): main(), Resolve the output directory, refusing to overwrite a completed run. An…, The spatial policy this strategy actually ran, resolved the same way…, (u, z, species) -> the hidden TRUE reactor composition. POST-CAMPAIGN ONLY. It…, resolve_outdir(), _spatial_mode_of(), _truth_predictor(), campaign_cost_units() (+3 more)

### Community 51 - "_set_dc"
Cohesion: 0.18
Nodes (11): _h_acq_time(), _h_fid(), _h_line_carryover(), _h_line_reaction(), _h_line_rtd(), _h_line_temperature(), _h_overlap(), _h_resource_aware() (+3 more)

### Community 52 - "MBDoESelector"
Cohesion: 0.25
Nodes (6): MBDoESelector, ndarray, Bounds in canonical order. A DEGENERATE dimension (lo == hi) is accepted and…, Design score with FLOORED eigenvalues. `slogdet` returns -inf for any singular…, The hybrid selector must improve on its coarse seed without leaving the user-…, test_continuous_design_refines_inside_bounds()

### Community 53 - "_geometry_objective"
Cohesion: 0.20
Nodes (10): _geometry_candidates(), _geometry_objective(), geometry_sizing_table(), _no_feasible_geometry_message(), optimal_geometry(), Every candidate the sizing considered, with the decomposed objective (info,…, Discrete geometry grid x packing state, from the declared levels.…, score = information - resource penalty, with feasibility. FEASIBILITY IS… (+2 more)

### Community 54 - "_nu"
Cohesion: 0.20
Nodes (10): _h_baseline(), _h_broadening(), _h_correlated_noise(), _h_gain(), _h_lineshape_mismatch(), _h_phase(), _h_response_calibration(), _h_shift() (+2 more)

### Community 55 - "campaign.py"
Cohesion: 0.29
Nodes (6): Closed-loop campaign runner - the "self-driving" part. For one strategy the…, RoundRecord, Inference model: everything the (virtual) experimenter is allowed to know.…, UncertaintyReport, Forward-model adapter around the Layer 1 PFR digital twin. This is the ONLY…, Virtual truth: the hidden ground-truth side of the self-driving laboratory.…

### Community 56 - "ordered_map"
Cohesion: 0.25
Nodes (9): ProcessPoolExecutor, governor_mc_validation(), governor_task(), First round at which the governor declares MODEL_INADEQUATE, plus WHY - the…, Monte Carlo validation of the governor (#calibration honesty): * correct-family…, ordered_map(), Apply `fn(*args)` to every tuple, returning results in SUBMISSION order. `fn`…, detection_rounds is a list the report reads positionally, so it must come back… (+1 more)

### Community 57 - "Troubleshooting"
Cohesion: 0.22
Nodes (9): A confidence interval is extremely large, EGMA has no obvious peak in an outlet plot, `ModuleNotFoundError` for `pfr_twin`, NaOH starts at half the configured concentration, Output files disappeared after changing catalysts, Runtime becomes large, The autonomous strategy repeats a condition, The first uncertainty is infinite or `logdet_F` is `-inf` (+1 more)

### Community 58 - "last_valid_rows"
Cohesion: 0.31
Nodes (9): _boot_ci(), last_valid_rows(), paired_comparison(), One row per SEED: that seed's LAST COMPLETED round. Using the per-seed last…, Last-valid-round distributional summary per strategy: median, IQR, mean,…, Common-random-number PAIRED comparison of two strategies at the final round:…, summarize_final(), A seed that stops early keeps its LAST VALID round in the summary (n_seeds… (+1 more)

### Community 59 - "ReactorGeometry"
Cohesion: 0.25
Nodes (7): ReactorGeometry, _row(), `arrhenius` and `van_t_hoff` are FEATURE GATES for the two temperature…, test_packed_uses_bed_void_fraction(), test_residence_time_scales_with_geometry(), test_unpacked_gives_epsilon_one(), test_packing_terminology_and_residence_time()

### Community 60 - "The self-driving loop"
Cohesion: 0.25
Nodes (8): 1. Select an operating condition, 2. Run the virtual experiment, 3. Add the measurement to the accumulated dataset, 4. Re-estimate every kinetic parameter, 5. Recompute local uncertainty, 6. Check the stopping condition, 7. Let MBDoE choose the next experiment, The self-driving loop

### Community 61 - "Limitations and responsible interpretation"
Cohesion: 0.25
Nodes (8): Candidate quality is constrained by the admissible design region, D-optimality is not every scientific goal, Experiment count is not total analytical cost, FIM uncertainty is local, Limitations and responsible interpretation, One seed is an illustration, not a statistical ranking, Synthetic validation is not experimental validation, The model can be precisely wrong

### Community 62 - "V6: what changed, and how to run it"
Cohesion: 0.29
Nodes (6): 1. Reactor validity now covers the whole design space, 2. Governor recalibration, 3. Single-measurement QC, Central feature control, Running, V6: what changed, and how to run it

### Community 63 - "Outputs and how to read them"
Cohesion: 0.29
Nodes (7): `campaign_history.csv`, `convergence_error.png`, `convergence_uncertainty.png`, `final_estimates.png`, `final_report.txt`, Outputs and how to read them, `validation_profiles.png`

### Community 64 - "Worked example: the included H2SO4 campaign"
Cohesion: 0.29
Nodes (7): Final campaign comparison, Final estimate from strategy D, What B versus A says about spatial data, What C versus A says about MBDoE with outlet-only data, Why D selected hot, slow experiments, Why error can rise while uncertainty falls, Worked example: the included H2SO4 campaign

### Community 65 - "_write_tables"
Cohesion: 0.29
Nodes (7): Every machine-readable table of the campaign, in `data/`. The audit tables come…, _write_tables(), _qc_reason(), qc_rows(), One CSV, with a DETERMINISTIC column order. Columns appear in the order the…, Per round: what the gate saw and what it did about it. Built from the unified…, write_rows()

### Community 66 - "Configuration reference"
Cohesion: 0.33
Nodes (6): Campaign controls, Configuration reference, Default H2SO4 candidate space, Default NaOH candidate space, Forward-model controls, Safe interpretation of configuration changes

### Community 67 - "Physical and kinetic model"
Cohesion: 0.33
Nodes (6): H2SO4 route, NaOH route, Physical and kinetic model, Reaction network, Reactor and feed arrangement, Temperature parameterization

### Community 68 - "FaultModel"
Cohesion: 0.33
Nodes (3): FaultModel, TRUTH-side hardware failures and quantification outliers. Two DELIBERATELY…, test_faults_off_means_no_injection_code_runs()

### Community 69 - "The four strategies"
Cohesion: 0.40
Nodes (5): A — outlet + fixed design, B — spatial + fixed design, C — outlet + MBDoE, D — spatial + MBDoE, The four strategies

### Community 70 - "Installation and use"
Cohesion: 0.40
Nodes (5): Installation and use, Prerequisites, Run from a terminal, Run from an IDE, Run the self-test

### Community 71 - "run_scenario"
Cohesion: 0.40
Nodes (5): merge(), Returns (round rows, per-parameter rows, per-campaign status rows). NO campaign…, run_scenario(), A scenario object that is not the one in SCENARIOS cannot be sent to a worker…, test_unregistered_spec_falls_back_to_serial()

### Community 72 - "ResourceEvent"
Cohesion: 0.40
Nodes (3): Capillary move + flush + one NMR acquisition at position z. retry=True marks a…, A position whose data was rejected by the QC gate (not assimilated); auditable,…, ResourceEvent

### Community 73 - "test_each_runner_owns_its_knobs_independently"
Cohesion: 0.40
Nodes (5): _load_runner(), The two entry points hold SEPARATE knob blocks and neither imports the other,…, The point of the CONFIG block is that a user can reach EVERY knob from one…, test_each_runner_owns_its_knobs_independently(), test_runner_knobs_cover_every_overridable_block()

### Community 74 - "How MBDoE chooses the next experiment"
Cohesion: 0.50
Nodes (4): A-optimal design, D-optimal design, How MBDoE chooses the next experiment, What the selection physically tends to explore

### Community 75 - "What constitutes an experiment?"
Cohesion: 0.50
Nodes (4): An important fairness distinction, Outlet measurement, Spatial measurement, What constitutes an experiment?

### Community 76 - "Uncertainty and Fisher information"
Cohesion: 0.50
Nodes (4): Fisher Information Matrix, Reported uncertainty measures, Sensitivity matrix, Uncertainty and Fisher information

### Community 77 - "derive_allowance"
Cohesion: 0.50
Nodes (4): derive_allowance(), kappa for this scenario's observation mode. Direct observation has an exact…, Derive kappa from WELL-SPECIFIED CONTROL DATA under THIS configuration. A hard-…, systematic_allowance()

### Community 78 - "_scoring_bridge"
Cohesion: 0.50
Nodes (4): The same model configuration in a different reactor - used to move a LEARNED…, Bridge used for BLIND SCORING: identical object when geometry optimization is…, _rebridge(), _scoring_bridge()

### Community 79 - "_refresh_faults"
Cohesion: 0.50
Nodes (4): _h_instrument_faults(), _h_outliers(), Rebuild FAULTS from the two switches and the declared magnitudes. A probability…, _refresh_faults()

### Community 80 - "test_lab_unreachable_from_controller_object_graph"
Cohesion: 0.50
Nodes (4): STRONG invariant: starting from everything the controller owns (ensemble,…, All Python objects reachable from `roots` via attributes and containers (id-…, _reachable_objects(), test_lab_unreachable_from_controller_object_graph()

### Community 81 - "_check_magnitudes"
Cohesion: 0.67
Nodes (3): _check_magnitudes(), _lookup(), A feature declared ON whose magnitude is zero is a lie in the run record: it…

## Knowledge Gaps
- **78 isolated node(s):** `Contents`, `What problem does this solve?`, `It is`, `It is not`, `Reactor and feed arrangement` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `main` to `Layer1Bridge`, `audit_export.py`, `OperatingConditions`, `benchmark_figures.py`, `benchmark_export.py`, `test_comparison.py`, `sdl_advanced/reporting.py`, `ParameterSpace`, `SpectralNuisance`, `literature_guess`, `apply_config`, `SpectralFitter`, `test_benchmark_report.py`, `benchmark_html.py`, `test_features.py`, `test_reactor_validity.py`, `validity_criteria`, `make_executor`, `main`, `_geometry_objective`, `ordered_map`, `last_valid_rows`, `run_scenario`, `derive_allowance`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Why does `OperatingConditions` connect `OperatingConditions` to `benchmark.py`, `AdvancedVirtualLaboratory`, `Layer1Bridge`, `SpatialDesigner`, `AcquisitionSettings`, `QCGateConfig`, `ParameterSpace`, `sdl/reporting.py`, `InferenceModel`, `SpectralNuisance`, `literature_guess`, `run_advanced_campaign.py`, `main`, `TransferConfig`, `self_test.py`, `AdvancedSelector`, `NoiseModel`, `test_features.py`, `.run_profile`, `MBDoESelector`, `campaign.py`, `FaultModel`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `Layer1Bridge` connect `Layer1Bridge` to `benchmark.py`, `AdvancedVirtualLaboratory`, `SpatialDesigner`, `OperatingConditions`, `AcquisitionSettings`, `QCGateConfig`, `test_comparison.py`, `ParameterSpace`, `sdl/reporting.py`, `InferenceModel`, `SpectralNuisance`, `literature_guess`, `apply_config`, `run_advanced_campaign.py`, `main`, `SpectralFitter`, `TransferConfig`, `self_test.py`, `NoiseModel`, `run_one_campaign`, `test_features.py`, `main`, `campaign.py`, `ReactorGeometry`, `FaultModel`, `_scoring_bridge`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `OperatingConditions` (e.g. with `AdvancedDesignConfig` and `AdvancedSelector`) actually correct?**
  _`OperatingConditions` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `Layer1Bridge` (e.g. with `AdvancedVirtualLaboratory` and `FaultModel`) actually correct?**
  _`Layer1Bridge` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `AcquisitionSettings` (e.g. with `BaselineLabAdapter` and `ScenarioSpec`) actually correct?**
  _`AcquisitionSettings` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `NoiseModel` (e.g. with `AdvancedStrategyResult` and `AdvRoundRecord`) actually correct?**
  _`NoiseModel` has 18 INFERRED edges - model-reasoned connections that need verification._