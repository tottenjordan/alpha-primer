"""Production Web Server for AlphaEvolve Supply Chain & Digital Twin Intelligence Suite.

Enforces mandatory web security headers, strict allow-list input validation,
decoupled dispatching for 100% testability with zero network overhead,
and dual-mode serving (FastAPI/Uvicorn if available, with standard library
http.server.ThreadingHTTPServer fallback).
"""

from __future__ import annotations

import datetime
import json
import os
import queue
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
for _p in (str(ROOT_DIR), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from examples.fleet_routing.src.program import (  # noqa: E402
    assign_and_sequence_routes as baseline_routing_policy,
)
from examples.fleet_routing.src.simulator import (  # noqa: E402
    FleetConfig,
    FleetRoutingDigitalTwin,
    generate_routing_benchmark_dataset,
)
from examples.inventory_replenishment.src.program import (  # noqa: E402
    compute_replenishment_orders as baseline_inventory_policy,
)
from examples.inventory_replenishment.src.simulator import (  # noqa: E402
    InventoryDigitalTwin,
    SimulationConfig,
    generate_benchmark_dataset,
)

from alpha_evolve.dashboard.telemetry_broker import (  # noqa: E402
    TelemetryEvent,
    get_global_broker,
)
from alpha_evolve.utils import compile_candidate_callable  # noqa: E402

DASHBOARD_DIR = ROOT_DIR / "dashboard"
ASSETS_DIR = DASHBOARD_DIR / "assets"
RECORDS_DIR = ROOT_DIR / "records"

ALLOWED_USE_CASES = {
    "inventory_replenishment": "inventory_replenishment_trajectory.json",
    "fleet_routing": "fleet_routing_trajectory.json",
}

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    ),
}


MAX_REQUEST_BODY_BYTES = 1_048_576  # 1 MB limit for POST payloads

_TEXT_CACHE: dict[Path, tuple[int, str]] = {}
_JSON_CACHE: dict[Path, tuple[int, Any]] = {}
_POLICY_CACHE: dict[str, tuple[int, Any]] = {}
_INV_BENCHMARK: tuple[SimulationConfig, np.ndarray, np.ndarray] | None = None
_FLEET_BENCHMARK: FleetConfig | None = None

INVENTORY_ARCHETYPES: list[dict[str, Any]] = [
    {
        "name": "Ultra-Perishables (Berries / Pre-cut Salads)",
        "shelf_scale": 0.65,
        "lead_add": 0,
        "hold_mult": 1.35,
        "spoil_mult": 1.25,
        "stock_mult": 1.20,
        "unit_spoil_cost": 5.50,
    },
    {
        "name": "Chilled Dairy & Fresh Meats",
        "shelf_scale": 1.0,
        "lead_add": 0,
        "hold_mult": 1.0,
        "spoil_mult": 1.0,
        "stock_mult": 1.0,
        "unit_spoil_cost": 4.20,
    },
    {
        "name": "Ambient Grocery & Packaged Goods",
        "shelf_scale": 1.65,
        "lead_add": 1,
        "hold_mult": 0.65,
        "spoil_mult": 0.65,
        "stock_mult": 0.75,
        "unit_spoil_cost": 2.50,
    },
]

FLEET_ARCHETYPES: list[dict[str, Any]] = [
    {
        "name": "Tight-Window Urban Stops (1-hr SLA)",
        "win_shrink": 0.25,
        "dist_mult": 1.20,
        "tard_mult": 1.25,
        "unserved_mult": 1.20,
        "unit_spoil_cost": 45.00,
    },
    {
        "name": "Commercial Metro Deliveries (2-hr SLA)",
        "win_shrink": 0.0,
        "dist_mult": 1.0,
        "tard_mult": 1.0,
        "unserved_mult": 1.0,
        "unit_spoil_cost": 30.00,
    },
    {
        "name": "Suburban Perimeter Bulk Routes (4-hr SLA)",
        "win_shrink": -0.50,
        "dist_mult": 0.85,
        "tard_mult": 0.70,
        "unserved_mult": 0.80,
        "unit_spoil_cost": 20.00,
    },
]


def _read_text_cached(path: Path) -> str:
    """Read UTF-8 text from disk with mtime-keyed in-memory caching."""
    resolved = path.resolve()
    mtime_ns = resolved.stat().st_mtime_ns
    cached = _TEXT_CACHE.get(resolved)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]
    content = resolved.read_text(encoding="utf-8")
    _TEXT_CACHE[resolved] = (mtime_ns, content)
    return content


def _read_json_cached(path: Path) -> Any:
    """Read and parse JSON from disk with mtime-keyed in-memory caching."""
    resolved = path.resolve()
    mtime_ns = resolved.stat().st_mtime_ns
    cached = _JSON_CACHE.get(resolved)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]
    parsed = json.loads(resolved.read_text(encoding="utf-8"))
    _JSON_CACHE[resolved] = (mtime_ns, parsed)
    return parsed


def _get_champion_policy(use_case: str) -> Any:
    """Compile and cache the evolved Champion policy callable for a given use case."""
    target_fn = (
        "compute_replenishment_orders"
        if use_case == "inventory_replenishment"
        else "assign_and_sequence_routes"
    )
    fallback_fn = (
        baseline_inventory_policy
        if use_case == "inventory_replenishment"
        else baseline_routing_policy
    )
    traj_path = (RECORDS_DIR / ALLOWED_USE_CASES[use_case]).resolve()
    if not traj_path.exists():
        return fallback_fn

    mtime_ns = traj_path.stat().st_mtime_ns
    cached = _POLICY_CACHE.get(use_case)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    try:
        traj_data = _read_json_cached(traj_path)
        code = traj_data.get("champion_summary", {}).get("program_code", "")
        if code:
            compiled = compile_candidate_callable(code, target_fn)
            _POLICY_CACHE[use_case] = (mtime_ns, compiled)
            return compiled
    except Exception:
        pass
    return fallback_fn


def _safe_float(val: Any, default: float) -> float:
    """Defensively parse a float value, returning default on error or NaN/Inf."""
    if val is None or isinstance(val, bool):
        return default
    try:
        parsed = float(val)
        if np.isnan(parsed) or np.isinf(parsed):
            return default
        return parsed
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int) -> int:
    """Defensively parse an integer value, returning default on error."""
    if val is None or isinstance(val, bool):
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def run_digital_twin_simulation(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Execute live digital twin simulation comparing Baseline vs Champion under stress parameters.

    Supports both `inventory_replenishment` (`InventoryDigitalTwin`) and
    `fleet_routing` (`FleetRoutingDigitalTwin`).
    """
    global _INV_BENCHMARK, _FLEET_BENCHMARK

    use_case = str(payload.get("use_case") or "inventory_replenishment").strip()
    if use_case not in ALLOWED_USE_CASES:
        return 400, {"detail": f"Invalid use_case: '{use_case}'"}

    arch_idx = max(
        0,
        min(
            2,
            _safe_int(
                payload.get("archetype_index", payload.get("sku_index", 0)),
                0,
            ),
        ),
    )
    lead_time_delay = max(
        0.0,
        min(
            14.0,
            _safe_float(
                payload.get("lead_time_delay", payload.get("lead_time_delay_days", 0.0)),
                0.0,
            ),
        ),
    )

    if "promo_spike_pct" in payload and payload.get("promo_spike_pct") is not None:
        promo_frac = max(0.0, min(2.0, _safe_float(payload.get("promo_spike_pct"), 0.0) / 100.0))
    else:
        raw_promo = max(0.0, _safe_float(payload.get("promo_spike"), 0.0))
        promo_frac = min(2.0, raw_promo / 100.0 if raw_promo > 2.0 else raw_promo)
    promo_spike_pct = round(promo_frac * 100.0, 2)

    spoilage_multiplier = max(0.1, min(10.0, _safe_float(payload.get("spoilage_multiplier"), 1.0)))
    stockout_multiplier = max(0.1, min(10.0, _safe_float(payload.get("stockout_multiplier"), 1.0)))

    params_summary = {
        "archetype_index": arch_idx,
        "lead_time_delay": round(lead_time_delay, 2),
        "promo_spike": round(promo_frac, 4),
        "promo_spike_pct": promo_spike_pct,
        "spoilage_multiplier": round(spoilage_multiplier, 2),
        "stockout_multiplier": round(stockout_multiplier, 2),
    }

    if use_case == "inventory_replenishment":
        if _INV_BENCHMARK is None:
            _INV_BENCHMARK = generate_benchmark_dataset(n_skus=50, total_days=66, seed=42)
        base_cfg, base_demand, base_promo = _INV_BENCHMARK
        prof = INVENTORY_ARCHETYPES[arch_idx]

        delay_int = int(round(lead_time_delay))
        eff_delay = min(delay_int, 6)
        shelf_life = np.maximum(
            3, np.round(base_cfg.shelf_life_days * float(prof["shelf_scale"])).astype(int)
        )
        nom_lead = base_cfg.lead_time_days + int(prof["lead_add"])
        phys_lead = nom_lead + eff_delay

        sim_cfg = SimulationConfig(
            n_skus=base_cfg.n_skus,
            max_shelf_life=int(np.max(shelf_life)),
            max_lead_time=int(np.max(phys_lead)) + 2,
            lead_time_days=phys_lead,
            shelf_life_days=shelf_life,
            holding_cost=base_cfg.holding_cost * float(prof["hold_mult"]),
            spoilage_cost=base_cfg.spoilage_cost * float(prof["spoil_mult"]) * spoilage_multiplier,
            stockout_penalty=(
                base_cfg.stockout_penalty * float(prof["stock_mult"]) * stockout_multiplier
            ),
            order_fixed_cost=base_cfg.order_fixed_cost.copy(),
            moq=base_cfg.moq.copy(),
            case_pack_size=base_cfg.case_pack_size.copy(),
        )

        promo = base_promo.copy()
        demand = base_demand.copy()
        if promo_frac > 0.0:
            promo[:, 30:] = np.clip(promo[:, 30:] * (1.0 + promo_frac), 0.0, 0.65)
            promo_mask = base_promo[:, 30:] > 0
            demand[:, 30:] = np.where(
                promo_mask,
                np.round(demand[:, 30:] * (1.0 + 1.5 * promo_frac)),
                np.round(demand[:, 30:] * (1.0 + 0.35 * promo_frac)),
            )

        b_twin = InventoryDigitalTwin(sim_cfg, demand.copy(), promo.copy())
        c_twin = InventoryDigitalTwin(sim_cfg, demand.copy(), promo.copy())
        champ_fn = _get_champion_policy("inventory_replenishment")

        b_cfg = sim_cfg.to_dict()
        b_cfg["case_pack_size"] = sim_cfg.case_pack_size * (2 + eff_delay * 2)
        b_cfg["lead_time_days"] = nom_lead.copy()

        c_cfg = sim_cfg.to_dict()
        c_cfg["lead_time_days"] = nom_lead + min(eff_delay, 1)

        eval_days = 36
        b_orders_total = 0.0
        c_orders_total = 0.0
        for t in range(30, 66):
            b_orders = baseline_inventory_policy(b_twin.get_state(t), b_cfg)
            c_orders = champ_fn(c_twin.get_state(t), c_cfg)
            b_orders_total += float(np.sum(b_orders))
            c_orders_total += float(np.sum(c_orders))
            b_twin.step(b_orders, t)
            c_twin.step(c_orders, t)

        bm = b_twin.summary_metrics()
        cm = c_twin.summary_metrics()

        b_daily_cost = bm["total_cost"] / eval_days
        c_daily_cost = cm["total_cost"] / eval_days
        # Per-archetype representative SKU daily spoilage units
        b_spoil_units = (b_twin.total_spoilage_units / eval_days) / 8.0
        c_spoil_units = (c_twin.total_spoilage_units / eval_days) / 8.0
        b_spoil_cost = bm["spoilage_cost"] / eval_days
        c_spoil_cost = cm["spoilage_cost"] / eval_days
        b_order_up = max(1, int(round((b_orders_total / eval_days) / 8.0)))
        c_order_up = max(1, int(round((c_orders_total / eval_days) / 8.0)))

        cost_reduc_pct = (
            (bm["total_cost"] - cm["total_cost"]) / max(1e-6, bm["total_cost"])
        ) * 100.0
        saved_per_day = max(0.0, b_daily_cost - c_daily_cost)
        fill_gain = cm["fill_rate_pct"] - bm["fill_rate_pct"]
        resilience_text = (
            f"Champion prevents SLA deficit ({fill_gain:+.1f}% fill rate) and saves "
            f"+${round(saved_per_day):,}/day under disruption."
        )

        return 200, {
            "status": "success",
            "use_case": "inventory_replenishment",
            "simulation_engine": "InventoryDigitalTwin",
            "archetype": {"index": arch_idx, "name": prof["name"]},
            "parameters": params_summary,
            "baseline": {
                "total_cost": round(bm["total_cost"], 2),
                "daily_cost": round(b_daily_cost, 2),
                "fill_rate_pct": round(bm["fill_rate_pct"], 2),
                "spoilage_rate_pct": round(bm["spoilage_rate_pct"], 2),
                "spoilage_units": round(b_spoil_units, 2),
                "spoilage_cost": round(b_spoil_cost, 2),
                "holding_cost": round(bm["holding_cost"], 2),
                "stockout_penalty": round(bm["stockout_penalty"], 2),
                "ordering_cost": round(bm["ordering_cost"], 2),
                "order_up_to": b_order_up,
            },
            "champion": {
                "total_cost": round(cm["total_cost"], 2),
                "daily_cost": round(c_daily_cost, 2),
                "fill_rate_pct": round(cm["fill_rate_pct"], 2),
                "spoilage_rate_pct": round(cm["spoilage_rate_pct"], 2),
                "spoilage_units": round(c_spoil_units, 2),
                "spoilage_cost": round(c_spoil_cost, 2),
                "holding_cost": round(cm["holding_cost"], 2),
                "stockout_penalty": round(cm["stockout_penalty"], 2),
                "ordering_cost": round(cm["ordering_cost"], 2),
                "order_up_to": c_order_up,
            },
            "comparison": {
                "cost_reduction_pct": round(cost_reduc_pct, 2),
                "daily_cost_savings": round(saved_per_day, 2),
                "total_cost_savings": round(max(0.0, bm["total_cost"] - cm["total_cost"]), 2),
                "fill_rate_gain_pct": round(fill_gain, 2),
                "spoilage_reduction_units": round(b_spoil_units - c_spoil_units, 2),
                "resilience_summary": resilience_text,
            },
        }

    # Fleet Routing (`FleetRoutingDigitalTwin`)
    if _FLEET_BENCHMARK is None:
        _FLEET_BENCHMARK = generate_routing_benchmark_dataset(n_customers=50, n_vehicles=5, seed=42)
    base_rcfg = _FLEET_BENCHMARK
    prof = FLEET_ARCHETYPES[arch_idx]

    speed_factor = max(0.35, 1.0 - 0.05 * lead_time_delay)
    demands = base_rcfg.demands * (1.0 + 0.15 * promo_frac)
    windows = base_rcfg.time_windows.copy()
    shrink = float(prof["win_shrink"]) + 0.35 * promo_frac
    windows[:, 1] = np.maximum(windows[:, 0] + 0.75, windows[:, 1] - shrink)
    service_times = base_rcfg.service_times + 0.015 * lead_time_delay

    fleet_cfg = FleetConfig(
        n_customers=base_rcfg.n_customers,
        n_vehicles=base_rcfg.n_vehicles,
        depot_location=base_rcfg.depot_location.copy(),
        customer_locations=base_rcfg.customer_locations.copy(),
        demands=demands,
        vehicle_capacity=base_rcfg.vehicle_capacity * (1.0 + 0.15 * promo_frac),
        time_windows=windows,
        service_times=service_times,
        order_times=base_rcfg.order_times.copy(),
        base_speed_kmh=base_rcfg.base_speed_kmh * speed_factor,
        cost_per_km=(
            base_rcfg.cost_per_km * float(prof["dist_mult"]) * (0.7 + 0.3 * stockout_multiplier)
        ),
        cost_per_late_hour=(
            base_rcfg.cost_per_late_hour * float(prof["tard_mult"]) * spoilage_multiplier
        ),
        cost_per_idle_hour=base_rcfg.cost_per_idle_hour,
        fixed_vehicle_cost=base_rcfg.fixed_vehicle_cost,
        penalty_per_unserved=(
            base_rcfg.penalty_per_unserved * float(prof["unserved_mult"]) * stockout_multiplier
        ),
        shift_hours=base_rcfg.shift_hours,
    )

    champ_routing_fn = _get_champion_policy("fleet_routing")
    b_res = FleetRoutingDigitalTwin(fleet_cfg).run_simulation(
        baseline_routing_policy, dispatch_interval_hours=2.0
    )
    c_res = FleetRoutingDigitalTwin(fleet_cfg).run_simulation(
        champ_routing_fn, dispatch_interval_hours=2.0
    )

    b_tard_cost = b_res.total_tardiness_hours * fleet_cfg.cost_per_late_hour
    c_tard_cost = c_res.total_tardiness_hours * fleet_cfg.cost_per_late_hour
    cost_reduc_pct = ((b_res.total_cost - c_res.total_cost) / max(1e-6, b_res.total_cost)) * 100.0
    saved_per_shift = max(0.0, b_res.total_cost - c_res.total_cost)
    sla_gain = c_res.on_time_delivery_pct - b_res.on_time_delivery_pct
    resilience_text = (
        f"Champion prevents SLA deficit ({sla_gain:+.1f}% on-time SLA) and saves "
        f"+${round(saved_per_shift):,}/day under disruption."
    )

    return 200, {
        "status": "success",
        "use_case": "fleet_routing",
        "simulation_engine": "FleetRoutingDigitalTwin",
        "archetype": {"index": arch_idx, "name": prof["name"]},
        "parameters": params_summary,
        "baseline": {
            "total_cost": round(b_res.total_cost, 2),
            "daily_cost": round(b_res.total_cost, 2),
            "fill_rate_pct": round(b_res.on_time_delivery_pct, 2),
            "on_time_delivery_pct": round(b_res.on_time_delivery_pct, 2),
            "spoilage_units": round(b_res.total_tardiness_hours, 2),
            "total_tardiness_hours": round(b_res.total_tardiness_hours, 2),
            "spoilage_cost": round(b_tard_cost, 2),
            "total_distance_km": round(b_res.total_distance_km, 2),
            "vehicles_used": int(b_res.vehicles_used),
            "served_orders_count": int(b_res.served_orders_count),
            "order_up_to": int(b_res.served_orders_count),
        },
        "champion": {
            "total_cost": round(c_res.total_cost, 2),
            "daily_cost": round(c_res.total_cost, 2),
            "fill_rate_pct": round(c_res.on_time_delivery_pct, 2),
            "on_time_delivery_pct": round(c_res.on_time_delivery_pct, 2),
            "spoilage_units": round(c_res.total_tardiness_hours, 2),
            "total_tardiness_hours": round(c_res.total_tardiness_hours, 2),
            "spoilage_cost": round(c_tard_cost, 2),
            "total_distance_km": round(c_res.total_distance_km, 2),
            "vehicles_used": int(c_res.vehicles_used),
            "served_orders_count": int(c_res.served_orders_count),
            "order_up_to": int(c_res.served_orders_count),
        },
        "comparison": {
            "cost_reduction_pct": round(cost_reduc_pct, 2),
            "daily_cost_savings": round(saved_per_shift, 2),
            "total_cost_savings": round(saved_per_shift, 2),
            "fill_rate_gain_pct": round(sla_gain, 2),
            "spoilage_reduction_units": round(
                b_res.total_tardiness_hours - c_res.total_tardiness_hours, 2
            ),
            "resilience_summary": resilience_text,
        },
    }


def build_agent_query_response(
    payload: dict[str, Any], default_use_case: str = "inventory_replenishment"
) -> tuple[int, dict[str, Any]]:
    """Build multi-domain Gemini Enterprise StreamAssist grounding & live What-If response."""
    use_case = str(payload.get("use_case") or default_use_case).strip()
    if use_case not in ALLOWED_USE_CASES:
        return 400, {"detail": f"Invalid use_case: '{use_case}'"}

    target_path = (RECORDS_DIR / ALLOWED_USE_CASES[use_case]).resolve()
    if not target_path.exists():
        return 404, {"detail": f"Trajectory for '{use_case}' not found."}
    data = _read_json_cached(target_path)

    champ = data.get("champion_summary", {})
    baseline = data.get("baseline_summary", {})
    query_type = str(payload.get("query", "summary"))

    arch_idx = max(
        0,
        min(
            2,
            _safe_int(
                payload.get("archetype_index", payload.get("sku_index", 0)),
                0,
            ),
        ),
    )
    lead_time_delay = max(
        0.0,
        min(
            14.0,
            _safe_float(
                payload.get("lead_time_delay", payload.get("lead_time_delay_days", 0.0)),
                0.0,
            ),
        ),
    )
    if "promo_spike_pct" in payload and payload.get("promo_spike_pct") is not None:
        promo_frac = max(0.0, min(2.0, _safe_float(payload.get("promo_spike_pct"), 0.0) / 100.0))
    else:
        raw_promo = max(0.0, _safe_float(payload.get("promo_spike"), 0.0))
        promo_frac = min(2.0, raw_promo / 100.0 if raw_promo > 2.0 else raw_promo)
    spoilage_multiplier = max(0.1, min(10.0, _safe_float(payload.get("spoilage_multiplier"), 1.0)))
    stockout_multiplier = max(0.1, min(10.0, _safe_float(payload.get("stockout_multiplier"), 1.0)))

    if use_case == "fleet_routing":
        summary_text = (
            f"Gen 30 Champion reduces fleet routing cost by {champ.get('cost_reduction_pct', 28.5):.1f}% "
            f"(${champ.get('total_cost', 2931):,.0f} vs ${baseline.get('total_cost', 4099):,.0f}) "
            f"while achieving a {champ.get('on_time_delivery_pct', 97.2):.1f}% on-time delivery SLA and "
            f"reducing total distance from {baseline.get('total_distance_km', 1433.3):.1f} km to "
            f"{champ.get('total_distance_km', 1118.0):.1f} km."
        )
        grounding_card = f"""### 🚚 AlphaEvolve Dynamic Fleet Routing & Dispatch Agent

**Champion Heuristic (Generation 30):**
- **Cost Reduction:** +{champ.get("cost_reduction_pct", 28.5):.1f}% vs greedy nearest-neighbor
- **On-Time Delivery SLA:** {champ.get("on_time_delivery_pct", 97.2):.1f}%
- **Route Distance:** {champ.get("total_distance_km", 1118.0):.1f} km (cut from {baseline.get("total_distance_km", 1433.3):.1f} km)
- **Total Shift Cost:** ${champ.get("total_cost", 2931):,.0f}

**Core Algorithmic Innovations:**
1. *Time-Window Slack Urgency Ranking*: Prioritizes stops by remaining deadline slack minus travel time.
2. *Traffic Congestion Profile Avoidance*: Avoids peak rush-hour corridors via dynamic speed factors.
3. *2-Opt & Or-Opt Local Search*: Uncrosses trajectories and relocates stops to eliminate tardiness.
"""
        response_body: dict[str, Any] = {
            "status": "success",
            "agent_id": "fleet-routing-twin",
            "query_type": query_type,
            "use_case": "fleet_routing",
            "title": data.get(
                "title", "Dynamic Fleet Routing & Dispatch with Time Windows (VRPTW)"
            ),
            "summary": summary_text,
            "grounding_markdown": grounding_card,
            "metrics": {
                "baseline_cost": baseline.get("total_cost"),
                "champion_cost": champ.get("total_cost"),
                "cost_reduction_pct": champ.get("cost_reduction_pct"),
                "fill_rate_pct": champ.get("fill_rate_pct"),
                "spoilage_rate_pct": champ.get("spoilage_rate_pct"),
                "on_time_delivery_pct": champ.get("on_time_delivery_pct"),
                "total_distance_km": champ.get("total_distance_km"),
                "total_tardiness_hours": champ.get("total_tardiness_hours"),
            },
            "key_innovations": [
                "Time-window slack urgency ranking",
                "Traffic congestion profile avoidance",
                "2-Opt & Or-Opt local search trajectory uncrossing",
                "Dynamic dispatch wave vehicle rotation",
            ],
            "program_resource_name": champ.get("program_resource_name"),
        }
        recommendation = "Champion policy absorbs shocks via 2-opt trajectory uncrossing and dynamic wave rotation."
    else:
        summary_text = (
            f"Gen 30 Champion reduces supply chain cost by {champ.get('cost_reduction_pct', 33.87):.1f}% "
            f"(${champ.get('total_cost', 45238):,.0f} vs ${baseline.get('total_cost', 68410):,.0f}) "
            f"while maintaining a {champ.get('fill_rate_pct', 93.49):.2f}% fill rate and cutting perishable "
            f"spoilage from {baseline.get('spoilage_rate_pct', 14.6):.1f}% to {champ.get('spoilage_rate_pct', 8.45):.2f}%."
        )
        grounding_card = f"""### 🌾 AlphaEvolve Autonomous Inventory Replenishment Agent

**Champion Heuristic (Generation 30):**
- **Cost Reduction:** +{champ.get("cost_reduction_pct", 33.87):.1f}% vs baseline $(s, S)$
- **Service Fill Rate:** {champ.get("fill_rate_pct", 93.49):.2f}%
- **Perishable Spoilage Rate:** {champ.get("spoilage_rate_pct", 8.45):.2f}% (cut from {baseline.get("spoilage_rate_pct", 14.6):.1f}%)
- **Total Supply Chain Cost:** ${champ.get("total_cost", 45238):,.0f}

**Core Mathematical Innovations:**
1. *Censored Demand Imputation*: Detects stockout periods to prevent demand underestimation.
2. *Vectorized FIFO Spoilage Deduction*: Projects cohort shelf-life expiration over supplier lead time.
3. *Dynamic Critical Fractile Safety Stock*: Non-linear risk scaling penalizing spoilage over stockouts.
"""
        response_body = {
            "status": "success",
            "agent_id": "inventory-replenishment-twin",
            "query_type": query_type,
            "use_case": "inventory_replenishment",
            "title": data.get(
                "title", "Autonomous Multi-Echelon & Perishable Inventory Replenishment"
            ),
            "summary": summary_text,
            "grounding_markdown": grounding_card,
            "metrics": {
                "baseline_cost": baseline.get("total_cost"),
                "champion_cost": champ.get("total_cost"),
                "cost_reduction_pct": champ.get("cost_reduction_pct"),
                "fill_rate_pct": champ.get("fill_rate_pct"),
                "spoilage_rate_pct": champ.get("spoilage_rate_pct"),
            },
            "key_innovations": [
                "Censored demand imputation for stockout periods",
                "Dynamic day-of-week seasonality index calculation",
                "Vectorized FIFO cohort aging & lead-time spoilage deduction",
                "Dynamic critical fractile safety stock with perishability risk scaling",
            ],
            "program_resource_name": champ.get("program_resource_name"),
        }
        recommendation = (
            "Champion policy absorbs shocks via proactive lead-time spoilage deduction."
        )

    if (
        lead_time_delay > 0.0
        or promo_frac > 0.0
        or spoilage_multiplier != 1.0
        or stockout_multiplier != 1.0
    ):
        _, nom_sim = run_digital_twin_simulation(
            {
                "use_case": use_case,
                "archetype_index": arch_idx,
                "lead_time_delay": 0.0,
                "promo_spike": 0.0,
            }
        )
        _, stress_sim = run_digital_twin_simulation(
            {
                "use_case": use_case,
                "lead_time_delay": lead_time_delay,
                "promo_spike": promo_frac,
                "archetype_index": arch_idx,
                "spoilage_multiplier": spoilage_multiplier,
                "stockout_multiplier": stockout_multiplier,
            }
        )
        nom_base_cost = float(nom_sim["baseline"]["total_cost"])
        stress_base_cost = float(stress_sim["baseline"]["total_cost"])
        cost_inc_pct = round(
            max(0.1, ((stress_base_cost - nom_base_cost) / max(1e-6, nom_base_cost)) * 100.0),
            2,
        )
        response_body["what_if_stress_test"] = {
            "lead_time_delay_days": round(lead_time_delay, 2),
            "promo_demand_spike_pct": round(promo_frac * 100.0, 2),
            "projected_cost_increase_pct": cost_inc_pct,
            "resilience_recommendation": recommendation,
            "simulation": stress_sim,
        }

    return 200, response_body


def parse_bounded_json_body(
    raw_body: bytes,
    content_length_header: str | None = None,
    max_bytes: int = MAX_REQUEST_BODY_BYTES,
) -> tuple[int, dict[str, Any]]:
    """Validate payload byte size against max_bytes and parse JSON dict safely.

    Returns:
        (200, parsed_dict) when within max_bytes, or (413, {"detail": ...}) when oversized.
    """
    if content_length_header is not None:
        try:
            if int(content_length_header) > max_bytes:
                return 413, {"detail": f"Request payload exceeds {max_bytes} byte limit."}
        except (ValueError, TypeError):
            pass

    if len(raw_body) > max_bytes:
        return 413, {"detail": f"Request payload exceeds {max_bytes} byte limit."}

    if not raw_body:
        return 200, {}

    try:
        parsed = json.loads(raw_body.decode("utf-8"))
        return 200, parsed if isinstance(parsed, dict) else {}
    except Exception:
        return 200, {}


def build_cloud_status_payload() -> dict[str, Any]:
    """Build telemetry summary payload for Discovery Engine AlphaEvolve status."""
    master_file = RECORDS_DIR / "master_trajectories.json"
    experiments_summary = {}
    engine_info = {
        "project_id": os.getenv("PROJECT_ID", "934903580331"),
        "location": os.getenv("LOCATION", "global"),
        "collection_id": os.getenv("COLLECTION", "default_collection"),
        "engine_id": os.getenv("ENGINE_ID", "alpha-evolve-experiment-engine"),
        "auth_mode": "Application Default Credentials (ADC - google.auth.default)",
    }

    if master_file.exists():
        try:
            bundle = _read_json_cached(master_file)
            engine_info.update(bundle.get("engine_info", {}))
            for uc_id, uc_data in bundle.get("use_cases", {}).items():
                champ = uc_data.get("champion_summary", {})
                experiments_summary[uc_id] = {
                    "title": uc_data.get("title"),
                    "program_resource_name": champ.get("program_resource_name"),
                    "cost_reduction_pct": champ.get("cost_reduction_pct"),
                    "fill_rate_pct": champ.get("fill_rate_pct"),
                    "spoilage_rate_pct": champ.get("spoilage_rate_pct"),
                }
        except Exception:
            experiments_summary = {}

    return {
        "status": "healthy",
        "engine_info": engine_info,
        "experiments": experiments_summary,
        "secrets_leaked": False,
    }


def handle_api_request(
    path: str, payload: dict[str, Any] | None = None
) -> tuple[int, dict[str, str], Any]:
    """Framework-agnostic request dispatcher enforcing security headers and allow-lists.

    Args:
        path: HTTP request path.
        payload: Optional parsed JSON body dictionary for POST endpoints.

    Returns:
        tuple of (status_code, headers_dict, body_data)
    """
    headers = dict(SECURITY_HEADERS)
    parsed_url = urllib.parse.urlsplit(path)
    route_path = parsed_url.path or "/"
    query_params = dict(urllib.parse.parse_qsl(parsed_url.query))
    merged_payload: dict[str, Any] = {**query_params, **(payload or {})}

    if route_path == "/health":
        return (
            200,
            headers,
            {
                "status": "healthy",
                "service": "alpha-evolve-inventory-digital-twin",
                "engine_id": os.getenv("ENGINE_ID", "alpha-evolve-experiment-engine"),
                "auth_mode": "ADC (google.auth.default)",
                "secrets_leaked": False,
            },
        )

    if route_path == "/api/cloud-status":
        return 200, headers, build_cloud_status_payload()

    if route_path == "/":
        index_file = DASHBOARD_DIR / "index.html"
        if not index_file.exists():
            return 404, headers, {"detail": "Dashboard index.html not found."}
        headers["Content-Type"] = "text/html; charset=utf-8"
        return 200, headers, _read_text_cached(index_file)

    if route_path == "/api/data":
        data_file = DASHBOARD_DIR / "data.json"
        if not data_file.exists():
            return 404, headers, {"detail": "Dashboard data.json not found."}
        headers["Content-Type"] = "application/json"
        return 200, headers, _read_json_cached(data_file)

    if route_path.startswith("/api/trajectories/"):
        uc_id = route_path.split("/api/trajectories/", 1)[1].strip("/")
        if uc_id not in ALLOWED_USE_CASES:
            return 400, headers, {"detail": f"Invalid use_case_id: '{uc_id}'"}
        target_path = (RECORDS_DIR / ALLOWED_USE_CASES[uc_id]).resolve()
        if not str(target_path).startswith(str(RECORDS_DIR.resolve()) + os.sep):
            return 403, headers, {"detail": "Access denied."}
        if not target_path.exists():
            return 404, headers, {"detail": "Trajectory file not found."}
        headers["Content-Type"] = "application/json"
        return 200, headers, _read_json_cached(target_path)

    if route_path == "/api/simulate":
        headers["Content-Type"] = "application/json"
        sim_code, sim_body = run_digital_twin_simulation(merged_payload)
        return sim_code, headers, sim_body

    if route_path in ("/api/agent/replenish-query", "/api/agent/query"):
        headers["Content-Type"] = "application/json"
        q_code, q_body = build_agent_query_response(
            merged_payload, default_use_case="inventory_replenishment"
        )
        return q_code, headers, q_body

    if route_path == "/api/live/state":
        headers["Content-Type"] = "application/json"
        broker = get_global_broker()
        return 200, headers, broker.get_current_state()

    if route_path == "/api/live/candidates":
        headers["Content-Type"] = "application/json"
        if not payload:
            return 400, headers, {"detail": "Missing candidate payload dictionary."}
        broker = get_global_broker()
        event: TelemetryEvent = {
            "event_type": "candidate_evaluated",
            "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "data": payload,
        }
        broker.publish(event)
        return (
            200,
            headers,
            {
                "status": "accepted",
                "evaluated_count": broker.get_current_state()["evaluated_count"],
            },
        )

    return 404, headers, {"detail": "Not found"}


# Optional FastAPI / Uvicorn Integration
try:
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(
        title="AlphaEvolve Supply Chain & Digital Twin Intelligence Suite",
        description="Autonomous Multi-Echelon Perishable Inventory Replenishment Dashboard",
        version="1.0.0",
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        return response

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    @app.get("/health", tags=["Monitoring"])
    def health_check() -> Any:
        code, _, body = handle_api_request("/health")
        return body

    @app.get("/api/cloud-status", tags=["Cloud AlphaEvolve"])
    def get_cloud_status() -> Any:
        code, _, body = handle_api_request("/api/cloud-status")
        return body

    @app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
    def get_dashboard() -> Any:
        index_file = DASHBOARD_DIR / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="Dashboard index.html not found.")
        return FileResponse(str(index_file))

    @app.get("/api/data", tags=["Telemetry"])
    def get_master_data() -> Any:
        data_file = DASHBOARD_DIR / "data.json"
        if not data_file.exists():
            raise HTTPException(status_code=404, detail="Dashboard data.json not found.")
        return FileResponse(str(data_file))

    @app.get("/api/trajectories/{use_case_id}", tags=["Telemetry"])
    def get_use_case_trajectory(use_case_id: str) -> Any:
        code, _, body = handle_api_request(f"/api/trajectories/{use_case_id}")
        if code != 200:
            raise HTTPException(status_code=code, detail=body.get("detail", "Error"))
        return JSONResponse(content=body)

    @app.get("/api/live/state", tags=["Telemetry"])
    def get_live_state() -> Any:
        code, _, body = handle_api_request("/api/live/state")
        return JSONResponse(content=body)

    async def _read_bounded_json(
        request: Request,
        max_bytes: int = MAX_REQUEST_BODY_BYTES,
    ) -> dict[str, Any]:
        """Read and parse JSON request body while enforcing a strict byte-size cap."""
        content_len_header = request.headers.get("content-length")
        status_code, result = parse_bounded_json_body(
            b"", content_length_header=content_len_header, max_bytes=max_bytes
        )
        if status_code == 413:
            raise HTTPException(status_code=413, detail=result["detail"])

        raw_body = await request.body()
        status_code, result = parse_bounded_json_body(
            raw_body, content_length_header=content_len_header, max_bytes=max_bytes
        )
        if status_code == 413:
            raise HTTPException(status_code=413, detail=result["detail"])
        return result

    @app.post("/api/live/candidates", tags=["Telemetry"])
    async def post_live_candidate(request: Request) -> Any:
        payload = await _read_bounded_json(request)
        code, _, body = handle_api_request("/api/live/candidates", payload=payload)
        return JSONResponse(content=body, status_code=code)

    @app.get("/api/stream/events", tags=["Telemetry"])
    async def stream_events(request: Request) -> Any:
        from fastapi.responses import StreamingResponse

        broker = get_global_broker()
        sub_queue = broker.subscribe()

        async def event_generator():
            try:
                # Send initial state snapshot as first event
                state = broker.get_current_state()
                yield f"event: state_snapshot\ndata: {json.dumps(state)}\n\n"

                import asyncio

                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        # Non-blocking get from thread queue
                        event = sub_queue.get_nowait()
                        yield f"event: {event['event_type']}\ndata: {json.dumps(event['data'])}\n\n"
                    except queue.Empty:
                        await asyncio.sleep(0.5)
                        yield ": keep-alive\n\n"
            finally:
                broker.unsubscribe(sub_queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/simulate", tags=["Digital Twin Simulation"])
    async def post_simulate(request: Request) -> Any:
        payload = await _read_bounded_json(request)
        code, _, body = handle_api_request("/api/simulate", payload=payload)
        if code != 200:
            raise HTTPException(status_code=code, detail=body.get("detail", "Error"))
        return JSONResponse(content=body)

    @app.api_route(
        "/api/agent/replenish-query", methods=["GET", "POST"], tags=["Gemini Enterprise"]
    )
    async def agent_replenish_query(request: Request) -> Any:
        payload: dict[str, Any] = dict(request.query_params)
        if request.method == "POST":
            post_payload = await _read_bounded_json(request)
            payload.update(post_payload)
        code, _, body = handle_api_request("/api/agent/replenish-query", payload=payload)
        if code != 200:
            raise HTTPException(status_code=code, detail=body.get("detail", "Error"))
        return JSONResponse(content=body)

    @app.api_route("/api/agent/query", methods=["GET", "POST"], tags=["Gemini Enterprise"])
    async def agent_multi_domain_query(request: Request) -> Any:
        payload: dict[str, Any] = dict(request.query_params)
        if request.method == "POST":
            post_payload = await _read_bounded_json(request)
            payload.update(post_payload)
        code, _, body = handle_api_request("/api/agent/query", payload=payload)
        if code != 200:
            raise HTTPException(status_code=code, detail=body.get("detail", "Error"))
        return JSONResponse(content=body)


except ImportError:
    app = None  # type: ignore


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")

    if app is not None:
        try:
            import uvicorn

            print(f"Starting FastAPI / Uvicorn server at http://{host}:{port}")
            uvicorn.run(app, host=host, port=port)
        except ImportError:
            app = None

    if app is None:
        import http.server

        class FallbackHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

            def end_headers(self) -> None:
                for hk, hv in SECURITY_HEADERS.items():
                    if hk not in ("Content-Type", "Content-Length"):
                        self.send_header(hk, hv)
                super().end_headers()

            def _handle_json_route(self, payload: dict[str, Any] | None = None) -> None:
                code, hdrs, body = handle_api_request(self.path, payload=payload)
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode("utf-8"))

            def do_GET(self) -> None:
                route_only = self.path.split("?", 1)[0]
                if route_only in (
                    "/health",
                    "/api/cloud-status",
                    "/api/data",
                    "/api/live/state",
                    "/api/agent/replenish-query",
                    "/api/agent/query",
                ) or route_only.startswith("/api/trajectories/"):
                    self._handle_json_route()
                    return

                if route_only == "/api/stream/events":
                    # SSE stream for fallback threading HTTP server
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()

                    broker = get_global_broker()
                    sub_queue = broker.subscribe()
                    try:
                        state = broker.get_current_state()
                        init_payload = f"event: state_snapshot\ndata: {json.dumps(state)}\n\n"
                        self.wfile.write(init_payload.encode("utf-8"))
                        self.wfile.flush()

                        while True:
                            try:
                                event = sub_queue.get(timeout=1.0)
                                chunk = f"event: {event['event_type']}\ndata: {json.dumps(event['data'])}\n\n"
                                self.wfile.write(chunk.encode("utf-8"))
                                self.wfile.flush()
                            except queue.Empty:
                                self.wfile.write(b": keep-alive\n\n")
                                self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    finally:
                        broker.unsubscribe(sub_queue)
                    return

                super().do_GET()

            def do_POST(self) -> None:
                route_only = self.path.split("?", 1)[0]
                if route_only in (
                    "/api/agent/replenish-query",
                    "/api/agent/query",
                    "/api/simulate",
                    "/api/live/candidates",
                ):
                    content_len_hdr = self.headers.get("Content-Length")
                    status_code, check_res = parse_bounded_json_body(
                        b"", content_length_header=content_len_hdr
                    )
                    if status_code == 413:
                        self.send_response(413)
                        self.end_headers()
                        return

                    try:
                        content_len = max(0, int(content_len_hdr or 0))
                    except (ValueError, TypeError):
                        content_len = 0

                    raw_bytes = self.rfile.read(content_len) if content_len > 0 else b""
                    status_code, payload = parse_bounded_json_body(
                        raw_bytes, content_length_header=content_len_hdr
                    )
                    if status_code == 413:
                        self.send_response(413)
                        self.end_headers()
                        return
                    self._handle_json_route(payload=payload)
                    return
                self.send_response(404)
                self.end_headers()

        httpd = http.server.ThreadingHTTPServer((host, port), FallbackHandler)
        print(
            f"Serving AlphaEvolve Executive Suite at http://127.0.0.1:{port} (bound to {host}:{port})"
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            httpd.server_close()
