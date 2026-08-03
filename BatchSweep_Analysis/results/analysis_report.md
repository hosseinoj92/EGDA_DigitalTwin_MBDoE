# Comprehensive batch-sweep analysis

## Executive summary

This report analyzes **3,000 loaded scenarios** directly from the saved `run_config.json` and `profiles.csv` files under `C:\Users\vt4ho\Simulations\kinetics_sim\EDGA\Homogenous_RESULTS\BatchSweep`. The reactor simulations were not rerun and no source result was changed.

All discovered scenario configurations had readable, schema-complete axial profiles; no scenario was excluded during loading.
Configuration-level duplicate records found: **0**.

The strongest conclusions are physics-first: temperature and residence time enter the kinetic exposure through the Damköhler numbers; catalyst/feed stoichiometry is additionally decisive for the consumed-NaOH route; and EGMA is an intermediate, so high conversion can reduce EGMA selectivity by pushing material onward to EG.

## Coverage and comparability

| Route | Geometry | Cases | Temperature levels (°C) | Feed concentration levels | Catalyst levels | Total-flow levels (mL/min) |
|---|---:|---:|---|---|---|---|
| H2SO4 | A | 1000 | [25.0, 40.0, 60.0, 80.0, 100.0, 120.0, 140.0, 160.0] | [0.1, 0.2, 0.3, 0.4, 0.5] | [0.1, 0.2, 0.3, 0.4, 0.5] | [2.0, 4.0, 6.0, 8.0, 10.0] |
| H2SO4 | B | 500 | [25.0, 40.0, 60.0, 80.0] | [0.1, 0.2, 0.3, 0.4, 0.5] | [0.1, 0.2, 0.3, 0.4, 0.5] | [2.0, 4.0, 6.0, 8.0, 10.0] |
| NaOH | A | 1000 | [25.0, 40.0, 60.0, 80.0, 100.0, 120.0, 140.0, 160.0] | [0.1, 0.2, 0.3, 0.4, 0.5] | [0.1, 0.2, 0.3, 0.4, 0.5] | [2.0, 4.0, 6.0, 8.0, 10.0] |
| NaOH | B | 500 | [25.0, 40.0, 60.0, 80.0] | [0.1, 0.2, 0.3, 0.4, 0.5] | [0.1, 0.2, 0.3, 0.4, 0.5] | [2.0, 4.0, 6.0, 8.0, 10.0] |

Every individual study is a complete balanced factorial grid over its own observed levels, so the discrete functional-ANOVA decomposition is exact and descriptive. Geometry A covers 25–160 °C; geometry B covers only 25–80 °C. Therefore, raw whole-grid geometry averages are not like-for-like comparisons.

Both stream flows are linked and equal in every loaded scenario. Consequently, the two individual flow effects cannot be identified separately: the analysis treats their sum as the flow factor and the mixed-stream dilution remains fixed at 1:1.

## Main statistical patterns

- **H2SO4, geometry A:** Y_EGMA main-effect variance fractions are temp_C (65.1%), Q_total_mL_min (8.5%), C_catalyst_feed_M (5.6%), C_EGDA_feed_M (0.0%). Interaction and higher-order components are reported separately and the reconstruction residual is numerical round-off.
- **H2SO4, geometry B:** Y_EGMA main-effect variance fractions are temp_C (68.1%), Q_total_mL_min (11.6%), C_catalyst_feed_M (9.6%), C_EGDA_feed_M (0.0%). Interaction and higher-order components are reported separately and the reconstruction residual is numerical round-off.
- **NaOH, geometry A:** Y_EGMA main-effect variance fractions are temp_C (11.1%), C_EGDA_feed_M (9.8%), C_catalyst_feed_M (5.6%), Q_total_mL_min (0.5%). Interaction and higher-order components are reported separately and the reconstruction residual is numerical round-off.
- **NaOH, geometry B:** Y_EGMA main-effect variance fractions are C_EGDA_feed_M (33.4%), C_catalyst_feed_M (4.2%), temp_C (0.5%), Q_total_mL_min (0.1%). Interaction and higher-order components are reported separately and the reconstruction residual is numerical round-off.

These percentages describe variation over the chosen discrete grid; they are not universal causal importance scores and should not be interpreted as p-values.

The polynomial response surfaces use linear, quadratic, and all two-factor interaction terms. Validation holds out one complete factor level at a time, which is a more demanding interpolation/extrapolation check than a random split.

- **H2SO4, geometry A:** median held-level-out Y_EGMA RMSE = 0.02426; median R² = 0.8962 and worst R² = -2.239e+04. Negative boundary-fold R² values mean that fold is worse than predicting its held-out mean; use the surrogate only where the fold-specific errors are acceptable.
- **H2SO4, geometry B:** median held-level-out Y_EGMA RMSE = 0.03501; median R² = 0.9462 and worst R² = -2.331. Negative boundary-fold R² values mean that fold is worse than predicting its held-out mean; use the surrogate only where the fold-specific errors are acceptable.
- **NaOH, geometry A:** median held-level-out Y_EGMA RMSE = 0.1022; median R² = 0.5324 and worst R² = -1.305. Negative boundary-fold R² values mean that fold is worse than predicting its held-out mean; use the surrogate only where the fold-specific errors are acceptable.
- **NaOH, geometry B:** median held-level-out Y_EGMA RMSE = 0.09433; median R² = 0.7344 and worst R² = -0.7471. Negative boundary-fold R² values mean that fold is worse than predicting its held-out mean; use the surrogate only where the fold-specific errors are acceptable.

## EGMA peak behavior

- **H2SO4, geometry A:** 2/1000 scenarios have an interior concentration peak, 998/1000 peak at the outlet, and 998/1000 are still increasing at the outlet. Interior peaks identify conditions where a shorter residence time can preserve more EGMA before the second cleavage step.
- **H2SO4, geometry B:** 18/500 scenarios have an interior concentration peak, 482/500 peak at the outlet, and 482/500 are still increasing at the outlet. Interior peaks identify conditions where a shorter residence time can preserve more EGMA before the second cleavage step.
- **NaOH, geometry A:** 522/1000 scenarios have an interior concentration peak, 478/1000 peak at the outlet, and 478/1000 are still increasing at the outlet. Interior peaks identify conditions where a shorter residence time can preserve more EGMA before the second cleavage step.
- **NaOH, geometry B:** 444/500 scenarios have an interior concentration peak, 56/500 peak at the outlet, and 56/500 are still increasing at the outlet. Interior peaks identify conditions where a shorter residence time can preserve more EGMA before the second cleavage step.

## Route-specific physics

- **NaOH:** hydroxide is a consumed stoichiometric reagent, not a conserved catalyst. 600/1500 cases start below one OH equivalent per EGDA and 779/1500 finish with ≤1% of inlet OH remaining. `R_OH`, residual OH, utilization, and stoichiometric ceilings should be considered alongside Damköhler numbers.
- **H₂SO₄:** the saved model uses reversible hydrolysis/esterification and conserves acid as a catalyst. 5/1500 cases reach at least 90% on one outlet equilibrium-proximity indicator. Q/K values distinguish equilibrium limitation from insufficient kinetic exposure.

## Pareto sets, top conditions, and robust windows

- **H2SO4, geometry A:** 997 exact Pareto scenarios and 0 threshold/neighbor-robust scenarios. The highest transparent screening score has T=160 °C, total flow=6 mL/min, feed EGDA=0.5 M, catalyst=0.5 M, Y_EGMA=0.3059, and STY=36.52 mol L-reactor⁻¹ h⁻¹. This point requires pressurization under the configured temperature screen.
- **H2SO4, geometry B:** 483 exact Pareto scenarios and 18 threshold/neighbor-robust scenarios. The highest transparent screening score has T=80 °C, total flow=10 mL/min, feed EGDA=0.5 M, catalyst=0.5 M, Y_EGMA=0.3638, and STY=1.072 mol L-reactor⁻¹ h⁻¹.
- **NaOH, geometry A:** 431 exact Pareto scenarios and 85 threshold/neighbor-robust scenarios. The highest transparent screening score has T=80 °C, total flow=10 mL/min, feed EGDA=0.5 M, catalyst=0.5 M, Y_EGMA=0.4964, and STY=98.76 mol L-reactor⁻¹ h⁻¹.
- **NaOH, geometry B:** 73 exact Pareto scenarios and 105 threshold/neighbor-robust scenarios. The highest transparent screening score has T=25 °C, total flow=10 mL/min, feed EGDA=0.5 M, catalyst=0.5 M, Y_EGMA=0.5218, and STY=1.538 mol L-reactor⁻¹ h⁻¹.

The top-condition score is explicitly a screening preference, not a fitted optimum. The exact Pareto table is the appropriate output when objective weights are not agreed; because seven objectives are used, a large nondominated set is expected and should be narrowed only after priorities are chosen. Robust-window membership depends on the thresholds recorded in `analysis_config.json`.

## Geometry-collapse assessment

There are 1000 one-to-one cross-geometry matches at common route, temperature, and feed concentrations. Only 0 are exact Da₁ matches; the median |log(Da₁,B/Da₁,A)| is 4.212, and the median absolute paired EGMA-yield difference is 0.1025.

Because the existing flow ranges do not generally give equal residence time or Da₁ in the two geometries, this is a nearest-dimensionless-exposure diagnostic, not proof of a geometry effect. A dedicated matched-Da experiment would be required for a clean collapse test.

## Model-validity and interpretation limits

Transport advisories across all scenarios: radially_segregated=3000. Conditions above the configured atmospheric-boiling screen occur in 750/3000 cases.

- The simulated reactor is an empty, ideal homogeneous tube. It is **not** a bead-packed bed; no porosity, tortuosity, pressure drop, external film transfer, or intraparticle diffusion is modeled.
- Reynolds, radial-diffusion, Taylor–Aris, and Bodenstein diagnostics are applicability screens. They do not correct the ideal-PFR predictions.
- Temperatures above 100 °C require a suitable pressurized liquid-phase setup under the default screen. The analysis flags them and does not assume such hardware exists.
- H₂SO₄ Ka₂ temperature/activity behavior is whatever was encoded in each saved run configuration and current simulator kinetics. This analysis does not refit Ka₂ or kinetic parameters.
- The H₂SO₄ route is reversible in these configurations. The NaOH route is intentionally irreversible because saponification consumes OH and is pulled toward carboxylate products.
- No experimental uncertainty, parameter uncertainty, replicate noise, or statistical sampling process is present. Therefore no significance tests, confidence intervals, or causal claims are made.
- Local elasticities are finite differences on the available grid. Temperature derivatives use 1/T as requested; boundary estimates are one-sided and can be less stable.
- The surrogate is an interpretable response surface, not a replacement for the mechanistic simulator and not evidence outside the swept domain.

## Output guide

The root CSV files contain the auditable scenario table, derivations, exclusions, factorial effects, elasticities, validation, regimes, peaks, geometry matching, Pareto sets, top conditions, and robust windows. Each PNG in `figures/` has a same-named CSV containing exactly the plotted data.

Generated figures: coverage_by_study, dimensionless_response_collapse, main_effects_yegma, pareto_yield_vs_sty, axial_egma_peak_location, regime_counts, temperature_flow_response, pfr_validity_diagnostics.
