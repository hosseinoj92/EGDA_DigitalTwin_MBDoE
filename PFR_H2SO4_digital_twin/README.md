# PFR Digital Twin — Homogeneous EGDA Cleavage (H₂SO₄ or NaOH)

A 1D deterministic, steady-state digital twin of an **isothermal plug flow
reactor** performing the liquid-phase cleavage of ethylene glycol diacetate
(EGDA) with a **selectable homogeneous catalyst system** dosed through an
ideal micromixer: sulfuric acid (reversible hydrolysis) or sodium hydroxide
(irreversible saponification, ~1000× faster per mole of catalyst). Unlike
the packed-bed / Amberlyst twin in `../EDGA_digital_twin_labscale`, both
routes here are homogeneous.

## Physical setup

```
Stream 1 (aq. EGDA)         ──┐
                              ├──► ideal micromixer ──► x = 0 ── isothermal PFR ── x = L
Stream 2 (aq. H₂SO₄ or NaOH)──┘        (instant,           (200 mm × 18 mm ID
                                        perfect mixing)     by default)
```

## Reaction network and rate laws

### Route 1 — H₂SO₄ (`catalyst: "H2SO4"`)

Two-step series hydrolysis, **reversible** (A-AC2 forward, Fischer
esterification reverse — the same H⁺ catalyzes both directions):

1. EGDA + H₂O ⇌ EGMA + AcOH  r₁ = k₁(T)·[H⁺]·([EGDA][H₂O] − [EGMA][AcOH]/K₁(T))/C_w,ref
2. EGMA + H₂O ⇌ EG + AcOH  r₂ = k₂(T)·[H⁺]·([EGMA][H₂O] − [EG][AcOH]/K₂(T))/C_w,ref

- **Thermodynamic consistency by construction** — the reverse rate constants
  are *derived* from the equilibrium constants,
  k_rev,i = k_i/(K_i·C_w,ref), so each net rate vanishes exactly at Q_i = K_i
  (microscopic reversibility); the model cannot violate thermodynamics for
  any parameter values. C_w,ref = 55.34 M (pure water) makes the forward
  term reduce to the legacy pseudo-first-order law in dilute solution, so
  k₁, k₂ keep their literature calibration and units.
- **Water is an explicit reactant** — its consumption slows the forward rate
  and its level shifts the equilibrium; concentrated / low-water feeds and
  even esterification-direction operation (feeding EG + AcOH) are handled
  correctly.
- **Legacy limit** — `reversible: False` in the CONFIG recovers the old
  irreversible pseudo-first-order model (exactly linear, closed-form
  solution), which remains the solver-verification reference.
- **[H⁺] constant along x** — the catalyst is not consumed. It is computed
  from the mixed [H₂SO₄] via the HSO₄⁻/SO₄²⁻ equilibrium (or a stoichiometric
  factor). AcOH (pKa 4.76) adds negligible H⁺ against the strong-acid
  background. **The speciation is temperature-dependent and, optionally,
  non-ideal:** Ka₂ collapses ~100× from 25 → 150 °C (`ka2_model: "tdep"`,
  Clarke–Glew / Hovey–Hepler), and at molar acid a Pitzer activity model
  (`activity_model: "pitzer"`) captures the non-ideality the dilute formula
  misses. See the [top-level README §3.4](../README.md#34-catalyst-speciation)
  and [`pfr_twin/speciation.py`](pfr_twin/speciation.py).

### Route 2 — NaOH (`catalyst: "NaOH"`), saponification

1. EGDA + OH⁻ → EGMA + AcO⁻  r₁ = k₁(T)·[OH⁻]·[EGDA]
2. EGMA + OH⁻ → EG + AcO⁻  r₂ = k₂(T)·[OH⁻]·[EGMA]

Chemically a different reaction (B-AC2), with three modelled consequences:

- **~1000× faster per mole of catalyst** — the ethyl acetate + NaOH
  benchmark is k ≈ 0.11 L mol⁻¹ s⁻¹ at 25 °C with Eₐ ≈ 46–48 kJ/mol, vs
  ≈ 1.1 × 10⁻⁴ for the acid-catalyzed route.
- **Not catalytic** — the leaving carboxylate is instantly the acetate ion
  (pKa 4.76 ≪ 15.7), so **one OH⁻ is consumed per acetate group released**.
  [OH⁻] is a *state variable*: the reaction self-quenches when NaOH is
  sub-stoichiometric (conversion ceiling = NaOH / acetate groups), which the
  twin reports as limiting-reagent diagnostics. The tracked "AcOH" pool is
  then total acetate (AcO⁻/NaOAc).
- **Irreversible** — carboxylate + alcohol do not re-esterify and the
  acid–base step is ~10⁹-fold downhill, so no equilibrium terms exist; net
  water consumption is zero (OH⁻ is the nucleophile).

Feeding free AcOH together with NaOH, or acid/base cross-feeds, are rejected
by the mixer (instant neutralization is not modelled).

## Governing equations (steady state, constant density)

With superficial velocity u = Q/A and residence coordinate τ = x/u:

```
u·dC_EGDA/dx = −r₁               u·dC_AcOH/dx = +r₁ + r₂
u·dC_EGMA/dx = +r₁ − r₂          u·dC_H₂O/dx  = −r₁ − r₂
u·dC_EG/dx   = +r₂
```

Integrated with `scipy.solve_ivp` (LSODA, rtol 1e-9) and **verified on every
run** in three ways: (1) against the closed-form solution in the exactly
linear irreversible limit (PASS threshold 1e-6), (2) conservation of the
three linear invariants (diol backbone, acetate groups, water + AcOH), and
(3) thermodynamic consistency — the net rates evaluated at the
coupled-equilibrium composition (from the algebraic equilibrium solver in
`analytical.py`) must vanish to machine precision.

## Kinetic parameters (literature-anchored estimates)

| Step | A (L mol⁻¹ s⁻¹) | Eₐ (kJ/mol) | k at 25 °C (L mol⁻¹ s⁻¹) | K_hyd at 25 °C (–) | ΔH_hyd (kJ/mol) |
|------|-----------------|-------------|---------------------------|--------------------|------------------|
| 1: EGDA ⇌ EGMA | 1.0 × 10⁶ | 55.0 | 2.27 × 10⁻⁴ | 0.50 | +5 |
| 2: EGMA ⇌ EG | 1.0 × 10⁶ | 57.0 | 1.03 × 10⁻⁴ | 0.125 | +5 |

Rate constants anchored to classic data for the specific acid-catalyzed
hydrolysis of acetate esters in water (ethyl acetate + HCl:
k ≈ 1.1 × 10⁻⁴ L mol⁻¹ s⁻¹ at 25 °C, Eₐ ≈ 54–65 kJ/mol), with a statistical
factor ≈ 2 for the diester's two equivalent acetate groups. Equilibrium
constants anchored to the classic acetate-esterification equilibrium
(K_est ≈ 4 per ester group, Berthelot & Péan de Saint-Gilles ⇒ hydrolysis
K_g ≈ 0.25; Δn = 0 so concentration and mole-fraction constants coincide)
with the same statistical factors: K₁ = 2K_g = 0.50, K₂ = K_g/2 = 0.125
(so K₁K₂ = K_g²). Esterification is nearly thermoneutral ⇒ small positive
van 't Hoff slope (+5 kJ/mol) for the hydrolysis direction. **These are
order-of-magnitude estimates** — recalibrate A/Eₐ/K_ref/ΔH against your lab
data before quantitative use. Provenance notes live in
[pfr_twin/parameters.py](pfr_twin/parameters.py).

At ~50 M water the equilibria still lie far to the hydrolysis side, but the
reverse terms cap the ultimate conversion (X_eq ≈ 99.7 % for the base case),
leave a persistent EGMA fraction at equilibrium (Y_EGMA,eq ≈ 11 % at 70 °C),
and slow the net rate as AcOH accumulates — the few-percent effects a
digital twin must capture near high conversion.

## What makes it a *twin* rather than a textbook exercise

- Inlet reconstructed from real dosing (two pump flows + stream molarities),
  including water molarity from stream densities.
- Bisulfate second-dissociation equilibrium for the true catalytic [H⁺].
- Plug-flow **validity diagnostics** on every run: Reynolds number, radial
  diffusion time vs residence time, Taylor–Aris dispersion / Bodenstein
  number when applicable — the twin tells you when its own idealization is
  optimistic for the given geometry and flow.
- Solver verification against the analytical solution on every run.

## Usage (IDE workflow)

> A full first-time manual — including every CONFIG parameter, worked
> examples, and troubleshooting — is in the
> [top-level README](../README.md#5-user-manual).

**Single runs** define all study parameters in a **`CONFIG` dictionary at the
top of the file** — edit the values there and press Run in the IDE:

- `run_simulation.py` — one operating point: profiles, KPIs, diagnostics,
  verification.
- `run_temperature_study.py` — a temperature sweep finding the EGMA
  series-reaction optimum, plus an EGMA axial-profile overlay at
  `profile_temps_C`.

**Batch runs** replace hand-editing with lists of values (`BASE` + `VARY` +
`MODE`), running every scenario in one go and adding cross-scenario
comparison figures/tables:

- `batch_simulation.py` — many base cases.
- `batch_temperature_study.py` — many temperature sweeps.

`VARY` maps dotted parameter paths to value lists, e.g.
`{"temp_C": [70, 100, 130], "reactor.length_m": [0.06, 0.20]}`; `MODE` is
`"grid"` (full factorial) or `"zip"` (paired lists). The batch scripts import
the single-run functions, so the physics has exactly one implementation.

Dependencies: `pip install -r requirements.txt` (numpy, scipy, matplotlib).

## Outputs

Every run writes into a folder whose **name encodes its hyperparameters**, so
scenarios never overwrite each other, and **every figure is accompanied by a
CSV of exactly the plotted data**:

```
results/base_case__cat-H2SO4_rev_T150C_L60mm_ID4mm_EGDA0.5M_cat1.5M_Q0.5+0.5/
```

| File | Content |
|------|---------|
| `concentration_profiles.png` / `.csv` | species along the reactor (+ equilibrium levels; OH⁻ on the NaOH route) |
| `conversion_yield.png` / `.csv` | X_EGDA, Y_EGMA, Y_EG vs x |
| `solver_validation.png` / `.csv` | numerical vs reference solution |
| `temperature_sweep.png` / `.csv` | outlet KPIs vs T, EGMA optimum annotated |
| `egma_profiles_vs_T.png` / `.csv` | EGMA axial profiles at selected temperatures |
| `profiles.csv` | full axial table: x, τ, all concentrations, X, yields |
| `summary.txt` | inlet state, diagnostics, outlet KPIs, verification block |
| `run_config.json` | the exact configuration + computed metrics |

Batch runs add a `_batch_summary/` folder with `scenario_index.csv` (one row
per scenario: varied parameters + all KPIs + folder name) and the
cross-scenario comparison figures, each with its paired CSV.

## Package layout

```
pfr_twin/
├── parameters.py    all constants & dataclasses (single source of truth)
├── mixer.py         ideal micromixer → inlet state (speciation at reactor T)
├── speciation.py    Ka₂(T) Clarke–Glew + Pitzer activity model for H₂SO₄
├── kinetics.py      Arrhenius/van 't Hoff constants and reversible net-rate laws
├── reactor.py       1D PFR integration + result object (incl. equilibrium metrics)
├── analytical.py    closed-form irreversible-limit solution + coupled-equilibrium solver
├── diagnostics.py   Re / dispersion / plug-flow validity advisories
├── plotting.py      styled figures, each writing its paired data CSV
├── runio.py         hyperparameter-tagged run folders + CSV writers
└── batch.py         parameter-grid expansion for the batch scripts
run_simulation.py            single base case   (CONFIG at top)
run_temperature_study.py     single T sweep     (CONFIG at top)
batch_simulation.py          many base cases    (BASE + VARY + MODE)
batch_temperature_study.py   many T sweeps      (BASE + VARY + MODE)
```

## Key assumptions (recap)

1. Instant, perfect micromixing; volumetric flows additive.
2. Isothermal reactor (feed pre-heated to T; hydrolysis heat neglected).
3. Ideal plug flow — but diagnostics quantify how good that assumption is.
4. Constant liquid density; dilute aqueous physical properties ≈ water.
5. Reversible hydrolysis/esterification with concentration-based equilibrium
   constants (ideal-solution activities; activity-coefficient corrections
   lumped into K_ref, dH — recalibrate against lab data).
6. Bisulfate Ka₂ is temperature-dependent by default (`ka2_model: "tdep"`);
   activity coefficients are optional (`activity_model: "pitzer"` for molar
   acid). The rate law consumes the resulting `[H⁺]` concentration —
   Hammett-acidity corrections to the rate law in very concentrated acid are
   not modelled.
