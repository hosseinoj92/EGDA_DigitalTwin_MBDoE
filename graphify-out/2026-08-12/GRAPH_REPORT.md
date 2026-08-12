# Graph Report - EGDA  (2026-08-12)

## Corpus Check
- 115 files · ~528,974 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1796 nodes · 4611 edges · 75 communities (74 shown, 1 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 407 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aae1ef81`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pipeline.py
- Sweep Integrity and Geometry Collapse Figures
- Sensitivity and Pareto Figures
- Regime, Robustness and Surrogate Figures
- InferenceModel
- Design Coverage and Damkohler Figures
- build_readme_figures.py
- sdl/reporting.py
- self_test.py
- batch_simulation.py
- plotting.py
- AssumedTransfer
- run_simulation.py
- pfr_twin/__init__.py
- ModelEnsemble
- test_comparison.py
- Codex Graphify Feature Set
- SpectralFitter
- test_audit_regression.py
- Claude Graphify Feature Set
- PFR digital twin layer README
- A/B/C/D four-strategy showcase
- test_analysis.py
- NMRSimulator
- Detection, Cache and Update Flow
- Extraction Spec and Honesty Rules
- sim_nmr(2).py
- KineticModel
- progress
- AcquisitionSettings
- instrument.py
- sdl/__init__.py
- ParameterSpace
- Batch Results Analysis CLI
- AdequacyGovernor
- run_advanced_campaign.py
- OperatingConditions
- Build, Cluster and Export Steps
- Codex Subagent Dispatch
- Auto-Rebuild Watch and Commit Hooks
- Graphify Workflow Policy
- Query, Path and Explain Flows
- test_geometry_packing.py
- test_parallel.py
- BatchSweep Package Init
- Layer1Bridge
- sdl_advanced/reporting.py
- benchmark.py
- ReactorGeometry
- io.py
- SpatialDesignConfig
- surrogate_validation
- SpatialDesigner
- test_truth_firewall.py
- audit_summary.py
- test_nmr_calibration.py
- NoiseModel
- create_figures
- ResourceMeter
- build_report
- apply_config
- AuditRecorder
- MBDoESelector
- .run_profile
- run_scenario
- main
- AdvancedSelector
- AnalysisTests
- test_resource_accounting.py
- campaign_task
- Literature-anchored kinetic parameter provenance
- .predict
- reactor.py
- last_valid_rows
- audit_export.py

## God Nodes (most connected - your core abstractions)
1. `OperatingConditions` - 115 edges
2. `Layer1Bridge` - 98 edges
3. `NoiseModel` - 60 edges
4. `InferenceModel` - 59 edges
5. `ParameterSpace` - 59 edges
6. `ModelEnsemble` - 59 edges
7. `main()` - 53 edges
8. `Measurement` - 52 edges
9. `AdvancedVirtualLaboratory` - 51 edges
10. `NMRSimulator` - 51 edges

## Surprising Connections (you probably didn't know these)
- `graphify Pipeline (Codex)` --semantically_similar_to--> `graphify Pipeline (Claude Code)`  [INFERRED] [semantically similar]
  .codex/skills/graphify/SKILL.md → .claude/skills/graphify/SKILL.md
- `Extraction Subagent Prompt (Compact)` --semantically_similar_to--> `Extraction Subagent Prompt`  [INFERRED] [semantically similar]
  .codex/skills/graphify/references/extraction-spec.md → .claude/skills/graphify/references/extraction-spec.md
- `Coupled equilibrium solver (Gauss–Seidel + Brent)` --implements--> `equilibrium_state()`  [EXTRACTED]
  README.md → PFR_H2SO4_digital_twin/pfr_twin/analytical.py
- `test_packing_terminology_and_residence_time()` --calls--> `ReactorGeometry`  [INFERRED]
  SDL_MBDoE/tests/test_nmr_calibration.py → PFR_H2SO4_digital_twin/pfr_twin/parameters.py
- `Truth/inference firewall` --rationale_for--> `VirtualLaboratory`  [EXTRACTED]
  README.md → SDL_MBDoE/sdl/truth.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **graphify Extraction Pipeline Flow** — _claude_skills_graphify_skill_detect_files, _claude_skills_graphify_skill_ast_extraction, _claude_skills_graphify_skill_semantic_extraction, _claude_skills_graphify_skill_merge_ast_semantic, _claude_skills_graphify_skill_build_graph, _claude_skills_graphify_skill_community_labeling [EXTRACTED 1.00]
- **Extraction Output Contract** — _claude_skills_graphify_references_extraction_spec_subagent_prompt, _claude_skills_graphify_references_extraction_spec_node_id_format, _claude_skills_graphify_references_extraction_spec_confidence_rubric, _claude_skills_graphify_references_extraction_spec_source_file_rule, _claude_skills_graphify_references_extraction_spec_hyperedge_rule, _claude_skills_graphify_references_extraction_spec_semantic_similarity_rule [EXTRACTED 1.00]
- **Query and Self-Improving Feedback Loop** — _claude_skills_graphify_references_query_query_expansion, _claude_skills_graphify_references_query_bfs_dfs_traversal, _claude_skills_graphify_references_query_networkx_fallback, _claude_skills_graphify_references_query_save_result, _claude_skills_graphify_references_query_work_memory, _claude_skills_graphify_references_update_incremental_update [EXTRACTED 1.00]
- **SDL closed loop: bridge, virtual lab, inference, design, campaign** — sdl_mbdoe_sdl_layer1_bridge, sdl_mbdoe_sdl_truth_virtuallaboratory, sdl_mbdoe_sdl_inference_inferencemodel, sdl_mbdoe_sdl_design_mbdoeselector, sdl_mbdoe_sdl_campaign_run_strategy [EXTRACTED 1.00]
- **Per-run self-verification: closed form, invariants, thermodynamic consistency, limiting reagent** — readme_self_verification, readme_linear_invariants, readme_coupled_equilibrium_solver, pfr_h2so4_digital_twin_pfr_twin_analytical, pfr_h2so4_digital_twin_pfr_twin_reactor [EXTRACTED 1.00]
- **BatchSweep analysis pipeline stages** — batchsweep_analysis_batchsweep_analysis_io, batchsweep_analysis_batchsweep_analysis_physics, batchsweep_analysis_batchsweep_analysis_statistics, batchsweep_analysis_batchsweep_analysis_plots, batchsweep_analysis_batchsweep_analysis_report, batchsweep_analysis_batchsweep_analysis_pipeline [EXTRACTED 1.00]
- **Catalyst x Geometry Four-Panel Faceting Convention** — batchsweep_analysis_docs_images_axial_egma_peaks_h2so4_catalyst, batchsweep_analysis_docs_images_axial_egma_peaks_naoh_catalyst, batchsweep_analysis_docs_images_axial_egma_peaks_geometry_a, batchsweep_analysis_docs_images_axial_egma_peaks_geometry_b, batchsweep_analysis_docs_images_consolidated_scenarios_figure, batchsweep_analysis_docs_images_data_coverage_figure, batchsweep_analysis_docs_images_derived_metrics_figure [INFERRED 0.85]
- **Damkohler Scaling Group (kappa1, tau, Da1, yield, R_OH)** — batchsweep_analysis_docs_images_derived_metrics_damkohler_da1, batchsweep_analysis_docs_images_derived_metrics_rate_constant_kappa1, batchsweep_analysis_docs_images_derived_metrics_residence_time_tau, batchsweep_analysis_docs_images_derived_metrics_outlet_egma_yield, batchsweep_analysis_docs_images_derived_metrics_r_oh [EXTRACTED 1.00]
- **BatchSweep CSV Artifact Pipeline (design to coverage to derived to peaks)** — batchsweep_analysis_docs_images_consolidated_scenarios_dataset, batchsweep_analysis_docs_images_data_coverage_dataset, batchsweep_analysis_docs_images_derived_metrics_dataset, batchsweep_analysis_docs_images_axial_egma_peaks_dataset [INFERRED 0.85]
- **Batch Sweep Data Integrity and Validity Audit Suite** — batchsweep_analysis_docs_images_duplicate_configs_figure, batchsweep_analysis_docs_images_excluded_or_invalid_scenarios_figure, batchsweep_analysis_docs_images_duplicate_configs_sweep_integrity_audit, batchsweep_analysis_docs_images_excluded_or_invalid_scenarios_zero_loader_exclusions [INFERRED 0.85]
- **Y_EGMA Four-Factor Interaction Basis (temp_C, Ccat, CEGDA, Q)** — batchsweep_analysis_docs_images_interaction_effects_temp_c, batchsweep_analysis_docs_images_interaction_effects_ccat, batchsweep_analysis_docs_images_interaction_effects_cegda, batchsweep_analysis_docs_images_interaction_effects_q_flow, batchsweep_analysis_docs_images_interaction_effects_y_egma [EXTRACTED 1.00]
- **Catalyst x Geometry Stratification of Sweep Results** — batchsweep_analysis_docs_images_geometry_collapse_metrics_h2so4_catalyst, batchsweep_analysis_docs_images_geometry_collapse_metrics_naoh_catalyst, batchsweep_analysis_docs_images_geometry_collapse_metrics_geometry_a, batchsweep_analysis_docs_images_geometry_collapse_metrics_geometry_b, batchsweep_analysis_docs_images_interaction_effects_figure, batchsweep_analysis_docs_images_geometry_collapse_metrics_figure [EXTRACTED 1.00]
- **All figures stratify results across the H2SO4/NaOH catalyst x geometry A/B four-panel design** — batchsweep_analysis_docs_images_local_elasticities_figure, batchsweep_analysis_docs_images_main_effects_figure, batchsweep_analysis_docs_images_regime_assignments_figure, batchsweep_analysis_docs_images_local_elasticities_h2so4_catalyst, batchsweep_analysis_docs_images_local_elasticities_naoh_catalyst, batchsweep_analysis_docs_images_local_elasticities_geometry_factor [EXTRACTED 1.00]
- **The four swept operating factors jointly define the EGMA yield design space** — batchsweep_analysis_docs_images_local_elasticities_temp_c, batchsweep_analysis_docs_images_local_elasticities_q_total_ml_min, batchsweep_analysis_docs_images_local_elasticities_c_egda_feed_m, batchsweep_analysis_docs_images_local_elasticities_c_catalyst_feed_m, batchsweep_analysis_docs_images_local_elasticities_egma_yield [EXTRACTED 1.00]
- **NaOH branch flags co-occur as a hydroxide-depletion / overreaction regime** — batchsweep_analysis_docs_images_regime_assignments_naoh_exhausted, batchsweep_analysis_docs_images_regime_assignments_naoh_stoichiometric_limit, batchsweep_analysis_docs_images_regime_assignments_overreaction_to_eg, batchsweep_analysis_docs_images_regime_assignments_interior_egma_peak [INFERRED 0.85]
- **Four-Case Catalyst x Geometry Faceting Shared Across Figures** — batchsweep_analysis_docs_images_regime_summary, batchsweep_analysis_docs_images_robust_operating_windows, batchsweep_analysis_docs_images_surrogate_validation, batchsweep_analysis_docs_images_top_conditions, batchsweep_analysis_docs_images_regime_summary_catalyst_geometry_case [EXTRACTED 1.00]
- **Four-Factor Screening Design Space (Flow, EGDA Feed, Catalyst Feed, Temperature)** — batchsweep_analysis_docs_images_surrogate_validation_q_total_ml_min, batchsweep_analysis_docs_images_surrogate_validation_c_egda_feed_m, batchsweep_analysis_docs_images_surrogate_validation_c_catalyst_feed_m, batchsweep_analysis_docs_images_surrogate_validation_temp_c [EXTRACTED 1.00]
- **Mutually Exclusive Primary Regime Taxonomy** — batchsweep_analysis_docs_images_regime_summary_egma_selective, batchsweep_analysis_docs_images_regime_summary_naoh_exhausted, batchsweep_analysis_docs_images_regime_summary_acid_equilibrium_limited, batchsweep_analysis_docs_images_regime_summary_interior_egma_peak, batchsweep_analysis_docs_images_regime_summary_intermediate, batchsweep_analysis_docs_images_regime_summary_low_conversion, batchsweep_analysis_docs_images_regime_summary_overreaction_to_eg [EXTRACTED 1.00]

## Communities (75 total, 1 thin omitted)

### Community 0 - "pipeline.py"
Cohesion: 0.18
Nodes (21): _coverage(), _invalid_records(), Any, Path, run_analysis(), functional_anova(), geometry_collapse(), _groups() (+13 more)

### Community 1 - "Sweep Integrity and Geometry Collapse Figures"
Cohesion: 0.09
Nodes (36): duplicate_configs.csv (data source), Duplicate Records (0), Figure: Configuration Identity Audit (duplicate_configs), Record Count Metric, Sweep Data Integrity Audit, Unique Loaded Configurations (3000), excluded_or_invalid_scenarios.csv (data source), Figure: Validity and Applicability Audit (excluded_or_invalid_scenarios) (+28 more)

### Community 2 - "Sensitivity and Pareto Figures"
Cohesion: 0.09
Nodes (36): C_catalyst_feed_M (catalyst feed concentration), C_EGDA_feed_M (EGDA feed concentration), EGMA Yield (Y_EGMA), Figure: Median absolute local elasticity of EGMA yield, Reactor Geometry A vs B, H2SO4 Catalyst Branch, Local Elasticity median |(x/y)dy/dx|, NaOH Catalyst Branch (+28 more)

### Community 3 - "Regime, Robustness and Surrogate Figures"
Cohesion: 0.08
Nodes (35): Regime Summary Figure (Mutually Exclusive Primary Regimes), acid_equilibrium_limited Regime, Catalyst/Geometry Case (H2SO4-A, H2SO4-B, NaOH-A, NaOH-B), regime_summary.csv (Data Source), EGMA_selective Regime, Finding: H2SO4 Cases Dominated by Low Conversion, interior_EGMA_peak Regime, intermediate Regime (+27 more)

### Community 4 - "InferenceModel"
Cohesion: 0.19
Nodes (8): InferenceModel, ndarray, Re-estimate theta from all accumulated data (warm start)., Central-difference S (m.size x p) in scaled parameter space., Expected FIM contribution of a candidate experiment, evaluated at the CURRENT…, THE expected-observation operator: what a measurement at (u, z) is predicted to…, Backward-compatibility contract of Measurement.cov_y., test_measurement_with_own_covariance_is_respected()

### Community 5 - "Design Coverage and Damkohler Figures"
Cohesion: 0.10
Nodes (30): axial_egma_peaks.csv (peak dataset), Figure: Axial EGMA Intermediate Maxima (H2SO4 vs NaOH), Reactor Geometry A, Reactor Geometry B, H2SO4 Catalyst Branch, Finding: H2SO4 peaks pinned at outlet, NaOH peaks interior, NaOH Catalyst Branch, Peak EGMA Yield (+22 more)

### Community 6 - "build_readme_figures.py"
Cohesion: 0.23
Nodes (25): axial_egma_peaks(), consolidated_scenarios(), convert(), data_coverage(), derived_metrics(), duplicate_configs(), excluded_or_invalid_scenarios(), geometry_collapse_metrics() (+17 more)

### Community 7 - "sdl/reporting.py"
Cohesion: 0.11
Nodes (35): campaign_history.csv per-round record, final_report.txt human-readable campaign summary, main(), Layer 2 showcase: virtual self-driving laboratory around the Layer 1 PFR twin.…, resolve_outdir(), Corners (plus centre) of the admissible box - the most informative design the…, reference_design(), Short name of the scaled theta component for a natural key. (+27 more)

### Community 8 - "self_test.py"
Cohesion: 0.08
Nodes (40): Truth/inference firewall, Truth-only systematic effects (transfer_time_s, calibration_gain), build_candidates(), build_fixed_design(), Full-factorial candidate grid over the feasible design space., Conventional campaign: temperature ladder at nominal flow/catalyst. `budget`…, literature_guess(), Initial estimates = Layer 1's literature-anchored kinetics for the chosen… (+32 more)

### Community 9 - "batch_simulation.py"
Cohesion: 0.06
Nodes (53): BatchSweep Analysis methods and interpretation README, Read-only post-processing layer over saved sweeps, _fmt_secs(), main(), _progress(), BATCH base-case runs of the PFR digital twin. Same physics and outputs as…, Yield items with a tqdm-style progress bar (count, %, elapsed, ETA). Uses tqdm…, Simulate every scenario, write per-scenario folders and the summary. (+45 more)

### Community 10 - "plotting.py"
Cohesion: 0.11
Nodes (29): run_config.json + profiles.csv as the analysis input contract, _end_label(), _legend(), _new_axes(), plot_concentration_profiles(), plot_conversion_yield(), plot_profile_overlay(), plot_scenario_bars() (+21 more)

### Community 11 - "AssumedTransfer"
Cohesion: 0.10
Nodes (24): AssumedTransfer, Particle, n joint (M, theta) posterior draws; model counts multinomial in the model…, INFERENCE-SIDE transfer knowledge: only COMMANDED / CALIBRATED quantities…, Back-compatible constructor for a plain mean-delay correction., InferenceModel whose expected-observation operator includes the…, TransportAwareInference, GaussianPrior (+16 more)

### Community 12 - "run_simulation.py"
Cohesion: 0.11
Nodes (33): analytical_profiles(), max_relative_error(), ndarray, Algebraic reference solutions used to verify the numerical integrator. 1.…, Largest |numerical - analytical| across species, relative to `scale`., Concentration-based reaction quotients (Q1, Q2) of the two steps; NaN where the…, reaction_quotients(), SolverSettings (+25 more)

### Community 13 - "pfr_twin/__init__.py"
Cohesion: 0.07
Nodes (44): flow_diagnostics(), Plug-flow validity diagnostics. A digital twin should say when its own…, Vogel-type correlation for liquid water, valid ~273-373 K., water_density_g_L(), water_viscosity_Pa_s(), pfr_twin - 1D deterministic digital twin of an isothermal plug flow reactor for…, Kinetic model of the two-step series ester cleavage, per catalyst system. Acid…, bisulfate_equilibrium() (+36 more)

### Community 14 - "ModelEnsemble"
Cohesion: 0.10
Nodes (33): AdequacyReport, GovernorState, Model-inadequacy governor: distinguishes "my parameters are uncertain" from "my…, DesignDecision, expected_information_gain(), NoiseSurrogate, Bayesian expected-information-gain (EIG) active learning with a FIM pre-screen…, (EIG_total, EIG_model) in nats, from cached particle predictions. preds: (N,… (+25 more)

### Community 15 - "test_comparison.py"
Cohesion: 0.10
Nodes (35): _agg(), _at_or_before(), budget_to_target_rows(), _first_reaching(), headline_rows(), matched_resource_rows(), Conventional-vs-optimized comparison: how much does the methodology actually…, What accuracy had each method reached by the time it had spent what the… (+27 more)

### Community 16 - "Codex Graphify Feature Set"
Cohesion: 0.12
Nodes (16): URL Ingest via /graphify add (Codex), Folder Watch Auto-Rebuild (Codex), FalkorDB Cypher Export (Codex), graphify MCP stdio Server (Codex), Neo4j Cypher Export (Codex), GitHub Repo Clone (Codex), Cross-Repo Graph Merge (Codex), Native CLAUDE.md Integration (Codex) (+8 more)

### Community 17 - "SpectralFitter"
Cohesion: 0.06
Nodes (53): bootstrap_coverage(), calibrate_empirical(), calibrate_nmr(), calibrate_responses(), _check_standards(), _default_standards(), QuantificationResult, Automated spectral deconvolution: spectrum -> concentrations + Sigma_y.… (+45 more)

### Community 18 - "test_audit_regression.py"
Cohesion: 0.14
Nodes (21): _compare(), _first_difference(), Regression guard for the publication audit trail. THE CLAIM UNDER TEST: turning…, A-D run unchanged sdl.campaign code and are audited entirely post-campaign, so…, E adds spatial optimization and per-round timing calls., The one that matters: F exercises the EIG selector (RNG), the QC gate and the…, S3 turns on the NMR pathway, the transfer line and the QC gate, so the…, S5 removes the correct model, so the governor fires and the selector switches… (+13 more)

### Community 19 - "Claude Graphify Feature Set"
Cohesion: 0.18
Nodes (15): /graphify Trigger Registration, FalkorDB Cypher Export, graphify MCP stdio Server, Neo4j Cypher Export, GitHub Repo Clone, Cross-Repo Graph Merge, Native CLAUDE.md Integration, BFS and DFS Traversal Modes (+7 more)

### Community 20 - "PFR digital twin layer README"
Cohesion: 0.09
Nodes (25): Axial EGMA peak location and 95% plateau interval, Damköhler kinetic-exposure metric, Contrast with the packed-bed Amberlyst twin, PFR digital twin layer README, Water as explicit reactant on the acid route, Layer 1 Python dependencies (numpy, scipy, matplotlib), R. P. Bell, Acid–Base Catalysis, Bisulfate catalyst speciation ([H+] from HSO4-/SO4 2-) (+17 more)

### Community 21 - "A/B/C/D four-strategy showcase"
Cohesion: 0.13
Nodes (15): Nearest-Damköhler geometry matching diagnostic, Local elasticities on the Arrhenius 1/T coordinate, What can and cannot be concluded from the sweeps, A/B/C/D four-strategy showcase, Synthetic CPR-NMR heteroscedastic correlated noise model, Fisher Information Matrix and Cramér–Rao bound, Franceschini & Macchietto (2008) MBDoE review, D-optimal Model-Based Design of Experiments (+7 more)

### Community 22 - "test_analysis.py"
Cohesion: 0.22
Nodes (12): assign_regime(), axial_peak(), enrich(), _kinetic_constants(), Any, Read the current simulator constants without modifying or running it., water_density_g_L(), water_viscosity_Pa_s() (+4 more)

### Community 23 - "NMRSimulator"
Cohesion: 0.15
Nodes (18): first_order_multiplet(), Line, NMRSimulator, ndarray, One acquisition's random draw of the nuisance parameters., One transition: unit-area Lorentzian x area., [(ppm, relative_area), ...]; binomial first-order multiplet (unchanged physics…, Forward model: molar concentrations -> 80 MHz 1H spectrum. `simulate` is the… (+10 more)

### Community 24 - "Detection, Cache and Update Flow"
Cohesion: 0.21
Nodes (13): URL Ingest via /graphify add, Token Reduction Benchmark, Monorepo Subfolder Extraction Flow, Whisper Video and Audio Transcription, Post-Update Graph Diff, Incremental --update Flow, Corpus Size Gate and Narrowing Prompt, Corpus File Detection (Step 2) (+5 more)

### Community 25 - "Extraction Spec and Honesty Rules"
Cohesion: 0.19
Nodes (13): Confidence Score Rubric, DEEP_MODE Aggressive Inference, Hyperedge Extraction Rule, Node ID Format Rule, Semantic Similarity Edge Rule, source_file Verbatim Rule, Extraction Subagent Prompt, Image Vision Extraction Rules (+5 more)

### Community 26 - "sim_nmr(2).py"
Cohesion: 0.07
Nodes (60): area_under_curve(), averaged_exchange_peak(), build_group_records(), build_species_records(), build_spectrum(), concentrations_at(), _draw_labels(), emit_zooms() (+52 more)

### Community 27 - "KineticModel"
Cohesion: 0.12
Nodes (11): KineticModel, kappa_i = k_i(T) * c_cat, the forward time-scale constants. c_cat is [H+] on…, Net rates (positive = ester-cleavage direction) for the state vector c in…, ArrheniusStep, EquilibriumStep, k(T) = A * exp(-Ea / (R T)) with A in L/(mol s) and Ea in J/mol., Concentration-based hydrolysis equilibrium constant of one step, K(T) = (…, ndarray (+3 more)

### Community 28 - "progress"
Cohesion: 0.23
Nodes (6): progress(), Any, Small tqdm wrapper with a no-dependency text fallback., Minimal progress reporter used only when tqdm is unavailable., Return tqdm when installed, otherwise a basic percentage reporter., _TextProgress

### Community 29 - "AcquisitionSettings"
Cohesion: 0.09
Nodes (29): generate(), ndarray, Three deterministic representative NMR examples for the publication figures.…, (label, ppm, observed, fitted, residual, components) per example., Per-species (plus pool and baseline) contribution to the FITTED spectrum.…, Simulate, deconvolve and export the three examples. Returns one summary row per…, _species_components(), spectra_for_plot() (+21 more)

### Community 30 - "instrument.py"
Cohesion: 0.12
Nodes (21): Propagator, AdvancedVirtualLaboratory: the hidden-truth side of the advanced system. Owns…, Sample-transfer model for the single moving CPR capillary. Hardware represented…, Composition arriving at the NMR cell for a sample drawn at z. Applies (in…, Stateful virtual transfer line (owned by the instrument). Remembers the…, (taus, weights) of the residence-time quadrature., TransferConfig, TransferLine (+13 more)

### Community 31 - "sdl/__init__.py"
Cohesion: 0.11
Nodes (22): The inverse problem — kinetics from noisy measurements, Reference-temperature (k_ref, Ea) reparameterization, Seven-step self-driving closed loop, Measurement object (condition, ports, species, noisy values), noise_true vs noise_assumed misspecification study hook, OperatingConditions experiment record, Recommended study extensions (Monte Carlo, cost-aware, ablation), Laplace-approximate Bayesian posterior for ONE kinetic-model hypothesis.… (+14 more)

### Community 32 - "ParameterSpace"
Cohesion: 0.14
Nodes (9): ParameterSpace, ndarray, Estimated components merged with the held-fixed ones, so the forward model…, Keys whose estimate is resting on its box constraint. A bounded least-squares…, Approximate 95% relative confidence half-widths, %, per parameter. For ln-…, Copy of this space with `keys` moved out of theta and pinned at their initial-…, benchmark_params.csv was empty because an early rank-deficient FIM gives an…, test_parameter_rows_are_populated_even_with_singular_fim() (+1 more)

### Community 33 - "Batch Results Analysis CLI"
Cohesion: 0.31
Nodes (8): main(), parse_args(), load_config(), _merge(), Any, Path, Large-sweep storage/detail degradation strategy, Namespace

### Community 34 - "AdequacyGovernor"
Cohesion: 0.16
Nodes (8): AdequacyGovernor, ndarray, Max standardized mean residual over (experiment x species) CELLS, Sidak-…, (component p-values, combined Sidak min-p, species bias, chi2/dof score, pooled…, THE single definition of which diagnostics enter the decision. Used identically…, Sidak-combined min-p over the DECISION components., B must satisfy 1/(B+1) <= alpha or the bootstrap p-value can never reach the…, Parametric-bootstrap empirical p-value of the DECISION statistic (same…

### Community 35 - "run_advanced_campaign.py"
Cohesion: 0.36
Nodes (7): _figure_a(), _figure_d(), main(), Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling…, Truth vs deconvolved concentration over random compositions., True profile + equal vs optimized positions + information density., resolve_outdir()

### Community 36 - "OperatingConditions"
Cohesion: 0.10
Nodes (36): Bounded continuous Powell refinement of the best candidate, Experiment design: fixed (conventional) designs and autonomous MBDoE. Fixed…, bounds_vector(), DesignResolution, free_indices(), from_vector(), ndarray, Continuous design space: instrument resolution and bounded refinement. WHY THIS… (+28 more)

### Community 37 - "Build, Cluster and Export Steps"
Cohesion: 0.25
Nodes (8): Agent-Crawlable Wiki Export, Cluster-Only Rerun, Deleted-File Pruning, Build, Cluster and Analyze (Step 4), Community Labeling (Step 5), Directed Graph Mode, AST + Semantic Merge (Part C), graph.json Shrink Guard

### Community 38 - "Codex Subagent Dispatch"
Cohesion: 0.29
Nodes (8): Parallel Subagent Chunk Dispatch, General-Purpose Subagent Requirement, Confidence Score Rubric (Codex), Node ID Format Rule (Codex), Extraction Subagent Prompt (Compact), In-Memory Chunk Collection, Codex multi_agent Feature Flag, Codex spawn_agent Dispatch

### Community 39 - "Auto-Rebuild Watch and Commit Hooks"
Cohesion: 0.40
Nodes (6): Watcher Debounce Window, Folder Watch Auto-Rebuild, Post-Commit Auto-Rebuild Hook, Work Memory and LESSONS.md Reflections, Code-Only Change Fast Path, Structural AST Extraction (Part A)

### Community 40 - "Graphify Workflow Policy"
Cohesion: 0.33
Nodes (6): Dirty graphify-out files are expected, Query-first policy for codebase questions, graphify update . (AST-only, no API cost), AGENTS.md graphify workflow rules, CLAUDE.md graphify workflow rules, graphify-out artifacts (graph.json, wiki, GRAPH_REPORT)

### Community 41 - "Query, Path and Explain Flows"
Cohesion: 0.50
Nodes (5): Explain a Single Node, Inline NetworkX Traversal Fallback, save-result Feedback Loop, Shortest Path Between Concepts, Token-Budget Aware Output

### Community 42 - "test_geometry_packing.py"
Cohesion: 0.07
Nodes (36): check_truth_in_domain(), Is every hidden true parameter inside the candidate model's domain? Returns a…, domain_scan(), k_sensitivity(), phi_profiles(), plot_phi_profiles(), ndarray, Equilibrium observability of the reversible EGDA hydrolysis. The reversible… (+28 more)

### Community 43 - "test_parallel.py"
Cohesion: 0.12
Nodes (25): ProcessPoolExecutor, describe_workers(), make_executor(), ordered_map(), pin_numerical_threads(), Cross-platform, determinism-preserving process parallelism for the benchmark.…, Apply `fn(*args)` to every tuple, returning results in SUBMISSION order. `fn`…, Pin every numerical backend to `n_threads`. Call this BEFORE importing… (+17 more)

### Community 45 - "Layer1Bridge"
Cohesion: 0.09
Nodes (45): GovernorConfig, make_lab(), AdvancedVirtualLaboratory, InstrumentConfig, POST-CAMPAIGN benchmarking only., build_egda_family(), The interpretable EGDA/H2SO4 candidate family (see module docstring). `include`…, Campaign resource accounting and the resource-aware utility terms. Every… (+37 more)

### Community 46 - "sdl_advanced/reporting.py"
Cohesion: 0.09
Nodes (40): _csv(), figure_a_spatial_value(), figure_b_position_rounds(), figure_c_spectrum(), figure_convergence_band(), figure_d_truth_vs_recovered(), figure_design_trajectory(), figure_e_convergence() (+32 more)

### Community 47 - "benchmark.py"
Cohesion: 0.05
Nodes (55): AdvancedDesignConfig, active_geometry(), _assumed_transfer_from(), BaselineLabAdapter, blind_rmse(), continuous_kwargs(), design_for_budget(), design_resolution() (+47 more)

### Community 48 - "ReactorGeometry"
Cohesion: 0.11
Nodes (8): Straight cylindrical tube, optionally filled with INERT packing. Defaults match…, epsilon actually used by the hydrodynamics (1 when unpacked)., Empty-tube cross-section (geometric)., Cross-section carrying flowing liquid; sets the INTERSTITIAL velocity u = Q /…, Total (empty-tube) reactor volume., Flowing-liquid holdup: epsilon * V_tube., tau = epsilon A L / Q (= A L / Q for an unpacked tube)., ReactorGeometry

### Community 49 - "io.py"
Cohesion: 0.45
Nodes (10): configuration_key(), _csv_value(), discover(), flatten_run_config(), _number(), Any, Path, read_profile() (+2 more)

### Community 50 - "SpatialDesignConfig"
Cohesion: 0.19
Nodes (16): fixed_equal_positions(), Spatial measurement design for the moving-capillary CPR. The sampling position…, Exact legacy layout of run_sdl_campaign.py: z_i = i L/N, i=1..N., SpatialDesignConfig, _field_and_designer(), Tests of optimal spatial sampling (sdl_advanced.spatial_design). Runnable…, TRUE closed-loop requirement: changing the FIRST measured result must be able…, Acceptance criterion 3: fixed_equal == L * arange(1..N)/N. (+8 more)

### Community 51 - "surrogate_validation"
Cohesion: 0.24
Nodes (10): _compiled_nondominated_indices(), _error_metrics(), _nondominated_indices(), _polynomial_design(), ndarray, Validate one quadratic response surface per study. All requested responses…, Compiled incremental skyline scan for large exact fronts., Return nondominated row indices for a maximization matrix. Lexicographic… (+2 more)

### Community 52 - "SpatialDesigner"
Cohesion: 0.19
Nodes (11): _logdet_floored(), ndarray, (y (n_species,), S (n_species x p)) linearly interpolated at z., Chooses sampling positions for one operating condition. cov_builder(y_at_z) ->…, Full profile for one condition, according to cfg.mode., Adaptive-sequential step: best next z given positions already measured at this…, Deterministic cyclic coordinate polish of the selected positions on the…, (z_grid, marginal log-det gain of one acquisition at each z) - the information-… (+3 more)

### Community 53 - "test_truth_firewall.py"
Cohesion: 0.24
Nodes (12): _mini_campaign(), Truth/inference firewall tests for the advanced system, exercised through a…, STRONG invariant: starting from everything the controller owns (ensemble,…, The observation operator must be built from COMMANDED/ASSUMED transfer…, All Python objects reachable from `roots` via attributes and containers (id-…, _reachable_objects(), test_full_campaign_never_reveals_truth(), test_lab_unreachable_from_controller_object_graph() (+4 more)

### Community 54 - "audit_summary.py"
Cohesion: 0.17
Nodes (14): _boot_ci_median(), _checksums(), convergence_summary_rows(), _git_commit(), _package_versions(), parameter_domain_check_rows(), ndarray, Run-level audit artifacts: convergence summaries that survive failed campaigns,… (+6 more)

### Community 55 - "test_nmr_calibration.py"
Cohesion: 0.09
Nodes (24): NMRCalibration, ndarray, DESIGN-TIME predictor of the deconvolution covariance for a CANDIDATE…, PUBLIC calibration artifact: everything a real Fourier-80 campaign would obtain…, Predicted Sigma_y for ONE position's species concentrations., Species-major covariance for a whole candidate profile., No-op: this model is analytic, not data-fitted (interface parity with…, Guard used by the firewall test: the artifact must expose only calibration… (+16 more)

### Community 56 - "NoiseModel"
Cohesion: 0.15
Nodes (17): greedy_d_optimal(), information_matrices(), _logdet_floored(), ndarray, Pre-campaign identifiability screen. Before a single experiment is spent, ask…, Per-condition information M_e = S_e' Sigma_e^-1 S_e at `theta_vec` (default:…, log det F with eigenvalues floored, so a rank-deficient F still ranks sensibly…, FIM of the greedy D-optimal `budget`-experiment design over `mats`. (+9 more)

### Community 57 - "create_figures"
Cohesion: 0.52
Nodes (6): create_figures(), _finish(), Any, Figure, Path, _study_groups()

### Community 58 - "ResourceMeter"
Cohesion: 0.17
Nodes (8): ndarray, Capillary move + flush + one NMR acquisition at position z. retry=True marks a…, A position whose data was rejected by the QC gate (not assimilated); auditable,…, Scalar penalty term of the resource-aware utility for a HYPOTHETICAL experiment…, Accumulates the campaign's physical cost from logged events., Reactor condition set + stabilization to steady state. Idempotent for an…, ResourceEvent, ResourceMeter

### Community 59 - "build_report"
Cohesion: 0.47
Nodes (5): build_report(), _fmt(), Any, Path, Independent regime flags and primary regime priority

### Community 60 - "apply_config"
Cohesion: 0.24
Nodes (11): apply_config(), Apply a runner's CONFIG knobs to this module's configuration blocks. The…, Every knob's CURRENT value - what the run actually used., resolved_config(), test_geometry_optimization_picks_from_the_declared_space(), test_per_experiment_geometry_refuses_rather_than_pretending(), A silently-ignored knob is indistinguishable from a knob that had no effect;…, The point of the CONFIG block is that a user can reach EVERY knob from one… (+3 more)

### Community 61 - "AuditRecorder"
Cohesion: 0.13
Nodes (8): AuditRecorder, Passive audit recorder for the publication workflow. DESIGN RULE, and the whole…, `part` is the controller's per-position view of one acquisition: {"z", "y",…, Whole-profile convenience for the ungated (direct-observation) path, where…, Wall-clock only. Reading a clock cannot change a result, and these columns are…, Picklable primitives only, for the trip back from a worker., Append-only sink. Holds plain Python/NumPy scalars so the payload is cheap to…, `screened` is the selector's own sorted list of (screen_score, u, z_positions,…

### Community 62 - "MBDoESelector"
Cohesion: 0.36
Nodes (4): MBDoESelector, ndarray, Bounds in canonical order. A DEGENERATE dimension (lo == hi) is accepted and…, Design score with FLOORED eigenvalues. `slogdet` returns -inf for any singular…

### Community 63 - ".run_profile"
Cohesion: 0.18
Nodes (6): ndarray, Hidden true composition (ALL Layer-1 species) at each z., Batch-reaction propagator at the transfer-line temperature, closed over the…, Set condition u, sample the requested positions in the given order (one moving…, Legacy-style observation: concentrations + NoiseModel noise. cov_y stays None…, Spectrum -> deconvolution. The fitter sees only the spectrum.

### Community 64 - "run_scenario"
Cohesion: 0.14
Nodes (16): Returns (round rows, per-parameter rows, per-campaign status rows). NO campaign…, run_scenario(), runtime_s measures the RUN, not the chemistry: it is the one field a worker…, Plain `==` is unusable here: legitimate NaNs (p_correct for a non-Bayesian…, Guard the guard: the NaN-tolerant comparator must not be so forgiving that the…, Only primitives may cross the process boundary - never a laboratory, a…, The whole point, end to end: a real registered scenario with all six of its…, A scenario object that is not the one in SCENARIOS cannot be sent to a worker… (+8 more)

### Community 65 - "main"
Cohesion: 0.15
Nodes (16): _finals(), main(), _mean_curves(), Main EGDA advanced benchmark (corrected framework, v3 outputs). Runs the…, # NOTE: with this on, blind RMSE is computed in the CHOSEN reactor, so, resolve_outdir(), _write_rows(), campaign_cost_units() (+8 more)

### Community 66 - "AdvancedSelector"
Cohesion: 0.13
Nodes (13): AdvancedSelector, _logdet_floored(), ndarray, Sigma for ONE position's species vector., Species-major covariance for a whole profile (block per z)., Hierarchical (u, Z) selector for strategy F., Sensitivity field of the EXPECTED OBSERVATION (through the candidate's…, Sensitivity matrix of the reference-grid predictions wrt theta (best model,… (+5 more)

### Community 67 - "AnalysisTests"
Cohesion: 0.22
Nodes (6): pareto_front(), Find exact fronts for small studies and epsilon fronts for large ones. Exact…, AnalysisTests, Path, sample_payload(), write_scenario()

### Community 68 - "test_resource_accounting.py"
Cohesion: 0.22
Nodes (12): _meter(), Tests of resource accounting (sdl_advanced.resources). Runnable standalone., Predicted candidate cost and realized event accounting must use the same…, Acceptance criterion 13: totals are nonnegative and re-derivable from the event…, Adaptive one-z-at-a-time sampling at the SAME (T,Q,C_EGDA,C_cat) must not re-…, test_candidate_cost_consistent_with_realized_events(), test_candidate_cost_penalizes_motion_and_switches(), test_capillary_travel_is_sum_of_moves() (+4 more)

### Community 69 - "campaign_task"
Cohesion: 0.18
Nodes (11): campaign_task(), ONE campaign, as a picklable pure function of its four labels. This is the unit…, The EIG is Monte-Carlo and consumes the selector's RNG. The audit may report…, A QC-rejected spectrum never reaches the posterior, so it exists in no…, The cumulative columns are re-derived from raw events, so they must land on the…, F is a Laplace posterior: its curvature includes the prior, so the eigenvalues…, test_audit_tables_are_populated_and_self_consistent(), test_identifiability_labels_which_matrix_it_used() (+3 more)

### Community 70 - "Literature-anchored kinetic parameter provenance"
Cohesion: 0.40
Nodes (5): Berthelot & Péan de Saint-Gilles (1862) esterification equilibrium, A. J. Kirby, Comprehensive Chemical Kinetics Vol. 10, Literature-anchored kinetic parameter provenance, Ethyl acetate + NaOH conductometric saponification benchmarks, Statistical factors for equivalent acetate groups

### Community 71 - ".predict"
Cohesion: 0.27
Nodes (4): ndarray, The candidate's expected-observation operator - the ONE way any controller-side…, Current MAP if fitted, else the initial guess (for pre-data design)., Particle prediction through the candidate's expected-observation operator (NOT…

### Community 72 - "reactor.py"
Cohesion: 0.11
Nodes (16): _bracketed_root(), equilibrium_state(), Composition at simultaneous chemical equilibrium of both steps. Solves for the…, Root of a monotonically increasing f on [lo, hi] with f(lo) <= 0 <= f(hi)., nu_matrix(), ndarray, Steady-state, isothermal, 1D plug flow reactor model. Governing equations…, Stoichiometric matrix of the chosen catalyst system. (+8 more)

### Community 73 - "last_valid_rows"
Cohesion: 0.31
Nodes (9): _boot_ci(), last_valid_rows(), paired_comparison(), One row per SEED: that seed's LAST COMPLETED round. Using the per-seed last…, Last-valid-round distributional summary per strategy: median, IQR, mean,…, Common-random-number PAIRED comparison of two strategies at the final round:…, summarize_final(), A seed that stops early keeps its LAST VALID round in the summary (n_seeds… (+1 more)

### Community 75 - "audit_export.py"
Cohesion: 0.12
Nodes (28): blind_prediction_rows(), calibration_rows(), collect_campaign(), design_history_rows(), _empty(), empty_bundle(), _f(), governor_rows() (+20 more)

## Ambiguous Edges - Review These
- `Feed / Catalyst Concentration Combinations (bubble area)` → `R_OH Hydroxide Ratio`  [AMBIGUOUS]
  BatchSweep_Analysis/docs/images/derived_metrics.png · relation: conceptually_related_to
- `duplicate_configs.csv (data source)` → `Figure: Largest Y_EGMA Interaction Components`  [AMBIGUOUS]
  BatchSweep_Analysis/docs/images/interaction_effects.png · relation: shares_data_with
- `Advisory: radially_segregated (2250 scenarios)` → `Geometry B`  [AMBIGUOUS]
  BatchSweep_Analysis/docs/images/excluded_or_invalid_scenarios.png · relation: conceptually_related_to
- `Finding: NaOH branch variance driven by C_EGDA_feed_M, especially geometry B (~33%)` → `Unexplained Variance (higher-order interactions)`  [AMBIGUOUS]
  BatchSweep_Analysis/docs/images/main_effects.png · relation: conceptually_related_to
- `Finding: NaOH scenarios reach highest yields (~0.5) and highest STY` → `Finding: physical_validity_question flags 100% of scenarios in all four branches`  [AMBIGUOUS]
  BatchSweep_Analysis/docs/images/regime_assignments.png · relation: conceptually_related_to
- `NaOH_exhausted Regime` → `Finding: NaOH Surrogate Error ~4x Larger Than H2SO4`  [AMBIGUOUS]
  BatchSweep_Analysis/docs/images/surrogate_validation.png · relation: conceptually_related_to

## Knowledge Gaps
- **61 isolated node(s):** `Cumulative Token Cost Tracker`, `Obsidian Vault Export`, `Token Reduction Benchmark`, `Native CLAUDE.md Integration`, `Post-Update Graph Diff` (+56 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Feed / Catalyst Concentration Combinations (bubble area)` and `R_OH Hydroxide Ratio`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `duplicate_configs.csv (data source)` and `Figure: Largest Y_EGMA Interaction Components`?**
  _Edge tagged AMBIGUOUS (relation: shares_data_with) - confidence is low._
- **What is the exact relationship between `Advisory: radially_segregated (2250 scenarios)` and `Geometry B`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Finding: NaOH branch variance driven by C_EGDA_feed_M, especially geometry B (~33%)` and `Unexplained Variance (higher-order interactions)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Finding: NaOH scenarios reach highest yields (~0.5) and highest STY` and `Finding: physical_validity_question flags 100% of scenarios in all four branches`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `NaOH_exhausted Regime` and `Finding: NaOH Surrogate Error ~4x Larger Than H2SO4`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `OperatingConditions` connect `OperatingConditions` to `InferenceModel`, `sdl/reporting.py`, `self_test.py`, `AssumedTransfer`, `pfr_twin/__init__.py`, `ModelEnsemble`, `SpectralFitter`, `KineticModel`, `instrument.py`, `sdl/__init__.py`, `run_advanced_campaign.py`, `test_geometry_packing.py`, `Layer1Bridge`, `benchmark.py`, `SpatialDesignConfig`, `test_truth_firewall.py`, `NoiseModel`, `MBDoESelector`, `.run_profile`, `main`, `AdvancedSelector`, `.predict`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._