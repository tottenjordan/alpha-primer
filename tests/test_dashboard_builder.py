"""Unit tests for dashboard builder, Safe DOM compliance, and trajectory datasets."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from alpha_evolve.dashboard.build_dashboard import build_dashboard_html
from alpha_evolve.dashboard.trajectory_generator import generate_inventory_trajectory_dataset

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_trajectory_generator_compiles_data(tmp_path: Path) -> None:
    bundle = generate_inventory_trajectory_dataset(output_dir=tmp_path)
    assert (tmp_path / "inventory_replenishment_trajectory.json").exists()
    assert (tmp_path / "master_trajectories.json").exists()
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


def test_master_trajectories_contains_all_use_cases(tmp_path: Path) -> None:
    """Verify master_trajectories.json bundles both inventory_replenishment and fleet_routing."""
    from alpha_evolve.dashboard.fleet_routing_trajectory_generator import (
        generate_fleet_routing_trajectory_dataset,
    )
    from alpha_evolve.dashboard.trajectory_generator import generate_inventory_trajectory_dataset

    # Generate both into tmp_path
    generate_inventory_trajectory_dataset(output_dir=tmp_path)
    generate_fleet_routing_trajectory_dataset(output_dir=tmp_path)

    # Master bundle must contain both use cases
    master_path = tmp_path / "master_trajectories.json"
    assert master_path.exists()
    master = json.loads(master_path.read_text(encoding="utf-8"))
    assert "use_cases" in master
    assert "inventory_replenishment" in master["use_cases"]
    assert "fleet_routing" in master["use_cases"]


def test_all_use_cases_schema_parity(tmp_path: Path) -> None:
    """Verify every use case in master_trajectories.json implements the full UI data contract."""
    from alpha_evolve.dashboard.fleet_routing_trajectory_generator import (
        generate_fleet_routing_trajectory_dataset,
    )
    from alpha_evolve.dashboard.trajectory_generator import generate_inventory_trajectory_dataset

    generate_inventory_trajectory_dataset(output_dir=tmp_path)
    generate_fleet_routing_trajectory_dataset(output_dir=tmp_path)

    master = json.loads((tmp_path / "master_trajectories.json").read_text(encoding="utf-8"))
    required_top_keys = {
        "use_case_id",
        "title",
        "subtitle",
        "recorded_at_utc",
        "baseline_summary",
        "champion_summary",
        "milestones",
        "ribbon_milestones",
        "cost_waterfall",
        "pareto_frontier",
        "sku_archetypes",
        "trajectory_generations",
    }
    required_metrics_keys = {
        "total_cost",
        "fill_rate_pct",
        "spoilage_rate_pct",
        "holding_cost",
        "stockout_penalty",
        "spoilage_cost",
        "ordering_cost",
        "cost_reduction_pct",
        "fitness_score",
    }
    required_series_item_keys = {
        "day",
        "phase",
        "on_hand",
        "in_transit",
        "sales",
        "demand",
        "spoilage_units",
        "cost",
    }

    for uc_id, uc_data in master["use_cases"].items():
        missing_top = required_top_keys - set(uc_data.keys())
        assert not missing_top, f"{uc_id} missing top-level keys: {missing_top}"
        assert len(uc_data["ribbon_milestones"]) >= 4
        assert len(uc_data["cost_waterfall"]["components"]) == 4
        assert len(uc_data["sku_archetypes"]) >= 1
        assert len(uc_data["pareto_frontier"]) == 31
        assert len(uc_data["trajectory_generations"]) == 31

        for gen_entry in uc_data["trajectory_generations"]:
            assert "metrics" in gen_entry, f"{uc_id} gen {gen_entry['generation']} missing metrics"
            missing_m = required_metrics_keys - set(gen_entry["metrics"].keys())
            assert not missing_m, f"{uc_id} missing metric keys: {missing_m}"
            assert "daily_series" in gen_entry, f"{uc_id} missing daily_series"
            assert isinstance(gen_entry["daily_series"], list)
            assert len(gen_entry["daily_series"]) == 90
            missing_s = required_series_item_keys - set(gen_entry["daily_series"][0].keys())
            assert not missing_s, f"{uc_id} missing daily_series item keys: {missing_s}"

        for m_gen, m_data in uc_data["milestones"].items():
            assert len(m_data["evolve_block"].splitlines()) >= 10, (
                f"{uc_id} milestone {m_gen} should have a realistic multi-line evolve_block"
            )
            assert "metrics" in m_data
            assert "key_innovations" in m_data


def test_dashboard_multi_use_case_switcher_elements(tmp_path: Path) -> None:
    """Verify index.html contains use-case switcher pills and navigation elements."""
    html_path = build_dashboard_html(output_dir=tmp_path)
    content = html_path.read_text(encoding="utf-8")

    assert 'id="use-case-switcher"' in content
    assert 'data-use-case="inventory_replenishment"' in content
    assert 'data-use-case="fleet_routing"' in content
    assert 'id="active-use-case-title"' in content


def test_dashboard_client_use_case_switching_logic(tmp_path: Path) -> None:
    """Verify JavaScript includes switchUseCase function and Safe DOM re-binding."""
    html_path = build_dashboard_html(output_dir=tmp_path)
    content = html_path.read_text(encoding="utf-8")

    assert "switchUseCase" in content
    assert "currentUseCaseId" in content
    assert "innerHTML" not in content  # Strict enterprise rule


def test_build_dashboard_html_safe_dom_compliance(tmp_path: Path) -> None:
    html_path = build_dashboard_html(output_dir=tmp_path)
    assert html_path.exists()
    assert html_path.parent == tmp_path
    assert (tmp_path / "data.json").exists()
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


def test_trajectory_milestone_and_pareto_metadata(tmp_path: Path) -> None:
    bundle = generate_inventory_trajectory_dataset(output_dir=tmp_path)
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


def test_high_visibility_diff_engine_elements(tmp_path: Path) -> None:
    html_path = build_dashboard_html(output_dir=tmp_path)
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


def test_evolutionary_progression_suite_and_dual_whatif(tmp_path: Path) -> None:
    html_path = build_dashboard_html(output_dir=tmp_path)
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


def test_diff_engine_robustness_and_client_js_execution(tmp_path: Path) -> None:
    html_path = build_dashboard_html(output_dir=tmp_path)
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
        test_script = f"""
        const fs = require('fs');
        const html = fs.readFileSync({json.dumps(str(html_path))}, 'utf8');
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


def test_realtime_stream_dashboard_elements(tmp_path: Path) -> None:
    """Verify index.html contains real-time SSE components and Safe DOM live handlers."""
    html_path = build_dashboard_html(output_dir=tmp_path)
    content = html_path.read_text(encoding="utf-8")

    # Live streaming status pill and toast notification
    assert 'id="pill-stream-status"' in content
    assert 'id="dot-stream-status"' in content
    assert 'id="text-stream-status"' in content
    assert 'id="live-toast"' in content
    assert 'id="live-toast-text"' in content

    # Server-Sent Events client connection
    assert 'new EventSource("/api/stream/events")' in content
    assert "connectTelemetryStream" in content
    assert 'addEventListener("candidate_evaluated"' in content
    assert 'addEventListener("state_snapshot"' in content
    assert 'addEventListener("run_started"' in content
    assert 'addEventListener("run_completed"' in content

    # Dynamic trajectory updating without innerHTML
    assert "innerHTML" not in content
    assert "showLiveToast" in content


def test_dashboard_template_modularity() -> None:
    """Verify build_dashboard.py is modularized with separate CSS, HTML, and JS templates."""
    builder_path = ROOT_DIR / "src" / "alpha_evolve" / "dashboard" / "build_dashboard.py"
    templates_dir = ROOT_DIR / "src" / "alpha_evolve" / "dashboard" / "templates"

    assert len(builder_path.read_text(encoding="utf-8").splitlines()) < 150
    for filename in ("styles.css", "body.html", "app.js"):
        asset_path = templates_dir / filename
        assert asset_path.exists(), f"Missing template asset: {filename}"
        assert "innerHTML" not in asset_path.read_text(encoding="utf-8")


def test_web_app_development_design_and_multi_domain_standards(tmp_path: Path) -> None:
    """Verify HSL token discipline, zero inline styles, ARIA semantics, and multi-domain scaling."""
    templates_dir = ROOT_DIR / "src" / "alpha_evolve" / "dashboard" / "templates"
    css_text = (templates_dir / "styles.css").read_text(encoding="utf-8")
    body_text = (templates_dir / "body.html").read_text(encoding="utf-8")
    js_text = (templates_dir / "app.js").read_text(encoding="utf-8")

    # 1. Design system hygiene: HSL tokens, tabular numerals, no purple-on-dark, zero inline styles
    assert "hsl(" in css_text
    assert "--surface-gradient:" in css_text
    assert "font-variant-numeric: tabular-nums" in css_text
    assert "--accent-purple" not in css_text
    assert "#A855F7" not in css_text
    assert 'style="' not in body_text
    assert ".style." not in js_text

    # 2. Semantic HTML5 & WAI-ARIA landmarks and unique interactive control IDs
    html_path = build_dashboard_html(output_dir=tmp_path)
    content = html_path.read_text(encoding="utf-8")
    assert '<main id="dashboard-main">' in content
    assert 'role="tablist"' in content
    assert 'role="tab"' in content
    assert 'role="tabpanel"' in content
    assert 'id="btn-speed-toggle"' in content
    assert 'id="btn-preset-0"' in content
    assert 'id="btn-diff-0-8"' in content

    # 3. Interactive canvas tooltip HUDs & multi-domain synchronization hooks
    assert 'id="tooltip-trajectory"' in content
    assert 'id="tooltip-convergence"' in content
    assert 'id="thead-archetypes-row"' in content
    assert "updateDomainControls" in content


def test_fleet_routing_spatial_topology_and_canvas_rendering(tmp_path: Path) -> None:
    """Verify Fleet Routing exports 50-customer spatial topology, 2-opt uncrossing snapshots, and UI hooks."""
    from alpha_evolve.dashboard.fleet_routing_trajectory_generator import (
        generate_fleet_routing_trajectory_dataset,
    )

    fr = generate_fleet_routing_trajectory_dataset(output_dir=tmp_path)

    # 1. Verify spatial_topology schema (50 customers, (50, 50) depot, 4 quadrants, coordinates & windows)
    topo = fr["spatial_topology"]
    assert topo["grid_bounds_km"] == [0.0, 100.0, 0.0, 100.0]
    assert topo["depot"]["x_km"] == 50.0 and topo["depot"]["y_km"] == 50.0
    assert topo["depot"]["x"] == 50.0 and topo["depot"]["y"] == 50.0
    assert len(topo["cluster_centers"]) == 4
    assert len(topo["customers"]) == 50
    assert len(topo["customer_coordinates"]) == 50
    assert len(topo["time_windows"]) == 50

    for idx, c in enumerate(topo["customers"]):
        assert c["id"] == idx
        assert 0.0 <= c["x_km"] <= 100.0 and 0.0 <= c["y_km"] <= 100.0
        assert [c["x_km"], c["y_km"]] == topo["customer_coordinates"][idx]
        assert c["tw_end"] > c["tw_start"] >= 0.0
        assert c["time_window"] == [c["tw_start"], c["tw_end"]]
        assert c["time_window"] == topo["time_windows"][idx]

    static_customers = [c for c in topo["customers"] if not c["is_dynamic"]]
    dynamic_customers = [c for c in topo["customers"] if c["is_dynamic"]]
    assert len(static_customers) == 30
    assert len(dynamic_customers) == 20

    # 2. Verify Gen 0 vs Gen 30 route_sequences and dispatch_snapshots ("0", "7", "16", "30")
    assert "customer_coordinates" in fr
    assert "time_windows" in fr
    assert fr["customer_coordinates"] == topo["customer_coordinates"]
    assert fr["time_windows"] == topo["time_windows"]
    assert "route_sequences" in fr
    assert "route_sequences" in topo
    assert fr["route_sequences"]["gen_0"] == fr["route_sequences"]["0"]
    assert fr["route_sequences"]["gen_30"] == fr["route_sequences"]["30"]
    assert fr["route_sequences"]["gen_0"] != fr["route_sequences"]["gen_30"]
    assert fr["baseline_summary"]["route_sequences"] == fr["route_sequences"]["gen_0"]
    assert fr["champion_summary"]["route_sequences"] == fr["route_sequences"]["gen_30"]
    assert fr["milestones"]["0"]["route_sequences"] == fr["route_sequences"]["gen_0"]
    assert fr["milestones"]["30"]["route_sequences"] == fr["route_sequences"]["gen_30"]

    snaps = fr["dispatch_snapshots"]
    for key in ("0", "7", "16", "30"):
        assert key in snaps
        snap = snaps[key]
        assert len(snap["tours"]) > 0
        total_stops = sum(len(t["stops"]) for t in snap["tours"])
        assert total_stops == 50
        assert len(snap["stop_outcomes"]) == 50
        assert "route_sequences" in snap
        assert "vehicle_routes" in snap
        assert len(snap["vehicle_routes"]) == 5
        seq_stops = [s for v in ("0", "1", "2", "3", "4") for s in snap["route_sequences"][v]]
        assert len(seq_stops) == 50
        assert set(seq_stops) == set(range(50))

    assert snaps["0"]["summary"]["intra_route_crossings"] > 0
    assert snaps["16"]["summary"]["intra_route_crossings"] == 0
    assert snaps["30"]["summary"]["intra_route_crossings"] == 0
    assert snaps["30"]["summary"]["late_stops_count"] < snaps["0"]["summary"]["late_stops_count"]
    assert snaps["30"]["summary"]["total_cost"] < snaps["0"]["summary"]["total_cost"]

    # 3. Verify compiled dashboard HTML contains spatial topology renderer, mode toggle, and filter controls
    html_path = build_dashboard_html(output_dir=tmp_path)
    content = html_path.read_text(encoding="utf-8")
    assert 'id="canvas1-mode-toggles"' in content
    assert 'id="btn-mode-topology"' in content
    assert 'id="btn-mode-trajectory"' in content
    assert 'id="fleet-map-controls"' in content
    assert 'data-fleet-filter="wave0"' in content
    assert 'data-fleet-filter="dynamic"' in content
    assert 'data-fleet-filter="late"' in content
    assert "drawFleetSpatialCanvas" in content


def test_fleet_routing_2d_route_topology_map_canvas_mode_js_execution() -> None:
    """Execute app.js in Node.js to verify 2D Route Topology Map rendering, filters, hover HUD, SSE, and mode toggling."""
    node_path = shutil.which("node")
    if not node_path:
        return

    app_js_path = ROOT_DIR / "src" / "alpha_evolve" / "dashboard" / "templates" / "app.js"
    master_path = ROOT_DIR / "records" / "master_trajectories.json"

    node_harness = f"""
    const fs = require('fs');
    const masterData = fs.readFileSync({json.dumps(str(master_path))}, 'utf8');
    const appJs = fs.readFileSync({json.dumps(str(app_js_path))}, 'utf8');

    const elements = new Map();
    const canvasTexts = [];
    const rectCalls = [];
    let arcCalls = 0;
    let lineToCalls = 0;
    let mockCanvasWidth = 760;
    let mockCanvasHeight = 310;
    let sseListeners = {{}};

    function makeEl(tag, id) {{
      return {{
        tagName: tag,
        id: id || '',
        className: '',
        textContent: '',
        value: '0',
        children: [],
        attributes: new Map(),
        listeners: {{}},
        classList: {{
          classes: new Set(),
          add(c) {{ this.classes.add(c); }},
          remove(c) {{ this.classes.delete(c); }},
          toggle(c, force) {{
            if (force === undefined) {{
              if (this.classes.has(c)) this.classes.delete(c); else this.classes.add(c);
            }} else if (force) {{
              this.classes.add(c);
            }} else {{
              this.classes.delete(c);
            }}
          }},
          contains(c) {{ return this.classes.has(c); }}
        }},
        appendChild(child) {{ this.children.push(child); return child; }},
        replaceChildren(...nodes) {{ this.children = nodes; }},
        insertBefore(node) {{ this.children.push(node); }},
        remove() {{}},
        setAttribute(k, v) {{ this.attributes.set(k, String(v)); }},
        getAttribute(k) {{ return this.attributes.get(k) || null; }},
        addEventListener(ev, fn) {{
          if (!this.listeners[ev]) this.listeners[ev] = [];
          this.listeners[ev].push(fn);
        }},
        querySelectorAll() {{ return []; }},
        getBoundingClientRect() {{ return {{ left: 0, top: 0, width: mockCanvasWidth, height: mockCanvasHeight }}; }},
        getContext() {{
          return {{
            scale() {{}}, clearRect() {{}},
            fillRect(x, y, w, h) {{ rectCalls.push({{ x, y, w, h }}); }},
            beginPath() {{}},
            moveTo() {{}}, lineTo() {{ lineToCalls++; }}, stroke() {{}}, fill() {{}},
            arc() {{ arcCalls++; }}, setLineDash() {{}},
            strokeRect(x, y, w, h) {{ rectCalls.push({{ x, y, w, h }}); }},
            fillText(txt) {{ canvasTexts.push(String(txt)); }},
            createLinearGradient() {{ return {{ addColorStop() {{}} }}; }}
          }};
        }}
      }};
    }}

    function getEl(id) {{
      if (!elements.has(id)) {{
        const e = makeEl('div', id);
        if (id === 'master-trajectory-data') e.textContent = masterData;
        if (id === 'canvas1-mode-toggles' || id === 'fleet-map-controls') e.classList.add('hidden');
        if (id === 'btn-mode-topology') e.classList.add('active');
        elements.set(id, e);
      }}
      return elements.get(id);
    }}

    const useCaseBtns = ['inventory_replenishment', 'fleet_routing'].map(uc => {{
      const b = makeEl('button', 'btn-' + uc);
      b.setAttribute('data-use-case', uc);
      return b;
    }});

    const filterBtns = ['all', 'wave0', 'dynamic', 'late', 'v0', 'v1', 'v2', 'v3', 'v4'].map(f => {{
      const b = makeEl('button', 'filter-' + f);
      b.setAttribute('data-fleet-filter', f);
      if (f === 'all') b.classList.add('active');
      return b;
    }});

    class MockEventSource {{
      constructor() {{ sseListeners = {{}}; }}
      addEventListener(ev, fn) {{ sseListeners[ev] = fn; }}
    }}

    global.EventSource = MockEventSource;
    global.window = {{
      location: {{ protocol: 'file:' }},
      devicePixelRatio: 2,
      EventSource: MockEventSource,
      addEventListener() {{}}
    }};
    global.document = {{
      createElement(tag) {{ return makeEl(tag, ''); }},
      createTextNode(txt) {{ return {{ textContent: String(txt) }}; }},
      createDocumentFragment() {{ return makeEl('fragment', ''); }},
      getElementById(id) {{ return getEl(id); }},
      querySelectorAll(sel) {{
        if (sel === '.use-case-btn') return useCaseBtns;
        if (sel === '.btn-fleet-filter') return filterBtns;
        return [];
      }}
    }};

    global.setTimeout = () => 1;
    global.clearTimeout = () => {{}};
    global.setInterval = () => 1;
    global.clearInterval = () => {{}};

    eval(appJs);

    // 1. Switch to fleet_routing and verify 2D Route Topology Map mode is active
    useCaseBtns[1].listeners['click'][0]();
    if (getEl('canvas1-mode-toggles').classList.contains('hidden')) {{
      throw new Error('canvas1-mode-toggles should be visible in fleet_routing');
    }}
    if (getEl('fleet-map-controls').classList.contains('hidden')) {{
      throw new Error('fleet-map-controls should be visible in topology mode');
    }}
    if (!getEl('canvas1-container').classList.contains('fleet-spatial-mode')) {{
      throw new Error('canvas1-container missing fleet-spatial-mode class');
    }}
    if (!getEl('canvas1-title').textContent.includes('2D Route Topology Map')) {{
      throw new Error('Unexpected canvas1-title: ' + getEl('canvas1-title').textContent);
    }}
    if (!canvasTexts.includes('GEN 0: GREEDY BASELINE') || !canvasTexts.includes('DELTA HUD')) {{
      throw new Error('Missing expected 2D topology viewport headers on canvas');
    }}
    if (!canvasTexts.includes('GEN 30: REGRET-2 + 2-OPT')) {{
      throw new Error('Missing GEN 30: REGRET-2 + 2-OPT header on right viewport');
    }}
    if (arcCalls < 100 || lineToCalls < 50) {{
      throw new Error('Expected customer arcs and route polylines to be drawn');
    }}

    // Verify Gen 16 distinct right-viewport header
    canvasTexts.length = 0;
    getEl('scrubber').listeners['input'][0]({{ target: {{ value: '16' }} }});
    if (!canvasTexts.includes('GEN 16: TRAFFIC + 2-OPT')) {{
      throw new Error('Expected GEN 16: TRAFFIC + 2-OPT header when scrubbing to Gen 16');
    }}
    getEl('scrubber').listeners['input'][0]({{ target: {{ value: '30' }} }});

    // 2. Test interactive customer hover on #canvas-trajectory in topology mode
    const parsedMaster = JSON.parse(masterData);
    const c0 = parsedMaster.use_cases.fleet_routing.spatial_topology.customers[0];
    const centerW = Math.min(116, Math.max(48, Math.round(760 * 0.16)));
    const boxW = Math.max(36, Math.floor((760 - centerW - 24) / 2));
    const mapTop = 24, mapBot = 302, mapH = mapBot - mapTop;
    const cx = 6 + 10 + (c0.x_km / 100.0) * (boxW - 20);
    const cy = mapBot - 10 - (c0.y_km / 100.0) * (mapH - 20);

    const moveFn = getEl('canvas-trajectory').listeners['mousemove'][0];
    moveFn({{ clientX: cx, clientY: cy }});
    const tipEl = getEl('tooltip-trajectory');
    if (!tipEl.classList.contains('visible') || tipEl.children.length === 0) {{
      throw new Error('Expected tooltip-trajectory to become visible on stop hover');
    }}
    const tipText = tipEl.children[0].textContent;
    if (!tipText.includes('Stop #0') || !tipText.includes('Gen 0:') || !tipText.includes('Gen 30:')) {{
      throw new Error('Unexpected stop hover tooltip text: ' + tipText);
    }}

    // 3. Test filter buttons (wave0, dynamic, late, v0)
    filterBtns[1].listeners['click'][0]();
    if (!filterBtns[1].classList.contains('active') || filterBtns[0].classList.contains('active')) {{
      throw new Error('Wave 0 filter button did not activate properly');
    }}
    filterBtns[0].listeners['click'][0]();

    // 4. Toggle Canvas 1 mode to 90-Step Shift Trajectory and back to 2D Route Topology Map
    getEl('btn-mode-trajectory').listeners['click'][0]();
    if (!getEl('fleet-map-controls').classList.contains('hidden')) {{
      throw new Error('fleet-map-controls should hide when 90-Step Shift Trajectory mode is active');
    }}
    if (getEl('canvas1-subtitle').classList.contains('hidden')) {{
      throw new Error('canvas1-subtitle should be visible in 90-Step Shift Trajectory mode');
    }}
    if (!getEl('canvas1-title').textContent.includes('90-Step Fleet Active Route Load')) {{
      throw new Error('Expected 90-Step trajectory title, got: ' + getEl('canvas1-title').textContent);
    }}

    getEl('btn-mode-topology').listeners['click'][0]();
    if (getEl('fleet-map-controls').classList.contains('hidden')) {{
      throw new Error('fleet-map-controls should reappear when switching back to 2D Route Topology Map');
    }}
    if (!getEl('canvas1-title').textContent.includes('2D Route Topology Map')) {{
      throw new Error('Expected 2D Route Topology Map title after switching back');
    }}

    // 5. Test SSE candidate_evaluated at iteration 35 while in 2D Route Topology Map mode
    if (sseListeners['candidate_evaluated']) {{
      canvasTexts.length = 0;
      sseListeners['candidate_evaluated']({{
        data: JSON.stringify({{
          iteration: 35,
          score: 31.4,
          is_best: true,
          scores: {{ on_time_delivery_pct: 98.0, total_distance_km: 1090 }}
        }})
      }});
      if (!canvasTexts.includes('GEN 35: REGRET-2 + 2-OPT')) {{
        throw new Error('Expected SSE iteration 35 to render GEN 35: REGRET-2 + 2-OPT in topology mode');
      }}
    }}

    // 6. Test ultra-narrow mobile viewport (<320px) stays within canvas width
    mockCanvasWidth = 240;
    mockCanvasHeight = 220;
    rectCalls.length = 0;
    getEl('scrubber').listeners['input'][0]({{ target: {{ value: '30' }} }});
    const outOfBounds = rectCalls.some(r => (r.x + r.w) > mockCanvasWidth + 1);
    if (outOfBounds) {{
      throw new Error('Viewport or HUD box overflowed ultra-narrow 240px canvas width');
    }}

    // 7. Test pure route_sequences fallback (without tours/stop_outcomes) and coincident stop coordinates
    mockCanvasWidth = 760;
    mockCanvasHeight = 310;
    const customMaster = JSON.parse(masterData);
    const frCustom = customMaster.use_cases.fleet_routing;
    // Place customer 1 at identical coordinates to customer 0
    frCustom.spatial_topology.customers[1].x_km = c0.x_km;
    frCustom.spatial_topology.customers[1].y_km = c0.y_km;
    frCustom.spatial_topology.customers[1].is_dynamic = false;
    // Strip tours and stop_outcomes to exercise pure route_sequences fallback
    delete frCustom.dispatch_snapshots['0'].tours;
    delete frCustom.dispatch_snapshots['0'].stop_outcomes;
    delete frCustom.dispatch_snapshots['30'].tours;
    delete frCustom.dispatch_snapshots['30'].stop_outcomes;

    elements.clear();
    useCaseBtns.forEach(b => {{ b.listeners = {{}}; }});
    filterBtns.forEach(b => {{ b.listeners = {{}}; }});
    getEl('master-trajectory-data').textContent = JSON.stringify(customMaster);
    eval(appJs);
    useCaseBtns[1].listeners['click'][0]();
    const moveFn2 = getEl('canvas-trajectory').listeners['mousemove'][0];
    moveFn2({{ clientX: cx, clientY: cy }});
    const tipText2 = getEl('tooltip-trajectory').children[0].textContent;
    if (!tipText2.includes('Stop #1') || tipText2.includes('Unassigned')) {{
      throw new Error('Expected topmost coincident Stop #1 with route_sequences vehicle fallback, got: ' + tipText2);
    }}

    console.log('TOPOLOGY_MAP_JS_CHECKS_PASSED');
    """

    proc = subprocess.run(
        [node_path, "-e", node_harness],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "TOPOLOGY_MAP_JS_CHECKS_PASSED" in proc.stdout
