#!/usr/bin/env python3
"""Run end-to-end AlphaEvolve optimization for Fleet Routing & Dispatch.

Usage:
    # Run locally in offline dry-run mode (no GCP credentials needed):
    uv run python examples/fleet_routing/run_evolution.py --dry-run --max-programs 5

    # Run with live Gemini Enterprise AlphaEvolve API:
    uv run python examples/fleet_routing/run_evolution.py --max-programs 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repository root is on Python search path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alpha_evolve.dashboard.telemetry_broker import get_global_broker
from alpha_evolve.experiment import AlphaEvolveExperiment
from alpha_evolve.utils import compile_candidate_callable
from examples.fleet_routing.src.evaluate import (
    VehicleRoutingEvaluator,
)
from examples.fleet_routing.src.program import assign_and_sequence_routes
from examples.fleet_routing.src.report import evaluate_on_locked_holdout


def main() -> None:
    parser = argparse.ArgumentParser(description="AlphaEvolve Fleet Routing Optimization")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run in offline mock mode without connecting to Google Cloud.",
    )
    parser.add_argument(
        "--max-programs",
        type=int,
        default=5,
        help="Total number of programs to generate and evaluate.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of parallel evaluation workers.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/fleet_routing",
        help="Directory to save best candidate code and evaluation reports.",
    )
    parser.add_argument(
        "--stream-to-dashboard",
        action="store_true",
        default=False,
        help="Broadcast candidate evaluations in real-time to the executive dashboard.",
    )
    args = parser.parse_args()

    example_dir = Path(__file__).resolve().parent
    instructions_path = example_dir / "instructions.md"
    seed_program_path = example_dir / "src" / "program.py"

    evaluator = VehicleRoutingEvaluator()
    broker = get_global_broker() if args.stream_to_dashboard else None

    experiment = AlphaEvolveExperiment.from_files(
        experiment_name="Dynamic Fleet Routing & Dispatch Digital Twin",
        instructions_path=instructions_path,
        seed_program_path=seed_program_path,
        evaluator=evaluator,
        max_programs=args.max_programs,
        parallel_workers=args.workers,
        dry_run=args.dry_run,
        telemetry_broker=broker,
    )

    best_candidate = experiment.run(output_dir=args.output_dir)

    best_policy_fn = compile_candidate_callable(
        best_candidate.code,
        "assign_and_sequence_routes",
        filename="<best_candidate>",
    )

    # Evaluate on Locked Holdout (100 Customers / Dynamic Traffic)
    evaluate_on_locked_holdout(
        baseline_fn=assign_and_sequence_routes,
        evolved_fn=best_policy_fn,
    )


if __name__ == "__main__":
    main()
