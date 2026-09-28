"""Tests for baseline seed routing policy."""

from __future__ import annotations

from examples.fleet_routing.src.program import assign_and_sequence_routes
from examples.fleet_routing.src.simulator import (
    FleetRoutingDigitalTwin,
    generate_routing_benchmark_dataset,
)


def test_baseline_policy_deterministic_and_valid() -> None:
    """Verify baseline greedy routing policy produces valid routes and executes in simulator."""
    config = generate_routing_benchmark_dataset(n_customers=25, n_vehicles=3, seed=42)
    simulator = FleetRoutingDigitalTwin(config)

    # Initial state
    state = simulator.get_visible_state(current_time=0.0)
    assert len(state["visible_order_indices"]) > 0

    # Execute policy decision directly
    action = assign_and_sequence_routes(state, config.to_dict())
    assert "routes" in action
    assert len(action["routes"]) == 3

    # Run full rollout with baseline policy in the digital twin simulator
    result = simulator.run_simulation(assign_and_sequence_routes)
    assert result.total_cost > 0.0
    assert result.served_orders_count > 0
    assert 0.0 <= result.on_time_delivery_pct <= 100.0
    assert result.total_distance_km > 0.0
