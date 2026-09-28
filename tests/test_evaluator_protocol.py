"""Unit tests for EvaluatorProtocol, TierResult, and EvaluationTier."""

from __future__ import annotations

from typing import Any

from alpha_evolve.evaluators.base import (
    EvaluationTier,
    EvaluatorProtocol,
    TierResult,
)


def test_tier_result_success_and_failure() -> None:
    succ = TierResult.success(
        tier=EvaluationTier.SMOKE,
        metrics={"latency_ms": 12.5},
        insights={"health": "passed"},
    )
    assert succ.passed is True
    assert succ.tier == EvaluationTier.SMOKE
    assert succ.metrics["latency_ms"] == 12.5
    assert succ.error_message is None

    fail = TierResult.failure(
        tier=EvaluationTier.SMOKE,
        error_message="Output contains NaNs",
        issue="nan_values",
    )
    assert fail.passed is False
    assert fail.error_message is not None and "NaNs" in fail.error_message
    assert fail.insights.get("issue") == "nan_values"


def test_evaluator_protocol_type_check() -> None:
    class DummyEvaluator:
        name = "dummy"
        primary_metric = "accuracy"
        higher_is_better = True
        target_function_name = "predict"

        def evaluate(self, candidate_callable: Any):
            from alpha_evolve.models import EvaluationResult

            return EvaluationResult()

        def evaluate_holdout(self, candidate_callable: Any):
            from alpha_evolve.models import EvaluationResult

            return EvaluationResult()

    dummy = DummyEvaluator()
    assert isinstance(dummy, EvaluatorProtocol)
