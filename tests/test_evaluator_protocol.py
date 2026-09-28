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


def test_base_evaluator_tiered_execution_and_early_exit() -> None:
    from alpha_evolve.evaluators.base import BaseEvaluator

    class MockLinearEvaluator(BaseEvaluator):
        name = "mock_linear"
        primary_metric = "score"
        higher_is_better = True
        target_function_name = "compute"

        def evaluate_smoke(self, candidate_callable: Any) -> TierResult:
            res = candidate_callable(0)
            if res < 0:
                return TierResult.failure(
                    EvaluationTier.SMOKE,
                    "Negative output on zero",
                    issue="neg_val",
                )
            return TierResult.success(EvaluationTier.SMOKE, {"smoke_ok": 1.0})

        def evaluate_validation(self, candidate_callable: Any) -> TierResult:
            score = float(candidate_callable(10))
            return TierResult.success(
                EvaluationTier.VALIDATION,
                metrics={"score": score},
                insights={"perf": f"Generated score {score}"},
            )

    evaluator = MockLinearEvaluator()
    assert isinstance(evaluator, EvaluatorProtocol)

    # Success case
    succ_result = evaluator.evaluate(lambda x: x * 2)
    assert succ_result.status == "SUCCESS"
    assert succ_result.scores.to_dict()["score"] == 20.0
    assert "perf" in succ_result.insights.to_dict()
    assert succ_result.execution_time_s >= 0.0

    # Callable dunder verification
    call_result = evaluator(lambda x: x * 3)
    assert call_result.status == "SUCCESS"
    assert call_result.scores.to_dict()["score"] == 30.0

    # Early exit on smoke failure
    fail_result = evaluator.evaluate(lambda x: -5)
    assert fail_result.status == "FAILED"
    assert fail_result.error_message is not None and "Negative output" in fail_result.error_message
    assert fail_result.insights.to_dict()["issue"] == "neg_val"
    assert fail_result.insights.to_dict()["tier"] == EvaluationTier.SMOKE.value
