"""End-to-end integration tests verifying real-time evaluation streaming from runner to server."""

from __future__ import annotations

from pathlib import Path

from examples.inventory_replenishment.src.evaluate import (
    InventoryReplenishmentEvaluator,
)
from server import handle_api_request

from alpha_evolve.dashboard.telemetry_broker import get_global_broker
from alpha_evolve.experiment import AlphaEvolveExperiment

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_realtime_e2e_streaming_pipeline() -> None:
    """Run simulated evolution experiment and verify events stream through broker & API."""
    broker = get_global_broker()
    broker.clear()

    sub_queue = broker.subscribe()

    instructions_path = ROOT_DIR / "examples" / "inventory_replenishment" / "instructions.md"
    seed_program_path = ROOT_DIR / "examples" / "inventory_replenishment" / "src" / "program.py"
    evaluator = InventoryReplenishmentEvaluator()

    experiment = AlphaEvolveExperiment.from_files(
        experiment_name="E2E Realtime Test",
        instructions_path=instructions_path,
        seed_program_path=seed_program_path,
        evaluator=evaluator,
        max_programs=3,
        parallel_workers=1,
        dry_run=True,
        telemetry_broker=broker,
    )

    # Run evolution
    best = experiment.run(output_dir=ROOT_DIR / "artifacts" / "test_run")
    assert best is not None

    # Drain events
    events = []
    while not sub_queue.empty():
        events.append(sub_queue.get_nowait())

    event_types = [e["event_type"] for e in events]
    assert "run_started" in event_types
    assert "candidate_evaluated" in event_types
    assert "run_completed" in event_types

    # Query /api/live/state via server dispatcher
    code, headers, state = handle_api_request("/api/live/state")
    assert code == 200
    assert state["status"] == "COMPLETED"
    assert state["evaluated_count"] >= 3
    assert state["best_score"] > -1e5
    assert state["experiment_name"] == "E2E Realtime Test"

    broker.unsubscribe(sub_queue)
