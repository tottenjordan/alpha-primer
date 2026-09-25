"""Holdout test evaluation and comparative reporting for evolved inventory policies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.table import Table

from .evaluate import _CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL
from .simulator import InventoryDigitalTwin

console = Console()


def evaluate_on_locked_holdout(
    baseline_fn: Callable[[dict[str, Any], dict[str, Any]], Any],
    evolved_fn: Callable[[dict[str, Any], dict[str, Any]], Any],
    test_start_day: int = 66,
    test_end_day: int = 89,
) -> dict[str, Any]:
    """Execute out-of-sample holdout test comparing baseline vs evolved policy over Days 66-90."""
    console.print(
        f"\n[bold magenta]📊 Evaluating Out-of-Sample Locked Holdout Test (Days {test_start_day}–{test_end_day})...[/bold magenta]"
    )

    config_dict = _CONFIG_FULL.to_dict()

    # 1. Run Baseline Policy
    twin_base = InventoryDigitalTwin(_CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL)
    for t in range(test_start_day, test_end_day + 1):
        state = twin_base.get_state(t)
        orders = baseline_fn(state, config_dict)
        twin_base.step(orders, t)
    base_metrics = twin_base.summary_metrics()

    # 2. Run Evolved Policy
    twin_evolved = InventoryDigitalTwin(_CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL)
    for t in range(test_start_day, test_end_day + 1):
        state = twin_evolved.get_state(t)
        orders = evolved_fn(state, config_dict)
        twin_evolved.step(orders, t)
    evolved_metrics = twin_evolved.summary_metrics()

    cost_diff_pct = (
        (base_metrics["total_cost"] - evolved_metrics["total_cost"]) / base_metrics["total_cost"]
    ) * 100.0
    spoilage_diff_pct = (
        (base_metrics["spoilage_cost"] - evolved_metrics["spoilage_cost"])
        / max(1.0, base_metrics["spoilage_cost"])
    ) * 100.0

    table = Table(title="Out-of-Sample Holdout Performance (Days 66–90)")
    table.add_column("Metric", style="bold")
    table.add_column("Baseline (s, S)", justify="right")
    table.add_column("Evolved Policy", justify="right", style="bold green")
    table.add_column("Delta / Improvement", justify="right", style="cyan")

    table.add_row(
        "Total Supply Chain Cost",
        f"${base_metrics['total_cost']:,.0f}",
        f"${evolved_metrics['total_cost']:,.0f}",
        f"{cost_diff_pct:+.1f}%",
    )
    table.add_row(
        "Spoilage Waste Cost",
        f"${base_metrics['spoilage_cost']:,.0f}",
        f"${evolved_metrics['spoilage_cost']:,.0f}",
        f"{spoilage_diff_pct:+.1f}%",
    )
    table.add_row(
        "Stockout Penalty",
        f"${base_metrics['stockout_penalty']:,.0f}",
        f"${evolved_metrics['stockout_penalty']:,.0f}",
        f"${evolved_metrics['stockout_penalty'] - base_metrics['stockout_penalty']:+,.0f}",
    )
    table.add_row(
        "Customer Fill Rate",
        f"{base_metrics['fill_rate_pct']:.1f}%",
        f"{evolved_metrics['fill_rate_pct']:.1f}%",
        f"{evolved_metrics['fill_rate_pct'] - base_metrics['fill_rate_pct']:+.1f}% pts",
    )
    table.add_row(
        "Perishable Spoilage Rate",
        f"{base_metrics['spoilage_rate_pct']:.1f}%",
        f"{evolved_metrics['spoilage_rate_pct']:.1f}%",
        f"{evolved_metrics['spoilage_rate_pct'] - base_metrics['spoilage_rate_pct']:+.1f}% pts",
    )

    console.print(table)

    return {
        "baseline": base_metrics,
        "evolved": evolved_metrics,
        "cost_reduction_pct": cost_diff_pct,
        "spoilage_reduction_pct": spoilage_diff_pct,
    }
