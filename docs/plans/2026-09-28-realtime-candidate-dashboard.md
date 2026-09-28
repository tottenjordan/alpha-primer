# Real-Time Candidate Evaluation Executive Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable the executive web dashboard to stream and visualize optimization runs in real-time as program candidates are acquired and evaluated by AlphaEvolve.

**Architecture:** 
1. Build a zero-dependency thread-safe `LiveTelemetryBroker` in `src/alpha_evolve/dashboard/telemetry_broker.py` maintaining active session buffers and publishing events (`candidate_evaluated`, `run_started`, `run_completed`, `milestone_discovered`).
2. Integrate `LiveTelemetryBroker` into `EvolutionController` (`src/alpha_evolve/controller.py`) and `AlphaEvolveExperiment` (`src/alpha_evolve/experiment.py`) so every evaluated candidate broadcasts real-time metrics, code blocks, and simulation frames.
3. Expose Server-Sent Events (SSE) `/api/stream/events` and REST ingestion `/api/live/candidates` on `server.py` supporting both standard `ThreadingHTTPServer` fallback and FastAPI/Uvicorn.
4. Update `build_dashboard.py` and `dashboard/index.html` with an SSE client (`EventSource`), live status pill (LIVE STREAMING / HISTORIC ARCHIVE), live candidate toast/ticker, dynamic canvas re-rendering as new generations arrive, and interactive auto-scroll to latest candidate.
5. Create comprehensive automated unit and integration tests in `tests/test_realtime_dashboard.py` and end-to-end tests verifying streaming with mock evolution runs.

**Tech Stack:** Python 3.12, SSE (Server-Sent Events), threading, JSON, vanilla Safe DOM JavaScript, HTML5 Canvas 2D, pytest, ty, ruff.

---

### Task 1: Live Telemetry Broker
**Files:**
- Create: `src/alpha_evolve/dashboard/telemetry_broker.py`
- Test: `tests/test_realtime_dashboard.py`

**Step 1: Write failing test for LiveTelemetryBroker**
```python
def test_broker_publish_and_subscribe():
    broker = LiveTelemetryBroker()
    q = broker.subscribe()
    broker.publish({"type": "candidate_evaluated", "generation": 1, "score": 12.5})
    event = q.get(timeout=1.0)
    assert event["type"] == "candidate_evaluated"
    assert event["generation"] == 1
    broker.unsubscribe(q)
```

**Step 2: Run test to verify it fails**
Run: `uv run --frozen pytest tests/test_realtime_dashboard.py::test_broker_publish_and_subscribe -v`
Expected: FAIL with ModuleNotFoundError or ImportError

**Step 3: Implement LiveTelemetryBroker**
Implement thread-safe `LiveTelemetryBroker` singleton with event history ring buffer, subscriber queues, and helper methods `publish_candidate_evaluation`, `publish_run_start`, and `publish_run_complete`.

**Step 4: Run test to verify it passes**
Run: `uv run --frozen pytest tests/test_realtime_dashboard.py::test_broker_publish_and_subscribe -v`
Expected: PASS

**Step 5: Commit**
`git commit -am "feat(dashboard): add thread-safe LiveTelemetryBroker for real-time streaming"`

---

### Task 2: Controller & Experiment Real-Time Hooks
**Files:**
- Modify: `src/alpha_evolve/controller.py`
- Modify: `src/alpha_evolve/experiment.py`
- Test: `tests/test_realtime_dashboard.py`

**Step 1: Write failing test for controller live telemetry publishing**
Verify `EvolutionController` publishes candidate evaluation events through `broker` for both seed program and acquired batch candidates.

**Step 2: Run test to verify it fails**
Expected: FAIL

**Step 3: Implement controller broker integration**
Accept optional `telemetry_broker` in `EvolutionController` (defaulting to global broker instance or None). Broadcast `run_started`, each candidate evaluated (with iteration, scores, insights, evolve_block, execution_time_s), and `run_completed`.

**Step 4: Run test to verify it passes**
Run: `uv run --frozen pytest tests/test_realtime_dashboard.py -v`
Expected: PASS

**Step 5: Commit**
`git commit -am "feat(controller): publish real-time evaluation events to telemetry broker"`

---

### Task 3: Server Real-Time SSE Endpoint & Dispatcher
**Files:**
- Modify: `server.py`
- Test: `tests/test_server.py`

**Step 1: Write failing test for SSE `/api/stream/events` and `/api/live/state`**
Test `server.py` handles `/api/stream/events` headers (`text/event-stream`, `Cache-Control: no-cache`), returns current state snapshot on `/api/live/state`, and accepts live candidate submissions on `/api/live/candidates`.

**Step 2: Run test to verify it fails**
Expected: FAIL (404 Not Found)

**Step 3: Implement SSE & Live state handlers in `server.py`**
In `handle_api_request`:
- `/api/live/state`: returns active running experiment status, candidate count, latest candidate, and best score.
- `/api/live/candidates`: POST route to ingest candidate evaluations from external or CLI worker processes.
- In `FallbackHandler`: support `text/event-stream` chunked streaming or event generator.
- In FastAPI app: add `EventSourceResponse` or StreamingResponse for `/api/stream/events`.

**Step 4: Run test to verify it passes**
Run: `uv run --frozen pytest tests/test_server.py tests/test_realtime_dashboard.py -v`
Expected: PASS

**Step 5: Commit**
`git commit -am "feat(server): add Server-Sent Events stream and live candidate API"`

---

### Task 4: Interactive Dashboard Real-Time Visualizer
**Files:**
- Modify: `src/alpha_evolve/dashboard/build_dashboard.py`
- Recompile: `dashboard/index.html`
- Test: `tests/test_dashboard_builder.py`

**Step 1: Write failing test for real-time UI components in build_dashboard**
Assert generated `index.html` contains:
- `live-stream-badge` indicating connection state (`OFFLINE`, `CONNECTING`, `LIVE STREAMING`).
- EventSource connection logic to `/api/stream/events`.
- Safe DOM real-time trajectory appending and scrubber dynamic max extension.
- Dynamic Pareto frontier and milestone ribbon updates on incoming candidate events.
- Toast alert or live candidate feed.

**Step 2: Run test to verify it fails**
Expected: FAIL

**Step 3: Implement Real-Time Client Logic in `build_dashboard.py`**
Add:
- Top-bar Live Status Pill with pulsing live indicator when SSE stream is open (`CONNECTED (LIVE)`).
- Automatic fallback to embedded historical data if SSE stream is unavailable or closes.
- `EventSource` subscriber: on `candidate_evaluated`, dynamically:
  1. Append candidate to `trajectories` array.
  2. Update scrubber `max` and current playhead.
  3. Update KPI cards and active generation banner.
  4. Redraw Canvas 1 (Trajectory) and Canvas 2 (Pareto / Waterfall).
  5. Add new node to Milestone Ribbon if candidate sets new best score.
  6. Flash a transient toast notification: `New Candidate: Gen X (Cost -Y%, Score Z)`.

**Step 4: Run test to verify it passes and recompile dashboard**
Run: `uv run python -m alpha_evolve.dashboard.build_dashboard`
Run: `uv run --frozen pytest tests/test_dashboard_builder.py -v`
Expected: PASS

**Step 5: Commit**
`git commit -am "feat(dashboard): add real-time SSE streaming visualizer and live playhead sync"`

---

### Task 5: End-to-End Simulation & Verification
**Files:**
- Add: `tests/test_realtime_e2e.py`
- Update: `examples/inventory_replenishment/run_evolution.py` (add `--stream-to-dashboard` flag)
- Update: `docs/USER_GUIDE.md` & `docs/notes/realtime_dashboard.md`

**Step 1: Write comprehensive end-to-end streaming test**
Simulate an evolution run while streaming candidates through the broker and reading from the server's SSE endpoint.

**Step 2: Verify all 56+ tests pass and `make check` is 100% green**
Run: `make check`
Expected: All linter, type checks, and tests pass.

**Step 3: Commit and open Pull Request**
`git commit -am "docs: document real-time candidate streaming and CLI integration"`
`gh pr create`
