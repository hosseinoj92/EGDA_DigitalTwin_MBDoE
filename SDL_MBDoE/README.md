# Layer 2 — Virtual Self-Driving Laboratory (MBDoE) around the PFR Twin

> Project overview, the full mathematical background, and a first-time user
> manual for both layers live in the [top-level README](../README.md).

A virtual autonomous kinetic-discovery framework built **around** the Layer 1
PFR digital twin (`../PFR_H2SO4_digital_twin`) — the **catalyst-selectable**
twin (H₂SO₄: reversible hydrolysis/esterification; NaOH: irreversible
saponification with stoichiometric OH⁻ consumption) — which is treated as an
immutable, hidden, high-fidelity reactor. Layer 1 is not modified in any way
by this layer. `CONFIG["catalyst"]` switches the whole campaign, including
the estimated parameter set (6 acid / 4 base), the design space, and the
hidden truth.

The closed loop is the classic self-driving-laboratory cycle:

```
select operating condition ─► run virtual PFR ─► generate CPR–NMR profile
        ▲                                                   │
        └── evaluate candidate experiments ◄── estimate kinetics & uncertainty
```

## Truth / inference firewall

| Side | Module | Contains |
|---|---|---|
| **Virtual truth** | [sdl/truth.py](sdl/truth.py) | hidden parameter vector (private), Layer 1 simulator, sampling ports, synthetic NMR noise, optional systematic effects |
| **Inference** | [sdl/inference.py](sdl/inference.py) | current estimates, bounds, forward-model adapter, accumulated measurements, *assumed* covariance, sensitivities / FIM |

The estimation and design algorithms interact with the truth **only** through
`VirtualLaboratory.run_experiment()`, which returns noisy measurements.
`reveal_truth()` is called once, after all campaigns end, for benchmarking —
the call counter is reported and asserted zero-during-loop in the tests.

## Mathematical machinery (see the concept document)

- Measurement vector, species-major: `y[i·Nz + k] = C_i(z_k)`.
- Noise: σ = σ_abs + σ_rel·C, optional correlated EGDA↔EGMA errors
  (overlapping acetyl resonances at 80 MHz) via ρ_overlap → full Σ_y.
- Estimation: weighted least squares, residuals whitened per experiment with
  the Cholesky factor of the assumed Σ_y (`scipy.optimize.least_squares`).
- Parameterization (H₂SO₄): θ = [ln k₁_ref, Eₐ₁, ln k₂_ref, Eₐ₂, ln K₁_ref,
  ln K₂_ref] with k(T) = k_ref·exp[−(Eₐ/R)(1/T − 1/T_ref)] and the hydrolysis
  equilibrium constants K(T) = K_ref·exp[−(ΔH/R)(1/T − 1/T_ref)],
  T_ref = 60 °C — decorrelates the Arrhenius pair; the bridge converts to
  Layer 1 (A, Eₐ) + EquilibriumStep form. The near-athermal van 't Hoff
  slopes ΔH are fixed at their literature values (unidentifiable over
  30–90 °C), so the campaign learns six parameters: two rate constants, two
  activation energies, and two equilibrium constants. The K's are informed
  only by near-equilibrium data (hot, slow, high-acid conditions), which is
  exactly the kind of experiment MBDoE learns to request.
- Parameterization (NaOH): θ = [ln k₁_ref, Eₐ₁, ln k₂_ref, Eₐ₂] — no Keq
  exists (saponification is irreversible). Here the challenge is inverted:
  the reaction is ~1000× faster, so outlet data mostly encode the
  *stoichiometric endpoint* (OH⁻ exhaustion), not the kinetics; MBDoE
  responds by requesting cold (10 °C), fast-flow (40 mL/min) conditions
  that push the transient back into the observable window.
- Sensitivities S by central finite differences; Fisher information
  F = Σₑ Sₑᵀ Σₑ⁻¹ Sₑ; parameter covariance V ≈ F⁻¹; correlation matrix and
  FIM eigen-spectrum reported for identifiability diagnosis.
- MBDoE: D-optimal — pick the candidate u maximizing
  log det(F_current + F_candidate(θ̂, u)) over a feasible grid
  (T × total flow × catalyst molarity; on the NaOH route the catalyst
  molarity doubles as the OH⁻/acetate stoichiometric-ratio axis).
  A-optimality available via config.

## The showcase: strategies A–D

| Strategy | Measurements | Selection | Demonstrates |
|---|---|---|---|
| A | outlet only (4 obs/exp) | fixed T-ladder | baseline |
| B | 8-port spatial profile (32 obs/exp) | fixed T-ladder | information gain of spatial profiling |
| C | outlet only | autonomous MBDoE | efficiency gain of MBDoE |
| D | spatial profile | autonomous MBDoE | combined advantage |

All strategies share the same hidden truth, initial guess (Layer 1 literature
kinetics), first experiment, and budget.

Typical H₂SO₄ result (seed 7, 8 experiments, 6 parameters): mean |rel. error|
16.8 % (A) → 5.9 % (B) → 30.8 % (C) → **8.0 % (D)**, with log det F increasing
17.5 → 27.6 → 20.4 → **32.5**. The worst-case CI is dominated by K₁_ref, which
is informed only by near-equilibrium data: the fixed T-ladder (A/B) never
leaves the nominal flow, while MBDoE (D) autonomously requests the hot, slow,
high-acid conditions (90 °C, 4 mL/min) that pin the equilibrium constants
down (K₁: 1.07 [0.60, 1.91] vs truth 0.80; K₂: 0.133 [0.120, 0.148] vs truth
0.12).

Typical NaOH result (seed 7, 8 experiments, 4 parameters): the fast
saponification makes outlet-only fixed designs nearly uninformative for
k₁/Eₐ₁ (strategy A ends with corr(ln k₁, Eₐ₁) = 0.998 and an unbounded CI —
the outlet only sees the OH⁻-exhaustion endpoint), while MBDoE + spatial (D)
requests cold, fast-flow experiments (10 °C, 40 mL/min) and recovers all four
parameters to **2.0 % mean error, max CI 10 %** (log det F 19.2).

The D-criterion plot is the clean information measure; the parameter-error
plot depends on the specific noise realization (change `seed` to see other
draws).

## Usage (IDE workflow)

Open [run_sdl_campaign.py](run_sdl_campaign.py), edit the `CONFIG` dictionary
at the top (hidden truth, noise, ports, budget, design space, systematics),
press Run. Runtime ≈ 20–60 s for the default budget. Outputs in `results/`:

| File | Content |
|---|---|
| `convergence_error.png` | true parameter error vs experiment count, A–D |
| `convergence_uncertainty.png` | D-criterion (joint uncertainty) vs experiment count |
| `final_estimates.png` | final estimates ± 95 % CI vs hidden truth, per parameter |
| `validation_profiles.png` | predictive check at an unseen condition |
| `campaign_history.csv` | every round of every strategy, machine-readable |
| `final_report.txt` | estimates, CIs, correlation matrices, FIM eigenvalues, chosen experiments |

Tests: `python tests/self_test.py` (also pytest-compatible) — forward-engine
consistency (irreversible limit), thermodynamic consistency (net rates vanish
at the coupled equilibrium), long-residence approach to the algebraic
equilibrium state with invariant conservation, NaOH route physics (~1000×
rate-constant ratio vs acid, limiting-reagent self-quench, saponification
invariants, 4-D parameter space), truth firewall, FIM positive-definiteness,
low-noise recovery of all six acid-route parameters, measurement shapes.

## Package layout

```
sdl/
├── layer1_bridge.py   ONLY module importing Layer 1; θ ↔ KineticParameters,
│                      u ↔ streams/mixer, concentrations at sampling ports
├── parameters.py      θ parameter space, transforms, bounds, CI interpretation
├── observation.py     measurement vector layout + NoiseModel → Σ_y
├── truth.py           VirtualLaboratory (hidden truth + synthetic NMR)
├── inference.py       WLS estimation, S, F = SᵀΣ⁻¹S, V ≈ F⁻¹
├── design.py          fixed designs + D-optimal MBDoE selector
├── campaign.py        closed-loop runner, strategies A–D
└── reporting.py       showcase figures, CSV, final report (only truth consumer)
run_sdl_campaign.py    entry point with CONFIG dict
tests/self_test.py     standalone + pytest-compatible tests
```

## Extension hooks already in place

- `transfer_time_s` — sample keeps reacting in the transfer line (truth only):
  study bias from unmodelled sampling transport.
- `calibration_gain` — per-species multiplicative NMR bias (truth only).
- `noise_assumed` vs `noise_true` — mis-specified covariance robustness.
- `catalyst: "NaOH"` — switch the entire campaign to the saponification
  route (4-parameter estimation, colder/faster design space, OH⁻/acetate
  stoichiometric ratio as a design axis).
- `forward_engine: "analytical"` — exact closed-form forward model for fast
  large-scale studies; valid only on the acid route with `reversible: False`
  (the reversible ODEs are bilinear and the NaOH route has a depleting
  reagent — neither has a closed form). Verified against the ODE engine in
  the tests.
- `reversible: False` — legacy irreversible acid twin for back-to-back
  comparisons of what neglecting the esterification back-reactions does to
  the identified kinetics.
- `mbdoe_criterion: "A"` — A-optimal design as an alternative to D-optimal.
