# Real-Time Candidate Evaluation Telemetry & Live Dashboard

This note documents the architecture, wire protocols, and operational workflows for streaming live AlphaEvolve candidate evaluations directly to the executive dashboard in real time.

---

## Architecture Overview

Prior to this implementation, the executive dashboard functioned solely as an archive visualizer, reading pre-generated static trajectory datasets (`dashboard/data.json` or `records/inventory_replenishment_trajectory.json`).

The real-time streaming system introduces an event-driven telemetry pipeline:

```
[Evolution Controller / Worker Pool]
                │
                ▼ (Publish events)
    [LiveTelemetryBroker (Singleton)]
          │                     │
          ▼ (Ring Buffer)       ▼ (Subscriber Queues)
    [Recent 500 Events]    [Server HTTP Workers]
                                │
                                ▼ Server-Sent Events (text/event-stream)
                    [Browser Executive Dashboard (EventSource)]
```

### Components

1. **`alpha_evolve.dashboard.telemetry_broker.LiveTelemetryBroker`**:
   - A thread-safe, in-process publish/subscribe message broker.
   - Maintains an in-memory ring buffer (default capacity: 500 events) for historical catch-up on new client connections.
   - Provides thread-safe fanout to multiple concurrent subscriber queues (`queue.Queue`).
   - Tracks live summary statistics: `status`, `evaluated_count`, `best_score`, and `latest_candidate`.
   - Accessible via singleton `get_global_broker()`.

2. **Server Streaming Endpoints (`server.py`)**:
   - Dual-framework support: Works seamlessly with FastAPI (`StreamingResponse`) or fallback `ThreadingHTTPServer` (`text/event-stream` chunked response).
   - `GET /api/stream/events`: Server-Sent Events stream delivering JSON-encoded events (`state_snapshot`, `run_started`, `candidate_evaluated`, `run_completed`) with periodic `:keep-alive` comments.
   - `GET /api/live/state`: Returns JSON snapshot of current broker state and recent events.
   - `POST /api/live/candidates`: Ingestion endpoint allowing out-of-process workers or external runners to push evaluation events directly via HTTP.

3. **Client-Side Live Visualization (`dashboard/index.html` & `build_dashboard.py`)**:
   - Built with strict **Safe DOM** standards (zero `innerHTML`).
   - Browser `EventSource("/api/stream/events")` listener:
     - Header status pill transitions between `LIVE STREAMING (SSE)` and `ARCHIVE DATA (OFFLINE)`.
     - Scrubber dynamic range updates: Scrubber maximum dynamically expands as candidates are evaluated.
     - Live 2D Pareto Frontier: Evaluated candidates are dynamically added to the non-dominated envelope and plotted on the Canvas.
     - Dynamic Milestone Ribbon: When a new best score is acquired, a star/trophy node is dynamically prepended/appended with click-to-scrub capabilities.
     - Toast alerts: Displays transient notifications for candidate evaluations, improvements, and champion breakthroughs.

---

## Wire Event Schemas

All Server-Sent Events are formatted as `data: <json>\n\n`.

### 1. `state_snapshot`
Sent immediately upon client connection:
```json
{
  "event_type": "state_snapshot",
  "payload": {
    "status": "running",
    "evaluated_count": 12,
    "best_score": 0.428,
    "latest_candidate": {
      "candidate_id": "cand_12",
      "generation": 12,
      "score": 0.428,
      "metrics": {"cost_reduction_pct": 31.4, "fill_rate": 0.985},
      "evolve_block": "def replenish(...): ...",
      "execution_time_ms": 142.5,
      "is_best": true
    }
  },
  "timestamp": 1727560000.123
}
```

### 2. `run_started`
Published when an experiment begins:
```json
{
  "event_type": "run_started",
  "payload": {
    "experiment_id": "exp_replenishment_01",
    "max_programs": 25,
    "evaluator": "inventory_replenishment"
  },
  "timestamp": 1727560001.000
}
```

### 3. `candidate_evaluated`
Published each time a candidate completes evaluation:
```json
{
  "event_type": "candidate_evaluated",
  "payload": {
    "candidate_id": "cand_05",
    "generation": 5,
    "score": 0.385,
    "metrics": {
      "cost_reduction_pct": 28.2,
      "service_fill_rate": 0.978,
      "spoilage_units": 145.0
    },
    "evolve_block": "# EVOLVE-BLOCK\norder_qty = max(0, target - inventory)\n",
    "execution_time_ms": 98.4,
    "is_best": false
  },
  "timestamp": 1727560005.456
}
```

### 4. `run_completed`
Published when the optimization run finishes:
```json
{
  "event_type": "run_completed",
  "payload": {
    "total_evaluated": 25,
    "best_score": 0.485,
    "best_candidate_id": "cand_22"
  },
  "timestamp": 1727560030.789
}
```

---

## Usage Instructions

### Running Live Streaming

1. **Start the Dashboard Server**:
   ```bash
   uv run python server.py
   ```
   Open `http://127.0.0.1:8080` in your web browser. The status pill will display `CONNECTING...` and then transition to `LIVE STREAMING (SSE)`.

2. **Execute Optimization with Telemetry Streaming**:
   ```bash
   # Dry-run mock evolution
   uv run python examples/inventory_replenishment/run_evolution.py --dry-run --max-programs 20 --stream-to-dashboard

   # Live Cloud evolution
   uv run python examples/inventory_replenishment/run_evolution.py --max-programs 30 --workers 4 --stream-to-dashboard
   ```

3. **Verify Dashboard Visuals**:
   - Watch the generation count in the hero header increment in real-time.
   - Watch the Pareto Frontier graph plot new bubbles as evaluations finish.
   - Inspect toast notifications appearing in the bottom-right corner.
   - Scrub back and forth to inspect past candidates while the run continues in the background.
