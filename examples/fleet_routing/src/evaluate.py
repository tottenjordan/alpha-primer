"""3-Tier Vehicle Routing Evaluator subclassing BaseEvaluator."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from alpha_evolve.evaluators import BaseEvaluator, EvaluationTier, TierResult
from alpha_evolve.models import EvaluationResult

from .simulator import (
    FleetConfig,
    FleetRoutingDigitalTwin,
    generate_routing_benchmark_dataset,
)

# Reference baseline cost on validation split (pre-computed with greedy heuristic)
_BASELINE_VALIDATION_COST = 4250.0


class VehicleRoutingEvaluator(BaseEvaluator):
    """Tiered domain evaluator for dynamic vehicle routing and dispatch policies."""

    name: str = "vehicle_routing_evaluator"
    primary_metric: str = "score"
    higher_is_better: bool = True
    target_function_name: str = "assign_and_sequence_routes"
    smoke_timeout_s: float = 2.0
    validation_timeout_s: float = 15.0

    def __init__(
        self,
        smoke_customers: int = 15,
        smoke_vehicles: int = 2,
        val_customers: int = 50,
        val_vehicles: int = 5,
        holdout_customers: int = 100,
        holdout_vehicles: int = 10,
    ) -> None:
        self.smoke_customers = smoke_customers
        self.smoke_vehicles = smoke_vehicles
        self.val_customers = val_customers
        self.val_vehicles = val_vehicles
        self.holdout_customers = holdout_customers
        self.holdout_vehicles = holdout_vehicles

        self._smoke_config: FleetConfig | None = None
        self._val_config: FleetConfig | None = None
        self._holdout_config: FleetConfig | None = None
        self.setup()

    def setup(self) -> None:
        """Precompute and cache deterministic benchmark datasets for all 3 tiers."""
        if self._smoke_config is None:
            self._smoke_config = generate_routing_benchmark_dataset(
                n_customers=self.smoke_customers,
                n_vehicles=self.smoke_vehicles,
                seed=99,
            )
        if self._val_config is None:
            self._val_config = generate_routing_benchmark_dataset(
                n_customers=self.val_customers,
                n_vehicles=self.val_vehicles,
                seed=42,
            )
        if self._holdout_config is None:
            self._holdout_config = generate_routing_benchmark_dataset(
                n_customers=self.holdout_customers,
                n_vehicles=self.holdout_vehicles,
                seed=1337,
            )

    def evaluate_smoke(self, candidate_callable: Any) -> TierResult:
        """Tier 1: Fast sanity check (<100ms, 15 customers, 2 vehicles)."""
        start_time = time.perf_counter()
        if self._smoke_config is None:
            self.setup()

        assert self._smoke_config is not None
        twin = FleetRoutingDigitalTwin(self._smoke_config)
        cfg_dict = self._smoke_config.to_dict()

        # Step 0 check
        state = twin.get_visible_state(current_time=0.0)
        try:
            decision = candidate_callable(state, cfg_dict)
        except Exception as e:
            return TierResult.failure(
                EvaluationTier.SMOKE,
                error_message=f"Candidate crashed on initial state: {e}",
                issue="candidate_exception",
                insights={"error": str(e)[:300]},
                execution_time_s=time.perf_counter() - start_time,
            )

        if not isinstance(decision, dict) or "routes" not in decision:
            return TierResult.failure(
                EvaluationTier.SMOKE,
                error_message="Candidate return value must be dict containing 'routes' key.",
                issue="invalid_return_structure",
                execution_time_s=time.perf_counter() - start_time,
            )

        routes = decision["routes"]
        if not isinstance(routes, (list, dict)):
            return TierResult.failure(
                EvaluationTier.SMOKE,
                error_message=f"'routes' must be list or dict, got {type(routes)}.",
                issue="invalid_routes_type",
                execution_time_s=time.perf_counter() - start_time,
            )

        # Quick rollout on smoke scenario
        try:
            res = twin.run_simulation(candidate_callable, dispatch_interval_hours=4.0)
        except Exception as e:
            return TierResult.failure(
                EvaluationTier.SMOKE,
                error_message=f"Simulation rollout crashed during smoke check: {e}",
                issue="rollout_exception",
                execution_time_s=time.perf_counter() - start_time,
            )

        return TierResult.success(
            EvaluationTier.SMOKE,
            metrics={"smoke_passed": 1.0, "smoke_cost": float(res.total_cost)},
            insights={"smoke_status": "ok", "served_orders": str(res.served_orders_count)},
            execution_time_s=time.perf_counter() - start_time,
        )

    def evaluate_validation(self, candidate_callable: Any) -> TierResult:
        """Tier 2: Full validation rollout (50 customers, 5 vehicles, traffic congestion)."""
        start_time = time.perf_counter()
        if self._val_config is None:
            self.setup()

        assert self._val_config is not None
        twin = FleetRoutingDigitalTwin(self._val_config)

        try:
            res = twin.run_simulation(candidate_callable, dispatch_interval_hours=2.0)
        except Exception as e:
            return TierResult.failure(
                EvaluationTier.VALIDATION,
                error_message=f"Simulation failed during validation: {e}",
                issue="validation_exception",
                execution_time_s=time.perf_counter() - start_time,
            )

        # Fitness scoring:
        # 1. Cost reduction vs baseline
        cost_reduction_pct = (
            (_BASELINE_VALIDATION_COST - res.total_cost) / _BASELINE_VALIDATION_COST
        ) * 100.0

        # 2. SLA penalty if on-time rate drops below 95%
        sla_deficit = max(0.0, 95.0 - res.on_time_delivery_pct)
        sla_penalty = 1.5 * (sla_deficit**1.5)

        # 3. Fulfillment penalty if unserved orders remain
        unserved_penalty = (res.unserved_orders_count / self.val_customers) * 50.0

        fitness_score = cost_reduction_pct - sla_penalty - unserved_penalty

        metrics = {
            "score": round(float(fitness_score), 2),
            "total_cost": round(float(res.total_cost), 2),
            "cost_reduction_pct": round(float(cost_reduction_pct), 2),
            "total_distance_km": round(float(res.total_distance_km), 2),
            "on_time_delivery_pct": round(float(res.on_time_delivery_pct), 2),
            "total_tardiness_hours": round(float(res.total_tardiness_hours), 2),
            "total_wait_hours": round(float(res.total_wait_hours), 2),
            "vehicles_used": float(res.vehicles_used),
            "served_orders_count": float(res.served_orders_count),
            "unserved_orders_count": float(res.unserved_orders_count),
        }

        insights = {
            "cost_breakdown": f"Total Cost: ${res.total_cost:,.2f} | Distance: {res.total_distance_km:.1f} km",
            "service_level": f"On-Time Rate: {res.on_time_delivery_pct:.1f}% (Target: >=95.0%)",
            "fulfillment": f"Served {res.served_orders_count}/{self.val_customers} orders",
            "fleet_utilization": f"Active Vehicles: {res.vehicles_used}/{self.val_vehicles}",
        }

        if res.on_time_delivery_pct < 95.0:
            insights["sla_warning"] = (
                f"SLA missed ({res.on_time_delivery_pct:.1f}%). Incurred -{sla_penalty:.1f} penalty. "
                "Prioritize stops with urgent deadline windows and avoid peak congestion windows."
            )
        if res.unserved_orders_count > 0:
            insights["unserved_warning"] = (
                f"{res.unserved_orders_count} orders unserved. "
                "Ensure available vehicles are loaded up to max capacity each dispatch cycle."
            )

        return TierResult.success(
            EvaluationTier.VALIDATION,
            metrics=metrics,
            insights=insights,
            execution_time_s=time.perf_counter() - start_time,
        )

    def evaluate_holdout(self, candidate_callable: Any) -> TierResult:
        """Tier 3: Locked out-of-sample holdout (100 customers, 10 vehicles, high traffic)."""
        start_time = time.perf_counter()
        if self._holdout_config is None:
            self.setup()

        assert self._holdout_config is not None
        twin = FleetRoutingDigitalTwin(self._holdout_config)

        try:
            res = twin.run_simulation(candidate_callable, dispatch_interval_hours=2.0)
        except Exception as e:
            return TierResult.failure(
                EvaluationTier.HOLDOUT,
                error_message=f"Simulation failed during holdout: {e}",
                issue="holdout_exception",
                execution_time_s=time.perf_counter() - start_time,
            )

        metrics = {
            "total_cost": round(float(res.total_cost), 2),
            "total_distance_km": round(float(res.total_distance_km), 2),
            "on_time_delivery_pct": round(float(res.on_time_delivery_pct), 2),
            "total_tardiness_hours": round(float(res.total_tardiness_hours), 2),
            "vehicles_used": float(res.vehicles_used),
            "served_orders_count": float(res.served_orders_count),
            "unserved_orders_count": float(res.unserved_orders_count),
        }

        insights = {
            "holdout_summary": f"Holdout Cost: ${res.total_cost:,.2f} | On-Time: {res.on_time_delivery_pct:.1f}%",
            "fulfillment": f"Served {res.served_orders_count}/{self.holdout_customers} orders",
        }

        return TierResult.success(
            EvaluationTier.HOLDOUT,
            metrics=metrics,
            insights=insights,
            execution_time_s=time.perf_counter() - start_time,
        )


_DEFAULT_ROUTING_EVALUATOR = VehicleRoutingEvaluator()


def evaluate_routing_policy(
    policy_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> EvaluationResult:
    """Evaluate candidate routing policy through 3-tier validation harness."""
    return _DEFAULT_ROUTING_EVALUATOR.evaluate(policy_fn)


__all__ = [
    "VehicleRoutingEvaluator",
    "evaluate_routing_policy",
]
