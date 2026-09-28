"""Tests for fleet routing digital twin simulator and dataset generation."""

from __future__ import annotations

from typing import Any

import numpy as np

from examples.fleet_routing.src.simulator import (
    FleetRoutingDigitalTwin,
    generate_routing_benchmark_dataset,
)


def test_dataset_generation_shapes_and_reproducibility() -> None:
    """Verify generate_routing_benchmark_dataset produces expected shapes deterministically."""
    config1 = generate_routing_benchmark_dataset(n_customers=50, n_vehicles=5, seed=42)
    config2 = generate_routing_benchmark_dataset(n_customers=50, n_vehicles=5, seed=42)

    assert config1.n_customers == 50
    assert config1.n_vehicles == 5
    assert config1.customer_locations.shape == (50, 2)
    assert config1.demands.shape == (50,)
    assert config1.time_windows.shape == (50, 2)
    assert config1.service_times.shape == (50,)
    assert config1.order_times.shape == (50,)

    # Reproducibility check
    np.testing.assert_allclose(config1.customer_locations, config2.customer_locations)
    np.testing.assert_allclose(config1.time_windows, config2.time_windows)
    np.testing.assert_allclose(config1.demands, config2.demands)


def test_causal_isolation_order_visibility() -> None:
    """Verify simulator enforces strict causal order visibility at time t."""
    config = generate_routing_benchmark_dataset(n_customers=30, n_vehicles=4, seed=123)
    simulator = FleetRoutingDigitalTwin(config)

    # Initial state at t = 0.0
    state_0 = simulator.get_visible_state(current_time=0.0)
    visible_indices_0 = state_0["visible_order_indices"]

    # All visible orders must have order_time <= 0.0
    for idx in visible_indices_0:
        assert config.order_times[idx] <= 0.0

    # Orders with order_time > 0.0 must NOT be in visible_indices_0
    for idx in range(config.n_customers):
        if config.order_times[idx] > 0.0:
            assert idx not in visible_indices_0

    # At later time t = 5.0, more orders become visible
    state_5 = simulator.get_visible_state(current_time=5.0)
    visible_indices_5 = state_5["visible_order_indices"]
    assert len(visible_indices_5) >= len(visible_indices_0)


def test_simulator_rollout_with_dummy_policy() -> None:
    """Verify simulator runs full shift rollout with a simple sequential policy."""
    config = generate_routing_benchmark_dataset(n_customers=20, n_vehicles=3, seed=77)
    simulator = FleetRoutingDigitalTwin(config)

    def dummy_policy(state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
        # Assign first available unassigned order to first vehicle with capacity
        visible = state["visible_order_indices"]
        assignments: list[list[int]] = [[] for _ in range(cfg["n_vehicles"])]
        remaining_cap = state["vehicle_remaining_capacities"].copy()

        for order_idx in visible:
            demand = cfg["demands"][order_idx]
            for v in range(cfg["n_vehicles"]):
                if remaining_cap[v] >= demand:
                    assignments[v].append(order_idx)
                    remaining_cap[v] -= demand
                    break
        return {"routes": assignments}

    result = simulator.run_simulation(dummy_policy)

    assert result.total_distance_km > 0.0
    assert result.total_cost > 0.0
    assert 0.0 <= result.on_time_delivery_pct <= 100.0
    assert result.served_orders_count <= config.n_customers
    assert result.served_orders_count + result.unserved_orders_count == config.n_customers
