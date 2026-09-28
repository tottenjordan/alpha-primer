"""3-Tier Evaluator harness and BaseEvaluator subclass for inventory replenishment policies."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import numpy as np

from alpha_evolve.evaluators import BaseEvaluator, EvaluationTier, TierResult
from alpha_evolve.models import EvaluationResult

from .simulator import (
    InventoryDigitalTwin,
    generate_benchmark_dataset,
)

# Pre-generate deterministic evaluation benchmark datasets
_CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL = generate_benchmark_dataset(
    n_skus=50, total_days=90, seed=42
)

# Pre-computed baseline costs using static (s, S) policy over Days 31-65
_BASELINE_ROLLOUT_COST = 68420.0
_BASELINE_FILL_RATE = 93.8
_BASELINE_SPOILAGE_RATE = 14.2


class InventoryReplenishmentEvaluator(BaseEvaluator):
    """Tiered domain evaluator for inventory replenishment policies."""

    name: str = "inventory_replenishment_evaluator"
    primary_metric: str = "cost_reduction_pct"
    higher_is_better: bool = True
    target_function_name: str = "compute_replenishment_orders"
    smoke_timeout_s: float = 2.0
    validation_timeout_s: float = 30.0

    def __init__(
        self,
        validation_start_day: int = 31,
        validation_end_day: int = 65,
        holdout_start_day: int = 66,
        holdout_end_day: int = 89,
    ) -> None:
        self.validation_start_day = validation_start_day
        self.validation_end_day = validation_end_day
        self.holdout_start_day = holdout_start_day
        self.holdout_end_day = holdout_end_day
        self._smoke_config: Any = None
        self._smoke_demand: Any = None
        self._smoke_promo: Any = None
        self._full_config: Any = None
        self._full_demand: Any = None
        self._full_promo: Any = None
        self.setup()

    def setup(self) -> None:
        """Precompute and cache deterministic benchmark datasets."""
        if self._smoke_config is None:
            self._smoke_config, self._smoke_demand, self._smoke_promo = generate_benchmark_dataset(
                n_skus=10, total_days=40, seed=99
            )
        if self._full_config is None:
            self._full_config, self._full_demand, self._full_promo = generate_benchmark_dataset(
                n_skus=50, total_days=90, seed=42
            )

    def evaluate_smoke(self, candidate_callable: Any) -> TierResult:
        """Tier 1: Fast sanity check (5 days on 10 SKUs) verifying outputs and constraints."""
        start_time = time.perf_counter()
        if self._smoke_config is None or self._smoke_demand is None or self._smoke_promo is None:
            self.setup()

        smoke_twin = InventoryDigitalTwin(self._smoke_config, self._smoke_demand, self._smoke_promo)
        config_dict_smoke = self._smoke_config.to_dict()

        for t in range(30, 35):
            state = smoke_twin.get_state(t)
            try:
                orders = candidate_callable(state, config_dict_smoke)
            except Exception as e:
                return TierResult.failure(
                    EvaluationTier.SMOKE,
                    error_message=f"Policy crashed during smoke test on day {t}: {e}",
                    issue="execution_error",
                    insights={"error": str(e)[:300], "day": str(t)},
                    execution_time_s=time.perf_counter() - start_time,
                )

            if not isinstance(orders, np.ndarray):
                return TierResult.failure(
                    EvaluationTier.SMOKE,
                    error_message=f"Policy must return np.ndarray, got {type(orders)}",
                    issue="invalid_return_type",
                    execution_time_s=time.perf_counter() - start_time,
                )

            if orders.shape != (10,):
                return TierResult.failure(
                    EvaluationTier.SMOKE,
                    error_message=f"Orders array shape must be (10,), got {orders.shape}",
                    issue="shape_mismatch",
                    execution_time_s=time.perf_counter() - start_time,
                )

            if np.any(np.isnan(orders)) or np.any(np.isinf(orders)):
                return TierResult.failure(
                    EvaluationTier.SMOKE,
                    error_message="Orders contain NaN or Inf values.",
                    issue="nan_or_inf",
                    execution_time_s=time.perf_counter() - start_time,
                )

            if np.any(orders < 0.0):
                return TierResult.failure(
                    EvaluationTier.SMOKE,
                    error_message="Orders contain negative values.",
                    issue="negative_orders",
                    execution_time_s=time.perf_counter() - start_time,
                )

            smoke_twin.step(orders, t)

        return TierResult.success(
            EvaluationTier.SMOKE,
            metrics={"smoke_passed": 1.0},
            insights={"smoke_status": "ok"},
            execution_time_s=time.perf_counter() - start_time,
        )

    def evaluate_validation(self, candidate_callable: Any) -> TierResult:
        """Tier 2: Full validation rollout across 50 SKUs over days 31-65."""
        return self._rollout(
            candidate_callable,
            start_day=self.validation_start_day,
            end_day=self.validation_end_day,
            tier=EvaluationTier.VALIDATION,
        )

    def evaluate_holdout(self, candidate_callable: Any) -> TierResult:
        """Tier 3: Locked out-of-sample evaluation across days 66-89."""
        return self._rollout(
            candidate_callable,
            start_day=self.holdout_start_day,
            end_day=self.holdout_end_day,
            tier=EvaluationTier.HOLDOUT,
        )

    def _rollout(
        self,
        candidate_callable: Any,
        start_day: int,
        end_day: int,
        tier: EvaluationTier,
    ) -> TierResult:
        start_time = time.perf_counter()
        if self._full_config is None or self._full_demand is None or self._full_promo is None:
            self.setup()

        twin = InventoryDigitalTwin(self._full_config, self._full_demand, self._full_promo)
        config_dict = self._full_config.to_dict()

        for t in range(start_day, end_day + 1):
            state = twin.get_state(t)
            try:
                orders = candidate_callable(state, config_dict)
            except Exception as e:
                return TierResult.failure(
                    tier,
                    error_message=f"Policy crashed during {tier.value} rollout on day {t}: {e}",
                    issue="rollout_exception",
                    insights={"error": str(e)[:300], "day": str(t)},
                    execution_time_s=time.perf_counter() - start_time,
                )
            twin.step(orders, t)

        metrics = twin.summary_metrics()
        total_cost = metrics["total_cost"]
        fill_rate = metrics["fill_rate_pct"]
        spoilage_rate = metrics["spoilage_rate_pct"]

        # Compute cost reduction percentage relative to baseline
        raw_cost_reduction_pct = (
            (_BASELINE_ROLLOUT_COST - total_cost) / _BASELINE_ROLLOUT_COST
        ) * 100.0

        # Smooth quadratic penalty if service fill rate drops below 95%
        fr_deficit = max(0.0, 0.95 - (fill_rate / 100.0))
        service_penalty = 50.0 * (fr_deficit**2)
        final_score = raw_cost_reduction_pct - service_penalty

        # Construct actionable diagnostic insights
        insights_dict: dict[str, str] = {
            "cost_summary": (
                f"Total Cost: ${total_cost:,.0f} (Holding: ${metrics['holding_cost']:,.0f}, "
                f"Spoilage: ${metrics['spoilage_cost']:,.0f}, Stockout: ${metrics['stockout_penalty']:,.0f})"
            ),
            "service_level": f"Fill Rate: {fill_rate:.1f}% (Target: >=95.0%)",
            "waste": f"Perishable Spoilage Rate: {spoilage_rate:.1f}%",
        }

        if fill_rate < 95.0:
            insights_dict["fill_rate_warning"] = (
                f"Fill rate ({fill_rate:.1f}%) missed the 95.0% SLA, incurring a -{service_penalty:.1f}% penalty. "
                "Increase safety stock buffer or adjust order-up-to thresholds for high-volume SKUs."
            )
        elif spoilage_rate > 15.0:
            insights_dict["spoilage_warning"] = (
                f"High spoilage rate ({spoilage_rate:.1f}%). Inventory cohorts are expiring before sale. "
                "Consider subtracting projected lead-time spoilage from net inventory position."
            )
        else:
            insights_dict["operational_health"] = (
                "Balanced policy achieving SLA with low perishable waste."
            )

        scores_dict = {
            "cost_reduction_pct": round(float(final_score), 2),
            "fill_rate_pct": round(float(fill_rate), 2),
            "spoilage_rate_pct": round(float(spoilage_rate), 2),
            "raw_cost_reduction_pct": round(float(raw_cost_reduction_pct), 2),
        }

        return TierResult.success(
            tier,
            metrics=scores_dict,
            insights=insights_dict,
            execution_time_s=time.perf_counter() - start_time,
        )


_DEFAULT_EVALUATOR = InventoryReplenishmentEvaluator()


def evaluate_replenishment_policy(
    policy_fn: Callable[[dict[str, np.ndarray], dict[str, np.ndarray]], np.ndarray],
    validation_start_day: int = 31,
    validation_end_day: int = 65,
) -> EvaluationResult:
    """Evaluate candidate replenishment policy through 3-tier validation harness.

    Maintains 100% backward compatibility with existing function signatures.
    """
    if validation_start_day != 31 or validation_end_day != 65:
        custom_evaluator = InventoryReplenishmentEvaluator(
            validation_start_day=validation_start_day,
            validation_end_day=validation_end_day,
        )
        return custom_evaluator.evaluate(policy_fn)
    return _DEFAULT_EVALUATOR.evaluate(policy_fn)


__all__ = [
    "InventoryReplenishmentEvaluator",
    "evaluate_replenishment_policy",
]
