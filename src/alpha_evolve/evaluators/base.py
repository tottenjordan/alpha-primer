"""Base evaluator protocol and tier result schemas for AlphaEvolve."""

from __future__ import annotations

import abc
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from alpha_evolve.models import (
    AlphaEvolveEvaluationInsights,
    AlphaEvolveEvaluationScores,
    EvaluationResult,
)


class EvaluationTier(StrEnum):
    """Execution tiers for AlphaEvolve evaluation."""

    SYNTAX = "tier_0_syntax"
    SMOKE = "tier_1_smoke"
    VALIDATION = "tier_2_validation"
    HOLDOUT = "tier_3_holdout"


class TierResult(BaseModel):
    """Result of an individual evaluation tier."""

    tier: EvaluationTier
    passed: bool
    metrics: dict[str, float] = Field(default_factory=dict)
    insights: dict[str, str] = Field(default_factory=dict)
    error_message: str | None = None
    execution_time_s: float = 0.0

    @field_validator("insights", mode="before")
    @classmethod
    def _coerce_insights(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items()}
        return v

    @classmethod
    def success(
        cls,
        tier: EvaluationTier,
        metrics: dict[str, float] | None = None,
        insights: dict[str, Any] | None = None,
        execution_time_s: float = 0.0,
    ) -> TierResult:
        """Construct a successful tier execution result."""
        str_insights = {str(k): str(v) for k, v in (insights or {}).items()}
        return cls(
            tier=tier,
            passed=True,
            metrics=metrics or {},
            insights=str_insights,
            execution_time_s=execution_time_s,
        )

    @classmethod
    def failure(
        cls,
        tier: EvaluationTier,
        error_message: str,
        issue: str | None = None,
        insights: dict[str, Any] | None = None,
        execution_time_s: float = 0.0,
    ) -> TierResult:
        """Construct a failed tier execution result with diagnostic metadata."""
        diag = {str(k): str(v) for k, v in (insights or {}).items()}
        if issue:
            diag["issue"] = issue
        return cls(
            tier=tier,
            passed=False,
            error_message=error_message,
            insights=diag,
            execution_time_s=execution_time_s,
        )


@runtime_checkable
class EvaluatorProtocol(Protocol):
    """Protocol defining the interface for domain evaluators."""

    name: str
    primary_metric: str
    higher_is_better: bool
    target_function_name: str

    def evaluate(self, candidate_callable: Any) -> EvaluationResult: ...

    def evaluate_holdout(self, candidate_callable: Any) -> EvaluationResult: ...


class BaseEvaluator(abc.ABC):
    """Abstract base class orchestrating tiered candidate evaluation."""

    name: str = "base_evaluator"
    primary_metric: str = "score"
    higher_is_better: bool = True
    target_function_name: str = "compute"
    smoke_timeout_s: float = 2.0
    validation_timeout_s: float = 30.0

    def setup(self) -> None:
        """Hook called before evaluation runs to precompute constants or cache datasets."""
        return None

    def teardown(self) -> None:
        """Hook called to release resources after evolution completes."""
        return None

    @abc.abstractmethod
    def evaluate_smoke(self, candidate_callable: Any) -> TierResult:
        """Tier 1: Fast sanity check (<100ms) verifying types, shapes, and constraints."""
        raise NotImplementedError

    @abc.abstractmethod
    def evaluate_validation(self, candidate_callable: Any) -> TierResult:
        """Tier 2: Full validation rollout computing primary fitness and diagnostic insights."""
        raise NotImplementedError

    def evaluate_holdout(self, candidate_callable: Any) -> TierResult:
        """Tier 3: Locked out-of-sample evaluation to verify generalization without overfitting."""
        return self.evaluate_validation(candidate_callable)

    def evaluate(self, candidate_callable: Any) -> EvaluationResult:
        """Orchestrate tiered execution: Tier 1 smoke test -> Tier 2 validation rollout."""
        start_time = time.perf_counter()

        # Tier 1: Smoke Check
        smoke_result = self.evaluate_smoke(candidate_callable)
        if not smoke_result.passed:
            diag = smoke_result.insights.copy()
            diag["tier"] = EvaluationTier.SMOKE.value
            return EvaluationResult.failure(
                error_message=smoke_result.error_message or "Smoke test failed.",
                insights=diag,
            )

        # Tier 2: Validation Rollout
        validation_result = self.evaluate_validation(candidate_callable)
        elapsed = time.perf_counter() - start_time

        if not validation_result.passed:
            diag = validation_result.insights.copy()
            diag["tier"] = EvaluationTier.VALIDATION.value
            return EvaluationResult.failure(
                error_message=validation_result.error_message or "Validation rollout failed.",
                insights=diag,
            )

        return EvaluationResult(
            status="SUCCESS",
            scores=AlphaEvolveEvaluationScores.from_dict(validation_result.metrics),
            insights=AlphaEvolveEvaluationInsights.from_dict(validation_result.insights),
            execution_time_s=elapsed,
        )

    def __call__(self, candidate_callable: Any) -> EvaluationResult:
        """Allow evaluator instances to be passed directly as callables."""
        return self.evaluate(candidate_callable)


def resolve_evaluator(
    evaluator: BaseEvaluator | Callable[[Any], EvaluationResult] | None = None,
    evaluator_fn: Callable[[Any], EvaluationResult] | None = None,
    target_function_name: str | None = None,
    primary_metric: str | None = None,
) -> tuple[
    BaseEvaluator | Callable[[Any], EvaluationResult],
    Callable[[Any], EvaluationResult],
    str,
    str,
    bool,
]:
    """Normalize an evaluator or legacy callable into (evaluator, evaluator_fn, target_fn, metric, higher_is_better)."""
    resolved = evaluator if evaluator is not None else evaluator_fn
    if resolved is None:
        raise ValueError("Either 'evaluator' or 'evaluator_fn' must be provided.")

    if isinstance(resolved, BaseEvaluator):
        return (
            resolved,
            resolved.evaluate,
            target_function_name or resolved.target_function_name,
            primary_metric or resolved.primary_metric,
            resolved.higher_is_better,
        )

    return (
        resolved,
        resolved,
        target_function_name or "compute",
        primary_metric or "cost_reduction_pct",
        bool(getattr(resolved, "higher_is_better", True)),
    )


__all__ = [
    "BaseEvaluator",
    "EvaluationTier",
    "EvaluatorProtocol",
    "TierResult",
    "resolve_evaluator",
]
