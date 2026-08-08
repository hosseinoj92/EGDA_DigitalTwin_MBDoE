# Graph Report - EGDA  (2026-08-05)

## Corpus Check
- 68 files · ~165,787 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 830 nodes · 1807 edges · 45 communities (43 shown, 2 thin omitted)
- Extraction: 90% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 169 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e0e8fb5c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BatchSweep IO and Pipeline Core
- Sweep Integrity and Geometry Collapse Figures
- Sensitivity and Pareto Figures
- Regime, Robustness and Surrogate Figures
- SDL Campaign and Virtual Laboratory
- Design Coverage and Damkohler Figures
- README Figure Builder Script
- SDL Parameter Space and Reporting
- SDL Campaign Entry and Self-Tests
- Batch Temperature Study and Run IO
- PFR Twin Plotting
- Analytical Reference Solutions
- Base-Case Simulation Runner
- Sulfuric Acid Bisulfate Speciation
- Inference Model and Fisher Information
- Batch Scenario Expansion
- Codex Graphify Feature Set
- Temperature Sweep Runner
- PFR Result and Stoichiometry
- Claude Graphify Feature Set
- EGDA Reaction Network and Catalyst Routes
- MBDoE Theory and Epistemic Caveats
- Plug-Flow Validity Diagnostics
- Layer 1 Bridge and Thermodynamic Tests
- Detection, Cache and Update Flow
- Extraction Spec and Honesty Rules
- Batch Base-Case Simulation
- Kinetic Model Rate Laws
- Text Progress Fallback
- Kinetic Parameter Provenance
- Feed Streams and Mixing
- MBDoE Candidate Selector
- Parameter Space Scaling
- Batch Results Analysis CLI
- Layer READMEs and Activity Models
- Micromixer and Bisulfate Equilibrium
- Arrhenius and Equilibrium Steps
- Build, Cluster and Export Steps
- Codex Subagent Dispatch
- Auto-Rebuild Watch and Commit Hooks
- Graphify Workflow Policy
- Query, Path and Explain Flows
- Equilibrium Solver Verification
- Uncertainty Report Covariance
- BatchSweep Package Init

## God Nodes (most connected - your core abstractions)
1. `OperatingConditions` - 43 edges
2. `Layer1Bridge` - 34 edges
3. `ParameterSpace` - 29 edges
4. `InferenceModel` - 28 edges
5. `run_analysis()` - 23 edges
6. `PFRResult` - 23 edges
7. `main()` - 23 edges
8. `NoiseModel` - 22 edges
9. `KineticModel` - 20 edges
10. `MBDoESelector` - 20 edges

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

## Communities (45 total, 2 thin omitted)

### Community 0 - "BatchSweep IO and Pipeline Core"
Cohesion: 0.06
Nodes (70): configuration_key(), _csv_value(), discover(), flatten_run_config(), _number(), Any, Path, read_profile() (+62 more)

### Community 1 - "Sweep Integrity and Geometry Collapse Figures"
Cohesion: 0.09
Nodes (36): duplicate_configs.csv (data source), Duplicate Records (0), Figure: Configuration Identity Audit (duplicate_configs), Record Count Metric, Sweep Data Integrity Audit, Unique Loaded Configurations (3000), excluded_or_invalid_scenarios.csv (data source), Figure: Validity and Applicability Audit (excluded_or_invalid_scenarios) (+28 more)

### Community 2 - "Sensitivity and Pareto Figures"
Cohesion: 0.09
Nodes (36): C_catalyst_feed_M (catalyst feed concentration), C_EGDA_feed_M (EGDA feed concentration), EGMA Yield (Y_EGMA), Figure: Median absolute local elasticity of EGMA yield, Reactor Geometry A vs B, H2SO4 Catalyst Branch, Local Elasticity median |(x/y)dy/dx|, NaOH Catalyst Branch (+28 more)

### Community 3 - "Regime, Robustness and Surrogate Figures"
Cohesion: 0.08
Nodes (35): Regime Summary Figure (Mutually Exclusive Primary Regimes), acid_equilibrium_limited Regime, Catalyst/Geometry Case (H2SO4-A, H2SO4-B, NaOH-A, NaOH-B), regime_summary.csv (Data Source), EGMA_selective Regime, Finding: H2SO4 Cases Dominated by Low Conversion, interior_EGMA_peak Regime, intermediate Regime (+27 more)

### Community 4 - "SDL Campaign and Virtual Laboratory"
Cohesion: 0.14
Nodes (22): Seven-step self-driving closed loop, Bounded continuous Powell refinement of the best candidate, Measurement object (condition, ports, species, noisy values), noise_true vs noise_assumed misspecification study hook, OperatingConditions experiment record, Recommended study extensions (Monte Carlo, cost-aware, ablation), Closed-loop campaign runner - the "self-driving" part. For one strategy the…, RoundRecord (+14 more)

### Community 5 - "Design Coverage and Damkohler Figures"
Cohesion: 0.10
Nodes (30): axial_egma_peaks.csv (peak dataset), Figure: Axial EGMA Intermediate Maxima (H2SO4 vs NaOH), Reactor Geometry A, Reactor Geometry B, H2SO4 Catalyst Branch, Finding: H2SO4 peaks pinned at outlet, NaOH peaks interior, NaOH Catalyst Branch, Peak EGMA Yield (+22 more)

### Community 6 - "README Figure Builder Script"
Cohesion: 0.23
Nodes (25): axial_egma_peaks(), consolidated_scenarios(), convert(), data_coverage(), derived_metrics(), duplicate_configs(), excluded_or_invalid_scenarios(), geometry_collapse_metrics() (+17 more)

### Community 7 - "SDL Parameter Space and Reporting"
Cohesion: 0.13
Nodes (32): campaign_history.csv per-round record, final_report.txt human-readable campaign summary, main(), StrategyResult, Short name of the scaled theta component for a natural key., theta_component_name(), campaign_score_pct(), log_mean_rel_error_pct() (+24 more)

### Community 8 - "SDL Campaign Entry and Self-Tests"
Cohesion: 0.10
Nodes (31): Truth/inference firewall, Truth-only systematic effects (transfer_time_s, calibration_gain), build_candidates(), build_fixed_design(), Full-factorial candidate grid over the feasible design space., Conventional campaign: temperature ladder at nominal flow/catalyst. `budget`…, literature_guess(), Initial estimates = Layer 1's literature-anchored kinetics for the chosen… (+23 more)

### Community 9 - "Batch Temperature Study and Run IO"
Cohesion: 0.13
Nodes (21): run_config.json + profiles.csv as the analysis input contract, main(), BATCH temperature studies of the PFR digital twin. Same physics and outputs as…, Index table plus the cross-scenario comparison figures (each + CSV)., Sweep every scenario, write per-scenario folders and the summary., run_batch(), _write_summary(), index_rows() (+13 more)

### Community 10 - "PFR Twin Plotting"
Cohesion: 0.21
Nodes (21): _end_label(), _legend(), _new_axes(), plot_concentration_profiles(), plot_conversion_yield(), plot_profile_overlay(), plot_scenario_bars(), plot_scenario_curves() (+13 more)

### Community 11 - "Analytical Reference Solutions"
Cohesion: 0.13
Nodes (18): analytical_profiles(), _bracketed_root(), equilibrium_state(), max_relative_error(), ndarray, Algebraic reference solutions used to verify the numerical integrator. 1.…, Composition at simultaneous chemical equilibrium of both steps. Solves for the…, Largest |numerical - analytical| across species, relative to `scale`. (+10 more)

### Community 12 - "Base-Case Simulation Runner"
Cohesion: 0.16
Nodes (15): Straight cylindrical tube; defaults match the 200 mm x 18 mm ID lab PFR., ReactorGeometry, SolverSettings, Integrate the plug-flow balances from x = 0 to x = L., simulate_pfr(), CaseOutcome, main(), Base-case run of the PFR digital twin (selectable catalyst system). Pipeline:… (+7 more)

### Community 13 - "Sulfuric Acid Bisulfate Speciation"
Cohesion: 0.15
Nodes (19): default_kinetics(), Literature-anchored KineticParameters for the chosen catalyst system. For…, aphi(), bisulfate_pitzer(), _g(), h_plus_concentration(), ka2_clarke_glew(), ka2_prs() (+11 more)

### Community 14 - "Inference Model and Fisher Information"
Cohesion: 0.14
Nodes (12): covariance_from_fim(), InferenceModel, ndarray, Central-difference S (m.size x p) in scaled parameter space., Expected FIM contribution of a candidate experiment, evaluated at the CURRENT…, V ~ F^-1, with uninformative directions given HUGE variance. np.linalg.pinv is…, Re-estimate theta from all accumulated data (warm start)., Measurement (+4 more)

### Community 15 - "Batch Scenario Expansion"
Cohesion: 0.17
Nodes (15): BatchSweep Analysis methods and interpretation README, Read-only post-processing layer over saved sweeps, expand(), _fmt(), get_path(), Any, Batch-study plumbing: turn lists of parameter values into a list of configs. A…, One point of a batch: a complete config plus the overrides applied. (+7 more)

### Community 16 - "Codex Graphify Feature Set"
Cohesion: 0.12
Nodes (16): URL Ingest via /graphify add (Codex), Folder Watch Auto-Rebuild (Codex), FalkorDB Cypher Export (Codex), graphify MCP stdio Server (Codex), Neo4j Cypher Export (Codex), GitHub Repo Clone (Codex), Cross-Repo Graph Merge (Codex), Native CLAUDE.md Integration (Codex) (+8 more)

### Community 17 - "Temperature Sweep Runner"
Cohesion: 0.21
Nodes (15): Write named equal-length numeric columns as a headed CSV., write_columns_csv(), build_kinetics(), KineticParameters for the configured catalyst system., main(), Temperature sensitivity study of the PFR digital twin. Sweeps the (isothermal)…, Everything one temperature sweep produces., Run the configured temperature sweep. Writes nothing. The inlet is re-mixed at… (+7 more)

### Community 18 - "PFR Result and Stoichiometry"
Cohesion: 0.17
Nodes (8): nu_matrix(), PFRResult, ndarray, Stoichiometric matrix of the chosen catalyst system., Axial profiles plus the scalars needed to interpret them., Fractional EGDA conversion X(x)., Yield of EGMA or EG on a diol-backbone basis: (C_i - C_i0)/C_EGDA0., Outlet selectivity of EGMA among converted EGDA.

### Community 19 - "Claude Graphify Feature Set"
Cohesion: 0.18
Nodes (15): /graphify Trigger Registration, FalkorDB Cypher Export, graphify MCP stdio Server, Neo4j Cypher Export, GitHub Repo Clone, Cross-Repo Graph Merge, Native CLAUDE.md Integration, BFS and DFS Traversal Modes (+7 more)

### Community 20 - "EGDA Reaction Network and Catalyst Routes"
Cohesion: 0.14
Nodes (15): Axial EGMA peak location and 95% plateau interval, Damköhler kinetic-exposure metric, Contrast with the packed-bed Amberlyst twin, Water as explicit reactant on the acid route, R. P. Bell, Acid–Base Catalysis, EGDA Digital Twin & Self-Driving Laboratory framework, Layer 1 — deterministic PFR digital twin, Layer 2 — virtual self-driving laboratory (+7 more)

### Community 21 - "MBDoE Theory and Epistemic Caveats"
Cohesion: 0.13
Nodes (15): Nearest-Damköhler geometry matching diagnostic, Local elasticities on the Arrhenius 1/T coordinate, What can and cannot be concluded from the sweeps, A/B/C/D four-strategy showcase, Synthetic CPR-NMR heteroscedastic correlated noise model, Fisher Information Matrix and Cramér–Rao bound, Franceschini & Macchietto (2008) MBDoE review, D-optimal Model-Based Design of Experiments (+7 more)

### Community 22 - "Plug-Flow Validity Diagnostics"
Cohesion: 0.28
Nodes (8): Transport/radial-mixing validity screen, flow_diagnostics(), Plug-flow validity diagnostics. A digital twin should say when its own…, Vogel-type correlation for liquid water, valid ~273-373 K., water_density_g_L(), water_viscosity_Pa_s(), Plug-flow validity diagnostics (Re, t_rad/tau, Bodenstein), Taylor–Aris dispersion in laminar tube flow

### Community 23 - "Layer 1 Bridge and Thermodynamic Tests"
Cohesion: 0.14
Nodes (16): The inverse problem — kinetics from noisy measurements, Reference-temperature (k_ref, Ea) reparameterization, greedy_d_optimal(), information_matrices(), _logdet_floored(), ndarray, Pre-campaign identifiability screen. Before a single experiment is spent, ask…, Per-condition information M_e = S_e' Sigma_e^-1 S_e at `theta_vec` (default:… (+8 more)

### Community 24 - "Detection, Cache and Update Flow"
Cohesion: 0.21
Nodes (13): URL Ingest via /graphify add, Token Reduction Benchmark, Monorepo Subfolder Extraction Flow, Whisper Video and Audio Transcription, Post-Update Graph Diff, Incremental --update Flow, Corpus Size Gate and Narrowing Prompt, Corpus File Detection (Step 2) (+5 more)

### Community 25 - "Extraction Spec and Honesty Rules"
Cohesion: 0.19
Nodes (13): Confidence Score Rubric, DEEP_MODE Aggressive Inference, Hyperedge Extraction Rule, Node ID Format Rule, Semantic Similarity Edge Rule, source_file Verbatim Rule, Extraction Subagent Prompt, Image Vision Extraction Rules (+5 more)

### Community 26 - "Batch Base-Case Simulation"
Cohesion: 0.17
Nodes (17): _fmt_secs(), main(), _progress(), BATCH base-case runs of the PFR digital twin. Same physics and outputs as…, Yield items with a tqdm-style progress bar (count, %, elapsed, ETA). Uses tqdm…, Simulate every scenario, write per-scenario folders and the summary., Index table plus the cross-scenario comparison figures (each + CSV)., Write the normal numerical outputs without constructing figures. (+9 more)

### Community 27 - "Kinetic Model Rate Laws"
Cohesion: 0.26
Nodes (6): KineticModel, kappa_i = k_i(T) * c_cat, the forward time-scale constants. c_cat is [H+] on…, Net rates (positive = ester-cleavage direction) for the state vector c in…, ndarray, Concentrations (mol/L) at axial positions z_m, flattened species-major: y[i*Nz…, Advance each port composition by dt_s of batch reaction (the batch time…

### Community 28 - "Text Progress Fallback"
Cohesion: 0.33
Nodes (3): Any, Minimal progress reporter used only when tqdm is unavailable., _TextProgress

### Community 29 - "Kinetic Parameter Provenance"
Cohesion: 0.40
Nodes (4): Layer 2 showcase: virtual self-driving laboratory around the Layer 1 PFR twin.…, resolve_outdir(), Corners (plus centre) of the admissible box - the most informative design the…, reference_design()

### Community 30 - "Feed Streams and Mixing"
Cohesion: 0.23
Nodes (8): mix_streams(), One feed stream to the micromixer. composition : mol/L of *solutes* (any of…, Flow-weighted ideal blending of the two feed streams. T_K is the (isothermal)…, Stream, KineticParameters, Acid route (catalyst = "H2SO4"), reversible rate laws (first order in each…, build_inlet(), Mixed inlet state at x = 0 from the two configured feed streams, with catalyst…

### Community 31 - "MBDoE Candidate Selector"
Cohesion: 0.14
Nodes (15): MBDoESelector, ndarray, Design score with FLOORED eigenvalues. `slogdet` returns -inf for any singular…, OperatingConditions, One experiment's controllable inputs (the vector u of the theory)., Per mole of catalyst, saponification must be orders of magnitude faster.…, Sub-stoichiometric NaOH: acetate released must equal the OH- consumed, the…, The bridge must speciate at each experiment's own temperature: with the default… (+7 more)

### Community 32 - "Parameter Space Scaling"
Cohesion: 0.20
Nodes (4): ndarray, Estimated components merged with the held-fixed ones, so the forward model…, Keys whose estimate is resting on its box constraint. A bounded least-squares…, Approximate 95% relative confidence half-widths, %, per parameter. For ln-…

### Community 33 - "Batch Results Analysis CLI"
Cohesion: 0.31
Nodes (8): main(), parse_args(), load_config(), _merge(), Any, Path, Large-sweep storage/detail degradation strategy, Namespace

### Community 34 - "Layer READMEs and Activity Models"
Cohesion: 0.24
Nodes (10): PFR digital twin layer README, Layer 1 Python dependencies (numpy, scipy, matplotlib), Bisulfate catalyst speciation ([H+] from HSO4-/SO4 2-), Hovey & Hepler (1990) bisulfate second-dissociation thermochemistry, Temperature-dependent Ka2 (Clarke–Glew constant-dCp), Pitzer ion-interaction activity model, Pitzer, Roy & Silvester (1977) ion-interaction parameters, Sippola & Taskinen (2014) Pitzer parameter refit for aqueous H2SO4 (+2 more)

### Community 35 - "Micromixer and Bisulfate Equilibrium"
Cohesion: 0.25
Nodes (8): bisulfate_equilibrium(), Ideal micromixer model. Stream 1 (aqueous EGDA) and Stream 2 (aqueous catalyst:…, [H+] for total sulfate molarity c_total, ideal activities (back-compat alias…, bisulfate_dilute(), [H+] (mol/L) for total sulfate molarity c_total with ideal activities. First…, Mixer rejection of acid/base cross-feeds, Ideal micromixer inlet reconstruction from pump dosing, Equal-flow dilution of pre-mixing stream concentrations

### Community 36 - "Arrhenius and Equilibrium Steps"
Cohesion: 0.13
Nodes (11): ArrheniusStep, EquilibriumStep, Single source of truth for every physical, chemical, and operational parameter.…, k(T) = A * exp(-Ea / (R T)) with A in L/(mol s) and Ea in J/mol., Concentration-based hydrolysis equilibrium constant of one step, K(T) = (…, Berthelot & Péan de Saint-Gilles (1862) esterification equilibrium, A. J. Kirby, Comprehensive Chemical Kinetics Vol. 10, Literature-anchored kinetic parameter provenance (+3 more)

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
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

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
- **Why does `default_kinetics()` connect `Sulfuric Acid Bisulfate Speciation` to `BatchSweep IO and Pipeline Core`, `Arrhenius and Equilibrium Steps`, `SDL Campaign Entry and Self-Tests`, `Analytical Reference Solutions`, `Base-Case Simulation Runner`, `Temperature Sweep Runner`, `Feed Streams and Mixing`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._