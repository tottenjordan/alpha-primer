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
    assert body["use_case"] == "inventory_replenishment"
    assert "Gen 30 Champion reduces supply chain cost" in body["summary"]
    assert "metrics" in body
    assert body["metrics"]["cost_reduction_pct"] > 30.0
    assert len(body["key_innovations"]) == 4
    assert headers["Content-Type"] == "application/json"
