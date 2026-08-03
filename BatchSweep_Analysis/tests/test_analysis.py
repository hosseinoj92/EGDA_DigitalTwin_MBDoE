from __future__ import annotations

import csv
import itertools
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from batchsweep_analysis.config import DEFAULT_CONFIG
from batchsweep_analysis.io import discover, write_csv
from batchsweep_analysis.physics import axial_peak, enrich
from batchsweep_analysis.statistics import functional_anova, geometry_collapse, pareto_front


PROFILE_FIELDS = [
    "x_m", "tau_s", "C_EGDA_mol_L", "C_EGMA_mol_L", "C_EG_mol_L",
    "C_AcOH_mol_L", "C_H2O_mol_L", "C_OH_mol_L", "X_EGDA", "Y_EGMA", "Y_EG",
]


def sample_payload(outdir: str = "results") -> dict:
    return {
        "config": {
            "catalyst": "NaOH", "temp_C": 25,
            "stream1": {"Q_mL_min": 1.0, "C_EGDA_M": 0.2, "density_g_L": 1000.0},
            "stream2": {"Q_mL_min": 1.0, "C_cat_M": 0.1, "density_g_L": 1000.0},
            "reactor": {"length_m": 0.06, "diameter_m": 0.004},
            "h_plus_model": "equilibrium", "n_eff_protons": 1.0,
            "ka2_model": "tdep", "activity_model": "dilute",
            "equilibrium": {"reversible": False}, "outdir": outdir,
        },
        "metrics": {
            "tau_s": 22.6194671058, "X_EGDA": 0.4, "Y_EGMA": 0.3,
            "Y_EG": 0.1, "S_EGMA": 0.75, "kappa1_1_s": 0.01,
            "kappa2_1_s": 0.005, "verification_error": 1e-12,
            "invariant_drift": 1e-12,
        },
    }


def sample_profile() -> list[dict[str, float]]:
    return [
        dict(zip(PROFILE_FIELDS, values))
        for values in [
            (0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 55.0, 0.05, 0.0, 0.0, 0.0),
            (0.03, 10.0, 0.07, 0.025, 0.005, 0.035, 54.965, 0.015, 0.3, 0.25, 0.05),
            (0.06, 20.0, 0.06, 0.03, 0.01, 0.05, 54.95, 0.0, 0.4, 0.3, 0.1),
        ]
    ]


def write_scenario(directory: Path, with_profile: bool = True, outdir: str = "results") -> None:
    directory.mkdir(parents=True)
    (directory / "run_config.json").write_text(json.dumps(sample_payload(outdir)), encoding="utf-8")
    if with_profile:
        with (directory / "profiles.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PROFILE_FIELDS)
            writer.writeheader()
            writer.writerows(sample_profile())


class AnalysisTests(unittest.TestCase):
    def test_recursive_discovery_missing_and_duplicate_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_scenario(root / "route" / "one")
            write_scenario(root / "route" / "two", outdir="different")
            write_scenario(root / "route" / "missing", with_profile=False)
            rows, profiles, excluded, duplicates = discover(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(profiles), 2)
            self.assertEqual(len(excluded), 1)
            self.assertEqual(len(duplicates), 2)

    def test_geometry_and_flow_formulas(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_scenario(root / "one")
            rows, profiles, _, _ = discover(root)
            enriched = enrich(rows[0], profiles[rows[0]["scenario_id"]], DEFAULT_CONFIG)
            area = math.pi * 0.004 ** 2 / 4.0
            volume = area * 0.06
            flow = 2.0e-6 / 60.0
            self.assertAlmostEqual(enriched["area_m2"], area)
            self.assertAlmostEqual(enriched["volume_m3"], volume)
            self.assertAlmostEqual(enriched["tau_calculated_s"], volume / flow)
            self.assertAlmostEqual(enriched["C_EGDA_in_M"], 0.1)
            self.assertAlmostEqual(enriched["R_OH"], 0.5)

    def test_axial_peak_metrics(self) -> None:
        profile = sample_profile()
        profile.append({**profile[-1], "x_m": 0.09, "tau_s": 30.0, "C_EGMA_mol_L": 0.02, "Y_EGMA": 0.2})
        peak = axial_peak(profile, 0.95)
        self.assertTrue(peak["peak_is_interior"])
        self.assertFalse(peak["peak_is_at_outlet"])
        self.assertAlmostEqual(peak["x_peak_m"], 0.06)
        self.assertFalse(peak["EGMA_increasing_at_outlet"])

    def test_exact_functional_anova_reconstruction(self) -> None:
        rows = []
        for t, c, e, q in itertools.product((1.0, 2.0), repeat=4):
            y = 3.0 * t + 2.0 * c + t * c + 0.5 * e - q
            rows.append({
                "catalyst": "route", "geometry": "A", "temp_C": t,
                "C_catalyst_feed_M": c, "C_EGDA_feed_M": e,
                "Q_total_mL_min": q, "Y_EGMA": y,
            })
        main, interactions = functional_anova(rows, ["Y_EGMA"])
        components = {}
        for record in main + interactions:
            components[record["factor"]] = record["component_variance"]
            self.assertAlmostEqual(record["reconstruction_residual"], 0.0, places=11)
        total = main[0]["total_variance"]
        self.assertAlmostEqual(sum(components.values()), total, places=11)

    def test_exact_pareto_dominance(self) -> None:
        base = {"catalyst": "route", "geometry": "A", "S_EGMA": 0.8, "temp_C": 50.0, "C_catalyst_feed_M": 0.2, "tau_s": 10.0, "Y_EG": 0.1,
                "C_EGDA_feed_M": 0.2, "Q_total_mL_min": 2.0}
        rows = [
            {**base, "scenario_id": "best", "Y_EGMA": 0.7, "STY_EGMA_mol_Lreactor_h": 2.0},
            {**base, "scenario_id": "dominated", "Y_EGMA": 0.6, "STY_EGMA_mol_Lreactor_h": 1.0},
        ]
        config = {"pareto_objectives": {"maximize": ["Y_EGMA", "S_EGMA", "STY_EGMA_mol_Lreactor_h"], "minimize": ["temp_C", "C_catalyst_feed_M", "tau_s", "Y_EG"]}}
        front = pareto_front(rows, config)
        self.assertEqual([row["scenario_id"] for row in front], ["best"])

    def test_geometry_collapse_pair(self) -> None:
        common = {"catalyst": "route", "temp_C": 25.0, "C_catalyst_feed_M": 0.1, "C_EGDA_feed_M": 0.2, "tau_s": 10.0, "X_EGDA": 0.4, "Y_EGMA": 0.3, "S_EGMA": 0.75}
        rows = [
            {**common, "scenario_id": "a", "geometry": "A", "Da1": 1.0},
            {**common, "scenario_id": "b", "geometry": "B", "Da1": 1.0},
        ]
        pairs = geometry_collapse(rows)
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs[0]["exact_Da1_match"])
        self.assertAlmostEqual(pairs[0]["delta_Y_EGMA_B_minus_A"], 0.0)

    def test_csv_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.csv"
            second = Path(temporary) / "second.csv"
            rows = [{"a": 1, "b": 0.123456789012345}, {"a": 2, "b": True}]
            write_csv(first, rows)
            write_csv(second, rows)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()

