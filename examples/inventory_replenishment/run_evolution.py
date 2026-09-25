#!/usr/bin/env python3
"""Run end-to-end AlphaEvolve optimization for the Inventory Replenishment Digital Twin.

Usage:
    # Run locally in offline dry-run mode (no GCP credentials needed):
    uv run python examples/inventory_replenishment/run_evolution.py --dry-run --max-programs 5

    # Run with live Gemini Enterprise AlphaEvolve API:
    uv run python examples/inventory_replenishment/run_evolution.py --max-programs 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repository root is on Python search path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alpha_evolve.experiment import AlphaEvolveExperiment
from examples.inventory_replenishment.src.evaluate import evaluate_replenishment_policy
from examples.inventory_replenishment.src.program import compute_replenishment_orders
from examples.inventory_replenishment.src.report import evaluate_on_locked_holdout


def main() -> None:
    parser = argparse.ArgumentParser(description="AlphaEvolve Inventory Replenishment Optimization")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run in offline mock mode without connecting to Google Cloud.",
    )
    parser.add_argument(
        "--max-programs",
        type=int,
        default=10,
        help="Total number of programs to generate and evaluate.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel evaluation workers.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/inventory_replenishment",
        help="Directory to save best candidate code and evaluation reports.",
    )
    args = parser.parse_args()

    example_dir = Path(__file__).resolve().parent
    instructions_path = example_dir / "instructions.md"
    seed_program_path = example_dir / "src" / "program.py"

    experiment = AlphaEvolveExperiment.from_files(
        experiment_name="Inventory Replenishment Digital Twin (BASF Reference)",
        instructions_path=instructions_path,
        seed_program_path=seed_program_path,
        evaluator_fn=evaluate_replenishment_policy,
        target_function_name="compute_replenishment_orders",
        primary_metric="cost_reduction_pct",
        max_programs=args.max_programs,
        parallel_workers=args.workers,
        dry_run=args.dry_run,
    )

    best_candidate = experiment.run(output_dir=args.output_dir)

    # Compile the best candidate code to evaluate on locked holdout
    scope: dict[str, object] = {}
    exec(compile(best_candidate.code, "<best_candidate>", "exec"), scope)
    best_policy_fn = scope["compute_replenishment_orders"]

    # Evaluate on Locked Holdout Days 66-90
    evaluate_on_locked_holdout(
        baseline_fn=compute_replenishment_orders,
        evolved_fn=best_policy_fn,  # type: ignore[arg-type]
        test_start_day=66,
        test_end_day=89,
    )


if __name__ == "__main__":
    main()
