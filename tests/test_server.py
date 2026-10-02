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
