"""
CENTRAL BOOLEAN FEATURE CONTROL - the one place that says what is switched on.

THE PROBLEM THIS SOLVES.  The optional physics of this framework used to be
spread across a dozen files: whether the chemistry is reversible lived in a
Layer1Bridge argument, whether the transfer line reacts lived in a
TransferConfig field, whether the NMR noise is coloured lived in a
SpectralNuisance magnitude, whether the reactor is packed lived in a
geometry dict, whether the design space is continuous lived in yet another
dict.  Answering "what physics is this run actually simulating?" meant
reading all of them, and answering "what changes if I turn X off?" meant
reading the code that consumes them.  A configuration nobody can summarise
is a configuration nobody can review.

THE CONTRACT.

  1. Every optional feature has ONE boolean here.  This module is the
     authority; the detail blocks (GEOMETRY, TRANSFER_TRUE, ACQ,
     NMR_NUISANCE_TRUE, QC_GATE, ...) carry the MAGNITUDES of a feature that
     is on, never the question of whether it is on.
  2. False means BYPASSED, not "small".  Every handler below routes to a
     code path that is genuinely skipped - a `bool` the simulator branches
     on, an object that is not constructed, a parameter that is held fixed.
     Setting a magnitude to 1e-9 while the code still runs is exactly the
     failure this module exists to prevent, and `validate` rejects the
     inverse case too: a feature declared ON whose magnitude is zero.
  3. Switches apply to TRUTH AND INFERENCE ALIKE.  A feature that is off is
     absent from the world and from the model of the world.  Deliberate
     divergence between the two is a separate, explicitly named section
     (MODEL_MISMATCH) which is OFF by default, so an inverse crime or an
     accidental mismatch cannot be created by flipping a physics switch.
  4. The RESOLVED state is written with every run.  There are no hidden
     defaults: `resolved()` returns every switch, its value, and the
     concrete configuration it produced.

HOW TO ADD A FEATURE.  Add a `Feature(...)` record to FEATURES_SPEC with its
three explanations (what it represents / what True does / what False
recovers), and a handler in `_HANDLERS` that performs the bypass.  A feature
without a handler raises at import: a switch that does not switch anything
is worse than no switch.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclasses_fields, replace
from typing import Any, Callable, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# The catalogue
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Feature:
    """One switch, with the three explanations a reader needs."""
    name: str
    section: str
    #: what physical or numerical effect it represents
    represents: str
    #: what happens when it is True
    when_true: str
    #: what idealized behaviour is recovered when it is False
    when_false: str
    default: bool
    #: features that must be True for this one to mean anything
    requires: Tuple[str, ...] = ()


SECTIONS = ("chemistry", "reactor", "transfer", "nmr", "quantification",
            "faults", "design", "inference", "resources")

FEATURES_SPEC: Tuple[Feature, ...] = (
    # ---- chemistry -------------------------------------------------------- #
    Feature(
        "reversible_chemistry", "chemistry",
        "Ester hydrolysis is an equilibrium reaction: EGDA <-> EGMA <-> EG "
        "with equilibrium constants K1, K2 and thermodynamically consistent "
        "reverse rates.",
        "Both steps carry reverse rates; K1_ref and K2_ref are estimated "
        "parameters; net rates vanish exactly at the coupled-equilibrium "
        "composition (microscopic reversibility).",
        "Irreversible A -> B -> C kinetics.  The K parameters do not exist "
        "in the truth or in any candidate model, conversion is monotone to "
        "completion, and the parameter vector drops to four.",
        True),
    Feature(
        "temperature_dependent_kinetics", "chemistry",
        "Arrhenius temperature dependence of the two rate constants, "
        "k_i(T) = k_i_ref exp[-(Ea_i/R)(1/T - 1/T_ref)].",
        "Ea1 and Ea2 act on the rates and are estimated; temperature is an "
        "informative design dimension.",
        "Ea = 0 is applied in the forward model and Ea1/Ea2 are held FIXED "
        "in every parameter space: k(T) = k_ref, isothermal kinetics, and "
        "the temperature axis carries no kinetic information.",
        True),
    Feature(
        "temperature_dependent_equilibrium", "chemistry",
        "van 't Hoff temperature dependence of the two equilibrium "
        "constants, K_i(T) = K_i_ref exp[-(dH_i/R)(1/T - 1/T_ref)].",
        "The literature dH values shift the equilibrium with temperature "
        "(they are fixed, not estimated - see layer1_bridge).",
        "dH = 0: K(T) = K_ref, a temperature-independent equilibrium.",
        True, requires=("reversible_chemistry",)),
    Feature(
        "nonideal_acid_activity", "chemistry",
        "Pitzer activity coefficients for the catalytic proton in a "
        "concentrated aqueous sulfate medium.",
        "The catalytic activity a_H+ = gamma * [H+] uses the Pitzer model, "
        "so rate constants respond to ionic strength as well as to acid "
        "concentration.",
        "Dilute-solution ideality, gamma = 1: activity equals concentration "
        "and the acid axis acts purely through [H+].",
        True),
    Feature(
        "acid_speciation_equilibrium", "chemistry",
        "Second dissociation of sulfuric acid, HSO4- <-> H+ + SO4(2-), "
        "solved as an equilibrium rather than assumed complete.",
        "[H+] is obtained from the Ka2 equilibrium at the local "
        "temperature, so it is a nonlinear function of total sulfate.",
        "Stoichiometric protons: [H+] = n_eff * [H2SO4], independent of "
        "temperature and of the sulfate equilibrium.",
        True),
    Feature(
        "temperature_dependent_ka2", "chemistry",
        "Temperature dependence of Ka2, which moves by orders of magnitude "
        "over the 40-160 C window.",
        "Ka2(T) is evaluated at the LOCAL temperature - reactor temperature "
        "in the reactor, line temperature in the cooled transfer line.",
        "Ka2 is held at its reference-temperature value everywhere.",
        True, requires=("acid_speciation_equilibrium",)),

    # ---- reactor ---------------------------------------------------------- #
    Feature(
        "packed_bed_reactor", "reactor",
        "Inert random packing (spherical beads, void fraction eps) in the "
        "tubular reactor.",
        "Liquid holdup is eps * V, so tau shrinks by eps and the "
        "interstitial velocity rises by 1/eps; the bed's mechanical "
        "dispersion replaces molecular diffusion in the plug-flow criterion, "
        "which is what makes the reactor admissible at the design flows.",
        "An OPEN tube: eps = 1, tau = V/Q, and radial mixing is molecular "
        "only.  At the declared flows this is a radially segregated laminar "
        "tube, so `reactor_validity_enforcement` will refuse it (see the "
        "guidance the validity check prints).",
        True),
    Feature(
        "reactor_validity_enforcement", "reactor",
        "Whether the plug-flow criterion is a CONSTRAINT or a comment.",
        "The reactor in use is checked at EVERY permitted flow and an "
        "inadmissible reactor stops the run (VALIDITY policy 'error'), with "
        "guidance on which bound to change.",
        "The check still runs and is still archived, but never blocks "
        "(policy 'ignore') - a deliberate non-ideal study, recorded as one.",
        True),
    Feature(
        "axial_dispersion_criterion", "reactor",
        "The Bodenstein criterion Bo = uL/D_ax >= 100 (the classical "
        "'< 1 % deviation from plug flow' boundary), in addition to the "
        "radial-mixing criterion.",
        "Both criteria must hold.  For an open tube they are one criterion "
        "in disguise (Bo = 48/(t_rad/tau)); for a packed bed the axial one "
        "becomes the bed aspect ratio requirement.",
        "Only the radial-mixing ratio decides; Bo is computed and archived "
        "but does not enter the verdict - the historical behaviour.  (With "
        "reactor_validity_enforcement off this still changes the RECORDED "
        "verdict, it just stops being a blocking constraint.)",
        True),
    Feature(
        "geometry_optimization", "reactor",
        "Treating the reactor geometry itself as a design variable "
        "('I am building a reactor for this chemistry') instead of a given "
        "('I have this reactor').",
        "The reactor is sized once from the PRIOR before round 1, under "
        "information minus resource cost with plug-flow feasibility "
        "enforced over the whole flow envelope; blind scoring still happens "
        "in the declared reference reactor.",
        "The declared GEOMETRY is used unchanged for every campaign - the "
        "conservative default, and the question the published benchmark "
        "answered before geometry became a design variable.",
        False),

    # ---- transfer line ---------------------------------------------------- #
    Feature(
        "transfer_line", "transfer",
        "The physical path from the sampling capillary orifice to the NMR "
        "flow cell: a finite volume with a finite residence time.",
        "Sampling is not instantaneous; the composition reaching the cell "
        "differs from the composition at z.  Enables the four effects below.",
        "Identity transform: the NMR sees exactly the reactor composition "
        "at the sampled position.",
        True),
    Feature(
        "transfer_line_reaction", "transfer",
        "Continued reaction in the sample between withdrawal and detection.",
        "Each residence-time quadrature node is propagated with the true "
        "kinetics for its own transit time, so the measurement is of an "
        "OLDER state than the sampling position.",
        "The sample is frozen at withdrawal: transport delays the sample "
        "but does not change it.",
        True, requires=("transfer_line",)),
    Feature(
        "transfer_line_temperature_correction", "transfer",
        "The line is COOLED before the flow cell, so post-sampling reaction "
        "runs at the line temperature and not at the reactor temperature.",
        "T_line_C is commanded (25 C): a sample leaving a 160 C reactor "
        "barely reacts on the way, and the catalytic [H+] is re-solved at "
        "the LINE temperature.  Both truth and inference use the commanded "
        "value, which is public knowledge.",
        "T_line = T_reactor, the legacy assumption: the sample keeps "
        "reacting at full reactor temperature all the way to the cell, "
        "which over-states the in-line conversion badly at high T.",
        True, requires=("transfer_line", "transfer_line_reaction")),
    Feature(
        "transfer_line_rtd_dispersion", "transfer",
        "Residence-time distribution of the line (tanks-in-series / gamma) "
        "rather than a single delay.",
        "The cell sees a WEIGHTED MIXTURE of ages, so the measurement is "
        "smeared as well as delayed.",
        "Plug (delta) RTD: one sharp delay, the legacy transfer_time_s "
        "limit.",
        True, requires=("transfer_line",)),
    Feature(
        "transfer_line_carryover", "transfer",
        "Incomplete flushing after the capillary moves: the line still "
        "holds part of the previous sample.",
        "An exponential flushing model mixes old and new sample, so a "
        "measurement depends on the PREVIOUS sampling position.",
        "Every acquisition sees only its own sample.",
        True, requires=("transfer_line",)),
    Feature(
        "transfer_correction_in_inference", "transfer",
        "Whether the CONTROLLER corrects its predictions for the transfer "
        "delay it commanded.",
        "The observation operator adds the nominal tau(z) = V(z)/Q_sample "
        "at the commanded line temperature, from COMMANDED quantities only "
        "- never the truth's RTD or carryover, which stay unmodelled.",
        "The controller compares the kinetic model against the reactor "
        "state as if the line did not exist - the F-uncorr ablation.",
        True, requires=("transfer_line",)),

    # ---- NMR spectrum ----------------------------------------------------- #
    Feature(
        "nmr_fid_engine", "nmr",
        "Time-domain simulation: complex FID -> T2* decay -> receiver noise "
        "-> phase -> FFT, the honest model of the instrument.",
        "The acquisition time, dwell, point count and zero filling are all "
        "physical and affect the spectrum; slower.",
        "The ANALYTIC engine builds the frequency-domain lineshape "
        "directly.  It has no acquisition time at all (the acquisition "
        "settings then affect only the campaign clock), and it is what "
        "makes 40-seed Monte Carlo affordable.",
        False),
    Feature(
        "nmr_white_noise", "nmr",
        "Additive receiver noise on the spectrum.",
        "Each acquisition carries independent Gaussian noise of "
        "noise_sigma/sqrt(n_scans) per point.",
        "A noiseless spectrum: repeated acquisitions of one composition are "
        "bit-identical, and quantification error comes only from lineshape "
        "and overlap.",
        True),
    Feature(
        "nmr_correlated_noise", "nmr",
        "Colour (AR(1) correlation) in that noise, which real receiver and "
        "processing chains have and a white-noise fitter does not model.",
        "Neighbouring spectral points are correlated, so the fitted "
        "covariance - derived under a white-noise assumption - understates "
        "the true parameter uncertainty.",
        "White noise: the fitter's noise assumption is exactly right.",
        True, requires=("nmr_white_noise",)),
    Feature(
        "nmr_line_broadening", "nmr",
        "Acquisition-to-acquisition variation in linewidth (shim drift, "
        "temperature, flow).",
        "Each acquisition draws a lognormal linewidth factor; the fitter "
        "must estimate it.",
        "Every acquisition has exactly the nominal linewidth, so the fitter has one fewer nuisance to estimate.",
        True),
    Feature(
        "nmr_baseline_distortion", "nmr",
        "Baseline offset, curvature and a cubic term that the fitter's "
        "quadratic baseline model cannot represent.",
        "A polynomial background is added; the cubic part is deliberately "
        "outside the fitter's model, so baseline error is not fully "
        "removable.",
        "A flat, zero baseline: whatever the fitter cannot remove is not there in the first place.",
        True),
    Feature(
        "nmr_chemical_shift_drift", "nmr",
        "Reference drift, per-group shift jitter, and a per-campaign STATIC "
        "shift miscalibration of the instrument.",
        "Peak positions move between acquisitions and are systematically "
        "off from the database, which matters in the 7 Hz EGDA/EGMA acetyl "
        "overlap where a sub-Hz shift reapportions area between species.",
        "Every resonance sits exactly at its database shift, so the overlap is apportioned by area alone.",
        True),
    Feature(
        "nmr_phase_error", "nmr",
        "Zero-order phase error, which mixes dispersion lineshape into the "
        "absorption spectrum.",
        "A random phase per acquisition; the fitter estimates it within a "
        "bounded window.",
        "Perfectly phased spectra: pure absorption lineshape, no dispersion component to fit.",
        True),
    Feature(
        "nmr_gain_drift", "nmr",
        "Receiver-gain drift between acquisitions.",
        "A multiplicative factor scales EVERY species coherently, which is "
        "why it enters the covariance as a rank-one correlated term rather "
        "than a diagonal one.",
        "Constant, exactly calibrated receiver gain - no coherent scaling term in the covariance.",
        True),
    Feature(
        "nmr_lineshape_mismatch", "nmr",
        "TRUTH-MODEL MISMATCH (anti-inverse-crime): the true lineshape is "
        "pseudo-Voigt and the true 3J differs from the fitter's database, "
        "so the fitter never fits its own exact physics.",
        "The truth deviates from the fitting model in ways the fitter does "
        "not know, which is what makes synthetic validation meaningful.",
        "Pure Lorentzian truth with the database J: the fitter's model is "
        "EXACTLY correct - an inverse crime, useful only as a control.",
        True),
    Feature(
        "nmr_response_calibration", "nmr",
        "Pre-campaign per-species response calibration against prepared "
        "standards - the real Fourier-80 workflow.",
        "Systematic response/lineshape bias is absorbed into measured "
        "public factors, and the residual error model (bias, correlation, "
        "variance) is regressed on those standards.",
        "Nominal response factors are assumed: any true response error "
        "passes straight into the quantified concentrations uncorrected.",
        True),

    # ---- quantification --------------------------------------------------- #
    Feature(
        "overlap_correlated_errors", "quantification",
        "Correlated quantification error between species whose resonances "
        "overlap (EGDA/EGMA acetyl).",
        "The assumed direct-observation covariance carries rho_overlap "
        "between the overlapping pair, matching what the spectral fit "
        "produces naturally through its Jacobian.",
        "Independent per-species errors: a strictly diagonal covariance, as if the resonances did not overlap.",
        True),
    Feature(
        "quantification_uncertainty", "quantification",
        "The part of the measurement error that a single spectrum's "
        "Jacobian cannot see: reproducibility floors, coherent gain, "
        "shift-jitter propagation and the empirically calibrated residual "
        "covariance.",
        "Sigma_y = within-spectrum fit covariance + floor + rank-one gain "
        "term + shift-jitter propagation + the empirical model measured on "
        "standards.  This is the covariance the design layer also uses.",
        "Sigma_y is the pure within-spectrum statistical covariance.  "
        "Optimistic by construction - useful for isolating how much of the "
        "reported uncertainty comes from the error model rather than the "
        "spectra.",
        True),

    # ---- faults and QC ---------------------------------------------------- #
    Feature(
        "instrument_faults", "faults",
        "Gross, QC-DETECTABLE hardware failures: lost lock, a gas bubble in "
        "the flow cell, a failed shim.",
        "A fraction of acquisitions carry a structured artifact no "
        "lineshape model can fit, so the deconvolution raises FAIL and the "
        "QC gate rejects them before assimilation.",
        "The only QC failures are genuine spectral-fit failures on hard "
        "compositions - which still occur, and are still caught.",
        False),
    Feature(
        "measurement_outliers", "faults",
        "UNDETECTABLE quantification outliers: a mis-apportioned overlapped "
        "integral gives a concentration wrong by many claimed sigmas while "
        "the spectral residual stays normal.",
        "Heavy-tailed quantification error that the QC gate cannot see, "
        "testing the robustness of the INFERENCE rather than of the gate.",
        "Quantification error stays within its calibrated distribution - no heavy tail beyond the reported sigma.",
        False),
    Feature(
        "qc_rejection", "faults",
        "The quality-control gate between the spectrometer and the kinetic "
        "posterior.",
        "A spectrum with FAIL flags is NEVER assimilated; persistent "
        "failure pauses the campaign instead of designing new chemistry on "
        "corrupted data.",
        "Every quantified spectrum is assimilated, flags and all - the posterior sees whatever the instrument produced.",
        True),
    Feature(
        "qc_retry_on_failure", "faults",
        "Re-acquiring a position whose spectrum failed QC.",
        "Up to max_retries reacquisitions per failing position, metered as "
        "instrument time; a transient fault costs time, not data.",
        "A failing position is dropped immediately - no second attempt, and no reacquisition time is spent.",
        True, requires=("qc_rejection",)),

    # ---- design ----------------------------------------------------------- #
    Feature(
        "continuous_design_space", "design",
        "Whether operating conditions are chosen from a factorial GRID or "
        "anywhere inside the declared bounds.",
        "The optimizer may propose any point inside continuous_bounds, "
        "SNAPPED to the resolution the hardware can command and accepted "
        "only when it strictly beats the best grid point - so it can never "
        "be worse than the grid.",
        "The classical discrete factorial grid only - conditions are chosen from declared levels and nowhere else.",
        False),
    Feature(
        "spatial_optimization", "design",
        "Choosing WHERE along the reactor to sample, rather than sampling "
        "equally spaced ports.",
        "Positions are selected by incremental D-optimality on the current "
        "information landscape.",
        "Fixed, equally spaced axial positions - the classical profile, identical in every round.",
        True),
    Feature(
        "adaptive_single_measurement", "design",
        "Truly sequential axial sampling: choose z, acquire ONE spectrum, "
        "update the full posterior, then choose the next z.",
        "The realized measurement changes the next position.  Note the "
        "consequence for QC: a round contains a single acquisition, so a "
        "per-round rejection FRACTION is meaningless and the gate's "
        "persistence rules (consecutive / rolling window) are what detect a "
        "broken instrument.",
        "Positions for a round are chosen as a BATCH before any of them is "
        "measured.",
        True, requires=("spatial_optimization",)),
    Feature(
        "bayesian_model_discrimination", "design",
        "Designing experiments to tell candidate MODELS apart, not only to "
        "sharpen parameters.",
        "The acquisition adds a model-discrimination EIG term, up-weighted "
        "while the ensemble is undecided.",
        "Pure parameter-information design; model probabilities are still "
        "tracked but never steer an experiment.",
        True),

    # ---- inference -------------------------------------------------------- #
    Feature(
        "model_inadequacy_governor", "inference",
        "The lack-of-fit governor that decides whether the residuals mean "
        "'parameters still uncertain' or 'model structurally wrong'.",
        "Every round is tested; a MODEL_INADEQUATE verdict stops the "
        "controller exploiting a model it no longer trusts.",
        "The controller always exploits the current best model - the "
        "F-noGovernor ablation.",
        True),
    Feature(
        "governor_dispersion_robust", "inference",
        "Whether the governor's lack-of-fit decision is invariant to a "
        "uniform mis-scaling of the measurement covariance.",
        "The realized dispersion phi = r'r/dof is estimated and used to "
        "standardize the STRUCTURAL components, and the absolute chi2 "
        "magnitude leaves the decision set under a declared measurement "
        "systematic - because its power against a mis-scaled Sigma_y grows "
        "without bound in n.  The gross-misfit override still applies.",
        "The historical behaviour: chi2 magnitude decides, and the "
        "structural nulls assume the claimed Sigma_y is exactly right.",
        True),
    Feature(
        "identifiability_screen", "inference",
        "A pre-campaign screen that holds parameters the declared design "
        "space cannot identify at their literature values.",
        "Unidentifiable parameters are fixed rather than fitted, so their "
        "unbounded confidence intervals do not contaminate the D-optimal "
        "criterion.",
        "Every parameter is estimated regardless of whether the design "
        "space can excite it, unbounded intervals included.",
        True),

    # ---- resources -------------------------------------------------------- #
    Feature(
        "resource_accounting", "resources",
        "Metering of campaign time, material, waste, energy and capillary "
        "travel from an auditable event log.",
        "Every physical action is logged and totalled; convergence can be "
        "reported per unit resource, not only per round.",
        "Resources are not metered (all totals zero); only round counts "
        "are comparable.",
        True),
    Feature(
        "resource_aware_design", "resources",
        "Letting the design objective trade information against resource "
        "cost (the lambda weights).",
        "The acquisition maximizes information MINUS lambda-weighted cost, "
        "so a marginally more informative but far more expensive experiment "
        "loses.",
        "Pure information maximization: lambda = 0, cost is metered and "
        "reported but never influences a decision.",
        True, requires=("resource_accounting",)),
    Feature(
        "acquisition_time_accounting", "resources",
        "Deriving the per-spectrum clock from the acquisition settings: "
        "t = overhead + n_scans x (recycle + acquisition).",
        "n_scans, the recycle delay and the acquisition time move the "
        "campaign clock as they physically must - the spectrometer settings "
        "and the campaign clock are ONE model.",
        "A LEGACY fixed per-spectrum duration, independent of the "
        "acquisition settings.  Provided only to reproduce archives made "
        "before the decomposition existed.",
        True, requires=("resource_accounting",)),
)

FEATURES_BY_NAME: Dict[str, Feature] = {f.name: f for f in FEATURES_SPEC}
DEFAULTS: Dict[str, bool] = {f.name: f.default for f in FEATURES_SPEC}


def defaults() -> Dict[str, bool]:
    return dict(DEFAULTS)


# --------------------------------------------------------------------------- #
# MODEL MISMATCH - the ONLY place truth and inference are allowed to differ
# --------------------------------------------------------------------------- #
# Everything above applies to truth and inference alike.  This block exists
# for validation experiments that deliberately give the learner a DIFFERENT
# world model from the one it is learning about ("what does the framework do
# when its structural assumption is wrong?").  It is OFF by default and every
# entry defaults to None = "same as truth", so nothing here can bite unless
# it was asked for.  When it is on, the run record says so prominently.
MISMATCH_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    #: inference-side chemistry that DIFFERS from the truth's.  None = same.
    "inference_reversible": None,           # True | False | None
    "inference_activity_model": None,       # "pitzer" | "dilute" | None
    "inference_arrhenius": None,            # True | False | None
    "inference_van_t_hoff": None,           # True | False | None
    #: multiply the inference's ASSUMED measurement sigma by this factor
    #: (>1 = the learner believes its data are worse than they are)
    "inference_noise_scale": 1.0,
    #: SYSTEMATIC DISCREPANCY in the truth that no candidate can represent:
    #: multiplicative factors on the hidden true parameters, e.g.
    #: {"k2_ref": 1.5}.  Empty = none.
    "truth_parameter_bias": {},
}


def mismatch_defaults() -> Dict[str, Any]:
    out = dict(MISMATCH_DEFAULTS)
    out["truth_parameter_bias"] = dict(MISMATCH_DEFAULTS["truth_parameter_bias"])
    return out


# --------------------------------------------------------------------------- #
# Handlers: how each switch reaches the code
# --------------------------------------------------------------------------- #
# Each handler takes (namespace, on) and mutates the benchmark module's
# configuration blocks.  They only ever FORCE the "off" state; a feature that
# is ON leaves the detail block's configured magnitude alone.  That makes
# them idempotent, which matters because a worker process replays the whole
# configuration on start-up.


def _set_dc(ns: Dict, name: str, **kw) -> None:
    """Rebuild a frozen dataclass block with new field values."""
    ns[name] = replace(ns[name], **kw)


def _chem(ns: Dict, key: str, value) -> None:
    ns["TRUTH_CHEMISTRY"][key] = value
    ns["INFERENCE_CHEMISTRY"][key] = value


def _h_reversible(ns, on):
    _chem(ns, "reversible", bool(on))
    if not on:
        # The whole reversible FAMILY disappears, not just the reverse rate
        # term: a candidate that carries K parameters is not a hypothesis
        # about a world with no equilibrium.  The map rewrites every
        # scenario's declared family, so no scenario can smuggle one back.
        ns["FEATURE_FAMILY_MAP"].update({"rev-pitzer": None,
                                         "rev-dilute": None})
        ns["FEATURE_FAMILY_FALLBACK"] = "irreversible"


def _h_tdep_kinetics(ns, on):
    _chem(ns, "arrhenius", bool(on))
    if not on:
        # Ea cannot be estimated when it does not act: hold it fixed so the
        # parameter space matches the forward model instead of fitting a
        # direction with no gradient.
        ns["FEATURE_FIXED_PARAMS"] = tuple(
            sorted(set(ns["FEATURE_FIXED_PARAMS"]) | {"Ea1_J", "Ea2_J"}))


def _h_tdep_equilibrium(ns, on):
    _chem(ns, "van_t_hoff", bool(on))


def _h_activity(ns, on):
    _chem(ns, "activity_model", "pitzer" if on else "dilute")
    if not on:
        # With gamma = 1 the "Pitzer" candidate IS the dilute candidate, so
        # keeping both would present one hypothesis as two and split its
        # posterior probability in half.
        ns["FEATURE_FAMILY_MAP"]["rev-pitzer"] = "rev-dilute"


def _h_speciation(ns, on):
    _chem(ns, "h_plus_model", "equilibrium" if on else "stoichiometric")


def _h_ka2(ns, on):
    _chem(ns, "ka2_model", "tdep" if on else "constant")


def _h_packing(ns, on):
    ns["GEOMETRY"]["packing_enabled"] = bool(on)
    ns["GEOMETRY"]["bed_void_fraction"] = (
        float(ns["GEOMETRY_DESIGN"]["bed_void_fraction"]) if on else 1.0)
    ns["GEOMETRY_DESIGN"]["packing"] = "auto" if on else False


def _h_validity(ns, on):
    """The switch decides whether the criterion BINDS; the VALIDITY block
    decides how loudly ("error" refuses, "warn" reports and continues).

    Off forces "ignore".  On leaves the configured policy alone, except
    that it refuses to leave it at "ignore" - claiming enforcement while
    ignoring the verdict is the contradiction this section exists to
    prevent."""
    if not on:
        ns["VALIDITY"]["policy"] = "ignore"
        return
    if str(ns["VALIDITY"].get("policy", "error")).lower() == "ignore":
        raise ValueError(
            "FEATURES['reactor_validity_enforcement'] is True but "
            "VALIDITY['policy'] is 'ignore', so nothing is enforced.  Use "
            "'error' (refuse an inadmissible reactor) or 'warn' (report and "
            "continue), or set the feature to False to declare the "
            "non-ideal study explicitly.")


def _h_bodenstein(ns, on):
    ns["VALIDITY"]["criteria"]["enforce_bodenstein"] = bool(on)


def _h_geometry_design(ns, on):
    ns["GEOMETRY_DESIGN"]["enabled"] = bool(on)


def _h_transfer(ns, on):
    _set_dc(ns, "TRANSFER_TRUE", enabled=bool(on))


def _h_line_reaction(ns, on):
    _set_dc(ns, "TRANSFER_TRUE", react_in_line=bool(on))


def _h_line_temperature(ns, on):
    # None means "the sample stays at reactor temperature" - the legacy,
    # physically wrong assumption.  A number is the commanded line
    # temperature, which both truth and inference are entitled to.
    _set_dc(ns, "TRANSFER_TRUE",
            T_line_C=(float(ns["TRANSFER_LINE_T_C"]) if on else None))


def _h_line_rtd(ns, on):
    _set_dc(ns, "TRANSFER_TRUE", rtd=("gamma" if on else "delta"))


def _h_line_carryover(ns, on):
    _set_dc(ns, "TRANSFER_TRUE", carryover=bool(on))


def _h_transfer_correction(ns, on):
    ns["FEATURE_TRANSPORT_AWARE"] = bool(on)


def _h_fid(ns, on):
    _set_dc(ns, "ACQ", engine=("fid" if on else "analytic"))


def _nu(ns, **kw):
    _set_dc(ns, "NMR_NUISANCE_TRUE", **kw)


def _h_white_noise(ns, on):
    _nu(ns, white_noise=bool(on))


def _h_correlated_noise(ns, on):
    _nu(ns, correlated_noise=bool(on))


def _h_broadening(ns, on):
    _nu(ns, line_broadening=bool(on))


def _h_baseline(ns, on):
    _nu(ns, baseline_distortion=bool(on))


def _h_shift(ns, on):
    _nu(ns, chemical_shift_drift=bool(on))


def _h_phase(ns, on):
    _nu(ns, phase_error=bool(on))


def _h_gain(ns, on):
    _nu(ns, gain_drift=bool(on))


def _h_lineshape_mismatch(ns, on):
    _nu(ns, lineshape_mismatch=bool(on))


def _h_response_calibration(ns, on):
    _nu(ns, response_error=bool(on))
    ns["QUANTIFICATION"]["calibrate_responses"] = bool(on)


def _h_overlap(ns, on):
    if not on:
        _set_dc(ns, "NOISE_DIRECT", rho_overlap=0.0)


def _h_quant_uncertainty(ns, on):
    q = ns["QUANTIFICATION"]
    q["empirical_error_model"] = bool(on)
    if not on:
        # not "a small floor": NO floor, NO coherent-gain term, NO
        # shift-jitter propagation, NO empirical covariance.  Sigma_y is
        # then the pure within-spectrum Jacobian covariance.
        q["sigma_floor_abs_M"] = 0.0
        q["sigma_floor_rel"] = 0.0
        q["gain_drift_rel"] = 0.0
        q["shift_jitter_ppm"] = 0.0


def _refresh_faults(ns) -> None:
    """Rebuild FAULTS from the two switches and the declared magnitudes.

    A probability of zero is the bypass: `FaultModel.spectrum_faults_active`
    / `outliers_active` are then False and the injection code is not
    reached at all."""
    d = ns["FAULT_MODEL"]
    sp = float(d["spectrum_fault_prob"]) if ns.get("_FAULT_SPECTRA_ON") else 0.0
    ou = float(d["outlier_prob"]) if ns.get("_FAULT_OUTLIERS_ON") else 0.0
    ns["FAULTS"] = ns["FAULT_MODEL_CLASS"](
        enabled=bool(sp > 0.0 or ou > 0.0),
        spectrum_fault_prob=sp,
        spectrum_fault_amplitude_sigma=float(
            d["spectrum_fault_amplitude_sigma"]),
        outlier_prob=ou,
        outlier_scale_sigma=float(d["outlier_scale_sigma"]))


def _h_instrument_faults(ns, on):
    ns["_FAULT_SPECTRA_ON"] = bool(on)
    _refresh_faults(ns)


def _h_outliers(ns, on):
    ns["_FAULT_OUTLIERS_ON"] = bool(on)
    _refresh_faults(ns)


def _h_qc(ns, on):
    ns["QC_GATE"]["enabled_for_nmr"] = bool(on)


def _h_qc_retry(ns, on):
    if not on:
        ns["QC_GATE"]["max_retries"] = 0


def _h_continuous(ns, on):
    ns["DESIGN_SPACE"]["continuous"] = bool(on)


def _h_spatial(ns, on):
    ns["FEATURE_SPATIAL_OPTIMIZATION"] = bool(on)


def _h_adaptive(ns, on):
    ns["FEATURE_ADAPTIVE_SEQUENTIAL"] = bool(on)


def _h_model_discrimination(ns, on):
    if not on:
        ns["ADVANCED_DESIGN"]["beta_model"] = 0.0
        ns["ADVANCED_DESIGN"]["beta_model_discrimination"] = 0.0


def _h_governor(ns, on):
    ns["FEATURE_USE_GOVERNOR"] = bool(on)


def _h_governor_dispersion(ns, on):
    ns["GOVERNOR"]["dispersion_robust"] = bool(on)


def _h_screen(ns, on):
    ns["FEATURE_IDENTIFIABILITY_SCREEN"] = bool(on)


def _h_resource_accounting(ns, on):
    ns["FEATURE_RESOURCE_ACCOUNTING"] = bool(on)


def _h_resource_aware(ns, on):
    if on:
        return
    # lambda = 0 is the DEFINED ideal here, not a small number: the resource
    # terms drop out of the objective identically, which is exactly what
    # "pure information maximization" means (see resources.py).
    _set_dc(ns, "RESOURCE_COSTS",
            **{k: 0.0 for k in ns["RESOURCE_LAMBDA_FIELDS"]})
    for k in list(ns["GEOMETRY_DESIGN"]["objective_lambdas"]):
        ns["GEOMETRY_DESIGN"]["objective_lambdas"][k] = 0.0
    for name, spec in ns["SCENARIOS"].items():
        for key, var in list(spec.f_variants.items()):
            if "costs" in var:
                var["costs"] = replace(
                    var["costs"],
                    **{k: 0.0 for k in ns["RESOURCE_LAMBDA_FIELDS"]})


def _h_acq_time(ns, on):
    _set_dc(ns, "RESOURCE_COSTS",
            legacy_fixed_nmr_time_s=(None if on
                                     else float(ns["LEGACY_NMR_TIME_S"])))


_HANDLERS: Dict[str, Callable[[Dict, bool], None]] = {
    "reversible_chemistry": _h_reversible,
    "temperature_dependent_kinetics": _h_tdep_kinetics,
    "temperature_dependent_equilibrium": _h_tdep_equilibrium,
    "nonideal_acid_activity": _h_activity,
    "acid_speciation_equilibrium": _h_speciation,
    "temperature_dependent_ka2": _h_ka2,
    "packed_bed_reactor": _h_packing,
    "reactor_validity_enforcement": _h_validity,
    "axial_dispersion_criterion": _h_bodenstein,
    "geometry_optimization": _h_geometry_design,
    "transfer_line": _h_transfer,
    "transfer_line_reaction": _h_line_reaction,
    "transfer_line_temperature_correction": _h_line_temperature,
    "transfer_line_rtd_dispersion": _h_line_rtd,
    "transfer_line_carryover": _h_line_carryover,
    "transfer_correction_in_inference": _h_transfer_correction,
    "nmr_fid_engine": _h_fid,
    "nmr_white_noise": _h_white_noise,
    "nmr_correlated_noise": _h_correlated_noise,
    "nmr_line_broadening": _h_broadening,
    "nmr_baseline_distortion": _h_baseline,
    "nmr_chemical_shift_drift": _h_shift,
    "nmr_phase_error": _h_phase,
    "nmr_gain_drift": _h_gain,
    "nmr_lineshape_mismatch": _h_lineshape_mismatch,
    "nmr_response_calibration": _h_response_calibration,
    "overlap_correlated_errors": _h_overlap,
    "quantification_uncertainty": _h_quant_uncertainty,
    "instrument_faults": _h_instrument_faults,
    "measurement_outliers": _h_outliers,
    "qc_rejection": _h_qc,
    "qc_retry_on_failure": _h_qc_retry,
    "continuous_design_space": _h_continuous,
    "spatial_optimization": _h_spatial,
    "adaptive_single_measurement": _h_adaptive,
    "bayesian_model_discrimination": _h_model_discrimination,
    "model_inadequacy_governor": _h_governor,
    "governor_dispersion_robust": _h_governor_dispersion,
    "identifiability_screen": _h_screen,
    "resource_accounting": _h_resource_accounting,
    "resource_aware_design": _h_resource_aware,
    "acquisition_time_accounting": _h_acq_time,
}

_missing = sorted(set(FEATURES_BY_NAME) - set(_HANDLERS))
if _missing:                                   # pragma: no cover - import guard
    raise RuntimeError(
        "features.py: no handler for " + ", ".join(_missing)
        + ".  A switch that does not switch anything is worse than no "
          "switch; add the bypass or remove the Feature record.")


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
#: features whose magnitude, if zero, contradicts a True switch.  The pair is
#: (namespace expression, human name).  Checked so that "the feature is on"
#: and "the feature does something" cannot disagree - the flip side of
#: forbidding "off means a tiny number".
_NONZERO_WHEN_ON: Dict[str, Tuple[str, str]] = {
    "nmr_white_noise": ("NMR_NUISANCE_TRUE.noise_sigma", "noise_sigma"),
    "nmr_correlated_noise": ("NMR_NUISANCE_TRUE.noise_ar1", "noise_ar1"),
    "nmr_line_broadening": ("NMR_NUISANCE_TRUE.linewidth_rel_sigma",
                            "linewidth_rel_sigma"),
    "nmr_phase_error": ("NMR_NUISANCE_TRUE.phase_error_deg",
                        "phase_error_deg"),
    "nmr_gain_drift": ("NMR_NUISANCE_TRUE.gain_drift_rel_sigma",
                       "gain_drift_rel_sigma"),
    "instrument_faults": ("FAULTS.spectrum_fault_prob",
                          "spectrum_fault_prob"),
    "measurement_outliers": ("FAULTS.outlier_prob", "outlier_prob"),
    "qc_retry_on_failure": ("QC_GATE.max_retries", "max_retries"),
}


def _lookup(ns: Dict, path: str):
    obj: Any = ns[path.split(".")[0]]
    for part in path.split(".")[1:]:
        obj = obj[part] if isinstance(obj, dict) else getattr(obj, part)
    return obj


def cascade(features: Dict[str, bool]) -> Dict[str, bool]:
    """Switch off anything whose prerequisite is off.

    Turning a master switch off must take its dependants with it: "no
    transfer line, but the transfer line reacts" is not a configuration, it
    is a contradiction.  Cascading (rather than refusing) is what makes the
    master switches usable - one edit turns off a whole mechanism - while
    `validate` still refuses a contradiction the user wrote EXPLICITLY.

    Iterated to a fixed point so a chain (A -> B -> C) collapses fully."""
    out = {**DEFAULTS, **features}
    for _ in range(len(FEATURES_SPEC)):
        changed = False
        for f in FEATURES_SPEC:
            if out[f.name] and any(not out[d] for d in f.requires):
                out[f.name] = False
                changed = True
        if not changed:
            break
    return out


def validate(features: Dict[str, bool],
             mismatch: Optional[Dict[str, Any]] = None,
             explicit: Optional[set] = None) -> None:
    """Reject unknown switches, contradictions and incoherent pairs.

    Runs BEFORE anything is applied, so a bad configuration fails at
    start-up rather than nine hours into a campaign.

    `explicit` is the set of switches the caller actually WROTE.  A
    dependant that is True only because it is the default is cascaded off
    silently; a dependant the caller explicitly set True while its
    prerequisite is off is a contradiction and raises."""
    unknown = sorted(set(features) - set(FEATURES_BY_NAME))
    if unknown:
        raise KeyError(
            "Unknown FEATURES switch(es): " + ", ".join(unknown)
            + ".  Known switches:\n  "
            + "\n  ".join(f"{f.name:38s} [{f.section}]"
                          for f in FEATURES_SPEC))
    for name, value in features.items():
        if not isinstance(value, bool):
            raise TypeError(
                f"FEATURES['{name}'] must be True or False, got "
                f"{value!r}.  Magnitudes belong in the detail blocks; this "
                f"section is only about what is switched on.")
    resolved_f = {**DEFAULTS, **features}
    written = set(explicit if explicit is not None else features)
    for f in FEATURES_SPEC:
        if not resolved_f[f.name] or f.name not in written:
            continue
        for dep in f.requires:
            if not resolved_f[dep]:
                raise ValueError(
                    f"FEATURES['{f.name}'] is explicitly True but its "
                    f"prerequisite '{dep}' is False.  {f.name} is "
                    f"meaningless without {dep}: {f.represents}  "
                    f"Set '{dep}' to True, or drop '{f.name}' and let it "
                    f"cascade off with its prerequisite.")
    mm = {**mismatch_defaults(), **(mismatch or {})}
    unknown_mm = sorted(set(mm) - set(MISMATCH_DEFAULTS))
    if unknown_mm:
        raise KeyError("Unknown MODEL_MISMATCH field(s): "
                       + ", ".join(unknown_mm))
    if not mm["enabled"]:
        declared = [k for k, v in mm.items()
                    if k not in ("enabled", "inference_noise_scale")
                    and v not in (None, {}, ())]
        if declared or float(mm["inference_noise_scale"]) != 1.0:
            raise ValueError(
                "MODEL_MISMATCH declares "
                + ", ".join(declared + (["inference_noise_scale"]
                                        if float(mm["inference_noise_scale"])
                                        != 1.0 else []))
                + " but is not enabled.  Deliberate truth/inference "
                  "divergence must be switched on explicitly - a mismatch "
                  "that is configured but not declared is exactly the "
                  "silent inverse-crime risk this section exists to "
                  "prevent.  Set MODEL_MISMATCH['enabled'] = True.")
    if float(mm["inference_noise_scale"]) <= 0.0:
        raise ValueError("MODEL_MISMATCH['inference_noise_scale'] must be "
                         "positive.")


def _check_magnitudes(ns: Dict, features: Dict[str, bool]) -> None:
    """A feature declared ON whose magnitude is zero is a lie in the run
    record: it will be reported as active while doing nothing."""
    for name, (path, label) in _NONZERO_WHEN_ON.items():
        if not features.get(name, DEFAULTS[name]):
            continue
        try:
            value = float(_lookup(ns, path))
        except (KeyError, AttributeError, TypeError):      # pragma: no cover
            continue
        if value == 0.0:
            raise ValueError(
                f"FEATURES['{name}'] is True but {label} is 0, so the "
                f"feature is switched on and does nothing.  Either give it a "
                f"magnitude or set the switch to False - the run record must "
                f"not claim an effect that is not simulated.")


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
def apply(features: Dict[str, bool], mismatch: Dict[str, Any],
          ns: Dict, explicit: Optional[set] = None) -> Dict[str, Any]:
    """Route the switches into the configuration blocks of `ns`.

    Called at the END of benchmark.apply_config, so FEATURES has the last
    word over anything a detail block set - that is what "one source of
    truth" means here.  Idempotent: handlers only force the OFF state, so
    replaying the configuration in a worker process is a no-op."""
    validate(features, mismatch, explicit)
    resolved_f = cascade(features)
    # Write the cascade back so the STATE and the RECORD agree: a switch
    # that was silently turned off by its prerequisite must read False
    # everywhere, not just inside this function.
    features.update(resolved_f)
    # reset the derived selectors, then let the handlers rebuild them
    ns["FEATURE_FIXED_PARAMS"] = ()
    ns["FEATURE_FAMILY_MAP"] = {}
    ns["FEATURE_FAMILY_FALLBACK"] = None
    ns["INFERENCE_CHEMISTRY"] = dict(ns["TRUTH_CHEMISTRY_BASE"])
    ns["TRUTH_CHEMISTRY"] = dict(ns["TRUTH_CHEMISTRY_BASE"])
    for f in FEATURES_SPEC:
        _HANDLERS[f.name](ns, bool(resolved_f[f.name]))
    _check_magnitudes(ns, resolved_f)
    _apply_mismatch(ns, {**mismatch_defaults(), **(mismatch or {})})
    return resolved_f


def _apply_mismatch(ns: Dict, mm: Dict[str, Any]) -> None:
    """Split TRUTH_CHEMISTRY from INFERENCE_CHEMISTRY where asked to.

    Nothing here runs unless `enabled` is True, and `validate` refuses a
    configuration that declares a divergence without enabling it."""
    ns["MODEL_MISMATCH_ACTIVE"] = bool(mm["enabled"])
    if not mm["enabled"]:
        ns["INFERENCE_NOISE_SCALE"] = 1.0
        ns["TRUTH_PARAMETER_BIAS"] = {}
        return
    inf = ns["INFERENCE_CHEMISTRY"]
    for key, field_name in (("inference_reversible", "reversible"),
                            ("inference_activity_model", "activity_model"),
                            ("inference_arrhenius", "arrhenius"),
                            ("inference_van_t_hoff", "van_t_hoff")):
        if mm[key] is not None:
            inf[field_name] = mm[key]
    ns["INFERENCE_NOISE_SCALE"] = float(mm["inference_noise_scale"])
    ns["TRUTH_PARAMETER_BIAS"] = dict(mm["truth_parameter_bias"])


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def resolved(features: Dict[str, bool], mismatch: Dict[str, Any],
             ns: Dict) -> Dict[str, Any]:
    """The COMPLETE feature state, for the run record.

    Every switch appears with its value and its explanation, whether or not
    the runner mentioned it - so an archived run has no hidden defaults."""
    resolved_f = cascade(features)
    mm = {**mismatch_defaults(), **(mismatch or {})}
    return {
        "features": {f.name: bool(resolved_f[f.name]) for f in FEATURES_SPEC},
        "explanations": {
            f.name: {"section": f.section, "represents": f.represents,
                     "when_true": f.when_true, "when_false": f.when_false,
                     "default": f.default, "requires": list(f.requires),
                     "differs_from_default":
                         bool(resolved_f[f.name]) != f.default}
            for f in FEATURES_SPEC},
        "non_default": sorted(f.name for f in FEATURES_SPEC
                              if bool(resolved_f[f.name]) != f.default),
        "model_mismatch": {**mm, "ACTIVE": bool(mm["enabled"])},
        "derived": {
            "truth_chemistry": dict(ns.get("TRUTH_CHEMISTRY", {})),
            "inference_chemistry": dict(ns.get("INFERENCE_CHEMISTRY", {})),
            "fixed_parameters": list(ns.get("FEATURE_FIXED_PARAMS", ())),
            "family_map": dict(ns.get("FEATURE_FAMILY_MAP", {})),
            "family_fallback": ns.get("FEATURE_FAMILY_FALLBACK"),
            "inference_noise_scale": ns.get("INFERENCE_NOISE_SCALE", 1.0),
            "truth_parameter_bias": dict(ns.get("TRUTH_PARAMETER_BIAS", {})),
        },
    }


def summary_lines(features: Dict[str, bool],
                  mismatch: Optional[Dict[str, Any]] = None) -> List[str]:
    """Compact human-readable state, for the run banner."""
    resolved_f = cascade(features)
    lines = []
    for section in SECTIONS:
        names = [f.name for f in FEATURES_SPEC if f.section == section]
        on = [n for n in names if resolved_f[n]]
        off = [n for n in names if not resolved_f[n]]
        lines.append(f"    {section:15s} on: {len(on)}/{len(names)}"
                     + (f"   OFF: {', '.join(off)}" if off else ""))
    mm = {**mismatch_defaults(), **(mismatch or {})}
    if mm["enabled"]:
        lines.append("    MODEL MISMATCH ACTIVE: truth and inference "
                     "deliberately differ - this is a validation "
                     "experiment, not a physics run.")
    return lines
