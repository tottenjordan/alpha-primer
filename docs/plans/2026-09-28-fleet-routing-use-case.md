# Dynamic Fleet Routing & Dispatch Use Case Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a production-grade, end-to-end AlphaEvolve use case for Dynamic Fleet Routing & Vehicle Dispatch with Time Windows (`examples/fleet_routing/`) with high-fidelity digital twin simulation, tiered evaluation, CLI runner, test suite, and executive dashboard integration.

**Architecture:** The use case implements an online vehicle routing & dispatch heuristic under dynamic traffic congestion, vehicle capacity limits, and strict delivery time windows. It integrates directly with AlphaEvolve's multi-tiered `BaseEvaluator` protocol (`evaluate_smoke`, `evaluate_validation`, `evaluate_holdout`), causal simulation masking, the telemetry broker, and the multi-use-case dashboard API.

**Tech Stack:** Python 3.12, NumPy, SciPy, Pydantic, pytest, ruff, ty, and AlphaEvolve Core SDK.

---

## Component Breakdown

1. **Domain Simulator & Dataset Generator** (`examples/fleet_routing/src/simulator.py`):
   - Discrete-event spatial delivery simulator with causal isolation (stops revealed only as order time $t_{\text{order}} \le t$).
   - Heterogeneous fleet of $K$ vehicles departing central depot $(0, 0)$ with maximum payload capacities.
   - Dynamic time-of-day traffic congestion model ($\tau(t) = 1.0 + 0.6 \sin^2(\pi t / 12)$) and stochastic travel noise.
   - Exact tracking of route distance, service times, early idle waiting, and time-window tardiness.
   - Synthetic benchmark generator (`generate_routing_benchmark_dataset`) producing reproducible spatial clusters.

2. **Baseline Seed Algorithm** (`examples/fleet_routing/src/program.py`):
   - Bounded by `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END`.
   - Baseline greedy heuristic: Nearest-neighbor with Earliest Deadline First (EDF) penalty scoring.
   - Vectorized feature scoring interface ready for LLM-driven evolutionary mutation.

3. **Multi-Tier Domain Evaluator** (`examples/fleet_routing/src/evaluate.py`):
   - Subclasses `BaseEvaluator`.
   - **Tier 1 (Smoke Sanity Check, <100ms)**: Validates non-negative scores, finite outputs, vehicle capacity invariants.
   - **Tier 2 (Validation Rollout, ~1.2s)**: 20-day simulation across 100 customer stops and 10 vehicles, computing `cost_reduction_pct` relative to baseline.
   - **Tier 3 (Holdout Test Rollout)**: Generalization test on unseen spatial customer clusters and extreme rush-order surges.

4. **Post-Evolution Reporter & Visualizer** (`examples/fleet_routing/src/report.py`):
   - Route path geometry export, vehicle Gantt schedules, and cost breakdown comparison.

5. **Executable Evolution Entrypoint** (`examples/fleet_routing/run_evolution.py`):
   - Standalone CLI runner with `--dry-run`, `--max-programs`, `--workers`, and `--stream-to-dashboard`.

6. **Documentation & Problem Context** (`examples/fleet_routing/README.md` & `instructions.md`):
   - Mathematical formulation, business context, state feature specifications, and prompt instructions.

7. **Test Suite** (`examples/fleet_routing/tests/`):
   - `test_program.py`: Seed algorithm input/output and capacity compliance.
   - `test_simulator.py`: Spatial distance calculations, causal isolation, and FIFO vehicle queue transitions.
   - `test_evaluator.py`: Smoke, validation, and holdout tiered execution and early-exit on broken candidates.

8. **Trajectory & Server Integration** (`records/fleet_routing_trajectory.json` & `server.py`):
   - 31-generation evolutionary trajectory recording.
   - Registered under `server.py` `ALLOWED_USE_CASES` for `/api/trajectories/fleet_routing`.

---

## Tasks

### Task 1: Domain Simulator & Benchmark Dataset Generator

**Files:**
- Create: `examples/fleet_routing/__init__.py`
- Create: `examples/fleet_routing/src/__init__.py`
- Create: `examples/fleet_routing/src/simulator.py`
- Test: `examples/fleet_routing/tests/__init__.py`
- Test: `examples/fleet_routing/tests/test_simulator.py`

**Step 1: Write the failing test**
Create `examples/fleet_routing/tests/test_simulator.py` testing:
- Dataset generation shapes (`locations`, `time_windows`, `demands`, `order_times`).
- Causal isolation: ensuring day $t$ cannot observe orders placed at $t' > t$.
- Simulator execution: running a baseline assignment and computing total distance and tardiness penalties.

**Step 2: Run test to verify it fails**
```bash
uv run --frozen pytest examples/fleet_routing/tests/test_simulator.py -v
```
Expected: FAIL (ModuleNotFoundError: No module named 'examples.fleet_routing')

**Step 3: Implement minimal code**
Create:
- `examples/fleet_routing/__init__.py`
- `examples/fleet_routing/src/__init__.py`
- `examples/fleet_routing/src/simulator.py` implementing `generate_routing_benchmark_dataset`, `VehicleRoutingDigitalTwin`, and simulation loop with traffic congestion.

**Step 4: Run test to verify it passes**
```bash
uv run --frozen pytest examples/fleet_routing/tests/test_simulator.py -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add examples/fleet_routing/
git commit -m "feat(fleet_routing): add digital twin spatial routing simulator and dataset generator"
```

---

### Task 2: Baseline Seed Program with EVOLVE-BLOCK

**Files:**
- Create: `examples/fleet_routing/src/program.py`
- Test: `examples/fleet_routing/tests/test_program.py`

**Step 1: Write the failing test**
Create `examples/fleet_routing/tests/test_program.py` testing:
- `assign_and_sequence_routes` returns valid vehicle assignments and sequential visit orders.
- No vehicle capacity is exceeded.
- Unassigned stops are handled or flagged appropriately.

**Step 2: Run test to verify it fails**
```bash
uv run --frozen pytest examples/fleet_routing/tests/test_program.py -v
```
Expected: FAIL (ImportError: cannot import name 'assign_and_sequence_routes')

**Step 3: Implement minimal code**
Create `examples/fleet_routing/src/program.py`:
- Defined with `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END`.
- Implements `assign_and_sequence_routes` using nearest-neighbor distance and time-window slack balancing.

**Step 4: Run test to verify it passes**
```bash
uv run --frozen pytest examples/fleet_routing/tests/test_program.py -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add examples/fleet_routing/src/program.py examples/fleet_routing/tests/test_program.py
git commit -m "feat(fleet_routing): add baseline greedy route dispatch algorithm with EVOLVE-BLOCK"
```

---

### Task 3: 3-Tier Vehicle Routing Evaluator (`BaseEvaluator` Subclass)

**Files:**
- Create: `examples/fleet_routing/src/evaluate.py`
- Test: `examples/fleet_routing/tests/test_evaluator.py`

**Step 1: Write the failing test**
Create `examples/fleet_routing/tests/test_evaluator.py` testing:
- `VehicleRoutingEvaluator` inherits from `BaseEvaluator`.
- `evaluate_smoke` catches non-callable, crashing, or capacity-violating candidates.
- `evaluate_validation` computes primary metric `cost_reduction_pct` and secondary metrics (`on_time_rate_pct`, `total_distance_km`, `capacity_utilization_pct`).
- `evaluate_holdout` scores candidate generalization on unseen geographic distribution.

**Step 2: Run test to verify it fails**
```bash
uv run --frozen pytest examples/fleet_routing/tests/test_evaluator.py -v
```
Expected: FAIL (ModuleNotFoundError: No module named 'examples.fleet_routing.src.evaluate')

**Step 3: Implement minimal code**
Create `examples/fleet_routing/src/evaluate.py`:
- Subclasses `BaseEvaluator`.
- Implements `evaluate_smoke`, `evaluate_validation`, `evaluate_holdout`.
- Returns structured `TierResult` and `EvaluationResult` with numerical `Scores` and diagnostic `Insights`.

**Step 4: Run test to verify it passes**
```bash
uv run --frozen pytest examples/fleet_routing/tests/test_evaluator.py -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add examples/fleet_routing/src/evaluate.py examples/fleet_routing/tests/test_evaluator.py
git commit -m "feat(fleet_routing): implement tiered VehicleRoutingEvaluator subclassing BaseEvaluator"
```

---

### Task 4: Post-Evolution Report Generator & Visualizer

**Files:**
- Create: `examples/fleet_routing/src/report.py`

**Step 1: Write the failing test**
Add test in `examples/fleet_routing/tests/test_evaluator.py` testing `generate_routing_report`:
- Verifies generation of metrics summary dict and textual breakdown.

**Step 2: Run test to verify it fails**
```bash
uv run --frozen pytest examples/fleet_routing/tests/test_evaluator.py::test_routing_report_generation -v
```
Expected: FAIL

**Step 3: Implement minimal code**
Create `examples/fleet_routing/src/report.py`:
- Implements `generate_routing_report(best_callable, holdout_data)`.
- Calculates statistical confidence intervals and route efficiency gains.

**Step 4: Run test to verify it passes**
```bash
uv run --frozen pytest examples/fleet_routing/tests/test_evaluator.py::test_routing_report_generation -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add examples/fleet_routing/src/report.py examples/fleet_routing/tests/test_evaluator.py
git commit -m "feat(fleet_routing): add post-evolution route report and statistics generator"
```

---

### Task 5: Evolution Entrypoint CLI Runner

**Files:**
- Create: `examples/fleet_routing/run_evolution.py`

**Step 1: Write the failing test**
Create test in `tests/test_realtime_e2e.py` (or dedicated test) verifying `run_evolution.py --dry-run --max-programs 2` runs successfully via subprocess.

**Step 2: Run test to verify it fails**
```bash
uv run --frozen pytest tests/test_fleet_routing_cli.py -v
```
Expected: FAIL (File not found)

**Step 3: Implement minimal code**
Create `examples/fleet_routing/run_evolution.py`:
- Parses `--dry-run`, `--max-programs`, `--workers`, `--stream-to-dashboard`.
- Instantiates `VehicleRoutingEvaluator` and `AlphaEvolveExperiment`.
- Runs evolutionary loop and exports `artifacts/fleet_routing/best_evolved_program.py`.

**Step 4: Run test to verify it passes**
```bash
uv run --frozen python examples/fleet_routing/run_evolution.py --dry-run --max-programs 3
```
Expected: PASS with 3 programs evaluated and champion output.

**Step 5: Commit**
```bash
git add examples/fleet_routing/run_evolution.py tests/test_fleet_routing_cli.py
git commit -m "feat(fleet_routing): add run_evolution.py executable entrypoint with dry-run support"
```

---

### Task 6: Domain Documentation & Prompt Instructions

**Files:**
- Create: `examples/fleet_routing/README.md`
- Create: `examples/fleet_routing/instructions.md`
- Modify: `examples/README.md`

**Step 1: Write documentation**
- `instructions.md`: State variables, mathematical cost weights, search space constraints for LLM mutations.
- `README.md`: Problem statement, business impact, execution commands, and mathematical formulations.
- `examples/README.md`: Add `fleet_routing` to the Catalog of Use Cases table.

**Step 2: Verify lint and markdown consistency**
```bash
uv run --frozen ruff check .
```
Expected: PASS

**Step 3: Commit**
```bash
git add examples/fleet_routing/README.md examples/fleet_routing/instructions.md examples/README.md
git commit -m "docs(fleet_routing): add comprehensive domain instructions and update catalog"
```

---

### Task 7: Synthetic Trajectory Dataset & Server / Multi-Use-Case Integration

**Files:**
- Create: `records/fleet_routing_trajectory.json`
- Modify: `server.py`
- Modify: `tests/test_server.py`

**Step 1: Write the failing test**
Add test in `tests/test_server.py`:
- Request `GET /api/trajectories/fleet_routing` and assert HTTP 200 with valid 31-generation trajectory payload.

**Step 2: Run test to verify it fails**
```bash
uv run --frozen pytest tests/test_server.py::test_server_trajectories_fleet_routing -v
```
Expected: FAIL (HTTP 404)

**Step 3: Implement minimal code**
- Generate realistic 31-generation evolutionary trajectory `records/fleet_routing_trajectory.json`.
- Add `"fleet_routing": "fleet_routing_trajectory.json"` to `ALLOWED_USE_CASES` in `server.py`.

**Step 4: Run test to verify it passes**
```bash
uv run --frozen pytest tests/test_server.py::test_server_trajectories_fleet_routing -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add records/fleet_routing_trajectory.json server.py tests/test_server.py
git commit -m "feat(server): register fleet_routing use case in trajectory API"
```

---

### Task 8: End-to-End Quality Audit & Documentation

**Files:**
- Modify: `docs/USER_GUIDE.md`
- Modify: `docs/notes/README.md`

**Step 1: Update documentation**
- Document `examples/fleet_routing` in `docs/USER_GUIDE.md` with CLI commands.
- Verify full test suite passes.

**Step 2: Run all checks**
```bash
make check
```
Expected: 100% PASS (ruff check, ruff format, ty check, pytest).

**Step 3: Commit**
```bash
git add docs/USER_GUIDE.md docs/notes/README.md
git commit -m "docs: document fleet_routing use case in USER_GUIDE"
```

---

## Verification Plan

### Automated Tests
1. Unit tests for simulator:
   ```bash
   uv run --frozen pytest examples/fleet_routing/tests/test_simulator.py -v
   ```
2. Unit tests for seed algorithm:
   ```bash
   uv run --frozen pytest examples/fleet_routing/tests/test_program.py -v
   ```
3. Unit tests for evaluator:
   ```bash
   uv run --frozen pytest examples/fleet_routing/tests/test_evaluator.py -v
   ```
4. Server endpoint test:
   ```bash
   uv run --frozen pytest tests/test_server.py -k fleet_routing -v
   ```
5. Full repository check:
   ```bash
   make check
   ```

### Manual Verification
1. Run dry-run evolutionary search:
   ```bash
   uv run python examples/fleet_routing/run_evolution.py --dry-run --max-programs 5
   ```
2. Verify output summary in terminal showing progressive score improvements.
3. Test trajectory endpoint:
   ```bash
   curl -s http://127.0.0.1:8080/api/trajectories/fleet_routing | jq .use_case_id
   ```
