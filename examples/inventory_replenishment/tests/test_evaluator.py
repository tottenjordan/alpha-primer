"""Unit tests for the 3-tier evaluator harness and InventoryReplenishmentEvaluator."""

from __future__ import annotations

import numpy as np
from examples.inventory_replenishment.src.evaluate import (
    InventoryReplenishmentEvaluator,
    evaluate_replenishment_policy,
)
from examples.inventory_replenishment.src.program import compute_replenishment_orders

from alpha_evolve.evaluators import EvaluatorProtocol


def test_evaluator_scores_seed_program() -> None:
    # Evaluate baseline policy over standard validation window via backward-compatible function
    result = evaluate_replenishment_policy(
        compute_replenishment_orders,
        validation_start_day=31,
        validation_end_day=65,
    )

    assert result.status == "SUCCESS"
    scores = result.scores.to_dict()
    assert "cost_reduction_pct" in scores
    assert "fill_rate_pct" in scores
    assert "spoilage_rate_pct" in scores
    assert scores["fill_rate_pct"] > 85.0
    assert result.execution_time_s > 0.0

    insights = result.insights.to_dict()
    assert "cost_summary" in insights
    assert "service_level" in insights


def test_evaluator_catches_invalid_policy() -> None:
    # Faulty policy returning negative numbers
    def broken_policy(state: dict[str, np.ndarray], config: dict[str, np.ndarray]) -> np.ndarray:
        return np.full(10, -5.0)

    result = evaluate_replenishment_policy(broken_policy)
    assert result.status == "FAILED"
    assert result.scores.to_dict()["score"] == -1e9
    assert "negative_orders" in result.insights.to_dict().get("issue", "")


def test_inventory_replenishment_evaluator_tiered_methods() -> None:
    evaluator = InventoryReplenishmentEvaluator()
    assert isinstance(evaluator, EvaluatorProtocol)
    assert evaluator.target_function_name == "compute_replenishment_orders"
    assert evaluator.primary_metric == "cost_reduction_pct"

    # Tier 1: Smoke
    smoke_res = evaluator.evaluate_smoke(compute_replenishment_orders)
    assert smoke_res.passed
    assert smoke_res.metrics.get("smoke_passed") == 1.0

    # Tier 2: Validation
    val_res = evaluator.evaluate_validation(compute_replenishment_orders)
    assert val_res.passed
    assert "cost_reduction_pct" in val_res.metrics
    assert "fill_rate_pct" in val_res.metrics

    # Tier 3: Holdout
    holdout_res = evaluator.evaluate_holdout(compute_replenishment_orders)
    assert holdout_res.passed
    assert "cost_reduction_pct" in holdout_res.metrics

    # Full tiered pipeline execution
    full_eval = evaluator.evaluate(compute_replenishment_orders)
    assert full_eval.status == "SUCCESS"
    assert full_eval.scores.to_dict()["fill_rate_pct"] > 85.0


def test_inventory_replenishment_evaluator_smoke_failure_cases() -> None:
    evaluator = InventoryReplenishmentEvaluator()

    # Non-ndarray return
    bad_type = evaluator.evaluate(lambda s, c: [1.0] * 10)  # type: ignore[return-value]
    assert bad_type.status == "FAILED"
    assert "invalid_return_type" in bad_type.insights.to_dict().get("issue", "")

    # Shape mismatch
    bad_shape = evaluator.evaluate(lambda s, c: np.ones(5))
    assert bad_shape.status == "FAILED"
    assert "shape_mismatch" in bad_shape.insights.to_dict().get("issue", "")

    # NaN / Inf
    bad_nan = evaluator.evaluate(lambda s, c: np.full(10, np.nan))
    assert bad_nan.status == "FAILED"
    assert "nan_or_inf" in bad_nan.insights.to_dict().get("issue", "")
