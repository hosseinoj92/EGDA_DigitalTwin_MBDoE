"""
Plug-flow validity of a reactor OVER ITS WHOLE OPERATING ENVELOPE.

WHY THIS MODULE EXISTS
----------------------
The framework's entire information source is the mapping "axial position ->
residence time".  If the reactor is not a plug-flow reactor at the flow the
experiment commands, that mapping is a distribution rather than a number and
every profile measurement is mis-modelled.  Validity is therefore not a
diagnostic, it is a CONSTRAINT - and it has to hold at every operating point
the design space can reach, not only at a nominal one.

Two failure modes are checked, both with a criterion Layer 1 already
publishes (pfr_twin/diagnostics.py):

  RADIAL   t_rad / tau, the radial mixing time over the residence time.
           Large -> the streamlines never exchange, axial position maps to a
           DISTRIBUTION of ages, plug flow is optimistic.

  AXIAL    Bo = u L / D_ax, the vessel Bodenstein (Peclet) number.
           Bo >~ 100 is the classical "< 1 % deviation from plug flow"
           boundary; small Bo means back-mixing smears the profile.

OPEN TUBE
---------
Radial mixing is molecular: t_rad = R^2 / D_m, tau = eps V / Q, so

    t_rad / tau = Q / (pi D_m L eps)                                    (1)

- the BORE CANCELS, only length, flow and holdup help.  In the Taylor-Aris
regime the axial dispersion coefficient is D_ax = D_m + u^2 R^2 / (48 D_m),
and substituting u = Q / (pi R^2) gives the closed form

    Bo = u L / D_ax  ->  48 pi D_m L / Q  =  48 / (t_rad/tau)            (2)

(to within the negligible molecular term).  The bore cancels here too, and
the two criteria are ONE criterion in disguise: Bo >= 100 is exactly
t_rad/tau <= 0.48.  That is worth stating plainly, because it means an open
laminar tube cannot be made plug-flow by choosing a different bore, and the
lenient advisory boundary t_rad/tau <= 10 corresponds to Bo = 4.8, i.e. a
strongly back-mixed vessel.  Taylor-Aris itself only applies when
t_rad << tau; outside that range the Bodenstein number computed from it is
meaningless and is reported as NaN rather than as a pass.

PACKED BED
----------
Beads break the laminar streamlines, which is the whole engineering point of
packing - but "packed" is NOT a synonym for "valid", and returning a
validity ratio of zero for a packed bed (as this framework previously did)
asserts an ideality instead of checking one.  The bed is therefore checked
against the standard packed-bed dispersion picture:

    d_p   = d / bed_to_particle_ratio          (wall-channelling limit)
    D_r   = D_m / tortuosity + u_i d_p / Pe_r  (radial dispersion)
    D_ax  = D_m / tortuosity + u_i d_p / Pe_ax (axial dispersion)
    t_rad / tau = (R^2 / D_r) / (eps V / Q)
    Bo    = u_i L / D_ax
    plus the geometric requirement  L / d_p >= min_bed_aspect

with Pe_ax ~ 0.5 and Pe_r ~ 10 the low-Reynolds liquid-phase asymptotes
(Gunn 1987; Delgado 2006 - liquids disperse axially much more than gases,
so 0.5 is the conservative end of the reported 0.5-2 band).  Because the
mechanical terms dominate and both scale with u_i, Bo -> Pe_ax L / d_p at
any appreciable flow: the packed-bed criterion becomes a BED ASPECT RATIO
requirement, which is exactly how the packed-bed literature states it.

ASSUMPTIONS THAT CODE CANNOT VALIDATE (declared, not hidden):
  * Pe_ax, Pe_r and the tortuosity are literature ASYMPTOTES, not measured
    values for this bed;
  * the bed is assumed uniformly packed with monodisperse inert spheres of
    d_p = d / bed_to_particle_ratio, with no wall channelling beyond what
    that ratio guards against, and no stagnant intra-particle holdup;
  * D_m is a single dilute-aqueous value for every species.
Setting packed_plug_flow_assumed=True restores the old "a packed bed is
valid by declaration" behaviour; it is then recorded in the run record as an
ASSUMPTION rather than as a check that passed.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence

import numpy as np

_LAYER1_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "PFR_H2SO4_digital_twin"))
if _LAYER1_DIR not in sys.path:
    sys.path.insert(0, _LAYER1_DIR)

from pfr_twin.parameters import DIFFUSIVITY_LIQ, ReactorGeometry  # noqa: E402


@dataclass(frozen=True)
class ValidityCriteria:
    """The plug-flow admissibility criteria, as configuration.

    Defaults reproduce Layer 1 published advisory boundary for the radial
    criterion (10.0) and the classical Bo >= 100 for the axial one."""
    #: t_rad / tau above which radial segregation invalidates plug flow
    max_radial_ratio: float = 10.0
    #: vessel Bodenstein number below which axial dispersion invalidates it.
    #: None disables the axial criterion (it is then still REPORTED).
    min_bodenstein: Optional[float] = 100.0
    #: enforce the axial criterion, or only report it.  Reporting-only is a
    #: deliberate, declared relaxation - never a silent one.
    enforce_bodenstein: bool = True
    #: d / d_p; >= 10 is the standard guard against wall channelling
    bed_to_particle_ratio: float = 10.0
    #: L / d_p; >= 100 is the standard packed-bed entrance/exit requirement
    min_bed_aspect: float = 100.0
    #: low-Re liquid asymptotes of the particle Peclet numbers
    packed_peclet_axial: float = 0.5
    packed_peclet_radial: float = 10.0
    #: bed tortuosity applied to the molecular contribution
    tortuosity: float = 1.4
    #: dilute-aqueous molecular diffusivity, m^2/s
    diffusivity_m2_s: float = DIFFUSIVITY_LIQ
    #: LEGACY / DECLARED-IDEALITY escape hatch: treat any packed bed as
    #: plug-flow valid without checking it.  Recorded as an assumption.
    packed_plug_flow_assumed: bool = False

    def __post_init__(self) -> None:
        if self.max_radial_ratio <= 0.0:
            raise ValueError("max_radial_ratio must be positive.")
        if self.min_bodenstein is not None and self.min_bodenstein <= 0.0:
            raise ValueError("min_bodenstein must be positive or None.")
        for name in ("bed_to_particle_ratio", "min_bed_aspect",
                     "packed_peclet_axial", "packed_peclet_radial",
                     "tortuosity", "diffusivity_m2_s"):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be positive.")


DEFAULT_CRITERIA = ValidityCriteria()

#: the criterion names a row can fail, in report order
CRITERIA_NAMES = ("radial_mixing", "axial_dispersion", "bed_aspect")


def _geom(geometry) -> ReactorGeometry:
    if isinstance(geometry, ReactorGeometry):
        return geometry
    g = {k: v for k, v in dict(geometry).items() if not k.startswith("_")}
    return ReactorGeometry(**g)


def evaluate(geometry, q_mL_min: float,
             crit: ValidityCriteria = DEFAULT_CRITERIA) -> Dict:
    """Full plug-flow diagnosis of ONE geometry at ONE total flow.

    Returns a flat dict (one CSV row) carrying every quantity the verdict
    rests on, so a reader can re-derive the decision without rerunning
    anything."""
    g = _geom(geometry)
    q_m3s = float(q_mL_min) * 1e-6 / 60.0
    eps = g.void_fraction
    radius = 0.5 * g.diameter_m
    d_m = float(crit.diffusivity_m2_s)
    tau = g.residence_time_s(q_m3s)
    u_int = q_m3s / g.flow_area_m2                 # interstitial velocity
    packed = bool(g.packing_enabled)
    failed: List[str] = []

    if packed and crit.packed_plug_flow_assumed:
        # DECLARED ideality: recorded as an assumption, not as a check.
        row = _row(g, q_mL_min, tau, u_int, eps, packed)
        row.update({"particle_diameter_m": float("nan"),
                    "bed_aspect_L_over_dp": float("nan"),
                    "D_rad_m2_s": float("nan"), "D_ax_m2_s": float("nan"),
                    "t_rad_over_tau": 0.0, "bodenstein": float("inf"),
                    "threshold": float(crit.max_radial_ratio),
                    "min_bodenstein": (float(crit.min_bodenstein)
                                       if crit.min_bodenstein else
                                       float("nan")),
                    "plug_flow_valid": 1, "failed_criteria": "",
                    "basis": "ASSUMED (packed_plug_flow_assumed=True)",
                    "regime": "packed bed, plug flow ASSUMED not checked"})
        return row

    if packed:
        d_p = g.diameter_m / float(crit.bed_to_particle_ratio)
        aspect = g.length_m / d_p
        d_mol = d_m / float(crit.tortuosity)
        d_rad = d_mol + u_int * d_p / float(crit.packed_peclet_radial)
        d_ax = d_mol + u_int * d_p / float(crit.packed_peclet_axial)
        t_rad = radius ** 2 / d_rad
        ratio = t_rad / tau if tau > 0.0 else float("inf")
        bo = u_int * g.length_m / d_ax if d_ax > 0.0 else float("inf")
        basis = (f"packed bed: d_p = d/{crit.bed_to_particle_ratio:g}, "
                 f"Pe_ax = {crit.packed_peclet_axial:g}, "
                 f"Pe_r = {crit.packed_peclet_radial:g}")
        if aspect < float(crit.min_bed_aspect):
            failed.append("bed_aspect")
    else:
        d_p = float("nan")
        aspect = float("nan")
        d_rad = d_m
        t_rad = radius ** 2 / d_m
        ratio = t_rad / tau if tau > 0.0 else float("inf")
        # Taylor-Aris is only defined where the tube IS radially mixed; the
        # closed form Bo = 48/(t_rad/tau) is reported only there.
        if ratio <= 1.0:
            u_sup = q_m3s / g.area_m2
            d_ax = d_m + u_sup ** 2 * radius ** 2 / (48.0 * d_m)
            bo = u_sup * g.length_m / d_ax
        else:
            d_ax = float("nan")
            bo = float("nan")
        basis = "open tube: t_rad = R^2/D_m, Taylor-Aris D_ax"

    if not np.isfinite(ratio) or ratio > float(crit.max_radial_ratio):
        failed.append("radial_mixing")
    if crit.min_bodenstein is not None and crit.enforce_bodenstein:
        # A NaN Bodenstein (Taylor-Aris inapplicable) is NOT a pass: it is
        # reported as a failure of the axial criterion.
        if not np.isfinite(bo) or bo < float(crit.min_bodenstein):
            failed.append("axial_dispersion")

    row = _row(g, q_mL_min, tau, u_int, eps, packed)
    row.update({
        "particle_diameter_m": float(d_p),
        "bed_aspect_L_over_dp": float(aspect),
        "D_rad_m2_s": float(d_rad), "D_ax_m2_s": float(d_ax),
        "t_rad_over_tau": float(ratio), "bodenstein": float(bo),
        "threshold": float(crit.max_radial_ratio),
        "min_bodenstein": (float(crit.min_bodenstein)
                           if crit.min_bodenstein is not None
                           else float("nan")),
        "plug_flow_valid": int(not failed),
        "failed_criteria": "+".join(failed),
        "basis": basis,
        "regime": _regime(packed, ratio, bo, crit),
    })
    return row


def _row(g: ReactorGeometry, q_mL_min: float, tau: float, u_int: float,
         eps: float, packed: bool) -> Dict:
    return {"length_m": float(g.length_m), "diameter_m": float(g.diameter_m),
            "packed": int(packed), "bed_void_fraction": float(eps),
            "Q_total_mL_min": float(q_mL_min), "tau_s": float(tau),
            "interstitial_velocity_m_s": float(u_int)}


def _regime(packed: bool, ratio: float, bo: float,
            crit: ValidityCriteria) -> str:
    if not np.isfinite(ratio):
        return "no flow / degenerate geometry"
    if ratio > 10.0:
        base = "RADIALLY SEGREGATED STREAMLINES"
    elif ratio > 1.0:
        base = "partial radial mixing"
    elif ratio > 0.1:
        base = "approaching Taylor-Aris"
    else:
        base = "radially well mixed (Taylor-Aris)"
    if packed:
        base = "packed bed, " + base
    if crit.min_bodenstein is None:
        return base
    if not np.isfinite(bo):
        return base + "; Bo undefined (Taylor-Aris inapplicable)"
    if bo < float(crit.min_bodenstein):
        return base + f"; back-mixed (Bo = {bo:.1f})"
    return base + f"; axially plug-flow (Bo = {bo:.0f})"


def rows(geometry, flows: Sequence[float],
         crit: ValidityCriteria = DEFAULT_CRITERIA) -> List[Dict]:
    """One row per flow, sorted by flow - the archive table."""
    return [evaluate(geometry, float(q), crit)
            for q in sorted(float(x) for x in flows)]


def is_feasible(geometry, flows: Sequence[float],
                crit: ValidityCriteria = DEFAULT_CRITERIA) -> bool:
    """True only when the geometry is valid at EVERY flow given.

    This is the function the geometry optimizer must call: a reactor that is
    admissible only at a nominal flow is not admissible, because the design
    space is free to command any of the others."""
    return all(r["plug_flow_valid"] for r in rows(geometry, flows, crit))


def worst_row(geometry, flows: Sequence[float],
              crit: ValidityCriteria = DEFAULT_CRITERIA) -> Dict:
    """The flow at which the geometry is furthest from admissible - the one
    that decides feasibility."""
    rs = rows(geometry, flows, crit)
    bad = [r for r in rs if not r["plug_flow_valid"]]
    pool = bad or rs
    return max(pool, key=lambda r: (r["t_rad_over_tau"]
                                    if np.isfinite(r["t_rad_over_tau"])
                                    else np.inf))


# --------------------------------------------------------------------------- #
# Guidance for when NOTHING in the declared box is admissible
# --------------------------------------------------------------------------- #
def max_admissible_flow_mL_min(geometry,
                               crit: ValidityCriteria = DEFAULT_CRITERIA
                               ) -> float:
    """Largest total flow at which this geometry still satisfies every
    enforced criterion (0.0 if none does).

    For an open tube both criteria are monotone in Q and the answer is
    closed-form; for a packed bed the mechanical terms make the ratios
    almost flow-independent, so a bisection over a wide bracket is used."""
    g = _geom(geometry)
    if not g.packing_enabled:
        d_m = float(crit.diffusivity_m2_s)
        lim = float(crit.max_radial_ratio)
        if crit.min_bodenstein is not None and crit.enforce_bodenstein:
            # Bo = 48 / (t_rad/tau)  ->  ratio <= 48 / Bo_min
            lim = min(lim, 48.0 / float(crit.min_bodenstein))
        q_m3s = lim * np.pi * d_m * g.length_m * g.void_fraction
        return float(q_m3s * 60.0 * 1e6)
    lo, hi = 0.0, 1.0e4
    if not evaluate(g, 1e-6, crit)["plug_flow_valid"]:
        return 0.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if evaluate(g, mid, crit)["plug_flow_valid"]:
            lo = mid
        else:
            hi = mid
    return float(lo)


def min_admissible_length_m(geometry, q_mL_min: float,
                            crit: ValidityCriteria = DEFAULT_CRITERIA
                            ) -> float:
    """Shortest reactor of this bore/packing state that is admissible at
    q_mL_min - the number to quote when recommending a bound change."""
    g = _geom(geometry)
    if not g.packing_enabled:
        d_m = float(crit.diffusivity_m2_s)
        lim = float(crit.max_radial_ratio)
        if crit.min_bodenstein is not None and crit.enforce_bodenstein:
            lim = min(lim, 48.0 / float(crit.min_bodenstein))
        q_m3s = float(q_mL_min) * 1e-6 / 60.0
        return float(q_m3s / (lim * np.pi * d_m * g.void_fraction))
    lo, hi = 1e-4, 1.0e3
    if not evaluate(replace(g, length_m=hi), q_mL_min,
                    crit)["plug_flow_valid"]:
        return float("inf")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if evaluate(replace(g, length_m=mid), q_mL_min,
                    crit)["plug_flow_valid"]:
            hi = mid
        else:
            lo = mid
    return float(hi)


def explain(geometry, flows: Sequence[float],
            crit: ValidityCriteria = DEFAULT_CRITERIA) -> str:
    """Human-readable verdict plus WHICH BOUND TO CHANGE.

    Written as guidance rather than a bare refusal, because "no admissible
    reactor exists" is only useful next to "here is what would make one
    exist"."""
    g = _geom(geometry)
    rs = rows(g, flows, crit)
    bad = [r for r in rs if not r["plug_flow_valid"]]
    kind = ("PACKED, eps={:.2f}".format(g.void_fraction)
            if g.packing_enabled else "OPEN tube")
    head = "reactor {:.1f} cm x {:.1f} mm ({})".format(
        g.length_m * 100.0, g.diameter_m * 1e3, kind)
    if not bad:
        return ("{}: plug-flow valid at all {} design flows "
                "({:g}-{:g} mL/min).".format(
                    head, len(rs),
                    min(r["Q_total_mL_min"] for r in rs),
                    max(r["Q_total_mL_min"] for r in rs)))
    w = worst_row(g, flows, crit)
    q_hi = max(float(q) for q in flows)
    q_max = max_admissible_flow_mL_min(g, crit)
    l_min = min_admissible_length_m(g, q_hi, crit)
    bo_lim = crit.min_bodenstein if crit.min_bodenstein else "off"
    lines = [
        "{}: FAILS plug-flow validity at {}/{} design flows.  Worst: "
        "{:g} mL/min, t_rad/tau = {:.3g} (limit {:g}), Bo = {:.3g} "
        "(limit {}); failed: {}.".format(
            head, len(bad), len(rs), w["Q_total_mL_min"],
            w["t_rad_over_tau"], crit.max_radial_ratio, w["bodenstein"],
            bo_lim, w["failed_criteria"]),
        "  Axial position then maps to a DISTRIBUTION of residence times "
        "rather than a single tau, which is the entire information source "
        "of this framework.",
        "  To make the declared design space admissible, change ONE of:",
        "    * flow bound     -> Q_total <= {:.3g} mL/min in this reactor "
        "(the design space currently commands up to {:g})".format(
            q_max, q_hi),
        "    * reactor length -> L >= {:.3g} m at the highest commanded "
        "flow (currently {:.3g} m)".format(l_min, g.length_m),
    ]
    if not g.packing_enabled:
        lines.append(
            "    * PACK the tube (inert spheres, eps ~ 0.4): the beads break "
            "the laminar streamlines.  This is the standard engineering fix "
            "and the only one that does not shrink the design space.  It "
            "shortens tau by eps and therefore changes every conversion - a "
            "deliberate physics change, to be declared, never a silent "
            "default.")
    lines.append(
        "    * or accept the non-ideality EXPLICITLY by raising "
        "max_radial_ratio / lowering min_bodenstein, which knowingly applies "
        "the plug-flow model outside its range.")
    return "\n".join(lines)
