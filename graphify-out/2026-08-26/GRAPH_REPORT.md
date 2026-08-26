# Graph Report - EGDA_DigitalTwin_MBDoE  (2026-08-26)

## Corpus Check
- 127 files · ~760,014 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2254 nodes · 5722 edges · 102 communities (96 shown, 6 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 514 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c71d3dc9`
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
- NoiseModel
- batch_temperature_study.py
- pfr_twin/__init__.py
- OperatingConditions
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
- campaign_export.py
- _TextProgress
- test_spectral.py
- AuditRecorder
- screen
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
- AcquisitionSettings
- sdl_advanced/reporting.py
- benchmark.py
- observability.py
- io.py
- sdl/__init__.py
- surrogate_validation
- SpatialDesignConfig
- test_truth_firewall.py
- audit_summary.py
- test_nmr_calibration.py
- main
- create_figures
- test_resource_accounting.py
- build_report
- apply_config
- test_deconvolution.py
- run_simulation.py
- .run_profile
- test_geometry_packing.py
- QCGateConfig
- .select
- evaluate
- features.py
- _round_metrics
- Literature-anchored kinetic parameter provenance
- ._through_line
- reactor.py
- last_valid_rows
- KineticModel
- audit_export.py
- main
- AdequacyGovernor
- test_features.py
- Layer1Bridge
- apply
- ReactorGeometry
- test_campaign_report.py
- run_temperature_study.py
- run_scenario
- PFRResult
- LaplacePosterior
- campaign_html.py
- .predict
- _set_dc
- ResourceEvent
- CompositionEnvelope
- nmr_examples.py
- total_cost_units
- derive_allowance
- governor_mc_validation
- _refresh_faults
- _UStub
- prepare_outdir
- Feature
- _h_validity
- .probs_reliable

## God Nodes (most connected - your core abstractions)
1. `OperatingConditions` - 126 edges
2. `Layer1Bridge` - 111 edges
3. `AcquisitionSettings` - 67 edges
4. `NoiseModel` - 66 edges
5. `ModelEnsemble` - 63 edges
6. `main()` - 62 edges
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

## Communities (102 total, 6 thin omitted)

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

### Community 4 - "InferenceModel"
Cohesion: 0.12
Nodes (15): The inverse problem — kinetics from noisy measurements, Reference-temperature (k_ref, Ea) reparameterization, Laplace-approximate Bayesian posterior for ONE kinetic-model hypothesis.…, covariance_from_fim(), InferenceModel, ndarray, Inference model: everything the (virtual) experimenter is allowed to know.…, Re-estimate theta from all accumulated data (warm start). (+7 more)

### Community 5 - "Design Coverage and Damkohler Figures"
Cohesion: 0.10
Nodes (30): axial_egma_peaks.csv (peak dataset), Figure: Axial EGMA Intermediate Maxima (H2SO4 vs NaOH), Reactor Geometry A, Reactor Geometry B, H2SO4 Catalyst Branch, Finding: H2SO4 peaks pinned at outlet, NaOH peaks interior, NaOH Catalyst Branch, Peak EGMA Yield (+22 more)

### Community 6 - "build_readme_figures.py"
Cohesion: 0.23
Nodes (25): axial_egma_peaks(), consolidated_scenarios(), convert(), data_coverage(), derived_metrics(), duplicate_configs(), excluded_or_invalid_scenarios(), geometry_collapse_metrics() (+17 more)

### Community 7 - "sdl/reporting.py"
Cohesion: 0.12
Nodes (29): campaign_history.csv per-round record, final_report.txt human-readable campaign summary, Short name of the scaled theta component for a natural key., theta_component_name(), campaign_score_pct(), log_mean_rel_error_pct(), mean_rel_error_pct(), _new_axes() (+21 more)

### Community 8 - "self_test.py"
Cohesion: 0.13
Nodes (25): Truth/inference firewall, Truth-only systematic effects (transfer_time_s, calibration_gain), build_candidates(), build_fixed_design(), Full-factorial candidate grid over the feasible design space., Conventional campaign: temperature ladder at nominal flow/catalyst. `budget`…, _make_loop(), _ports() (+17 more)

### Community 9 - "campaign_figures.py"
Cohesion: 0.10
Nodes (50): Every figure of the campaign, in `figures/`. Each builder is handed the…, _write_figures(), _clip_ci(), color_for(), figure_concentration_profiles(), figure_conditions(), figure_correlation_matrices(), figure_design_decisions() (+42 more)

### Community 10 - "plotting.py"
Cohesion: 0.18
Nodes (23): run_config.json + profiles.csv as the analysis input contract, _end_label(), _legend(), _new_axes(), plot_concentration_profiles(), plot_conversion_yield(), plot_profile_overlay(), plot_scenario_bars() (+15 more)

### Community 11 - "NoiseModel"
Cohesion: 0.20
Nodes (13): AssumedTransfer, INFERENCE-SIDE transfer knowledge: only COMMANDED / CALIBRATED quantities…, Back-compatible constructor for a plain mean-delay correction., InferenceModel whose expected-observation operator includes the…, TransportAwareInference, NoiseModel, ndarray, Tests of the common expected-observation operator (predict_at) and its use by… (+5 more)

### Community 12 - "batch_temperature_study.py"
Cohesion: 0.11
Nodes (27): BatchSweep Analysis methods and interpretation README, Read-only post-processing layer over saved sweeps, Index table plus the cross-scenario comparison figures (each + CSV)., _write_summary(), main(), BATCH temperature studies of the PFR digital twin. Same physics and outputs as…, Index table plus the cross-scenario comparison figures (each + CSV)., Sweep every scenario, write per-scenario folders and the summary. (+19 more)

### Community 13 - "pfr_twin/__init__.py"
Cohesion: 0.06
Nodes (47): flow_diagnostics(), Plug-flow validity diagnostics. A digital twin should say when its own…, Vogel-type correlation for liquid water, valid ~273-373 K., water_density_g_L(), water_viscosity_Pa_s(), pfr_twin - 1D deterministic digital twin of an isothermal plug flow reactor for…, Kinetic model of the two-step series ester cleavage, per catalyst system. Acid…, bisulfate_equilibrium() (+39 more)

### Community 14 - "OperatingConditions"
Cohesion: 0.08
Nodes (52): Exception, AdequacyReport, GovernorState, Model-inadequacy governor: distinguishes "my parameters are uncertain" from "my…, AdvancedDesignConfig, AdvancedSelector, DesignDecision, NoiseSurrogate (+44 more)

### Community 15 - "test_comparison.py"
Cohesion: 0.09
Nodes (36): _agg(), _at_or_before(), budget_to_target_rows(), _first_reaching(), headline_rows(), matched_resource_rows(), Conventional-vs-optimized comparison: how much does the methodology actually…, What accuracy had each method reached by the time it had spent what the… (+28 more)

### Community 16 - "Codex Graphify Feature Set"
Cohesion: 0.12
Nodes (16): URL Ingest via /graphify add (Codex), Folder Watch Auto-Rebuild (Codex), FalkorDB Cypher Export (Codex), graphify MCP stdio Server (Codex), Neo4j Cypher Export (Codex), GitHub Repo Clone (Codex), Cross-Repo Graph Merge (Codex), Native CLAUDE.md Integration (Codex) (+8 more)

### Community 17 - "SpectralFitter"
Cohesion: 0.09
Nodes (34): _figure_recovery(), Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling…, # NOTE: with this on, blind RMSE is computed in the CHOSEN reactor, so, # NOTE: the shipped 20 cm OPEN tube FAILS this at every design flow, Truth vs deconvolved concentration over random compositions. Instrument-level…, calibrate_empirical(), calibrate_nmr(), calibrate_responses() (+26 more)

### Community 18 - "test_audit_regression.py"
Cohesion: 0.09
Nodes (32): campaign_task(), ONE campaign, as a picklable pure function of its four labels. This is the unit…, _compare(), _first_difference(), Regression guard for the publication audit trail. THE CLAIM UNDER TEST: turning…, A-D run unchanged sdl.campaign code and are audited entirely post-campaign, so…, E adds spatial optimization and per-round timing calls., The one that matters: F exercises the EIG selector (RNG), the QC gate and the… (+24 more)

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
Cohesion: 0.11
Nodes (23): first_order_multiplet(), Line, NMRSimulator, _noise_grid_factor(), ndarray, Std-dev change caused by RESAMPLING the FFT-bin noise onto the display grid,…, Is this effect simulated? `enabled` is the master switch, the per-effect gate…, What this instrument actually simulates - for the run record. (+15 more)

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
Cohesion: 0.10
Nodes (42): Every machine-readable table of the campaign, in `data/`. The audit tables come…, _write_tables(), _assimilated(), CampaignRecord, concentration_rows(), _corr_max_offdiag(), export_spectra(), _f() (+34 more)

### Community 28 - "_TextProgress"
Cohesion: 0.33
Nodes (3): Any, Minimal progress reporter used only when tqdm is unavailable., _TextProgress

### Community 29 - "test_spectral.py"
Cohesion: 0.21
Nodes (12): delta(H2O)/ppm ~ 5.051 - 0.0111*T(degC). Empirical aqueous relation inherited…, water_shift(), _ideal_sim(), Tests of the NMR forward model (sdl_advanced.spectral). Runnable standalone:…, Doubling [EGDA] must exactly double the EGDA-only spectral area., FFT of the simulated FID must reproduce the analytic Lorentzian spectrum (ideal…, The exchange-pool position must track the NMR-CELL temperature, not any reactor…, test_area_proportional_to_concentration() (+4 more)

### Community 30 - "AuditRecorder"
Cohesion: 0.12
Nodes (9): AuditRecorder, Passive audit recorder for the publication workflow. DESIGN RULE, and the whole…, `curve` is `SpatialDesigner.last_selection`: the marginal log-det gain the…, `part` is the controller's per-position view of one acquisition: {"z", "y",…, Whole-profile convenience for the ungated (direct-observation) path, where…, Wall-clock only. Reading a clock cannot change a result, and these columns are…, Picklable primitives only, for the trip back from a worker., Append-only sink. Holds plain Python/NumPy scalars so the payload is cheap to… (+1 more)

### Community 31 - "screen"
Cohesion: 0.24
Nodes (11): greedy_d_optimal(), information_matrices(), _logdet_floored(), ndarray, Pre-campaign identifiability screen. Before a single experiment is spent, ask…, Per-condition information M_e = S_e' Sigma_e^-1 S_e at `theta_vec` (default:…, log det F with eigenvalues floored, so a rank-deficient F still ranks sensibly…, FIM of the greedy D-optimal `budget`-experiment design over `mats`. (+3 more)

### Community 32 - "ParameterSpace"
Cohesion: 0.09
Nodes (27): check_truth_in_domain(), _geometry_score(), Is every hidden true parameter inside the candidate model's domain? Returns a…, Pre-campaign identifiability screen (same code as run_sdl_campaign.py),…, D-optimal information of a REFERENCE design in this reactor, under the PRIOR…, screened_dropped_keys(), literature_guess(), Initial estimates = Layer 1's literature-anchored kinetics for the chosen… (+19 more)

### Community 33 - "Batch Results Analysis CLI"
Cohesion: 0.31
Nodes (8): main(), parse_args(), load_config(), _merge(), Any, Path, Large-sweep storage/detail degradation strategy, Namespace

### Community 34 - "._model_components"
Cohesion: 0.15
Nodes (7): ndarray, phi = r_w' r_w / dof, the factor by which the residuals exceed the size the…, Max standardized mean residual over (experiment x species) CELLS, Sidak-…, (component p-values, combined Sidak min-p, species bias, chi2/dof score, pooled…, THE single definition of which diagnostics enter the decision. Used identically…, Sidak-combined min-p over the DECISION components., governor_rows()

### Community 35 - "test_acquisition.py"
Cohesion: 0.12
Nodes (17): _noise_std(), _quiet_nuisance(), Three corrections found by external review, each with the property that made it…, Both sides must call the SAME helper - a correction applied to only one of them…, The defect: changing acquisition_time_s changed nothing., Enlarging fft_points interpolates the spectrum; it must not improve SNR, which…, The returned spectrum must carry the declared receiver noise, on the same…, Acquisition time is a physical FID setting; the analytic engine builds the… (+9 more)

### Community 36 - "test_design_space.py"
Cohesion: 0.06
Nodes (54): Leave-one-factor-level-out surrogate validation, A/B/C/D four-strategy showcase, Franceschini & Macchietto (2008) MBDoE review, D-optimal Model-Based Design of Experiments, A-optimal design criterion, Four-axis coarse candidate design grid, Bounded continuous Powell refinement of the best candidate, Equal-experiment-budget fairness caveat (+46 more)

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
Cohesion: 0.12
Nodes (25): ProcessPoolExecutor, describe_workers(), make_executor(), ordered_map(), pin_numerical_threads(), Cross-platform, determinism-preserving process parallelism for the benchmark.…, Apply `fn(*args)` to every tuple, returning results in SUBMISSION order. `fn`…, Pin every numerical backend to `n_threads`. Call this BEFORE importing… (+17 more)

### Community 45 - "AcquisitionSettings"
Cohesion: 0.04
Nodes (74): make_lab(), The line THIS scenario runs, built from the CURRENT global configuration plus…, The hidden truth for this scenario. MODEL_MISMATCH['truth_parameter_bias'] is…, ScenarioSpec, AdvancedVirtualLaboratory, FaultModel, InstrumentConfig, AdvancedVirtualLaboratory: the hidden-truth side of the advanced system. Owns… (+66 more)

### Community 46 - "sdl_advanced/reporting.py"
Cohesion: 0.10
Nodes (36): _csv(), figure_a_spatial_value(), figure_b_position_rounds(), figure_c_spectrum(), figure_convergence_band(), figure_d_truth_vs_recovered(), figure_design_trajectory(), figure_e_convergence() (+28 more)

### Community 47 - "benchmark.py"
Cohesion: 0.10
Nodes (21): assumed_noise(), _assumed_transfer_from(), BaselineLabAdapter, continuous_kwargs(), design_for_budget(), design_resolution(), Reproducible Monte Carlo benchmark of strategies A-F on the EGDA/H2SO4 system.…, Keyword arguments for the BASELINE MBDoESelector (strategies C/D/E). Empty when… (+13 more)

### Community 48 - "observability.py"
Cohesion: 0.13
Nodes (20): domain_scan(), k_sensitivity(), phi_profiles(), plot_phi_profiles(), ndarray, Equilibrium observability of the reversible EGDA hydrolysis. The reversible…, One diagnostic row per operating condition over the reachable domain: residence…, Domain-level verdict on equilibrium identifiability. phi_threshold: below this… (+12 more)

### Community 49 - "io.py"
Cohesion: 0.30
Nodes (13): configuration_key(), _csv_value(), discover(), flatten_run_config(), _number(), Any, Path, read_profile() (+5 more)

### Community 50 - "sdl/__init__.py"
Cohesion: 0.11
Nodes (25): Seven-step self-driving closed loop, noise_true vs noise_assumed misspecification study hook, Recommended study extensions (Monte Carlo, cost-aware, ablation), main(), Layer 2 showcase: virtual self-driving laboratory around the Layer 1 PFR twin.…, resolve_outdir(), Closed-loop campaign runner - the "self-driving" part. For one strategy the…, RoundRecord (+17 more)

### Community 51 - "surrogate_validation"
Cohesion: 0.22
Nodes (10): _compiled_nondominated_indices(), _error_metrics(), _nondominated_indices(), _polynomial_design(), ndarray, Validate one quadratic response surface per study. All requested responses…, Compiled incremental skyline scan for large exact fronts., Return nondominated row indices for a maximization matrix. Lexicographic… (+2 more)

### Community 52 - "SpatialDesignConfig"
Cohesion: 0.11
Nodes (25): _figure_spatial_value(), True profile + equal vs optimized positions + information density. A REFERENCE…, fixed_equal_positions(), _logdet_floored(), ndarray, Spatial measurement design for the moving-capillary CPR. The sampling position…, (y (n_species,), S (n_species x p)) linearly interpolated at z., Full profile for one condition, according to cfg.mode. (+17 more)

### Community 53 - "test_truth_firewall.py"
Cohesion: 0.24
Nodes (12): _mini_campaign(), Truth/inference firewall tests for the advanced system, exercised through a…, STRONG invariant: starting from everything the controller owns (ensemble,…, The observation operator must be built from COMMANDED/ASSUMED transfer…, All Python objects reachable from `roots` via attributes and containers (id-…, _reachable_objects(), test_full_campaign_never_reveals_truth(), test_lab_unreachable_from_controller_object_graph() (+4 more)

### Community 54 - "audit_summary.py"
Cohesion: 0.17
Nodes (14): _boot_ci_median(), _checksums(), convergence_summary_rows(), _git_commit(), _package_versions(), parameter_domain_check_rows(), ndarray, Run-level audit artifacts: convergence summaries that survive failed campaigns,… (+6 more)

### Community 55 - "test_nmr_calibration.py"
Cohesion: 0.14
Nodes (17): DESIGN-TIME predictor of the deconvolution covariance for a CANDIDATE…, No-op: this model is analytic, not data-fitted (interface parity with…, SpectralCovarianceModel, _calibration(), coverage_gate(), Priority-1 tests: ONE public NMR calibration artifact shared by the measurement…, FAIL only when we can be CONFIDENT the true coverage is below `severe`: the…, End-to-end Priority-1 acceptance on the REACHABLE suite (the one the campaign… (+9 more)

### Community 56 - "main"
Cohesion: 0.15
Nodes (16): _finals(), git_provenance(), main(), _mean_curves(), Main EGDA advanced benchmark (corrected framework, v3 outputs). Runs the…, Where this run writes - and a refusal to overwrite anything else. A completed…, Exact commit + working-tree state, so a result can be traced to code. A dirty…, resolve_outdir() (+8 more)

### Community 57 - "create_figures"
Cohesion: 0.52
Nodes (6): create_figures(), _finish(), Any, Figure, Path, _study_groups()

### Community 58 - "test_resource_accounting.py"
Cohesion: 0.31
Nodes (9): _meter(), Tests of resource accounting (sdl_advanced.resources). Runnable standalone., Acceptance criterion 13: totals are nonnegative and re-derivable from the event…, Adaptive one-z-at-a-time sampling at the SAME (T,Q,C_EGDA,C_cat) must not re-…, test_capillary_travel_is_sum_of_moves(), test_reacquisitions_counted_separately(), test_totals_nonnegative_and_auditable(), test_unchanged_condition_stabilizes_once() (+1 more)

### Community 59 - "build_report"
Cohesion: 0.47
Nodes (5): build_report(), _fmt(), Any, Path, Independent regime flags and primary regime priority

### Community 60 - "apply_config"
Cohesion: 0.09
Nodes (46): active_geometry(), apply_config(), geometry_sizing_table(), invalidate_caches(), Every candidate the sizing considered, with the decomposed objective (info,…, The reactor this campaign runs in: the declared GEOMETRY, or the prior-optimal…, Initializer for a parallel worker process. Two jobs. First, silence the per-…, Refuse a direct assignment to a feature-derived field. `replay=True` (the call… (+38 more)

### Community 61 - "test_deconvolution.py"
Cohesion: 0.13
Nodes (15): bootstrap_coverage(), Parametric bootstrap: simulate n_boot noisy spectra of a KNOWN composition,…, Tests of spectral quantification (sdl_advanced.spectral_fit). Runnable…, A spectrum the lineshape model cannot explain must raise FAIL QC., Acceptance criterion 6: an ideal spectrum must be deconvolved back to the…, EGDA (4.335) and EGMA ester triplet (4.245) are ~7 Hz apart at 80 MHz: the…, Monte Carlo intervals under the FULL truth-model mismatch, after the response…, Anti-inverse-crime: FID-engine truth (time-domain generation, colored noise,… (+7 more)

### Community 62 - "run_simulation.py"
Cohesion: 0.10
Nodes (34): _fmt_secs(), main(), _progress(), BATCH base-case runs of the PFR digital twin. Same physics and outputs as…, Yield items with a tqdm-style progress bar (count, %, elapsed, ETA). Uses tqdm…, Simulate every scenario, write per-scenario folders and the summary., Write the normal numerical outputs without constructing figures., Remove stale or summary figures while retaining paired CSV files. (+26 more)

### Community 63 - ".run_profile"
Cohesion: 0.14
Nodes (9): ndarray, Hidden true composition (ALL Layer-1 species) at each z., Batch-reaction propagator at the transfer-line temperature, closed over the…, Set condition u, sample the requested positions in the given order (one moving…, Legacy-style observation: concentrations + NoiseModel noise. cov_y stays None…, Gross, QC-DETECTABLE corruption of one acquisition. A rolling artifact spanning…, UNDETECTABLE quantification outliers: displace a species by many CLAIMED sigmas…, Spectrum -> deconvolution. The fitter sees only the spectrum. (+1 more)

### Community 64 - "test_geometry_packing.py"
Cohesion: 0.17
Nodes (11): Stage-1 regression tests for the corrected framework: configurable geometry +…, A packed bed has less liquid holdup -> shorter tau -> LOWER conversion; the…, REGRESSION: publication mode (budget 8) aborted because the declared…, Budgets that fit the declared ladder must reproduce the PREVIOUS behaviour…, test_declared_ladder_untouched_when_budget_fits(), test_fixed_design_ladder_supports_every_planned_budget(), test_packed_uses_bed_void_fraction(), test_packing_changes_conversion_only_when_enabled() (+3 more)

### Community 65 - "QCGateConfig"
Cohesion: 0.11
Nodes (30): measure_with_qc(), _qc_failed(), qc_fault_verdict(), QCGateConfig, QCMonitor, Per-campaign memory of acquisition dispositions (rules 3 and 4). Deliberately…, Apply the four gate rules (see QCGateConfig) and say WHICH one fired. Separated…, Measure the positions with the QC gate applied BEFORE assimilation. Returns… (+22 more)

### Community 66 - ".select"
Cohesion: 0.13
Nodes (12): expected_information_gain(), _logdet_floored(), ndarray, Sigma for ONE position's species vector., Species-major covariance for a whole profile (block per z)., (EIG_total, EIG_model) in nats, from cached particle predictions. preds: (N,…, Sensitivity matrix of the reference-grid predictions wrt theta (best model,…, Hand the ALREADY-COMPUTED scores to the audit sink, if any. Nothing here is… (+4 more)

### Community 67 - "evaluate"
Cohesion: 0.10
Nodes (34): evaluate(), explain(), _geom(), is_feasible(), max_admissible_flow_mL_min(), min_admissible_length_m(), Plug-flow validity of a reactor OVER ITS WHOLE OPERATING ENVELOPE. WHY THIS…, Full plug-flow diagnosis of ONE geometry at ONE total flow. Returns a flat dict… (+26 more)

### Community 68 - "features.py"
Cohesion: 0.08
Nodes (18): _chem(), _h_activity(), _h_baseline(), _h_broadening(), _h_correlated_noise(), _h_gain(), _h_ka2(), _h_lineshape_mismatch() (+10 more)

### Community 69 - "_round_metrics"
Cohesion: 0.17
Nodes (13): blind_rmse(), _entropy(), _param_rows(), ndarray, The same model configuration in a different reactor - used to move a LEARNED…, Bridge used for BLIND SCORING: identical object when geometry optimization is…, Blind predictive RMSE of the REACTOR state (transport correction is an…, Per-parameter posterior reporting (#identifiability): estimate, scaled sigma,… (+5 more)

### Community 70 - "Literature-anchored kinetic parameter provenance"
Cohesion: 0.40
Nodes (5): Berthelot & Péan de Saint-Gilles (1862) esterification equilibrium, A. J. Kirby, Comprehensive Chemical Kinetics Vol. 10, Literature-anchored kinetic parameter provenance, Ethyl acetate + NaOH conductometric saponification benchmarks, Statistical factors for equivalent acetate groups

### Community 71 - "._through_line"
Cohesion: 0.29
Nodes (3): Propagator, Composition arriving at the NMR cell for a sample drawn at z. Applies (in…, (taus, weights) of the residence-time quadrature.

### Community 72 - "reactor.py"
Cohesion: 0.12
Nodes (19): analytical_profiles(), _bracketed_root(), equilibrium_state(), max_relative_error(), ndarray, Algebraic reference solutions used to verify the numerical integrator. 1.…, Composition at simultaneous chemical equilibrium of both steps. Solves for the…, Largest |numerical - analytical| across species, relative to `scale`. (+11 more)

### Community 73 - "last_valid_rows"
Cohesion: 0.31
Nodes (9): _boot_ci(), last_valid_rows(), paired_comparison(), One row per SEED: that seed's LAST COMPLETED round. Using the per-seed last…, Last-valid-round distributional summary per strategy: median, IQR, mean,…, Common-random-number PAIRED comparison of two strategies at the final round:…, summarize_final(), A seed that stops early keeps its LAST VALID round in the summary (n_seeds… (+1 more)

### Community 74 - "KineticModel"
Cohesion: 0.12
Nodes (11): KineticModel, kappa_i = k_i(T) * c_cat, the forward time-scale constants. c_cat is [H+] on…, Net rates (positive = ester-cleavage direction) for the state vector c in…, ArrheniusStep, EquilibriumStep, k(T) = A * exp(-Ea / (R T)) with A in L/(mol s) and Ea in J/mol., Concentration-based hydrolysis equilibrium constant of one step, K(T) = (…, ndarray (+3 more)

### Community 75 - "audit_export.py"
Cohesion: 0.14
Nodes (25): blind_prediction_rows(), calibration_rows(), collect_campaign(), design_history_rows(), _empty(), empty_bundle(), _f(), identifiability_rows() (+17 more)

### Community 76 - "main"
Cohesion: 0.09
Nodes (32): main(), Resolve the output directory, refusing to overwrite a completed run. An…, The spatial policy this strategy actually ran, resolved the same way…, (u, z, species) -> the hidden TRUE reactor composition. POST-CAMPAIGN ONLY. It…, resolve_outdir(), _spatial_mode_of(), _truth_predictor(), assert_reactor_validity() (+24 more)

### Community 77 - "AdequacyGovernor"
Cohesion: 0.20
Nodes (13): AdequacyGovernor, GovernorConfig, B must satisfy 1/(B+1) <= alpha or the bootstrap p-value can never reach the…, Parametric-bootstrap empirical p-value of the DECISION statistic (same…, Stage-1 regression tests for: NMR calibration/validation independence and PSD…, assess(), the analytical combination and the bootstrap must all use the SAME…, B must be able to resolve alpha: 1/(B+1) <= alpha, else reject., Cheap check (B kept small via an explicit large alpha): the returned p is a… (+5 more)

### Community 78 - "test_features.py"
Cohesion: 0.10
Nodes (23): fitter_kwargs(), The quantification error-model terms the fitter reports in Sigma_y. With…, This scenario's candidate family AFTER the feature switches. A feature that…, scenario_family(), Central Boolean feature control. The contract these tests defend: * ONE switch…, With the noise gate off (and nothing else random left on), repeated…, Gate off == that effect absent, bit for bit. Compared against a nuisance whose…, REGRESSION: the scenarios used to CAPTURE a TransferConfig at import, so a… (+15 more)

### Community 79 - "Layer1Bridge"
Cohesion: 0.09
Nodes (23): Layer1Bridge, Configured gateway to the Layer 1 simulator., Per mole of catalyst, saponification must be orders of magnitude faster.…, Sub-stoichiometric NaOH: acetate released must equal the OH- consumed, the…, The bridge must speciate at each experiment's own temperature: with the default…, ODE and analytical forward engines must match in the irreversible limit (there…, Net rates must vanish exactly at the coupled-equilibrium composition…, At long residence time the reversible PFR must (i) conserve the three linear… (+15 more)

### Community 80 - "apply"
Cohesion: 0.14
Nodes (20): apply(), _apply_mismatch(), cascade(), _check_magnitudes(), _lookup(), mismatch_defaults(), Any, Route the switches into the configuration blocks of `ns`. Called at the END of… (+12 more)

### Community 81 - "ReactorGeometry"
Cohesion: 0.11
Nodes (9): Straight cylindrical tube, optionally filled with INERT packing. Defaults match…, epsilon actually used by the hydrodynamics (1 when unpacked)., Empty-tube cross-section (geometric)., Cross-section carrying flowing liquid; sets the INTERSTITIAL velocity u = Q /…, Total (empty-tube) reactor volume., Flowing-liquid holdup: epsilon * V_tube., tau = epsilon A L / Q (= A L / Q for an unpacked tube)., ReactorGeometry (+1 more)

### Community 82 - "test_campaign_report.py"
Cohesion: 0.16
Nodes (18): Regression guard for the per-campaign scientific record. THE CLAIM UNDER TEST,…, F is the one that matters: it exercises the EIG selector's RNG, the QC gate and…, The control: D runs unchanged sdl.campaign code, so this must pass trivially -…, The information curve is KEPT from the greedy step, not recomputed. Its…, The decomposition must ADD UP: reactor -> cell -> reported., The firewall: nothing may ask the laboratory for truth while it is still…, A campaign on real hardware has no hidden truth. The reporting layer must then…, One campaign, with the reporting sinks either all on or all off. (+10 more)

### Community 83 - "run_temperature_study.py"
Cohesion: 0.21
Nodes (16): SolverSettings, Integrate the plug-flow balances from x = 0 to x = L. u is the INTERSTITIAL…, simulate_pfr(), build_kinetics(), KineticParameters for the configured catalyst system., main(), Temperature sensitivity study of the PFR digital twin. Sweeps the (isothermal)…, Everything one temperature sweep produces. (+8 more)

### Community 84 - "run_scenario"
Cohesion: 0.13
Nodes (17): merge(), Returns (round rows, per-parameter rows, per-campaign status rows). NO campaign…, run_scenario(), runtime_s measures the RUN, not the chemistry: it is the one field a worker…, Plain `==` is unusable here: legitimate NaNs (p_correct for a non-Bayesian…, Guard the guard: the NaN-tolerant comparator must not be so forgiving that the…, Only primitives may cross the process boundary - never a laboratory, a…, The whole point, end to end: a real registered scenario with all six of its… (+9 more)

### Community 85 - "PFRResult"
Cohesion: 0.17
Nodes (8): nu_matrix(), PFRResult, ndarray, Stoichiometric matrix of the chosen catalyst system., Axial profiles plus the scalars needed to interpret them., Fractional EGDA conversion X(x)., Yield of EGMA or EG on a diol-backbone basis: (C_i - C_i0)/C_EGDA0., Outlet selectivity of EGMA among converted EGDA.

### Community 86 - "LaplacePosterior"
Cohesion: 0.22
Nodes (4): LaplacePosterior, ndarray, Per-parameter Gaussian posterior mass lying OUTSIDE the box - the diagnostic…, n draws from the Laplace Gaussian PROPERLY truncated to the box. Strategy:…

### Community 87 - "campaign_html.py"
Cohesion: 0.36
Nodes (11): build_report(), _e(), _figure(), _files(), _fmt(), _last_per_strategy(), _num(), The human-readable half of the campaign record: one self-contained HTML page.… (+3 more)

### Community 88 - ".predict"
Cohesion: 0.24
Nodes (5): Sensitivity field of the EXPECTED OBSERVATION (through the candidate's…, ndarray, The candidate's expected-observation operator - the ONE way any controller-side…, Current MAP if fitted, else the initial guess (for pre-data design)., Particle prediction through the candidate's expected-observation operator (NOT…

### Community 89 - "_set_dc"
Cohesion: 0.18
Nodes (11): _h_acq_time(), _h_fid(), _h_line_carryover(), _h_line_reaction(), _h_line_rtd(), _h_line_temperature(), _h_overlap(), _h_resource_aware() (+3 more)

### Community 90 - "ResourceEvent"
Cohesion: 0.18
Nodes (6): ndarray, Reactor condition set + stabilization to steady state. Idempotent for an…, Capillary move + flush + one NMR acquisition at position z. retry=True marks a…, A position whose data was rejected by the QC gate (not assimilated); auditable,…, Scalar penalty term of the resource-aware utility for a HYPOTHETICAL experiment…, ResourceEvent

### Community 91 - "CompositionEnvelope"
Cohesion: 0.24
Nodes (9): _check_standards(), CompositionEnvelope, _mass_balance_series(), DATASET 2 - independent calibration-CHECK standards. A conversion series over…, The composition range prepared standards have to cover. `egda_reactor_M` are…, Highest concentration of each species this envelope reaches - the number a…, Declare the composition envelope the prepared standards must span., Conversion series on the A -> B -> C mass-balance manifold. `offset` shifts the… (+1 more)

### Community 92 - "nmr_examples.py"
Cohesion: 0.31
Nodes (8): generate(), ndarray, Three deterministic representative NMR examples for the publication figures.…, (label, ppm, observed, fitted, residual, components) per example., Per-species (plus pool and baseline) contribution to the FITTED spectrum.…, Simulate, deconvolve and export the three examples. Returns one summary row per…, _species_components(), spectra_for_plot()

### Community 93 - "total_cost_units"
Cohesion: 0.50
Nodes (4): campaign_cost_units(), Approximate work of one campaign, in arbitrary units ~ seconds., Total weighted work of a benchmark run (campaigns + governor MC)., total_cost_units()

### Community 94 - "derive_allowance"
Cohesion: 0.50
Nodes (4): derive_allowance(), kappa for this scenario's observation mode. Direct observation has an exact…, Derive kappa from WELL-SPECIFIED CONTROL DATA under THIS configuration. A hard-…, systematic_allowance()

### Community 95 - "governor_mc_validation"
Cohesion: 0.50
Nodes (4): governor_mc_validation(), governor_task(), First round at which the governor declares MODEL_INADEQUATE, plus WHY - the…, Monte Carlo validation of the governor (#calibration honesty): * correct-family…

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
- **Why does `OperatingConditions` connect `OperatingConditions` to `InferenceModel`, `sdl/reporting.py`, `self_test.py`, `NoiseModel`, `pfr_twin/__init__.py`, `SpectralFitter`, `screen`, `test_acquisition.py`, `test_design_space.py`, `AcquisitionSettings`, `benchmark.py`, `observability.py`, `sdl/__init__.py`, `SpatialDesignConfig`, `test_truth_firewall.py`, `main`, `.run_profile`, `test_geometry_packing.py`, `QCGateConfig`, `.select`, `KineticModel`, `AdequacyGovernor`, `test_features.py`, `Layer1Bridge`, `.predict`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._