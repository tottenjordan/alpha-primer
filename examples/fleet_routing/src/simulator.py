"""High-performance spatial vehicle routing & dispatch digital twin simulator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class FleetConfig:
    """Configuration parameters and customer order data for fleet routing."""

    n_customers: int
    n_vehicles: int
    depot_location: np.ndarray  # shape (2,)
    customer_locations: np.ndarray  # shape (N, 2)
    demands: np.ndarray  # shape (N,)
    vehicle_capacity: float
    time_windows: np.ndarray  # shape (N, 2) [earliest, latest] in hours
    service_times: np.ndarray  # shape (N,) in hours
    order_times: np.ndarray  # shape (N,) in hours (time when order becomes visible)
    base_speed_kmh: float = 40.0
    cost_per_km: float = 1.50
    cost_per_late_hour: float = 30.0
    cost_per_idle_hour: float = 8.0
    fixed_vehicle_cost: float = 60.0
    penalty_per_unserved: float = 150.0
    shift_hours: float = 12.0

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary passed to routing policies."""
        return {
            "n_customers": self.n_customers,
            "n_vehicles": self.n_vehicles,
            "depot_location": self.depot_location.copy(),
            "customer_locations": self.customer_locations.copy(),
            "demands": self.demands.copy(),
            "vehicle_capacity": self.vehicle_capacity,
            "time_windows": self.time_windows.copy(),
            "service_times": self.service_times.copy(),
            "order_times": self.order_times.copy(),
            "base_speed_kmh": self.base_speed_kmh,
            "shift_hours": self.shift_hours,
        }


@dataclass
class SimulationResult:
    """Rollout metrics from a simulated fleet routing shift."""

    total_cost: float
    total_distance_km: float
    on_time_delivery_pct: float
    total_tardiness_hours: float
    total_wait_hours: float
    vehicles_used: int
    capacity_utilization_pct: float
    served_orders_count: int
    unserved_orders_count: int

    def to_dict(self) -> dict[str, float]:
        """Convert simulation metrics to dictionary."""
        return {
            "total_cost": self.total_cost,
            "total_distance_km": self.total_distance_km,
            "on_time_delivery_pct": self.on_time_delivery_pct,
            "total_tardiness_hours": self.total_tardiness_hours,
            "total_wait_hours": self.total_wait_hours,
            "vehicles_used": float(self.vehicles_used),
            "capacity_utilization_pct": self.capacity_utilization_pct,
            "served_orders_count": float(self.served_orders_count),
            "unserved_orders_count": float(self.unserved_orders_count),
        }


def generate_routing_benchmark_dataset(
    n_customers: int = 100,
    n_vehicles: int = 10,
    seed: int = 42,
) -> FleetConfig:
    """Generate realistic synthetic customer stops, spatial clusters, and time windows.

    Generates customer clusters around suburban / urban commercial districts with
    stochastic order release times and heterogeneous delivery deadlines.
    """
    rng = np.random.default_rng(seed)

    depot = np.array([50.0, 50.0], dtype=np.float64)

    # 4 Spatial cluster centers in 100x100 km region
    cluster_centers = np.array(
        [
            [25.0, 25.0],
            [25.0, 75.0],
            [75.0, 25.0],
            [75.0, 75.0],
        ],
        dtype=np.float64,
    )

    customer_locations = np.zeros((n_customers, 2), dtype=np.float64)
    demands = np.zeros(n_customers, dtype=np.float64)
    time_windows = np.zeros((n_customers, 2), dtype=np.float64)
    service_times = np.zeros(n_customers, dtype=np.float64)
    order_times = np.zeros(n_customers, dtype=np.float64)

    for i in range(n_customers):
        # 80% assigned to a cluster, 20% uniform random outlier
        if rng.random() < 0.8:
            center = cluster_centers[rng.integers(0, len(cluster_centers))]
            loc = center + rng.normal(0.0, 7.5, size=2)
        else:
            loc = rng.uniform(5.0, 95.0, size=2)

        customer_locations[i] = np.clip(loc, 0.0, 100.0)

        # Demand: 1 to 8 units (e.g. parcels / cartons)
        demands[i] = float(rng.integers(1, 9))

        # Order time: 60% placed pre-shift (t = 0.0), 40% dynamic in first 6 hours
        o_time = 0.0 if rng.random() < 0.6 else float(np.round(rng.uniform(0.5, 6.0), 2))
        order_times[i] = o_time

        # Time windows: delivery window starts after order time
        earliest_start = float(
            np.round(o_time + rng.uniform(0.5, 3.0), 2)
        )
        earliest_start = min(earliest_start, 9.0)
        window_width = float(np.round(rng.uniform(2.0, 4.5), 2))
        latest_deadline = min(12.0, earliest_start + window_width)
        time_windows[i] = [earliest_start, latest_deadline]

        # Service duration: 6 to 18 minutes (0.1 to 0.3 hours)
        service_times[i] = float(np.round(rng.uniform(0.1, 0.3), 2))

    vehicle_capacity = 45.0  # max parcel capacity per van

    return FleetConfig(
        n_customers=n_customers,
        n_vehicles=n_vehicles,
        depot_location=depot,
        customer_locations=customer_locations,
        demands=demands,
        vehicle_capacity=vehicle_capacity,
        time_windows=time_windows,
        service_times=service_times,
        order_times=order_times,
    )


class FleetRoutingDigitalTwin:
    """Digital twin simulation engine for dynamic vehicle routing and dispatching."""

    def __init__(self, config: FleetConfig) -> None:
        self.config = config

    def traffic_congestion_factor(self, current_time: float) -> float:
        """Compute non-linear time-of-day traffic congestion multiplier.

        Simulates morning (t=2..4) and evening (t=8..10) rush hours where travel times
        inflate by up to 50%.
        """
        # Peak congestion around t=3.0 (morning) and t=9.0 (evening)
        norm_t = (current_time % 12.0) / 12.0
        wave = np.sin(2.0 * np.pi * norm_t) ** 2
        return 1.0 + 0.5 * float(wave)

    def calculate_distance(self, loc_a: np.ndarray, loc_b: np.ndarray) -> float:
        """Euclidean distance in kilometers."""
        return float(np.linalg.norm(loc_a - loc_b))

    def get_visible_state(
        self,
        current_time: float,
        served_mask: np.ndarray | None = None,
        vehicle_positions: np.ndarray | None = None,
        vehicle_capacities: np.ndarray | None = None,
    ) -> dict[str, Any]:
        """Extract causally isolated state visible to the dispatch policy at current_time.

        Orders with order_time > current_time are completely hidden.
        """
        if served_mask is None:
            served_mask = np.zeros(self.config.n_customers, dtype=bool)

        visible_mask = (self.config.order_times <= current_time) & (~served_mask)
        visible_indices = np.where(visible_mask)[0]

        if vehicle_positions is None:
            vehicle_positions = np.tile(
                self.config.depot_location, (self.config.n_vehicles, 1)
            )

        if vehicle_capacities is None:
            vehicle_capacities = np.full(
                self.config.n_vehicles, self.config.vehicle_capacity, dtype=np.float64
            )

        return {
            "current_time": current_time,
            "visible_order_indices": visible_indices,
            "traffic_factor": self.traffic_congestion_factor(current_time),
            "vehicle_positions": vehicle_positions.copy(),
            "vehicle_remaining_capacities": vehicle_capacities.copy(),
            "customer_locations": self.config.customer_locations[visible_indices],
            "demands": self.config.demands[visible_indices],
            "time_windows": self.config.time_windows[visible_indices],
            "service_times": self.config.service_times[visible_indices],
            "depot_location": self.config.depot_location.copy(),
        }

    def run_simulation(
        self,
        policy_callable: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        dispatch_interval_hours: float = 2.0,
    ) -> SimulationResult:
        """Execute a full 12-hour operational day simulation with periodic dispatch rounds."""
        cfg_dict = self.config.to_dict()

        served_mask = np.zeros(self.config.n_customers, dtype=bool)
        tardiness_hours = np.zeros(self.config.n_customers, dtype=np.float64)
        wait_hours = np.zeros(self.config.n_customers, dtype=np.float64)

        vehicle_locations = np.tile(
            self.config.depot_location, (self.config.n_vehicles, 1)
        )
        vehicle_available_times = np.zeros(self.config.n_vehicles, dtype=np.float64)
        vehicle_odometers = np.zeros(self.config.n_vehicles, dtype=np.float64)
        vehicle_used = np.zeros(self.config.n_vehicles, dtype=bool)
        vehicle_payload_delivered = np.zeros(self.config.n_vehicles, dtype=np.float64)

        current_time = 0.0
        while current_time < self.config.shift_hours:
            state = self.get_visible_state(
                current_time=current_time,
                served_mask=served_mask,
                vehicle_positions=vehicle_locations,
            )

            # Check if there are orders to assign
            if len(state["visible_order_indices"]) > 0:
                try:
                    decision = policy_callable(state, cfg_dict)
                    routes = decision.get("routes", [])
                except Exception:
                    routes = []

                # Execute planned route sequences for each vehicle
                for v_idx, route in enumerate(routes):
                    if v_idx >= self.config.n_vehicles or not route:
                        continue

                    # Filter route to unserved visible stops only
                    valid_stops = [
                        idx
                        for idx in route
                        if idx in state["visible_order_indices"]
                        and not served_mask[idx]
                    ]

                    # Verify capacity constraint
                    total_demand = sum(self.config.demands[s] for s in valid_stops)
                    if total_demand > self.config.vehicle_capacity:
                        # Truncate route to respect capacity
                        accum_d = 0.0
                        capped_stops = []
                        for s in valid_stops:
                            if accum_d + self.config.demands[s] <= self.config.vehicle_capacity:
                                capped_stops.append(s)
                                accum_d += self.config.demands[s]
                            else:
                                break
                        valid_stops = capped_stops

                    if not valid_stops:
                        continue

                    vehicle_used[v_idx] = True
                    v_time = max(current_time, vehicle_available_times[v_idx])
                    curr_pos = vehicle_locations[v_idx]

                    for stop in valid_stops:
                        stop_loc = self.config.customer_locations[stop]
                        dist = self.calculate_distance(curr_pos, stop_loc)
                        vehicle_odometers[v_idx] += dist

                        # Travel time accounting for traffic
                        traffic = self.traffic_congestion_factor(v_time)
                        effective_speed = max(10.0, self.config.base_speed_kmh / traffic)
                        travel_time = dist / effective_speed
                        v_time += travel_time

                        # Time window check
                        earliest, deadline = self.config.time_windows[stop]
                        if v_time < earliest:
                            # Arrived early: idle wait
                            idle_time = earliest - v_time
                            wait_hours[stop] = idle_time
                            v_time = earliest
                        elif v_time > deadline:
                            # Arrived late: tardiness penalty
                            tardiness_hours[stop] = v_time - deadline

                        # Service duration
                        v_time += self.config.service_times[stop]
                        served_mask[stop] = True
                        vehicle_payload_delivered[v_idx] += self.config.demands[stop]
                        curr_pos = stop_loc

                    # Return to depot
                    return_dist = self.calculate_distance(
                        curr_pos, self.config.depot_location
                    )
                    vehicle_odometers[v_idx] += return_dist
                    traffic = self.traffic_congestion_factor(v_time)
                    return_time = return_dist / max(
                        10.0, self.config.base_speed_kmh / traffic
                    )
                    v_time += return_time

                    # Update vehicle state for next round
                    vehicle_locations[v_idx] = self.config.depot_location.copy()
                    vehicle_available_times[v_idx] = v_time

            current_time += dispatch_interval_hours

        # Compute summary metrics
        total_distance = float(np.sum(vehicle_odometers))
        total_tardiness = float(np.sum(tardiness_hours))
        total_wait = float(np.sum(wait_hours))
        active_vehicles = int(np.sum(vehicle_used))
        served_count = int(np.sum(served_mask))
        unserved_count = self.config.n_customers - served_count

        total_cost = (
            total_distance * self.config.cost_per_km
            + total_tardiness * self.config.cost_per_late_hour
            + total_wait * self.config.cost_per_idle_hour
            + active_vehicles * self.config.fixed_vehicle_cost
            + unserved_count * self.config.penalty_per_unserved
        )

        on_time_count = sum(
            1 for i in range(self.config.n_customers) if served_mask[i] and tardiness_hours[i] <= 0.05
        )
        on_time_pct = (
            (on_time_count / served_count * 100.0) if served_count > 0 else 0.0
        )

        max_capacity_pool = (
            active_vehicles * self.config.vehicle_capacity
            if active_vehicles > 0
            else 1.0
        )
        utilization_pct = min(
            100.0,
            (float(np.sum(vehicle_payload_delivered)) / max_capacity_pool) * 100.0,
        )

        return SimulationResult(
            total_cost=round(total_cost, 2),
            total_distance_km=round(total_distance, 2),
            on_time_delivery_pct=round(on_time_pct, 2),
            total_tardiness_hours=round(total_tardiness, 2),
            total_wait_hours=round(total_wait, 2),
            vehicles_used=active_vehicles,
            capacity_utilization_pct=round(utilization_pct, 2),
            served_orders_count=served_count,
            unserved_orders_count=unserved_count,
        )
