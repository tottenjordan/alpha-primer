"""Unit tests for the baseline replenishment program."""

from __future__ import annotations

import numpy as np
from examples.inventory_replenishment.src.program import compute_replenishment_orders
from examples.inventory_replenishment.src.simulator import (
    InventoryDigitalTwin,
    generate_benchmark_dataset,
)


def test_seed_program_generates_valid_orders() -> None:
    config, demand, promo = generate_benchmark_dataset(n_skus=10, total_days=40, seed=42)
    twin = InventoryDigitalTwin(config, demand, promo)

    state = twin.get_state(31)
    config_dict = config.to_dict()

    orders = compute_replenishment_orders(state, config_dict)

    assert isinstance(orders, np.ndarray)
    assert orders.shape == (10,)
    assert np.all(orders >= 0.0)
    assert not np.any(np.isnan(orders))

    # Case pack multiples check
    case_packs = config_dict["case_pack_size"]
    # Non-zero orders should be integer multiples of case pack size
    non_zero = orders > 0
    if np.any(non_zero):
        remainder = orders[non_zero] % case_packs[non_zero]
        assert np.all(remainder == 0.0)
