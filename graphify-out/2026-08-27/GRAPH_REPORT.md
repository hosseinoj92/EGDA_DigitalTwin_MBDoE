# Graph Report - EGDA_DigitalTwin_MBDoE  (2026-08-26)

## Corpus Check
- 131 files · ~777,632 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2376 nodes · 6093 edges · 97 communities (89 shown, 8 thin omitted)
- Extraction: 91% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 516 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `66a833bf`
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
- campaign_figures.py
- plotting.py
- .covariance
- batch_simulation.py
- pfr_twin/__init__.py
- OperatingConditions
- efficiency.py
- Codex Graphify Feature Set
- run_advanced_campaign.py
- test_audit_regression.py
- Claude Graphify Feature Set
- PFR digital twin layer README
- A/B/C/D four-strategy showcase
- physics.py
- Line
- Detection, Cache and Update Flow
- Extraction Spec and Honesty Rules
- sim_nmr(2).py
- campaign_export.py
- _TextProgress
- benchmark_figures.py
- AuditRecorder
- benchmark_export.py
- ParameterSpace
- Batch Results Analysis CLI
- AdequacyGovernor
- AcquisitionSettings
- test_design_space.py
- Build, Cluster and Export Steps
- Codex Subagent Dispatch
- Auto-Rebuild Watch and Commit Hooks
- Graphify Workflow Policy
- Query, Path and Explain Flows
- NMRSimulator
- test_parallel.py
- BatchSweep Package Init
- sdl_advanced/__init__.py
- sdl_advanced/reporting.py
- _resource_lambdas
- controller.py
- io.py
- sdl/__init__.py
- test_analysis.py
- SpatialDesigner
- test_comparison.py
- main
- BaselineLabAdapter
- test_benchmark_report.py
- SpatialDesignConfig
- campaign_task
- build_report
- apply_config
- MBDoESelector
- _nu
- .run_profile
- test_each_runner_owns_its_knobs_independently
- QCGateConfig
- AdvancedSelector
- evaluate
- features.py
- _round_metrics
- Literature-anchored kinetic parameter provenance
- test_apply_config_is_strict_about_typos
- run_simulation.py
- last_valid_rows
- KineticModel
- audit_export.py
- benchmark.py
- test_calibration_governor.py
- test_features.py
- _check_magnitudes
- apply
- ReactorGeometry
- test_campaign_report.py
- run_temperature_study.py
- run_scenario
- PFRResult
- test_open_tube_ratio_is_linear_in_flow_and_bore_free
- benchmark_html.py
- .predict
- _set_dc
- ResourceMeter
- test_open_tube_bodenstein_approaches_48_over_the_radial_ratio
- test_packed_bed_is_checked_not_assumed
- _refresh_faults
- _UStub
- Feature
- _h_validity

## God Nodes (most connected - your core abstractions)
1. `OperatingConditions` - 126 edges
2. `Layer1Bridge` - 111 edges
3. `main()` - 96 edges
4. `AcquisitionSettings` - 67 edges
5. `NoiseModel` - 66 edges
6. `ModelEnsemble` - 63 edges
7. `InferenceModel` - 61 edges
8. `NMRSimulator` - 60 edges
9. `ParameterSpace` - 59 edges
10. `AdvancedVirtualLaboratory` - 58 edges

## Surprising Connections (you probably didn't know these)
- `graphify Pipeline (Codex)` --semantically_similar_to--> `graphify Pipeline (Claude Code)`  [INFERRED] [semantically similar]
  .codex/skills/graphify/SKILL.md → .claude/skills/graphify/SKILL.md
- `Extraction Subagent Prompt (Compact)` --semantically_similar_to--> `Extraction Subagent Prompt`  [INFERRED] [semantically similar]
  .codex/skills/graphify/references/extraction-spec.md → .claude/skills/graphify/references/extraction-spec.md
- `Coupled equilibrium solver (Gauss–Seidel + Brent)` --implements--> `equilibrium_state()`  [EXTRACTED]
  README.md → PFR_H2SO4_digital_twin/pfr_twin/analytical.py
- `Truth/inference firewall` --rationale_for--> `VirtualLaboratory`  [EXTRACTED]
  README.md → SDL_MBDoE/sdl/truth.py
- `Codex spawn_agent Dispatch` --semantically_similar_to--> `Parallel Subagent Chunk Dispatch`  [INFERRED] [semantically similar]
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

## Communities (97 total, 8 thin omitted)

### Community 0 - "pipeline.py"
Cohesion: 0.12
Nodes (34): _coverage(), _invalid_records(), Any, Path, run_analysis(), progress(), Small tqdm wrapper with a no-dependency text fallback., Return tqdm when installed, otherwise a basic percentage reporter. (+26 more)

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
Cohesion: 0.08
Nodes (24): LaplacePosterior, ndarray, Laplace-approximate Bayesian posterior for ONE kinetic-model hypothesis.…, Per-parameter Gaussian posterior mass lying OUTSIDE the box - the diagnostic…, n draws from the Laplace Gaussian PROPERLY truncated to the box. Strategy:…, covariance_from_fim(), InferenceModel, ndarray (+16 more)

### Community 5 - "Design Coverage and Damkohler Figures"
Cohesion: 0.10
Nodes (30): axial_egma_peaks.csv (peak dataset), Figure: Axial EGMA Intermediate Maxima (H2SO4 vs NaOH), Reactor Geometry A, Reactor Geometry B, H2SO4 Catalyst Branch, Finding: H2SO4 peaks pinned at outlet, NaOH peaks interior, NaOH Catalyst Branch, Peak EGMA Yield (+22 more)

### Community 6 - "build_readme_figures.py"
Cohesion: 0.23
Nodes (25): axial_egma_peaks(), consolidated_scenarios(), convert(), data_coverage(), derived_metrics(), duplicate_configs(), excluded_or_invalid_scenarios(), geometry_collapse_metrics() (+17 more)

### Community 7 - "sdl/reporting.py"
Cohesion: 0.13
Nodes (32): campaign_history.csv per-round record, final_report.txt human-readable campaign summary, main(), StrategyResult, Short name of the scaled theta component for a natural key., theta_component_name(), campaign_score_pct(), log_mean_rel_error_pct() (+24 more)

### Community 8 - "self_test.py"
Cohesion: 0.10
Nodes (28): Truth/inference firewall, Truth-only systematic effects (transfer_time_s, calibration_gain), build_fixed_design(), Conventional campaign: temperature ladder at nominal flow/catalyst. `budget`…, _make_loop(), _ports(), Layer 2 self-tests. Pytest-compatible (plain test_* functions with asserts),…, The closed loop must never read the hidden parameters. (+20 more)

### Community 9 - "campaign_figures.py"
Cohesion: 0.10
Nodes (49): Every figure of the campaign, in `figures/`. Each builder is handed the…, _write_figures(), _clip_ci(), figure_concentration_profiles(), figure_conditions(), figure_correlation_matrices(), figure_design_decisions(), figure_governor() (+41 more)

### Community 10 - "plotting.py"
Cohesion: 0.14
Nodes (28): run_config.json + profiles.csv as the analysis input contract, _end_label(), _legend(), _new_axes(), plot_concentration_profiles(), plot_conversion_yield(), plot_profile_overlay(), plot_scenario_bars() (+20 more)

### Community 12 - "batch_simulation.py"
Cohesion: 0.09
Nodes (36): BatchSweep Analysis methods and interpretation README, Read-only post-processing layer over saved sweeps, _fmt_secs(), main(), _progress(), BATCH base-case runs of the PFR digital twin. Same physics and outputs as…, Yield items with a tqdm-style progress bar (count, %, elapsed, ETA). Uses tqdm…, Simulate every scenario, write per-scenario folders and the summary. (+28 more)

### Community 13 - "pfr_twin/__init__.py"
Cohesion: 0.06
Nodes (44): pfr_twin - 1D deterministic digital twin of an isothermal plug flow reactor for…, Kinetic model of the two-step series ester cleavage, per catalyst system. Acid…, bisulfate_equilibrium(), mix_streams(), Ideal micromixer model. Stream 1 (aqueous EGDA) and Stream 2 (aqueous catalyst:…, One feed stream to the micromixer. composition : mol/L of *solutes* (any of…, [H+] for total sulfate molarity c_total, ideal activities (back-compat alias…, Flow-weighted ideal blending of the two feed streams. T_K is the (isothermal)… (+36 more)

### Community 14 - "OperatingConditions"
Cohesion: 0.04
Nodes (88): noise_true vs noise_assumed misspecification study hook, Recommended study extensions (Monte Carlo, cost-aware, ablation), GovernorConfig, Model-inadequacy governor: distinguishes "my parameters are uncertain" from "my…, _combine_positions(), Rebuild one species-major Measurement from per-position parts., AssumedTransfer, build_egda_family() (+80 more)

### Community 15 - "efficiency.py"
Cohesion: 0.09
Nodes (35): _conc_bin_label(), nmr_performance_rows(), Deconvolution behaviour by species and concentration regime. NOTE ON WHAT IS…, median / IQR / bootstrap CI of the median, under one column prefix. The…, _stat_block(), _agg(), _at_or_before(), budget_to_target_rows() (+27 more)

### Community 16 - "Codex Graphify Feature Set"
Cohesion: 0.12
Nodes (16): URL Ingest via /graphify add (Codex), Folder Watch Auto-Rebuild (Codex), FalkorDB Cypher Export (Codex), graphify MCP stdio Server (Codex), Neo4j Cypher Export (Codex), GitHub Repo Clone (Codex), Cross-Repo Graph Merge (Codex), Native CLAUDE.md Integration (Codex) (+8 more)

### Community 17 - "run_advanced_campaign.py"
Cohesion: 0.15
Nodes (16): main(), Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling…, # NOTE: with this on, blind RMSE is computed in the CHOSEN reactor, so, # NOTE: the shipped 20 cm OPEN tube FAILS this at every design flow, Resolve the output directory, refusing to overwrite a completed run. An…, The spatial policy this strategy actually ran, resolved the same way…, (u, z, species) -> the hidden TRUE reactor composition. POST-CAMPAIGN ONLY. It…, Every machine-readable table of the campaign, in `data/`. The audit tables come… (+8 more)

### Community 18 - "test_audit_regression.py"
Cohesion: 0.14
Nodes (21): _compare(), _first_difference(), Regression guard for the publication audit trail. THE CLAIM UNDER TEST: turning…, A-D run unchanged sdl.campaign code and are audited entirely post-campaign, so…, E adds spatial optimization and per-round timing calls., The one that matters: F exercises the EIG selector (RNG), the QC gate and the…, S3 turns on the NMR pathway, the transfer line and the QC gate, so the…, S5 removes the correct model, so the governor fires and the selector switches… (+13 more)

### Community 19 - "Claude Graphify Feature Set"
Cohesion: 0.18
Nodes (15): /graphify Trigger Registration, FalkorDB Cypher Export, graphify MCP stdio Server, Neo4j Cypher Export, GitHub Repo Clone, Cross-Repo Graph Merge, Native CLAUDE.md Integration, BFS and DFS Traversal Modes (+7 more)

### Community 20 - "PFR digital twin layer README"
Cohesion: 0.17
Nodes (15): Contrast with the packed-bed Amberlyst twin, PFR digital twin layer README, Layer 1 Python dependencies (numpy, scipy, matplotlib), Bisulfate catalyst speciation ([H+] from HSO4-/SO4 2-), EGDA Digital Twin & Self-Driving Laboratory framework, Hovey & Hepler (1990) bisulfate second-dissociation thermochemistry, Temperature-dependent Ka2 (Clarke–Glew constant-dCp), Layer 1 — deterministic PFR digital twin (+7 more)

### Community 21 - "A/B/C/D four-strategy showcase"
Cohesion: 0.13
Nodes (15): Nearest-Damköhler geometry matching diagnostic, Local elasticities on the Arrhenius 1/T coordinate, What can and cannot be concluded from the sweeps, A/B/C/D four-strategy showcase, Synthetic CPR-NMR heteroscedastic correlated noise model, Fisher Information Matrix and Cramér–Rao bound, Franceschini & Macchietto (2008) MBDoE review, D-optimal Model-Based Design of Experiments (+7 more)

### Community 22 - "physics.py"
Cohesion: 0.12
Nodes (21): assign_regime(), axial_peak(), enrich(), _kinetic_constants(), Any, Read the current simulator constants without modifying or running it., water_density_g_L(), water_viscosity_Pa_s() (+13 more)

### Community 23 - "Line"
Cohesion: 0.11
Nodes (21): first_order_multiplet(), Line, _noise_grid_factor(), ndarray, Std-dev change caused by RESAMPLING the FFT-bin noise onto the display grid,…, Is this effect simulated? `enabled` is the master switch, the per-effect gate…, What this instrument actually simulates - for the run record., One acquisition's random draw of the nuisance parameters. (+13 more)

### Community 24 - "Detection, Cache and Update Flow"
Cohesion: 0.21
Nodes (13): URL Ingest via /graphify add, Token Reduction Benchmark, Monorepo Subfolder Extraction Flow, Whisper Video and Audio Transcription, Post-Update Graph Diff, Incremental --update Flow, Corpus Size Gate and Narrowing Prompt, Corpus File Detection (Step 2) (+5 more)

### Community 25 - "Extraction Spec and Honesty Rules"
Cohesion: 0.19
Nodes (13): Confidence Score Rubric, DEEP_MODE Aggressive Inference, Hyperedge Extraction Rule, Node ID Format Rule, Semantic Similarity Edge Rule, source_file Verbatim Rule, Extraction Subagent Prompt, Image Vision Extraction Rules (+5 more)

### Community 26 - "sim_nmr(2).py"
Cohesion: 0.07
Nodes (60): area_under_curve(), averaged_exchange_peak(), build_group_records(), build_species_records(), build_spectrum(), concentrations_at(), _draw_labels(), emit_zooms() (+52 more)

### Community 27 - "campaign_export.py"
Cohesion: 0.11
Nodes (36): _assimilated(), CampaignRecord, concentration_rows(), _corr_max_offdiag(), export_spectra(), _f(), _join(), measurement_rows() (+28 more)

### Community 28 - "_TextProgress"
Cohesion: 0.33
Nodes (3): Any, Minimal progress reporter used only when tqdm is unavailable., _TextProgress

### Community 29 - "benchmark_figures.py"
Cohesion: 0.11
Nodes (44): figure_design_by_round(), figure_design_distribution(), figure_design_joint(), figure_matrix(), figure_model_discrimination(), figure_nmr_performance(), figure_overview_accuracy(), figure_paired_seeds() (+36 more)

### Community 30 - "AuditRecorder"
Cohesion: 0.12
Nodes (9): AuditRecorder, Passive audit recorder for the publication workflow. DESIGN RULE, and the whole…, `curve` is `SpatialDesigner.last_selection`: the marginal log-det gain the…, `part` is the controller's per-position view of one acquisition: {"z", "y",…, Whole-profile convenience for the ungated (direct-observation) path, where…, Wall-clock only. Reading a clock cannot change a result, and these columns are…, Picklable primitives only, for the trip back from a worker., Append-only sink. Holds plain Python/NumPy scalars so the payload is cheap to… (+1 more)

### Community 31 - "benchmark_export.py"
Cohesion: 0.14
Nodes (33): _condition_rows(), design_by_round_rows(), design_selection_rows(), _f(), _final_per_seed(), _finite(), master_summary_rows(), matrix_rows() (+25 more)

### Community 32 - "ParameterSpace"
Cohesion: 0.09
Nodes (19): check_truth_in_domain(), _param_rows(), Is every hidden true parameter inside the candidate model's domain? Returns a…, Per-parameter posterior reporting (#identifiability): estimate, scaled sigma,…, ParameterSpace, ndarray, Estimated components merged with the held-fixed ones, so the forward model…, Keys whose estimate is resting on its box constraint. A bounded least-squares… (+11 more)

### Community 33 - "Batch Results Analysis CLI"
Cohesion: 0.31
Nodes (8): main(), parse_args(), load_config(), _merge(), Any, Path, Large-sweep storage/detail degradation strategy, Namespace

### Community 34 - "AdequacyGovernor"
Cohesion: 0.15
Nodes (9): AdequacyGovernor, ndarray, phi = r_w' r_w / dof, the factor by which the residuals exceed the size the…, Max standardized mean residual over (experiment x species) CELLS, Sidak-…, (component p-values, combined Sidak min-p, species bias, chi2/dof score, pooled…, THE single definition of which diagnostics enter the decision. Used identically…, Sidak-combined min-p over the DECISION components., B must satisfy 1/(B+1) <= alpha or the bootstrap p-value can never reach the… (+1 more)

### Community 35 - "AcquisitionSettings"
Cohesion: 0.04
Nodes (57): AcquisitionSettings, flow_response(), Reusable 1H NMR forward model of the EGDA hydrolysis mixture at 80 MHz.…, SW = (ppm window) x (spectrometer frequency)., Complex dwell = 1 / SW., Number of COMPLEX FID points actually sampled., What the instrument really spends: N_acquired x dwell. Differs from…, FFT length >= acquired points; default is the next power of two (zero filling,… (+49 more)

### Community 36 - "test_design_space.py"
Cohesion: 0.09
Nodes (38): Bounded continuous Powell refinement of the best candidate, Measurement object (condition, ports, species, noisy values), OperatingConditions experiment record, build_candidates(), Experiment design: fixed (conventional) designs and autonomous MBDoE. Fixed…, Full-factorial candidate grid over the feasible design space., bounds_vector(), DesignResolution (+30 more)

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

### Community 42 - "NMRSimulator"
Cohesion: 0.05
Nodes (61): _figure_recovery(), Truth vs deconvolved concentration over random compositions. Instrument-level…, generate(), ndarray, Three deterministic representative NMR examples for the publication figures.…, (label, ppm, observed, fitted, residual, components) per example., Per-species (plus pool and baseline) contribution to the FITTED spectrum.…, Simulate, deconvolve and export the three examples. Returns one summary row per… (+53 more)

### Community 43 - "test_parallel.py"
Cohesion: 0.12
Nodes (25): ProcessPoolExecutor, describe_workers(), make_executor(), ordered_map(), pin_numerical_threads(), Cross-platform, determinism-preserving process parallelism for the benchmark.…, Apply `fn(*args)` to every tuple, returning results in SUBMISSION order. `fn`…, Pin every numerical backend to `n_threads`. Call this BEFORE importing… (+17 more)

### Community 45 - "sdl_advanced/__init__.py"
Cohesion: 0.06
Nodes (49): Propagator, make_lab(), The line THIS scenario runs, built from the CURRENT global configuration plus…, The hidden truth for this scenario. MODEL_MISMATCH['truth_parameter_bias'] is…, ScenarioSpec, sdl_advanced - Layer 2+ : realistic CPR + Fourier-80 virtual instrument and…, AdvancedVirtualLaboratory, InstrumentConfig (+41 more)

### Community 46 - "sdl_advanced/reporting.py"
Cohesion: 0.09
Nodes (40): _csv(), figure_a_spatial_value(), figure_b_position_rounds(), figure_c_spectrum(), figure_convergence_band(), figure_d_truth_vs_recovered(), figure_design_trajectory(), figure_e_convergence() (+32 more)

### Community 47 - "_resource_lambdas"
Cohesion: 0.50
Nodes (4): The S6 lambda sweep: one base weight vector x a scale factor. The base values…, _resource_lambdas(), One information-resource exchange rate for the whole framework: the sizing…, test_sizing_lambdas_are_the_s6_exchange_rate()

### Community 48 - "controller.py"
Cohesion: 0.15
Nodes (25): Exception, AdequacyReport, GovernorState, AdvancedDesignConfig, DesignDecision, NoiseSurrogate, Bayesian expected-information-gain (EIG) active learning with a FIM pre-screen…, Expected observation-covariance model LEARNED from the campaign's own… (+17 more)

### Community 49 - "io.py"
Cohesion: 0.25
Nodes (16): configuration_key(), _csv_value(), discover(), flatten_run_config(), _number(), Any, Path, read_profile() (+8 more)

### Community 50 - "sdl/__init__.py"
Cohesion: 0.10
Nodes (28): The inverse problem — kinetics from noisy measurements, Reference-temperature (k_ref, Ea) reparameterization, Seven-step self-driving closed loop, Layer 2 showcase: virtual self-driving laboratory around the Layer 1 PFR twin.…, resolve_outdir(), Closed-loop campaign runner - the "self-driving" part. For one strategy the…, RoundRecord, run_strategy() (+20 more)

### Community 51 - "test_analysis.py"
Cohesion: 0.21
Nodes (7): pareto_front(), Find exact fronts for small studies and epsilon fronts for large ones. Exact…, AnalysisTests, Path, sample_payload(), sample_profile(), write_scenario()

### Community 52 - "SpatialDesigner"
Cohesion: 0.17
Nodes (12): _logdet_floored(), ndarray, Spatial measurement design for the moving-capillary CPR. The sampling position…, (y (n_species,), S (n_species x p)) linearly interpolated at z., Chooses sampling positions for one operating condition. cov_builder(y_at_z) ->…, Full profile for one condition, according to cfg.mode., Adaptive-sequential step: best next z given positions already measured at this…, Deterministic cyclic coordinate polish of the selected positions on the… (+4 more)

### Community 53 - "test_comparison.py"
Cohesion: 0.13
Nodes (21): active_geometry(), geometry_sizing_table(), Every candidate the sizing considered, with the decomposed objective (info,…, The reactor this campaign runs in: the declared GEOMETRY, or the prior-optimal…, Conventional-vs-optimized comparison, and reactor geometry as an optional…, With the resource penalty OFF the objective is monotone in information and runs…, theta is intrinsic: c(tau) never depends on which tube produced the data, so…, Sizing a reactor happens BEFORE the kinetics are known; reading the hidden… (+13 more)

### Community 54 - "main"
Cohesion: 0.09
Nodes (29): _finals(), git_provenance(), main(), _mean_curves(), prepare_layout(), Main EGDA advanced benchmark (corrected framework, v3 outputs). Runs the…, Create the subdirectories and return {key: absolute path}., Where this run writes - and a refusal to overwrite anything else. A completed… (+21 more)

### Community 55 - "BaselineLabAdapter"
Cohesion: 0.11
Nodes (18): BaselineLabAdapter, Presents AdvancedVirtualLaboratory as the legacy VirtualLaboratory so…, DESIGN-TIME predictor of the deconvolution covariance for a CANDIDATE…, No-op: this model is analytic, not data-fitted (interface parity with…, SpectralCovarianceModel, _calibration(), coverage_gate(), Priority-1 tests: ONE public NMR calibration artifact shared by the measurement… (+10 more)

### Community 56 - "test_benchmark_report.py"
Cohesion: 0.14
Nodes (22): paired_seed_rows(), Transport distortion vs quantification error, aggregated by species. SIMULATION…, EVERY seed's paired difference against its scenario's reference strategy, not…, transfer_decomposition_summary_rows(), reference_strategy(), _first_difference(), Regression guard for the benchmark's run-level summary. THE CLAIM UNDER TEST,…, A ten-position profile chooses ONE operating condition, not ten, and weighting… (+14 more)

### Community 57 - "SpatialDesignConfig"
Cohesion: 0.18
Nodes (17): _adaptive_profile_bayes(), _field_for_model(), Sensitivity field of the model's EXPECTED OBSERVATION at u., TRULY data-adaptive sequential axial sampling: choose z -> acquire NMR ->…, SpatialDesignConfig, _field_and_designer(), Tests of optimal spatial sampling (sdl_advanced.spatial_design). Runnable…, TRUE closed-loop requirement: changing the FIRST measured result must be able… (+9 more)

### Community 58 - "campaign_task"
Cohesion: 0.12
Nodes (15): campaign_task(), The same model configuration in a different reactor - used to move a LEARNED…, Bridge used for BLIND SCORING: identical object when geometry optimization is…, ONE campaign, as a picklable pure function of its four labels. This is the unit…, _rebridge(), _scoring_bridge(), The EIG is Monte-Carlo and consumes the selector's RNG. The audit may report…, A QC-rejected spectrum never reaches the posterior, so it exists in no… (+7 more)

### Community 59 - "build_report"
Cohesion: 0.47
Nodes (5): build_report(), _fmt(), Any, Path, Independent regime flags and primary regime priority

### Community 60 - "apply_config"
Cohesion: 0.12
Nodes (31): apply_config(), assert_reactor_validity(), invalidate_caches(), Refuse a direct assignment to a feature-derived field. `replay=True` (the call…, Apply a runner's CONFIG knobs to this module's configuration blocks. The…, Drop every configuration-derived cache. A cache keyed on the configuration is…, Every knob's CURRENT value - what the run actually used. Includes the DERIVED…, Apply VALIDITY['policy'] to the reactor in use, over the WHOLE design envelope.… (+23 more)

### Community 61 - "MBDoESelector"
Cohesion: 0.25
Nodes (6): MBDoESelector, ndarray, Bounds in canonical order. A DEGENERATE dimension (lo == hi) is accepted and…, Design score with FLOORED eigenvalues. `slogdet` returns -inf for any singular…, The hybrid selector must improve on its coarse seed without leaving the user-…, test_continuous_design_refines_inside_bounds()

### Community 62 - "_nu"
Cohesion: 0.20
Nodes (10): _h_baseline(), _h_broadening(), _h_correlated_noise(), _h_gain(), _h_lineshape_mismatch(), _h_phase(), _h_response_calibration(), _h_shift() (+2 more)

### Community 63 - ".run_profile"
Cohesion: 0.14
Nodes (9): ndarray, Hidden true composition (ALL Layer-1 species) at each z., Batch-reaction propagator at the transfer-line temperature, closed over the…, Set condition u, sample the requested positions in the given order (one moving…, Legacy-style observation: concentrations + NoiseModel noise. cov_y stays None…, Gross, QC-DETECTABLE corruption of one acquisition. A rolling artifact spanning…, UNDETECTABLE quantification outliers: displace a species by many CLAIMED sigmas…, Spectrum -> deconvolution. The fitter sees only the spectrum. (+1 more)

### Community 64 - "test_each_runner_owns_its_knobs_independently"
Cohesion: 0.40
Nodes (5): _load_runner(), The two entry points hold SEPARATE knob blocks and neither imports the other,…, The point of the CONFIG block is that a user can reach EVERY knob from one…, test_each_runner_owns_its_knobs_independently(), test_runner_knobs_cover_every_overridable_block()

### Community 65 - "QCGateConfig"
Cohesion: 0.10
Nodes (32): measure_with_qc(), _qc_failed(), qc_fault_verdict(), QCGateConfig, QCMonitor, Per-campaign memory of acquisition dispositions (rules 3 and 4). Deliberately…, Per-position view of a species-major Measurement., Apply the four gate rules (see QCGateConfig) and say WHICH one fired. Separated… (+24 more)

### Community 66 - "AdvancedSelector"
Cohesion: 0.12
Nodes (15): AdvancedSelector, expected_information_gain(), _logdet_floored(), ndarray, Sigma for ONE position's species vector., Species-major covariance for a whole profile (block per z)., (EIG_total, EIG_model) in nats, from cached particle predictions. preds: (N,…, Hierarchical (u, Z) selector for strategy F. (+7 more)

### Community 67 - "evaluate"
Cohesion: 0.15
Nodes (26): evaluate(), explain(), _geom(), is_feasible(), max_admissible_flow_mL_min(), min_admissible_length_m(), Plug-flow validity of a reactor OVER ITS WHOLE OPERATING ENVELOPE. WHY THIS…, Full plug-flow diagnosis of ONE geometry at ONE total flow. Returns a flat dict… (+18 more)

### Community 68 - "features.py"
Cohesion: 0.10
Nodes (8): _chem(), _h_activity(), _h_ka2(), _h_reversible(), _h_speciation(), _h_tdep_equilibrium(), _h_tdep_kinetics(), CENTRAL BOOLEAN FEATURE CONTROL - the one place that says what is switched on.…

### Community 69 - "_round_metrics"
Cohesion: 0.29
Nodes (7): blind_rmse(), _entropy(), ndarray, Blind predictive RMSE of the REACTOR state (transport correction is an…, Per-round metric rows + per-parameter rows for one campaign (hidden truth used…, _round_metrics(), _truth_prediction()

### Community 70 - "Literature-anchored kinetic parameter provenance"
Cohesion: 0.40
Nodes (5): Berthelot & Péan de Saint-Gilles (1862) esterification equilibrium, A. J. Kirby, Comprehensive Chemical Kinetics Vol. 10, Literature-anchored kinetic parameter provenance, Ethyl acetate + NaOH conductometric saponification benchmarks, Statistical factors for equivalent acetate groups

### Community 71 - "test_apply_config_is_strict_about_typos"
Cohesion: 0.33
Nodes (4): A silently-ignored knob is indistinguishable from a knob that had no effect;…, test_apply_config_is_strict_about_typos(), Outside the radially-mixed regime the Taylor-Aris D_ax is meaningless. It must…, test_taylor_aris_bodenstein_is_not_reported_where_it_does_not_apply()

### Community 72 - "run_simulation.py"
Cohesion: 0.08
Nodes (38): analytical_profiles(), _bracketed_root(), equilibrium_state(), max_relative_error(), ndarray, Algebraic reference solutions used to verify the numerical integrator. 1.…, Composition at simultaneous chemical equilibrium of both steps. Solves for the…, Largest |numerical - analytical| across species, relative to `scale`. (+30 more)

### Community 73 - "last_valid_rows"
Cohesion: 0.31
Nodes (9): _boot_ci(), last_valid_rows(), paired_comparison(), One row per SEED: that seed's LAST COMPLETED round. Using the per-seed last…, Last-valid-round distributional summary per strategy: median, IQR, mean,…, Common-random-number PAIRED comparison of two strategies at the final round:…, summarize_final(), A seed that stops early keeps its LAST VALID round in the summary (n_seeds… (+1 more)

### Community 74 - "KineticModel"
Cohesion: 0.23
Nodes (6): KineticModel, kappa_i = k_i(T) * c_cat, the forward time-scale constants. c_cat is [H+] on…, Net rates (positive = ester-cleavage direction) for the state vector c in…, ndarray, Concentrations (mol/L) at axial positions z_m, flattened species-major: y[i*Nz…, Advance each position's composition by dt_s of batch reaction (the batch time…

### Community 75 - "audit_export.py"
Cohesion: 0.12
Nodes (29): blind_prediction_rows(), calibration_rows(), collect_campaign(), design_history_rows(), _empty(), empty_bundle(), _f(), governor_rows() (+21 more)

### Community 76 - "benchmark.py"
Cohesion: 0.05
Nodes (64): _figure_spatial_value(), True profile + equal vs optimized positions + information density. A REFERENCE…, assumed_noise(), _assumed_transfer_from(), campaign_cost_units(), continuous_kwargs(), derive_allowance(), design_for_budget() (+56 more)

### Community 77 - "test_calibration_governor.py"
Cohesion: 0.17
Nodes (15): _calibrated_fitter(), Stage-1 regression tests for: NMR calibration/validation independence and PSD…, assess(), the analytical combination and the bootstrap must all use the SAME…, B must be able to resolve alpha: 1/(B+1) <= alpha, else reject., Cheap check (B kept small via an explicit large alpha): the returned p is a…, The validation spectra must not be the calibration spectra: the calibration RNG…, Sigma_eff = Sigma_fit + Sigma_empirical; the ASSUMED surrogate floor terms must…, _small_ensemble() (+7 more)

### Community 78 - "test_features.py"
Cohesion: 0.09
Nodes (22): fitter_kwargs(), The quantification error-model terms the fitter reports in Sigma_y. With…, FaultModel, TRUTH-side hardware failures and quantification outliers. Two DELIBERATELY…, Central Boolean feature control. The contract these tests defend: * ONE switch…, With the noise gate off (and nothing else random left on), repeated…, Gate off == that effect absent, bit for bit. Compared against a nuisance whose…, REGRESSION: the scenarios used to CAPTURE a TransferConfig at import, so a… (+14 more)

### Community 79 - "_check_magnitudes"
Cohesion: 0.67
Nodes (3): _check_magnitudes(), _lookup(), A feature declared ON whose magnitude is zero is a lie in the run record: it…

### Community 80 - "apply"
Cohesion: 0.18
Nodes (17): apply(), _apply_mismatch(), cascade(), mismatch_defaults(), Any, Route the switches into the configuration blocks of `ns`. Called at the END of…, Split TRUTH_CHEMISTRY from INFERENCE_CHEMISTRY where asked to. Nothing here…, The COMPLETE feature state, for the run record. Every switch appears with its… (+9 more)

### Community 81 - "ReactorGeometry"
Cohesion: 0.07
Nodes (21): flow_diagnostics(), Plug-flow validity diagnostics. A digital twin should say when its own…, Vogel-type correlation for liquid water, valid ~273-373 K., water_density_g_L(), water_viscosity_Pa_s(), InletState, Mixed-cup state leaving the micromixer = PFR inlet (x = 0)., Inlet concentration of the rate-driving species: [H+] on the acid route, [OH-]… (+13 more)

### Community 82 - "test_campaign_report.py"
Cohesion: 0.15
Nodes (20): Reactor sampling point -> NMR cell -> reported concentration, per acquisition…, transfer_rows(), Regression guard for the per-campaign scientific record. THE CLAIM UNDER TEST,…, F is the one that matters: it exercises the EIG selector's RNG, the QC gate and…, The control: D runs unchanged sdl.campaign code, so this must pass trivially -…, The information curve is KEPT from the greedy step, not recomputed. Its…, The decomposition must ADD UP: reactor -> cell -> reported., The firewall: nothing may ask the laboratory for truth while it is still… (+12 more)

### Community 83 - "run_temperature_study.py"
Cohesion: 0.15
Nodes (21): main(), BATCH temperature studies of the PFR digital twin. Same physics and outputs as…, Index table plus the cross-scenario comparison figures (each + CSV)., Sweep every scenario, write per-scenario folders and the summary., run_batch(), _write_summary(), Write named equal-length numeric columns as a headed CSV., Write heterogeneous rows (numbers and strings) as a headed CSV. (+13 more)

### Community 84 - "run_scenario"
Cohesion: 0.13
Nodes (17): merge(), Returns (round rows, per-parameter rows, per-campaign status rows). NO campaign…, run_scenario(), runtime_s measures the RUN, not the chemistry: it is the one field a worker…, Plain `==` is unusable here: legitimate NaNs (p_correct for a non-Bayesian…, Guard the guard: the NaN-tolerant comparator must not be so forgiving that the…, Only primitives may cross the process boundary - never a laboratory, a…, The whole point, end to end: a real registered scenario with all six of its… (+9 more)

### Community 85 - "PFRResult"
Cohesion: 0.20
Nodes (6): PFRResult, ndarray, Axial profiles plus the scalars needed to interpret them., Fractional EGDA conversion X(x)., Yield of EGMA or EG on a diol-backbone basis: (C_i - C_i0)/C_EGDA0., Outlet selectivity of EGMA among converted EGDA.

### Community 87 - "benchmark_html.py"
Cohesion: 0.27
Nodes (18): build_report(), derive_findings(), _pct(), The human-readable half of the benchmark: one self-contained HTML report. It is…, Write the benchmark report. Missing figures/files are skipped., Statements this run's data supports, each with its evidence. Returns dicts with…, _sc_title(), build_report() (+10 more)

### Community 88 - ".predict"
Cohesion: 0.31
Nodes (4): ndarray, The candidate's expected-observation operator - the ONE way any controller-side…, Current MAP if fitted, else the initial guess (for pre-data design)., Particle prediction through the candidate's expected-observation operator (NOT…

### Community 89 - "_set_dc"
Cohesion: 0.18
Nodes (11): _h_acq_time(), _h_fid(), _h_line_carryover(), _h_line_reaction(), _h_line_rtd(), _h_line_temperature(), _h_overlap(), _h_resource_aware() (+3 more)

### Community 90 - "ResourceMeter"
Cohesion: 0.10
Nodes (21): ndarray, Accumulates the campaign's physical cost from logged events., `enabled=False` is the FEATURE bypass for resource accounting…, Reactor condition set + stabilization to steady state. Idempotent for an…, Capillary move + flush + one NMR acquisition at position z. retry=True marks a…, A position whose data was rejected by the QC gate (not assimilated); auditable,…, Scalar penalty term of the resource-aware utility for a HYPOTHETICAL experiment…, ResourceEvent (+13 more)

### Community 96 - "_refresh_faults"
Cohesion: 0.50
Nodes (4): _h_instrument_faults(), _h_outliers(), Rebuild FAULTS from the two switches and the declared magnitudes. A probability…, _refresh_faults()

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
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

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
- **Why does `main()` connect `main` to `ParameterSpace`, `AcquisitionSettings`, `InferenceModel`, `last_valid_rows`, `NMRSimulator`, `audit_export.py`, `benchmark.py`, `test_parallel.py`, `OperatingConditions`, `efficiency.py`, `sdl_advanced/reporting.py`, `run_scenario`, `test_comparison.py`, `benchmark_html.py`, `test_benchmark_report.py`, `apply_config`, `benchmark_figures.py`, `benchmark_export.py`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._