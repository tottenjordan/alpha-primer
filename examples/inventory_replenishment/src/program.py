"""Baseline Replenishment Policy for AlphaEvolve Optimization.

Implements a vectorized static (s, S) order-up-to policy with trailing 14-day mean demand
and static z=1.65 safety stock.
"""

from __future__ import annotations

import numpy as np


# EVOLVE-BLOCK-START
def compute_replenishment_orders(
    state: dict[str, np.ndarray],
    config: dict[str, np.ndarray],
) -> np.ndarray:
    """Computes vectorized replenishment order quantities across all SKU-store nodes.

    Args:
        state: Vectorized dictionary for day t containing ONLY causal history (<= t):
            - 'on_hand_by_age': shape (N_skus, max_shelf_life), FIFO inventory cohorts
            - 'in_transit_pipeline': shape (N_skus, max_lead_time), arriving orders
            - 'demand_history': shape (N_skus, lookback_days), past observed sales
            - 'stockout_history': shape (N_skus, lookback_days), past censored stockout flags
            - 'promo_schedule_lookahead': shape (N_skus, 7), known planned discounts
            - 'day_of_week': int (0..6)
        config: Static SKU parameters:
            - 'lead_time_days': shape (N_skus,)
            - 'shelf_life_days': shape (N_skus,)
            - 'holding_cost', 'spoilage_cost', 'stockout_penalty': shape (N_skus,)
            - 'moq', 'case_pack_size': shape (N_skus,)

    Returns:
        1D np.ndarray of non-negative order quantities of shape (N_skus,).
    """
    demand_history = state["demand_history"]
    on_hand_by_age = state["on_hand_by_age"]
    in_transit = state["in_transit_pipeline"]

    lead_times = config["lead_time_days"]
    case_packs = np.maximum(1, config["case_pack_size"])
    moqs = config["moq"]

    # Trailing 14-day mean and standard deviation
    lookback_days = 14
    recent_demand = demand_history[:, -lookback_days:]
    mean_demand = np.mean(recent_demand, axis=1)
    std_demand = np.std(recent_demand, axis=1) + 1e-4

    # Current effective inventory position: on-hand + on-order
    total_on_hand = np.sum(on_hand_by_age, axis=1)
    total_pipeline = np.sum(in_transit, axis=1)
    net_inventory = total_on_hand + total_pipeline

    # Classical (s, S) order-up-to target with static z=1.65 (approx 95% service level)
    z = 1.65
    lead_time_demand = mean_demand * (lead_times + 1)
    safety_stock = z * std_demand * np.sqrt(lead_times + 1)
    order_up_to = lead_time_demand + safety_stock

    # Raw deficit
    deficit = np.maximum(0.0, order_up_to - net_inventory)

    # Apply MOQ constraint
    orders = np.where(deficit >= moqs, deficit, 0.0)

    # Round up to whole case packs
    orders = np.ceil(orders / case_packs) * case_packs

    return orders.astype(np.float64)


# EVOLVE-BLOCK-END
