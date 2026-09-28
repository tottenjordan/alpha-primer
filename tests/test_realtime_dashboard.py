"""Tests for real-time candidate evaluation telemetry broker and streaming."""

from __future__ import annotations

import queue

import pytest

from alpha_evolve.dashboard.telemetry_broker import (
    LiveTelemetryBroker,
    TelemetryEvent,
    get_global_broker,
)


def test_broker_publish_and_subscribe() -> None:
    """Verify broker publishes events to active subscriber queues."""
    broker = LiveTelemetryBroker()
    subscriber_queue = broker.subscribe()

    test_event: TelemetryEvent = {
        "event_type": "candidate_evaluated",
        "timestamp_utc": "2026-09-28T21:45:00Z",
        "data": {
            "iteration": 1,
            "program_id": "exp/programs/candidate_1",
            "status": "SUCCESS",
            "score": 14.5,
            "cost_reduction_pct": 14.5,
            "fill_rate_pct": 92.1,
            "spoilage_rate_pct": 11.2,
            "is_best": True,
        },
    }

    broker.publish(test_event)

    received = subscriber_queue.get(timeout=1.0)
    assert received["event_type"] == "candidate_evaluated"
    assert received["data"]["iteration"] == 1
    assert received["data"]["is_best"] is True

    broker.unsubscribe(subscriber_queue)
    # Publishing again should not add to unsubscribed queue
    broker.publish(test_event)
    with pytest.raises(queue.Empty):
        subscriber_queue.get(timeout=0.1)


def test_broker_ring_buffer_history() -> None:
    """Verify broker retains recent events in ring buffer for late-joining subscribers."""
    broker = LiveTelemetryBroker(buffer_size=5)

    for i in range(10):
        broker.publish(
            {
                "event_type": "candidate_evaluated",
                "timestamp_utc": f"2026-09-28T21:45:0{i}Z",
                "data": {"iteration": i},
            }
        )

    history = broker.get_history()
    assert len(history) == 5
    assert history[0]["data"]["iteration"] == 5
    assert history[-1]["data"]["iteration"] == 9


def test_broker_clear_and_state_summary() -> None:
    """Verify state summary accurately captures latest experiment progress."""
    broker = LiveTelemetryBroker()
    broker.publish(
        {
            "event_type": "run_started",
            "timestamp_utc": "2026-09-28T21:45:00Z",
            "data": {
                "experiment_name": "Test Experiment",
                "max_programs": 10,
                "primary_metric": "cost_reduction_pct",
            },
        }
    )
    broker.publish(
        {
            "event_type": "candidate_evaluated",
            "timestamp_utc": "2026-09-28T21:45:01Z",
            "data": {
                "iteration": 0,
                "is_baseline": True,
                "score": 0.0,
                "is_best": True,
            },
        }
    )
    broker.publish(
        {
            "event_type": "candidate_evaluated",
            "timestamp_utc": "2026-09-28T21:45:02Z",
            "data": {
                "iteration": 1,
                "is_baseline": False,
                "score": 15.2,
                "is_best": True,
            },
        }
    )

    state = broker.get_current_state()
    assert state["status"] == "RUNNING"
    assert state["experiment_name"] == "Test Experiment"
    assert state["evaluated_count"] == 2
    assert state["best_score"] == 15.2

    broker.publish(
        {
            "event_type": "run_completed",
            "timestamp_utc": "2026-09-28T21:45:03Z",
            "data": {"best_score": 15.2, "evaluated_count": 2},
        }
    )
    state_after = broker.get_current_state()
    assert state_after["status"] == "COMPLETED"


def test_global_broker_singleton() -> None:
    """Verify get_global_broker returns the singleton instance."""
    b1 = get_global_broker()
    b2 = get_global_broker()
    assert b1 is b2


def test_controller_telemetry_streaming() -> None:
    """Verify EvolutionController publishes run_started, candidate_evaluated, and run_completed."""
    from alpha_evolve.client import MockAlphaEvolveClient
    from alpha_evolve.controller import EvolutionController
    from alpha_evolve.models import EvaluationResult, ExperimentConfig, RunSettings

    broker = LiveTelemetryBroker()
    sub_q = broker.subscribe()

    config = ExperimentConfig(
        project_id="test-proj",
        location="global",
        collection="default_collection",
        engine_id="test-engine",
        assistant_id="default_assistant",
        experiment_name="Stream Test",
        user_instructions="Optimize",
        seed_code="def solve(x):\n    # EVOLVE-BLOCK-START\n    return x + 1\n    # EVOLVE-BLOCK-END\n",
        run_settings=RunSettings(max_programs=3, parallel_workers=1, mock_mode=True),
    )

    def mock_evaluator(func: object) -> EvaluationResult:
        return EvaluationResult.success_result(
            scores={"cost_reduction_pct": 12.0},
            insights={"complexity": 5},
            execution_time_s=0.01,
        )

    client = MockAlphaEvolveClient(seed_code=config.seed_code)
    controller = EvolutionController(
        config=config,
        client=client,
        evaluator_fn=mock_evaluator,
        target_function_name="solve",
        primary_metric="cost_reduction_pct",
        telemetry_broker=broker,
    )

    best = controller.run()
    assert best is not None

    events = []
    while not sub_q.empty():
        events.append(sub_q.get_nowait())

    types = [e["event_type"] for e in events]
    assert "run_started" in types
    assert "candidate_evaluated" in types
    assert "run_completed" in types

    # Check candidate event data
    cand_events = [e for e in events if e["event_type"] == "candidate_evaluated"]
    assert len(cand_events) >= 2  # Seed + at least 1 acquired
    assert cand_events[0]["data"]["is_baseline"] is True
    assert cand_events[0]["data"]["iteration"] == 0
    assert "evolve_block" in cand_events[0]["data"]
