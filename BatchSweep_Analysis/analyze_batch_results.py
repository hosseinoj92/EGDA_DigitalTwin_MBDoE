#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from batchsweep_analysis.config import load_config
from batchsweep_analysis.pipeline import run_analysis


# =============================================================================
# IDE CONFIGURATION -- EDIT THESE PATHS WHEN YOUR DATA LOCATION CHANGES
# =============================================================================
# Common parent folder below which all catalyst, geometry, and scenario result
# folders exist. The analysis searches this folder recursively for
# run_config.json files.
SOURCE_RESULTS_ROOT = Path(
    r"D:\Simulations\EGDA_kinetics\Homogenous_Catalysis\BatchSweep_CPR_big_data"
)

# Separate destination for every generated CSV, JSON, report, and figure.
ANALYSIS_OUTPUT_ROOT = Path(
    r"D:\Simulations\EGDA_kinetics\Homogenous_Catalysis\BatchSweep_CPR_big_Analysis"
)

# Analysis thresholds and objectives. Set this to None to use the defaults
# defined in batchsweep_analysis/config.py instead.
ANALYSIS_CONFIG_PATH: Path | None = Path(__file__).resolve().with_name(
    "analysis_config.json"
)

# Set to False if you ever want to suppress all progress bars.
SHOW_PROGRESS = True
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only, physics-first analysis of saved EDGA batch-sweep scenarios."
    )
    parser.add_argument(
        "--root",
        type=Path,
        help=(
            "Folder containing all batch-result subfolders. It is searched "
            "recursively for run_config.json. If omitted, SOURCE_RESULTS_ROOT "
            "from the IDE configuration block is used."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        help=(
            "Separate folder in which all analysis outputs will be created. "
            "If omitted, ANALYSIS_OUTPUT_ROOT from the IDE configuration block "
            "is used."
        ),
    )
    parser.add_argument("--config", type=Path, help="Optional JSON override of the documented default analysis settings")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.root if args.root is not None else SOURCE_RESULTS_ROOT
    output_root = args.out if args.out is not None else ANALYSIS_OUTPUT_ROOT
    config_path = args.config if args.config is not None else ANALYSIS_CONFIG_PATH

    print(f"Source results root : {source_root.resolve()}")
    print(f"Analysis output root: {output_root.resolve()}")
    print()

    manifest = run_analysis(
        source_root,
        output_root,
        load_config(config_path),
        show_progress=SHOW_PROGRESS,
    )
    print(f"Loaded {manifest['loaded_scenarios']} scenarios.")
    print(f"Loader exclusions: {manifest['excluded_loader_failures']}.")
    print(f"Pareto scenarios: {manifest['pareto_scenarios']}.")
    print(f"Robust-window scenarios: {manifest['robust_window_scenarios']}.")
    print(f"Analysis written to: {output_root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
