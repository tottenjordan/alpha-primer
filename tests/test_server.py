"""Unit tests for server.py endpoints, security headers, and input validation."""

from __future__ import annotations

from server import SECURITY_HEADERS, handle_api_request


def test_server_health_endpoint() -> None:
    code, headers, body = handle_api_request("/health")
    assert code == 200
    assert body["status"] == "healthy"
    assert body["service"] == "alpha-evolve-inventory-digital-twin"
    assert body["secrets_leaked"] is False

    # Enforce security headers
    for key in SECURITY_HEADERS:
        assert key in headers
    assert "Content-Security-Policy" in headers


def test_server_cloud_status_endpoint() -> None:
    code, headers, body = handle_api_request("/api/cloud-status")
    assert code == 200
    assert body["status"] == "healthy"
    assert "engine_info" in body
    assert body["secrets_leaked"] is False
    assert "experiments" in body


def test_server_dashboard_index_endpoint() -> None:
    code, headers, body = handle_api_request("/")
    assert code == 200
    assert isinstance(body, str)
    assert "<!DOCTYPE html>" in body
    assert "AlphaEvolve Supply Chain" in body
    assert headers["Content-Type"] == "text/html; charset=utf-8"


def test_server_data_json_endpoint() -> None:
    code, headers, body = handle_api_request("/api/data")
    assert code == 200
    assert isinstance(body, dict)
    assert "platform_title" in body
    assert "use_cases" in body
    assert "inventory_replenishment" in body["use_cases"]


def test_server_trajectories_valid() -> None:
    code, headers, body = handle_api_request("/api/trajectories/inventory_replenishment")
    assert code == 200
    assert isinstance(body, dict)
    assert body["use_case_id"] == "inventory_replenishment"
    assert len(body["trajectory_generations"]) == 31


def test_server_trajectories_fleet_routing() -> None:
    code, headers, body = handle_api_request("/api/trajectories/fleet_routing")
    assert code == 200
    assert isinstance(body, dict)
    assert body["use_case_id"] == "fleet_routing"
    assert len(body["trajectory_generations"]) == 31


def test_server_trajectories_invalid() -> None:
    code, headers, body = handle_api_request("/api/trajectories/unknown_use_case")
    assert code == 400
    assert "Invalid use_case_id" in body["detail"]


def test_server_trajectories_path_traversal() -> None:
    code, headers, body = handle_api_request("/api/trajectories/../../etc/passwd")
    assert code == 400
    assert "Invalid use_case_id" in body["detail"]


def test_server_unknown_path() -> None:
    code, headers, body = handle_api_request("/some/unknown/route")
    assert code == 404
    assert body["detail"] == "Not found"


def test_server_agent_replenish_query() -> None:
    code, headers, body = handle_api_request("/api/agent/replenish-query")
    assert code == 200
    assert body["status"] == "success"
    assert body["agent_id"] == "inventory-replenishment-twin"
    assert body["use_case"] == "inventory_replenishment"
    assert "Gen 30 Champion reduces supply chain cost" in body["summary"]
    assert (
        "### 🌾 AlphaEvolve Autonomous Inventory Replenishment Agent" in body["grounding_markdown"]
    )
    assert "metrics" in body
    assert body["metrics"]["cost_reduction_pct"] > 30.0
    assert len(body["key_innovations"]) == 4
    assert headers["Content-Type"] == "application/json"


def test_server_agent_replenish_query_with_what_if_payload() -> None:
    payload = {
        "query": "what-if",
        "lead_time_delay": 2.0,
        "promo_spike": 0.3,
    }
    code, headers, body = handle_api_request("/api/agent/replenish-query", payload=payload)
    assert code == 200
    assert body["status"] == "success"
    assert body["query_type"] == "what-if"
    assert "what_if_stress_test" in body
    stress = body["what_if_stress_test"]
    assert stress["lead_time_delay_days"] == 2.0
    assert stress["promo_demand_spike_pct"] == 30.0
    assert stress["projected_cost_increase_pct"] > 0.0
    assert "Champion policy absorbs shocks" in stress["resilience_recommendation"]


def test_server_agent_replenish_query_with_malformed_payload() -> None:
    # Verify non-numeric or malformed payload does not crash server (defensive float casting)
    payload = {
        "query": "malformed_test",
        "lead_time_delay": "not-a-number",
        "promo_spike": None,
    }
    code, headers, body = handle_api_request("/api/agent/replenish-query", payload=payload)
    assert code == 200
    assert body["status"] == "success"
    assert "what_if_stress_test" not in body
    assert body["metrics"]["cost_reduction_pct"] > 30.0


def test_server_live_state_and_candidates() -> None:
    """Verify /api/live/state and /api/live/candidates endpoints."""
    from alpha_evolve.dashboard.telemetry_broker import get_global_broker

    broker = get_global_broker()
    broker.clear()

    # Initial state should be IDLE
    code, headers, body = handle_api_request("/api/live/state")
    assert code == 200
    assert headers["Content-Type"] == "application/json"
    assert body["status"] == "IDLE"
    assert body["evaluated_count"] == 0

    # Post new candidate
    candidate_payload = {
        "iteration": 1,
        "program_id": "test/programs/cand_1",
        "score": 18.5,
        "is_best": True,
    }
    code, headers, body = handle_api_request("/api/live/candidates", payload=candidate_payload)
    assert code == 200
    assert body["status"] == "accepted"
    assert body["evaluated_count"] == 1

    # Verify state reflects candidate
    code, headers, body = handle_api_request("/api/live/state")
    assert code == 200
    assert body["evaluated_count"] == 1
    assert body["best_score"] == 18.5
    assert body["latest_candidate"]["iteration"] == 1

    # Empty payload should return 400
    code, headers, body = handle_api_request("/api/live/candidates", payload={})
    assert code == 400
    assert "Missing candidate" in body["detail"]


def test_server_mtime_cache_and_invalidation(tmp_path) -> None:
    """Verify _read_json_cached serves cached content and invalidates when file mtime changes."""
    import time

    from server import _read_json_cached

    sample_file = tmp_path / "sample.json"
    sample_file.write_text('{"version": 1}', encoding="utf-8")
    assert _read_json_cached(sample_file) == {"version": 1}

    # Ensure mtime advances before rewriting
    time.sleep(0.01)
    sample_file.write_text('{"version": 2}', encoding="utf-8")
    assert _read_json_cached(sample_file) == {"version": 2}


def test_bounded_json_payload_enforces_1mb_limit() -> None:
    """Verify POST payload parser enforces the 1 MB request body limit with HTTP 413."""
    from server import MAX_REQUEST_BODY_BYTES, parse_bounded_json_body

    # 1. Valid payload within limit
    status_ok, parsed = parse_bounded_json_body(b'{"query": "what-if"}', content_length_header="19")
    assert status_ok == 200
    assert parsed == {"query": "what-if"}

    # 2. Oversized Content-Length header rejected immediately with 413
    status_hdr, err_hdr = parse_bounded_json_body(
        b"", content_length_header=str(MAX_REQUEST_BODY_BYTES + 1)
    )
    assert status_hdr == 413
    assert "exceeds" in err_hdr["detail"]

    # 3. Oversized raw body rejected with 413 even without Content-Length header
    oversized_bytes = b"x" * (MAX_REQUEST_BODY_BYTES + 128)
    status_raw, err_raw = parse_bounded_json_body(oversized_bytes)
    assert status_raw == 413
    assert "exceeds" in err_raw["detail"]


def test_server_simulate_inventory_replenishment() -> None:
    """Verify /api/simulate executes real InventoryDigitalTwin for Baseline and Champion."""
    code0, headers, sim0 = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "inventory_replenishment",
            "archetype_index": 0,
            "lead_time_delay": 0,
            "promo_spike_pct": 0,
        },
    )
    assert code0 == 200
    assert headers["Content-Type"] == "application/json"
    assert sim0["status"] == "success"
    assert sim0["use_case"] == "inventory_replenishment"
    assert sim0["simulation_engine"] == "InventoryDigitalTwin"
    assert sim0["champion"]["total_cost"] < sim0["baseline"]["total_cost"]
    assert sim0["champion"]["fill_rate_pct"] > sim0["baseline"]["fill_rate_pct"]
    assert sim0["comparison"]["cost_reduction_pct"] > 0.0
    assert sim0["comparison"]["daily_cost_savings"] > 0.0

    # Stressed simulation should increase baseline cost and amplify savings
    code_stress, _, sim_stress = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "inventory_replenishment",
            "archetype_index": 0,
            "lead_time_delay": 3,
            "promo_spike_pct": 30,
            "spoilage_multiplier": 1.5,
            "stockout_multiplier": 1.5,
        },
    )
    assert code_stress == 200
    assert sim_stress["baseline"]["total_cost"] > sim0["baseline"]["total_cost"]
    assert sim_stress["champion"]["total_cost"] < sim_stress["baseline"]["total_cost"]
    assert sim_stress["champion"]["fill_rate_pct"] > sim_stress["baseline"]["fill_rate_pct"]


def test_server_simulate_fleet_routing() -> None:
    """Verify /api/simulate executes real FleetRoutingDigitalTwin for Baseline and Champion."""
    code0, _, sim0 = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "fleet_routing",
            "archetype_index": 1,
            "lead_time_delay": 0,
            "promo_spike_pct": 0,
        },
    )
    assert code0 == 200
    assert sim0["status"] == "success"
    assert sim0["use_case"] == "fleet_routing"
    assert sim0["simulation_engine"] == "FleetRoutingDigitalTwin"
    assert sim0["champion"]["total_cost"] < sim0["baseline"]["total_cost"]
    assert sim0["champion"]["on_time_delivery_pct"] > sim0["baseline"]["on_time_delivery_pct"]
    assert sim0["champion"]["total_tardiness_hours"] < sim0["baseline"]["total_tardiness_hours"]
    assert sim0["comparison"]["cost_reduction_pct"] > 0.0

    code_stress, _, sim_stress = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "fleet_routing",
            "archetype_index": 0,
            "lead_time_delay": 3,
            "promo_spike_pct": 35,
            "spoilage_multiplier": 1.4,
            "stockout_multiplier": 1.4,
        },
    )
    assert code_stress == 200
    assert sim_stress["baseline"]["total_cost"] > sim0["baseline"]["total_cost"]
    assert sim_stress["champion"]["total_cost"] < sim_stress["baseline"]["total_cost"]


def test_server_simulate_validation_and_defensive_clamping() -> None:
    """Verify /api/simulate rejects unknown use_case and clamps malformed parameters safely."""
    code_bad, _, body_bad = handle_api_request(
        "/api/simulate", payload={"use_case": "invalid_domain"}
    )
    assert code_bad == 400
    assert "Invalid use_case" in body_bad["detail"]

    code_edge, _, body_edge = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "inventory_replenishment",
            "archetype_index": 99,
            "lead_time_delay": "not-a-number",
            "promo_spike": True,
            "spoilage_multiplier": -10.0,
            "stockout_multiplier": None,
        },
    )
    assert code_edge == 200
    assert body_edge["parameters"]["archetype_index"] == 2
    assert body_edge["parameters"]["lead_time_delay"] == 0.0
    assert body_edge["parameters"]["promo_spike"] == 0.0
    assert body_edge["parameters"]["spoilage_multiplier"] == 0.1
    assert body_edge["parameters"]["stockout_multiplier"] == 1.0


def test_server_agent_multi_domain_query() -> None:
    """Verify /api/agent/query supports both inventory_replenishment and fleet_routing."""
    code_fr, _, body_fr = handle_api_request(
        "/api/agent/query",
        payload={
            "use_case": "fleet_routing",
            "query": "what-if",
            "lead_time_delay": 2.0,
            "promo_spike": 0.25,
        },
    )
    assert code_fr == 200
    assert body_fr["status"] == "success"
    assert body_fr["agent_id"] == "fleet-routing-twin"
    assert body_fr["use_case"] == "fleet_routing"
    assert "### 🚚 AlphaEvolve Dynamic Fleet Routing" in body_fr["grounding_markdown"]
    assert "what_if_stress_test" in body_fr
    stress = body_fr["what_if_stress_test"]
    assert stress["lead_time_delay_days"] == 2.0
    assert stress["promo_demand_spike_pct"] == 25.0
    assert stress["projected_cost_increase_pct"] > 0.0
    assert stress["simulation"]["simulation_engine"] == "FleetRoutingDigitalTwin"

    code_invalid, _, body_invalid = handle_api_request(
        "/api/agent/query", payload={"use_case": "nonexistent"}
    )
    assert code_invalid == 400
    assert "Invalid use_case" in body_invalid["detail"]


def test_server_simulate_extreme_stress_and_all_archetypes() -> None:
    """Verify Champion strictly outperforms Baseline across all archetypes and extreme stress inputs."""
    for use_case in ("inventory_replenishment", "fleet_routing"):
        for arch_idx in (0, 1, 2):
            for delay, promo_pct, mult in ((0.0, 0.0, 1.0), (14.0, 200.0, 10.0)):
                code, _, sim = handle_api_request(
                    "/api/simulate",
                    payload={
                        "use_case": use_case,
                        "archetype_index": arch_idx,
                        "lead_time_delay": delay,
                        "promo_spike_pct": promo_pct,
                        "spoilage_multiplier": mult,
                        "stockout_multiplier": mult,
                    },
                )
                assert code == 200
                assert sim["champion"]["total_cost"] < sim["baseline"]["total_cost"]
                assert sim["champion"]["fill_rate_pct"] > sim["baseline"]["fill_rate_pct"]
                assert sim["champion"]["spoilage_units"] < sim["baseline"]["spoilage_units"]
                assert sim["comparison"]["cost_reduction_pct"] > 0.0
                assert sim["comparison"]["fill_rate_gain_pct"] > 0.0
                assert sim["comparison"]["spoilage_reduction_units"] > 0.0


def test_server_agent_query_archetype_alignment_and_url_query_params() -> None:
    """Verify /api/agent/query compares matching archetypes and parses URL query parameters."""
    # Archetype 2 (Ambient Grocery) has lower base cost than Archetype 0; stress test must
    # compare against Archetype 2's nominal baseline rather than Archetype 0.
    code_arch2, _, body_arch2 = handle_api_request(
        "/api/agent/query",
        payload={
            "use_case": "inventory_replenishment",
            "archetype_index": 2,
            "lead_time_delay_days": 1.0,
            "promo_spike_pct": 20.0,
        },
    )
    assert code_arch2 == 200
    stress2 = body_arch2["what_if_stress_test"]
    assert stress2["lead_time_delay_days"] == 1.0
    assert stress2["promo_demand_spike_pct"] == 20.0
    assert stress2["projected_cost_increase_pct"] > 10.0

    # Verify URL query string parameters work on GET /api/agent/query?...
    code_qs, _, body_qs = handle_api_request(
        "/api/agent/query?use_case=fleet_routing&lead_time_delay=2&promo_spike_pct=25"
    )
    assert code_qs == 200
    assert body_qs["use_case"] == "fleet_routing"
    assert "what_if_stress_test" in body_qs
    assert body_qs["what_if_stress_test"]["lead_time_delay_days"] == 2.0
    assert body_qs["what_if_stress_test"]["promo_demand_spike_pct"] == 25.0

    # Verify fractional lead_time_delay (0.4), small promo_spike_pct (1.0), and >6 day delays
    _, _, nom_inv = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "inventory_replenishment",
            "lead_time_delay": 0.0,
            "promo_spike_pct": 0.0,
        },
    )
    _, _, frac_delay_inv = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "inventory_replenishment",
            "lead_time_delay": 0.4,
            "promo_spike_pct": 0.0,
        },
    )
    assert frac_delay_inv["baseline"]["total_cost"] > nom_inv["baseline"]["total_cost"]

    _, _, small_promo_inv = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "inventory_replenishment",
            "lead_time_delay": 0.0,
            "promo_spike_pct": 1.0,
        },
    )
    assert small_promo_inv["baseline"]["total_cost"] > nom_inv["baseline"]["total_cost"]

    _, _, delay6_inv = handle_api_request(
        "/api/simulate",
        payload={"use_case": "inventory_replenishment", "lead_time_delay": 6.0},
    )
    _, _, delay10_inv = handle_api_request(
        "/api/simulate",
        payload={"use_case": "inventory_replenishment", "lead_time_delay": 10.0},
    )
    assert delay10_inv["baseline"]["total_cost"] != delay6_inv["baseline"]["total_cost"]

    # Verify <1.0 cost multipliers report negative projected_cost_increase_pct
    code_disc, _, body_disc = handle_api_request(
        "/api/agent/query",
        payload={
            "use_case": "inventory_replenishment",
            "spoilage_multiplier": 0.5,
            "stockout_multiplier": 0.5,
        },
    )
    assert code_disc == 200
    assert body_disc["what_if_stress_test"]["projected_cost_increase_pct"] < 0.0


def test_whatif_sandbox_client_js_live_simulate_and_race_guard() -> None:
    """Execute app.js in Node.js with a simulated DOM to verify fetch('/api/simulate') and race guards."""
    import json
    import shutil
    import subprocess
    from pathlib import Path

    node_path = shutil.which("node")
    if not node_path:
        return

    root_dir = Path(__file__).resolve().parent.parent
    app_js_path = root_dir / "src" / "alpha_evolve" / "dashboard" / "templates" / "app.js"
    master_path = root_dir / "records" / "master_trajectories.json"

    _, _, inv_sim = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "inventory_replenishment",
            "archetype_index": 0,
            "lead_time_delay": 2,
            "promo_spike_pct": 30,
        },
    )
    _, _, fleet_sim = handle_api_request(
        "/api/simulate",
        payload={
            "use_case": "fleet_routing",
            "archetype_index": 0,
            "lead_time_delay": 2,
            "promo_spike_pct": 30,
        },
    )

    node_harness = f"""
    const fs = require('fs');
    const masterData = fs.readFileSync({json.dumps(str(master_path))}, 'utf8');
    const appJs = fs.readFileSync({json.dumps(str(app_js_path))}, 'utf8');
    const invSim = {json.dumps(inv_sim)};
    const fleetSim = {json.dumps(fleet_sim)};

    const elements = new Map();
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
        getBoundingClientRect() {{ return {{ left: 0, top: 0, width: 600, height: 260 }}; }},
        getContext() {{
          return {{
            scale() {{}}, clearRect() {{}}, fillRect() {{}}, beginPath() {{}},
            moveTo() {{}}, lineTo() {{}}, stroke() {{}}, fill() {{}}, arc() {{}},
            setLineDash() {{}}, fillText() {{}}, strokeRect() {{}},
            createLinearGradient() {{ return {{ addColorStop() {{}} }}; }}
          }};
        }}
      }};
    }}

    function getEl(id) {{
      if (!elements.has(id)) {{
        const e = makeEl('div', id);
        if (id === 'master-trajectory-data') e.textContent = masterData;
        if (id === 'slide-spoil' || id === 'slide-stockout') e.value = '10';
        elements.set(id, e);
      }}
      return elements.get(id);
    }}

    const useCaseBtns = ['inventory_replenishment', 'fleet_routing'].map(uc => {{
      const b = makeEl('button', 'btn-' + uc);
      b.setAttribute('data-use-case', uc);
      return b;
    }});

    global.window = {{
      location: {{ protocol: 'http:' }},
      devicePixelRatio: 1,
      addEventListener() {{}}
    }};
    global.document = {{
      createElement(tag) {{ return makeEl(tag, ''); }},
      createTextNode(txt) {{ return {{ textContent: String(txt) }}; }},
      createDocumentFragment() {{ return makeEl('fragment', ''); }},
      getElementById(id) {{ return getEl(id); }},
      querySelectorAll(sel) {{
        if (sel === '.use-case-btn') return useCaseBtns;
        return [];
      }}
    }};

    let pendingTimers = [];
    global.setTimeout = (fn) => {{ pendingTimers.push(fn); return pendingTimers.length; }};
    global.clearTimeout = () => {{ pendingTimers = []; }};
    global.setInterval = () => 1;
    global.clearInterval = () => {{}};

    let fetchCalls = [];
    let nextSimOverride = null;
    let shouldRejectFetch = false;
    let customFetchPromise = null;
    global.fetch = (url, opts) => {{
      const body = JSON.parse(opts.body);
      fetchCalls.push({{ url, body }});
      if (customFetchPromise) return customFetchPromise;
      if (shouldRejectFetch) return Promise.reject(new Error('Network offline'));
      const payloadToReturn = nextSimOverride || (body.use_case === 'fleet_routing' ? fleetSim : invSim);
      return Promise.resolve({{
        ok: true,
        json: () => Promise.resolve(payloadToReturn)
      }});
    }};

    // Run app.js initialization
    eval(appJs);

    async function runChecks() {{
      // 1. Trigger slider change (lead_time_delay=2, promo_spike_pct=30)
      getEl('slide-leadtime').value = '2';
      getEl('slide-promo').value = '30';
      const inputListeners = getEl('slide-leadtime').listeners['input'] || [];
      if (inputListeners.length === 0) throw new Error('Missing input listener on slide-leadtime');
      inputListeners[0]();

      // Flush debounce timer
      while (pendingTimers.length > 0) {{
        const fn = pendingTimers.shift();
        fn();
      }}
      await new Promise(r => setImmediate(r));

      const expectedCost = '$' + Math.round(invSim.champion.daily_cost).toLocaleString() + ' / day';
      if (getEl('val-champ-cost').textContent !== expectedCost) {{
        throw new Error('Expected ' + expectedCost + ' but got ' + getEl('val-champ-cost').textContent);
      }}
      if (getEl('whatif-resilience-text').textContent !== invSim.comparison.resilience_summary) {{
        throw new Error('Resilience summary mismatch');
      }}

      // 2. Verify zero-value coalescing (0 ?? fallback preserves 0.0 instead of fallback)
      nextSimOverride = {{
        baseline: {{ ...invSim.baseline, spoilage_units: 0, spoilage_cost: 0 }},
        champion: {{ ...invSim.champion, spoilage_units: 0, spoilage_cost: 0 }},
        comparison: invSim.comparison
      }};
      inputListeners[0]();
      while (pendingTimers.length > 0) pendingTimers.shift()();
      await new Promise(r => setImmediate(r));
      if (getEl('val-champ-spoil').textContent !== '0.0 units ($0)') {{
        throw new Error('Zero spoilage_units was overwritten by fallback: ' + getEl('val-champ-spoil').textContent);
      }}
      nextSimOverride = null;

      // 3. Switch use case to fleet_routing and verify live FleetRoutingDigitalTwin metrics apply
      useCaseBtns[1].listeners['click'][0]();
      while (pendingTimers.length > 0) pendingTimers.shift()();
      await new Promise(r => setImmediate(r));
      const expectedFleetCost = '$' + Math.round(fleetSim.champion.daily_cost).toLocaleString() + ' / day';
      if (getEl('val-champ-cost').textContent !== expectedFleetCost) {{
        throw new Error('Expected fleet cost ' + expectedFleetCost + ' but got ' + getEl('val-champ-cost').textContent);
      }}

      // 4. Verify offline fallback for fleet_routing uses 50 stops and select change event works
      shouldRejectFetch = true;
      getEl('whatif-sku').value = '1';
      const changeListeners = getEl('whatif-sku').listeners['change'] || [];
      if (changeListeners.length === 0) throw new Error('Missing change listener on whatif-sku');
      changeListeners[0]();
      while (pendingTimers.length > 0) pendingTimers.shift()();
      await new Promise(r => setImmediate(r));
      if (getEl('val-champ-orderup').textContent !== '50 stops (dynamic)') {{
        throw new Error('Expected 50 stops (dynamic) in offline fleet fallback, got ' + getEl('val-champ-orderup').textContent);
      }}
      shouldRejectFetch = false;

      // 5. Verify out-of-order stale response race condition guard (reqId !== whatIfReqSeq)
      let resolveSlow;
      customFetchPromise = new Promise(res => {{ resolveSlow = res; }});
      inputListeners[0]();
      while (pendingTimers.length > 0) pendingTimers.shift()();
      customFetchPromise = null;

      // Issue a newer request that resolves immediately with fleetSim
      inputListeners[0]();
      while (pendingTimers.length > 0) pendingTimers.shift()();
      await new Promise(r => setImmediate(r));

      // Now resolve the stale first request with bogus cost 999999; it must be ignored
      resolveSlow({{
        ok: true,
        json: () => Promise.resolve({{
          baseline: {{ ...fleetSim.baseline, daily_cost: 999999 }},
          champion: {{ ...fleetSim.champion, daily_cost: 999999 }},
          comparison: fleetSim.comparison
        }})
      }});
      await new Promise(r => setImmediate(r));
      if (getEl('val-champ-cost').textContent !== expectedFleetCost) {{
        throw new Error('Stale out-of-order response overwrote newer state: ' + getEl('val-champ-cost').textContent);
      }}

      console.log('ALL_JS_CHECKS_PASSED');
    }}
    runChecks().catch(err => {{ console.error(err); process.exit(1); }});
    """

    proc = subprocess.run(
        [node_path, "-e", node_harness],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ALL_JS_CHECKS_PASSED" in proc.stdout
