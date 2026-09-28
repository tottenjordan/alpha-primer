"""Post-evolution route analytics and holdout evaluation reporting."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.table import Table

from .simulator import (
    FleetConfig,
    FleetRoutingDigitalTwin,
    generate_routing_benchmark_dataset,
)

console = Console()


def evaluate_on_locked_holdout(
    baseline_fn: Callable[[dict[str, Any], dict[str, Any]], Any],
    evolved_fn: Callable[[dict[str, Any], dict[str, Any]], Any],
    holdout_config: FleetConfig | None = None,
) -> dict[str, Any]:
    """Execute out-of-sample holdout test comparing baseline vs evolved route dispatch policies."""
    console.print(
        "\n[bold magenta]📊 Evaluating Out-of-Sample Locked Holdout Test (100 Customers, 10 Vehicles)...[/bold magenta]"
    )

    if holdout_config is None:
        holdout_config = generate_routing_benchmark_dataset(
            n_customers=100,
            n_vehicles=10,
            seed=1337,
        )

    # 1. Run Baseline Policy
    twin_base = FleetRoutingDigitalTwin(holdout_config)
    base_res = twin_base.run_simulation(baseline_fn, dispatch_interval_hours=2.0)

    # 2. Run Evolved Policy
    twin_evolved = FleetRoutingDigitalTwin(holdout_config)
    evolved_res = twin_evolved.run_simulation(evolved_fn, dispatch_interval_hours=2.0)

    cost_diff_pct = (
        (base_res.total_cost - evolved_res.total_cost) / max(1.0, base_res.total_cost)
    ) * 100.0
    distance_diff_pct = (
        (base_res.total_distance_km - evolved_res.total_distance_km)
        / max(1.0, base_res.total_distance_km)
    ) * 100.0

    table = Table(title="Out-of-Sample Holdout Performance (100 Customers / Dynamic Traffic)")
    table.add_column("Metric", style="bold")
    table.add_column("Baseline Heuristic", justify="right")
    table.add_column("Evolved Policy", justify="right", style="bold green")
    table.add_column("Delta / Improvement", justify="right", style="cyan")

    table.add_row(
        "Total Fleet Cost",
        f"${base_res.total_cost:,.2f}",
        f"${evolved_res.total_cost:,.2f}",
        f"{cost_diff_pct:+.1f}%",
    )
    table.add_row(
        "Total Distance Traveled",
        f"{base_res.total_distance_km:,.1f} km",
        f"{evolved_res.total_distance_km:,.1f} km",
        f"{distance_diff_pct:+.1f}%",
    )
    table.add_row(
        "On-Time Delivery Rate",
        f"{base_res.on_time_delivery_pct:.1f}%",
        f"{evolved_res.on_time_delivery_pct:.1f}%",
        f"{evolved_res.on_time_delivery_pct - base_res.on_time_delivery_pct:+.1f}% pts",
    )
    table.add_row(
        "Total Tardiness",
        f"{base_res.total_tardiness_hours:,.2f} hrs",
        f"{evolved_res.total_tardiness_hours:,.2f} hrs",
        f"{evolved_res.total_tardiness_hours - base_res.total_tardiness_hours:+,.2f} hrs",
    )
    table.add_row(
        "Fulfilled Orders",
        f"{base_res.served_orders_count}/{holdout_config.n_customers}",
        f"{evolved_res.served_orders_count}/{holdout_config.n_customers}",
        f"{evolved_res.served_orders_count - base_res.served_orders_count:+d}",
    )
    table.add_row(
        "Active Vehicles",
        f"{base_res.vehicles_used}/{holdout_config.n_vehicles}",
        f"{evolved_res.vehicles_used}/{holdout_config.n_vehicles}",
        f"{evolved_res.vehicles_used - base_res.vehicles_used:+d}",
    )

    console.print(table)

    return {
        "baseline": base_res.__dict__,
        "evolved": evolved_res.__dict__,
        "cost_reduction_pct": cost_diff_pct,
        "distance_reduction_pct": distance_diff_pct,
    }


__all__ = ["evaluate_on_locked_holdout"]
