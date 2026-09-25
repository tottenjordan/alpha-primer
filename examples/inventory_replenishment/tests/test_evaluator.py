"""Unit tests for the 3-tier evaluator harness."""

from __future__ import annotations

import numpy as np
from examples.inventory_replenishment.src.evaluate import evaluate_replenishment_policy
from examples.inventory_replenishment.src.program import compute_replenishment_orders


def test_evaluator_scores_seed_program() -> None:
    # Evaluate baseline policy over standard validation window
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
