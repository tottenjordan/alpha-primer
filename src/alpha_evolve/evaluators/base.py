"""Base evaluator protocol and tier result schemas for AlphaEvolve."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from alpha_evolve.models import EvaluationResult


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

    @classmethod
    def success(
        cls,
        tier: EvaluationTier,
        metrics: dict[str, float] | None = None,
        insights: dict[str, str] | None = None,
        execution_time_s: float = 0.0,
    ) -> TierResult:
        """Construct a successful tier execution result."""
        return cls(
            tier=tier,
            passed=True,
            metrics=metrics or {},
            insights=insights or {},
            execution_time_s=execution_time_s,
        )

    @classmethod
    def failure(
        cls,
        tier: EvaluationTier,
        error_message: str,
        issue: str | None = None,
        insights: dict[str, str] | None = None,
        execution_time_s: float = 0.0,
    ) -> TierResult:
        """Construct a failed tier execution result with diagnostic metadata."""
        diag = insights.copy() if insights else {}
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
