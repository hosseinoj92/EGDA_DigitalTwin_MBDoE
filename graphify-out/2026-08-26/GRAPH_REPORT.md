# Graph Report - EGDA  (2026-08-18)

## Corpus Check
- 116 files · ~618,592 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1878 nodes · 4781 edges · 82 communities (76 shown, 6 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 409 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a9ca408f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pipeline.py
- Sweep Integrity and Geometry Collapse Figures
- Sensitivity and Pareto Figures
- Regime, Robustness and Surrogate Figures
- ndarray
- Design Coverage and Damkohler Figures
- build_readme_figures.py
- sdl/reporting.py
- literature_guess
- speciation.py
- plotting.py
- Layer1Bridge
- batch_simulation.py
- pfr_twin/__init__.py
- benchmark.py
- test_comparison.py
- Codex Graphify Feature Set
- SpectralFitter
- test_audit_regression.py
- Claude Graphify Feature Set
- PFR digital twin layer README
- Fisher Information Matrix and Cramér–Rao bound
- test_analysis.py
- NMRSimulator
- Detection, Cache and Update Flow
- Extraction Spec and Honesty Rules
- sim_nmr(2).py
- .effective_constants
- progress
- test_spectral.py
- AuditRecorder
- OperatingConditions
- ParameterSpace
- Batch Results Analysis CLI
- ._model_components
- test_acquisition.py
- test_design_space.py
- Build, Cluster and Export Steps
- Codex Subagent Dispatch
- Auto-Rebuild Watch and Commit Hooks
- Graphify Workflow Policy
- Query, Path and Explain Flows
- NMRCalibration
- test_parallel.py
- BatchSweep Package Init
- AdvancedVirtualLaboratory
- sdl_advanced/reporting.py
- run_one_campaign
- ReactorGeometry
- io.py
- run_sdl_campaign.py
- surrogate_validation
- ndarray
- AcquisitionSettings
- audit_summary.py
- test_nmr_calibration.py
- main
- create_figures
- ResourceMeter
- build_report
- apply_config
- test_deconvolution.py
- run_temperature_study.py
- .run_profile
- _geometry_score
- Measurement
- AdvancedSelector
- MBDoESelector
- campaign_task
- _round_metrics
- Literature-anchored kinetic parameter provenance
- ._through_line
- Per-run self-verification block (PASS/FAIL residuals)
- last_valid_rows
- .concentrations_at
- audit_export.py
- run_case
- .bootstrap_pvalue
- _scoring_bridge
- .covariance
- Ideal micromixer inlet reconstruction from pump dosing
- test_recorder_never_touches_an_rng

## God Nodes (most connected - your core abstractions)
1. `OperatingConditions` - 118 edges
2. `Layer1Bridge` - 106 edges
3. `AcquisitionSettings` - 62 edges
4. `NoiseModel` - 60 edges
5. `InferenceModel` - 59 edges
6. `ParameterSpace` - 59 edges
7. `ModelEnsemble` - 59 edges
8. `main()` - 56 edges
9. `NMRSimulator` - 55 edges
10. `Measurement` - 52 edges

## Surprising Connections (you probably didn't know these)
- `Coupled equilibrium solver (Gauss–Seidel + Brent)` --implements--> `equilibrium_state()`  [EXTRACTED]
  README.md → PFR_H2SO4_digital_twin/pfr_twin/analytical.py
- `graphify Pipeline (Codex)` --semantically_similar_to--> `graphify Pipeline (Claude Code)`  [INFERRED] [semantically similar]
  .codex/skills/graphify/SKILL.md → .claude/skills/graphify/SKILL.md
- `Extraction Subagent Prompt (Compact)` --semantically_similar_to--> `Extraction Subagent Prompt`  [INFERRED] [semantically similar]
  .codex/skills/graphify/references/extraction-spec.md → .claude/skills/graphify/references/extraction-spec.md
- `Codex spawn_agent Dispatch` --semantically_similar_to--> `Parallel Subagent Chunk Dispatch`  [INFERRED] [semantically similar]
  .codex/skills/graphify/SKILL.md → .claude/skills/graphify/SKILL.md
- `In-Memory Chunk Collection` --semantically_similar_to--> `General-Purpose Subagent Requirement`  [INFERRED] [semantically similar]
  .codex/skills/graphify/SKILL.md → .claude/skills/graphify/SKILL.md

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

## Communities (82 total, 6 thin omitted)

### Community 0 - "pipeline.py"
Cohesion: 0.17
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

### Community 4 - "ndarray"
Cohesion: 0.29
Nodes (4): ndarray, Central-difference S (m.size x p) in scaled parameter space., Expected FIM contribution of a candidate experiment, evaluated at the CURRENT…, THE expected-observation operator: what a measurement at (u, z) is predicted to…

### Community 5 - "Design Coverage and Damkohler Figures"
Cohesion: 0.10
Nodes (30): axial_egma_peaks.csv (peak dataset), Figure: Axial EGMA Intermediate Maxima (H2SO4 vs NaOH), Reactor Geometry A, Reactor Geometry B, H2SO4 Catalyst Branch, Finding: H2SO4 peaks pinned at outlet, NaOH peaks interior, NaOH Catalyst Branch, Peak EGMA Yield (+22 more)

### Community 6 - "build_readme_figures.py"
Cohesion: 0.23
Nodes (25): axial_egma_peaks(), consolidated_scenarios(), convert(), data_coverage(), derived_metrics(), duplicate_configs(), excluded_or_invalid_scenarios(), geometry_collapse_metrics() (+17 more)

### Community 7 - "sdl/reporting.py"
Cohesion: 0.13
Nodes (32): campaign_history.csv per-round record, final_report.txt human-readable campaign summary, main(), StrategyResult, Short name of the scaled theta component for a natural key., theta_component_name(), campaign_score_pct(), log_mean_rel_error_pct() (+24 more)

### Community 8 - "literature_guess"
Cohesion: 0.14
Nodes (20): literature_guess(), Initial estimates = Layer 1's literature-anchored kinetics for the chosen…, param_keys_for(), Estimated parameter keys of the chosen catalyst system., _make_loop(), _ports(), Layer 2 self-tests. Pytest-compatible (plain test_* functions with asserts),…, Per mole of catalyst, saponification must be orders of magnitude faster.… (+12 more)

### Community 9 - "speciation.py"
Cohesion: 0.12
Nodes (22): bisulfate_equilibrium(), [H+] for total sulfate molarity c_total, ideal activities (back-compat alias…, aphi(), bisulfate_dilute(), bisulfate_pitzer(), _g(), h_plus_concentration(), ka2_clarke_glew() (+14 more)

### Community 10 - "plotting.py"
Cohesion: 0.12
Nodes (27): _end_label(), _legend(), _new_axes(), plot_concentration_profiles(), plot_conversion_yield(), plot_profile_overlay(), plot_scenario_bars(), plot_scenario_curves() (+19 more)

### Community 11 - "Layer1Bridge"
Cohesion: 0.09
Nodes (44): _truth_prediction(), AssumedTransfer, build_egda_family(), CandidateModel, Particle, Multi-model Bayesian kinetic inference: p(M, theta | D) via a Laplace model…, The interpretable EGDA/H2SO4 candidate family (see module docstring). `include`…, INFERENCE-SIDE transfer knowledge: only COMMANDED / CALIBRATED quantities… (+36 more)

### Community 12 - "batch_simulation.py"
Cohesion: 0.08
Nodes (42): BatchSweep Analysis methods and interpretation README, Read-only post-processing layer over saved sweeps, _fmt_secs(), main(), _progress(), BATCH base-case runs of the PFR digital twin. Same physics and outputs as…, Yield items with a tqdm-style progress bar (count, %, elapsed, ETA). Uses tqdm…, Simulate every scenario, write per-scenario folders and the summary. (+34 more)

### Community 13 - "pfr_twin/__init__.py"
Cohesion: 0.07
Nodes (51): analytical_profiles(), _bracketed_root(), equilibrium_state(), max_relative_error(), ndarray, Algebraic reference solutions used to verify the numerical integrator. 1.…, Composition at simultaneous chemical equilibrium of both steps. Solves for the…, Largest |numerical - analytical| across species, relative to `scale`. (+43 more)

### Community 14 - "benchmark.py"
Cohesion: 0.07
Nodes (56): _figure_a(), Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling…, # NOTE: with this on, blind RMSE is computed in the CHOSEN reactor, so, # NOTE: the shipped 20 cm OPEN tube FAILS this at every design flow, True profile + equal vs optimized positions + information density., AdequacyReport, GovernorState, AdvancedDesignConfig (+48 more)

### Community 15 - "test_comparison.py"
Cohesion: 0.10
Nodes (34): _agg(), _at_or_before(), budget_to_target_rows(), _first_reaching(), headline_rows(), matched_resource_rows(), Conventional-vs-optimized comparison: how much does the methodology actually…, What accuracy had each method reached by the time it had spent what the… (+26 more)

### Community 16 - "Codex Graphify Feature Set"
Cohesion: 0.12
Nodes (16): URL Ingest via /graphify add (Codex), Folder Watch Auto-Rebuild (Codex), FalkorDB Cypher Export (Codex), graphify MCP stdio Server (Codex), Neo4j Cypher Export (Codex), GitHub Repo Clone (Codex), Cross-Repo Graph Merge (Codex), Native CLAUDE.md Integration (Codex) (+8 more)

### Community 17 - "SpectralFitter"
Cohesion: 0.09
Nodes (38): generate(), ndarray, Three deterministic representative NMR examples for the publication figures.…, (label, ppm, observed, fitted, residual, components) per example., Per-species (plus pool and baseline) contribution to the FITTED spectrum.…, Simulate, deconvolve and export the three examples. Returns one summary row per…, _species_components(), spectra_for_plot() (+30 more)

### Community 18 - "test_audit_regression.py"
Cohesion: 0.16
Nodes (19): _compare(), _first_difference(), Regression guard for the publication audit trail. THE CLAIM UNDER TEST: turning…, A-D run unchanged sdl.campaign code and are audited entirely post-campaign, so…, E adds spatial optimization and per-round timing calls., The one that matters: F exercises the EIG selector (RNG), the QC gate and the…, S3 turns on the NMR pathway, the transfer line and the QC gate, so the…, S5 removes the correct model, so the governor fires and the selector switches… (+11 more)

### Community 19 - "Claude Graphify Feature Set"
Cohesion: 0.18
Nodes (15): /graphify Trigger Registration, FalkorDB Cypher Export, graphify MCP stdio Server, Neo4j Cypher Export, GitHub Repo Clone, Cross-Repo Graph Merge, Native CLAUDE.md Integration, BFS and DFS Traversal Modes (+7 more)

### Community 20 - "PFR digital twin layer README"
Cohesion: 0.09
Nodes (25): Axial EGMA peak location and 95% plateau interval, Damköhler kinetic-exposure metric, Contrast with the packed-bed Amberlyst twin, PFR digital twin layer README, Water as explicit reactant on the acid route, Layer 1 Python dependencies (numpy, scipy, matplotlib), R. P. Bell, Acid–Base Catalysis, Bisulfate catalyst speciation ([H+] from HSO4-/SO4 2-) (+17 more)

### Community 21 - "Fisher Information Matrix and Cramér–Rao bound"
Cohesion: 0.29
Nodes (7): Nearest-Damköhler geometry matching diagnostic, Local elasticities on the Arrhenius 1/T coordinate, What can and cannot be concluded from the sweeps, Synthetic CPR-NMR heteroscedastic correlated noise model, Fisher Information Matrix and Cramér–Rao bound, Whitened weighted least-squares estimation, FIM uncertainty is local and asymptotic

### Community 22 - "test_analysis.py"
Cohesion: 0.16
Nodes (16): assign_regime(), axial_peak(), enrich(), _kinetic_constants(), Any, Read the current simulator constants without modifying or running it., water_density_g_L(), water_viscosity_Pa_s() (+8 more)

### Community 23 - "NMRSimulator"
Cohesion: 0.13
Nodes (19): first_order_multiplet(), Line, NMRSimulator, _noise_grid_factor(), ndarray, Std-dev change caused by RESAMPLING the FFT-bin noise onto the display grid,…, One acquisition's random draw of the nuisance parameters., One transition: unit-area Lorentzian x area. (+11 more)

### Community 24 - "Detection, Cache and Update Flow"
Cohesion: 0.21
Nodes (13): URL Ingest via /graphify add, Token Reduction Benchmark, Monorepo Subfolder Extraction Flow, Whisper Video and Audio Transcription, Post-Update Graph Diff, Incremental --update Flow, Corpus Size Gate and Narrowing Prompt, Corpus File Detection (Step 2) (+5 more)

### Community 25 - "Extraction Spec and Honesty Rules"
Cohesion: 0.19
Nodes (13): Confidence Score Rubric, DEEP_MODE Aggressive Inference, Hyperedge Extraction Rule, Node ID Format Rule, Semantic Similarity Edge Rule, source_file Verbatim Rule, Extraction Subagent Prompt, Image Vision Extraction Rules (+5 more)

### Community 26 - "sim_nmr(2).py"
Cohesion: 0.07
Nodes (60): area_under_curve(), averaged_exchange_peak(), build_group_records(), build_species_records(), build_spectrum(), concentrations_at(), _draw_labels(), emit_zooms() (+52 more)

### Community 28 - "progress"
Cohesion: 0.23
Nodes (6): progress(), Any, Small tqdm wrapper with a no-dependency text fallback., Minimal progress reporter used only when tqdm is unavailable., Return tqdm when installed, otherwise a basic percentage reporter., _TextProgress

### Community 29 - "test_spectral.py"
Cohesion: 0.15
Nodes (16): flow_response(), Phenomenological incomplete-relaxation / flow response factor in [0,1]. E = 1 -…, Pooled fast-exchange H2O/OH/COOH line at the population-weighted average shift,…, delta(H2O)/ppm ~ 5.051 - 0.0111*T(degC). Empirical aqueous relation inherited…, water_shift(), _ideal_sim(), Tests of the NMR forward model (sdl_advanced.spectral). Runnable standalone:…, Doubling [EGDA] must exactly double the EGDA-only spectral area. (+8 more)

### Community 30 - "AuditRecorder"
Cohesion: 0.12
Nodes (10): AuditRecorder, Passive audit recorder for the publication workflow. DESIGN RULE, and the whole…, `part` is the controller's per-position view of one acquisition: {"z", "y",…, Whole-profile convenience for the ungated (direct-observation) path, where…, Wall-clock only. Reading a clock cannot change a result, and these columns are…, Picklable primitives only, for the trip back from a worker., Append-only sink. Holds plain Python/NumPy scalars so the payload is cheap to…, `screened` is the selector's own sorted list of (screen_score, u, z_positions,… (+2 more)

### Community 31 - "OperatingConditions"
Cohesion: 0.08
Nodes (36): The inverse problem — kinetics from noisy measurements, Reference-temperature (k_ref, Ea) reparameterization, noise_true vs noise_assumed misspecification study hook, Recommended study extensions (Monte Carlo, cost-aware, ablation), Laplace-approximate Bayesian posterior for ONE kinetic-model hypothesis.…, greedy_d_optimal(), information_matrices(), _logdet_floored() (+28 more)

### Community 32 - "ParameterSpace"
Cohesion: 0.13
Nodes (13): check_truth_in_domain(), Is every hidden true parameter inside the candidate model's domain? Returns a…, ParameterSpace, ndarray, Estimated components merged with the held-fixed ones, so the forward model…, Keys whose estimate is resting on its box constraint. A bounded least-squares…, Approximate 95% relative confidence half-widths, %, per parameter. For ln-…, Copy of this space with `keys` moved out of theta and pinned at their initial-… (+5 more)

### Community 33 - "Batch Results Analysis CLI"
Cohesion: 0.31
Nodes (8): main(), parse_args(), load_config(), _merge(), Any, Path, Large-sweep storage/detail degradation strategy, Namespace

### Community 34 - "._model_components"
Cohesion: 0.16
Nodes (5): ndarray, Max standardized mean residual over (experiment x species) CELLS, Sidak-…, (component p-values, combined Sidak min-p, species bias, chi2/dof score, pooled…, THE single definition of which diagnostics enter the decision. Used identically…, Sidak-combined min-p over the DECISION components.

### Community 35 - "test_acquisition.py"
Cohesion: 0.09
Nodes (27): _radial_ratio(), Open-tube plug-flow validity ratio t_rad/tau = Q/(pi D L eps) at the reference…, Plug-flow validity of the reactor ACTUALLY IN USE, at every flow the design…, reactor_validity_rows(), _bridge(), _noise_std(), _quiet_nuisance(), Three corrections found by external review, each with the property that made it… (+19 more)

### Community 36 - "test_design_space.py"
Cohesion: 0.07
Nodes (47): Leave-one-factor-level-out surrogate validation, A/B/C/D four-strategy showcase, Franceschini & Macchietto (2008) MBDoE review, D-optimal Model-Based Design of Experiments, A-optimal design criterion, Four-axis coarse candidate design grid, Bounded continuous Powell refinement of the best candidate, Equal-experiment-budget fairness caveat (+39 more)

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

### Community 42 - "NMRCalibration"
Cohesion: 0.12
Nodes (11): NMRCalibration, ndarray, QuantificationResult, Adopt a PUBLIC calibration artifact. The design-time SpectralCovarianceModel…, REPORTING ONLY: the per-species (and pool/baseline) contributions to an…, B(eta): columns = phased species spectra, exchange pool, baseline., Water dominates the pool; start at the water shift at the commanded NMR-cell…, PUBLIC calibration artifact: everything a real Fourier-80 campaign would obtain… (+3 more)

### Community 43 - "test_parallel.py"
Cohesion: 0.07
Nodes (46): ProcessPoolExecutor, merge(), governor_mc_validation(), governor_task(), Returns (round rows, per-parameter rows, per-campaign status rows). NO campaign…, First round at which the governor declares MODEL_INADEQUATE, or None. The…, Monte Carlo validation of the governor (#calibration honesty): * correct-family…, run_scenario() (+38 more)

### Community 45 - "AdvancedVirtualLaboratory"
Cohesion: 0.06
Nodes (61): AdequacyGovernor, GovernorConfig, Model-inadequacy governor: distinguishes "my parameters are uncertain" from "my…, _assumed_transfer_from(), BaselineLabAdapter, make_lab(), INFERENCE-side transfer correction from COMMANDED quantities only (nominal…, The S6 lambda sweep: one base weight vector x a scale factor. The base values… (+53 more)

### Community 46 - "sdl_advanced/reporting.py"
Cohesion: 0.09
Nodes (40): _csv(), figure_a_spatial_value(), figure_b_position_rounds(), figure_c_spectrum(), figure_convergence_band(), figure_d_truth_vs_recovered(), figure_design_trajectory(), figure_e_convergence() (+32 more)

### Community 47 - "run_one_campaign"
Cohesion: 0.19
Nodes (13): continuous_kwargs(), design_resolution(), Pre-campaign identifiability screen (same code as run_sdl_campaign.py),…, One (scenario, strategy, seed) campaign. Returns (result, lab, extra).…, Keyword arguments for the BASELINE MBDoESelector (strategies C/D/E). Empty when…, run_one_campaign(), screened_dropped_keys(), build_candidates() (+5 more)

### Community 48 - "ReactorGeometry"
Cohesion: 0.05
Nodes (35): Straight cylindrical tube, optionally filled with INERT packing. Defaults match…, epsilon actually used by the hydrodynamics (1 when unpacked)., Empty-tube cross-section (geometric)., Cross-section carrying flowing liquid; sets the INTERSTITIAL velocity u = Q /…, Total (empty-tube) reactor volume., Flowing-liquid holdup: epsilon * V_tube., tau = epsilon A L / Q (= A L / Q for an unpacked tube)., ReactorGeometry (+27 more)

### Community 49 - "io.py"
Cohesion: 0.39
Nodes (11): configuration_key(), _csv_value(), discover(), flatten_run_config(), _number(), Any, Path, read_profile() (+3 more)

### Community 50 - "run_sdl_campaign.py"
Cohesion: 0.12
Nodes (20): Truth/inference firewall, Seven-step self-driving closed loop, Truth-only systematic effects (transfer_time_s, calibration_gain), Layer 2 showcase: virtual self-driving laboratory around the Layer 1 PFR twin.…, resolve_outdir(), Closed-loop campaign runner - the "self-driving" part. For one strategy the…, RoundRecord, run_strategy() (+12 more)

### Community 51 - "surrogate_validation"
Cohesion: 0.22
Nodes (10): _compiled_nondominated_indices(), _error_metrics(), _nondominated_indices(), _polynomial_design(), ndarray, Validate one quadratic response surface per study. All requested responses…, Compiled incremental skyline scan for large exact fronts., Return nondominated row indices for a maximization matrix. Lexicographic… (+2 more)

### Community 52 - "ndarray"
Cohesion: 0.24
Nodes (7): _logdet_floored(), ndarray, (y (n_species,), S (n_species x p)) linearly interpolated at z., Full profile for one condition, according to cfg.mode., Adaptive-sequential step: best next z given positions already measured at this…, Deterministic cyclic coordinate polish of the selected positions on the…, (z_grid, marginal log-det gain of one acquisition at each z) - the information-…

### Community 53 - "AcquisitionSettings"
Cohesion: 0.07
Nodes (24): AcquisitionSettings, SW = (ppm window) x (spectrometer frequency)., Complex dwell = 1 / SW., Number of COMPLEX FID points actually sampled., What the instrument really spends: N_acquired x dwell. Differs from…, FFT length >= acquired points; default is the next power of two (zero filling,…, Digital bin spacing of the zero-filled spectrum, SW / N_fft. The TRUE…, Requested AND actual acquisition quantities, for the run record. Serializing… (+16 more)

### Community 54 - "audit_summary.py"
Cohesion: 0.17
Nodes (14): _boot_ci_median(), _checksums(), convergence_summary_rows(), _git_commit(), _package_versions(), parameter_domain_check_rows(), ndarray, Run-level audit artifacts: convergence summaries that survive failed campaigns,… (+6 more)

### Community 55 - "test_nmr_calibration.py"
Cohesion: 0.14
Nodes (17): DESIGN-TIME predictor of the deconvolution covariance for a CANDIDATE…, No-op: this model is analytic, not data-fitted (interface parity with…, SpectralCovarianceModel, _calibration(), coverage_gate(), Priority-1 tests: ONE public NMR calibration artifact shared by the measurement…, FAIL only when we can be CONFIDENT the true coverage is below `severe`: the…, End-to-end Priority-1 acceptance on the REACHABLE suite (the one the campaign… (+9 more)

### Community 56 - "main"
Cohesion: 0.13
Nodes (18): _finals(), main(), _mean_curves(), Main EGDA advanced benchmark (corrected framework, v3 outputs). Runs the…, # NOTE: the shipped 20 cm OPEN tube FAILS this at every design flow, resolve_outdir(), _write_rows(), assert_reactor_validity() (+10 more)

### Community 57 - "create_figures"
Cohesion: 0.52
Nodes (6): create_figures(), _finish(), Any, Figure, Path, _study_groups()

### Community 58 - "ResourceMeter"
Cohesion: 0.10
Nodes (20): ndarray, Accumulates the campaign's physical cost from logged events., Reactor condition set + stabilization to steady state. Idempotent for an…, Capillary move + flush + one NMR acquisition at position z. retry=True marks a…, A position whose data was rejected by the QC gate (not assimilated); auditable,…, Scalar penalty term of the resource-aware utility for a HYPOTHETICAL experiment…, ResourceEvent, ResourceMeter (+12 more)

### Community 59 - "build_report"
Cohesion: 0.47
Nodes (5): build_report(), _fmt(), Any, Path, Independent regime flags and primary regime priority

### Community 60 - "apply_config"
Cohesion: 0.08
Nodes (35): _figure_d(), main(), Truth vs deconvolved concentration over random compositions., resolve_outdir(), active_geometry(), apply_config(), _geometry_candidates(), geometry_sizing_table() (+27 more)

### Community 61 - "test_deconvolution.py"
Cohesion: 0.13
Nodes (15): bootstrap_coverage(), Parametric bootstrap: simulate n_boot noisy spectra of a KNOWN composition,…, Tests of spectral quantification (sdl_advanced.spectral_fit). Runnable…, A spectrum the lineshape model cannot explain must raise FAIL QC., Acceptance criterion 6: an ideal spectrum must be deconvolved back to the…, EGDA (4.335) and EGMA ester triplet (4.245) are ~7 Hz apart at 80 MHz: the…, Monte Carlo intervals under the FULL truth-model mismatch, after the response…, Anti-inverse-crime: FID-engine truth (time-domain generation, colored noise,… (+7 more)

### Community 62 - "run_temperature_study.py"
Cohesion: 0.13
Nodes (21): Write the normal numerical outputs without constructing figures., _write_case_outputs_csv_only(), _num(), Run-output plumbing: self-describing result folders and plot-paired CSVs. Two…, Write named equal-length numeric columns as a headed CSV., Compact fixed-point number, trailing FRACTIONAL zeros trimmed ('0.50' -> '0.5',…, Make a string safe for a directory name on Windows and POSIX., Persist the exact configuration that produced this folder. (+13 more)

### Community 63 - ".run_profile"
Cohesion: 0.18
Nodes (6): ndarray, Hidden true composition (ALL Layer-1 species) at each z., Batch-reaction propagator at the transfer-line temperature, closed over the…, Set condition u, sample the requested positions in the given order (one moving…, Legacy-style observation: concentrations + NoiseModel noise. cov_y stays None…, Spectrum -> deconvolution. The fitter sees only the spectrum.

### Community 64 - "_geometry_score"
Cohesion: 0.18
Nodes (12): design_for_budget(), _geometry_objective(), _geometry_score(), DESIGN with a conventional temperature ladder long enough for the requested…, What the reference campaign would CONSUME in this reactor, replayed…, score = information - resource penalty, with feasibility. Returns the…, D-optimal information of a REFERENCE design in this reactor, under the PRIOR…, _reference_campaign_cost() (+4 more)

### Community 65 - "Measurement"
Cohesion: 0.12
Nodes (20): _combine_positions(), measure_with_qc(), _qc_failed(), QCGateConfig, Per-position view of a species-major Measurement., Rebuild one species-major Measurement from per-position parts., Measure the positions with the QC gate applied BEFORE assimilation. Returns…, _split_positions() (+12 more)

### Community 66 - "AdvancedSelector"
Cohesion: 0.09
Nodes (18): AdvancedSelector, expected_information_gain(), _logdet_floored(), ndarray, Species-major covariance for a whole profile (block per z)., (EIG_total, EIG_model) in nats, from cached particle predictions. preds: (N,…, Hierarchical (u, Z) selector for strategy F., Sensitivity field of the EXPECTED OBSERVATION (through the candidate's… (+10 more)

### Community 67 - "MBDoESelector"
Cohesion: 0.25
Nodes (6): MBDoESelector, ndarray, Bounds in canonical order. A DEGENERATE dimension (lo == hi) is accepted and…, Design score with FLOORED eigenvalues. `slogdet` returns -inf for any singular…, The hybrid selector must improve on its coarse seed without leaving the user-…, test_continuous_design_refines_inside_bounds()

### Community 68 - "campaign_task"
Cohesion: 0.18
Nodes (11): campaign_task(), ONE campaign, as a picklable pure function of its four labels. This is the unit…, A QC-rejected spectrum never reaches the posterior, so it exists in no…, The cumulative columns are re-derived from raw events, so they must land on the…, F is a Laplace posterior: its curvature includes the prior, so the eigenvalues…, test_audit_tables_are_populated_and_self_consistent(), test_identifiability_labels_which_matrix_it_used(), test_rejected_acquisitions_are_recorded_not_just_counted() (+3 more)

### Community 69 - "_round_metrics"
Cohesion: 0.25
Nodes (8): blind_rmse(), _entropy(), _param_rows(), ndarray, Blind predictive RMSE of the REACTOR state (transport correction is an…, Per-parameter posterior reporting (#identifiability): estimate, scaled sigma,…, Per-round metric rows + per-parameter rows for one campaign (hidden truth used…, _round_metrics()

### Community 70 - "Literature-anchored kinetic parameter provenance"
Cohesion: 0.40
Nodes (5): Berthelot & Péan de Saint-Gilles (1862) esterification equilibrium, A. J. Kirby, Comprehensive Chemical Kinetics Vol. 10, Literature-anchored kinetic parameter provenance, Ethyl acetate + NaOH conductometric saponification benchmarks, Statistical factors for equivalent acetate groups

### Community 71 - "._through_line"
Cohesion: 0.29
Nodes (3): Propagator, Composition arriving at the NMR cell for a sample drawn at z. Applies (in…, (taus, weights) of the residence-time quadrature.

### Community 72 - "Per-run self-verification block (PASS/FAIL residuals)"
Cohesion: 0.50
Nodes (4): Legacy irreversible limit as verification reference, Coupled equilibrium solver (Gauss–Seidel + Brent), Linear conservation invariants, Per-run self-verification block (PASS/FAIL residuals)

### Community 73 - "last_valid_rows"
Cohesion: 0.31
Nodes (9): _boot_ci(), last_valid_rows(), paired_comparison(), One row per SEED: that seed's LAST COMPLETED round. Using the per-seed last…, Last-valid-round distributional summary per strategy: median, IQR, mean,…, Common-random-number PAIRED comparison of two strategies at the final round:…, summarize_final(), A seed that stops early keeps its LAST VALID round in the summary (n_seeds… (+1 more)

### Community 74 - ".concentrations_at"
Cohesion: 0.13
Nodes (10): ArrheniusStep, k(T) = A * exp(-Ea / (R T)) with A in L/(mol s) and Ea in J/mol., nu_matrix(), ndarray, Stoichiometric matrix of the chosen catalyst system., Fractional EGDA conversion X(x)., ndarray, Concentrations (mol/L) at axial positions z_m, flattened species-major: y[i*Nz… (+2 more)

### Community 75 - "audit_export.py"
Cohesion: 0.13
Nodes (27): blind_prediction_rows(), calibration_rows(), collect_campaign(), design_history_rows(), _empty(), empty_bundle(), _f(), governor_rows() (+19 more)

### Community 76 - "run_case"
Cohesion: 0.40
Nodes (5): CaseOutcome, main(), Everything one base-case run produces., Simulate one configuration and write its hyperparameter-tagged folder., run_case()

### Community 78 - "_scoring_bridge"
Cohesion: 0.50
Nodes (4): The same model configuration in a different reactor - used to move a LEARNED…, Bridge used for BLIND SCORING: identical object when geometry optimization is…, _rebridge(), _scoring_bridge()

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
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

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
- **Why does `OperatingConditions` connect `OperatingConditions` to `ndarray`, `sdl/reporting.py`, `literature_guess`, `Layer1Bridge`, `benchmark.py`, `SpectralFitter`, `test_acquisition.py`, `test_design_space.py`, `AdvancedVirtualLaboratory`, `run_one_campaign`, `ReactorGeometry`, `run_sdl_campaign.py`, `AcquisitionSettings`, `main`, `.run_profile`, `Measurement`, `AdvancedSelector`, `MBDoESelector`, `.concentrations_at`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._