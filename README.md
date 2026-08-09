# EGDA Autonomous Kinetics Framework — Digital Twin, Self-Driving Laboratory & CPR–NMR Virtual Instrument

A three-layer computational framework for the **homogeneously catalyzed cleavage
of ethylene glycol diacetate (EGDA)** in a continuous tubular reactor, built to
simulate — end to end and with quantified realism — the eventual autonomous
kinetic-modeling platform: a **Reacnostics compact profile reactor (CPR)** with
one axially moving sampling capillary, coupled to a **Bruker Fourier 80**
benchtop NMR.

| Layer | Directory | What it is |
|---|---|---|
| **Layer 1** | [`PFR_H2SO4_digital_twin/`](PFR_H2SO4_digital_twin/) | A deterministic **digital twin** of the reactor — given operating conditions, it predicts what comes out. The single authoritative source of chemistry. |
| **Layer 2** | [`SDL_MBDoE/sdl/`](SDL_MBDoE/) | A **virtual self-driving laboratory** wrapped around Layer 1 — it designs its own experiments to *learn* the kinetics it does not know (strategies A–D, preserved unchanged as the regression baseline). |
| **Layer 3** | [`SDL_MBDoE/sdl_advanced/`](SDL_MBDoE/sdl_advanced/) | A **realistic virtual instrument and Bayesian controller**: spatially continuous capillary sampling, sample transport with dispersion and carryover, synthetic 80 MHz ¹H NMR spectra, automated spectral deconvolution with honest covariances, multi-model Bayesian inference, a model-inadequacy governor, and resource-aware experiment design (strategies E–F + ablations). |

Layer 1 answers *"what will the reactor do?"*. Layer 2 answers *"how do I find
out, with the fewest experiments?"*. Layer 3 answers the question the real
machine will face: *"how do I find out when all I ever see is an imperfect NMR
spectrum of a sample that traveled through a real transfer line — and how do I
notice when my model itself is wrong?"*

Everything below is a **simulation**. No real CPR–NMR measurements exist yet.
The architecture is deliberately modular so that, when the hardware arrives,
the simulated spectra can be replaced by real Fourier 80 data without touching
the inference or design code (see §8).

### Results at a glance

The current reference result is the **v3 publication benchmark**: 11 scenarios
× 40 common-random-number seeds × budget 8, 1 320 closed-loop campaigns, 9 h of
compute, in [`SDL_MBDoE/results_advanced_v3/publication/`](SDL_MBDoE/results_advanced_v3/publication/).
Full analysis in [§6](#6-benchmark-results).

![Headline benchmark](SDL_MBDoE/results_advanced_v3/publication/figure_readme_headline.png)

| Claim | Evidence |
|---|---|
| Measurement-awareness matters most when the measurement is real | ideal 10.4 %→5.8 % param error, but NMR 41.5 %→16.7 % and transport 36.8 %→10.6 % (§6.1) |
| Sophisticated statistics on an unmodeled transfer line are **worse than naive** | F-uncorr 48.3 % vs D 36.8 %; modeling only the mean delay gives 10.6 % (§6.4) |
| The inadequacy governor detects a wrong model family | 40/40 seeds, median round 4 of 8, 2.5 % campaign false-alarm rate (§6.6) |
| High posterior model probability is **not** correctness | S4c reaches P = 1.00 on a wrong model at 116.9 % error (§6.5) |
| K₁ is unidentifiable in this design space — predicted *before* the campaign | best signal 5.3 mM ≈ 1.1σ anywhere in the box; posterior width 514 % (§6.7, §6.3) |
| The NMR covariance is calibrated, not inflated | all 12 species × suite cells at 0.86–1.00 held-out coverage (§6.10) |
| Resource-aware design is cheaper but **not** free | −61 % material, −73 % energy, at P(better) = 0.28 (§6.8) |

---

## Table of contents

1. [The chemistry](#1-the-chemistry)
2. [What problem this solves](#2-what-problem-this-solves)
3. [Layer 1 — the digital twin](#3-layer-1--the-digital-twin)
4. [Layer 2 — the self-driving laboratory (baseline)](#4-layer-2--the-self-driving-laboratory-baseline)
5. [Layer 3 — the CPR + Fourier 80 virtual instrument and Bayesian controller](#5-layer-3--the-cpr--fourier-80-virtual-instrument-and-bayesian-controller)
   - [5.1 The physical system](#51-the-physical-system-and-why-it-shapes-the-software)
   - [5.2 The measurement chain](#52-the-measurement-chain)
   - [5.3 NMR forward model](#53-the-nmr-forward-model)
   - [5.4 Spectral deconvolution and the measurement covariance](#54-spectral-deconvolution-and-the-measurement-covariance)
   - [5.5 Sample transport](#55-sample-transport-delay-dispersion-reaction-carryover)
   - [5.6 Optimal spatial sampling](#56-optimal-spatial-sampling)
   - [5.7 Bayesian multi-model inference](#57-bayesian-multi-model-inference)
   - [5.8 Expected information gain](#58-expected-information-gain-active-learning)
   - [5.9 The model-inadequacy governor](#59-the-model-inadequacy-governor)
   - [5.10 Resource-aware utility](#510-resource-aware-utility)
   - [5.11 Strategies E, F and the ablations](#511-strategies-e-f-and-the-ablations)
   - [5.12 The truth/inference firewall](#512-the-truthinference-firewall)
   - [5.13 Framework corrections (v2)](#513-framework-corrections-v2)
   - [5.14 Targeted scientific corrections (v3)](#514-targeted-scientific-corrections-v3)
   - [5.15 NMR uncertainty calibration (v3 final)](#515-nmr-uncertainty-calibration-v3-final)
6. [Benchmark results — the v3 publication run](#6-benchmark-results)
   - [6.1 Headline](#61-headline-what-each-layer-of-realism-costs-and-what-awareness-recovers)
   - [6.2 S1 ideal](#62-scenario-1--does-the-new-machinery-cost-anything-when-it-is-not-needed)
   - [6.3 S2 realistic NMR](#63-scenario-2--realistic-nmr-whose-covariance-does-the-estimator-believe)
   - [6.4 S3 transport + ablation](#64-scenario-3--transport-reality-and-the-transport-ablation)
   - [6.5 S4 model discrimination](#65-scenario-4--model-discrimination-and-its-three-honest-outcomes)
   - [6.6 S5 the governor](#66-scenario-5--the-model-inadequacy-governor)
   - [6.7 Equilibrium observability](#67-equilibrium-observability--a-pre-campaign-identifiability-verdict)
   - [6.8 S6 resource-aware campaigning](#68-scenario-6--resource-aware-campaigning)
   - [6.9 S7 spatial sampling modes](#69-scenario-7--spatial-sampling-modes)
   - [6.10 NMR quantification validation](#610-nmr-quantification-validation)
   - [6.11 Figures and data](#611-figures-and-data)
   - [6.12 Where the time went](#612-where-the-time-went)
   - [6.13 What this run does *not* establish](#613-what-this-run-does-not-establish)
7. [User manual](#7-user-manual)
8. [Scientific integrity and calibration status](#8-scientific-integrity-and-calibration-status)
9. [Code map](#9-code-map)
10. [Extending the framework](#10-extending-the-framework)
11. [Glossary and nomenclature](#11-glossary-and-nomenclature)
12. [References](#12-references)

---

## 1. The chemistry

EGDA is a diester: an ethylene glycol backbone carrying **two acetate groups**.
Cleaving both liberates ethylene glycol (EG) and two acetic acid molecules,
passing through the mono-ester EGMA (ethylene glycol monoacetate):

```
        EGDA                      EGMA                       EG
   AcO–CH₂–CH₂–OAc   →   HO–CH₂–CH₂–OAc    →    HO–CH₂–CH₂–OH
        (diester)     step 1  (monoester)   step 2   (diol)
                        + AcOH                 + AcOH
```

This is a **series (consecutive) reaction network**, and that single structural
fact drives everything interesting about it. The intermediate EGMA is both
produced (step 1) and destroyed (step 2), so its concentration rises, peaks,
and falls. If EGMA is your product, there is an *optimal* residence time and
temperature — run too briefly and you make little; run too long and you
over-cleave it to EG. The twin locates that optimum.

It is also, conveniently, an ideal NMR test system: EGDA and EG are symmetric
(their four backbone protons give one **singlet** each, at 4.335 and
3.660 ppm), while the desymmetrized intermediate EGMA gives a pair of J-coupled
**1:2:1 triplets** (4.245 and 3.780 ppm). At 80 MHz the EGDA singlet and the
EGMA ester triplet are only **7 Hz apart** — a genuine, quantifiable peak-overlap
problem that Layer 3 simulates and resolves (§5.4).

The framework supports **two catalyst systems**, which are chemically different
reactions, not two speeds of the same one. The Layer 3 demonstration uses
Route A only (homogeneous H₂SO₄), per the target CPR campaign.

### Route A — sulfuric acid (specific acid catalysis, A-AC2)

```
EGDA + H₂O  ⇌  EGMA + AcOH        (K₁)
EGMA + H₂O  ⇌  EG   + AcOH        (K₂)
```

H⁺ protonates the carbonyl, activating it toward attack by water. The proton
is regenerated — a **true catalyst**, not consumed, so [H⁺] is constant along
the reactor. Critically, **acid catalysis accelerates the forward and reverse
directions equally**, so the same H⁺ that drives hydrolysis also drives the
reverse Fischer esterification. These reactions are *reversible*, and at high
conversion the back-reaction matters.

### Route B — sodium hydroxide (saponification, B-AC2)

```
EGDA + OH⁻  →  EGMA + AcO⁻
EGMA + OH⁻  →  EG   + AcO⁻
```

Hydroxide attacks the carbonyl directly. Three consequences make this a
genuinely different model, not a re-parameterization: it is **~1000× faster**
per mole of catalyst; it is **not catalytic** (one OH⁻ is destroyed per acetate
group released — hydroxide is a stoichiometric reagent that can run out); and
it is **irreversible** (a carboxylate anion is not electrophilic enough for
re-esterification, and the acid–base step is ~10⁹-fold downhill).

---

## 2. What problem this solves

### The forward problem (Layer 1)

Building a real flow reactor and scanning temperature × flow rate × catalyst
loading × tube geometry costs weeks of lab time and material. A digital twin
that faithfully encodes the chemistry lets you scan that space in seconds,
find the interesting corners, and only then go to the bench. Concretely it
answers: what residence time and temperature maximize EGMA yield? How much
catalyst is needed for 90% conversion in a given tube? Is the tube even
behaving as a plug-flow reactor at this flow rate? How close to chemical
equilibrium is the outlet?

### The inverse problem (Layer 2)

A twin is only as good as its kinetic parameters, and those must come from
experiments. The classical approach — a temperature ladder at fixed conditions
— is *wasteful*: many of those experiments carry almost no information about
the parameters you care about. **Model-Based Design of Experiments (MBDoE)**
turns this around: after each experiment, re-estimate the parameters, compute
how uncertain they still are, and run the experiment expected to shrink that
uncertainty the most. Layer 2 demonstrates this on a virtual laboratory with a
hidden truth, so each strategy's performance can be *measured* — impossible
with real data, where truth is unknown.

### The realism problem (Layer 3)

Layer 2's virtual laboratory observes *concentrations plus Gaussian noise*.
The real platform will not. It will observe **an 80 MHz ¹H spectrum of a
sample that was withdrawn at position z by a moving capillary, traveled
through a transfer line while continuing to react, dispersed, and partially
mixed with the previous sample** — and every concentration it "measures" is
the output of a spectral fit with its own error structure. Three consequences,
each demonstrated quantitatively in §6:

1. **Measurement uncertainty is not a diagonal Gaussian you assume; it is a
   correlated object you must estimate** — overlapping EGDA/EGMA peaks make
   their concentration errors anti-correlated, coherent gain drift correlates
   *all* species, and sub-0.1 Hz shift-calibration jitter alone produces
   ~10 mM EGMA errors.
2. **Transport bias corrupts naive kinetics.** Treating the NMR reading as
   "the concentration at z" biases parameters by an order of magnitude when
   the line delay lets a hot sample keep reacting (Scenario 3: 127% parameter
   error naive vs 7.5% transport-aware).
3. **A wrong model can look confidently right.** Parameter uncertainty and
   model inadequacy are different failure modes; a controller that only
   maximizes Fisher information around its current model will happily become
   *more certain of a wrong answer*. Layer 3 adds a statistically calibrated
   governor that detects this and switches to diagnostic experiments.

Layer 3 exists so that (i) benchmark results are realistic enough to support a
publication and a funding proposal, and (ii) the software architecture survives
the transition to real hardware unchanged.

---

## 3. Layer 1 — the digital twin

### 3.1 Model hierarchy and assumptions

The reactor is modeled as a **steady-state, isothermal, constant-density 1D
plug flow reactor (PFR)** fed by an ideal micromixer:

```
Stream 1 (aq. EGDA)          ─┐
                              ├─► micromixer ─► x=0 ──── isothermal PFR ──── x=L
Stream 2 (aq. H₂SO₄ or NaOH) ─┘   (instant,          (constant cross-section)
                                   perfect)
```

| # | Assumption | Justification / check |
|---|---|---|
| 1 | Instant, perfect micromixing; flows additive | Micromixer residence ≪ reactor residence; dilute aqueous streams |
| 2 | Isothermal | Feeds pre-heated; dilute solutions, modest ΔH; **not** an energy-balance model |
| 3 | Ideal plug flow (no axial dispersion, flat velocity) | **Quantified, not assumed** — `diagnostics.py` reports Re, radial diffusion time vs τ, and Bodenstein number, and warns when the idealization is optimistic |
| 4 | Constant liquid density; properties ≈ water | Dilute aqueous solutions |
| 5 | Ideal-solution activities (concentration-based Keq) | Activity coefficients lumped into K_ref, ΔH — recalibrate for concentrated feeds |
| 6 | H⁺ constant along x (acid route) | True catalyst, not consumed; AcOH (pKa 4.76) contributes negligibly against a strong-acid background |
| 7 | Ka₂ of H₂SO₄: temperature-dependent by default | See §3.4 — it collapses ~100× between 25 and 150 °C |

What the twin deliberately does **not** model: heat effects and non-isothermal
operation, pressure drop, phase behaviour, catalyst deactivation, and
acid/base cross-feeds (the mixer rejects these rather than silently producing
nonsense).

### 3.2 Governing equations

For a steady, constant-density PFR with superficial velocity `u = Q_total/A`
and residence coordinate `τ = x/u`, a species balance on a differential slice
gives, for every species *i*:

$$u \frac{dC_i}{dx} = \sum_{j} \nu_{ij}\, r_j \qquad\Longleftrightarrow\qquad \frac{dC_i}{d\tau} = \sum_j \nu_{ij}\, r_j$$

The second form shows the key identity: **a steady-state PFR in τ obeys the
same equations as a batch reactor in time.** Layers 2 and 3 use this identity
to model a sample that keeps reacting after withdrawal — the transfer-line
propagator of §5.5 is literally the batch form of these equations.

Written out — the organic balances are the same for both catalysts:

```
u·dC_EGDA/dx = −r₁
u·dC_EGMA/dx = +r₁ − r₂
u·dC_EG  /dx = +r₂
u·dC_AcOH/dx = +r₁ + r₂          (AcOH = total acetate pool)
```

and the small-species balances differ by route:

```
H₂SO₄:  u·dC_H₂O/dx = −r₁ − r₂        u·dC_OH/dx = 0
NaOH :  u·dC_H₂O/dx = 0               u·dC_OH/dx = −r₁ − r₂
```

**Conserved quantities.** These balances imply exact linear invariants, used
as numerical self-checks on every run:

| Invariant | Acid | Base | Meaning |
|---|---|---|---|
| `C_EGDA + C_EGMA + C_EG` | ✔ | ✔ | diol backbones conserved |
| `2·C_EGDA + C_EGMA + C_AcOH` | ✔ | ✔ | acetate groups conserved (bound + free) |
| `C_H₂O + C_AcOH` | ✔ | — | one water consumed per acetate released |
| `C_OH + C_AcOH` | — | ✔ | one hydroxide consumed per acetate released |
| `C_H₂O` | — | ✔ | water untouched by saponification |

### 3.3 Rate laws in full

#### Acid route — reversible, thermodynamically consistent

$$r_1 = \frac{k_1(T)\,[\mathrm{H^+}]}{C_{w,\mathrm{ref}}}\left([\mathrm{EGDA}][\mathrm{H_2O}] - \frac{[\mathrm{EGMA}][\mathrm{AcOH}]}{K_1(T)}\right)$$

$$r_2 = \frac{k_2(T)\,[\mathrm{H^+}]}{C_{w,\mathrm{ref}}}\left([\mathrm{EGMA}][\mathrm{H_2O}] - \frac{[\mathrm{EG}][\mathrm{AcOH}]}{K_2(T)}\right)$$

with Arrhenius rate constants and van 't Hoff equilibrium constants:

$$k_i(T) = A_i \exp\!\left(-\frac{E_{a,i}}{RT}\right), \qquad K_i(T) = K_{i,\mathrm{ref}} \exp\!\left[-\frac{\Delta H_i}{R}\left(\frac{1}{T}-\frac{1}{T_{\mathrm{ref}}}\right)\right]$$

Three design decisions make the model trustworthy rather than merely plausible:

**(a) Reverse constants are derived, never fitted independently.** Writing the
bracket as `(forward − reverse/K)` means the implied reverse rate constant is

$$k_{i,\mathrm{rev}}(T) = \frac{k_i(T)}{K_i(T)\, C_{w,\mathrm{ref}}}$$

so the net rate vanishes **exactly** when the reaction quotient reaches the
equilibrium constant, `Q_i = K_i` — *microscopic reversibility built into the
algebra*. The model cannot violate thermodynamics for **any** parameter values,
including nonsense values an optimizer might try during fitting.

**(b) The reference water concentration keeps the literature meaning of k.**
`C_w,ref = 55.34 M` is pure water at 25 °C. In dilute solution `[H₂O] ≈ C_w,ref`,
so the forward term collapses to the classical pseudo-first-order form
`k_i[H⁺][ester]` — `k₁, k₂` retain exactly the units and numerical values of
the physical-organic literature, while the model still handles concentrated or
water-lean feeds correctly.

**(c) Why reversibility matters.** With ~50 M water the equilibria lie far
toward hydrolysis, so a beginner might drop the reverse terms. They would lose:
the conversion ceiling (X_eq < 100%), the residual EGMA persisting at
equilibrium, the rate slowdown as AcOH accumulates, and the ability to run the
model in the esterification direction. `reversible: False` recovers the
simpler model for comparison — and is one of the candidate *wrong models* the
Layer 3 governor is tested against.

#### Alkaline route — irreversible, self-quenching

$$r_1 = k_1(T)\,[\mathrm{OH^-}][\mathrm{EGDA}], \qquad r_2 = k_2(T)\,[\mathrm{OH^-}][\mathrm{EGMA}]$$

Formally simpler, but **[OH⁻] is a state variable**, falling as the reaction
proceeds, so the equations are still nonlinear and the reaction
*self-terminates* when hydroxide runs out.

### 3.4 Catalyst speciation

Sulfuric acid is diprotic. Its first dissociation is complete, the second is
not:

$$\mathrm{H_2SO_4} \to \mathrm{H^+} + \mathrm{HSO_4^-} \quad(\text{complete}), \qquad \mathrm{HSO_4^-} \rightleftharpoons \mathrm{H^+} + \mathrm{SO_4^{2-}} \quad (K_{a2})$$

So `[H⁺] ≠ 2[H₂SO₄]`, and two effects the naïve dilute-25 °C treatment misses
are both large:

**Temperature (`ka2_model`).** Bisulfate dissociation is exothermic with a
large negative heat-capacity change (ΔH ≈ −22 kJ/mol, ΔCp ≈ −260 J mol⁻¹ K⁻¹;
Hovey & Hepler 1990), so `Ka₂` *falls by ~2 orders of magnitude from 25 to
150 °C*. The default `ka2_model: "tdep"` uses the Clarke–Glew constant-ΔCp
equation anchored at 25 °C:

$$\ln K_{a2}(T) = \ln K_{a2}^{\circ} - \frac{\Delta H^{\circ}}{R}\!\left(\frac1T - \frac1{T_0}\right) + \frac{\Delta C_p^{\circ}}{R}\!\left(\frac{T_0}{T} - 1 + \ln\frac{T}{T_0}\right)$$

reproducing accepted `pKa₂` to ~0.1 units out to 250 °C.

**Non-ideality (`activity_model`).** At molar acid the ionic strength is ≫ 1
and `γ(SO₄²⁻) ≪ 1`. `activity_model: "pitzer"` uses the Pitzer ion-interaction
model with the temperature-dependent Pitzer–Roy–Silvester parameter package
(Sippola & Taskinen 2014 refit), solving

$$K_2 = \frac{m_{\mathrm{H}}\, m_{\mathrm{SO_4}}}{m_{\mathrm{HSO_4}}}\cdot\frac{\gamma_{\mathrm{H}}\,\gamma_{\mathrm{SO_4}}}{\gamma_{\mathrm{HSO_4}}}$$

on a molality basis. At 1 mol/kg, 25 °C this gives `[H⁺] ≈ 1.22 M` versus
≈ 1.01 M from the dilute quadratic — a real effect on the rate. In the dilute
limit the two agree to <2%. The **pitzer-vs-dilute distinction is also one of
the Layer 3 candidate-model axes** (§5.7): the truth twin uses `pitzer`, and
one candidate model deliberately approximates it with `dilute`.

Because speciation depends on temperature, the micromixer is evaluated at the
reactor temperature. NaOH is a strong base with complete dissociation and
needs none of this.

### 3.5 Chemical equilibrium (acid route)

At infinite residence time both steps reach equilibrium simultaneously. With
extents `x₁, x₂` the equilibrium conditions are two coupled nonlinear
equations,

$$\frac{(b_0+x_1-x_2)(d_0+x_1+x_2)}{(a_0-x_1)(w_0-x_1-x_2)} = K_1, \qquad \frac{(c_0+x_2)(d_0+x_1+x_2)}{(b_0+x_1-x_2)(w_0-x_1-x_2)} = K_2$$

solved by Gauss–Seidel alternation with Brent bracketing (each single-extent
condition is monotone in its own extent). The equilibrium state is reported as
the `t → ∞` ceiling on every acid run and used as a *thermodynamic consistency
test* (§3.7).

### 3.6 Numerical method

`scipy.integrate.solve_ivp`, method LSODA, `rtol = 1e-9`, `atol = 1e-12` — far
tighter than any physical uncertainty, so numerical error never confounds a
physical conclusion. 201 output points along x by default.

### 3.7 Self-verification (runs on every simulation)

Every run prints a verification block:

1. **Independent reference solution.** The acid irreversible limit is exactly
   the linear series reaction A → B → C with the classical closed form

   $$C_A(\tau) = C_{A0}e^{-\kappa_1\tau}, \qquad C_B(\tau) = C_{B0}e^{-\kappa_2\tau} + C_{A0}\frac{\kappa_1}{\kappa_2-\kappa_1}\left(e^{-\kappa_1\tau}-e^{-\kappa_2\tau}\right)$$

   Typical integrator agreement ~10⁻¹⁰ relative. The NaOH route (no closed
   form) is cross-checked against Radau, a structurally different integrator.
2. **Invariant conservation** (§3.2), typical drift ~10⁻¹³.
3. **Thermodynamic consistency** — net rates evaluated *at* the independently
   computed coupled-equilibrium composition must vanish; typical residual
   ~10⁻¹⁵ relative.
4. **Limiting-reagent bookkeeping** (NaOH): acetate released must equal
   hydroxide consumed, exactly.

### 3.8 Plug-flow validity diagnostics

`diagnostics.py` reports the Reynolds number and regime, the radial diffusion
time `t_rad = R²/D_m` versus τ (Taylor–Aris well-mixed vs segregated laminar),
and the Bodenstein number `Bo = uL/D_ax` with `D_ax = D_m + u²R²/(48 D_m)`.
The twin prints an explicit ADVISORY when its own idealization is optimistic.

### 3.9 Parameter provenance

**Literature-anchored order-of-magnitude estimates, not measurements of your
system** — recalibrating them from data is exactly what Layers 2–3 are for.

| Step | A (L mol⁻¹ s⁻¹) | Eₐ (kJ/mol) | k(25 °C) | K_hyd(25 °C) | ΔH_hyd (kJ/mol) |
|---|---|---|---|---|---|
| **H₂SO₄** 1: EGDA ⇌ EGMA | 1.0 × 10⁶ | 55.0 | 2.27 × 10⁻⁴ | 0.50 | +5 |
| **H₂SO₄** 2: EGMA ⇌ EG | 1.0 × 10⁶ | 57.0 | 1.03 × 10⁻⁴ | 0.125 | +5 |
| **NaOH** 1: EGDA → EGMA | 2.6 × 10⁷ | 46.0 | 0.226 | — | — |
| **NaOH** 2: EGMA → EG | 2.6 × 10⁷ | 48.0 | 0.101 | — | — |

Rate constants anchor to the classic acetate-ester benchmarks (acid ethyl
acetate hydrolysis `k ≈ 1.1 × 10⁻⁴ L mol⁻¹ s⁻¹` at 25 °C; saponification
`k ≈ 0.11`). Statistical factors: EGDA's two equivalent esters give step 1 a
factor ≈ 2. Equilibrium constants anchor to `K_est ≈ 4` per ester group
(Berthelot & Péan de Saint-Gilles), with the same statistical logic giving
`K₁ = 0.50`, `K₂ = 0.125`, and `K₁K₂ = K_group²` consistent overall.

---

## 4. Layer 2 — the self-driving laboratory (baseline)

This layer is **preserved unchanged** as the regression-compatible baseline
against which the advanced Layer 3 is scientifically compared. Its 20
self-tests still pass, and `run_sdl_campaign.py` runs bit-for-bit as before.

### 4.1 The inverse problem

Find the parameter vector **θ** minimizing the mismatch between model
predictions **ŷ**(θ) and measurements **y**, and quantify how well θ is
thereby determined.

**Parameterization matters enormously.** Fitting `(A, Eₐ)` directly is badly
conditioned — over a narrow temperature window `ln A` and `Eₐ` are almost
perfectly correlated. The cure is re-referencing to a temperature inside the
experimental window:

$$k_i(T) = k_{i,\mathrm{ref}}\exp\!\left[-\frac{E_{a,i}}{R}\left(\frac{1}{T}-\frac{1}{T_{\mathrm{ref}}}\right)\right], \qquad T_{\mathrm{ref}} = 60\ ^\circ\mathrm{C}$$

The estimator works in a scaled vector where rate and equilibrium constants
are log-transformed — enforcing positivity and making σ(ln k) a *relative*
uncertainty:

| Route | θ (scaled) | p |
|---|---|---|
| H₂SO₄ | `[ln k₁_ref, Eₐ₁/1000, ln k₂_ref, Eₐ₂/1000, ln K₁_ref, ln K₂_ref]` | 6 |
| NaOH | `[ln k₁_ref, Eₐ₁/1000, ln k₂_ref, Eₐ₂/1000]` | 4 |

The van 't Hoff slopes ΔH are held at literature values — near-athermal
equilibria are not identifiable from a 30–90 °C window. A **pre-campaign
identifiability screen** (`sdl/identifiability.py`) additionally builds the
best affordable D-optimal reference design at the initial guess and holds
fixed any parameter whose best achievable 95% CI still exceeds a threshold
(on this system that is typically `K₁_ref`: with ~55 M water, step 1 runs
effectively to completion and K₁ leaves almost no signature).

### 4.2 Parameter estimation (weighted least squares)

Measurements are species-major vectors, `y[i·N_z + k] = C_i(z_k)`. The
baseline synthetic noise is heteroscedastic with an optional correlated pair
(the overlapping EGDA/EGMA resonances), as an *assumed* model:

$$\sigma_i = \sigma_{\mathrm{abs}} + \sigma_{\mathrm{rel}}\,C_i, \qquad \Sigma_{y}[p,q] = \rho\,\sigma_p\sigma_q \ \text{for the overlap pair at the same position}$$

(Layer 3 replaces this hand-assumed ρ with a covariance *estimated from the
actual spectral fit* — §5.4.) Estimation minimizes the **whitened** residual:

$$\hat{\theta} = \arg\min_\theta \sum_e \left\| L_e^{-1}\left(\hat{y}_e(\theta) - y_e\right)\right\|^2, \qquad \Sigma_e = L_eL_e^\top$$

solved by trust-region-reflective bounded least squares, warm-started each
round.

> **Backward-compatible extension (new).** A `Measurement` may now carry its
> own covariance `cov_y`. If `cov_y is None` (all legacy code), the assumed
> `NoiseModel` reconstructs Σ exactly as before; if supplied (the Layer 3
> deconvolution pathway), it is used directly. This one hook is the entire
> Layer 2 code change — nothing else in `sdl/` was modified.

### 4.3 Uncertainty quantification (Fisher information)

The local sensitivity matrix **S** = ∂ŷ/∂θ (central finite differences in
scaled space) gives the **Fisher Information Matrix** and the Cramér–Rao
covariance bound:

$$F = \sum_e S_e^\top \Sigma_e^{-1} S_e, \qquad V_\theta \approx F^{-1}$$

Reports expose per-parameter σ and 95% CIs (asymmetric for log-parameters),
the correlation matrix, the eigenvalue spectrum of F (a near-zero eigenvalue
= a direction the data cannot see), and the D-criterion `(det V)^{1/2p}`.
Rank-deficient F is inverted with **floored eigenvalues** so unidentified
directions report *huge* variance — never the false zero variance of a
pseudo-inverse.

### 4.4 MBDoE: choosing the next experiment

Given θ̂, the expected information from a candidate experiment u is computable
*before running it*. D-optimal design picks

$$u^\star = \arg\max_{u\,\in\,\mathcal{U}} \ \log\det\!\left(F_{\text{current}} + F_{\text{candidate}}(\hat\theta, u)\right)$$

over a factorial candidate grid (T × Q × catalyst × EGDA molarity), with
optional bounded continuous refinement of the winner. Maximizing `log det F`
minimizes the *volume* of the joint uncertainty ellipsoid — it attacks
whichever direction is currently worst known.

What MBDoE discovers unprompted is the best evidence it works: on the acid
route it requests **hot, slow, high-acid** conditions (equilibrium constants
are only visible near equilibrium); on the NaOH route it requests **cold,
fast-flow** conditions (pulling the transient back into the observable
window). Nobody told it either of those things.

### 4.5 The A/B/C/D baseline showcase

Four strategies on identical truth, budget, initial guess, and first
experiment, isolating two factors:

| | Fixed design | Autonomous MBDoE |
|---|---|---|
| **Outlet only** | **A** — conventional baseline | **C** — value of smart selection |
| **Equally spaced spatial profile** | **B** — value of spatial data | **D** — both together |

(Representative single-seed results live in `SDL_MBDoE/results/`; the
multi-seed, resource-fair comparison including strategies E–F is §6.)

### 4.6 The truth/inference firewall

The virtual lab's true parameters live in a private attribute. Estimation and
design code touches the truth **only** through `run_experiment(...)`, which
returns noisy measurements. `reveal_truth()` exists solely for post-campaign
benchmarking, **counts its own calls**, and self-tests assert the count is
zero during the loop. Layer 3 extends this contract (§5.12).

---

## 5. Layer 3 — the CPR + Fourier 80 virtual instrument and Bayesian controller

Everything in this section lives in [`SDL_MBDoE/sdl_advanced/`](SDL_MBDoE/sdl_advanced/).
Design priorities, in order: (1) physically correct Layer 1 → position link,
(2) optimized spatial sampling, (3) true spectrum → deconvolution → covariance
pathway, (4) realistic direct-capillary transfer model, (5) truth firewall,
(6) calibrated model-adequacy detection, (7) Bayesian multi-model inference,
(8) resource-aware active learning. **Every feature has a limiting mode that
reduces it exactly to the baseline** — and tests assert those reductions.

### 5.1 The physical system, and why it shapes the software

The Reacnostics liquid CPR contains **one sampling capillary that moves
continuously along the reactor axis**. The sample enters through an orifice in
this capillary and travels through **one transfer line** directly to the NMR
flow cell. There are **no fixed sampling ports and no selector valve.**
A measurement is therefore the chain

```
reactor condition u → move capillary to position z → withdraw local sample
→ capillary/transfer line (delay, dispersion, continued reaction, carryover)
→ Fourier 80 acquisition → spectrum processing/deconvolution
→ concentration estimates ŷ + covariance Σ_y → kinetic inference
→ decide what to measure next
```

Consequences encoded in the software:

- **The sampling position z is a continuous decision variable**, not an index
  into a port list. All Layer 3 code speaks `z_m` / `z/L` fractions;
  "ports" survive only in the legacy baseline.
- **Sampling order matters physically**: moving the capillary from z_old to
  z_new leaves the line filled with the previous sample (carryover, §5.5),
  and capillary travel |z_new − z_old| costs time (§5.10).
- **Reactor temperature ≠ transfer-line temperature ≠ NMR-cell temperature.**
  Post-sampling kinetics follow the line's temperature history; the water
  chemical shift and lineshapes follow the *NMR cell* temperature. These are
  three independent settings and are never conflated.

### 5.2 The measurement chain

```
Layer 1 concentrations at z            sdl.layer1_bridge   (chemistry, unchanged)
  → transfer.py       TransferLine     delay τ(z), gamma RTD, in-line reaction,
                                       flush/carryover state
  → spectral.py       NMRSimulator     80.168 MHz forward model (analytic | FID)
  → spectral_fit.py   SpectralFitter   VarPro deconvolution → (ŷ, Σ_y, QC)
  → instrument.py     AdvancedVirtualLaboratory   owns all hidden truth; emits
                                       Measurement(y=ŷ, cov_y=Σ_y, meta=QC)
  → model_ensemble.py / posterior.py   Bayesian Laplace multi-model inference
  → adequacy.py       AdequacyGovernor NORMAL / DISCRIMINATE / INADEQUATE / FAULT
  → spatial_design.py + bayes_design.py    where to sample, what to run next
  → resources.py      ResourceMeter    auditable cost accounting
  → controller.py     run_strategy_e / run_strategy_f   the closed loops
```

The chain is **never short-circuited** in NMR mode: the inference layer never
sees a true concentration, only what survives deconvolution. The old
`sim_nmr(2).py` conversion-based speciation is *not* used anywhere in this
loop — all compositions come from Layer 1 at the requested z. (The standalone
script remains in `EGDA_NMR_sim/` as a visualization/teaching tool.)

### 5.3 The NMR forward model

`spectral.py` is a refactoring of the physics in `EGDA_NMR_sim/sim_nmr(2).py`
into a reusable, concentration-driven module.

**Inherited and preserved** (aqueous-literature values, provenance comments
kept): the 80.168 MHz field (1 ppm = 80.168 Hz); the chemical-shift database
(EGDA 4.335/2.140 s; EGMA 4.245/3.780 t + 2.125 s; EG 3.660 s; AcOH 2.080 s);
proton-count scaling; the EGMA vicinal coupling J = 4.7 Hz producing binomial
1:2:1 triplets by the first-order rule (n equivalent partners → n+1 lines,
spacing J, binomial intensities); fast-exchange pooling of H₂O / EGMA-OH /
EG-OH / AcOH-COOH into **one broad line at the population-weighted average
shift**; and the empirical water-shift law

$$\delta_{\mathrm{H_2O}}(T_{\mathrm{cell}}) \approx 5.051 - 0.0111\,T_{\mathrm{cell}}\ [^\circ\mathrm{C}]$$

evaluated at the **NMR-cell temperature**, never the reactor's.

**Changed:** the input API is `simulate(concentrations, rng)` with actual
molar Layer 1 concentrations; the mapping between Layer 1 names and the
original `D/M/G/aa/w` keys lives in one place (`LAYER1_TO_NMR`); the catalyst
is homogeneous H₂SO₄ (the original file's Amberlyst mention was corrected —
the spectral physics itself is catalyst-independent).

**Line convention.** Every transition contributes a **unit-area Lorentzian
scaled by its area** `a = n_H · C · f_resp · E · g`:

$$A(\delta;\delta_0,w) = a\,\frac{w/2}{\pi\left[(\delta-\delta_0)^2 + (w/2)^2\right]}, \qquad \int A\, d\delta = a$$

so integrated area — the physically meaningful NMR observable — is exactly
proportional to concentration and independent of linewidth.

**Two engines.**

*Analytic* (default; fast, for Monte Carlo campaigns): direct summation of
absorption Lorentzians, with dispersion-mode mixing for a phase error φ:
`y = cos φ · A + sin φ · D`, `D ∝ (δ−δ₀)/((δ−δ₀)² + (w/2)²)`.

*FID* (the honest instrument model): known transitions → complex time-domain
signal

$$s(t) = \sum_k a_k \exp\!\big[(\,i\,2\pi f_k - \pi\,w_k\,)\,t\big], \qquad w_k = \mathrm{FWHM}_k\ \mathrm{[Hz]} = \frac{1}{\pi T_{2,k}^{*}}$$

sampled at the complex dwell `1/SW`, half-first-point corrected, with complex
receiver noise, zero-order phase and frequency-reference error, then FFT
(×2·dt, because the one-sided FID transform carries half the two-sided
Lorentzian area). A test asserts FID and analytic engines agree to <5%.
Configurable: spectrometer frequency, spectral width, acquisition time,
number of complex points, T₂*/linewidth, receiver noise, phase, reference
error.

**`nmr_mode = "ideal"` vs `"realistic"`.** Ideal mode is deterministic (used
for regression tests). Realistic mode draws, per acquisition, from configured
distributions: additive spectral noise (σ = 0.10 area/ppm units ≈ per-point
SNR 400 on a 0.3 M peak, per scan); global shift drift (σ 0.004 ppm);
**per-group shift jitter** (σ 0.001 ppm — see why this tiny number matters in
§5.4); log-normal linewidth variation (8%); baseline offset and quadratic
curvature; zero-order phase error (2°); acquisition-to-acquisition gain drift
(1%); per-species response-factor error (EGMA +2%); imperfect water
suppression (configurable residual factor). All values are **simulation
assumptions marked `CAL:`** in the code (§8).

**Flow/relaxation response (§7 of the concept).** Peak area is *not* assumed
perfectly proportional to concentration under every flow condition. An
optional phenomenological factor

$$E_g = 1 - \exp\!\left(-\frac{t_{\mathrm{pol}}}{T_{1,g}}\right), \qquad t_{\mathrm{pol}} = \frac{V_{\mathrm{premag}}}{Q_{\mathrm{analytical}}} + t_{\mathrm{rep}}$$

multiplies each group's area with species-specific T₁ values (assumed 2.5–4.5 s).
It is **not** a rigorous flowing-spin Bloch model — it is a documented
surrogate that decreases with faster analytical flow or shorter recycle time,
and is **exactly 1 when disabled** (asserted by test). It lives only in the
truth instrument unless the fitter is explicitly calibrated for it, enabling
robustness studies of the form *"what if MBDoE changes flow and the response
is wrongly assumed flow-independent?"*.

### 5.4 Spectral deconvolution and the measurement covariance

`spectral_fit.py` is the module that makes Layer 3 honest: **the controller
never receives true concentrations — it receives what a fit to the spectrum
can recover, with the covariance that fit implies.**

**Variable projection (VarPro).** The model spectrum is linear in the
amplitudes and nonlinear in a small set of lineshape nuisances:

$$y(\delta) \;\approx\; B(\eta)\,a, \qquad
\eta = (\underbrace{\delta_{\mathrm{off}}}_{\text{global shift}},\ \underbrace{\ln\lambda_w}_{\text{linewidth factor}},\ \underbrace{\delta_{\mathrm{pool}}}_{\text{exchange-pool center}},\ \underbrace{\varphi}_{\text{zero-order phase}})$$

with columns of `B`: one **unit-concentration basis spectrum per quantified
species** (EGDA, EGMA, EG, AcOH — built from the same shift database, phased
as `cos φ·A + sin φ·D`), one broad exchange-pool shape (amplitude is a
nuisance — at 80 MHz the exchangeables carry no species-specific signal), and
Legendre-style baseline columns `1, x, x²`. For each η trial the linear
subproblem

$$\min_a \|y - B(\eta)a\|^2 \quad \text{s.t.}\ a_{\mathrm{species}} \ge 0,\ a_{\mathrm{pool}} \ge 0,\ a_{\mathrm{baseline}}\ \text{free}$$

is solved by bounded least squares (BVLS); the outer problem over η by
trust-region least squares on the projected residual. Because the basis
columns are unit-concentration spectra under nominal calibration, **the fitted
amplitudes are molar concentrations directly.**

**The covariance Σ_y** starts from the full Jacobian at the optimum
(linear columns + numerical η columns):

$$\Sigma^{(\mathrm{fit})} = \hat\sigma^2 \left(J^\top J\right)^{-1}\Big|_{\text{species block}}, \qquad \hat\sigma^2 = \frac{\|r\|^2}{n - p}$$

with floored eigenvalues. This *naturally* produces the anti-correlated
EGDA/EGMA errors caused by their 7 Hz overlap — no hand-chosen
`rho_overlap = 0.3` anywhere in the advanced pathway (the baseline keeps its
assumed NoiseModel untouched, which is exactly what Scenario 2 compares).

Three augmentation terms were introduced as ASSUMED surrogates for the
error the single-spectrum Jacobian cannot see (each a calibratable
instrument property — `CAL:`). **They are superseded in v3**: when a real
calibration artifact exists these surrogates are switched OFF and replaced
by the empirically measured residual model (§5.15), because keeping both
would double-count the same effect:

$$\Sigma_y \;=\; \Sigma^{(\mathrm{fit})} \;+\; \mathrm{diag}\big[(\sigma_{\mathrm{floor,abs}} + \sigma_{\mathrm{floor,rel}}\,\hat C_i)^2\big] \;+\; g^2\,\hat C\,\hat C^\top \;+\; \sum_{\mathrm{group}\ g'} \sigma_{\mathrm{jit}}^2\, J_{g'} J_{g'}^\top$$

1. a **reproducibility floor** (2 mM + 3% rel, `sigma_floor_rel=0.03`) — acquisition-to-acquisition
   effects invisible to one spectrum's Jacobian;
2. a **rank-one gain term** — receiver-gain drift scales *every* species
   coherently, so it contributes a correlated `g²·ĈĈᵀ`, not a diagonal entry;
3. **per-group shift-jitter propagation** — `J_{g'} = B^+ v_{g'}` is the
   linearized response of the fitted amplitudes to group g′'s center moving by
   σ_jit, with `v_{g'}` the shift-derivative of that group's lineshape. This
   term is *the* dominant realistic error for the overlapped pair: a 0.001 ppm
   (0.08 Hz!) relative shift between the EGDA singlet and the EGMA ester
   triplet re-apportions overlapped area worth ~10 mM of EGMA at 0.45 M EGDA.

**Quantification quality (measured, Monte Carlo, n = 120 random compositions
under the full realistic nuisance set):**

> **SUPERSEDED — do not cite.** The table below is the v1 in-sample result
> (the fitter was validated against spectra generated by its own physics and
> the surrogate covariance terms were tuned by hand). Independent held-out
> validation in v3 showed these numbers were optimistic. **The authoritative
> NMR validation is §6.2**, produced by the three-dataset calibration
> hierarchy and reported per suite in `quantification_validation.csv`.

| Species (v1, superseded) | in-sample coverage | RMSE |
|---|---|---|
| EGDA | 0.99 | 4.5 mM |
| EGMA | 0.97 | 12.5 mM |
| EG | 1.00 | 1.6 mM |
| AcOH | 1.00 | 3.2 mM |

Coverage at-or-slightly-above nominal (mildly conservative for well-resolved
species, near-calibrated for the overlapped pair) is the safe side of the
trade-off. EGMA is worst because it *is* the overlap species — exactly the
physics the framework exists to represent. `bootstrap_coverage()` provides
this parametric-bootstrap validation as a utility (never inside the campaign
loop).

**Returned per fit:** concentrations, Σ_y, fitted spectrum, residual spectrum,
residual RMS, basis condition number, the full correlation matrix, fitted η,
and QC flags (`FAIL` when the residual is far above the data's own noise
scale — the `MEASUREMENT_FAULT` input of §5.9).

### 5.5 Sample transport: delay, dispersion, reaction, carryover

`transfer.py` replaces the baseline's single `transfer_time_s` hook with a
proper transport model of the *actual hardware topology* (one moving
capillary → one line → NMR; no selector), while the delta/plug limit exactly
reproduces the legacy behaviour (asserted by test).

**Volume and delay.** The transfer volume may depend on capillary position
(the geometry is not frozen yet, hence configurable):

$$V(z) = V_{\mathrm{fixed}} \quad\text{or}\quad V(z) = V_{\mathrm{fixed}} + v'\,(L - z), \qquad \tau_{\mathrm{tr}}(z) = \frac{V(z)}{Q_{\mathrm{sample}}}$$

**Residence-time distribution.** A gamma / tanks-in-series RTD with shape
n (n → ∞ recovers plug flow):

$$g(\tau) = \frac{\tau^{n-1} e^{-n\tau/\bar\tau}}{\Gamma(n)\,(\bar\tau/n)^n}$$

**Continued reaction.** The composition the NMR sees is the RTD-average of
the withdrawn composition propagated through the *batch* form of the Layer 1
ODEs (the PFR/batch identity of §3.2) at the **transfer-line temperature**:

$$C_{\mathrm{seen}}(z) = \int_0^\infty g(\tau)\, \Phi_{\tau,\,T_{\mathrm{line}}}\!\left[C(z)\right] d\tau \;\approx\; \sum_{q} w_q\, \Phi_{\tau_q,\,T_{\mathrm{line}}}\!\left[C(z)\right]$$

evaluated by equal-probability quantile quadrature on the gamma CDF (midpoint
nodes, deterministic). The propagator Φ is injected by the instrument and
closes over the hidden true kinetics — this module itself holds no truth.

**Carryover.** When the capillary moves, the line initially contains the
previous position's material. An exponential flushing model mixes old and new:

$$C_{\mathrm{obs}} = (1-f)\,C_{\mathrm{seen}}(z_{\mathrm{new}}) + f\,C_{\mathrm{prev}}, \qquad f = e^{-V_{\mathrm{flush}}/V_{\mathrm{line}}}$$

with the previous transported composition held as instrument state (reset when
the operating condition changes and the system re-primes). This is the
physical reason **sampling order and flushing time are real design variables**.

**Inference-side correction.** The controller may know the *commanded* mean
delay `τ = V/Q` (public knowledge) and correct for it:
`TransportAwareInference` predicts concentrations with that mean delay applied
through the same batch identity — using its **own** kinetic estimate, never the
truth. The RTD spread and carryover remain unmodeled, a deliberate, realistic
imperfection of the correction. With `extra_tau_s = 0` the class is exactly
the baseline `InferenceModel`.

### 5.6 Optimal spatial sampling

`spatial_design.py` replaces `z_i = i·L/N` with a configurable policy:
`sampling_mode ∈ {fixed_equal, optimized, adaptive_sequential}`.

**`fixed_equal`** reproduces the legacy layout exactly:
`z_i = i·L/N, i = 1…N` (asserted by test, for multiple reactor lengths).

**`optimized` — the design criterion.** For operating condition u and current
estimate θ̂, the local sensitivity at z is `S(z,u) = ∂y(z,u)/∂θ`
(n_species × p, scaled space), and one acquisition at z contributes

$$F_z = S(z,u)^\top\, \Sigma_y(z,u)^{-1}\, S(z,u)$$

where Σ_y comes from the controller's *expected-covariance* model (the
assumed NoiseModel for E; the learned surrogate of §5.8 for F — never the
truth). Selecting the K individually best positions would pick redundant
neighbours, so positions are chosen by **greedy incremental D-optimality**,
each conditioned on the ones already selected:

$$z_{k+1} = \arg\max_{z}\ \log\det\!\Big(F_{\mathrm{current}} + \sum_{z' \in Z_{\mathrm{sel}}} F_{z'} + F_z\Big)$$

subject to `z ∈ [z_min, z_max]`, pairwise spacing ≥ `min_spacing`, no
duplicates, and an optional forced outlet — with floored eigenvalues so the
criterion still *ranks* candidates while F is rank-deficient (early rounds,
exactly when the choice matters most). One finite-difference sweep over a
dense z-grid builds an **interpolated sensitivity field** reused by both the
grid search and a deterministic cyclic coordinate refinement of the selected
positions — so continuous refinement costs almost nothing. Everything is
internally normalized to z/L, so changing the reactor length rescales all
designs automatically (asserted by test).

**`adaptive_sequential`.** Because the capillary moves continuously, the
machine need not always take 10 samples per condition. In this mode the
controller measures one position, updates the accumulated information (the
cheap FIM update between acquisitions; the full Bayesian update runs once per
condition), asks for the next best position **and its marginal gain**
`Δ log det F`, and stops when the expected marginal information per
acquisition falls below a configured threshold or the position budget is
reached. Marginal gains are provably non-increasing from a well-posed state
(submodularity of log det), which is what makes the stop rule sound — also
asserted by test.

The configuration block:

```python
SpatialDesignConfig(
    mode="optimized",              # fixed_equal | optimized | adaptive_sequential
    n_positions=10,
    candidate_grid_size=41,
    z_min_fraction=0.02, z_max_fraction=1.0,
    min_spacing_fraction=0.02,
    force_outlet=False,
    continuous_refinement=True,
    allow_profile_early_stop=False,
    marginal_information_threshold=0.05,   # nats / acquisition
)
```

### 5.7 Bayesian multi-model inference

The baseline WLS/FIM machinery is kept as-is; the advanced layer adds **model
uncertainty** instead of assuming the selected rate model must be correct.
The target is the joint posterior `p(M, θ | D)` over a small, scientifically
interpretable candidate family built entirely from existing Layer 1
capabilities — no black-box models:

| Model | Structure | θ dim |
|---|---|---|
| **M1** `rev-pitzer` | reversible hydrolysis, Pitzer H⁺ activity (the truth's structure) | 6 (minus screened) |
| **M2** `rev-dilute` | reversible, dilute-activity approximation (γ = 1) | 6 (minus screened) |
| **M3** `irreversible` | irreversible approximation (the legacy twin) | 4 |

**Laplace approximation per model.** Each candidate owns its own bridge,
parameter space, and a weak, documented Gaussian prior in the scaled space
(σ(ln k) = ln 10 — "the literature guess is right within a factor of ten";
σ(Eₐ) = 20 kJ/mol; σ(ln K) = ln 3). The MAP is the prior-penalized whitened
least-squares solution; the local posterior covariance is the inverse
Gauss–Newton Hessian `H = F(θ*) + P` (P the prior precision); and the model
evidence is the Laplace estimate

$$\ln Z_M \;\approx\; \ln p(y \mid \theta^{*}, M) + \ln p(\theta^{*} \mid M) + \frac{p}{2}\ln 2\pi - \frac12 \ln\det H$$

with full Gaussian normalization constants (they matter across models with
different dimensionality). Model probabilities are the normalized evidences;
posterior **particles** `(M_j, θ_j)` for design are drawn model-multinomially,
then from each model's Laplace Gaussian truncated to bounds. The API is
deliberately minimal (`fit_map / sample / log_evidence`) so an SMC/MCMC
backend can replace the Laplace approximation later without touching the
controller — full MCMC does not need to run inside every ten-second decision.

### 5.8 Expected-information-gain active learning

The advanced selector does not rely exclusively on the local FIM. A design is
the joint object `d = {T, Q, C_EGDA, C_H₂SO₄, Z}` with Z the spatial set. To
stay computationally practical the selection is **hierarchical**, never one
enormous joint optimizer:

1. feasible operating-condition grid (**hard bounds are hard constraints** —
   a violating candidate raises, it is not merely penalized);
2. per condition, optimize its spatial set Z (§5.6);
3. FIM D-score minus resource cost → keep the top K candidates;
4. Bayesian EIG on the top K; optional continuous refinement of the winner
   (positions).

**The EIG estimator** (nested Monte Carlo over the joint posterior): with
particles θ_i, cached predictions y_i = pred(θ_i, d), and the expected
observation covariance Σ(d):

$$I(d) \;=\; \mathbb{E}_{y \sim p(y\mid d, D)}\, \mathrm{KL}\big(p(M,\theta \mid y, d, D)\,\|\,p(M,\theta \mid D)\big) \;\approx\; \frac{1}{N_o}\sum_{o=1}^{N_o}\left[\ \ln p\big(y_o \mid \theta_{j(o)}\big) - \ln \frac{1}{N}\sum_{i=1}^{N} p\big(y_o \mid \theta_i\big)\right]$$

with outer samples `y_o = y_{j(o)} + L·ξ` (particle j(o) chosen uniformly,
noise from Σ = LLᵀ), all likelihoods in whitened, log-sum-exp arithmetic. The
**model-discrimination component** is computed from the same likelihood table:

$$I_M(d) = \mathbb{E}_y\, \mathrm{KL}\big(p(M \mid y)\,\|\,p(M)\big), \qquad p(M{=}m \mid y_o) \propto \sum_{i:\,M_i = m} p(y_o\mid\theta_i)$$

which naturally rewards both parameter learning and model discrimination.

**No pixel-level NMR for hypotheticals.** Full spectra are simulated only for
experiments the laboratory actually executes. For candidate scoring, Σ(d)
comes from a **noise surrogate learned from the campaign's own deconvolution
covariances** (permitted QC metadata, never truth): per position
`σ_i = a + b·C_i` fitted by least squares to all (concentration, claimed σ)
pairs seen so far, plus the running-mean EGDA/EGMA error correlation; before
any data arrives it falls back to the documented prior guesses.

### 5.9 The model-inadequacy governor

> **v2 note:** the statistics below were redesigned after review — see §5.13
> item 4. In particular, under NMR observation the z-autocorrelation test is
> reported but excluded from the inadequacy decision (composition-smooth
> quantification bias mimics it), the p-values are continuous and
> Šidák-combined, and alpha is spent uniformly across planned rounds.


The controller must distinguish *"my parameters are uncertain"* from *"my
model is systematically wrong"* **before** exploiting the current model for
D-optimal or EIG refinement. `adequacy.py` implements a four-state governor:

| State | Meaning | Controller response |
|---|---|---|
| `NORMAL_LEARNING` | data consistent, one model dominant | parameter-EIG design |
| `MODEL_DISCRIMINATION` | data consistent, several models plausible (max prob < 0.90) | boost the model-EIG weight β |
| `MODEL_INADEQUATE` | **every** candidate model shows calibrated lack of fit | stop exploiting FIM; diagnostic design |
| `MEASUREMENT_FAULT` | the spectral fits themselves raise FAIL QC | fix the instrument before blaming chemistry |

**Diagnostics.** On the best model's MAP whitened residuals r_w (∼ N(0, I)
when model and measurement model are both correct):

- **χ² magnitude test**: `T = r_wᵀr_w` against `χ²_{n−p}`, optionally with a
  Monte-Carlo-calibrated quantile (parametric bootstrap with refit under the
  fitted model — the mechanism that bounds the false-positive rate at the
  configured α by construction);
- **scale-free lag-1 residual autocorrelation along z** — the test that does
  the real work. Kinetic-model error is *smooth along the reactor*, so
  consecutive whitened residuals at neighbouring z are positively correlated,
  while acquisition noise is independent. Pooled over species and profiles:

  $$\hat\rho = \frac{\sum r_k r_{k+1}}{\sqrt{\sum r_k^2 \sum r_{k+1}^2}}, \qquad z = \hat\rho\sqrt{N_{\mathrm{pairs}}} \sim \mathcal{N}(0,1)\ \text{under } H_0$$

  Being a *correlation*, it is immune to a conservative (inflated) Σ_y that
  masks the χ² test — a methodologically important point discovered during
  calibration: with honest-but-safe covariances, χ²/dof sits near 0.2–0.5
  even for a *wrong* model, and only the autocorrelation signature exposes
  the structure error. The two tests are Bonferroni-combined per model:
  `p_M = min(2·min(p_χ², p_ρ), 1)`;
- **per-species standardized mean residual** `√n_s · mean(r_{w,s})` (which
  species is systematically off), **residual trend vs z and vs T** (where in
  the operating space the misfit lives), and the **QC-fail fraction** of the
  spectral fits.

The report carries the inadequacy score, p-values for every candidate,
per-species biases, the affected z/T region in words, the reasons, and the
campaign round of first detection. **Diagnostic-mode design** (entered on
`MODEL_INADEQUATE`) stops maximizing the (wrong) model's FIM and instead
selects the candidate maximizing the expected whitened *disagreement between
the candidate models' predictions* — the experiment best able to separate
parameter uncertainty from structural error.

**Measured behaviour** (publication benchmark, §6.6 — 40 dedicated seeds):
detection of the deliberately misspecified Scenario 5 in **40/40 seeds, median
round 4 of 8** (range 3–5); campaign-level false-alarm rate under the correct
model **1/40 = 2.5 %**, per-round false-inadequacy rate **0.0031**.

### 5.10 Resource-aware utility

`resources.py` accounts every physical action from an **auditable event log**
(tests re-derive all totals from the raw events): reactor stabilization time
(volumes × flow), EGDA and acid consumed, total liquid processed, analytical
sample and flush volumes, NMR acquisition time, capillary travel distance and
time, temperature-change/ramp time, condition switches, and a configurable
heating-energy surrogate (`Q·ρc_p·ΔT` + ramp term — a campaign-cost proxy,
**not** validated calorimetry). The design utility is

$$U(d) = \alpha\,\mathrm{EIG}_{\theta}(d) + \beta\,\mathrm{EIG}_{M}(d) - \lambda_{\mathrm{time}} t - \lambda_{\mathrm{mat}} n_{\mathrm{EGDA}} - \lambda_{\mathrm{waste}} V - \lambda_{\mathrm{energy}} E - \lambda_{\mathrm{switch}}\,\mathbb{1}_{\Delta T} - \lambda_{\mathrm{motion}} \sum |\Delta z|$$

with capillary motion costed by actual travel |z_next − z_current| along the
sampling sequence. Safety/equipment limits are **hard constraints**, never
negative penalties. All λ = 0 recovers pure information maximization
(asserted by test).

### 5.11 Strategies E, F and the ablations

The baseline A–D are untouched. New strategies:

| Key | Positions | Condition design | Inference | Observation |
|---|---|---|---|---|
| **A** | outlet | fixed ladder | WLS/FIM | direct + assumed noise |
| **B** | equally spaced | fixed ladder | WLS/FIM | direct + assumed noise |
| **C** | outlet | FIM MBDoE | WLS/FIM | direct + assumed noise |
| **D** | equally spaced | FIM MBDoE | WLS/FIM | direct + assumed noise |
| **E** | **greedy D-optimal** | FIM MBDoE | WLS/FIM | direct + assumed noise |
| **F** | optimized / adaptive | **Bayesian EIG, resource-aware, governor-guarded** | Laplace multi-model | **realistic NMR + transport, Σ_y from deconvolution** |

Ablations of F (constructed in the benchmark by switching instrument/config
flags, not by separate code paths): **F-noNMR** (direct noisy concentrations),
**F-noTransport / F-uncorr** (NMR active, transport absent / present-but-
uncorrected), **F-noGovernor** (adequacy safeguard disabled, assessments still
recorded for scoring).

For fairness, **all strategies in a scenario face the same
`AdvancedVirtualLaboratory` physics** — baselines run through a thin adapter
that strips `cov_y` (reproducing their legacy assumed-NoiseModel behaviour)
and the same `ResourceMeter`, so results are reportable both per reactor
condition *and* per actual resource budget. Ten 10-position profiles are
never claimed to cost the same as ten outlet samples.

### 5.12 The truth/inference firewall

The virtual laboratory knows the true kinetic parameters, true concentrations,
true spectral nuisance draws, true transfer-line behaviour, and true
calibration drift. The controller sees **only**: commanded conditions and
positions, spectra/FIDs, quantified concentration estimates, estimated Σ_y,
permitted calibration/QC metadata, and its own accumulated measurements.
`reveal_truth()` counts calls and is used only for post-campaign scoring.
Dedicated tests run a full miniature F campaign and assert: zero reveals
during the loop, no true parameter value reachable anywhere in the emitted
measurements/metadata, and final estimates that do not coincide with the
hidden truth.

---

### 5.13 Framework corrections (v2)

An external-review pass produced a corrected framework (all 78 tests green; new outputs in `results_advanced_v2/`, the previous reference run is preserved). The corrections, each pinned by tests:

1. **One measurement-aware prediction operator.** `InferenceModel.predict_at(θ, u, z, species)` is now the single expected-observation operator; `TransportAwareInference` overrides only it, so estimation, sensitivities, FIM, spatial design, particle/EIG prediction and diagnostic design ALL carry the assumed transfer correction consistently (previously EIG/spatial design bypassed it via direct `bridge.concentrations_at` calls). The assumed delay may be position-dependent, `τ(z) = V(z)/Q_sample`, from commanded geometry only; with the correction disabled the operator reduces exactly to the Layer-1 prediction (tested).
2. **NMR observability in design.** `SpectralCovarianceModel` predicts Σ_y for candidate compositions from the spectral basis/Jacobian plus the fitter's documented augmentation terms — so FIM screening, spatial design and EIG see the concentration/overlap dependence of spectral identifiability without simulating hypothetical spectra and without touching truth-side nuisances. The data-fitted `NoiseSurrogate` remains as fallback.
3. **Truly data-adaptive sequential sampling.** In `adaptive_sequential` mode the FULL Bayesian ensemble update runs after EVERY acquisition (measure → deconvolve → QC → update posterior → recompute information landscape → next z); a test demonstrates that changing the first measured result changes the second selected position. (Any earlier text describing a cheap between-position FIM update no longer applies: the between-position update is the FULL posterior update, gated by QC so only ACCEPTED measurements are assimilated.) Modes: `fixed_equal` / `optimized` (alias `optimized_batch`) / `adaptive_sequential`.
4. **Governor statistics redesigned.** Continuous per-component p-values (χ², z-autocorrelation, species bias, worst experiment×species cell, T-trend), Šidák-combined; uniform alpha-spending over planned rounds bounds the campaign-level false-alarm rate; an optional parametric-bootstrap-with-refit empirical p `p = (1+#{T*≥T})/(B+1)` replaces the earlier binary indicator. A documented `systematic_allowance` κ widens each null by the quantification-systematic share that the claimed Σ_y itself declares. Measured (not claimed): campaign-level false-inadequacy 0/8 under the correct family; detection of a 41 mM structural footprint (~2.7× the declared systematics) is *marginal at budget 6* — the honest detectability-limit finding: structural errors below the instrument's composition-dependent quantification systematics are not reliably detectable by any residual statistic, which sets a concrete calibration requirement for the real Fourier 80.
5. **MEASUREMENT_FAULT is a control state.** Spectral QC now gates BEFORE assimilation: failing spectra are never assimilated, the position is re-acquired up to `max_retries` (metered as reacquisitions), persistent failures are dropped and counted, and a round exceeding the reject fraction PAUSES the campaign (tested end-to-end).
6. **Inverse crime removed.** The truth simulator now deviates from the fitting model in ways the fitter does not know: pseudo-Voigt lineshapes, J-coupling mismatch, static per-group shift miscalibration, AR(1) colored noise, cubic baseline; a FID-truth validation suite fits FID-generated spectra with the analytic-basis fitter. A simulated **per-species response calibration against prepared standards** (public compositions — firewall-clean) absorbs the systematic shape bias exactly as real Fourier-80 calibration would; the residual composition-dependent systematic (~2–3%) is declared in Σ_y and honestly reported where coverage suffers (AcOH in the 1–4 Hz acetyl overlap: ~80–90% at nominal 95%).
7. **Quantification validation** (`sdl_advanced/validation.py`) — three CLEARLY DISTINCT suites, never pooled: **(A) synthetic-mixture stress test** (independent random compositions spanning the *spectral* space; NOT all physically reachable EGDA reaction states), **(B) reaction-reachable validation** (Layer-1 compositions over realistic T/Q/C_cat/z — the states a campaign actually meets), and **(C) FID-truth** (time-domain truth fitted by the analytic-basis fitter). Each reports bias/RMSE/95%-coverage per species, with censored (bound-active) species separated and given one-sided intervals.
8. **Bounded posterior sampling fixed.** `np.clip` replaced by rejection sampling with a Gibbs truncated-MVN fallback; zero samples pile on bounds (tested); `bound_interaction()` reports the Gaussian mass outside the box per parameter.
9. **Resource accounting corrected.** The meter tracks the FULL condition (T, Q, C_EGDA, C_cat): re-sampling z at an unchanged condition logs a zero-cost hold, not a new stabilization; reacquisitions and QC rejections are separate auditable counters; predicted candidate cost and realized event cost use identical assumptions (tested to 1e-9).
10. **Transfer carryover z=0 bug fixed** (`prev_z or z` treated position 0.0 as "no previous position"); regression-pinned.
11. **Benchmark strengthened.** Scenarios: S3 transport ablation (delay/RTD/carryover separated), S4a (hard 3-model ambiguity, extended budget, entropy tracked — may honestly end undecided), S4b (identifiable reversible-vs-irreversible discrimination), S6 λ-sweep Pareto frontier (no single weight vector presented as universal), S7 spatial-mode comparison; per-parameter posterior reporting (estimate, σ, 95% interval, width, bound-active flag, truth error post-hoc only); distributional summaries (median/IQR/bootstrap CI), common-random-number paired comparisons and P(A better than B); smoke/demo/publication modes with fixed seed lists (no cherry-picking). A configurable design objective separates "predictive kinetic model" (V-optimality over an internal reference grid) from "mechanistically identifiable parameters" (D-optimal/EIG).
12. **Firewall tests hardened.** The tautological assertion was replaced by a full object-graph reachability walk proving the virtual laboratory, its truth dict, truth transfer line and truth nuisance objects are unreachable from the controller's object graph, plus a test that the operator holds the ASSUMED (deliberately different) transfer volume, not the truth's.

### 5.14 Targeted scientific corrections (v3)

A second review pass produced these focused corrections (101 tests green; outputs in `results_advanced_v3/`). The architecture is unchanged.

**Reactor geometry and optional packing (configurable, never assumed).** `ReactorGeometry` now carries `packing_enabled` / `bed_void_fraction` / `particle_porosity`. Hydrodynamics use the INTERSTITIAL velocity, so

$$\tau = \frac{\varepsilon\,A\,L}{Q},\qquad \varepsilon = 1 \text{ (unpacked, default)}$$

`bed_void_fraction` is the flowing-interstitial-liquid fraction and is deliberately NOT equated with particle porosity; `particle_porosity` is metadata only and enters no calculation (stagnant intraparticle liquid would need a mass-transfer/holdup model this twin does not claim). Declaring a void fraction without `packing_enabled=True` changes nothing (tested). The EGDA demonstration now uses the **proposed 20 cm × 7 mm ID open CPR** (V_liq = 7.70 mL) — a documented hardware proposal, not an optimization result — read from one `GEOMETRY` dict by every consumer.

**Equilibrium observability (`sdl_advanced/observability.py`).** Because K only enters through the reverse term, a diagnostic now runs BEFORE any campaign, using assumed/literature parameters only (firewall-clean):

$$\phi_1 = \frac{[\mathrm{EGMA}][\mathrm{AcOH}]}{[\mathrm{EGDA}][\mathrm{H_2O}]}\Big/K_1,\qquad \phi_2 = \frac{[\mathrm{EG}][\mathrm{AcOH}]}{[\mathrm{EGMA}][\mathrm{H_2O}]}\Big/K_2$$

together with $|dC/d\ln K_i|$ over the reachable (T, Q, C_cat, z) domain, reported as an SNR against a nominal measurement sigma. The domain scan, a verdict (with an explicit "practically unidentifiable" message when the domain never excites the reverse kinetics) and a φ-profile figure are emitted every run. **Measured:** the 20 cm CPR reaches φ₁ = φ₂ = 1.0 at the hot/slow corner (τ up to 924 s vs 90 s for the old 6 cm tube), so equilibrium-informative experiments EXIST for MBDoE to choose — they are not forced.

**S4b made a valid well-specified test.** The old S4b truth K2 = 0.002 lay BELOW the candidate bound (0.0155), which is why K2 pinned with ~672% error — that was structural misspecification mislabelled as correct-model recovery. S4b now uses the **standard benchmark truth with no override at all** (nothing tuned), verified by a reusable `check_truth_in_domain()` guard that every `well_specified` scenario must pass. The out-of-domain case is preserved but relabelled **S4c_out_of_domain (MODEL-MISSPECIFICATION, not correct-model recovery)**.

**NMR uncertainty calibrated instead of inflated.** `calibrate_empirical()` measures, on PREPARED calibration standards with an INDEPENDENT RNG stream, the systematic bias and inter-species residual covariance the single-spectrum Jacobian cannot see, giving Σ_eff = Σ_fit + Σ_empirical (with bias correction). The hand-set surrogate floors switch OFF when this calibration is active, so the two are never double-counted. Held-out validation showed a constant empirical covariance insufficient, which justified — by the stated criterion — a composition-dependent form σ²(c) = v_const + (rel·c)², both regressed from calibration residuals, with the measured correlation preserved. AcOH coverage rose from **0.59 to within the honest 0.73–1.00 band**; the remaining under-coverage is reported, not papered over. (The v3-final rework of §5.15 closed the gap completely — 0.97 on reachable states; see §6.10.)

**Governor.** `decision_components()` is now the single definition of which diagnostics enter the decision, used identically by `assess()`, the analytic combination and every bootstrap replicate. `bootstrap_pvalue()` refuses any B that cannot resolve the threshold (B ≥ ⌈1/α⌉ − 1, since the smallest attainable p is 1/(B+1)). The allowance κ was **re-derived from the measured held-out coverage** (median implied σ-understatement r = 1.6 ⇒ κ = √(r²−1) ≈ 1.25), not tuned.

**Survivorship bias removed.** Aggregation uses each seed's LAST VALID round, so a campaign paused by the QC gate keeps its last valid posterior instead of vanishing; `campaign_status.csv` records completion, fault flag, QC rejections, reacquisitions, resources and stop reason per strategy × seed, and paired comparisons use explicitly identified common seeds.

**Boundary-aware evidence.** `ModelEnsemble.evidence_reliable` / `evidence_warnings` flag a Laplace evidence whose MAP is pinned or whose posterior mass presses on a bound — so a P(model) = 1.000 arising from a boundary-dominated posterior is never presented as strong evidence.

### 5.15 NMR uncertainty calibration (v3 final)

The measurement covariance was the last substantive scientific defect: v3's
first pass improved point accuracy but its intervals still under-covered
(held-out 0.73–0.79), and — worse — the design layer built its own
uncalibrated `SpectralFitter`, so the covariance MBDoE *expected* was not the
covariance the instrument *delivered*. Both are now fixed.

**One public calibration artifact.** `NMRCalibration` carries only what
prepared Fourier-80 standards would yield: response factors, the empirical
bias vector, the residual correlation matrix, the variance model (constant +
concentration-proportional parts), the interval scale, species order and
metadata. It contains no kinetic truth and no realized nuisance draw (a test
asserts this), so sharing it with the design layer cannot breach the
firewall. `SpectralFitter.apply_calibration()` and
`SpectralCovarianceModel(..., calibration=...)` consume the SAME object, so

$$\Sigma_{\text{expected (MBDoE)}}\quad\text{and}\quad\Sigma_{\text{actual (instrument)}}$$

are two evaluations of one model rather than two independently invented ones.

**Three-dataset hierarchy, three independent RNG streams.**

| Dataset | Standards | RNG offset | Used for |
|---|---|---|---|
| 1 — calibration-fit | 8 prepared mixtures | +900 001 | response factors, bias, correlation, variance model |
| 2 — calibration-check | 8 independent mixtures spanning reachable compositions | +800 002 | the interval **scale** $q_i=\text{quantile}_{0.95}(|e_i|/\sigma_i)/1.96$ |
| 3 — held-out validation | stress / reachable / FID suites | +12 345 | **reporting only — never fitted or scaled on** |

In calibrated mode the ASSUMED surrogate terms (reproducibility floor,
coherent gain, shift jitter) are switched **off** and replaced by the
measured model, so the two never double-count:

$$\Sigma_{\mathrm{eff}} = \underbrace{\Sigma_{\mathrm{fit}}/(r r^{\top})}_{\text{spectral, response-transformed}} + \underbrace{q\,\mathrm{diag}\!\left(\sqrt{v_i + (\rho_i c_i)^2}\right) C \,\mathrm{diag}(\cdot)\,q}_{\text{empirical, calibration-derived}}$$

**A statistical gate, not a slogan.** A Clopper–Pearson one-sided bound
refuses to call a covariance "calibrated" when the held-out coverage is
confidently below 0.85; the v3-first-pass numbers (0.73–0.79) fail it and the
current ones pass. In the publication run **all 12 species × suite cells pass**
(coverage 0.86–1.00, §6.10), including AcOH on reachable states — which was
0.59 before this rework.

**Governor allowance re-derived.** With Σ fixed, κ is measured on
WELL-SPECIFIED control data (`validation.derive_systematic_allowance`) as
κ = √(rms(z)² − 1) with z the standardized residual: rms(z) = 1.11,
per-species z-std [1.00, 0.77, 1.16, 1.06], but residual biases remain in the
overlapped resonances (z-mean EGMA −0.72, AcOH −0.52). Hence **κ = 0.47**,
down from 1.25 when the governor was silently compensating for a broken Σ.
It is derived from control data, never from kinetic-benchmark performance.

## 6. Benchmark results

**This section reports the v3 publication run** — the full Monte Carlo
benchmark executed with `CONFIG["mode"] = "publication"`:

| | |
|---|---|
| Scenarios | 11 (`S1_ideal`, `S2_nmr`, `S3_transport`, `S3ab_delay`, `S3ab_rtd`, `S4a_ambiguity`, `S4b_identifiable`, `S4c_out_of_domain`, `S5_inadequacy`, `S6_resources`, `S7_spatial_modes`) |
| Seeds | **40** common-random-number seeds (1–40), shared across strategies within a scenario |
| Budget | **8** reactor conditions per campaign (S4a: 10), 10 axial positions per profile |
| Reactor | 20 cm × 7 mm i.d., unpacked (ε = 1), τ = 58–924 s over the design box |
| Governor MC | 40 dedicated seeds, independent of the campaign seeds |
| Total campaigns | 1 320 closed-loop campaigns + 40 governor-validation campaigns |
| Wall time | **9.0 h** on a single laptop core (31 042 s scenarios + 1 392 s governor MC + validation/figures). The runner is now process-parallel — see §7.5; the results are unchanged by the worker count |
| Outputs | [`SDL_MBDoE/results_advanced_v3/publication/`](SDL_MBDoE/results_advanced_v3/publication/) — 18 MB, 103 files |

Everything below is **demonstrated by simulation under assumed instrument
parameters**. Nothing here is an experimentally validated Fourier-80 or CPR
property. *Parameter error* = geometric-mean relative error over the estimated
parameters against the hidden truth; *blind RMSE* = concentration RMSE on four
predetermined validation conditions that no controller ever sees. Both are
computable only because this is a simulation. All entries are **medians over
40 seeds** with inter-quartile ranges; the complete distributional summary
(mean, IQR, bootstrap CI) is in `strategy_table.csv`, and every per-round
metric of every campaign is in `benchmark_rounds.csv` (3.8 MB, one row per
campaign-round) with per-parameter posterior rows in `benchmark_params.csv`
(9.5 MB).

### 6.1 Headline: what each layer of realism costs, and what awareness recovers

![Headline benchmark](SDL_MBDoE/results_advanced_v3/publication/figure_readme_headline.png)

*Left: median parameter error. Right: median blind RMSE (log scale). Bars are
medians over 40 seeds, whiskers the IQR. Data: `figure_readme_headline.csv`.*

| Scenario | D — naive spatial MBDoE | F — measurement-aware Bayesian | paired P(F better) |
|---|---|---|---|
| S1 ideal | 10.4 % / 0.74 mM | **5.8 % / 0.63 mM** | 0.70 param, 0.63 RMSE |
| S2 NMR | 41.5 % / 3.09 mM | **16.7 % / 0.97 mM** | 0.80 param, **1.00** RMSE |
| S3 transport (full) | 36.8 % / 10.74 mM | **10.6 % / 1.26 mM** | 0.98 param, **1.00** RMSE |
| S3ab delay only | 41.9 % / 13.08 mM | **19.0 % / 0.96 mM** | — |
| S3ab + RTD | 36.8 % / 11.91 mM | **22.0 % / 1.06 mM** | — |
| S4a ambiguity | 40.7 % / 2.98 mM | **17.2 % / 0.93 mM** | — |
| S4b identifiable | 41.5 % / 3.09 mM | **19.8 % / 0.93 mM** | — |
| S5 inadequacy | **67.9 %** / 23.96 mM | 36.1 % / **48.2 mM** | — (see §6.6) |

`paired_comparisons.csv` holds the per-seed paired differences, their
bootstrap CIs, and P(F better) computed on the 40 matched seeds.

**The result that survives 40 seeds is the same one the 6-seed demo suggested,
and it is a statement about the *measurement model*, not about optimizer
sophistication.** In the ideal scenario the whole advanced apparatus buys
comparatively little (10.4 % → 5.8 %; P(F better) = 0.70, i.e. *not*
decisive). The moment the observation becomes an NMR spectrum, the gap opens
to 2.5×; the moment a physical transfer line is inserted, it opens to 3.5× in
parameters and **8.5× in blind prediction**, with P(F better) = 1.00 on RMSE.
The advanced machinery does not out-optimize the baseline — it stops the
baseline from confidently fitting the wrong quantity.

### 6.2 Scenario 1 — does the new machinery cost anything when it is not needed?

| Strategy | param err % (median) | IQR | blind RMSE mM |
|---|---|---|---|
| A outlet + fixed ladder | 46.7 | 41.7–53.3 | 3.94 |
| B spatial + fixed ladder | 30.0 | 15.8–40.9 | 1.34 |
| C outlet + MBDoE | 15.9 | 10.1–39.6 | 2.04 |
| D spatial + MBDoE | 10.4 | 4.6–19.2 | 0.74 |
| E optimized-z + MBDoE | 7.1 | 3.8–12.3 | 0.64 |
| **F full Bayesian** | **5.8** | 3.7–9.3 | **0.63** |

The ordering A > B > C > D > E > F is now **monotone across 40 seeds** — both
spatial resolution and model-based design pay, and they pay independently
(C vs B isolates design; B vs A isolates spatial sampling). But note the
honest ceiling: E → F is 7.1 % → 5.8 % with heavily overlapping IQRs, and the
paired test gives only P(F better than D) = 0.70. **Under ideal observation
the Bayesian ensemble, the EIG objective and the governor are close to free —
neither a large gain nor a penalty.** Their value appears only when the
observation stops being ideal.

Convergence traces per round, per acquisition and per campaign-second:
`figure_conv_S1_ideal_per_{round,acquisition,time}.png`.

### 6.3 Scenario 2 — realistic NMR: whose covariance does the estimator believe?

| Strategy | param err % | blind RMSE mM |
|---|---|---|
| B (hand-assumed `NoiseModel`) | 50.0 | 8.96 |
| D (hand-assumed `NoiseModel`) | 41.5 | 3.09 |
| **F (calibrated Σ_y from deconvolution)** | **16.7** | **0.97** |

Same spectra, same chemistry, same reactor. The only difference is the
covariance the estimator is given. P(F better than D) = 1.00 on blind RMSE
over 40 paired seeds. Since v3-final both sides of the loop consume the *same*
public `NMRCalibration` artifact (§5.15), so the Σ the designer plans against
is the Σ the instrument actually delivers.

Per-parameter posterior evolution (`figure_params_S2_nmr_F.csv`, round 8
medians over seeds):

| Parameter | 95 % rel. width | rel. error vs truth | bound active |
|---|---|---|---|
| Ea1 | 0.94 % | 0.27 % | 0/40 |
| Ea2 | 1.47 % | 0.43 % | 0/40 |
| k1_ref | 2.42 % | 1.23 % | 0/40 |
| k2_ref | 4.22 % | 1.51 % | 0/40 |
| K2_ref | 6.69 % | 2.14 % | 0/40 |
| **K1_ref** | **514 %** | **132 %** | 1/40 |

Five of six parameters are pinned to 1–7 % width with sub-2.2 % error. **K1
is not identified, and the framework said so before the campaign started** —
see §6.7. This is reported rather than hidden: no interval was widened and no
parameter was screened out to make the table look better.

### 6.4 Scenario 3 — transport reality, and the transport ablation

| Strategy | param err % | blind RMSE mM |
|---|---|---|
| D (naive concentration-at-z) | 36.8 | 10.74 |
| F-uncorr (full Bayesian, transport **un**modeled) | 48.3 | 12.70 |
| **F (mean-delay correction through its own kinetics)** | **10.6** | **1.26** |

![Transport ablation](SDL_MBDoE/results_advanced_v3/publication/figure_transport_ablation.png)

This is the framework's strongest and most transferable claim. With a real
transfer line (τ = V/Q delay, gamma RTD, continued reaction at line
temperature, 5 % carryover), sophisticated statistics **do not help at all**:
F-uncorr is *worse* than the naive baseline D (48.3 % vs 36.8 %) because it
confidently propagates a biased likelihood. Modeling only the commanded mean
delay — one line of physics, through the batch-advance identity — recovers
10.6 % / 1.26 mM. P(F better than F-uncorr) = 0.93 on parameters, 1.00 on
blind RMSE.

The ablation separates *which* transport effect matters
(`figure_transport_ablation.csv`, blind RMSE in mM):

| Transport realism | D (naive) | F (delay-corrected) |
|---|---|---|
| delay + in-line reaction (plug) | 13.08 | 0.96 |
| + RTD dispersion | 11.91 | 1.06 |
| + carryover (full) | 10.74 | 1.26 |

**The mean delay with in-line reaction is the dominant effect by an order of
magnitude**; RTD dispersion and carryover are second-order here, and are the
residual that F does *not* correct (F degrades gracefully, 0.96 → 1.26 mM, as
they are added). That is an actionable engineering conclusion: instrument the
transfer volume and the line temperature first; RTD characterization is a
refinement, not a prerequisite.

### 6.5 Scenario 4 — model discrimination, and its three honest outcomes

The three S4 variants were designed to produce three *different* answers, and
they do.

| | S4a ambiguity | S4b identifiable | S4c out-of-domain |
|---|---|---|---|
| final P(correct model) | **0.35** | **1.00** | 1.00 (on a *wrong* model) |
| final model entropy | 0.37 | 0.00 | 0.00 |
| F param err | 17.2 % | 19.8 % | **116.9 %** |
| F blind RMSE | 0.93 mM | 0.93 mM | **26.4 mM** |

![Model probabilities, S4a](SDL_MBDoE/results_advanced_v3/publication/figure_model_probs_S4a_ambiguity.png)
![Model probabilities, S4b](SDL_MBDoE/results_advanced_v3/publication/figure_model_probs_S4b_identifiable.png)

**S4a — genuinely unresolved, and reported as such.** Pitzer-vs-dilute
activity at 0.25–0.5 M acid is experimentally indistinguishable in this
domain. P(correct) rises 0.33 → 0.45, collapses to 0.15 when the irreversible
member is eliminated, and settles at 0.35 with entropy 0.37 after ten rounds.
The framework does not manufacture a winner. Predictions remain excellent
(0.93 mM) under *either* surviving structure — which is the correct scientific
reading: the two models are observationally equivalent here.

**S4b — discrimination completes when a discriminating region exists.**
P(correct) climbs 0.50 → 0.67 → 0.85 → 0.97 → 0.98 → 0.99 → **1.00** by round
7, entropy → 0, in essentially every seed. Model-EIG finds the discriminating
condition; this is the positive control for §5.8.

**S4c — the honest failure mode.** When the truth lies *outside* the candidate
family (K2 = 0.002, below the parameter-space bound), the ensemble converges
to P = 1.00 on the best available member by round 5 — and is **confidently
wrong**: 116.9 % parameter error, 26.4 mM blind RMSE, roughly 20× worse than
any in-domain scenario. High posterior model probability is *not* evidence of
correctness; only the governor and the blind set can catch this. The scenario
is retained precisely because it is the failure mode a real platform will hit.

### 6.6 Scenario 5 — the model-inadequacy governor

![Governor detection](SDL_MBDoE/results_advanced_v3/publication/figure_governor_S5.png)

The correct (reversible) structure is **removed** from the candidate family;
the truth is a documented hypothetical strongly reversible ester chemistry the
irreversible family cannot represent.

| Governor metric (40 dedicated seeds) | Value |
|---|---|
| Detection probability | **1.00 (40/40)** |
| Median detection round | **4** (range 3–5, of 8) |
| Campaign-level false-alarm rate (well-specified S1/S2) | **0.025 (1/40)** |
| Per-round false-inadequacy rate | **0.0031** |

This is the single largest improvement over v3: detection went from 3/12 to
**40/40** while the false-alarm rate *fell* to 2.5 % at the campaign level.
Both numbers now follow from the corrected Σ_y — with an honest covariance the
systematic allowance drops to κ = 0.47 (§5.15), so the χ²/dof statistic is
finally on a meaningful scale. `figure_governor_S5.png` shows the mechanism in
one picture: the naive loop's 95 % CI shrinks from 10⁴ % to ~12 % — *growing
confidence in a structurally wrong model* — while χ²/dof jumps 1.06 → 8.88 at
round 4 and the state flips to `MODEL_INADEQUATE`, eventually reaching 22.5.

**The honest caveat, unchanged and important.** Detection is not accuracy:

| Strategy | param err % | blind RMSE mM |
|---|---|---|
| D (naive, no governor) | 67.9 | **23.96** |
| F (governor active) | **36.1** | 48.2 |
| F-noGovernor | 38.4 | 51.4 |

F halves the parameter error but its blind RMSE is *twice* D's. When the
governor fires, F switches to diagnostic designs that probe the inadequacy
rather than designs that minimize prediction error — it deliberately spends
budget on finding out the model is wrong. F vs F-noGovernor (36.1 % vs 38.4 %,
48.2 vs 51.4 mM) shows the accuracy effect of the governor itself is within
noise. **The governor's demonstrated value is detection and honesty, not a
prediction win.** A platform that needs the best possible prediction from a
knowingly wrong model should not run diagnostic designs; a platform that needs
to know its model is wrong must.

### 6.7 Equilibrium observability — a pre-campaign identifiability verdict

![Equilibrium observability](SDL_MBDoE/results_advanced_v3/publication/figure_equilibrium_observability.png)

Before any campaign runs, the observability scan
(`equilibrium_observability.csv`) sweeps the design box and reports how close
each condition gets to equilibrium (φ = approach to equilibrium) and how
strongly the outlet composition responds to each equilibrium constant:

| Condition | τ (s) | X_outlet | max φ₁ | max φ₂ | dC/dlnK₁ | dC/dlnK₂ |
|---|---|---|---|---|---|---|
| 40 °C, 0.5 mL/min, 1.0 M | 924 | 0.28 | 0.002 | 0.002 | 0.08 mM | 0.008 mM |
| 100 °C, 0.5 mL/min, 1.0 M | 924 | 0.997 | 0.85 | 0.86 | 5.3 mM | 38.0 mM |
| **160 °C, 0.5 mL/min, 1.0 M** | 924 | 0.998 | **1.000** | **1.000** | 3.9 mM | **35.2 mM** |
| 160 °C, 8 mL/min, 0.5 M | 58 | 0.95 | 0.108 | 0.146 | 3.9 mM | 10.1 mM |

The 20 cm × 7 mm geometry **does** reach full equilibrium (φ = 1.000) at the
hot/slow corner — the old 6 cm tube topped out near φ ≈ 0.9. The verdict is
therefore split, and it is quantitative: the best K₂ signal anywhere in the box
is **38.0 mM ≈ 7.6σ**, so K₂ is identifiable; the best K₁ signal anywhere is
**5.6 mM ≈ 1.1σ**, so **K₁ is not identifiable in this design space, at any
condition, with this instrument** — exactly what the S2 posterior table in §6.3
then shows (514 % width, 132 % error). The diagnostic *predicted* the failure
before the data existed. Fixing it requires changing the experiment (longer
residence time, a different concentration regime, or a direct equilibrium
measurement), not changing the estimator.

### 6.8 Scenario 6 — resource-aware campaigning

![Pareto frontier, S6](SDL_MBDoE/results_advanced_v3/publication/figure_pareto_S6.png)

| Strategy | param err % | blind RMSE mM | EGDA mol | time s | energy kJ |
|---|---|---|---|---|---|
| D | 41.5 | 3.09 | 0.371 | 33 316 | 537 |
| F (pure information) | **16.7** | **0.97** | 0.218 | 33 172 | 400 |
| F-res-0.5× | 23.7 | 1.40 | 0.084 | 17 476 | 107 |
| **F-res-1×** | 21.8 | 1.66 | **0.085** | **17 285** | **107** |
| F-res-2× | 23.1 | 3.57 | 0.078 | 16 261 | 66 |
| F-res-4× | 31.7 | 24.60 | 0.168 | 11 311 | 125 |

Against pure-information F, the λ-weighted F-res-1× uses **61 % less EGDA,
48 % less campaign time and 73 % less energy proxy** for 21.8 % vs 16.7 %
parameter error. Unlike the 6-seed demo, the 40-seed paired test is now
unambiguous about the trade-off being *real*: P(F-res-1× better than F) =
0.275 on parameters and 0.175 on blind RMSE — **the resource penalty does cost
statistical performance, it is not free.** The frontier is flat from 0.5× to
2× and then collapses: at 4× the controller starts refusing informative
experiments outright (24.6 mM blind RMSE, and material use *rises* again
because it needs more rounds). Information per unit resource is the right
objective for an autonomous platform, but the multiplier has to be chosen
inside the flat region — and this benchmark locates it.

### 6.9 Scenario 7 — spatial sampling modes

![Spatial modes, S7](SDL_MBDoE/results_advanced_v3/publication/figure_spatial_modes_S7.png)

| Mode | param err % | blind RMSE mM | seeds paused on QC fault |
|---|---|---|---|
| **F-zbatch (optimized batch positions)** | **16.7** | **0.97** | 0/40 |
| F-zadaptive (data-adaptive within a profile) | 20.5 | 1.05 | **2/40** |
| F-zfixed (equal spacing) | 21.1 | 1.09 | 0/40 |

Optimized batch positions beat equal spacing (16.7 % vs 21.1 %) at equal
acquisition budgets. Truly adaptive within-profile sampling does **not** beat
optimized-batch here (20.5 %) — the information density along z is broad
enough (§5.6) that choosing all positions up front captures most of the
available gain. The 2 paused seeds are the QC gate working as designed: a
spectral fit failed acceptance, the controller declared `MEASUREMENT_FAULT`
and stopped rather than assimilating garbage, and both seeds are retained in
the statistics at their last valid round (no survivorship bias).

The per-budget trajectories (`figure_spatial_modes_S7.csv`) contain a finding
worth stating plainly: parameter error is **non-monotone in sample count** —
it bottoms out near 30–40 spatial samples (12.6–14.3 %) and then *rises* to
17–20 % at 80. Blind RMSE keeps improving monotonically (0.0956 → 0.0011 M).
The cause is K₁: as more data arrive, the posterior for the unidentifiable
K₁ drifts along its flat direction toward a bound and inflates the geometric
mean of relative errors, while every predictive quantity keeps getting better.
This is a property of the *metric* under partial identifiability, not a defect
of the loop — and it is another reason §6.7's pre-campaign verdict matters.

### 6.10 NMR quantification validation

![NMR coverage](SDL_MBDoE/results_advanced_v3/publication/figure_readme_coverage.png)

Three independent held-out suites, none of them the calibration data
(`quantification_validation.csv`):

| Species | Suite A stress mixtures | Suite B reachable states | Suite C FID truth |
|---|---|---|---|
| EGDA | 0.93 (n=74) | 0.88 (n=75) | 0.96 (n=24) |
| EGMA | 0.91 (n=58) | 0.95 (n=88) | 0.88 (n=24) |
| EG | 0.86 (n=74) | 0.91 (n=89) | 1.00 (n=24) |
| AcOH | 0.95 (n=66) | **0.97 (n=90)** | 0.95 (n=22) |

Nominal is 95 %. **Every species in every suite passes the Clopper–Pearson
severe-undercoverage gate** (one-sided upper bound ≥ 0.85), including
Suite C — the hardest case, where the spectra come from the FID engine while
the fitter uses the analytic lineshape model, so there is genuine forward-model
mismatch. The v3 AcOH catastrophe (coverage 0.59 on reachable states, bias
−6 mM) is **resolved**: 0.97 at n=90. Residual biases are honest and reported:
EGMA −6.24 mM and AcOH −2.04 mM on Suite B, both consequences of acetyl-region
overlap at 80 MHz. Coverage is achieved *with* those biases present, because
the calibration's composition-dependent variance σ²(c) = v_const + (rel·c)²
accounts for them rather than assuming them away.

Two entries are at the edge and are not being talked up: EGDA 0.88 on Suite B
and EG 0.86 on Suite A both sit below nominal, pass the gate on sample size
alone, and would be the first things to re-examine on real hardware.

### 6.11 Figures and data

Every figure ships with a same-name CSV of exactly the plotted numbers. All
paths are relative to `SDL_MBDoE/results_advanced_v3/publication/`.

| File(s) | Content |
|---|---|
| `figure_readme_headline.png` | D-vs-F medians + IQR across eight scenarios (both metrics) |
| `figure_readme_coverage.png` | NMR interval coverage, three held-out suites |
| `figure_conv_<scenario>_per_round.png` | parameter error, CI width, P(correct model), blind RMSE vs round |
| `figure_conv_<scenario>_per_acquisition.png` | the same vs NMR acquisitions (the fair-cost axis) |
| `figure_conv_<scenario>_per_time.png` | the same vs campaign seconds |
| `figure_params_<scenario>_F.png` | per-parameter CI width, relative error and bound-activity vs round |
| `figure_model_probs_<S4a\|S4b\|S4c>.png` | posterior model probability and entropy vs round |
| `figure_governor_S5.png` | naive CI shrinkage vs governor χ²/dof and state |
| `figure_transport_ablation.png` | delay → +RTD → +carryover, D vs F |
| `figure_pareto_S6.png` | blind RMSE vs material / time / acquisitions / energy |
| `figure_spatial_modes_S7.png` | fixed vs optimized-batch vs adaptive positions |
| `figure_equilibrium_observability.png` | φ₁, φ₂ and dC/dlnK over the design box |
| `strategy_table.csv/.txt` | median / IQR / mean / bootstrap-CI per scenario × strategy |
| `paired_comparisons.csv` | per-seed paired differences, bootstrap CI, P(a better) |
| `governor_validation.json` | detection probability, detection rounds, false-alarm rate |
| `quantification_validation.csv` | bias / RMSE / coverage per species per suite |
| `benchmark_rounds.csv`, `benchmark_params.csv`, `campaign_status.csv` | every per-round and per-parameter record |
| `benchmark_config.json` | complete reproduction record (truth, geometry, design, nuisance, seeds, runtimes) |
| `make_readme_figures.py` | the post-hoc script that produced the two `figure_readme_*` summaries from the CSVs above |

### 6.12 Where the time went

Per-scenario wall time (`benchmark_config.json` → `runtimes_s`), 40 seeds each:

| Scenario | s | | Scenario | s |
|---|---|---|---|---|
| S7_spatial_modes | **9 971** | | S3ab_rtd | 2 593 |
| S6_resources | 4 023 | | S4a_ambiguity | 1 967 |
| S3_transport | 3 470 | | S2_nmr | 1 916 |
| S3ab_delay | 2 553 | | S5_inadequacy | 1 515 |
| governor MC | 1 392 | | S4b_identifiable | 1 214 |
| | | | S1_ideal | 1 011 |
| | | | S4c_out_of_domain | 810 |

S7 alone is a third of the campaign (three F-variants, one of them adaptive
and therefore re-optimizing positions inside every profile), and S6 is another
eighth (six strategies, four of them F-variants). Together with the governor MC
they account for over half the run — worth knowing before scheduling one.

These are **single-core** times, which is how this run was executed. The
1 360 campaigns are independent, so the runner now distributes them over
processes (`CONFIG["n_workers"]`, §7.5) and every saved file is identical to
the one-core run — only the numbers in this table change.

### 6.13 What this run does *not* establish

- No real CPR or Fourier-80 measurement exists. Every instrument constant is
  an assumption (§8), and coverage of 0.95 against a simulated instrument is
  not coverage against a real one.
- **K₁ is unidentifiable in this design space** (§6.7). Any downstream use of
  the K₁ estimate is unsupported by this benchmark.
- S4c demonstrates that P(model) = 1.00 carries **no** guarantee of
  correctness when the family is misspecified.
- The governor's value is demonstrated as *detection*, not as improved
  prediction (§6.6).
- The resource trade-off is real, not free: P(F-res better than F) < 0.3
  (§6.8).
- The energy figure is a **campaign-cost proxy**, not calorimetry.

---

## 7. User manual

### 7.1 Installation

Requires **Python 3.9+**. From either layer directory:

```bash
pip install -r requirements.txt          # numpy, scipy, matplotlib
```

No package installation needed — scripts run from inside their own directory
and import the local package.

### 7.2 Layer 1: your first run (5 minutes)

```bash
cd PFR_H2SO4_digital_twin
python run_simulation.py         # one operating point + full printed report
python run_temperature_study.py  # T sweep; finds the EGMA optimum
```

Read the printed report top to bottom: feed streams → mixed inlet (note
`[H⁺] ≠ 2×[H₂SO₄]`) → **plug-flow diagnostics advisory** → conversion, EGMA
yield, approach to equilibrium → the verification block (all `PASS` = the
numbers above are sound; treat any `FAIL` as a bug report).

Results are never overwritten: every run creates a folder whose name encodes
the hyperparameters
(`base_case__cat-H2SO4_rev_T150C_L60mm_ID4mm_EGDA0.5M_cat1.5M_Q0.5+0.5/`),
containing every figure **with a CSV twin** of the plotted data, `summary.txt`,
and the exact `run_config.json`.

**Batch mode** — declare lists instead of editing repeatedly:

```bash
python batch_simulation.py           # many base cases
python batch_temperature_study.py    # many temperature sweeps
```

```python
BASE = {...}                                  # reference config
VARY = {"temp_C": [70, 100, 130],             # dotted paths → value lists
        "reactor.length_m": [0.060, 0.200]}
MODE = "grid"                                 # full factorial | "zip" paired
```

`_batch_summary/scenario_index.csv` is the whole study as one sortable table.

Key Layer 1 config switches: `catalyst` (`"H2SO4"`/`"NaOH"` — switches the
model, not just constants), `h_plus_model` (`"equilibrium"`/`"stoichiometric"`),
`ka2_model` (`"tdep"`/`"constant"`), `activity_model` (`"dilute"`/`"pitzer"`),
`equilibrium.reversible`, geometry and stream blocks. The Layer 1 README
documents every parameter.

### 7.3 Layer 2: the baseline A–D campaign

```bash
cd SDL_MBDoE
python tests/self_test.py      # 20 baseline self-tests
python run_sdl_campaign.py     # A/B/C/D campaign (~3 min with the screen)
```

`CONFIG` at the top controls the hidden truth, noise, ports, budget, design
space (per catalyst), identifiability screen, and strategies. Outputs in
`SDL_MBDoE/results/`: error/uncertainty convergence, final estimates vs truth,
a predictive validation figure, per-round history CSV, and the final text
report.

### 7.4 Layer 3: the advanced demonstration campaign

```bash
cd SDL_MBDoE
python run_advanced_campaign.py
```

Runs a single-seed strategy-D-vs-F comparison under the full-physics
`S3_transport` scenario and produces **Figures A–D** plus
`config_used.json` (complete CONFIG + scenario + truth + nuisance record for
exact reproduction). ~13 s. The `CONFIG` dict selects scenario, strategies,
budget, seed, and output directory.

### 7.5 Layer 3: the Monte Carlo benchmark

```bash
python run_advanced_benchmark.py
```

Runs the scenario suite × seeds × strategies and writes the full figure set,
`strategy_table.csv/.txt`, `paired_comparisons.csv`, `benchmark_rounds.csv`
(every per-round metric for every campaign), `benchmark_params.csv`,
`governor_validation.json`, `quantification_validation.csv`,
`equilibrium_observability.csv` and `benchmark_config.json`.

Three modes, selected by `CONFIG["mode"]` at the top of the runner
(`MODES` in `sdl_advanced/benchmark.py`):

| mode | seeds | budget | scenarios | campaigns | wall time (1 core) |
|---|---|---|---|---|---|
| `smoke` | 1 | 3 | 3 | 33 | ~2 min |
| `demo` (default) | 6 | 6 | 11 | 198 | ~45 min |
| `publication` | 40 | 8 | 11 | 1 360 | **~9 h** (the §6 run) |

`CONFIG["progress"] = True` shows a single tqdm bar with % complete and an ETA
weighted by per-strategy cost, so a long run is predictable. The output
directory is created at start-up (`resolve_outdir`), but almost all files are
written in the post-processing phase after every scenario has finished — an
apparently near-empty folder mid-run is expected. Scenario
definitions, the design space, truth, transfer/nuisance assumptions, and
resource-cost λ's all live in
[`sdl_advanced/benchmark.py`](SDL_MBDoE/sdl_advanced/benchmark.py) as one
config block per concern (`sampling_design` → `SpatialDesignConfig`, `nmr` →
`AcquisitionSettings`, `spectral_noise` → `SpectralNuisance`, `transfer` →
`TransferConfig`, `resource_cost` → `ResourceCosts`, `advanced_design` →
`AdvancedDesignConfig`, `model_adequacy` → `GovernorConfig`).

#### Running it on more than one core

One campaign is one task, and a campaign is a **pure function** of
`(scenario, strategy, seed, budget)` — `AdvancedVirtualLaboratory` seeds its
own `default_rng(seed)`, the design selector seeds `default_rng(seed + offset)`,
and nothing anywhere reads global RNG state. So the 1 360 campaigns of a
publication run are embarrassingly parallel. Set:

```python
CONFIG = {
    ...
    "n_workers": "auto",      # None/"auto" → cores−1 · 0 → all cores
                              # 1 → serial  · n → exactly n processes
    "threads_per_worker": 1,  # BLAS threads inside each worker — keep at 1
}
```

**The saved results do not depend on the worker count.** Verified end to end
by running the whole runner both ways and comparing every produced file:

| | |
|---|---|
| Byte-identical | 33 of 36 files — including **every** figure PNG, `benchmark_rounds.csv`, `benchmark_params.csv`, `strategy_table.csv`, `paired_comparisons.csv` and every figure CSV |
| Differ, by design | `runtime_s` in `campaign_status.csv`, `runtimes_s` in `benchmark_config.json`, and the recorded `n_workers` — i.e. **only wall-clock telemetry** |

Three things buy that guarantee, and each has a test in
[`tests/test_parallel.py`](SDL_MBDoE/tests/test_parallel.py):

1. **Submission-order reassembly.** `ordered_map` indexes results by the
   order tasks were *submitted*, never the order they *finished*, so every
   CSV row lands in the position a one-core run would have given it
   (strategy-major, then seed).
2. **Pinned numerical threads.** A multi-threaded BLAS reduction sums in a
   nondeterministic order, which perturbs the last digits and can diverge
   visibly over a long iterative campaign. The runner pins every backend
   (`OMP`/`OPENBLAS`/`MKL`/`VECLIB`/`NUMEXPR`) to one thread **before numpy
   is imported** — that ordering is itself asserted by a test, because doing
   it afterwards silently has no effect. It costs nothing here: the linear
   algebra is 6×6 parameter blocks, far below the size where threading one
   BLAS call pays for itself. It also prevents oversubscription
   (workers × threads > cores is slower, not faster).
3. **The `spawn` start method everywhere.** macOS (Apple Silicon included)
   and Windows already default to it; forcing it on Linux too means a worker
   is always a clean interpreter re-importing the package, so there is one
   behaviour on all three platforms. Only primitives cross the process
   boundary — a task is `(scenario_name, strategy, seed, budget)` and comes
   back as plain dict rows, never a laboratory or a posterior object.

Practical notes:

- On Apple Silicon `os.cpu_count()` counts performance **and** efficiency
  cores. The pool is dynamically load-balanced, so the slower cores simply
  take fewer campaigns; `"auto"` (cores − 1) keeps the machine usable.
- Memory scales with the worker count — each process holds its own numpy,
  laboratory and model ensemble. Drop `n_workers` if the machine starts
  swapping.
- Scaling is bounded by the longest single campaign, so a scenario with few
  seeds parallelizes less well than the full suite. A 6-worker smoke run
  measured 3.3×; `publication`, with 1 360 independent tasks, keeps workers
  saturated for far longer.
- Scenarios must be defined at module level in `SCENARIOS` to be
  parallelizable (a worker rebuilds the scenario by name). `run_scenario`
  detects an unregistered spec and runs it serially rather than silently
  substituting the registered one.
- `threads_per_worker` ≠ 1 is allowed but prints a warning: bit-identical
  agreement with a serial run is no longer guaranteed.

#### The publication audit trail

`CONFIG["audit"] = True` adds a complete, publication-ready record of *how*
every number was produced, under `audit/` in the output directory. It is
**pure reporting**: the recorder draws no random numbers and evaluates no
objective, so the scientific results are byte-identical with it on or off.
That is not an assertion — [`tests/test_audit_regression.py`](SDL_MBDoE/tests/test_audit_regression.py)
runs matched seeds both ways across a baseline, strategy E, the full
Bayesian loop, the NMR + transport loop and a governor trip, and compares
every result row exactly.

| Subfolder | Table | One row per |
|---|---|---|
| `design/` | `design_history.csv` | assimilated acquisition — conditions, z and z/L, spatial/design mode, EIG, QC status, cumulative resources |
| `design/` | `design_candidate_scores.csv` | selected candidate + the best alternatives, with screen score, EIG terms, resource penalty, total utility |
| `inference/` | `model_probabilities_long.csv` | (round, candidate model), carrying `evidence_reliable`, bound contact and the warning text |
| `inference/` | `posterior_covariance_long.csv` | (round, parameter pair) — covariance and correlation |
| `inference/` | `identifiability_summary.csv` | final-round parameter — estimate, error, interval width, bound flag, eigenvalues, effective rank, condition number |
| `governor/` | `governor_diagnostics_long.csv` | round — state, combined and per-component p-values, threshold, χ²/dof, trends, trigger reasons, affected species/region, first detection |
| `measurement/` | `nmr_measurements_long.csv` | (acquisition attempt, species) — fitted concentration, σ, censoring, QC flags, residual RMS, fit condition number, disposition |
| `measurement/` | `nmr_calibration_by_seed.csv` | (seed, species) — response factor, bias, variance terms, interval scale, correlations |
| `resources/` | `resource_events_long.csv` | metered event — incremental and cumulative time, material, waste, energy, motion, acquisitions |
| `resources/` | `controller_timing.csv` | round — fitting and design-selection wall time |
| `validation/` | `blind_predictions_long.csv` | (validation condition, z, species) — true, predicted, residual, squared error |

Plus `convergence_summary.csv`, `parameter_domain_checks.csv`,
`run_integrity_report.json`, `reproducibility_manifest.json` (git commit,
resolved config, package versions, platform, SHA-256 of every output), the
three representative NMR examples under `nmr_examples/`, and the new figures
under `figures/`.

Three design decisions in there are worth knowing, because each one is a
place where the easy implementation would have been wrong:

1. **The audit may not consume randomness.** The EIG is a Monte-Carlo
   estimate drawing on the selector's generator. Scoring extra candidates
   "just for the report" would advance that stream and change every later
   design decision. So the table exports the candidates the selector
   *actually evaluated* (`top_k`) with their EIG terms, and the remaining
   screened alternatives with `eig_evaluated = 0` and blank EIG columns.
2. **Failed campaigns must not vanish.** `convergence_summary.csv` reports
   every metric twice: `basis="observed"` (only campaigns that reached the
   round — honest, but the sample thins after a fault) and `basis="locf"`
   (last observation carried forward, constant *n*). `n_total`,
   `n_observed` and `n_faulted_cumulative` sit on every row, and the
   convergence figures draw the active count as a grey step, so a curve
   that improves because the sample shrank is visible as such.
3. **Eigen-diagnostics are labelled by what they actually are.** Baselines
   A–E are WLS/FIM, so `identifiability_summary.csv` reports genuine Fisher
   eigenvalues. F is a Laplace posterior whose curvature is `F + prior
   precision`; calling those "FIM eigenvalues" would overstate what the data
   alone determined, so they carry `matrix_kind = posterior_precision`.

Rejected spectra deserve a note of their own: the QC gate drops them before
assimilation, so they appear in no posterior-derived table. They are
recorded at the point of rejection instead, which is why
`nmr_measurements_long.csv` has a `disposition` column
(`accepted` / `accepted_after_reacquisition` / `failed_qc` / `rejected`)
rather than only a count.

**Cost**: the trail roughly doubles the output size of a smoke run and is
expected to add a few hundred MB to a 40-seed publication run (mostly
`nmr_measurements_long.csv` and `posterior_covariance_long.csv`).
Runtime overhead measured on the smoke run was ~15%, almost all of it in
writing the tables rather than in the campaigns.

The representative NMR spectra are generated **after** the benchmark from a
fixed seed of their own (`nmr_examples.EXAMPLE_SEED`) at three documented
compositions — low conversion, the overlap-rich intermediate case, and near
complete conversion. They are deliberately not sampled from a campaign:
pulling a spectrum out of a seeded run would either mean carrying every
spectrum through the run or re-simulating inside a live stream, and the
second would move the campaign.

### 7.6 Tests

```bash
cd SDL_MBDoE
for f in tests/*.py; do python $f; done      # 16 files, all standalone
```

**137 tests across 16 files, all standalone-runnable and pytest-compatible.**
The acceptance criteria they pin down include: existing Layer 1/2 tests unchanged;
`fixed_equal` ≡ the legacy port layout; reactor-length rescaling; optimized
positions in-bounds/spaced/unique/deterministic; zero-noise deconvolution
recovery to numerical tolerance; Monte Carlo interval coverage; all-transport-
off ≡ legacy observation (to 10⁻¹²); delta-RTD ≡ legacy `extra_tau_s`
(to 10⁻⁸); zero truth reveals in a full F campaign and no truth values
reachable in any emitted object; governor false-positive and detection
behaviour; non-negative, event-auditable resource totals; hard-bound
enforcement on candidates; parallel-vs-serial bit-identity of the whole
benchmark; audit-on/audit-off bit-identity of every scientific result;
configurable geometry and optional packing
(ε-aware τ, interstitial vs superficial velocity); the equilibrium-observability
verdict; the single public `NMRCalibration` artifact shared by the measurement
and design layers; the Clopper–Pearson severe-undercoverage gate; the
governor's shared decision-component definition and bootstrap resolution guard;
boundary-aware evidence reliability; and survivorship-free aggregation.

| File | Tests | File | Tests |
|---|---|---|---|
| `self_test.py` (Layer 2 baseline) | 20 | `test_posterior.py` | 6 |
| `test_geometry_packing.py` | 12 | `test_deconvolution.py` | 6 |
| `test_nmr_calibration.py` | 12 | `test_spatial_design.py` | 6 |
| `test_calibration_governor.py` | 9 | `test_adequacy.py` | 5 |
| `test_spectral.py` | 7 | `test_observation_operator.py` | 5 |
| `test_transfer.py` | 7 | `test_truth_firewall.py` | 5 |
| `test_resource_accounting.py` | 7 | `test_measurement_fault.py` | 4 |
| `test_parallel.py` | 13 | `test_audit_regression.py` | 13 |

### 7.7 Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: pfr_twin` / `sdl` | Run from inside the layer's own directory. |
| `catalyst='NaOH' requires reversible=False` | Saponification is irreversible by construction. |
| `Config has no parameter path '...'` | Batch `VARY` path typo — dotted, case-sensitive. |
| A verification line says `FAIL` | Treat as a bug; report the config. |
| `Candidate violates hard bound ...` | An operating-condition candidate lies outside `continuous_bounds` — the advanced selector refuses rather than penalizes. |
| Governor reports `MEASUREMENT_FAULT` | The spectral fits themselves failed QC (residual ≫ noise scale). Inspect `meta["qc"]` before blaming the kinetics. |
| `[H⁺]` unexpectedly low at high T | Expected: `ka2_model="tdep"` collapses the second dissociation when hot. |

---

## 8. Scientific integrity and calibration status

No literature parameters were manufactured. Every number in the framework
belongs to one of four provenance classes, kept explicitly separate:

1. **Layer 1 literature-anchored kinetics/thermodynamics** (§3.9) — classical
   physical-organic benchmarks with documented statistical factors;
   *recalibrate against your reactor before quantitative use*.
2. **Values inherited from `sim_nmr(2).py`** — aqueous-literature chemical
   shifts, J = 4.7 Hz, the water-shift law, linewidth classes. Provenance
   comments preserved; **not upgraded to "validated Fourier 80 parameters"**.
3. **Assumed simulation nuisance parameters** — every noise/drift/response/
   transport number in §5.3–5.5 and the Σ_y augmentation constants of §5.4.
   All are plausible-magnitude *assumptions*, marked **`CAL:`** in the code.
4. **Quantities requiring measurement on the physical hardware** — the `CAL:`
   set maps one-to-one onto a future calibration campaign: pure-component
   standards (shifts, linewidths, response factors, T₁ by inversion recovery),
   replicate standards (reproducibility floor, gain drift, shift jitter),
   tracer experiments (transfer volume, RTD shape, flush behaviour), and
   plant data (stabilization times, energy coefficients — the current energy
   number is a **campaign-cost proxy, not calorimetry**).

The hardware-transition path is explicit: `AdvancedVirtualLaboratory` is the
only class that *generates* spectra. Replacing `_observe_nmr`'s simulated
`(ppm, spectrum)` with a real Fourier 80 acquisition — and the `CAL:` constants
with measured ones — leaves the deconvolution, inference, governor, design,
and resource layers untouched. That separation (chemistry ≠ transport ≠ NMR
forward model ≠ spectral inversion ≠ inference ≠ design) is enforced by the
module boundaries, not by convention.

Every simulation output directory contains the complete configuration and RNG
seeds needed for exact reproduction (`run_config.json`, `config_used.json`,
`benchmark_config.json`).

**Calibration status after the v3 publication run.** The NMR covariance model
is now *calibrated* in the defensible sense — a single public artifact drives
both the measurement and design layers, and every held-out species × suite cell
passes the Clopper–Pearson gate (§6.10). That statement is about a **simulated**
instrument: it says the framework's internal uncertainty accounting is
self-consistent and honest, **not** that a Fourier 80 would deliver these
intervals. The first hardware calibration campaign replaces datasets 1 and 2 of
§5.15 with prepared standards and re-runs the same gate; if real coverage lands
below 0.85 the framework will say so rather than proceed. Two known weak spots
to test first: EGDA on reachable states (0.88) and EG on stress mixtures (0.86),
plus the persistent acetyl-overlap biases (EGMA −6.2 mM, AcOH −2.0 mM).

---

## 9. Code map

```
PFR_H2SO4_digital_twin/                    LAYER 1 (unchanged)
├── pfr_twin/
│   ├── parameters.py    constants, dataclasses, catalyst factory, provenance
│   ├── mixer.py         ideal micromixer → inlet state (speciation at T)
│   ├── speciation.py    Ka₂(T) Clarke–Glew + Pitzer activity model
│   ├── kinetics.py      Arrhenius + van 't Hoff; per-route rate laws
│   ├── reactor.py       1D PFR integration, stoichiometry, result object
│   ├── analytical.py    closed-form irreversible solution + equilibrium solver
│   ├── diagnostics.py   Re / dispersion / plug-flow advisories
│   ├── plotting.py      figures, each with paired CSV
│   ├── runio.py         hyperparameter-tagged run folders
│   └── batch.py         parameter-grid expansion
├── run_simulation.py / run_temperature_study.py
└── batch_simulation.py / batch_temperature_study.py

SDL_MBDoE/
├── sdl/                                   LAYER 2 (baseline, preserved)
│   ├── layer1_bridge.py  the ONLY module importing Layer 1
│   ├── parameters.py     θ space, transforms, bounds, CI interpretation
│   ├── observation.py    Measurement (now with optional cov_y/meta) + NoiseModel
│   ├── truth.py          legacy VirtualLaboratory (hidden truth + noise)
│   ├── inference.py      WLS, sensitivities, F = SᵀΣ⁻¹S, V ≈ F⁻¹  (cov_y-aware)
│   ├── design.py         fixed designs + D-optimal MBDoE selector
│   ├── identifiability.py pre-campaign identifiability screen
│   ├── campaign.py       closed-loop runner, strategies A–D
│   └── reporting.py      baseline figures/CSVs/report
├── sdl_advanced/                          LAYER 3 (new)
│   ├── spectral.py       NMR forward model (analytic + FID engines)
│   ├── spectral_fit.py   VarPro deconvolution → (ŷ, Σ_y, QC); bootstrap
│   ├── transfer.py       capillary transport: τ(z), gamma RTD, carryover
│   ├── spatial_design.py fixed_equal / optimized / adaptive positions
│   ├── instrument.py     AdvancedVirtualLaboratory (all hidden truth)
│   ├── resources.py      ResourceCosts + auditable ResourceMeter
│   ├── posterior.py      GaussianPrior + LaplacePosterior (MAP, evidence)
│   ├── model_ensemble.py candidate family M1–M3, TransportAwareInference
│   ├── adequacy.py       AdequacyGovernor (4 states, calibrated tests)
│   ├── bayes_design.py   NoiseSurrogate, EIG estimator, AdvancedSelector
│   ├── controller.py     run_strategy_e / run_strategy_f (+ ablations)
│   ├── benchmark.py      scenarios S1–S7, modes, fairness adapter, metrics
│   ├── observability.py  equilibrium-observability scan + identifiability verdict
│   ├── parallel.py       spawn pool + submission-order map (results unchanged)
│   ├── audit.py          passive recorder: candidate scores, timings, QC dispositions
│   ├── audit_export.py   post-campaign long tables (design/inference/governor/...)
│   ├── audit_summary.py  convergence (observed + LOCF), integrity, manifest
│   ├── nmr_examples.py   three representative spectra, own fixed seed
│   ├── validation.py     held-out NMR suites, kappa derivation from control data
│   └── reporting.py      figure set, strategy table, paired CSVs
├── run_sdl_campaign.py            baseline A–D entry point
├── run_advanced_campaign.py       Layer 3 demo (Figures A–D)
├── run_advanced_benchmark.py      Monte Carlo benchmark (smoke/demo/publication)
├── results_advanced_v3/publication/   the §6 run: 40 seeds x budget 8 x 11 scenarios
└── tests/                             137 tests, 16 files
    ├── self_test.py               20 baseline tests (unchanged)
    ├── test_geometry_packing.py   geometry/packing/observability/ladder (12)
    ├── test_nmr_calibration.py    one public calibration artifact + gate (12)
    ├── test_calibration_governor.py  governor components + bootstrap + PSD (9)
    ├── test_spectral.py           forward model (7)
    ├── test_transfer.py           transport + legacy limits (7)
    ├── test_resource_accounting.py  auditable costs (7)
    ├── test_deconvolution.py      quantification + coverage (6)
    ├── test_spatial_design.py     position optimality (6)
    ├── test_posterior.py          Laplace + evidence + cov_y contract (6)
    ├── test_adequacy.py           governor detection/calibration (5)
    ├── test_observation_operator.py  the single prediction operator (5)
    ├── test_truth_firewall.py     end-to-end firewall (5)
    ├── test_measurement_fault.py  QC-before-assimilation (4)
    ├── test_parallel.py           parallel == serial, byte for byte (13)
    └── test_audit_regression.py   audit ON == audit OFF, exactly (13)

EGDA_NMR_sim/sim_nmr(2).py         standalone spectrum visualization tool
                                   (NOT used inside the campaign loop)
BatchSweep_Analysis/               post-processing of Layer 1 batch sweeps
```

Layer-specific detail:
[`PFR_H2SO4_digital_twin/README.md`](PFR_H2SO4_digital_twin/README.md) and
[`SDL_MBDoE/README.md`](SDL_MBDoE/README.md).

---

## 10. Extending the framework

- **Replace simulated NMR with the real Fourier 80.** Swap the instrument side
  of `sdl_advanced/instrument.py` (`_observe_nmr`) for a driver returning real
  `(ppm, spectrum)` arrays, and replace the `CAL:` constants with calibrated
  values (§8). Nothing downstream changes.
- **Swap the Laplace posterior for SMC/MCMC.** Implement the three-method
  contract of `LaplacePosterior` (`fit_map / sample / log_evidence`); the
  ensemble, governor, and selector are agnostic.
- **Residual model discovery** (the optional Layer 3 follow-on): the governor
  already localizes *where* and *for which species* the model family fails;
  a sparse-residual-source-term layer (integral/ODE form, chemically sensible
  candidate terms, evidence-gated) can be added behind the
  `MODEL_INADEQUATE` state without touching the rest.
- **Recalibrate Layer 1** to your data; **add species/reactions/catalysts**
  per the Layer 1 README recipes (extend `SPECIES`, the stoichiometric matrix,
  `rates()`, and the corresponding invariant check).
- **Non-isothermal operation / axial dispersion** remain out of scope by
  construction (diagnosed, not solved).

## 11. Glossary and nomenclature

| Symbol | Meaning | Units |
|---|---|---|
| `C_i` | molar concentration of species *i* | mol/L |
| `r₁, r₂` | net volumetric rates of steps 1, 2 | mol/(L·s) |
| `u` | superficial velocity Q/A | m/s |
| `τ` | residence time x/u; `τ_tr(z)` transfer delay V(z)/Q_s | s |
| `k_i(T)`, `K_i(T)` | rate / hydrolysis-equilibrium constants | L/(mol·s), — |
| `θ` | estimated kinetic parameter vector (scaled) | mixed |
| `S` | sensitivity matrix ∂ŷ/∂θ | mixed |
| `F`, `V` | Fisher information, parameter covariance | mixed |
| `z`, `z/L` | capillary sampling position (continuous) | m, — |
| `F_z` | information of one acquisition at z | mixed |
| `Σ_y` | measurement covariance (from deconvolution in Layer 3) | M² |
| `η` | spectral-fit nonlinear nuisances (shift, linewidth, pool, phase) | mixed |
| `a` | fitted spectral amplitudes = concentrations | mol/L |
| `g(τ)` | transfer-line residence-time distribution (gamma) | 1/s |
| `f` | carryover fraction e^(−V_flush/V_line) | — |
| `E_g` | flow/relaxation response factor (1 when disabled) | — |
| `Z_M` | Laplace model evidence | — |
| `I(d)`, `I_M(d)` | expected information gain (total, model part) | nats |
| `ρ̂` | pooled lag-1 whitened-residual autocorrelation along z | — |
| `U(d)` | resource-aware design utility | nats-equivalent |

**Abbreviations.** EGDA/EGMA/EG ethylene glycol di-/mono-acetate, glycol ·
AcOH acetic acid (total acetate pool) · PFR plug flow reactor · CPR compact
profile reactor (Reacnostics; one moving sampling capillary) · MBDoE
model-based design of experiments · SDL self-driving laboratory · FIM Fisher
information matrix · WLS weighted least squares · FID free induction decay ·
VarPro variable projection · BVLS bounded-variable least squares · RTD
residence-time distribution · EIG expected information gain · MAP maximum a
posteriori · QC quality control.

## 12. References

Kinetics/thermodynamics anchors (see inline provenance in
[`pfr_twin/parameters.py`](PFR_H2SO4_digital_twin/pfr_twin/parameters.py)):

- R. P. Bell, *Acid–Base Catalysis* — specific acid catalysis, A-AC2.
- A. J. Kirby, in *Comprehensive Chemical Kinetics* Vol. 10 — ester hydrolysis.
- M. Berthelot & L. Péan de Saint-Gilles (1862) — acetate esterification
  equilibrium, `K_est ≈ 4`.
- J. K. Hovey & L. G. Hepler, *J. Chem. Soc. Faraday Trans.* **86** (1990)
  2831 — bisulfate dissociation thermochemistry (the `ka2_model:"tdep"` anchor).
- P. Sippola & P. Taskinen, *J. Chem. Eng. Data* **59** (2014) 2389; K. S.
  Pitzer, R. N. Roy & L. F. Silvester, *J. Am. Chem. Soc.* **99** (1977) 4930
  — Pitzer parameters and K₂(T) for aqueous H₂SO₄.
- G. Taylor / R. Aris — laminar-tube dispersion (the `Bo` diagnostic).
- O. Levenspiel, *Chemical Reaction Engineering* — PFR design equations,
  series-reaction selectivity, tanks-in-series RTD (the transfer-line model).

Experimental design, inference, and diagnostics:

- G. Franceschini & S. Macchietto, *Chem. Eng. Sci.* **63** (2008) 4846 —
  MBDoE review (D/A-criteria used by Layers 2–3).
- K. Chaloner & I. Verdinelli, *Statist. Sci.* **10** (1995) 273 — Bayesian
  experimental design; the decision-theoretic EIG objective of §5.8.
- E. G. Ryan et al., *Int. Statist. Rev.* **84** (2016) 128 — nested Monte
  Carlo estimators of expected information gain.
- R. E. Kass & A. E. Raftery, *J. Am. Statist. Assoc.* **90** (1995) 773 —
  Bayes factors and the Laplace evidence approximation of §5.7.
- G. E. P. Box & W. J. Hill, *Technometrics* **9** (1967) 57 — model
  discrimination among rival kinetic models (ancestor of §5.9's
  discrimination state).
- G. H. Golub & V. Pereyra, *SIAM J. Numer. Anal.* **10** (1973) 413 —
  variable projection for separable nonlinear least squares (§5.4).
- C. L. Lawson & R. J. Hanson, *Solving Least Squares Problems* — NNLS/BVLS.

---

*A digital twin is only as honest as its self-checks, and an autonomous
laboratory is only as honest as its measurement model. Every run in this
framework verifies itself — the reactor against closed forms and invariants,
the instrument against bootstrap coverage, the controller against a firewall
that counts every glance at the truth, and the governor against its own
false-positive rate.*
