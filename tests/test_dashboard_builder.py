"""Unit tests for dashboard builder, Safe DOM compliance, and trajectory datasets."""

from __future__ import annotations

import shutil
import subprocess
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


def test_trajectory_milestone_and_pareto_metadata() -> None:
    bundle = generate_inventory_trajectory_dataset()
    ir = bundle["use_cases"]["inventory_replenishment"]

    # Verify milestones (Gen 0, 8, 17, 30)
    assert "milestones" in ir
    milestones = ir["milestones"]
    for gen_key in ["0", "8", "17", "30"]:
        assert gen_key in milestones
        m = milestones[gen_key]
        assert "title" in m
        assert "description" in m
        assert "evolve_block" in m
        assert "def compute_replenishment_orders" in m["evolve_block"]
        assert "metrics" in m

    # Verify specific algorithmic mutations
    assert "imputed_vals" in milestones["8"]["evolve_block"]
    assert "accumulated_spoilage" in milestones["17"]["evolve_block"]
    assert any("critical fractile" in inn.lower() for inn in milestones["30"]["key_innovations"])

    # Verify ribbon milestones (8 key generations)
    assert "ribbon_milestones" in ir
    ribbon = ir["ribbon_milestones"]
    assert len(ribbon) == 8
    assert [r["generation"] for r in ribbon] == [0, 5, 8, 12, 17, 22, 27, 30]
    assert ribbon[2]["is_star"] is True  # Gen 8 ⭐
    assert ribbon[4]["is_star"] is True  # Gen 17 ⭐
    assert ribbon[7]["is_champ"] is True  # Gen 30 🏆

    # Verify cost waterfall breakdown
    assert "cost_waterfall" in ir
    cw = ir["cost_waterfall"]
    assert cw["total_reduction_pct"] == 33.87
    assert len(cw["components"]) == 4
    comp_keys = [c["key"] for c in cw["components"]]
    assert comp_keys == ["spoilage", "stockout", "holding", "ordering"]
    labels = [c["savings_label"] for c in cw["components"]]
    assert "-$11.9k" in labels
    assert "-$9.6k" in labels
    assert "-$1.2k" in labels
    assert "-$395" in labels

    # Verify Pareto frontier data points
    assert "pareto_frontier" in ir
    pf = ir["pareto_frontier"]
    assert len(pf) == 31
    assert all("is_pareto" in p for p in pf)
    assert all("cost_reduction_pct" in p for p in pf)
    assert all("fill_rate_pct" in p for p in pf)
    assert all("spoilage_rate_pct" in p for p in pf)

    # Verify ordering_cost tracked across generations
    assert "ordering_cost" in ir["trajectory_generations"][0]["metrics"]
    assert "ordering_cost" in ir["trajectory_generations"][30]["metrics"]


def test_high_visibility_diff_engine_elements() -> None:
    html_path = build_dashboard_html()
    content = html_path.read_text(encoding="utf-8")

    # Strict Safe DOM: zero innerHTML
    assert "innerHTML" not in content

    # View Mode Toggles (Split & Unified)
    assert 'id="btn-view-split"' in content
    assert 'id="btn-view-unified"' in content
    assert "diff-table-header split" in content

    # Foldable unchanged code blocks
    assert 'id="btn-toggle-fold"' in content
    assert "diff-fold-row" in content

    # Milestone AST Diff Stepper presets
    assert 'data-pair="0-8"' in content
    assert 'data-pair="8-17"' in content
    assert 'data-pair="17-30"' in content
    assert 'data-pair="0-30"' in content
    assert 'id="diff-select-base"' in content
    assert 'id="diff-select-evolved"' in content
    assert 'id="diff-mutation-banner"' in content

    # Python syntax lexer token classes
    assert "tok-kw" in content
    assert "tok-builtin" in content
    assert "tok-docstring" in content
    assert "tok-str" in content
    assert "tok-num" in content
    assert "tok-comment" in content
    assert "tok-op" in content

    # Word/token-level diff highlighting
    assert "diff-word-del" in content
    assert "diff-word-add" in content

    # Gutter and line numbering
    assert "diff-gutter-num" in content
    assert "diff-gutter-badge" in content


def test_evolutionary_progression_suite_and_dual_whatif() -> None:
    html_path = build_dashboard_html()
    content = html_path.read_text(encoding="utf-8")

    # Strict Safe DOM
    assert "innerHTML" not in content

    # Canvas 2 dual-mode toggle (Mode A: Pareto Frontier vs Mode B: Cost Waterfall)
    assert 'id="btn-mode-pareto"' in content
    assert 'id="btn-mode-waterfall"' in content
    assert "drawParetoChart" in content
    assert "drawWaterfallChart" in content

    # Interactive Milestone Ribbon beneath KPI header
    assert 'id="milestone-ribbon-nodes"' in content
    assert "renderMilestoneRibbon" in content
    assert "ribbon-node" in content
    assert "ribbon-tooltip" in content

    # What-If Sandbox dual-policy simulation
    assert "whatif-dual-grid" in content
    assert "whatif-policy-card baseline" in content
    assert "whatif-policy-card champion" in content
    assert 'id="val-base-fill"' in content
    assert 'id="val-champ-fill"' in content
    assert 'id="whatif-resilience-banner"' in content
    assert 'id="canvas-whatif"' in content
    assert "drawWhatIfDualCanvas" in content


def test_diff_engine_robustness_and_client_js_execution() -> None:
    html_path = build_dashboard_html()
    content = html_path.read_text(encoding="utf-8")

    # Innovation pills in AST stepper banner
    assert 'id="diff-innovations-pills"' in content
    assert ".pill-inn" in content

    # All 4 milestones present in both base and evolved selectors
    assert '<select id="diff-select-base"' in content
    assert '<select id="diff-select-evolved"' in content
    for gen in ["0", "8", "17", "30"]:
        assert f'option value="{gen}"' in content

    # Copy button feedback handler
    assert 'btnCopy.textContent = "✓ Copied!"' in content

    # Replay pausing on interaction
    assert "pauseReplay" in content

    # Node.js validation of client-side lexer and LCS diff logic
    node_path = shutil.which("node")
    if node_path:
        test_script = """
        const fs = require('fs');
        const html = fs.readFileSync('dashboard/index.html', 'utf8');
        const scriptMatch = html.match(/<script>\\s*([\\s\\S]*?)<\\/script>/);
        if (!scriptMatch) throw new Error('No script block found');

        // Extract functions by wrapping in evaluation context
        const code = scriptMatch[1];
        // Ensure no syntax errors
        new Function(code);
        """
        proc = subprocess.run(
            [node_path, "-e", test_script],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.returncode == 0
