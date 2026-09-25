"""Unit tests for dashboard builder, Safe DOM compliance, and trajectory datasets."""

from __future__ import annotations

from pathlib import Path

from alpha_evolve.dashboard.build_dashboard import build_dashboard_html
from alpha_evolve.dashboard.trajectory_generator import generate_inventory_trajectory_dataset

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_trajectory_generator_compiles_data() -> None:
    bundle = generate_inventory_trajectory_dataset()
    assert "platform_title" in bundle
    assert "use_cases" in bundle
    assert "inventory_replenishment" in bundle["use_cases"]

    ir = bundle["use_cases"]["inventory_replenishment"]
    assert len(ir["trajectory_generations"]) == 31
    assert ir["trajectory_generations"][0]["generation"] == 0
    assert ir["trajectory_generations"][30]["generation"] == 30

    # Verify baseline and champion metrics
    assert ir["baseline_summary"]["total_cost"] == 68410.0
    assert ir["champion_summary"]["total_cost"] == 45238.0
    assert ir["champion_summary"]["fill_rate_pct"] == 93.49
    assert ir["champion_summary"]["spoilage_rate_pct"] == 8.45


def test_build_dashboard_html_safe_dom_compliance() -> None:
    html_path = build_dashboard_html()
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    # Enterprise Safe DOM: zero innerHTML
    assert "innerHTML" not in content

    # Uses safe methods
    assert "createElement" in content
    assert "textContent" in content
    assert "replaceChildren" in content

    # Uses high-DPI Retina Canvas 2D
    assert "devicePixelRatio" in content
    assert 'getContext("2d")' in content or "getContext('2d')" in content
    assert "ctx.scale(dpr, dpr)" in content

    # Telemetry data island embedded safely
    assert '<script id="master-trajectory-data" type="application/json">' in content
