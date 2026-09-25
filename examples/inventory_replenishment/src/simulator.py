"""High-performance vectorized FIFO inventory digital twin simulation engine."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SimulationConfig:
    """Static parameters and cost coefficients for SKU-store nodes."""

    n_skus: int
    max_shelf_life: int
    max_lead_time: int
    lead_time_days: np.ndarray  # shape (N,)
    shelf_life_days: np.ndarray  # shape (N,)
    holding_cost: np.ndarray  # shape (N,)
    spoilage_cost: np.ndarray  # shape (N,)
    stockout_penalty: np.ndarray  # shape (N,)
    order_fixed_cost: np.ndarray  # shape (N,)
    moq: np.ndarray  # shape (N,)
    case_pack_size: np.ndarray  # shape (N,)

    def to_dict(self) -> dict[str, np.ndarray]:
        """Convert configuration to dictionary passed to replenishment policies."""
        return {
            "lead_time_days": self.lead_time_days,
            "shelf_life_days": self.shelf_life_days,
            "holding_cost": self.holding_cost,
            "spoilage_cost": self.spoilage_cost,
            "stockout_penalty": self.stockout_penalty,
            "order_fixed_cost": self.order_fixed_cost,
            "moq": self.moq,
            "case_pack_size": self.case_pack_size,
        }


def generate_benchmark_dataset(
    n_skus: int = 50,
    total_days: int = 90,
    seed: int = 42,
) -> tuple[SimulationConfig, np.ndarray, np.ndarray]:
    """Generate realistic synthetic demand trajectories, promo schedules, and SKU configs.

    Mirrors FreshRetailNet-50K distributions across short-life perishables and ambient SKUs.
    """
    rng = np.random.default_rng(seed)

    # SKU parameters
    # 60% short-life perishables (3-7 days), 40% longer life (10-21 days)
    is_perishable = rng.random(n_skus) < 0.6
    shelf_life = np.where(
        is_perishable,
        rng.integers(3, 8, size=n_skus),
        rng.integers(10, 22, size=n_skus),
    )
    max_shelf_life = int(np.max(shelf_life))

    lead_times = rng.integers(1, 4, size=n_skus)
    max_lead_time = int(np.max(lead_times))

    holding_cost = rng.uniform(0.05, 0.20, size=n_skus)
    spoilage_cost = rng.uniform(2.50, 6.00, size=n_skus)
    stockout_penalty = rng.uniform(3.00, 8.00, size=n_skus)
    order_fixed_cost = np.full(n_skus, 2.0)
    case_pack_size = rng.choice([6, 12, 24], size=n_skus)
    moq = case_pack_size * rng.integers(1, 4, size=n_skus)

    config = SimulationConfig(
        n_skus=n_skus,
        max_shelf_life=max_shelf_life,
        max_lead_time=max_lead_time,
        lead_time_days=lead_times,
        shelf_life_days=shelf_life,
        holding_cost=holding_cost,
        spoilage_cost=spoilage_cost,
        stockout_penalty=stockout_penalty,
        order_fixed_cost=order_fixed_cost,
        moq=moq,
        case_pack_size=case_pack_size,
    )

    # Non-stationary demand trajectories with weekly seasonality & promotions
    base_mean = rng.uniform(8.0, 35.0, size=(n_skus, 1))
    day_indices = np.arange(total_days)
    day_of_week = day_indices % 7
    weekend_multiplier = np.where((day_of_week == 5) | (day_of_week == 6), 1.45, 0.90)

    # Promo schedules (planned discounts in [0.0, 0.35])
    promo_matrix = np.zeros((n_skus, total_days))
    for i in range(n_skus):
        promo_days = rng.choice(total_days, size=rng.integers(4, 12), replace=False)
        promo_matrix[i, promo_days] = rng.uniform(0.15, 0.35, size=len(promo_days))

    promo_demand_lift = 1.0 + 2.5 * promo_matrix
    expected_demand = base_mean * weekend_multiplier[None, :] * promo_demand_lift
    true_demand = rng.poisson(expected_demand).astype(np.float64)

    return config, true_demand, promo_matrix


class InventoryDigitalTwin:
    """Stateful, causal digital twin simulating FIFO perishable replenishment dynamics."""

    def __init__(
        self,
        config: SimulationConfig,
        true_demand: np.ndarray,
        promo_matrix: np.ndarray,
    ) -> None:
        self.config = config
        self.true_demand = true_demand
        self.promo_matrix = promo_matrix
        self.n_skus = config.n_skus
        self.total_days = true_demand.shape[1]

        # Inventory state matrices
        # on_hand_by_age: (N, max_shelf_life) where 0 is oldest (expires today), max-1 is freshest
        self.on_hand_by_age = np.zeros((self.n_skus, config.max_shelf_life), dtype=np.float64)
        # in_transit_pipeline: (N, max_lead_time) where 0 arrives next day (t+1)
        self.in_transit_pipeline = np.zeros((self.n_skus, config.max_lead_time), dtype=np.float64)

        # Causal history recorded over simulation
        self.observed_sales_history = np.zeros((self.n_skus, self.total_days), dtype=np.float64)
        self.stockout_flags_history = np.zeros((self.n_skus, self.total_days), dtype=np.float64)

        # Cost & operational telemetry accumulators
        self.holding_cost_total = 0.0
        self.spoilage_cost_total = 0.0
        self.stockout_penalty_total = 0.0
        self.ordering_cost_total = 0.0
        self.total_demand_units = 0.0
        self.total_fulfilled_units = 0.0
        self.total_spoilage_units = 0.0

        self._warmup(warmup_days=30)

    def _warmup(self, warmup_days: int = 30) -> None:
        """Seed reasonable initial inventory cohorts across warm-up days."""
        for t in range(warmup_days):
            d_t = self.true_demand[:, t]
            # Simple heuristic order during warmup
            warmup_orders = (
                np.ceil(d_t * 1.2 / self.config.case_pack_size) * self.config.case_pack_size
            )
            self._step_internal(warmup_orders, t, record_metrics=False)

    def get_state(self, t: int) -> dict[str, np.ndarray | int]:
        """Return strictly causal state view observable by the policy at morning of day t."""
        # Known promo lookahead for upcoming 7 days
        lookahead_end = min(self.total_days, t + 7)
        promo_slice = self.promo_matrix[:, t:lookahead_end]
        if promo_slice.shape[1] < 7:
            padding = np.zeros((self.n_skus, 7 - promo_slice.shape[1]))
            promo_slice = np.hstack([promo_slice, padding])

        return {
            "on_hand_by_age": self.on_hand_by_age.copy(),
            "in_transit_pipeline": self.in_transit_pipeline.copy(),
            "demand_history": self.observed_sales_history[:, :t].copy(),
            "stockout_history": self.stockout_flags_history[:, :t].copy(),
            "promo_schedule_lookahead": promo_slice,
            "day_of_week": int(t % 7),
        }

    def step(self, orders: np.ndarray, t: int) -> dict[str, float]:
        """Advance the digital twin by 1 business day executing replenishment orders."""
        return self._step_internal(orders, t, record_metrics=True)

    def _step_internal(self, orders: np.ndarray, t: int, record_metrics: bool) -> dict[str, float]:
        # 1. Pipeline arrivals: Orders that completed lead time land today
        arriving_inventory = self.in_transit_pipeline[:, 0].copy()

        # Shift pipeline forward
        self.in_transit_pipeline[:, :-1] = self.in_transit_pipeline[:, 1:]
        self.in_transit_pipeline[:, -1] = 0.0

        # Inject newly placed orders into the pipeline at respective SKU lead times
        safe_orders = np.maximum(0.0, np.nan_to_num(orders, nan=0.0))
        for i in range(self.n_skus):
            lt = int(self.config.lead_time_days[i])
            if lt <= 1:
                # Arrives tomorrow morning
                self.in_transit_pipeline[i, 0] += safe_orders[i]
            else:
                self.in_transit_pipeline[i, min(lt - 1, self.config.max_lead_time - 1)] += (
                    safe_orders[i]
                )

        # Add arriving inventory to the freshest cohort of on-hand inventory
        for i in range(self.n_skus):
            m = int(self.config.shelf_life_days[i])
            freshest_idx = min(m - 1, self.config.max_shelf_life - 1)
            self.on_hand_by_age[i, freshest_idx] += arriving_inventory[i]

        # 2. Demand realization & FIFO depletion
        realized_demand = self.true_demand[:, t].copy()
        fulfilled_sales = np.zeros(self.n_skus, dtype=np.float64)

        # Deplete from oldest (cohort 0) to newest (cohort max-1)
        for age_idx in range(self.config.max_shelf_life):
            available = self.on_hand_by_age[:, age_idx]
            remaining_unmet = realized_demand - fulfilled_sales
            depleted = np.minimum(available, np.maximum(0.0, remaining_unmet))

            self.on_hand_by_age[:, age_idx] -= depleted
            fulfilled_sales += depleted

        # Record observed sales and stockout flags
        self.observed_sales_history[:, t] = fulfilled_sales
        stockout_occurred = fulfilled_sales < realized_demand
        self.stockout_flags_history[:, t] = stockout_occurred.astype(np.float64)

        unmet_units = np.maximum(0.0, realized_demand - fulfilled_sales)

        # 3. Aging & End-of-day Spoilage
        # Inventory at age 0 expires and is discarded
        spoiled_units = self.on_hand_by_age[:, 0].copy()
        # Shift all remaining cohorts 1 day closer to expiration: a -> a - 1
        self.on_hand_by_age[:, :-1] = self.on_hand_by_age[:, 1:]
        self.on_hand_by_age[:, -1] = 0.0

        # Zero out cohorts beyond each SKU's specific shelf life
        for i in range(self.n_skus):
            m = int(self.config.shelf_life_days[i])
            if m < self.config.max_shelf_life:
                self.on_hand_by_age[i, m:] = 0.0

        # Remaining on-hand incurs holding cost
        on_hand_end_of_day = np.sum(self.on_hand_by_age, axis=1)

        # Cost calculations
        daily_holding = float(np.sum(on_hand_end_of_day * self.config.holding_cost))
        daily_spoilage = float(np.sum(spoiled_units * self.config.spoilage_cost))
        daily_stockout = float(np.sum(unmet_units * self.config.stockout_penalty))
        daily_ordering = float(np.sum(np.where(safe_orders > 0, self.config.order_fixed_cost, 0.0)))

        if record_metrics:
            self.holding_cost_total += daily_holding
            self.spoilage_cost_total += daily_spoilage
            self.stockout_penalty_total += daily_stockout
            self.ordering_cost_total += daily_ordering
            self.total_demand_units += float(np.sum(realized_demand))
            self.total_fulfilled_units += float(np.sum(fulfilled_sales))
            self.total_spoilage_units += float(np.sum(spoiled_units))

        return {
            "holding_cost": daily_holding,
            "spoilage_cost": daily_spoilage,
            "stockout_penalty": daily_stockout,
            "ordering_cost": daily_ordering,
        }

    def summary_metrics(self) -> dict[str, float]:
        """Compute aggregated KPIs over the evaluated rollout window."""
        total_cost = (
            self.holding_cost_total
            + self.spoilage_cost_total
            + self.stockout_penalty_total
            + self.ordering_cost_total
        )
        fill_rate = (self.total_fulfilled_units / max(1.0, self.total_demand_units)) * 100.0
        spoilage_rate = (
            self.total_spoilage_units
            / max(1.0, self.total_fulfilled_units + self.total_spoilage_units)
        ) * 100.0

        return {
            "total_cost": total_cost,
            "holding_cost": self.holding_cost_total,
            "spoilage_cost": self.spoilage_cost_total,
            "stockout_penalty": self.stockout_penalty_total,
            "ordering_cost": self.ordering_cost_total,
            "fill_rate_pct": fill_rate,
            "spoilage_rate_pct": spoilage_rate,
            "total_demand_units": self.total_demand_units,
            "total_fulfilled_units": self.total_fulfilled_units,
        }
