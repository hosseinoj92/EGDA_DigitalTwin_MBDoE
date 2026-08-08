"""
Equilibrium observability of the reversible EGDA hydrolysis.

The reversible rate laws are

    r1 ~ k1 [H+] ( [EGDA][H2O] - [EGMA][AcOH]/K1 )
    r2 ~ k2 [H+] ( [EGMA][H2O] - [EG]  [AcOH]/K2 )

so K1 and K2 only influence the observables through the SECOND term: an
experiment that never accumulates products carries essentially no
information about the equilibrium constants, no matter how precisely it is
measured.  This module quantifies that BEFORE any campaign is designed.

Diagnostics per step i:

    phi_i = Q_i / K_i        (reaction quotient over equilibrium constant)

      phi << 1  forward-kinetic region: the reverse term is negligible and
                K_i is practically invisible
      phi ~ 1   equilibrium-sensitive region: K_i shapes the observables
      phi = 1   equilibrium

and the measurement-space sensitivity  |dC / d ln K_i|  (mol/L per e-fold
in K), evaluated by central finite differences with the SAME operator the
controller uses.

FIREWALL: every function here takes the parameter vector it is given.  The
campaign-side caller passes assumed/current/posterior parameters; the hidden
truth is only ever passed by post-campaign evaluation code.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from sdl import Layer1Bridge, OperatingConditions

#: species needed for the quotients (superset of the quantified ones)
_ALL = ("EGDA", "EGMA", "EG", "AcOH", "H2O")

#: below this concentration a denominator is treated as unresolvable and
#: the quotient is reported as NaN rather than exploding
_C_FLOOR = 1e-9


def reaction_quotients(conc: Dict[str, np.ndarray]
                       ) -> Tuple[np.ndarray, np.ndarray]:
    """(Q1, Q2) along a profile;  Q1 = [EGMA][AcOH]/([EGDA][H2O]),
    Q2 = [EG][AcOH]/([EGMA][H2O]).  NaN where a denominator vanishes."""
    def _q(num_a, num_b, den_a, den_b):
        den = np.asarray(den_a, float) * np.asarray(den_b, float)
        num = np.asarray(num_a, float) * np.asarray(num_b, float)
        out = np.full(np.shape(num), np.nan, dtype=float)
        ok = den > _C_FLOOR
        out[ok] = num[ok] / den[ok]
        return out

    q1 = _q(conc["EGMA"], conc["AcOH"], conc["EGDA"], conc["H2O"])
    q2 = _q(conc["EG"], conc["AcOH"], conc["EGMA"], conc["H2O"])
    return q1, q2


def phi_profiles(bridge: Layer1Bridge, theta_nat: Dict[str, float],
                 u: OperatingConditions, z_m: np.ndarray
                 ) -> Dict[str, np.ndarray]:
    """phi1, phi2 and the concentration profile at the given parameters."""
    flat = bridge.concentrations_at(theta_nat, u, np.asarray(z_m, float),
                                    _ALL)
    nz = len(np.atleast_1d(z_m))
    conc = {sp: flat[i * nz:(i + 1) * nz] for i, sp in enumerate(_ALL)}
    q1, q2 = reaction_quotients(conc)
    kin = bridge.kinetics_from_theta(theta_nat)
    T_K = u.T_C + 273.15
    K1, K2 = kin.eq1.K(T_K), kin.eq2.K(T_K)
    out = {sp: conc[sp] for sp in _ALL}
    out["phi1"] = q1 / K1
    out["phi2"] = q2 / K2
    out["z_m"] = np.asarray(z_m, float)
    return out


def k_sensitivity(bridge: Layer1Bridge, theta_nat: Dict[str, float],
                  u: OperatingConditions, z_m: np.ndarray,
                  species: Sequence[str] = ("EGDA", "EGMA", "EG", "AcOH"),
                  rel_step: float = 0.05
                  ) -> Dict[str, float]:
    """max_z |dC/d ln K_i| over the measured species, mol/L per e-fold.

    Central differences in ln K at the SUPPLIED parameters (no truth
    access).  Returns zeros for an irreversible parameterization."""
    out = {"dC_dlnK1": 0.0, "dC_dlnK2": 0.0}
    z = np.asarray(z_m, float)
    for key, name in (("K1_ref", "dC_dlnK1"), ("K2_ref", "dC_dlnK2")):
        if key not in theta_nat:
            continue
        hi = dict(theta_nat)
        lo = dict(theta_nat)
        hi[key] = theta_nat[key] * np.exp(rel_step)
        lo[key] = theta_nat[key] * np.exp(-rel_step)
        y_hi = bridge.concentrations_at(hi, u, z, tuple(species))
        y_lo = bridge.concentrations_at(lo, u, z, tuple(species))
        out[name] = float(np.max(np.abs(y_hi - y_lo)) / (2.0 * rel_step))
    return out


def domain_scan(bridge: Layer1Bridge, theta_nat: Dict[str, float],
                conditions: Sequence[OperatingConditions],
                n_z: int = 21) -> List[Dict]:
    """One diagnostic row per operating condition over the reachable
    domain: residence time, outlet conversion, max(phi1), max(phi2) and the
    two K sensitivities."""
    L = bridge.geometry.length_m
    z = np.linspace(L / n_z, L, n_z)
    rows = []
    for u in conditions:
        prof = phi_profiles(bridge, theta_nat, u, z)
        q_m3_s = (u.Q1_mL_min + u.Q2_mL_min) * 1e-6 / 60.0
        tau = bridge.geometry.residence_time_s(q_m3_s)
        c0 = float(prof["EGDA"][0] + prof["EGMA"][0] + prof["EG"][0])
        x_out = (1.0 - float(prof["EGDA"][-1]) / c0) if c0 > 0 else np.nan
        sens = k_sensitivity(bridge, theta_nat, u, z)
        rows.append({
            "T_C": u.T_C,
            "Q_total_mL_min": u.Q1_mL_min + u.Q2_mL_min,
            "C_cat_M": u.C_cat_M,
            "tau_s": tau,
            "X_outlet": x_out,
            "max_phi1": float(np.nanmax(prof["phi1"])),
            "max_phi2": float(np.nanmax(prof["phi2"])),
            **sens,
        })
    return rows


def verdict(rows: Sequence[Dict], phi_threshold: float = 0.05,
            sigma_ref_M: float = 0.005, snr_threshold: float = 1.0) -> Dict:
    """Domain-level verdict on equilibrium identifiability.

    phi_threshold: below this the reverse term contributes < ~5% of the
    forward term, i.e. K is practically invisible.
    sigma_ref_M: nominal per-point measurement sigma (default 5 mM, the
    order of the calibrated NMR quantification error), used to convert the
    raw sensitivity into an interpretable SNR

        snr_i = max_z |dC/d ln K_i| / sigma_ref

    snr < 1 means one e-fold of K_i moves the observables by less than one
    measurement sigma at the best condition in the domain: identifiable in
    principle, but only by averaging many acquisitions."""
    p1 = max((r["max_phi1"] for r in rows), default=0.0)
    p2 = max((r["max_phi2"] for r in rows), default=0.0)
    s1 = max((r["dC_dlnK1"] for r in rows), default=0.0)
    s2 = max((r["dC_dlnK2"] for r in rows), default=0.0)
    snr1, snr2 = s1 / sigma_ref_M, s2 / sigma_ref_M
    identifiable = {
        "K1_ref": bool(p1 >= phi_threshold and snr1 >= snr_threshold),
        "K2_ref": bool(p2 >= phi_threshold and snr2 >= snr_threshold),
    }
    msgs = []
    for key, phi, sens, snr in (("K1_ref", p1, s1, snr1),
                                ("K2_ref", p2, s2, snr2)):
        if phi < phi_threshold:
            msgs.append(
                f"{key} is practically unidentifiable because the "
                f"experimental domain does not sufficiently excite the "
                f"reversible kinetics (max phi = {phi:.3g} < "
                f"{phi_threshold:g}).")
        elif snr < snr_threshold:
            msgs.append(
                f"{key} is weakly identifiable: the domain DOES reach the "
                f"equilibrium-sensitive region (max phi = {phi:.3g}) but one "
                f"e-fold in {key} moves the observables by only "
                f"{sens * 1e3:.1f} mM = {snr:.2f} sigma_ref - it can only be "
                f"determined by averaging many acquisitions.")
    return {"max_phi1": p1, "max_phi2": p2,
            "max_dC_dlnK1": s1, "max_dC_dlnK2": s2,
            "snr_K1": snr1, "snr_K2": snr2, "sigma_ref_M": sigma_ref_M,
            "identifiable": identifiable, "messages": msgs}


def write_scan_csv(rows: Sequence[Dict], path: str) -> None:
    import csv
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    keys = ["T_C", "Q_total_mL_min", "C_cat_M", "tau_s", "X_outlet",
            "max_phi1", "max_phi2", "dC_dlnK1", "dC_dlnK2"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows([{k: r[k] for k in keys} for r in rows])
    print(f"saved: {os.path.relpath(path)}")


def plot_phi_profiles(bridge: Layer1Bridge, theta_nat: Dict[str, float],
                      conditions: Sequence[OperatingConditions],
                      path: str, n_z: int = 41) -> None:
    """Axial concentration profiles with phi1/phi2 underneath, so the
    kinetic -> equilibrium-sensitive transition is directly visible."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import os

    L = bridge.geometry.length_m
    z = np.linspace(L / n_z, L, n_z)
    n = len(conditions)
    fig, axes = plt.subplots(2, n, figsize=(4.2 * n, 6.4), squeeze=False,
                             sharex=True)
    for j, u in enumerate(conditions):
        prof = phi_profiles(bridge, theta_nat, u, z)
        ax = axes[0][j]
        for sp, col in (("EGDA", "#1b3a5c"), ("EGMA", "#2a7f62"),
                        ("EG", "#a23b2e"), ("AcOH", "#8c5a2b")):
            ax.plot(z / L, prof[sp], color=col, lw=1.6, label=sp)
        q_m3_s = (u.Q1_mL_min + u.Q2_mL_min) * 1e-6 / 60.0
        ax.set_title(f"T={u.T_C:.0f} C, Q={u.Q1_mL_min + u.Q2_mL_min:.2f} "
                     f"mL/min\ntau={bridge.geometry.residence_time_s(q_m3_s):.0f} s",
                     fontsize=9)
        if j == 0:
            ax.set_ylabel("concentration / M")
            ax.legend(fontsize=7, frameon=False, ncol=2)
        ax2 = axes[1][j]
        ax2.plot(z / L, prof["phi1"], color="#1b3a5c", lw=1.8,
                 label=r"$\phi_1 = Q_1/K_1$")
        ax2.plot(z / L, prof["phi2"], color="#a23b2e", lw=1.8,
                 label=r"$\phi_2 = Q_2/K_2$")
        ax2.axhline(1.0, color="#555555", ls="--", lw=0.9)
        ax2.axhline(0.05, color="#999999", ls=":", lw=0.9)
        ax2.set_yscale("log")
        ax2.set_xlabel("z / L")
        if j == 0:
            ax2.set_ylabel(r"$\phi$  (1 = equilibrium)")
            ax2.legend(fontsize=8, frameon=False)
    fig.suptitle("Equilibrium observability: kinetic region "
                 r"($\phi \ll 1$) $\rightarrow$ equilibrium-sensitive "
                 r"region ($\phi \sim 1$)")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"saved: {os.path.relpath(path)}")
