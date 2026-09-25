"""Unit tests for the Inventory Digital Twin and FIFO cohort mechanics."""

from __future__ import annotations

import numpy as np
from examples.inventory_replenishment.src.simulator import (
    InventoryDigitalTwin,
    generate_benchmark_dataset,
)


def test_dataset_generation() -> None:
    config, demand, promo = generate_benchmark_dataset(n_skus=10, total_days=50, seed=123)
    assert config.n_skus == 10
    assert demand.shape == (10, 50)
    assert promo.shape == (10, 50)
    assert np.all(demand >= 0)
    assert np.all(config.holding_cost > 0)
    assert np.all(config.spoilage_cost > 0)


def test_digital_twin_fifo_depletion() -> None:
    config, demand, promo = generate_benchmark_dataset(n_skus=5, total_days=40, seed=42)
    twin = InventoryDigitalTwin(config, demand, promo)

    # Initial state verification
    state = twin.get_state(30)
    assert "on_hand_by_age" in state
    assert "in_transit_pipeline" in state
    assert "demand_history" in state
    assert state["demand_history"].shape == (5, 30)

    # Step forward with non-negative orders
    orders = np.full(5, 24.0)
    step_costs = twin.step(orders, 30)

    assert "holding_cost" in step_costs
    assert "spoilage_cost" in step_costs
    assert "stockout_penalty" in step_costs
    assert step_costs["holding_cost"] >= 0.0

    metrics = twin.summary_metrics()
    assert metrics["total_cost"] > 0.0
    assert 0.0 <= metrics["fill_rate_pct"] <= 100.0


def test_causal_isolation() -> None:
    config, demand, promo = generate_benchmark_dataset(n_skus=5, total_days=45, seed=42)
    twin = InventoryDigitalTwin(config, demand, promo)

    state_day_32 = twin.get_state(32)
    # Demand history must only contain days < 32
    assert state_day_32["demand_history"].shape[1] == 32
