#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from batchsweep_analysis.config import load_config
from batchsweep_analysis.pipeline import run_analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only, physics-first analysis of saved EDGA batch-sweep scenarios."
    )
    parser.add_argument("--root", required=True, type=Path, help="BatchSweep result root searched recursively for run_config.json")
    parser.add_argument("--out", required=True, type=Path, help="Separate directory for all analysis outputs")
    parser.add_argument("--config", type=Path, help="Optional JSON override of the documented default analysis settings")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = run_analysis(args.root, args.out, load_config(args.config))
    print(f"Loaded {manifest['loaded_scenarios']} scenarios.")
    print(f"Loader exclusions: {manifest['excluded_loader_failures']}.")
    print(f"Pareto scenarios: {manifest['pareto_scenarios']}.")
    print(f"Robust-window scenarios: {manifest['robust_window_scenarios']}.")
    print(f"Analysis written to: {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

