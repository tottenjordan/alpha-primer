# Five-Axis Repository Code Review & Simplification Plan

**Repository**: `alpha-primer` (`AlphaEvolve` & Gemini Enterprise Digital Twin Optimization Suite)  
**Skills Applied**:
- [`code-review-and-quality`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/.agents/skills/code-review-and-quality/SKILL.md) (Five-Axis Multi-Dimensional Quality Review)
- [`code-simplification`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/.agents/skills/code-simplification/SKILL.md) (Structural Clarity, Redundancy Removal & Cognitive Load Reduction)
- [`source-driven-development`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/.agents/skills/source-driven-development/SKILL.md) (Authoritative Grounding & Standards Verification)
- [`CODE_STANDARDS.md`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/CODE_STANDARDS.md) (Repository Engineering Standards)

---

## 1. Executive Summary

A full five-axis audit (*Correctness*, *Readability & Simplicity*, *Architecture*, *Security*, *Performance*) was conducted across all `10,870` lines of source, dashboard, server, deployment, example, and test code in `alpha-primer`.

### Severity Distribution

| Severity Prefix | Count | Meaning (per `code-review-and-quality`) |
| :--- | :---: | :--- |
| **`Critical:`** | **1** | Runtime crash / broken feature on active user path; must resolve immediately. |
| *(No prefix — Required)* | **7** | Structural blocker, architectural boundary leak, security hardening, or significant duplication; must resolve before merge. |
| **`Consider:` / `Optional:`** | **4** | Non-blocking improvement worth addressing for cleaner lifecycle, dead-code hygiene, or ergonomics. |
| **`Nit:`** | **2** | Minor polish / consistency improvement. |

---

## 2. Five-Axis Findings (Ordered by Leverage)

### Axis 1: Correctness

#### 1. `Critical:` Fleet Routing Trajectory Schema Mismatch Breaks Dashboard Use-Case Switcher at Runtime
- **Locations**:
  - [`src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py#L159-L190)
  - [`src/alpha_evolve/dashboard/build_dashboard.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py#L1737-L1855)
  - [`src/alpha_evolve/dashboard/build_dashboard.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py#L2070-L2105)
- **Finding**:
  When switching the Executive Dashboard dropdown from `inventory_replenishment` to `fleet_routing`, `switchUseCase("fleet_routing")` updates `DATA` and invokes `renderMilestoneRibbon()` and `updateDisplay(genIdx)`. Three schema mismatches cause uncaught `TypeError` exceptions and broken charts in the browser:
  1. **Missing nested `metrics` object in `trajectory_generations`**: In [`trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/trajectory_generator.py#L300-L317), each generation entry wraps metrics inside `"metrics": {...}` and includes `"daily_series": [...]`. In [`fleet_routing_trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py#L177-L190), `trajectory_generations` appends a flat dict (`{"generation": gen, "total_cost": g_cost, ...}`) without a `"metrics"` key or `"daily_series"` array. In [`build_dashboard.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py#L1801-L1808), `const m = frame.metrics; document.getElementById('kpi-total-cost').textContent = fmtCurrency(m.total_cost);` throws `TypeError: Cannot read properties of undefined (reading 'total_cost')`.
  2. **Missing fields in `ribbon_milestones`**: [`renderMilestoneRibbon()`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py#L1737-L1765) calls `item.cost_reduc.toFixed(1)` and `item.fill_rate.toFixed(1)` and reads `item.innovation` and `item.is_champ`. [`fleet_routing_trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py#L159-L164) only populates `{"generation", "label", "badge", "title", "is_star"}`, throwing `TypeError: Cannot read properties of undefined (reading 'toFixed')`.
  3. **Domain-coupled Pareto & Replay Canvas keys**: [`drawParetoChart()`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py#L2086-L2101) reads `m.fill_rate_pct` and `m.spoilage_rate_pct`, which are `undefined` for `fleet_routing` (which produces `on_time_delivery_pct` and `total_distance_km`), yielding `NaN` canvas coordinates.
- **Why Existing Tests Missed It**:
  [`tests/test_dashboard_builder.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/tests/test_dashboard_builder.py#L230-L280) checked static substring presence (`assert "switchUseCase" in content`) and syntax compilation (`new Function(code)`), rather than executing `switchUseCase("fleet_routing")` in Node.js or validating schema parity between use-case bundles.
- **Remediation**:
  - Normalize `fleet_routing_trajectory_generator.py` so every use-case payload in `master_trajectories.json` conforms to a unified `UseCaseTrajectoryBundle` schema (including nested `metrics`, `daily_series`, complete `ribbon_milestones`, and normalized SLA/efficiency aliases or domain-aware chart accessors in JS).
  - Add a schema contract test in `tests/test_dashboard_builder.py` that validates both `inventory_replenishment` and `fleet_routing` against the exact fields accessed by `build_dashboard.py`, plus a Node.js execution test that invokes `switchUseCase('fleet_routing')` and `updateDisplay(0)` without throwing.

---

#### 2. `EvolutionController` Ignores `BaseEvaluator.higher_is_better` and Hardcodes `%` Formatting
- **Locations**:
  - [`src/alpha_evolve/controller.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/controller.py#L77-L78)
  - [`src/alpha_evolve/controller.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/controller.py#L131-L143)
  - [`src/alpha_evolve/controller.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/controller.py#L216-L246)
  - [`src/alpha_evolve/evaluators/base.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/evaluators/base.py#L104)
- **Finding**:
  [`BaseEvaluator`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/evaluators/base.py#L104) declares `higher_is_better: bool = True` as part of the abstract evaluator contract so domains can either maximize a fitness score or minimize raw cost/distance/latency. However, [`EvolutionController`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/controller.py#L78) ignores `self.evaluator.higher_is_better`:
  - Line 78 initializes `self.best_score: float = -float("inf")` unconditionally.
  - Line 133 checks `is_new_best = eval_result.valid and (curr_score > self.best_score)`.
  - Lines 217 and 245 format all scores as percentages (`f"{curr_score:+.2f}%"`), even when `primary_metric` is `"score"` (as in `VehicleRoutingEvaluator`) or raw dollars/kilometers.
- **Remediation**:
  - Respect `self.higher_is_better = self.evaluator.higher_is_better` in `EvolutionController`: initialize `self.best_score` to `-float("inf")` when `higher_is_better` is `True` and `+float("inf")` when `False`, and use a helper `_is_better(candidate_score, best_score)` for comparisons.
  - Format the metric suffix as `"%"` only when `self.primary_metric.endswith("_pct")`, otherwise display `f"{curr_score:+.2f}"`.
  - Add a unit test in `tests/test_evaluator_protocol.py` verifying a `higher_is_better = False` evaluator (minimization objective) tracks the minimum-scoring valid candidate as `best_candidate`.

---

### Axis 2: Architecture & Module Boundaries

#### 3. Monolithic 3,254-Line File in `build_dashboard.py` (Presumptive Size Blocker)
- **Location**:
  - [`src/alpha_evolve/dashboard/build_dashboard.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py#L1-L3254)
- **Finding**:
  Per [`code-review-and-quality`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/.agents/skills/code-review-and-quality/SKILL.md) (*File & Change Size Discipline*):
  > *"Is the touched file already past a healthy size (~1000 total lines is a common inspection signal)? Adding more code to a bloated file compounds the problem. Decompose, then add."*
  
  [`build_dashboard.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py) is **3,254 lines** long because it embeds ~930 lines of CSS, ~380 lines of HTML markup, and ~1,800 lines of client-side JavaScript inside a single Python f-string with manual brace escaping (`{{` and `}}`). This makes diffs noisy, prevents standalone JS/CSS syntax tooling, and mixes template storage with build orchestration.
- **Remediation**:
  - Decompose `src/alpha_evolve/dashboard/` by extracting static template assets into `src/alpha_evolve/dashboard/templates/`:
    - `styles.css` (~930 lines of pure CSS, zero `{{` escaping)
    - `body.html` (~380 lines of pure HTML markup)
    - `app.js` (~1,800 lines of pure JavaScript, zero `{{` escaping)
  - Reduce [`build_dashboard.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py) to a clean ~150-line Python assembler that loads the templates, injects the JSON data payload, and writes the self-contained single-file `dashboard/index.html` and `dashboard/data.json`.

---

#### 4. Domain-Specific Inventory Logic Leaking into Shared Core SDK & Server
- **Locations**:
  - [`src/alpha_evolve/client.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/client.py#L239-L260)
  - [`server.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py#L60-L66)
- **Finding**:
  Per [`code-review-and-quality`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/.agents/skills/code-review-and-quality/SKILL.md) (*Architecture — Layering & Boundaries*):
  > *"Is feature-specific logic leaking into a shared or general-purpose module? Keep logic in its owning layer."*
  1. [`MockAlphaEvolveClient._mutate_seed_code`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/client.py#L239-L260) in the core SDK hardcodes string replacements for inventory-replenishment variable names (`promo_schedule_lookahead`, `order_up_to`, `net_inventory`, `lookback_days = 14`). When running `fleet_routing` (or any custom user evaluator) in `--dry-run` mode, mutations 2 and 3 silently no-op because those variable names do not exist in `fleet_routing/src/program.py`.
  2. [`server.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py#L61) hardcodes project number `"934903580331"` in `_resolve_cloud_status()` fallback instead of reading `os.getenv("PROJECT_ID", "934903580331")`.
- **Remediation**:
  - Make `MockAlphaEvolveClient._mutate_seed_code` domain-adaptive: support fleet-routing heuristic mutations (e.g., adjusting urgency weight `0.05` and capacity threshold in `assign_and_sequence_routes`), inventory mutations, and generic numeric literal perturbations inside `# EVOLVE-BLOCK` regions so dry-run evolution produces meaningful candidate variations across any use case.
  - Read `os.getenv("PROJECT_ID")` and `os.getenv("ENGINE_ID")` in `server.py:_resolve_cloud_status()`.

---

### Axis 3: Readability & Code Simplification

#### 5. Duplicated Evaluator Resolution Boilerplate in `EvolutionController` and `AlphaEvolveExperiment`
- **Locations**:
  - [`src/alpha_evolve/controller.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/controller.py#L50-L65)
  - [`src/alpha_evolve/experiment.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/experiment.py#L37-L52)
- **Finding**:
  Per [`code-simplification`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/.agents/skills/code-simplification/SKILL.md) (*Redundancy & Duplication*):
  `EvolutionController.__init__` and `AlphaEvolveExperiment.__init__` contain character-for-character identical 16-line blocks resolving `evaluator: BaseEvaluator | Callable | None` and `evaluator_fn: Callable | None` into a `BaseEvaluator` instance (wrapping legacy callables in `FunctionEvaluatorWrapper`). Furthermore, when `AlphaEvolveExperiment.run()` instantiates `EvolutionController`, it runs the resolution logic a second time.
- **Remediation**:
  - Extract a single canonical function `resolve_evaluator(...) -> BaseEvaluator` in [`src/alpha_evolve/evaluators/base.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/evaluators/base.py) and call it from both `EvolutionController` and `AlphaEvolveExperiment`.

---

#### 6. Triplicated Candidate Compilation & Memory-Limit Setup in `workers.py`
- **Locations**:
  - [`src/alpha_evolve/workers.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py#L47-L168)
  - [`src/alpha_evolve/workers.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py#L251-L304)
  - [`src/alpha_evolve/workers.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py#L412-L470)
- **Finding**:
  [`src/alpha_evolve/workers.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py) duplicates three distinct concerns across multiple execution modes:
  1. **POSIX `RLIMIT_AS` setup** is duplicated in [`_sandbox_child_worker`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py#L56-L65) and [`_subprocess_runner_main`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py#L254-L263).
  2. **Tier-0 compilation, `exec()`, callable lookup, and return-type normalization** (`compile(code, ...)` -> `exec(compiled, module_scope)` -> `module_scope.get(function_name)` -> `callable()` check -> `EvaluationResult` coercion) is triplicated across `_sandbox_child_worker` (lines 68–112), `_execute_in_thread` (lines 134–167), and `_subprocess_runner_main` (lines 285–302).
  3. **Future timeout & exception handling** in [`WorkerPool.evaluate_candidate`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py#L412-L470) is duplicated across the `use_multiprocessing` and threaded branches.
- **Remediation**:
  - Extract `_apply_memory_limit(max_memory_mb: int) -> None` and `_compile_and_invoke(code: str, evaluator_fn: Callable[[Any], Any], function_name: str) -> EvaluationResult` in `workers.py`.
  - Unify future submission and timeout handling in `WorkerPool.evaluate_candidate`. This cuts ~110 lines of redundant boilerplate while ensuring identical Tier-0 behavior across thread, forkserver, and subprocess modes.

---

#### 7. Duplicated S-Curve Interpolation & Master Trajectory Merging Across Trajectory Generators
- **Locations**:
  - [`src/alpha_evolve/dashboard/trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/trajectory_generator.py#L33-L41)
  - [`src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py#L29-L36)
  - [`src/alpha_evolve/dashboard/trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/trajectory_generator.py#L741-L779)
  - [`src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py#L223-L256)
- **Finding**:
  Both trajectory generators implement identical S-curve interpolation math (`1.0 / (1.0 + math.exp(-10.0 * (progress - 0.45)))`) and duplicate the `master_trajectories.json` read-modify-write logic.
- **Remediation**:
  - Extract `interpolate_s_curve(start_val, end_val, gen, max_gen)` and `update_master_trajectories_bundle(use_case_id, use_case_data, target_dir, write_files)` into a shared helper module `src/alpha_evolve/dashboard/trajectory_utils.py`.

---

### Axis 4: Security

#### 8. Unbounded Request Body Read in FastAPI POST Endpoints & Subprocess `PYTHONPATH` Hygiene
- **Locations**:
  - [`server.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py#L322-L333)
  - [`server.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py#L373-L386)
  - [`src/alpha_evolve/workers.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py#L335-L338)
- **Finding**:
  1. **Unbounded FastAPI POST body read**: In `FallbackHandler.do_POST` ([`server.py:470`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py#L470)), `Content-Length` is checked against `1_048_576` (1 MB, returning HTTP 413). However, the primary production FastAPI routes (`post_live_candidate` at [`server.py:322`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py#L322) and `agent_replenish_query` at [`server.py:373`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py#L373)) call `await request.json()` without checking `Content-Length` or bounding the raw body size, allowing oversized payloads to be buffered in memory.
  2. **Subprocess `PYTHONPATH` relies on `Path.cwd()`**: In [`workers.py:335-337`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py#L335-L337), `_run_in_subprocess_sandbox` sets `repo_root = str(Path.cwd().resolve())` and prepends `{repo_root}:{repo_root}/tests` to `PYTHONPATH`. If invoked outside the repo root, imports fail; if invoked from an untrusted directory, arbitrary modules in `cwd` take precedence. It should derive `src_root = str(Path(__file__).resolve().parent.parent)` deterministically from `__file__`.
- **Remediation**:
  - Add a shared `_read_bounded_json(request: Request, max_bytes: int = 1_048_576) -> dict[str, Any]` helper in `server.py` (raising HTTP 413 when `Content-Length` or body length exceeds 1 MB) and use it in both FastAPI POST endpoints.
  - Anchor `_run_in_subprocess_sandbox` `PYTHONPATH` to `Path(__file__).resolve().parent.parent` (`src/`) and `Path(__file__).resolve().parent.parent.parent` (repo root).

---

### Axis 5: Performance

#### 9. Synchronous Per-Request Disk I/O and Re-Parsing on FastAPI Hot Paths
- **Locations**:
  - [`server.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py#L56-L157)
  - [`examples/inventory_replenishment/src/evaluate.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/examples/inventory_replenishment/src/evaluate.py#L19-L22)
  - [`examples/inventory_replenishment/src/evaluate.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/examples/inventory_replenishment/src/evaluate.py#L59-L69)
- **Finding**:
  1. **Per-request file reads in `server.py`**: Every HTTP GET/POST to `/`, `/api/data`, `/api/cloud-status`, `/api/trajectories/{use_case_id}`, and `/api/agent/replenish-query` reads and parses `dashboard/index.html` (~115 KB), `records/master_trajectories.json`, or `records/inventory_replenishment_trajectory.json` from disk synchronously inside `async def` handlers. Under concurrent requests on Cloud Run, this performs redundant disk reads and JSON deserialization on the event loop.
  2. **Duplicate dataset generation at import time in `inventory_replenishment/src/evaluate.py`**: Lines 20–22 run `generate_benchmark_dataset(n_skus=50, total_days=90, seed=42)` to populate `_CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL`, and then line 234 (`_DEFAULT_EVALUATOR = InventoryReplenishmentEvaluator()`) calls `setup()`, which calls `generate_benchmark_dataset(n_skus=50, total_days=90, seed=42)` a second time instead of reusing `_CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL`.
- **Remediation**:
  - Add an `mtime`-keyed in-memory file cache (`_read_json_cached(path)` and `_read_text_cached(path)`) in `server.py` so static/record files are parsed only once (or when modified on disk) while remaining 100% compatible with tests that monkeypatch `RECORDS_DIR` / `DASHBOARD_DIR`.
  - Reuse `_CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL` inside `InventoryReplenishmentEvaluator.setup()`.

---

### Non-Blocking Findings (`Consider:` / `Optional:` / `Nit:`)

#### 10. `Consider:` Dead Code Hygiene — Unused `load_file_content` Utility
- **Locations**:
  - [`src/alpha_evolve/utils.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/utils.py#L49-L51)
  - [`src/alpha_evolve/__init__.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/__init__.py#L14)
- **Finding**:
  Per [`code-review-and-quality`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/.agents/skills/code-review-and-quality/SKILL.md) (*Dead Code Hygiene*):
  `load_file_content(file_path)` in `src/alpha_evolve/utils.py` is exported in `__all__` (`src/alpha_evolve/__init__.py`) and tested in `tests/test_utils.py`, but is never called anywhere in `src/` or `examples/` (for example, [`AlphaEvolveExperiment.from_files`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/experiment.py#L96-L97) calls `Path(instructions_path).read_text(encoding="utf-8")` directly).
- **Recommendation**:
  Use `load_file_content` in `AlphaEvolveExperiment.from_files` so the public utility has an active caller and eliminates duplicate `Path(...).read_text(encoding="utf-8")` calls (preserving the public API export in `__init__.py`).

#### 11. `Consider:` Deduplicate Default State Schema in `LiveTelemetryBroker`
- **Locations**:
  - [`src/alpha_evolve/dashboard/telemetry_broker.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/telemetry_broker.py#L44-L54)
  - [`src/alpha_evolve/dashboard/telemetry_broker.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/telemetry_broker.py#L140-L150)
- **Finding**:
  `LiveTelemetryBroker.__init__` and `LiveTelemetryBroker.clear()` duplicate the 10-key `_current_state` dictionary literal, and `clear()` omits `"primary_metric"`, causing state schema drift if `clear()` is called after `notify_run_started()`.
- **Recommendation**:
  Extract a `_default_state() -> dict[str, Any]` helper method (including `"primary_metric": "cost_reduction_pct"`) and call it from both `__init__` and `clear()`.

#### 12. `Consider:` Add Context-Manager / `close()` Lifecycle to `AlphaEvolveClient`
- **Location**:
  - [`src/alpha_evolve/client.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/client.py#L55)
- **Finding**:
  `AlphaEvolveClient.__init__` creates `self._http_client = httpx.Client(timeout=30.0)` when `http_client` is not injected, but does not expose `close()`, `__enter__()`, or `__exit__()` to release the underlying connection pool.
- **Recommendation**:
  Add `close()`, `__enter__()`, and `__exit__()` to `AlphaEvolveClient` (and no-op equivalents on `MockAlphaEvolveClient`) so callers can deterministically close socket pools.

#### 13. `Consider:` Extract Shared Candidate Compilation Helper for `run_evolution.py` Entrypoints
- **Locations**:
  - [`examples/inventory_replenishment/run_evolution.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/examples/inventory_replenishment/run_evolution.py#L86-L90)
  - [`examples/fleet_routing/run_evolution.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/examples/fleet_routing/run_evolution.py#L86-L90)
- **Finding**:
  Both `run_evolution.py` scripts manually run `scope: dict[str, object] = {}; exec(compile(best_candidate.code, "<best_candidate>", "exec"), scope)` and require `# type: ignore[arg-type]` when passing `best_policy_fn` to `evaluate_on_locked_holdout`.
- **Recommendation**:
  Expose a typed `compile_candidate_callable(code: str, function_name: str) -> Callable[..., Any]` helper in `alpha_evolve.utils` (or `workers.py`) and call it in both `run_evolution.py` scripts, removing both raw `exec()` blocks and `# type: ignore` suppressions.

#### 14. `Nit:` Consistent `encoding="utf-8"` and `Path` Usage in `controller.py`
- **Location**:
  - [`src/alpha_evolve/controller.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/controller.py#L270-L280)
- **Finding**:
  `controller.py` already follows `encoding="utf-8"` cleanly; however, `evaluation_summary.json` omits `higher_is_better` and `evaluator_name` metadata that would aid post-experiment auditing.

#### 15. `Nit:` Unused `import os` in `fleet_routing_trajectory_generator.py` Check
- **Location**:
  - [`src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py#L146-L154)
- **Finding**:
  In `fleet_routing_trajectory_generator.py`, `milestones` uses keys `"0"`, `"6"`, `"14"`, `"25"`, whereas `build_dashboard.py` initializes `diffState = { leftGen: '0', rightGen: '30', ... }`. When switching to `fleet_routing`, `diffState.rightGen` (`'30'`) does not exist in `fleet_routing.milestones` (whose champion key is `'25'`), causing `renderDiffEngine()` to fall back to `m['30'] || m['0']` (comparing Gen 0 against Gen 0!) until the user clicks a milestone pill.
- **Remediation**:
  In `switchUseCase()`, dynamically set `diffState.leftGen` to the first milestone key and `diffState.rightGen` to the last milestone key of `DATA.milestones`, and dynamically rebuild the milestone stepper buttons from `DATA.milestones`!

---

## 3. The Review Checklist (`code-review-and-quality`)

- [x] Every finding has a clear severity prefix (`Critical:`, Required, `Consider:`, `Nit:`)
- [x] High-leverage architectural and correctness issues are presented first
- [x] Every test was evaluated against the mutation question (*"What broken code would this still pass on?"*) — specifically identifying why `test_dashboard_builder.py` missed the `fleet_routing` runtime schema mismatch
- [x] Security boundary checks applied to all external HTTP inputs (`server.py`) and sandboxed subprocess execution (`workers.py`)
- [x] File and change sizes checked against the presumptive ~1,000-line ceiling (`build_dashboard.py` at 3,254 lines flagged for decomposition)
- [x] Unused/unreachable code identified (`load_file_content`, duplicate benchmark generation)

---

## 4. Step-by-Step Remediation & Simplification Plan

> [!IMPORTANT]
> **No fixes have been applied yet.** Upon your approval of this plan, we will execute the remediation on a dedicated branch (`fix/five-axis-code-review`) using small, atomic commits that leave `make check` (`ruff`, `ty`, `pytest`) green after every step.

### Phase 1: Fix Critical Dashboard Multi-Use-Case Schema & Dynamic Stepper (Findings #1, #7, #15)
1. **Create [`src/alpha_evolve/dashboard/trajectory_utils.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/trajectory_utils.py)**:
   - Extract `interpolate_s_curve(start_val, end_val, gen, max_gen)` and `update_master_trajectories_bundle(...)` to eliminate duplication between `trajectory_generator.py` and `fleet_routing_trajectory_generator.py`.
2. **Normalize [`src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py)**:
   - Structure each entry in `trajectory_generations` with nested `"metrics"` (including `total_cost`, `cost_reduction_pct`, `fitness_score`, `on_time_delivery_pct`, `total_distance_km`, plus normalized `fill_rate_pct` / `spoilage_rate_pct` aliases for SLA/efficiency) and `"daily_series"` simulation curves so all 4 tabs render seamlessly.
   - Populate `cost_reduc`, `fill_rate`, `innovation`, and `is_champ` in `ribbon_milestones`.
3. **Make Milestone Diff Stepper & KPI Labels Use-Case Aware in Dashboard JS**:
   - In `switchUseCase()`, dynamically reset `diffState.leftGen` and `diffState.rightGen` to the first and last keys of `DATA.milestones`, and dynamically render the milestone comparison pills from `DATA.milestones` so Fleet Routing displays its `Gen 0 → Gen 6 → Gen 14 → Gen 25` milestones.
   - Regenerate `records/fleet_routing_trajectory.json`, `records/inventory_replenishment_trajectory.json`, `records/master_trajectories.json`, and `dashboard/index.html`.
4. **Mutation-Proof Test in [`tests/test_dashboard_builder.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/tests/test_dashboard_builder.py)**:
   - Add a schema contract test asserting that every use case in `master_trajectories.json` has identical required keys in `trajectory_generations[*].metrics`, `ribbon_milestones[*]`, and `milestones[*]`.
   - Add a Node.js runtime execution test that runs `switchUseCase('fleet_routing')` and verifies KPI text, Milestone Ribbon, Pareto Canvas, and Diff Stepper update without throwing.

### Phase 2: Decompose Monolithic `build_dashboard.py` (3,254 Lines → ~150 Lines) (Finding #3)
1. **Extract Static Templates into `src/alpha_evolve/dashboard/templates/`**:
   - `src/alpha_evolve/dashboard/templates/styles.css` (all dashboard CSS styles, unescaped).
   - `src/alpha_evolve/dashboard/templates/body.html` (all semantic HTML structure).
   - `src/alpha_evolve/dashboard/templates/app.js` (all client-side Safe DOM & Canvas 2D JavaScript, unescaped).
2. **Simplify [`src/alpha_evolve/dashboard/build_dashboard.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/build_dashboard.py)**:
   - Replace the 3,100-line f-string with a clean template loader that reads `styles.css`, `body.html`, and `app.js`, injects the serialized JSON data payload, and writes the standalone `dashboard/index.html` and `dashboard/data.json`.
   - Verify byte-for-byte / functional equivalence via `tests/test_dashboard_builder.py`.

### Phase 3: Core SDK Correctness, Layering & Code Simplification (Findings #2, #4, #5, #6, #10, #12, #13)
1. **Evaluator Resolution & `higher_is_better` Support**:
   - Extract `resolve_evaluator(...)` in [`src/alpha_evolve/evaluators/base.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/evaluators/base.py) and remove duplicated resolution blocks in [`controller.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/controller.py) and [`experiment.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/experiment.py).
   - Update [`EvolutionController`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/controller.py) to honor `self.evaluator.higher_is_better` (supporting both maximization and minimization objectives) and format non-percentage metrics cleanly.
   - Add a minimization evaluator test in `tests/test_evaluator_protocol.py`.
2. **Simplify `workers.py` & Harden Subprocess `PYTHONPATH` (Findings #6, #8b)**:
   - Extract `_apply_memory_limit(max_memory_mb)` and `_compile_and_invoke(code, evaluator_fn, function_name)` in [`src/alpha_evolve/workers.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/workers.py), eliminating 3x duplication across `_sandbox_child_worker`, `_execute_in_thread`, and `_subprocess_runner_main`.
   - Unify `future.result(timeout=...)` exception handling in `WorkerPool.evaluate_candidate`.
   - Anchor subprocess `PYTHONPATH` to `Path(__file__).resolve().parent.parent` instead of `Path.cwd()`.
3. **Decouple `MockAlphaEvolveClient` & Add Client Lifecycle (Findings #4, #10, #12, #13)**:
   - Generalize `MockAlphaEvolveClient._mutate_seed_code` in [`src/alpha_evolve/client.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/client.py) so dry-run mutations work across Inventory Replenishment, Fleet Routing, and arbitrary `# EVOLVE-BLOCK` functions.
   - Add `close()`, `__enter__()`, and `__exit__()` to `AlphaEvolveClient` and `MockAlphaEvolveClient`.
   - Use `load_file_content` in `AlphaEvolveExperiment.from_files` and add `compile_candidate_callable` in `src/alpha_evolve/utils.py` for `examples/*/run_evolution.py`.

### Phase 4: Server Security, Caching & Telemetry Hygiene (Findings #8a, #9, #11)
1. **Enforce 1 MB Request Body Limit in FastAPI POST Routes ([`server.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py))**:
   - Add `_read_bounded_json(request: Request, max_bytes: int = 1_048_576)` raising HTTP 413 on oversized payloads in `/api/live-telemetry/candidate` and `/api/agent/replenish-query`, plus unit tests in `tests/test_server.py`.
2. **Add `mtime`-Keyed File Cache in [`server.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py) & Deduplicate Benchmark Setup in [`evaluate.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/examples/inventory_replenishment/src/evaluate.py)**:
   - Cache parsed JSON and HTML files by `(resolved_path, stat.st_mtime_ns)` so hot endpoints serve from memory with zero redundant disk I/O while automatically invalidating if files are updated or monkeypatched in tests.
   - Reuse `_CONFIG_FULL, _DEMAND_FULL, _PROMO_FULL` in `InventoryReplenishmentEvaluator.setup()`.
3. **Deduplicate `LiveTelemetryBroker` Default State ([`telemetry_broker.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/src/alpha_evolve/dashboard/telemetry_broker.py))**:
   - Extract `_default_state()` and call it in `__init__` and `clear()`.

---

## 5. Verification Plan

1. **Automated Quality Gates (`make check`)**:
   - `uv run --frozen ruff check .` (0 lint errors)
   - `uv run --frozen ruff format --check .` (100% formatted)
   - `uv run --frozen ty check src/` (0 type errors across all modules)
   - `uv run --frozen pytest -v` (all existing + new unit/integration tests green)
2. **Mutation Testing Verification (per `code-review-and-quality` Step 2)**:
   - Temporarily break a key in `fleet_routing_trajectory_generator.py` and verify the new schema/Node.js test in `tests/test_dashboard_builder.py` fails immediately.
   - Temporarily invert the comparison in `EvolutionController` for `higher_is_better=False` and verify the new minimization test in `tests/test_evaluator_protocol.py` fails immediately.
   - Send a >1 MB payload to FastAPI `POST /api/agent/replenish-query` in `tests/test_server.py` and verify it returns HTTP `413 Payload Too Large`.
