"""Baseline vehicle routing and dispatch program with EVOLVE-BLOCK delimiters."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def _euclidean_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Compute 2D Euclidean distance between two points."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


# EVOLVE-BLOCK-START
def assign_and_sequence_routes(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Assign unserved customer orders to vehicles and sequence delivery stops.

    Parameters
    ----------
    state : dict
        Current snapshot of the delivery network:
        - "current_time": float (current shift time in hours, 0.0 to 12.0)
        - "vehicle_locations": list of (x, y) coordinates for each vehicle
        - "vehicle_remaining_capacities": list of remaining capacity units
        - "vehicle_busy_until": list of available times (hours)
        - "visible_order_indices": list of int indices for orders placed by current_time
        - "served_order_indices": set/list of order indices already fulfilled
        - "order_queue": list of unassigned visible order indices
    config : dict
        Problem specification:
        - "depot_location": (x, y) tuple
        - "customer_locations": list of (x, y) tuples
        - "demands": list of float demand units
        - "time_windows": list of (start_hour, end_hour) tuples
        - "service_times": list of service duration in hours
        - "n_vehicles": int count of fleet vehicles
        - "vehicle_capacity": float max capacity per vehicle

    Returns
    -------
    dict
        Action mapping:
        - "routes": dict mapping int vehicle_idx to list of int customer order indices
          representing the proposed delivery sequence.
    """
    unassigned_orders = list(state.get("visible_order_indices", state.get("order_queue", [])))
    n_vehicles = int(config.get("n_vehicles", 1))
    depot_loc = tuple(config.get("depot_location", (0.0, 0.0)))
    customer_locs = config.get("customer_locations", [])
    demands = config.get("demands", [])
    capacities = list(state.get("vehicle_remaining_capacities", [100.0] * n_vehicles))
    veh_locations = list(
        state.get("vehicle_positions", state.get("vehicle_locations", [depot_loc] * n_vehicles))
    )

    routes: dict[int, list[int]] = {v: [] for v in range(n_vehicles)}

    if not unassigned_orders:
        return {"routes": routes}

    # Baseline Heuristic:
    # Greedy nearest-neighbor clustering with earliest-time-window tie-breaking.
    # Orders are assigned to the closest vehicle with sufficient capacity.
    sorted_orders = sorted(
        unassigned_orders,
        key=lambda idx: (
            config["time_windows"][idx][0] if "time_windows" in config else 0.0,
            _euclidean_distance(depot_loc, customer_locs[idx]),
        ),
    )

    for order_idx in sorted_orders:
        order_demand = float(demands[order_idx]) if order_idx < len(demands) else 1.0
        target_loc = customer_locs[order_idx]

        best_vehicle = None
        min_dist = float("inf")

        for v_idx in range(n_vehicles):
            if capacities[v_idx] >= order_demand:
                curr_loc = routes[v_idx][-1] if routes[v_idx] else veh_locations[v_idx]
                if isinstance(curr_loc, (int, np.integer)):
                    curr_pos = customer_locs[int(curr_loc)]
                else:
                    curr_pos = curr_loc
                dist = _euclidean_distance(curr_pos, target_loc)
                if dist < min_dist:
                    min_dist = dist
                    best_vehicle = v_idx

        if best_vehicle is not None:
            routes[best_vehicle].append(order_idx)
            capacities[best_vehicle] -= order_demand

    return {"routes": routes}


# EVOLVE-BLOCK-END
