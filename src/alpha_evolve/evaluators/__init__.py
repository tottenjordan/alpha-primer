"""Evaluator framework for multi-tiered AlphaEvolve domain optimization."""

from __future__ import annotations

from .base import (
    BaseEvaluator,
    EvaluationTier,
    EvaluatorProtocol,
    TierResult,
    resolve_evaluator,
)

__all__ = [
    "BaseEvaluator",
    "EvaluationTier",
    "EvaluatorProtocol",
    "TierResult",
    "resolve_evaluator",
]
