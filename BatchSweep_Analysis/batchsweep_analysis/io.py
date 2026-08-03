from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


PROFILE_REQUIRED = {
    "x_m", "tau_s", "C_EGDA_mol_L", "C_EGMA_mol_L", "C_EG_mol_L",
    "C_AcOH_mol_L", "C_H2O_mol_L", "C_OH_mol_L", "X_EGDA",
    "Y_EGMA", "Y_EG",
}


def _number(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def read_profile(path: Path) -> list[dict[str, float]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = PROFILE_REQUIRED - fields
        if missing:
            raise ValueError(f"profiles.csv missing columns: {sorted(missing)}")
        rows = [{key: float(value) for key, value in row.items()} for row in reader]
    if len(rows) < 2:
        raise ValueError("profiles.csv contains fewer than two data rows")
    return rows


def flatten_run_config(payload: dict[str, Any], run_path: Path, root: Path) -> dict[str, Any]:
    cfg = payload["config"]
    metrics = payload["metrics"]
    s1, s2, reactor = cfg["stream1"], cfg["stream2"], cfg["reactor"]
    length = float(reactor["length_m"])
    diameter = float(reactor["diameter_m"])
    if math.isclose(length, 0.060) and math.isclose(diameter, 0.004):
        geometry = "A"
    elif math.isclose(length, 0.200) and math.isclose(diameter, 0.018):
        geometry = "B"
    else:
        geometry = f"L{length:g}_D{diameter:g}"
    relative = run_path.parent.relative_to(root).as_posix()
    scenario_id = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16]
    eq = cfg.get("equilibrium") or {}
    row: dict[str, Any] = {
        "scenario_id": scenario_id,
        "relative_path": relative,
        "run_config_path": str(run_path.resolve()),
        "profiles_path": str((run_path.parent / "profiles.csv").resolve()),
        "catalyst": cfg["catalyst"],
        "geometry": geometry,
        "temp_C": float(cfg["temp_C"]),
        "Q1_mL_min": float(s1["Q_mL_min"]),
        "Q2_mL_min": float(s2["Q_mL_min"]),
        "C_EGDA_feed_M": float(s1["C_EGDA_M"]),
        "C_catalyst_feed_M": float(s2["C_cat_M"]),
        "density1_g_L": float(s1.get("density_g_L", 1000.0)),
        "density2_g_L": float(s2.get("density_g_L", 1000.0)),
        "length_m": length,
        "diameter_m": diameter,
        "h_plus_model": cfg.get("h_plus_model", ""),
        "n_eff_protons": _number(cfg.get("n_eff_protons", "")),
        "ka2_model": cfg.get("ka2_model", ""),
        "activity_model": cfg.get("activity_model", ""),
        "reversible": eq.get("reversible", cfg.get("reversible", "")),
        "K1_ref": _number(eq.get("K1_ref", "")),
        "K2_ref": _number(eq.get("K2_ref", "")),
        "dH1_J_mol": _number(eq.get("dH1_J_mol", eq.get("dH1_J", float(eq["dH1_kJ"]) * 1000.0 if "dH1_kJ" in eq else ""))),
        "dH2_J_mol": _number(eq.get("dH2_J_mol", eq.get("dH2_J", float(eq["dH2_kJ"]) * 1000.0 if "dH2_kJ" in eq else ""))),
    }
    for key, value in metrics.items():
        row[key] = _number(value)
    return row


def configuration_key(row: dict[str, Any]) -> tuple[Any, ...]:
    names = (
        "catalyst", "temp_C", "Q1_mL_min", "Q2_mL_min", "C_EGDA_feed_M",
        "C_catalyst_feed_M", "length_m", "diameter_m", "h_plus_model",
        "n_eff_protons", "ka2_model", "activity_model", "reversible",
    )
    return tuple(row.get(name) for name in names)


def discover(root: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, float]]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    profiles: dict[str, list[dict[str, float]]] = {}
    excluded: list[dict[str, Any]] = []
    seen_dirs: set[Path] = set()
    for run_path in sorted(root.rglob("run_config.json")):
        seen_dirs.add(run_path.parent.resolve())
        try:
            with run_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if "config" not in payload or "metrics" not in payload:
                raise ValueError("run_config.json requires config and metrics objects")
            row = flatten_run_config(payload, run_path, root)
            profile_path = run_path.parent / "profiles.csv"
            if not profile_path.is_file():
                raise FileNotFoundError("profiles.csv is missing")
            profile = read_profile(profile_path)
            rows.append(row)
            profiles[row["scenario_id"]] = profile
        except Exception as exc:
            excluded.append({
                "relative_path": run_path.parent.relative_to(root).as_posix(),
                "reason": type(exc).__name__,
                "details": str(exc),
            })

    candidate_dirs = {p.parent.resolve() for name in ("profiles.csv", "summary.txt") for p in root.rglob(name)}
    for directory in sorted(candidate_dirs - seen_dirs, key=str):
        excluded.append({
            "relative_path": directory.relative_to(root.resolve()).as_posix(),
            "reason": "MissingRunConfig",
            "details": "Scenario-like directory has output files but no run_config.json",
        })

    duplicates: list[dict[str, Any]] = []
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(configuration_key(row), []).append(row)
    for group in buckets.values():
        if len(group) > 1:
            duplicate_group = hashlib.sha1(repr(configuration_key(group[0])).encode("utf-8")).hexdigest()[:12]
            for item in group:
                duplicates.append({
                    "duplicate_group": duplicate_group,
                    "scenario_id": item["scenario_id"],
                    "relative_path": item["relative_path"],
                    "group_size": len(group),
                })
    return rows, profiles, excluded, duplicates


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        observed: set[str] = set()
        for row in materialized:
            for key in row:
                if key not in observed:
                    observed.add(key)
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return format(value, ".12g")
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
