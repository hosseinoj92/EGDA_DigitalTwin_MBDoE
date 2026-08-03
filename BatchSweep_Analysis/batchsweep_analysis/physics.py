from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np


def _kinetic_constants(catalyst: str, temperature_K: float) -> tuple[float, float]:
    """Read the current simulator constants without modifying or running it."""
    source_root = Path(__file__).resolve().parents[2] / "PFR_H2SO4_digital_twin"
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    try:
        from pfr_twin.parameters import default_kinetics

        params = default_kinetics(catalyst)
        return params.step1.k(temperature_K), params.step2.k(temperature_K)
    except (ImportError, AttributeError):
        # Documented fallback matches the simulator defaults at analysis v1.0.
        if catalyst == "NaOH":
            a1, e1, a2, e2 = 2.6e7, 46_000.0, 2.6e7, 48_000.0
        else:
            a1, e1, a2, e2 = 1.0e6, 55_000.0, 1.0e6, 57_000.0
        gas_constant = 8.314462618
        return (
            a1 * math.exp(-e1 / (gas_constant * temperature_K)),
            a2 * math.exp(-e2 / (gas_constant * temperature_K)),
        )


def water_density_g_L(temperature_K: float) -> float:
    temperatures = np.array([273.15, 293.15, 313.15, 333.15, 353.15, 373.15])
    densities = np.array([999.8, 998.2, 992.2, 983.2, 971.8, 958.4])
    return float(np.interp(temperature_K, temperatures, densities))


def water_viscosity_Pa_s(temperature_K: float) -> float:
    return 2.414e-5 * 10.0 ** (247.8 / (temperature_K - 140.0))


def axial_peak(profile: list[dict[str, float]], relative_threshold: float = 0.95) -> dict[str, Any]:
    concentrations = np.array([point["C_EGMA_mol_L"] for point in profile], dtype=float)
    yields = np.array([point["Y_EGMA"] for point in profile], dtype=float)
    x = np.array([point["x_m"] for point in profile], dtype=float)
    time = np.array([point["tau_s"] for point in profile], dtype=float)
    index = int(np.nanargmax(concentrations))
    peak = float(concentrations[index])
    threshold = relative_threshold * peak
    indices = np.flatnonzero(concentrations >= threshold - 1e-15)
    first, last = int(indices[0]), int(indices[-1])
    length = float(x[-1])
    outlet_time = float(time[-1])
    scale_c = max(abs(float(concentrations[-1])), abs(float(concentrations[-2])), 1.0)
    return {
        "C_EGMA_peak_M": peak,
        "Y_EGMA_peak": float(yields[int(np.nanargmax(yields))]),
        "x_peak_m": float(x[index]),
        "tau_peak_s": float(time[index]),
        "x_peak_over_L": float(x[index] / length) if length else math.nan,
        "tau_peak_over_tau_out": float(time[index] / outlet_time) if outlet_time else math.nan,
        "peak_is_interior": 0 < index < len(profile) - 1,
        "peak_is_at_outlet": index == len(profile) - 1,
        "remaining_length_after_peak_m": float(length - x[index]),
        "remaining_time_after_peak_s": float(outlet_time - time[index]),
        "EGMA_increasing_at_outlet": bool(concentrations[-1] - concentrations[-2] > 1e-12 * scale_c),
        "peak95_start_x_m": float(x[first]),
        "peak95_end_x_m": float(x[last]),
        "peak95_width_m": float(x[last] - x[first]),
        "peak95_width_over_L": float((x[last] - x[first]) / length) if length else math.nan,
        "peak95_start_tau_s": float(time[first]),
        "peak95_end_tau_s": float(time[last]),
        "peak95_width_s": float(time[last] - time[first]),
    }


def enrich(row: dict[str, Any], profile: list[dict[str, float]], config: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    temperature_K = float(row["temp_C"]) + 273.15
    q1 = float(row["Q1_mL_min"])
    q2 = float(row["Q2_mL_min"])
    q_total_mL_min = q1 + q2
    q_total_m3_s = q_total_mL_min * 1.0e-6 / 60.0
    area = math.pi * float(row["diameter_m"]) ** 2 / 4.0
    volume = area * float(row["length_m"])
    velocity = q_total_m3_s / area
    tau_calculated = volume / q_total_m3_s
    first, last = profile[0], profile[-1]
    c_egda0 = first["C_EGDA_mol_L"]
    c_water0 = first["C_H2O_mol_L"]
    c_oh0 = first["C_OH_mol_L"]
    c_catalyst_mixed = q2 / q_total_mL_min * float(row["C_catalyst_feed_M"])
    k1, k2 = _kinetic_constants(str(row["catalyst"]), temperature_K)
    kappa1 = float(row.get("kappa1_1_s", k1 * c_catalyst_mixed))
    kappa2 = float(row.get("kappa2_1_s", k2 * c_catalyst_mixed))
    c_rate_driver = kappa1 / k1 if k1 > 0.0 else math.nan
    catalyst_to_egda = c_catalyst_mixed / c_egda0 if c_egda0 > 0.0 else math.nan

    density_mix_25 = (q1 * float(row["density1_g_L"]) + q2 * float(row["density2_g_L"])) / q_total_mL_min
    density_temperature = density_mix_25 * water_density_g_L(temperature_K) / water_density_g_L(298.15)
    viscosity = water_viscosity_Pa_s(temperature_K)
    reynolds = density_temperature * velocity * float(row["diameter_m"]) / viscosity
    t_rad = (float(row["diameter_m"]) / 2.0) ** 2 / float(config["diffusivity_m2_s"])
    radial_ratio = t_rad / tau_calculated
    d_ax = math.nan
    bo = math.nan
    if reynolds >= 4000.0:
        flow_regime = "turbulent"
        pfr_advisory = "turbulent_plug_flow_reasonable"
    elif reynolds >= 2100.0:
        flow_regime = "transitional"
        pfr_advisory = "transitional_plug_flow_reasonable"
    elif radial_ratio < 0.1:
        flow_regime = "laminar"
        d_ax = float(config["diffusivity_m2_s"]) + velocity ** 2 * (float(row["diameter_m"]) / 2.0) ** 2 / (48.0 * float(config["diffusivity_m2_s"]))
        bo = velocity * float(row["length_m"]) / d_ax
        pfr_advisory = "taylor_aris_good" if bo > 100.0 else "taylor_aris_axial_dispersion"
    elif radial_ratio > 10.0:
        flow_regime = "laminar"
        pfr_advisory = "radially_segregated"
    else:
        flow_regime = "laminar"
        pfr_advisory = "partial_radial_mixing"

    pressure_flag = float(row["temp_C"]) > float(config["pressure_threshold_C"])
    verification = abs(float(row.get("verification_error", 0.0) or 0.0))
    drift = abs(float(row.get("invariant_drift", 0.0) or 0.0))
    numerical_valid = verification <= float(config["verification_error_limit"]) and drift <= float(config["invariant_drift_limit"])
    pressure_valid = bool(config["allow_pressurized_operation"]) or not pressure_flag
    pfr_supported = pfr_advisory not in {"radially_segregated", "partial_radial_mixing", "taylor_aris_axial_dispersion"}
    physical_valid = numerical_valid and pressure_valid and pfr_supported

    c_egma_out = last["C_EGMA_mol_L"]
    c_eg_out = last["C_EG_mol_L"]
    c_acoh_out = last["C_AcOH_mol_L"]
    c_water_out = last["C_H2O_mol_L"]
    c_egda_out = last["C_EGDA_mol_L"]
    egma_molar_flow = q_total_m3_s * c_egma_out * 1000.0
    eg_feed_molar_flow = q1 * 1.0e-6 / 60.0 * float(row["C_EGDA_feed_M"]) * 1000.0
    catalyst_feed_molar_flow = q2 * 1.0e-6 / 60.0 * float(row["C_catalyst_feed_M"]) * 1000.0
    sty_mol_m3_s = egma_molar_flow / volume
    sty_mol_L_h = sty_mol_m3_s * 3.6

    additions = {
        "temperature_K": temperature_K,
        "inverse_temperature_K_inv": 1.0 / temperature_K,
        "area_m2": area,
        "volume_m3": volume,
        "volume_mL": volume * 1.0e6,
        "Q_total_mL_min": q_total_mL_min,
        "Q_total_m3_s": q_total_m3_s,
        "superficial_velocity_m_s": velocity,
        "tau_calculated_s": tau_calculated,
        "tau_relative_error": (float(row["tau_s"]) - tau_calculated) / tau_calculated,
        "linked_equal_flows": math.isclose(q1, q2, rel_tol=0.0, abs_tol=1e-12),
        "stream1_flow_fraction": q1 / q_total_mL_min,
        "stream2_flow_fraction": q2 / q_total_mL_min,
        "C_EGDA_in_M": c_egda0,
        "C_catalyst_mixed_M": c_catalyst_mixed,
        "C_rate_driver_in_M": c_rate_driver,
        "C_H_plus_in_M": c_rate_driver if row["catalyst"] == "H2SO4" else 0.0,
        "C_OH_in_M": c_oh0,
        "C_H2O_in_M": c_water0,
        "EGDA_dilution_factor": c_egda0 / float(row["C_EGDA_feed_M"]),
        "catalyst_dilution_factor": c_catalyst_mixed / float(row["C_catalyst_feed_M"]),
        "catalyst_to_EGDA_molar_ratio": catalyst_to_egda,
        "catalyst_per_acetate_group": catalyst_to_egda / 2.0,
        "k1_L_mol_s": k1,
        "k2_L_mol_s": k2,
        "k1_over_k2": k1 / k2,
        "Da1": kappa1 * tau_calculated,
        "Da2": kappa2 * tau_calculated,
        "R_OH": c_oh0 / c_egda0 if c_egda0 > 0.0 else math.nan,
        "EGDA_feed_mol_s": eg_feed_molar_flow,
        "catalyst_feed_mol_s": catalyst_feed_molar_flow,
        "EGMA_out_mol_s": egma_molar_flow,
        "STY_EGMA_mol_m3_s": sty_mol_m3_s,
        "STY_EGMA_mol_Lreactor_h": sty_mol_L_h,
        "EGMA_mol_per_catalyst_mol": egma_molar_flow / catalyst_feed_molar_flow if catalyst_feed_molar_flow else math.nan,
        "EGMA_mol_per_EGDA_feed_mol": egma_molar_flow / eg_feed_molar_flow if eg_feed_molar_flow else math.nan,
        "water_depletion_fraction": (c_water0 - c_water_out) / c_water0 if c_water0 else math.nan,
        "density_estimated_g_L": density_temperature,
        "viscosity_Pa_s": viscosity,
        "Re": reynolds,
        "flow_regime": flow_regime,
        "radial_diffusion_time_s": t_rad,
        "t_rad_over_tau": radial_ratio,
        "Taylor_Aris_Dax_m2_s": d_ax,
        "Bo": bo,
        "pfr_advisory": pfr_advisory,
        "requires_pressurization": pressure_flag,
        "numerically_valid": numerical_valid,
        "pressure_valid": pressure_valid,
        "ideal_pfr_supported": pfr_supported,
        "physical_valid": physical_valid,
        "C_EGDA_out_profile_M": c_egda_out,
        "C_EGMA_out_profile_M": c_egma_out,
        "C_EG_out_profile_M": c_eg_out,
        "C_AcOH_out_profile_M": c_acoh_out,
        "C_H2O_out_profile_M": c_water_out,
        "C_OH_out_profile_M": last["C_OH_mol_L"],
    }

    if row["catalyst"] == "NaOH":
        oh_out = last["C_OH_mol_L"]
        additions.update({
            "OH_residual_fraction": oh_out / c_oh0 if c_oh0 else math.nan,
            "OH_utilization_fraction": (c_oh0 - oh_out) / c_oh0 if c_oh0 else math.nan,
            "EGDA_conversion_stoichiometric_ceiling": min(1.0, c_oh0 / c_egda0) if c_egda0 else math.nan,
            "total_cleavage_stoichiometric_fraction": min(1.0, c_oh0 / (2.0 * c_egda0)) if c_egda0 else math.nan,
            "Q1_over_K1_out": math.nan,
            "Q2_over_K2_out": math.nan,
            "X_over_Xeq": math.nan,
        })
    else:
        k_eq1 = float(row.get("K1", math.nan))
        k_eq2 = float(row.get("K2", math.nan))
        qeq1 = c_egma_out * c_acoh_out / (c_egda_out * c_water_out) if c_egda_out > 0.0 and c_water_out > 0.0 else math.inf
        qeq2 = c_eg_out * c_acoh_out / (c_egma_out * c_water_out) if c_egma_out > 0.0 and c_water_out > 0.0 else math.inf
        xeq = float(row.get("X_eq", math.nan))
        additions.update({
            "OH_residual_fraction": math.nan,
            "OH_utilization_fraction": math.nan,
            "EGDA_conversion_stoichiometric_ceiling": math.nan,
            "total_cleavage_stoichiometric_fraction": math.nan,
            "Q1_over_K1_out": qeq1 / k_eq1 if k_eq1 > 0.0 else math.nan,
            "Q2_over_K2_out": qeq2 / k_eq2 if k_eq2 > 0.0 else math.nan,
            "X_over_Xeq": float(row["X_EGDA"]) / xeq if xeq > 0.0 else math.nan,
        })

    result.update(additions)
    result.update(axial_peak(profile, float(config["peak_relative_threshold"])))
    return result


def assign_regime(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    limits = config["regimes"]
    low = float(row["X_EGDA"]) <= float(limits["low_conversion_max"])
    over = float(row["Y_EG"]) > float(row["Y_EGMA"])
    selective = float(row["S_EGMA"]) >= float(limits["selective_min_selectivity"]) and float(row["Y_EGMA"]) >= float(limits["selective_min_yield"])
    peak_inside = bool(row["peak_is_interior"])
    naoh_exhausted = row["catalyst"] == "NaOH" and float(row.get("OH_residual_fraction", math.inf)) <= float(limits["naoh_exhausted_fraction"])
    naoh_limited = row["catalyst"] == "NaOH" and float(row.get("R_OH", math.inf)) < 1.0
    acid_equilibrium = row["catalyst"] == "H2SO4" and max(float(row.get("Q1_over_K1_out", 0.0)), float(row.get("Q2_over_K2_out", 0.0)), float(row.get("X_over_Xeq", 0.0))) >= float(limits["acid_equilibrium_fraction"])
    questionable = not bool(row["physical_valid"])
    if naoh_exhausted:
        primary = "NaOH_exhausted"
    elif acid_equilibrium:
        primary = "acid_equilibrium_limited"
    elif over:
        primary = "overreaction_to_EG"
    elif low:
        primary = "low_conversion"
    elif selective:
        primary = "EGMA_selective"
    elif peak_inside:
        primary = "interior_EGMA_peak"
    else:
        primary = "intermediate"
    return {
        "scenario_id": row["scenario_id"],
        "catalyst": row["catalyst"],
        "geometry": row["geometry"],
        "primary_regime": primary,
        "flag_low_conversion": low,
        "flag_overreaction_to_EG": over,
        "flag_EGMA_selective": selective,
        "flag_interior_EGMA_peak": peak_inside,
        "flag_NaOH_exhausted": naoh_exhausted,
        "flag_NaOH_stoichiometric_limit": naoh_limited,
        "flag_acid_equilibrium_limit": acid_equilibrium,
        "flag_physical_validity_question": questionable,
    }
