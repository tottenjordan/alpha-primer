"""Tests for tiered VehicleRoutingEvaluator."""

from __future__ import annotations

from examples.fleet_routing.src.evaluate import (
    VehicleRoutingEvaluator,
    evaluate_routing_policy,
)
from examples.fleet_routing.src.program import assign_and_sequence_routes


def test_vehicle_routing_evaluator_tiers_and_success() -> None:
    """Verify VehicleRoutingEvaluator passes smoke, validation, and holdout on baseline."""
    evaluator = VehicleRoutingEvaluator()

    # Test smoke
    smoke_result = evaluator.evaluate_smoke(assign_and_sequence_routes)
    assert smoke_result.passed is True
    assert smoke_result.metrics.get("smoke_passed") == 1.0

    # Test evaluate (orchestrates smoke -> validation)
    eval_result = evaluator.evaluate(assign_and_sequence_routes)
    assert eval_result.status == "SUCCESS"
    scores_dict = eval_result.scores.to_dict()
    assert "score" in scores_dict
    assert "total_cost" in scores_dict
    assert "on_time_delivery_pct" in scores_dict

    # Test holdout tier
    holdout_result = evaluator.evaluate_holdout(assign_and_sequence_routes)
    assert holdout_result.passed is True
    assert "total_cost" in holdout_result.metrics

    # Test functional wrapper
    fn_result = evaluate_routing_policy(assign_and_sequence_routes)
    assert fn_result.status == "SUCCESS"


def test_evaluator_catches_invalid_candidate() -> None:
    """Verify evaluator catches invalid return format or crashing candidate in smoke tier."""
    evaluator = VehicleRoutingEvaluator()

    def bad_policy(state: dict, config: dict) -> dict:
        return {"routes": "invalid"}

    result = evaluator.evaluate(bad_policy)
    assert result.status == "FAILED"
    insights_dict = result.insights.to_dict()
    assert "tier_1_smoke" in str(insights_dict.get("tier", ""))
