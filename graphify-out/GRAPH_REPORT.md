# Graph Report - EGDA  (2026-08-08)

## Corpus Check
- 104 files · ~508,642 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1395 nodes · 3672 edges · 60 communities (56 shown, 4 thin omitted)
- Extraction: 89% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 382 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a2519ac9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pipeline.py
- Sweep Integrity and Geometry Collapse Figures
- Sensitivity and Pareto Figures
- Regime, Robustness and Surrogate Figures
- Layer1Bridge
- Design Coverage and Damkohler Figures
- build_readme_figures.py
- sdl/reporting.py
- self_test.py
- run_temperature_study.py
- plotting.py
- benchmark.py
- run_simulation.py
- pfr_twin/__init__.py
- ModelEnsemble
- batch_simulation.py
- Codex Graphify Feature Set
- NMRSimulator
- PFRResult
- Claude Graphify Feature Set
- PFR digital twin layer README
- MBDoE Theory and Epistemic Caveats
- test_analysis.py
- Line
- Detection, Cache and Update Flow
- Extraction Spec and Honesty Rules
- sim_nmr(2).py
- .effective_constants
- progress
- AcquisitionSettings
- sdl_advanced/__init__.py
- OperatingConditions
- ndarray
- Batch Results Analysis CLI
- AdequacyGovernor
- SpatialDesigner
- Literature-anchored kinetic parameter provenance
- Build, Cluster and Export Steps
- Codex Subagent Dispatch
- Auto-Rebuild Watch and Commit Hooks
- Graphify Workflow Policy
- Query, Path and Explain Flows
- Equilibrium Solver Verification
- Uncertainty Report Covariance
- BatchSweep Package Init
- AdvancedVirtualLaboratory
- main
- test_measurement_fault.py
- AnalysisTests
- io.py
- AdvancedSelector
- surrogate_validation
- .run_profile
- test_truth_firewall.py
- covariance_from_fim
- SpectralCovarianceModel
- ndarray
- create_figures
- ResourceMeter
- build_report

## God Nodes (most connected - your core abstractions)
1. `OperatingConditions` - 92 edges
2. `Layer1Bridge` - 80 edges
3. `InferenceModel` - 56 edges
4. `NoiseModel` - 56 edges
5. `ModelEnsemble` - 55 edges
6. `Measurement` - 52 edges
7. `ParameterSpace` - 48 edges
8. `AdvancedVirtualLaboratory` - 48 edges
9. `NMRSimulator` - 41 edges
10. `AcquisitionSettings` - 39 edges

## Surprising Connections (you probably didn't know these)
- `Coupled equilibrium solver (Gauss–Seidel + Brent)` --implements--> `equilibrium_state()`  [EXTRACTED]
  README.md → PFR_H2SO4_digital_twin/pfr_twin/analytical.py
- `graphify Pipeline (Codex)` --semantically_similar_to--> `graphify Pipeline (Claude Code)`  [INFERRED] [semantically similar]
  .codex/skills/graphify/SKILL.md → .claude/skills/graphify/SKILL.md
- `Extraction Subagent Prompt (Compact)` --semantically_similar_to--> `Extraction Subagent Prompt`  [INFERRED] [semantically similar]
  .codex/skills/graphify/references/extraction-spec.md → .claude/skills/graphify/references/extraction-spec.md
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

## Communities (60 total, 4 thin omitted)

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

### Community 4 - "Layer1Bridge"
Cohesion: 0.09
Nodes (47): _figure_a(), True profile + equal vs optimized positions + information density., Pre-campaign identifiability screen (same code as run_sdl_campaign.py),…, screened_dropped_keys(), AssumedTransfer, build_egda_family(), Multi-model Bayesian kinetic inference: p(M, theta | D) via a Laplace model…, The interpretable EGDA/H2SO4 candidate family (see module docstring). `include`… (+39 more)

### Community 5 - "Design Coverage and Damkohler Figures"
Cohesion: 0.10
Nodes (30): axial_egma_peaks.csv (peak dataset), Figure: Axial EGMA Intermediate Maxima (H2SO4 vs NaOH), Reactor Geometry A, Reactor Geometry B, H2SO4 Catalyst Branch, Finding: H2SO4 peaks pinned at outlet, NaOH peaks interior, NaOH Catalyst Branch, Peak EGMA Yield (+22 more)

### Community 6 - "build_readme_figures.py"
Cohesion: 0.23
Nodes (25): axial_egma_peaks(), consolidated_scenarios(), convert(), data_coverage(), derived_metrics(), duplicate_configs(), excluded_or_invalid_scenarios(), geometry_collapse_metrics() (+17 more)

### Community 7 - "sdl/reporting.py"
Cohesion: 0.11
Nodes (36): The inverse problem — kinetics from noisy measurements, Reference-temperature (k_ref, Ea) reparameterization, campaign_history.csv per-round record, final_report.txt human-readable campaign summary, main(), resolve_outdir(), StrategyResult, Estimation parameter space (catalyst-aware). Natural parameters (dict keys,… (+28 more)

### Community 8 - "self_test.py"
Cohesion: 0.07
Nodes (40): Truth/inference firewall, Truth-only systematic effects (transfer_time_s, calibration_gain), build_fixed_design(), Conventional campaign: temperature ladder at nominal flow/catalyst. `budget`…, greedy_d_optimal(), information_matrices(), _logdet_floored(), ndarray (+32 more)

### Community 9 - "run_temperature_study.py"
Cohesion: 0.11
Nodes (31): main(), BATCH temperature studies of the PFR digital twin. Same physics and outputs as…, Sweep every scenario, write per-scenario folders and the summary., run_batch(), make_run_dir(), _num(), Run-output plumbing: self-describing result folders and plot-paired CSVs. Two…, Write named equal-length numeric columns as a headed CSV. (+23 more)

### Community 10 - "plotting.py"
Cohesion: 0.17
Nodes (25): Index table plus the cross-scenario comparison figures (each + CSV)., _write_summary(), _end_label(), _legend(), _new_axes(), plot_concentration_profiles(), plot_conversion_yield(), plot_profile_overlay() (+17 more)

### Community 11 - "benchmark.py"
Cohesion: 0.21
Nodes (14): _assumed_transfer_from(), governor_mc_validation(), make_lab(), Reproducible Monte Carlo benchmark of strategies A-F on the EGDA/H2SO4 system.…, INFERENCE-side transfer correction from COMMANDED quantities only (nominal…, One (scenario, strategy, seed) campaign. Returns (result, lab, extra)., Monte Carlo validation of the governor (#calibration honesty): * correct-family…, run_one_campaign() (+6 more)

### Community 12 - "run_simulation.py"
Cohesion: 0.06
Nodes (42): Concentration-based reaction quotients (Q1, Q2) of the two steps; NaN where the…, reaction_quotients(), KineticModel, Kinetic model of the two-step series ester cleavage, per catalyst system. Acid…, mix_streams(), One feed stream to the micromixer. composition : mol/L of *solutes* (any of…, Flow-weighted ideal blending of the two feed streams. T_K is the (isothermal)…, Stream (+34 more)

### Community 13 - "pfr_twin/__init__.py"
Cohesion: 0.07
Nodes (45): analytical_profiles(), _bracketed_root(), equilibrium_state(), max_relative_error(), ndarray, Algebraic reference solutions used to verify the numerical integrator. 1.…, Composition at simultaneous chemical equilibrium of both steps. Solves for the…, Largest |numerical - analytical| across species, relative to `scale`. (+37 more)

### Community 14 - "ModelEnsemble"
Cohesion: 0.10
Nodes (39): AdequacyReport, GovernorState, Model-inadequacy governor: distinguishes "my parameters are uncertain" from "my…, AdvancedDesignConfig, DesignDecision, NoiseSurrogate, Bayesian expected-information-gain (EIG) active learning with a FIM pre-screen…, Expected observation-covariance model LEARNED from the campaign's own… (+31 more)

### Community 15 - "batch_simulation.py"
Cohesion: 0.09
Nodes (32): BatchSweep Analysis methods and interpretation README, Read-only post-processing layer over saved sweeps, _fmt_secs(), main(), _progress(), BATCH base-case runs of the PFR digital twin. Same physics and outputs as…, Yield items with a tqdm-style progress bar (count, %, elapsed, ETA). Uses tqdm…, Simulate every scenario, write per-scenario folders and the summary. (+24 more)

### Community 16 - "Codex Graphify Feature Set"
Cohesion: 0.12
Nodes (16): URL Ingest via /graphify add (Codex), Folder Watch Auto-Rebuild (Codex), FalkorDB Cypher Export (Codex), graphify MCP stdio Server (Codex), Neo4j Cypher Export (Codex), GitHub Repo Clone (Codex), Cross-Repo Graph Merge (Codex), Native CLAUDE.md Integration (Codex) (+8 more)

### Community 17 - "NMRSimulator"
Cohesion: 0.08
Nodes (40): _figure_d(), main(), Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling…, Truth vs deconvolved concentration over random compositions., resolve_outdir(), bootstrap_coverage(), calibrate_responses(), ndarray (+32 more)

### Community 18 - "PFRResult"
Cohesion: 0.20
Nodes (6): PFRResult, ndarray, Axial profiles plus the scalars needed to interpret them., Fractional EGDA conversion X(x)., Yield of EGMA or EG on a diol-backbone basis: (C_i - C_i0)/C_EGDA0., Outlet selectivity of EGMA among converted EGDA.

### Community 19 - "Claude Graphify Feature Set"
Cohesion: 0.18
Nodes (15): /graphify Trigger Registration, FalkorDB Cypher Export, graphify MCP stdio Server, Neo4j Cypher Export, GitHub Repo Clone, Cross-Repo Graph Merge, Native CLAUDE.md Integration, BFS and DFS Traversal Modes (+7 more)

### Community 20 - "PFR digital twin layer README"
Cohesion: 0.09
Nodes (25): Axial EGMA peak location and 95% plateau interval, Damköhler kinetic-exposure metric, Contrast with the packed-bed Amberlyst twin, PFR digital twin layer README, Water as explicit reactant on the acid route, Layer 1 Python dependencies (numpy, scipy, matplotlib), R. P. Bell, Acid–Base Catalysis, Bisulfate catalyst speciation ([H+] from HSO4-/SO4 2-) (+17 more)

### Community 21 - "MBDoE Theory and Epistemic Caveats"
Cohesion: 0.13
Nodes (15): Nearest-Damköhler geometry matching diagnostic, Local elasticities on the Arrhenius 1/T coordinate, What can and cannot be concluded from the sweeps, A/B/C/D four-strategy showcase, Synthetic CPR-NMR heteroscedastic correlated noise model, Fisher Information Matrix and Cramér–Rao bound, Franceschini & Macchietto (2008) MBDoE review, D-optimal Model-Based Design of Experiments (+7 more)

### Community 22 - "test_analysis.py"
Cohesion: 0.26
Nodes (11): assign_regime(), axial_peak(), enrich(), _kinetic_constants(), Any, Read the current simulator constants without modifying or running it., water_density_g_L(), water_viscosity_Pa_s() (+3 more)

### Community 23 - "Line"
Cohesion: 0.15
Nodes (15): first_order_multiplet(), Line, ndarray, One acquisition's random draw of the nuisance parameters., One transition: unit-area Lorentzian x area., [(ppm, relative_area), ...]; binomial first-order multiplet (unchanged physics…, Transition list for a composition (Layer-1 names, mol/L). static_shift: the…, Unit-area Gaussian with the same FWHM (pseudo-Voigt component). (+7 more)

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

### Community 29 - "AcquisitionSettings"
Cohesion: 0.13
Nodes (19): AcquisitionSettings, flow_response(), Reusable 1H NMR forward model of the EGDA hydrolysis mixture at 80 MHz.…, Phenomenological incomplete-relaxation / flow response factor in [0,1]. E = 1 -…, Pooled fast-exchange H2O/OH/COOH line at the population-weighted average shift,…, delta(H2O)/ppm ~ 5.051 - 0.0111*T(degC). Empirical aqueous relation inherited…, Fourier-80 acquisition/processing settings (known to BOTH the truth instrument…, water_shift() (+11 more)

### Community 30 - "sdl_advanced/__init__.py"
Cohesion: 0.11
Nodes (23): Propagator, sdl_advanced - Layer 2+ : realistic CPR + Fourier-80 virtual instrument and…, AdvancedVirtualLaboratory: the hidden-truth side of the advanced system. Owns…, Campaign resource accounting and the resource-aware utility terms. Every…, Sample-transfer model for the single moving CPR capillary. Hardware represented…, Composition arriving at the NMR cell for a sample drawn at z. Applies (in…, Stateful virtual transfer line (owned by the instrument). Remembers the…, (taus, weights) of the residence-time quadrature. (+15 more)

### Community 31 - "OperatingConditions"
Cohesion: 0.09
Nodes (33): Seven-step self-driving closed loop, Bounded continuous Powell refinement of the best candidate, Measurement object (condition, ports, species, noisy values), noise_true vs noise_assumed misspecification study hook, OperatingConditions experiment record, Recommended study extensions (Monte Carlo, cost-aware, ablation), Layer 2 showcase: virtual self-driving laboratory around the Layer 1 PFR twin.…, Closed-loop campaign runner - the "self-driving" part. For one strategy the… (+25 more)

### Community 32 - "ndarray"
Cohesion: 0.20
Nodes (4): ndarray, Estimated components merged with the held-fixed ones, so the forward model…, Keys whose estimate is resting on its box constraint. A bounded least-squares…, Approximate 95% relative confidence half-widths, %, per parameter. For ln-…

### Community 33 - "Batch Results Analysis CLI"
Cohesion: 0.31
Nodes (8): main(), parse_args(), load_config(), _merge(), Any, Path, Large-sweep storage/detail degradation strategy, Namespace

### Community 34 - "AdequacyGovernor"
Cohesion: 0.24
Nodes (5): AdequacyGovernor, ndarray, Max standardized mean residual over (experiment x species) CELLS, Sidak-…, (component p-values, combined Sidak min-p, species bias, chi2/dof score, pooled…, Parametric-bootstrap empirical p-value of the composite (min-p) statistic for…

### Community 35 - "SpatialDesigner"
Cohesion: 0.11
Nodes (25): _logdet_floored(), ndarray, Spatial measurement design for the moving-capillary CPR. The sampling position…, (y (n_species,), S (n_species x p)) linearly interpolated at z., Chooses sampling positions for one operating condition. cov_builder(y_at_z) ->…, Full profile for one condition, according to cfg.mode., Adaptive-sequential step: best next z given positions already measured at this…, Deterministic cyclic coordinate polish of the selected positions on the… (+17 more)

### Community 36 - "Literature-anchored kinetic parameter provenance"
Cohesion: 0.40
Nodes (5): Berthelot & Péan de Saint-Gilles (1862) esterification equilibrium, A. J. Kirby, Comprehensive Chemical Kinetics Vol. 10, Literature-anchored kinetic parameter provenance, Ethyl acetate + NaOH conductometric saponification benchmarks, Statistical factors for equivalent acetate groups

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

### Community 42 - "Equilibrium Solver Verification"
Cohesion: 0.50
Nodes (4): Legacy irreversible limit as verification reference, Coupled equilibrium solver (Gauss–Seidel + Brent), Linear conservation invariants, Per-run self-verification block (PASS/FAIL residuals)

### Community 45 - "AdvancedVirtualLaboratory"
Cohesion: 0.12
Nodes (23): GovernorConfig, BaselineLabAdapter, The S6 lambda sweep: one base weight vector x a scale factor. The base values…, Presents AdvancedVirtualLaboratory as the legacy VirtualLaboratory so…, _resource_lambdas(), AdvancedVirtualLaboratory, InstrumentConfig, POST-CAMPAIGN benchmarking only. (+15 more)

### Community 46 - "main"
Cohesion: 0.07
Nodes (46): _finals(), main(), _mean_curves(), Main EGDA advanced benchmark (corrected framework, v2 outputs). Runs the…, resolve_outdir(), _write_rows(), blind_rmse(), _boot_ci() (+38 more)

### Community 47 - "test_measurement_fault.py"
Cohesion: 0.24
Nodes (12): measure_with_qc(), _qc_failed(), Measure the positions with the QC gate applied BEFORE assimilation. Returns…, _Corruptor, _lab(), Tests of the MEASUREMENT_FAULT control state: QC gating BEFORE assimilation,…, Wraps the truth simulator: corrupts the spectrum for the first `n_bad`…, Persistent instrument failure must pause the campaign - never update the… (+4 more)

### Community 48 - "AnalysisTests"
Cohesion: 0.21
Nodes (7): pareto_front(), Find exact fronts for small studies and epsilon fronts for large ones. Exact…, AnalysisTests, Path, sample_payload(), sample_profile(), write_scenario()

### Community 49 - "io.py"
Cohesion: 0.39
Nodes (11): configuration_key(), _csv_value(), discover(), flatten_run_config(), _number(), Any, Path, read_profile() (+3 more)

### Community 50 - "AdvancedSelector"
Cohesion: 0.11
Nodes (16): AdvancedSelector, expected_information_gain(), _logdet_floored(), ndarray, Sigma for ONE position's species vector., Species-major covariance for a whole profile (block per z)., (EIG_total, EIG_model) in nats, from cached particle predictions. preds: (N,…, Hierarchical (u, Z) selector for strategy F. (+8 more)

### Community 51 - "surrogate_validation"
Cohesion: 0.22
Nodes (10): _compiled_nondominated_indices(), _error_metrics(), _nondominated_indices(), _polynomial_design(), ndarray, Validate one quadratic response surface per study. All requested responses…, Compiled incremental skyline scan for large exact fronts., Return nondominated row indices for a maximization matrix. Lexicographic… (+2 more)

### Community 52 - ".run_profile"
Cohesion: 0.18
Nodes (6): ndarray, Hidden true composition (ALL Layer-1 species) at each z., Batch-reaction propagator at the transfer-line temperature, closed over the…, Set condition u, sample the requested positions in the given order (one moving…, Legacy-style observation: concentrations + NoiseModel noise. cov_y stays None…, Spectrum -> deconvolution. The fitter sees only the spectrum.

### Community 53 - "test_truth_firewall.py"
Cohesion: 0.24
Nodes (12): _mini_campaign(), Truth/inference firewall tests for the advanced system, exercised through a…, STRONG invariant: starting from everything the controller owns (ensemble,…, The observation operator must be built from COMMANDED/ASSUMED transfer…, All Python objects reachable from `roots` via attributes and containers (id-…, _reachable_objects(), test_full_campaign_never_reveals_truth(), test_lab_unreachable_from_controller_object_graph() (+4 more)

### Community 54 - "covariance_from_fim"
Cohesion: 0.20
Nodes (8): covariance_from_fim(), ndarray, Central-difference S (m.size x p) in scaled parameter space., Expected FIM contribution of a candidate experiment, evaluated at the CURRENT…, V ~ F^-1, with uninformative directions given HUGE variance. np.linalg.pinv is…, THE expected-observation operator: what a measurement at (u, z) is predicted to…, A rank-deficient FIM must yield HUGE variance along its null space.…, test_covariance_inflates_unconstrained_directions()

### Community 55 - "SpectralCovarianceModel"
Cohesion: 0.29
Nodes (5): DESIGN-TIME predictor of the deconvolution covariance for a CANDIDATE…, Predicted Sigma_y for ONE position's species concentrations., Species-major covariance for a whole candidate profile., No-op: this model is analytic, not data-fitted (interface parity with…, SpectralCovarianceModel

### Community 57 - "create_figures"
Cohesion: 0.52
Nodes (6): create_figures(), _finish(), Any, Figure, Path, _study_groups()

### Community 58 - "ResourceMeter"
Cohesion: 0.10
Nodes (20): ndarray, Capillary move + flush + one NMR acquisition at position z. retry=True marks a…, A position whose data was rejected by the QC gate (not assimilated); auditable,…, Scalar penalty term of the resource-aware utility for a HYPOTHETICAL experiment…, Accumulates the campaign's physical cost from logged events., Reactor condition set + stabilization to steady state. Idempotent for an…, ResourceEvent, ResourceMeter (+12 more)

### Community 59 - "build_report"
Cohesion: 0.47
Nodes (5): build_report(), _fmt(), Any, Path, Independent regime flags and primary regime priority

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
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

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
- **Why does `OperatingConditions` connect `OperatingConditions` to `SpatialDesigner`, `Layer1Bridge`, `sdl/reporting.py`, `self_test.py`, `benchmark.py`, `run_simulation.py`, `AdvancedVirtualLaboratory`, `ModelEnsemble`, `test_measurement_fault.py`, `NMRSimulator`, `AdvancedSelector`, `.run_profile`, `test_truth_firewall.py`, `covariance_from_fim`, `sdl_advanced/__init__.py`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._