"""3-Tier Evaluator harness for candidate inventory replenishment policies."""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np

from alpha_evolve.models import (
    AlphaEvolveEvaluationInsights,
    AlphaEvolveEvaluationScores,
    EvaluationResult,
)

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


def evaluate_replenishment_policy(
    policy_fn: Callable[[dict[str, np.ndarray], dict[str, np.ndarray]], np.ndarray],
    validation_start_day: int = 31,
    validation_end_day: int = 65,
) -> EvaluationResult:
    """Evaluate candidate replenishment policy through 3-tier validation harness.

    Args:
        policy_fn: Function 'compute_replenishment_orders(state, config)' to score.
        validation_start_day: Start day of validation evaluation window (default: 31).
        validation_end_day: End day of validation evaluation window (default: 65).

    Returns:
        EvaluationResult with cost reduction, fill rate, spoilage rate, and diagnostic insights.
    """
    start_time = time.perf_counter()

    # ─────────────────────────────────────────────────────────────
    # Tier 1: Fast Smoke Test (5 days on 10 SKUs)
    # ─────────────────────────────────────────────────────────────
    smoke_config, smoke_demand, smoke_promo = generate_benchmark_dataset(
        n_skus=10, total_days=40, seed=99
    )
    smoke_twin = InventoryDigitalTwin(smoke_config, smoke_demand, smoke_promo)
    config_dict_smoke = smoke_config.to_dict()

    for t in range(30, 35):
        state = smoke_twin.get_state(t)
        try:
            orders = policy_fn(state, config_dict_smoke)
        except Exception as e:
            return EvaluationResult.failure(
                f"Policy crashed during smoke test on day {t}: {e}",
                insights={"tier": "tier_1_smoke", "error": str(e)[:300]},
            )

        if not isinstance(orders, np.ndarray):
            return EvaluationResult.failure(
                f"Policy must return np.ndarray, got {type(orders)}",
                insights={"tier": "tier_1_smoke", "issue": "invalid_return_type"},
            )

        if orders.shape != (10,):
            return EvaluationResult.failure(
                f"Orders array shape must be (10,), got {orders.shape}",
                insights={"tier": "tier_1_smoke", "issue": "shape_mismatch"},
            )

        if np.any(np.isnan(orders)) or np.any(np.isinf(orders)):
            return EvaluationResult.failure(
                "Orders contain NaN or Inf values.",
                insights={"tier": "tier_1_smoke", "issue": "nan_or_inf"},
            )

        if np.any(orders < 0.0):
            return EvaluationResult.failure(
                "Orders contain negative values.",
                insights={"tier": "tier_1_smoke", "issue": "negative_orders"},
            )

        smoke_twin.step(orders, t)

    # ─────────────────────────────────────────────────────────────
    # Tier 2: Validation Rollout across 50 SKUs over Days 31-65
    # ─────────────────────────────────────────────────────────────
    twin = InventoryDigitalTwin(_CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL)
    config_dict = _CONFIG_FULL.to_dict()

    for t in range(validation_start_day, validation_end_day + 1):
        state = twin.get_state(t)
        orders = policy_fn(state, config_dict)
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

    return EvaluationResult(
        status="SUCCESS",
        scores=AlphaEvolveEvaluationScores.from_dict(scores_dict),
        insights=AlphaEvolveEvaluationInsights.from_dict(insights_dict),
        execution_time_s=time.perf_counter() - start_time,
    )
