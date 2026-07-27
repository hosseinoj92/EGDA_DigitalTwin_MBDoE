# EGDA Homogeneous Hydrolysis — Digital Twin & Self-Driving Laboratory

A two-layer computational framework for the **homogeneously catalyzed cleavage
of ethylene glycol diacetate (EGDA)** in a continuous tubular reactor:

| Layer | Directory | What it is |
|---|---|---|
| **Layer 1** | [`PFR_H2SO4_digital_twin/`](PFR_H2SO4_digital_twin/) | A deterministic **digital twin** of the reactor — given operating conditions, it predicts what comes out. |
| **Layer 2** | [`SDL_MBDoE/`](SDL_MBDoE/) | A **virtual self-driving laboratory** wrapped around Layer 1 — it designs its own experiments to *learn* the kinetics it does not know. |

Layer 1 answers *"what will the reactor do?"*. Layer 2 answers the harder,
inverse question: *"how do I find out, with the fewest experiments?"*

---

## Table of contents

1. [The chemistry](#1-the-chemistry)
2. [What problem this solves](#2-what-problem-this-solves)
3. [Layer 1 — the digital twin](#3-layer-1--the-digital-twin)
   - [Model hierarchy and assumptions](#31-model-hierarchy-and-assumptions)
   - [Governing equations](#32-governing-equations)
   - [Rate laws in full](#33-rate-laws-in-full)
   - [Catalyst speciation](#34-catalyst-speciation)
   - [Chemical equilibrium](#35-chemical-equilibrium-acid-route)
   - [Numerical method](#36-numerical-method)
   - [Self-verification](#37-self-verification-runs-on-every-simulation)
   - [Plug-flow validity diagnostics](#38-plug-flow-validity-diagnostics)
   - [Parameter provenance](#39-parameter-provenance)
4. [Layer 2 — the self-driving laboratory](#4-layer-2--the-self-driving-laboratory)
   - [The inverse problem](#41-the-inverse-problem)
   - [Parameter estimation](#42-parameter-estimation-weighted-least-squares)
   - [Uncertainty: Fisher information](#43-uncertainty-quantification-fisher-information)
   - [MBDoE: choosing the next experiment](#44-mbdoe-choosing-the-next-experiment)
   - [The A/B/C/D showcase](#45-the-abcd-showcase)
   - [The truth/inference firewall](#46-the-truthinference-firewall)
5. [User manual](#5-user-manual)
   - [Installation](#51-installation)
   - [Your first run](#52-your-first-run-5-minutes)
   - [Understanding the output folder](#53-understanding-the-output-folder)
   - [Every configuration parameter](#54-every-configuration-parameter-explained)
   - [Batch mode](#55-batch-mode-many-scenarios-at-once)
   - [Running Layer 2](#56-running-layer-2)
   - [Worked examples](#57-worked-examples)
   - [Troubleshooting](#58-troubleshooting)
6. [Code map](#6-code-map)
7. [Extending the framework](#7-extending-the-framework)
8. [Glossary and nomenclature](#8-glossary-and-nomenclature)
9. [References](#9-references)

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

The framework supports **two catalyst systems**, which are chemically
different reactions, not two speeds of the same one:

### Route A — sulfuric acid (specific acid catalysis, A-AC2)

```
EGDA + H₂O  ⇌  EGMA + AcOH        (K₁)
EGMA + H₂O  ⇌  EG   + AcOH        (K₂)
```

H⁺ protonates the carbonyl, activating it toward attack by water. The proton
is regenerated — a **true catalyst**, not consumed, so [H⁺] is constant along
the reactor. Critically, **acid catalysis accelerates the forward and reverse
directions equally** (that is what a catalyst does), so the same H⁺ that
drives hydrolysis also drives the reverse Fischer esterification. These
reactions are *reversible*, and at high conversion the back-reaction matters.

### Route B — sodium hydroxide (saponification, B-AC2)

```
EGDA + OH⁻  →  EGMA + AcO⁻
EGMA + OH⁻  →  EG   + AcO⁻
```

Hydroxide attacks the carbonyl directly. Three consequences make this a
genuinely different model, not a re-parameterization:

1. **~1000× faster** per mole of catalyst (k ≈ 0.11 vs ≈ 1.1 × 10⁻⁴ L mol⁻¹ s⁻¹
   at 25 °C for the ethyl acetate benchmark).
2. **Not catalytic.** The leaving group is the carboxylate — the conjugate
   base of acetic acid (pKa 4.76), which cannot give its proton back to
   hydroxide (pKa 15.7). **One OH⁻ is destroyed per acetate group released.**
   Hydroxide is a *stoichiometric reagent* that can run out, at which point
   the reaction simply stops. This is why soap-making uses a measured lye
   charge, not a catalytic pinch.
3. **Irreversible.** A carboxylate anion is not electrophilic enough to be
   re-attacked by an alcohol, and the deprotonation step is ~10⁹-fold
   downhill. There is no back-reaction to model.

---

## 2. What problem this solves

### The forward problem (Layer 1)

Building a real flow reactor and scanning temperature × flow rate × catalyst
loading × tube geometry costs weeks of lab time and material. A digital twin
that faithfully encodes the chemistry lets you scan that space in seconds,
find the interesting corners, and only then go to the bench. Concretely it
answers:

- What residence time and temperature maximize EGMA yield?
- How much catalyst do I need for 90% conversion in a 200 mm tube?
- With NaOH, how much base is needed before the reaction stops running out?
- Is my tube even behaving as a plug-flow reactor at this flow rate?
- How close to chemical equilibrium is my outlet?

### The inverse problem (Layer 2)

A twin is only as good as its kinetic parameters, and those must come from
experiments. The classical approach — a temperature ladder at fixed
conditions — is *wasteful*: many of those experiments carry almost no
information about the parameters you care about, and you cannot tell which
ones until afterwards.

**Model-Based Design of Experiments (MBDoE)** turns this around. After each
experiment, the framework re-estimates the parameters, computes how uncertain
they still are, and then asks: *among all experiments I could run next, which
one would shrink that uncertainty the most?* It runs that one. The result is
the same parameter precision from far fewer experiments — and, importantly,
a *quantified* statement of how precise the answer is.

Layer 2 demonstrates this on a **virtual laboratory**: a hidden "true"
parameter set the algorithms cannot see, observed only through synthetic
noisy measurements. Because the truth is known to the *benchmark* (but never
to the estimator), you can measure exactly how well each experimental
strategy performs — impossible with real data, where truth is unknown.

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

Assumptions, each with its justification and the code that enforces or checks it:

| # | Assumption | Justification / check |
|---|---|---|
| 1 | Instant, perfect micromixing; flows additive | Micromixer residence ≪ reactor residence; dilute aqueous streams |
| 2 | Isothermal | Feeds pre-heated; dilute solutions, modest ΔH; **not** an energy-balance model |
| 3 | Ideal plug flow (no axial dispersion, flat velocity) | **Quantified, not assumed** — `diagnostics.py` reports Re, radial diffusion time vs τ, and Bodenstein number, and warns when the idealization is optimistic |
| 4 | Constant liquid density; properties ≈ water | Dilute aqueous solutions |
| 5 | Ideal-solution activities (concentration-based Keq) | Activity coefficients lumped into K_ref, ΔH — recalibrate for concentrated feeds |
| 6 | H⁺ constant along x (acid route) | True catalyst, not consumed; AcOH (pKa 4.76) contributes negligibly against a strong-acid background |
| 7 | Ka₂ of H₂SO₄ at 25 °C | Its T-dependence is weak compared with the Arrhenius terms |

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
same equations as a batch reactor in time.** (Layer 2 uses this to model a
sample that keeps reacting in a transfer line.)

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

Water is a genuine reactant on the acid route (it is the nucleophile); on the
alkaline route hydroxide is, and water is untouched.

**Conserved quantities.** These balances imply exact linear invariants, which
the code uses as a numerical self-check:

| Invariant | Acid | Base | Meaning |
|---|---|---|---|
| `C_EGDA + C_EGMA + C_EG` | ✔ | ✔ | diol backbones are neither created nor destroyed |
| `2·C_EGDA + C_EGMA + C_AcOH` | ✔ | ✔ | acetate groups are conserved (bound + free) |
| `C_H₂O + C_AcOH` | ✔ | — | one water consumed per acetate released |
| `C_OH + C_AcOH` | — | ✔ | one hydroxide consumed per acetate released |
| `C_H₂O` | — | ✔ | water is not consumed by saponification |

### 3.3 Rate laws in full

#### Acid route — reversible, thermodynamically consistent

$$r_1 = \frac{k_1(T)\,[\mathrm{H^+}]}{C_{w,\mathrm{ref}}}\left([\mathrm{EGDA}][\mathrm{H_2O}] - \frac{[\mathrm{EGMA}][\mathrm{AcOH}]}{K_1(T)}\right)$$

$$r_2 = \frac{k_2(T)\,[\mathrm{H^+}]}{C_{w,\mathrm{ref}}}\left([\mathrm{EGMA}][\mathrm{H_2O}] - \frac{[\mathrm{EG}][\mathrm{AcOH}]}{K_2(T)}\right)$$

with Arrhenius rate constants and van 't Hoff equilibrium constants:

$$k_i(T) = A_i \exp\!\left(-\frac{E_{a,i}}{RT}\right), \qquad K_i(T) = K_{i,\mathrm{ref}} \exp\!\left[-\frac{\Delta H_i}{R}\left(\frac{1}{T}-\frac{1}{T_{\mathrm{ref}}}\right)\right]$$

Three design decisions are worth spelling out, because they are what make the
model trustworthy rather than merely plausible:

**(a) Reverse constants are derived, never fitted independently.** Writing the
bracket as `(forward − reverse/K)` means the implied reverse rate constant is

$$k_{i,\mathrm{rev}}(T) = \frac{k_i(T)}{K_i(T)\, C_{w,\mathrm{ref}}}$$

so the net rate vanishes **exactly** when the reaction quotient reaches the
equilibrium constant, `Q_i = K_i`. This is the principle of *microscopic
reversibility*, and building it into the algebra means the model cannot
violate thermodynamics for *any* parameter values — including nonsense values
an optimizer might try during fitting. A model with an independently fitted
`k_rev` can drift into predicting perpetual motion; this one cannot.

**(b) The reference water concentration keeps the literature meaning of k.**
`C_w,ref = 55.34 M` is pure water at 25 °C. In dilute solution `[H₂O] ≈ C_w,ref`,
so the forward term collapses to the classical pseudo-first-order form
`k_i[H⁺][ester]` — meaning `k₁, k₂` retain exactly the units and numerical
values reported in the physical-organic literature, while the model still
handles concentrated or water-lean feeds correctly.

**(c) Why reversibility matters here.** With ~50 M water the equilibria lie far
toward hydrolysis, so a beginner might drop the reverse terms. They would
lose: the conversion ceiling (X_eq < 100%), the residual EGMA that persists at
equilibrium, the rate slowdown as AcOH accumulates, and any ability to model
the reaction run backwards (esterification). Setting `reversible: False`
recovers that simpler model for comparison.

#### Alkaline route — irreversible, self-quenching

$$r_1 = k_1(T)\,[\mathrm{OH^-}][\mathrm{EGDA}], \qquad r_2 = k_2(T)\,[\mathrm{OH^-}][\mathrm{EGMA}]$$

Formally simpler, but **[OH⁻] is a state variable**, not a parameter. It
appears in its own ODE and falls as the reaction proceeds, so these equations
are still nonlinear and the reaction *self-terminates* when hydroxide runs
out. The conversion ceiling is set by stoichiometry:

$$\text{acetate released} \le [\mathrm{OH^-}]_0, \qquad \text{so} \qquad \frac{[\mathrm{OH^-}]_0}{2[\mathrm{EGDA}]_0 + [\mathrm{EGMA}]_0} < 1 \implies \text{base-limited}$$

The twin reports this ratio and the fraction of OH⁻ consumed on every alkaline
run. Note the useful consequence: **sub-stoichiometric NaOH is a selectivity
tool** — with enough base for roughly one cleavage per molecule, the reaction
stalls near EGMA.

### 3.4 Catalyst speciation

Sulfuric acid is diprotic. Its first dissociation is complete, the second is
not:

$$\mathrm{H_2SO_4} \to \mathrm{H^+} + \mathrm{HSO_4^-} \quad(\text{complete}), \qquad \mathrm{HSO_4^-} \rightleftharpoons \mathrm{H^+} + \mathrm{SO_4^{2-}} \quad (K_{a2} = 1.02\times10^{-2}\ \mathrm{M})$$

So `[H⁺] ≠ 2[H₂SO₄]`. Solving the second equilibrium with `x` the extent of
the second dissociation:

$$K_{a2} = \frac{(c+x)\,x}{c-x} \;\Longrightarrow\; x^2 + (c + K_{a2})x - K_{a2}c = 0, \qquad [\mathrm{H^+}] = c + x$$

At 1 M H₂SO₄ this gives ≈ 1.01 protons per molecule, not 2 — a factor-of-two
error if you assume full diprotic dissociation. Set `h_plus_model:
"stoichiometric"` with `n_eff_protons` to override.

NaOH is a strong base with complete dissociation: `[OH⁻] = [NaOH]` at the
inlet, then depleting.

### 3.5 Chemical equilibrium (acid route)

At infinite residence time both steps reach equilibrium simultaneously.
Writing the extents of reaction as `x₁, x₂` (mol/L) the composition is

```
[EGDA] = a₀ − x₁          [AcOH] = d₀ + x₁ + x₂
[EGMA] = b₀ + x₁ − x₂     [H₂O]  = w₀ − x₁ − x₂
[EG]   = c₀ + x₂
```

and the equilibrium conditions are two coupled nonlinear equations:

$$\frac{(b_0+x_1-x_2)(d_0+x_1+x_2)}{(a_0-x_1)(w_0-x_1-x_2)} = K_1, \qquad \frac{(c_0+x_2)(d_0+x_1+x_2)}{(b_0+x_1-x_2)(w_0-x_1-x_2)} = K_2$$

`analytical.equilibrium_state()` solves these by Gauss–Seidel alternation:
each single-extent condition is monotone in its own extent, so it has a
unique bracketed root found by Brent's method; alternating converges rapidly.
Negative extents are handled naturally, so an **esterification-direction feed**
(EG + AcOH, no ester) equilibrates correctly.

This equilibrium state is reported as the `t → ∞` ceiling on every acid run,
drawn as dashed guides on the concentration figure, and — crucially — used as
a *thermodynamic consistency test* (§3.7).

### 3.6 Numerical method

The ODE system is integrated with `scipy.integrate.solve_ivp`:

- **Method** LSODA (adaptive, switches between non-stiff Adams and stiff BDF)
- **Tolerances** `rtol = 1e-9`, `atol = 1e-12` — far tighter than any physical
  uncertainty, so numerical error never confounds a physical conclusion
- **Output grid** 201 points along x by default

Both models are mildly nonlinear (bilinear in concentrations) and non-stiff at
realistic conditions. The acid *irreversible limit* is exactly linear, which
is what makes the closed-form verification below possible.

### 3.7 Self-verification (runs on every simulation)

A digital twin that cannot check itself is a liability. Every run prints a
verification block:

**1. Independent reference solution.**
*Acid route:* the irreversible limit is exactly the linear series reaction
A → B → C, whose closed form is classical:

$$C_A(\tau) = C_{A0}e^{-\kappa_1\tau}, \qquad C_B(\tau) = C_{B0}e^{-\kappa_2\tau} + C_{A0}\frac{\kappa_1}{\kappa_2-\kappa_1}\left(e^{-\kappa_1\tau}-e^{-\kappa_2\tau}\right)$$

(with the L'Hôpital limit when κ₁ = κ₂), and the rest from the linear
invariants. The integrator is checked against it; typical agreement is
~10⁻¹⁰ relative. *NaOH route:* no closed form exists (depleting reagent), so
LSODA is cross-checked against **Radau**, a structurally different implicit
integrator.

**2. Invariant conservation.** The linear invariants of §3.2 must be constant
along x. Typical drift ~10⁻¹³ relative.

**3. Thermodynamic consistency (acid, reversible only).** The net rates are
evaluated *at* the independently computed coupled-equilibrium composition and
must vanish. Typical residual ~10⁻¹⁵ relative to the inlet rate. This closes
the loop between the kinetic and thermodynamic halves of the model: they are
not merely compatible, they are provably the same equilibrium.

**4. Limiting-reagent bookkeeping (NaOH only).** Acetate released must equal
hydroxide consumed, exactly.

Every check prints `PASS`/`FAIL` with the numerical residual. Treat any
`FAIL` as a bug report.

### 3.8 Plug-flow validity diagnostics

Ideal plug flow is an idealization, and in a narrow lab tube at low flow it
can be a poor one. `diagnostics.py` reports on every run:

- **Reynolds number** `Re = ρuD/μ` and the flow regime.
- **Radial diffusion time vs residence time**, `t_rad = R²/D_m` vs `τ`. If
  `t_rad ≪ τ`, molecules sample the whole cross-section and the flow is
  radially well-mixed (Taylor–Aris regime). If `t_rad ≫ τ`, streamlines stay
  segregated and the parabolic laminar velocity profile means a broad
  residence-time distribution — real conversion will fall short of the ideal
  prediction.
- **Bodenstein number** `Bo = uL/D_ax` with the Taylor–Aris dispersion
  coefficient `D_ax = D_m + u²R²/(48 D_m)`, when applicable. `Bo ≳ 100` means
  under ~1% deviation from ideal PFR.

The twin prints an explicit ADVISORY when its own idealization is optimistic —
please read it rather than the conversion number alone.

### 3.9 Parameter provenance

**These are literature-anchored order-of-magnitude estimates, not measurements
of your system.** Recalibrate against your own data before quantitative use —
that is exactly what Layer 2 is for.

| Step | A (L mol⁻¹ s⁻¹) | Eₐ (kJ/mol) | k(25 °C) | K_hyd(25 °C) | ΔH_hyd (kJ/mol) |
|---|---|---|---|---|---|
| **H₂SO₄** 1: EGDA ⇌ EGMA | 1.0 × 10⁶ | 55.0 | 2.27 × 10⁻⁴ | 0.50 | +5 |
| **H₂SO₄** 2: EGMA ⇌ EG | 1.0 × 10⁶ | 57.0 | 1.03 × 10⁻⁴ | 0.125 | +5 |
| **NaOH** 1: EGDA → EGMA | 2.6 × 10⁷ | 46.0 | 0.226 | — (irreversible) | — |
| **NaOH** 2: EGMA → EG | 2.6 × 10⁷ | 48.0 | 0.101 | — | — |

**Rate constants.** Anchored to the classic benchmarks for acetate esters in
water: acid-catalyzed ethyl acetate hydrolysis, `k ≈ 1.1 × 10⁻⁴ L mol⁻¹ s⁻¹`
at 25 °C with `Eₐ ≈ 54–65 kJ/mol`; alkaline saponification of ethyl acetate,
`k ≈ 0.11 L mol⁻¹ s⁻¹` at 25 °C with `Eₐ ≈ 46–48 kJ/mol`.

**Statistical factors.** EGDA has two chemically equivalent acetate groups, so
step 1 gets a factor ≈ 2 relative to a mono-ester; EGMA has one remaining
group, slightly deactivated by the free hydroxyl, so step 2 sits near the
mono-ester benchmark. This gives `k₁/k₂ ≈ 2`.

**Equilibrium constants.** Anchored to the classic acetate esterification
equilibrium (`K_est ≈ 4` per ester group; Berthelot & Péan de Saint-Gilles),
hence hydrolysis `K_group ≈ 0.25`. Since Δn = 0 for these reactions,
mole-fraction and concentration constants coincide. The same statistical
logic applies: step 1 cleaves one of *two* equivalent esters while its reverse
esterifies the *single* EGMA hydroxyl → `K₁ = 2K_group = 0.50`; step 2 cleaves
one ester while its reverse esterifies one of *two* equivalent EG hydroxyls →
`K₂ = K_group/2 = 0.125`. Their product `K₁K₂ = K_group²` is then the
statistically consistent overall constant. Esterification is nearly
thermoneutral, hence the small positive ΔH for the hydrolysis direction.

---

## 4. Layer 2 — the self-driving laboratory

### 4.1 The inverse problem

You measure concentrations; you want rate constants. Formally: find the
parameter vector **θ** minimizing the mismatch between model predictions
**ŷ**(θ) and measurements **y**, and quantify how well θ is thereby determined.

**Parameterization matters enormously.** Fitting `(A, Eₐ)` directly is badly
conditioned: over a narrow temperature window, `ln A` and `Eₐ` are almost
perfectly correlated (raising both leaves k nearly unchanged), so the fit is a
long thin valley. The standard cure — used here — is to re-reference to a
temperature inside the experimental window:

$$k_i(T) = k_{i,\mathrm{ref}}\exp\!\left[-\frac{E_{a,i}}{R}\left(\frac{1}{T}-\frac{1}{T_{\mathrm{ref}}}\right)\right], \qquad T_{\mathrm{ref}} = 60\ ^\circ\mathrm{C}$$

Now `k_ref` (the rate at the middle of your data) and `Eₐ` (its temperature
slope) are nearly independent. The estimator works in a scaled vector where
rate and equilibrium constants are log-transformed — enforcing positivity and
making σ(ln k) directly a *relative* uncertainty:

| Route | θ (scaled) | p |
|---|---|---|
| H₂SO₄ | `[ln k₁_ref, Eₐ₁/1000, ln k₂_ref, Eₐ₂/1000, ln K₁_ref, ln K₂_ref]` | 6 |
| NaOH | `[ln k₁_ref, Eₐ₁/1000, ln k₂_ref, Eₐ₂/1000]` | 4 |

The van 't Hoff slopes ΔH are held at literature values — near-athermal
equilibria are simply not identifiable from a 30–90 °C window, and trying
would only inflate every other confidence interval.

### 4.2 Parameter estimation (weighted least squares)

Measurements are species-major vectors, `y[i·N_z + k] = C_i(z_k)`, over
sampling ports `z_k`. Synthetic CPR-NMR noise is heteroscedastic with an
optional correlated pair (overlapping EGDA/EGMA acetyl resonances):

$$\sigma_i = \sigma_{\mathrm{abs}} + \sigma_{\mathrm{rel}}\,C_i, \qquad \Sigma_{y}[p,q] = \rho\,\sigma_p\sigma_q \ \text{for the overlap pair at the same port}$$

Estimation minimizes the **whitened** residual — each experiment's residual is
pre-multiplied by the inverse Cholesky factor of its covariance, which turns a
correlated, unequal-variance problem into an ordinary least-squares one:

$$\hat{\theta} = \arg\min_\theta \sum_e \left\| L_e^{-1}\left(\hat{y}_e(\theta) - y_e\right)\right\|^2, \qquad \Sigma_e = L_eL_e^\top$$

solved by `scipy.optimize.least_squares` (trust-region reflective, bounded,
warm-started from the previous round).

### 4.3 Uncertainty quantification (Fisher information)

The local sensitivity matrix **S** = ∂ŷ/∂θ (central finite differences in the
scaled space) gives the **Fisher Information Matrix**:

$$F = \sum_e S_e^\top \Sigma_e^{-1} S_e, \qquad V_\theta \approx F^{-1}$$

This is the Cramér–Rao bound: `F⁻¹` is the smallest covariance any unbiased
estimator can achieve. Its interpretation is geometric — `F` defines the
uncertainty ellipsoid in parameter space, and each experiment adds its own
information contribution. The reports expose:

- **σ per parameter** and 95% confidence intervals (asymmetric for
  log-parameters: `[v·e^{−1.96σ}, v·e^{+1.96σ}]`);
- the **correlation matrix**, which reveals *which* parameters are confounded;
- the **eigenvalue spectrum of F** — a near-zero eigenvalue means a direction
  in parameter space the data simply cannot see (structural non-identifiability);
- the **D-criterion** `(det V)^{1/2p}`, a single scalar "geometric-mean σ".

### 4.4 MBDoE: choosing the next experiment

Given the current estimate θ̂, the *expected* information from a candidate
experiment **u** is computable **before running it** — sensitivities are a
property of the model, not of the data. D-optimal design picks:

$$u^\star = \arg\max_{u\,\in\,\mathcal{U}} \ \log\det\!\left(F_{\text{current}} + F_{\text{candidate}}(\hat\theta, u)\right)$$

Maximizing `log det F` minimizes the *volume* of the joint uncertainty
ellipsoid — it attacks whichever direction is currently worst-known, which is
precisely why it beats a fixed ladder. (A-optimality, minimizing the trace of
`V`, is available via config.) The candidate grid `𝒰` is a factorial over
temperature × total flow × catalyst molarity.

**What MBDoE discovers, unprompted, is the best evidence it works:**

- *Acid route:* the equilibrium constants K₁, K₂ are only visible in data near
  equilibrium, so the algorithm requests **hot, slow, high-acid** conditions
  (90 °C, 4 mL/min) that a temperature ladder at fixed flow never visits.
- *NaOH route:* the reaction is so fast that outlet data mostly encode the
  stoichiometric endpoint, not the kinetics — so the algorithm requests
  **cold, fast-flow** conditions (10 °C, 40 mL/min) that pull the transient
  back into the observable window.

Nobody told it either of those things.

### 4.5 The A/B/C/D showcase

Four strategies on identical truth, budget, initial guess, and first experiment,
isolating the two independent factors:

| | Fixed design | Autonomous MBDoE |
|---|---|---|
| **Outlet only** (4 obs/exp) | **A** — the conventional baseline | **C** — value of smart selection |
| **8-port spatial profile** (32 obs/exp) | **B** — value of spatial data | **D** — both together |

Representative results (seed 7, 8 experiments):

| Route | Metric | A | B | C | D |
|---|---|---|---|---|---|
| H₂SO₄ (6 params) | mean rel. error | 16.8% | 5.9% | 30.8% | **8.0%** |
| | log det F | 17.5 | 27.6 | 20.4 | **32.5** |
| NaOH (4 params) | mean rel. error | 11.8% | 15.9% | 10.1% | **2.0%** |
| | max 95% CI | ~10⁸% | 64.8% | 45.8% | **10.1%** |
| | log det F | −4.2 | 12.6 | 8.7 | **19.2** |

Read `log det F` as the reliable information measure; the parameter-error
column depends on the particular noise draw (change `seed` to see the spread).
Strategy A on the NaOH route is the instructive failure: an unbounded CI with
correlation 0.998 between `ln k₁` and `Eₐ₁` — the outlet alone cannot separate
"fast reaction" from "steep temperature dependence" when everything reaches
the stoichiometric endpoint anyway.

### 4.6 The truth/inference firewall

The virtual lab's true parameters live in a private attribute of
`VirtualLaboratory`. Estimation and design code touches the truth **only**
through `run_experiment(u, spatial)`, which returns noisy measurements.
`reveal_truth()` exists solely for post-campaign benchmarking, **counts its
own calls**, and a self-test asserts the count is zero during the loop. This
prevents the classic simulation-study self-deception of accidentally letting
the estimator peek at the answer.

Optional systematic effects can be injected into the truth *only*, to study
robustness against model mismatch: `transfer_time_s` (sample keeps reacting
in the transfer line), `calibration_gain` (per-species NMR bias), and
`noise_assumed` ≠ `noise_true` (mis-specified covariance).

---

## 5. User manual

### 5.1 Installation

Requires **Python 3.9+**. From either layer directory:

```bash
pip install -r requirements.txt          # numpy, scipy, matplotlib
```

No installation of the packages themselves is needed — scripts are run from
inside their own directory and import the local package.

> **Windows note:** if `python` on your PATH resolves to a bundled
> interpreter (e.g. Inkscape's) that lacks numpy/scipy, call your real one
> explicitly, e.g.
> `& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" run_simulation.py`.

### 5.2 Your first run (5 minutes)

```bash
cd PFR_H2SO4_digital_twin
python run_simulation.py
```

This simulates one operating point and prints a full report. Reading it top to
bottom:

```
EGDA PFR digital twin - base case (H2SO4, reversible hydrolysis/esterification)
```
↳ which catalyst route and model variant is active.

```
Feed streams (before micromixer):        what you dosed
Mixed inlet (x = 0):                     what the reactor actually sees
  [H+] catalytic = 1.0100 M              ← note: NOT 2 × [H2SO4]
```

```
Flow / plug-flow diagnostics:            ← READ THIS
  Reynolds number : 23.3 (laminar)
  ADVISORY: laminar flow with t_rad >> tau -> radially segregated ...
```
↳ how trustworthy the plug-flow idealization is for *your* geometry and flow.

```
Reactor solution:
  EGDA conversion X    :  99.22 %
  EGMA yield  Y_EGMA   :  13.64 %
  Approach to equilibrium : Q1/K1 = 0.177   (1.000 = equilibrated)
  Equilibrium limit (t->inf) : X_eq = 99.96 %
```
↳ performance, plus how much room is left before thermodynamics stops you.

```
Verification:
  Integrator vs closed form ... = 1.81e-10  [PASS]
  Invariant conservation ...    = 1.71e-13  [PASS]
  Thermodynamic consistency ... = 3.03e-15  [PASS]
```
↳ the twin's self-audit. All `PASS` means the numbers above are sound.

Then try the sweep, which finds the EGMA optimum:

```bash
python run_temperature_study.py
```

### 5.3 Understanding the output folder

Results are **never overwritten**. Every run creates a folder whose *name
encodes the hyperparameters that produced it*:

```
results/
└── base_case__cat-H2SO4_rev_T150C_L60mm_ID4mm_EGDA0.5M_cat1.5M_Q0.5+0.5/
    ├── concentration_profiles.png   ├── concentration_profiles.csv
    ├── conversion_yield.png         ├── conversion_yield.csv
    ├── solver_validation.png        ├── solver_validation.csv
    ├── profiles.csv          full axial table (all species, X, yields)
    ├── summary.txt           the printed report
    └── run_config.json       the EXACT config + computed metrics
```

Folder name fields: `cat-<catalyst>` · `rev`/`irr` (reversible or not) ·
`T<temp>C` (or `T<lo>-<hi>C-<n>pts` for sweeps) · `L<length>mm_ID<diameter>mm` ·
`EGDA<c>M_cat<c>M` · `Q<q1>+<q2>` (mL/min).

**Every figure has a CSV twin** with the same basename holding exactly the
plotted data — so you can re-plot in Excel/Origin, or re-analyze, without
re-running anything. The folder name is a readable summary;
`run_config.json` is the exact, machine-readable record.

### 5.4 Every configuration parameter explained

Both single-run scripts have one `CONFIG` dict at the top. Edit and re-run.

| Parameter | Units | Meaning and guidance |
|---|---|---|
| `catalyst` | — | `"H2SO4"` or `"NaOH"`. Switches the whole model, not just constants. |
| `temp_C` | °C | Isothermal reactor temperature. *(single-run only)* |
| `T_min_C`, `T_max_C`, `n_points` | °C, — | Sweep window and resolution. *(temperature study only)* |
| `profile_temps_C` | °C | Temperatures for the axial-profile overlay figure. *(temperature study only)* |
| `stream1.Q_mL_min` | mL/min | EGDA pump rate. With stream 2, sets residence time τ = V/Q. |
| `stream1.C_EGDA_M` | mol/L | EGDA molarity *before* mixing — halved by 1:1 blending. |
| `stream1.density_g_L` | g/L | Used to reconstruct `[H₂O]` and for Reynolds number. |
| `stream2.Q_mL_min` | mL/min | Catalyst pump rate. |
| `stream2.C_cat_M` | mol/L | Catalyst molarity before mixing. **On NaOH this also sets the stoichiometric ceiling** — check the reported NaOH/acetate ratio. |
| `stream2.density_g_L` | g/L | ≈1060 for 2 M H₂SO₄; ≈1080 for 2 M NaOH. |
| `reactor.length_m` | m | Tube length. τ ∝ L. |
| `reactor.diameter_m` | m | Inner diameter. Affects τ (∝ D²) *and* plug-flow validity — narrow bore is better mixed radially. |
| `h_plus_model` | — | `"equilibrium"` (solve HSO₄⁻ Ka₂, recommended) or `"stoichiometric"`. *Acid only.* |
| `n_eff_protons` | — | Protons per H₂SO₄, stoichiometric model only. |
| `equilibrium.reversible` | bool | `False` = legacy irreversible model, for comparison. *Acid only.* |
| `equilibrium.K1_ref`, `K2_ref` | — | Hydrolysis equilibrium constants at 25 °C. *Acid only.* |
| `equilibrium.dH1_kJ`, `dH2_kJ` | kJ/mol | van 't Hoff slopes, hydrolysis direction. *Acid only.* |
| `outdir` | — | Output root; relative paths resolve next to the script. |

> **On the NaOH route** the entire `equilibrium` block and `h_plus_model` are
> ignored — saponification is irreversible and has no proton speciation. The
> code rejects `catalyst="NaOH"` with `reversible=True` rather than silently
> ignoring it.

### 5.5 Batch mode (many scenarios at once)

Instead of editing CONFIG repeatedly, declare **lists** of values and run
everything in one go:

```bash
python batch_simulation.py           # many base cases
python batch_temperature_study.py    # many temperature sweeps
```

Each batch script has three knobs:

```python
BASE = {...}                     # reference config (same shape as CONFIG)

VARY = {                         # DOTTED paths into BASE → lists of values
    "temp_C":           [70.0, 100.0, 130.0],
    "reactor.length_m": [0.060, 0.200],
    "stream2.C_cat_M":  [0.5, 1.5],
}

MODE = "grid"                    # "grid" = full factorial | "zip" = paired
```

- **`"grid"`** — full factorial: the example above runs 3 × 2 × 2 = **12
  scenarios**. Use it to map a design space.
- **`"zip"`** — lists walked together (all must be the same length), giving
  hand-picked scenarios. Essential when parameters must move together, e.g.
  comparing catalysts whose useful temperature windows differ:

  ```python
  VARY = {"catalyst": ["H2SO4", "NaOH"],
          "T_min_C":  [40.0,      5.0],
          "T_max_C":  [150.0,    60.0]}
  MODE = "zip"                     # → 2 scenarios, not 8
  ```

Any parameter in `BASE` can be varied by its dotted path — `temp_C`,
`reactor.diameter_m`, `stream1.Q_mL_min`, `equilibrium.reversible`, … A typo
in a path raises immediately with the offending name rather than silently
doing nothing.

**Batch output:**

```
results/batch_base_case/
├── s00__cat-H2SO4_rev_T70C_L60mm_ID4mm_EGDA0.5M_cat0.5M_Q0.5+0.5/
│   └── (a complete single-run folder: figures, paired CSVs, summary, config)
├── s01__.../  s02__.../  ...
└── _batch_summary/
    ├── scenario_index.csv     ← one row per scenario: varied params + all KPIs
    ├── outlet_kpis.png/.csv       grouped bars, X / Y_EGMA / Y_EG
    ├── conversion_vs_x.png/.csv   axial conversion, one curve per scenario
    ├── egma_vs_x.png/.csv         axial EGMA, one curve per scenario
    └── batch_config.json          BASE + VARY + MODE exactly as run
```

`scenario_index.csv` is the file to open first — it is the whole study as one
sortable table. The temperature-study batch produces the analogous
`conversion_vs_T`, `egma_yield_vs_T`, `eg_yield_vs_T`, and `egma_optimum`
comparisons.

### 5.6 Running Layer 2

```bash
cd SDL_MBDoE
python tests/self_test.py      # 10 self-tests, ~1 min — run this first
python run_sdl_campaign.py     # the A/B/C/D campaign, ~1 min
```

`CONFIG` in `run_sdl_campaign.py` controls the hidden truth, the noise model,
the sampling ports, the budget, the design space (per catalyst), and the
strategies to compare. Set `"catalyst": "NaOH"` to switch routes — the
parameter set, design space, and truth block all follow automatically.

Outputs in `SDL_MBDoE/results/`: convergence of parameter error and of the
D-criterion, final estimates with confidence intervals against truth, a
predictive validation check at an unseen condition, the full per-round
history CSV, and a text report with correlation matrices and FIM eigenvalues.

### 5.7 Worked examples

**"Where is the EGMA yield optimum for my tube?"**
```bash
python run_temperature_study.py     # after setting your geometry/flows in CONFIG
```
The console prints the optimum temperature and yield; `temperature_sweep.csv`
has the full curve.

**"Which of length / temperature / acid loading matters most?"**
Set all three as lists in `batch_simulation.py` with `MODE = "grid"`, run, then
sort `_batch_summary/scenario_index.csv` by `Y_EGMA`.

**"How much NaOH do I need?"**
```python
BASE.update({"catalyst": "NaOH", "temp_C": 40.0})
VARY = {"stream2.C_cat_M": [0.25, 0.5, 1.0, 1.5, 2.0, 3.0]}
```
Watch `NaOH_per_acetate_group` and `OH_consumed_frac` in the index CSV: below
a ratio of 1.0 the reaction is base-limited and stalls — which, deliberately
used, is a way to stop at EGMA.

**"Does ignoring the back-reaction matter for my conditions?"**
```python
VARY = {"equilibrium.reversible": [True, False], "temp_C": [70.0, 110.0, 150.0]}
```
The gap between the pairs is the error you would make with an irreversible
model; it grows with conversion.

**"Is my reactor really plug flow?"**
Read the diagnostics block. If you see the `t_rad >> tau` advisory, either
narrow the tube, raise the flow, or add static mixing — and treat the
predicted conversion as an optimistic bound until you do.

### 5.8 Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: pfr_twin` | Run from inside `PFR_H2SO4_digital_twin/` (scripts import the local package). |
| `ModuleNotFoundError: numpy` | Wrong interpreter — see the Windows note in §5.1. |
| `catalyst='NaOH' requires reversible=False` | Saponification is irreversible by construction; use `default_kinetics("NaOH")` or leave the equilibrium block alone. |
| `catalyst='H2SO4' but a feed stream declares NaOH` | Acid/base cross-feeds would neutralize; not modelled. Match `catalyst` to your stream 2 solute. |
| `Config has no parameter path 'temp_c'` | A `VARY` key typo — paths are case-sensitive and dotted, e.g. `reactor.length_m`. |
| `mode='zip' requires equal-length value lists` | In zip mode every list must have the same length; use `grid` for a factorial. |
| A verification line says `FAIL` | Treat as a bug. Check for extreme parameters; report the config. |
| `Water depletion QUESTIONABLE` | Concentrated feed — the reversible model handles it, but check the pseudo-order assumption if you set `reversible: False`. |
| Conversion looks impossibly high/low | Check `[H⁺]` in the report (not 2 × [H₂SO₄]!), the NaOH stoichiometric ratio, and τ in the diagnostics. |

---

## 6. Code map

```
PFR_H2SO4_digital_twin/
├── pfr_twin/
│   ├── parameters.py    all constants, dataclasses, catalyst factory, provenance
│   ├── mixer.py         ideal micromixer, H⁺/OH⁻ speciation → inlet state
│   ├── kinetics.py      Arrhenius + van 't Hoff constants; per-route rate laws
│   ├── reactor.py       1D PFR integration, per-route stoichiometry, result object
│   ├── analytical.py    closed-form irreversible solution + equilibrium solver
│   ├── diagnostics.py   Re / dispersion / plug-flow validity advisories
│   ├── plotting.py      styled figures — each writes its paired data CSV
│   ├── runio.py         hyperparameter-tagged run folders, CSV writers
│   └── batch.py         parameter-grid expansion for the batch scripts
├── run_simulation.py            single base case  (CONFIG at top)
├── run_temperature_study.py     single T sweep    (CONFIG at top)
├── batch_simulation.py          many base cases   (BASE + VARY + MODE)
└── batch_temperature_study.py   many T sweeps     (BASE + VARY + MODE)

SDL_MBDoE/
├── sdl/
│   ├── layer1_bridge.py  the ONLY module importing Layer 1
│   ├── parameters.py     θ space, transforms, bounds, CI interpretation
│   ├── observation.py    measurement layout + noise model → Σ_y
│   ├── truth.py          VirtualLaboratory (hidden truth + synthetic NMR)
│   ├── inference.py      WLS estimation, sensitivities, F = SᵀΣ⁻¹S, V ≈ F⁻¹
│   ├── design.py         fixed designs + D-optimal MBDoE selector
│   ├── campaign.py       closed-loop runner, strategies A–D
│   └── reporting.py      showcase figures, CSVs, final report
├── run_sdl_campaign.py   entry point (CONFIG at top)
└── tests/self_test.py    10 self-tests, standalone or pytest
```

The single-run scripts expose reusable functions (`simulate_case`/`run_case`,
`simulate_sweep`/`run_sweep`) which the batch scripts import — so the physics
has exactly one implementation, and batch mode cannot drift from single mode.

Layer-specific detail lives in
[`PFR_H2SO4_digital_twin/README.md`](PFR_H2SO4_digital_twin/README.md) and
[`SDL_MBDoE/README.md`](SDL_MBDoE/README.md).

## 7. Extending the framework

- **Recalibrate to your data.** Replace the `ArrheniusStep`/`EquilibriumStep`
  defaults in `parameters.py`, or run a Layer 2 campaign against real
  measurements.
- **Add a species or reaction.** Extend `SPECIES`, add a column to the
  stoichiometric matrices in `reactor.py`, and a term in `kinetics.rates()`.
  Add the corresponding invariant to the verification block.
- **Add a catalyst.** Add it to `CATALYSTS`, give it a branch in
  `KineticModel.rates()`, a stoichiometry in `nu_matrix()`, speciation in
  `mixer.mix_streams()`, and defaults in `default_kinetics()`.
- **Non-isothermal operation** would require an energy balance coupled to the
  species ODEs — the current model is isothermal by construction.
- **Axial dispersion** would turn the ODEs into a boundary-value problem
  (Danckwerts conditions); today dispersion is *diagnosed*, not solved.

## 8. Glossary and nomenclature

| Symbol | Meaning | Units |
|---|---|---|
| `C_i` | molar concentration of species *i* | mol/L |
| `r₁, r₂` | net volumetric rates of steps 1, 2 | mol/(L·s) |
| `ν_ij` | stoichiometric coefficient | — |
| `u` | superficial velocity, Q/A | m/s |
| `τ` | residence time, x/u (outlet: V/Q) | s |
| `k_i(T)` | second-order rate constant | L/(mol·s) |
| `κ_i` | `k_i · c_cat`, pseudo-first-order constant | 1/s |
| `A, Eₐ` | Arrhenius pre-exponential, activation energy | L/(mol·s), J/mol |
| `K_i(T)` | hydrolysis equilibrium constant | — (Δn = 0) |
| `Q_i` | reaction quotient (equals `K_i` at equilibrium) | — |
| `ΔH` | reaction enthalpy, hydrolysis direction | J/mol |
| `X` | conversion of fed EGDA | — |
| `Y_i` | yield of *i* on a diol-backbone basis | — |
| `S` | selectivity, Y/X | — |
| `Re`, `Bo` | Reynolds, Bodenstein numbers | — |
| `θ` | estimated parameter vector | mixed |
| `S` (Layer 2) | sensitivity matrix ∂ŷ/∂θ | mixed |
| `F`, `V` | Fisher information, parameter covariance | mixed |

**Abbreviations.** EGDA ethylene glycol diacetate · EGMA ethylene glycol
monoacetate · EG ethylene glycol · AcOH acetic acid (total acetate pool) ·
PFR plug flow reactor · MBDoE model-based design of experiments · SDL
self-driving laboratory · FIM Fisher information matrix · WLS weighted least
squares · CPR-NMR compact/benchtop process NMR.

## 9. References

The kinetic and thermodynamic anchors are classical physical-organic
chemistry; see the inline provenance notes in
[`pfr_twin/parameters.py`](PFR_H2SO4_digital_twin/pfr_twin/parameters.py) for
the specific numbers used.

- R. P. Bell, *Acid–Base Catalysis* — specific acid catalysis, A-AC2 mechanism.
- A. J. Kirby, in *Comprehensive Chemical Kinetics* Vol. 10 — ester hydrolysis
  rate data and mechanism.
- M. Berthelot & L. Péan de Saint-Gilles (1862) — the classic acetate
  esterification equilibrium, `K_est ≈ 4`.
- Conductometric saponification kinetics of ethyl acetate + NaOH:
  `k(25 °C) ≈ 0.11 L mol⁻¹ s⁻¹`, `Eₐ ≈ 11.6 kcal/mol ≈ 48 kJ/mol` — e.g.
  [*J. Chem. Educ.* study of the rate constant](https://pubs.acs.org/doi/10.1021/acs.jchemed.5c00554)
  and the widely replicated
  [Arrhenius-parameter estimations](https://isca.me/rjcs/Archives/v5/i11/8.ISCA-RJCS-2015-150.pdf).
- G. Taylor / R. Aris — dispersion in laminar tube flow (the `Bo` diagnostic).
- O. Levenspiel, *Chemical Reaction Engineering* — PFR design equations,
  series-reaction selectivity, residence-time distributions.
- G. Franceschini & S. Macchietto, *Chem. Eng. Sci.* **63** (2008) 4846 —
  model-based design of experiments, a review of the criteria used here.

---

*A digital twin is only as honest as its self-checks. Every run in this
framework prints its own verification residuals — read them.*
