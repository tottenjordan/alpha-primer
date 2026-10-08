# Alpha Primer User Guide: End-to-End Operational Manual

This guide provides an end-to-end operational walkthrough of the `alpha-primer` repository, covering architecture concepts, prerequisites, execution modes, interactive visualizations, Cloud Run deployment, and developer workflows.

---

## 1. Overview & Core Concept

`alpha-primer` is a reference framework for **Google Cloud AlphaEvolve with Gemini Enterprise** (Discovery Engine v1alpha).

It solves complex enterprise optimization challenges by pairing LLM code-generation capabilities with closed-loop, data-isolated simulation engines.

### The Hybrid Execution Split

A foundational architectural principle of this repository is the strict separation between cloud-based LLM reasoning and private, local evaluation:

```mermaid
flowchart TD
    subgraph Cloud["Google Cloud Platform (Serverless)"]
        GE["Gemini Enterprise (Discovery Engine v1alpha)"]
        CR["Cloud Run (Dashboard, /api/simulate & Webhooks)"]
    end

    subgraph Local["Local Private Environment (Your Machine)"]
        CTL["AlphaEvolve Controller"]
        WP["Isolated Worker Pool (Multi-Process)"]
        DT["Domain Digital Twins (Inventory & Fleet Routing)"]
        DATA["Proprietary Telemetry, POS & Dispatch Data"]
    end

    CTL -- "1. Submit Initial Seed & Goals" --> GE
    GE -- "2. Stream Mutated Code (# EVOLVE-BLOCK)" --> CTL
    CTL -- "3. Dispatch Code" --> WP
    WP <--> DT
    DT <--> DATA
    WP -- "4. Return Scores & Diagnostic Insights" --> CTL
    CTL -- "5. Report Evaluation Results" --> GE
    CR -- "Query Evolved Policy & Run What-If" --> DT
```

- **Cloud (Serverless)**: Gemini Enterprise manages the evolutionary session and generates code mutations based on structured evaluation feedback.
- **Local (Isolated Sandbox)**: Digital twin simulations run 100% locally. Proprietary business logic, cost formulas, and customer demand or routing datasets never leave your private environment.

---

## 2. Prerequisites & Environment Setup

This project uses [`uv`](https://docs.astral.sh/uv/) for package and virtual environment management, [`ruff`](https://github.com/astral-sh/ruff) for linting and formatting, [`ty`](https://github.com/astral-sh/ty) for type checking, and [`pytest`](https://pytest.org/) for tests.

### Step 1: Install `uv`
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Step 2: Clone and Install Dependencies
```bash
git clone https://github.com/tottenjordan/alpha-primer.git
cd alpha-primer

# Synchronize all dependency groups using uv
uv sync --frozen --all-groups
```

### Step 3: Configure Environment
Copy the example configuration to `.env`:
```bash
cp .env.example .env
```

Key environment variables:
| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `PROJECT_ID` | Google Cloud Project ID | `hybrid-vertex` |
| `LOCATION` | Cloud Engine location | `global` |
| `COLLECTION` | Discovery Engine collection | `default_collection` |
| `ENGINE_ID` | Discovery Engine app ID | `alpha-evolve-experiment-engine` |
| `ASSISTANT_ID` | Discovery Engine assistant ID | `default_assistant` |
| `MOCK_ALPHAEVOLVE` | Enable offline mock client | `false` (or set `true` for offline) |

### Step 4: Google Cloud Authentication (For Cloud Modes)
```bash
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>
```

---

## 3. The 5 Execution Modes

### Mode A: Local Dry-Run (Offline Testing, Zero Cloud Quotas)
Run the full evolutionary loop locally without sending any API requests to Google Cloud. The system uses a deterministic mock client that generates synthetic candidate mutations to test your simulation engine and evaluator harness.

```bash
# Use Case 1: Perishable Inventory Replenishment Digital Twin
uv run --frozen python examples/inventory_replenishment/run_evolution.py --dry-run --max-programs 5

# Use Case 2: Dynamic Fleet Routing & Dispatch Digital Twin (VRPTW)
uv run --frozen python examples/fleet_routing/run_evolution.py --dry-run --max-programs 5
```

- **When to use**: Continuous Integration (CI), local code development, debugging evaluators, and rapid syntax verification.
- **Output**: Terminal logs displaying generation-by-generation scores and diagnostic insights, plus local artifacts in `artifacts/inventory_replenishment/` or `artifacts/fleet_routing/`.

---

### Mode B: Cloud Evolution with Gemini Enterprise
Execute live evolutionary search against Google Cloud Discovery Engine's AlphaEvolve v1alpha API:

```bash
# Live Cloud Evolution: Perishable Inventory Replenishment
uv run --frozen python examples/inventory_replenishment/run_evolution.py --max-programs 25 --workers 4

# Live Cloud Evolution: Dynamic Fleet Routing (VRPTW)
uv run --frozen python examples/fleet_routing/run_evolution.py --max-programs 25 --workers 4
```

- **Execution Flow**:
  1. Initializes a serverless session under your Discovery Engine instance.
  2. Creates an `alphaEvolveExperiments` resource and registers the initial baseline seed from `examples/inventory_replenishment/src/program.py` (`compute_replenishment_orders`) or `examples/fleet_routing/src/program.py` (`assign_and_sequence_routes`).
  3. Gemini 3.5 Flash inspects past scores and diagnostic insights to propose targeted code mutations in `# EVOLVE-BLOCK`.
  4. Local workers run the 3-tier evaluator (`InventoryReplenishmentEvaluator` or `VehicleRoutingEvaluator`), calculating cost reductions, service fill / on-time SLA rates, and spoilage / tardiness metrics.
  5. The cycle repeats until `--max-programs` is reached or convergence is achieved.
  6. Exports the global champion program and holdout evaluation summary to `artifacts/inventory_replenishment/` or `artifacts/fleet_routing/` (`best_evolved_program.py` and `best_evaluation_summary.json`).

---

### Mode C: Launch the Interactive Dashboard (Local Development)
Serve the interactive executive dashboard locally using the built-in web server:

```bash
uv run --frozen python server.py
```
Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)** in your browser.

#### Dashboard Capabilities
1. **Digital Twin Replay & Spatial Visualization (Tab 1)**:
   - Scrub through 31 generations of evolution (`Gen 0` to `Gen 30`) with `1x`/`2x` playback speed controls and keyboard navigation (`Space` to toggle play/pause, `←` / `→` to scrub).
   - **Primary Domain Canvas (Canvas 1)**:
     - *In Retail & Perishable Inventory mode*: Renders the **90-Day Digital Twin Inventory Trajectory & Spoilage Stack** across Warmup (`Days 0..29`), Eval (`Days 30..65`), and Holdout (`Days 66..89`) phases.
     - *In Dynamic Fleet Routing (VRPTW) mode*: Provides an interactive mode toggle (`#canvas1-mode-toggles`) between:
       - **2D Route Topology Map (`topology` mode)**: Dual-viewport Retina Canvas 2D spatial visualizer over a $100 \times 100\text{ km}$ urban grid with a central depot at $(50, 50)$ and 50 customer delivery stops across 4 quadrant clusters (30 static Wave 0 orders + 20 dynamic orders arriving mid-shift in Waves 1–4). Compares **GEN 0: GREEDY BASELINE** (crisscrossing trajectories, 19 intra-route crossings, 20 late stops) on the left against the selected generation on the right (**GEN 7: SLACK URGENCY**, **GEN 16: TRAFFIC + 2-OPT**, **GEN 30: REGRET-2 + 2-OPT** with **0 intra-route crossings**, `-28.5%` validation cost reduction, and `97.2%` on-time SLA). Includes a center **DELTA HUD** card summarizing `Crossings` (`19 → 0`), `Late Stops` (`20 → 7`), `On-Time`, `Distance`, and `PEAK WAVE LOAD` vehicle utilization bars (`V0`–`V4`), interactive filter pills (`All Waves`, `Wave 0 (Static)`, `Waves 1–4 (Dynamic)`, `SLA Breaches`, and vehicles `V0`–`V4`), and customer stop hover tooltips showing vehicle assignments, stop sequences, time windows, and late/on-time status.
       - **90-Step Shift Trajectory (`trajectory` mode)**: Time-series operational shift profile (`Steps 0..29 Morning Rush | 30..65 Midday | 66..89 Evening Wave`) tracking active route load, in-transit stops, and late events.
   - **Secondary Convergence Canvas (Canvas 2)**:
     - *Mode A (Pareto Frontier)*: 2D plot of Service Fill Rate / On-Time Delivery SLA vs. Cost Reduction with spoilage / late-penalty bubble gradients and the non-dominated frontier envelope.
     - *Mode B (Cost Waterfall)*: Stacked 31-generation breakdown showing reductions across Spoilage (`-$11.9k`), Stockout Penalties (`-$9.6k`), Holding (`-$1.2k`), and Ordering (`-$395`) for Inventory (`$68.4k` &rarr; `$45.2k`), or Fuel & Distance (`-$561`), SLA Tardiness Penalties (`-$362`), Overtime & Unserved Avoidance (`-$140`), and Fleet Dispatch Consolidation (`-$105`) for Fleet Routing (`$4,099` &rarr; `$2,931`).
   - **Interactive Milestone Ribbon**: Click any milestone node to jump directly to key breakthrough generations (`Gen 0`, `Gen 8`, `Gen 17`, `Gen 30` for Inventory; `Gen 0`, `Gen 7`, `Gen 16`, `Gen 30` for Fleet Routing).
2. **Interactive What-If Sandbox with Live `POST /api/simulate` Execution (Tab 2)**:
   - Run real-time dual-policy stress simulations comparing the Baseline policy against the compiled AlphaEvolve Champion heuristic side-by-side.
   - Adjusting any slider or archetype dispatches a debounced `POST /api/simulate` request to `server.py` (with sequence-ID race-condition protection and automatic `<2ms` client-side analytical fallback when offline), executing the real `InventoryDigitalTwin` or `FleetRoutingDigitalTwin` in Python.
   - **Domain-Adaptive Stress Parameters**:
     - *Archetype Selector*: Switch between SKU categories (`Ultra-Perishables (Berries / Pre-cut Salads - 3 Days)`, `Chilled Dairy & Fresh Meats (7 Days)`, `Ambient Grocery & Packaged Goods (21 Days)`) or Fleet route categories (`Tight-Window Urban Stops (1-hr SLA)`, `Commercial Metro Deliveries (2-hr SLA)`, `Suburban Perimeter Bulk Routes (4-hr SLA)`).
     - *Disruption Sliders*: Adjust Supplier Lead Time Delay (`+0` to `+5 days`) / Urban Traffic Congestion Delay (`+0` to `+60 mins`), Promotional Demand Spike / Dynamic Order Surge (`+0%` to `+150%`), Spoilage Cost / SLA Tardiness Penalty Multiplier (`0.5x` to `3.0x`), and Stockout Penalty / Unserved & Overtime Multiplier (`0.5x` to `3.0x`).
3. **Benchmark & Domain Mathematics (Tab 3)**:
   - Dynamically renders the domain-specific **Objective Function** (`Score = Cost_Reduction_% - 50.0 × max(0, 0.95 - Fill_Rate)^2` for Inventory vs. `Score = Cost_Reduction_% - 60.0 × max(0, 0.95 - OnTime_SLA)^2` for Fleet Routing), total cost decomposition equations (`C_holding + C_spoilage + C_stockout + C_ordering` vs. `C_distance + C_tardiness + C_overtime + C_dispatch`), causal isolation rules (`t <= now`), and 3-phase operational horizons (`Days 0..29 Warmup / Days 30..65 Validation / Days 66..89 Holdout` for Inventory; `Morning Rush 06:00..09:30 / Midday Window 09:30..15:30 / Evening Wave 15:30..18:00` for Fleet Routing).
4. **Evolved Code Diffs (Tab 4)**:
   - High-visibility AST code diff viewer powered by client-side LCS diffing and zero-dependency Python syntax highlighting.
   - Toggle between **Split** (side-by-side) and **Unified** diffs with line badges and foldable unchanged sections.
   - Use the **Milestone AST Stepper** to inspect exact code mutations between milestone generations (`Gen 0 ↔ Gen 8`, `Gen 8 ↔ Gen 17`, `Gen 17 ↔ Gen 30`, `Gen 0 ↔ Gen 30 (Full)` for Inventory; `Gen 0 ↔ Gen 7`, `Gen 7 ↔ Gen 16`, `Gen 16 ↔ Gen 30`, `Gen 0 ↔ Gen 30 (Full)` for Fleet Routing).
5. **Multi-Use-Case Domain Switcher**:
   - Seamlessly switch domains in the top navigation bar between:
     - 📦 **Retail & Perishable Inventory**: 90-day simulation tracking inventory on hand, in transit, FIFO spoilage waste, and $(s, S)$ vs. AlphaEvolve lookahead policies.
     - 🚚 **Dynamic Fleet Routing (VRPTW)**: 12-hour simulation tracking fleet travel costs, vehicle routing distance, time-window delivery deadlines, and greedy nearest-neighbor vs. AlphaEvolve regret-2 / 2-opt traffic-aware heuristics.
   - Instant Safe DOM re-binding of all KPI cards, milestone ribbons, 2D Route Topology Map / trajectory canvases, archetypes tables, What-If sandbox controls, and code diff AST selectors with zero page reload latency.

---

### Mode C.1: Real-Time Live Streaming Candidate Evaluations
Stream live candidate acquisitions and evaluation metrics directly into the executive dashboard over Server-Sent Events (SSE) as an optimization run executes:

**Terminal 1 — Launch Dashboard Server**:
```bash
uv run --frozen python server.py
```
Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)**. The status pill in the top-right header connects to `/api/stream/events` (`LIVE STREAMING (SSE)`, settling on `ADC VERIFIED (IDLE)` until a run begins).

**Terminal 2 — Run Optimization with Telemetry Streaming**:
```bash
# Dry-run mock evolution streaming to dashboard (Inventory or Fleet Routing)
uv run --frozen python examples/inventory_replenishment/run_evolution.py --dry-run --max-programs 20 --stream-to-dashboard
uv run --frozen python examples/fleet_routing/run_evolution.py --dry-run --max-programs 20 --stream-to-dashboard

# Live Cloud evolution streaming to dashboard
uv run --frozen python examples/inventory_replenishment/run_evolution.py --max-programs 30 --workers 4 --stream-to-dashboard
uv run --frozen python examples/fleet_routing/run_evolution.py --max-programs 30 --workers 4 --stream-to-dashboard
```

#### Real-Time Visualizer Features
- **Dynamic Scrubber Range**: Scrubber track and maximum counter automatically expand as each candidate finishes evaluation.
- **Dynamic 2D Pareto Frontier & Topology Map**: New candidate bubbles are dynamically plotted on Retina Canvas 2D, non-dominated frontier curves recalculate live, and the Fleet Routing 2D Route Topology Map updates the right-hand viewport header and delta metrics dynamically.
- **Dynamic Milestone Ribbon**: Whenever a candidate achieves a new best fitness score, a milestone node is appended to the ribbon with instant click-to-scrub navigation.
- **Live Toast Notifications**: Non-intrusive notifications pop in the bottom-right corner displaying candidate IDs, validation scores, and breakthrough alerts.
- **Graceful Offline Fallback**: If the server is stopped or running in static mode, the dashboard gracefully transitions to `ARCHIVE MODE (OFFLINE)` while preserving all historical interactive playback.

---

### Mode D: Serverless Cloud Run Deployment, Live `/api/simulate`, & Gemini Enterprise Webhooks
Deploy the full web dashboard, live digital twin simulation engine, and Gemini Enterprise agent webhooks to Google Cloud Run with automated Artifact Registry provisioning, security hardening, and optional Discovery Engine external agent registration:

```bash
# Automated deployment with active gcloud credentials
./scripts/deploy_cloud_run.sh

# Or deploy via Makefile target
make deploy

# Dry-run validation (synthesizes exact execution plan without cloud mutations)
make deploy-dry-run

# Custom deployment with specific GCP project, region, and Gemini Enterprise Engine ID:
./scripts/deploy_cloud_run.sh \
  --project=my-project-id \
  --region=us-central1 \
  --service-name=alpha-evolve-primer-ui \
  --engine-id=my-experiment-engine \
  --register-agent
```

#### What This Provisions & Automates
1. **Pre-flight Checks**: Verifies `gcloud` authentication and ensures required Google Cloud APIs (`run.googleapis.com`, `cloudbuild.googleapis.com`, `artifactregistry.googleapis.com`, `discoveryengine.googleapis.com`) are accessible.
2. **Container Registry Setup**: Ensures an **Artifact Registry** repository (`alpha-evolve-repo`) exists in the specified region.
3. **Cloud Build Submission**: Submits a multi-stage non-root container build (`python:3.12-slim` + `uv` frozen dependencies) to **Google Cloud Build**.
4. **Serverless Cloud Run Deployment**: Deploys managed service with tuned parameters:
   - Concurrency: 80 requests/instance
   - Memory: 512Mi / 1 vCPU
   - Auto-scaling: 0 to 5 instances (scale-to-zero when idle)
   - Strict enterprise security headers: Content-Security-Policy (CSP), HSTS, nosniff, frame-ancestors, and a 1 MB request payload limit (`HTTP 413` protection).
5. **Post-Deployment Health Check**: Automatically probes `${SERVICE_URL}/health` and `${SERVICE_URL}/api/cloud-status`.
6. **Gemini Enterprise Assistant Registration**: Automatically registers the Cloud Run webhook endpoint (`${SERVICE_URL}/api/agent/replenish-query` and multi-domain `${SERVICE_URL}/api/agent/query`) as an External Agent under `assistants/default_assistant/agents` in Discovery Engine v1alpha.
7. **CI/CD Automation**: Fully declarative build via [`cloudbuild.yaml`](../cloudbuild.yaml) and GitHub Actions workflow via [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).

#### HTTP API & Webhook Reference (`server.py`)

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Interactive executive dashboard (`dashboard/index.html` with Safe DOM, Retina Canvas 2D, 2D Route Topology Map, What-If Sandbox, and AST code diffs). |
| `/health` | `GET` | Service health probe and ADC credential status (`secrets_leaked: false`). |
| `/api/cloud-status` | `GET` | Discovery Engine connection metadata and multi-use-case experiment summaries. |
| `/api/data` | `GET` | Master multi-domain trajectory bundle (`dashboard/data.json`). |
| `/api/trajectories/{use_case_id}` | `GET` | 31-generation trajectory dataset for `inventory_replenishment` or `fleet_routing`. |
| `/api/simulate` | `POST` | **Live Digital Twin Simulation**: Executes `InventoryDigitalTwin` or `FleetRoutingDigitalTwin` comparing Baseline vs. Champion under custom stress parameters. |
| `/api/agent/query` | `GET`, `POST` | **Multi-Domain Gemini Enterprise Webhook**: Returns StreamAssist Markdown grounding cards, KPI metrics, and optional live `what_if_stress_test` simulations for `inventory_replenishment` (`inventory-replenishment-twin`) or `fleet_routing` (`fleet-routing-twin`). |
| `/api/agent/replenish-query` | `GET`, `POST` | Backward-compatible Gemini Enterprise webhook defaulting to `inventory_replenishment`. |
| `/api/live/state` | `GET` | Current real-time telemetry broker state snapshot (`IDLE` or active run metrics). |
| `/api/live/candidates` | `POST` | Ingests a newly evaluated candidate event and broadcasts it to all SSE subscribers. |
| `/api/stream/events` | `GET` | Server-Sent Events (`text/event-stream`) feed for real-time dashboard updates. |

#### Example 1: Live Digital Twin Stress Simulation (`POST /api/simulate`)
```bash
# Simulate Perishable Inventory Replenishment under a 3-day lead-time delay and +30% promo spike
curl -s -X POST http://127.0.0.1:8080/api/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "use_case": "inventory_replenishment",
    "archetype_index": 0,
    "lead_time_delay": 3.0,
    "promo_spike_pct": 30.0,
    "spoilage_multiplier": 1.5,
    "stockout_multiplier": 1.2
  }' | jq .

# Simulate Dynamic Fleet Routing (VRPTW) under traffic congestion delay and +35% order surge
curl -s -X POST http://127.0.0.1:8080/api/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "use_case": "fleet_routing",
    "archetype_index": 0,
    "lead_time_delay": 3.0,
    "promo_spike_pct": 35.0,
    "spoilage_multiplier": 1.4,
    "stockout_multiplier": 1.4
  }' | jq .
```

#### Example 2: Multi-Domain Gemini Enterprise Agent Query (`POST /api/agent/query`)
```bash
# Query the Fleet Routing Digital Twin Agent with a live What-If stress test
curl -s -X POST http://127.0.0.1:8080/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "use_case": "fleet_routing",
    "query": "what-if",
    "archetype_index": 1,
    "lead_time_delay": 2.0,
    "promo_spike_pct": 25.0
  }' | jq .
```

---

### Mode E: Developer Quality, Dashboard Compilation & Test Workflows
All contributions must adhere to the quality standards defined in [`CODE_STANDARDS.md`](../CODE_STANDARDS.md):

```bash
# Run full test suite across SDK, server, dashboard, and domain digital twins
uv run --frozen pytest -v

# Run ruff linter
uv run --frozen ruff check .

# Run ruff code formatter check
uv run --frozen ruff format --check .

# Run static type checking with ty
uv run --frozen ty check src/

# Run all quality gates at once
make check

# Regenerate 31-generation trajectory datasets and recompile dashboard/index.html
PYTHONPATH=.:src uv run --frozen python -m alpha_evolve.dashboard.trajectory_generator
PYTHONPATH=.:src uv run --frozen python -m alpha_evolve.dashboard.fleet_routing_trajectory_generator
PYTHONPATH=.:src uv run --frozen python -m alpha_evolve.dashboard.build_dashboard
```

---

## 4. Authoring Custom Evaluators (`BaseEvaluator`)

AlphaEvolve uses a **multi-tiered evaluation architecture** (`src/alpha_evolve/evaluators/`) to accelerate evolutionary loops by early-exiting broken candidates before running expensive simulations:

1. **Tier 1 (Smoke Sanity Check, <100ms)**: Fast input/output shape, type (`np.ndarray`), numerical validity (no NaN/Inf), and domain constraint checks.
2. **Tier 2 (Validation Rollout, 1s-30s)**: Full simulation computing primary fitness score and diagnostic feedback strings.
3. **Tier 3 (Holdout Generalization)**: Out-of-sample evaluation on unseen test datasets to detect overfitting.

### Creating a Domain Evaluator Subclass

To create a new evaluator for your domain:
1. Subclass `BaseEvaluator` from `alpha_evolve.evaluators`.
2. Define class attributes: `name`, `primary_metric`, `higher_is_better`, and `target_function_name`.
3. Implement `evaluate_smoke()` and `evaluate_validation()`.
4. (Optional) Implement `setup()` to cache datasets and `evaluate_holdout()` for out-of-sample testing.

```python
from typing import Any
from alpha_evolve.evaluators import BaseEvaluator, EvaluationTier, TierResult


class MyCustomEvaluator(BaseEvaluator):
    name = "my_custom_evaluator"
    primary_metric = "cost_reduction_pct"
    higher_is_better = True
    target_function_name = "solve"

    def evaluate_smoke(self, candidate_callable: Any) -> TierResult:
        try:
            out = candidate_callable(0)
            if out < 0:
                return TierResult.failure(EvaluationTier.SMOKE, "Output must be non-negative")
            return TierResult.success(EvaluationTier.SMOKE, {"smoke_passed": 1.0})
        except Exception as e:
            return TierResult.failure(EvaluationTier.SMOKE, f"Crashed: {e}")

    def evaluate_validation(self, candidate_callable: Any) -> TierResult:
        # Run simulation and score
        score = candidate_callable(10)
        return TierResult.success(
            EvaluationTier.VALIDATION,
            metrics={"cost_reduction_pct": float(score)},
            insights={"summary": f"Achieved score {score}"},
        )
```

Pass the evaluator instance directly to `AlphaEvolveExperiment` or `EvolutionController`:
```python
experiment = AlphaEvolveExperiment.from_files(
    experiment_name="My Optimization",
    instructions_path="instructions.md",
    seed_program_path="src/program.py",
    evaluator=MyCustomEvaluator(),
)
```

---

## 5. Candidate Execution Sandboxing & Security

During evolutionary search, LLMs generate arbitrary Python code mutations that are executed iteratively. To protect the host system, prevent runaway CPU loops, isolate segfaults or fatal exits, and restrict unbounded memory growth, AlphaEvolve provides **OS-level sandboxing** in `alpha_evolve.workers`:

### Sandbox Modes

Configured via `RunSettings.sandbox_mode` in `alpha_evolve.models`:

1. **`process` (Default, Recommended for Production)**:
   - Spawns candidate evaluation in an isolated POSIX process (`multiprocessing.get_context("spawn")`).
   - Traps fatal terminations (`os._exit()`, `sys.exit()`, segfaults) without terminating the controller.
   - Enforces virtual memory caps (`RLIMIT_AS`) on POSIX systems via `resource.setrlimit`.
   - Employs escalating unblockable termination: graceful `SIGTERM`, followed by non-catchable `SIGKILL` on timeout expiration to prevent zombie CPU starvation.
   - Gracefully falls back to thread execution for unpicklable local closures/lambdas.

2. **`subprocess`**:
   - Executes candidate evaluation in a completely clean, isolated OS process via `subprocess.Popen` running `python -m alpha_evolve.workers`.
   - Completely resets the Python interpreter runtime, garbage collection state, and memory space.
   - Ideal for untrusted multi-tenant execution or code with native C extensions.

3. **`thread` (Lightweight / Local Debugging)**:
   - Evaluates candidates in a `ThreadPoolExecutor` within the controller process.
   - Minimum spawning overhead; suitable for fast unit testing or environments without process spawning support.

### Configuring Sandboxing in Code

```python
from alpha_evolve.models import ExperimentConfig, RunSettings

config = ExperimentConfig(
    project_id="hybrid-vertex",
    engine_id="alpha-evolve-experiment-engine",
    experiment_name="Sandboxed Optimization",
    user_instructions="Optimize the target policy inside # EVOLVE-BLOCK.",
    seed_code="# EVOLVE-BLOCK-START\ndef solve(x):\n    return x\n# EVOLVE-BLOCK-END\n",
    run_settings=RunSettings(
        max_evaluation_time_s=30.0,  # Max seconds before SIGTERM/SIGKILL escalation
        max_memory_mb=2048,  # Hard virtual memory limit (RLIMIT_AS) in MB
        sandbox_mode="process",  # "process" | "subprocess" | "thread"
    ),
)
```

---

## 6. Key Repository Map

```
alpha-primer/
├── examples/inventory_replenishment/  # Flagship use case: Perishable inventory digital twin
│   ├── src/
│   │   ├── program.py                 # Candidate policy (# EVOLVE-BLOCK)
│   │   ├── simulator.py               # Vectorized FIFO inventory digital twin engine
│   │   ├── evaluate.py                # InventoryReplenishmentEvaluator (3-tier validation harness)
│   │   └── report.py                  # Post-evolution benchmark reporting
│   ├── tests/                         # Unit tests for simulator and evaluator
│   ├── DATASET.md                     # Complete dataset specification (50 SKUs, 90 days)
│   ├── README.md                      # Use case summary and problem formulation
│   ├── instructions.md                # Domain prompt context for Gemini Enterprise
│   └── run_evolution.py               # CLI entrypoint for local or cloud evolution
├── examples/fleet_routing/            # Dynamic Fleet Routing & Dispatch Digital Twin
│   ├── src/
│   │   ├── program.py                 # Greedy route dispatch policy (# EVOLVE-BLOCK)
│   │   ├── simulator.py               # Spatial digital twin with dynamic traffic & causal isolation
│   │   ├── evaluate.py                # VehicleRoutingEvaluator (3-tier validation harness)
│   │   └── report.py                  # Post-evolution holdout analytics and reporting
│   ├── tests/                         # Unit tests for routing simulator and evaluator
│   ├── README.md                      # Urban fleet routing problem formulation and results
│   ├── instructions.md                # Domain prompt context for Gemini Enterprise
│   └── run_evolution.py               # CLI entrypoint for fleet routing evolution
├── src/alpha_evolve/                  # Core client library & orchestration runtime
│   ├── client.py                      # Discovery Engine v1alpha REST client with ADC
│   ├── controller.py                  # Evolutionary search loop manager
│   ├── experiment.py                  # High-level AlphaEvolveExperiment orchestrator
│   ├── evaluators/                    # Abstract Evaluator Protocol & BaseEvaluator ABC
│   │   ├── __init__.py                # Exported protocol schemas and base classes
│   │   └── base.py                    # EvaluationTier, TierResult, EvaluatorProtocol, BaseEvaluator
│   ├── models.py                      # Type-safe Pydantic schemas (scores, insights, configs)
│   ├── utils.py                       # EVOLVE-BLOCK extraction, compilation & artifact export
│   ├── workers.py                     # True process/subprocess sandboxed worker pool
│   └── dashboard/                     # Trajectory aggregation, SSE broker & dashboard compiler
│       ├── trajectory_utils.py        # Shared S-curve interpolation & master bundle utilities
│       ├── trajectory_generator.py    # 31-generation Inventory Replenishment trajectory builder
│       ├── fleet_routing_trajectory_generator.py # 31-gen Fleet Routing & 2D spatial topology builder
│       ├── build_dashboard.py         # Safe DOM HTML/CSS/JS compiler
│       ├── telemetry_broker.py        # Thread-safe Server-Sent Events pub/sub broker
│       └── templates/                 # Modular Safe DOM UI templates (styles.css, body.html, app.js)
├── dashboard/                         # Compiled web dashboard bundle
│   ├── index.html                     # Safe DOM, Retina Canvas 2D, 2D Route Topology Map, LCS diff engine
│   └── data.json                      # Precompiled 31-generation master trajectory records
├── records/                           # Domain trajectory & spatial topology datasets
│   ├── master_trajectories.json       # Unified multi-use-case trajectory bundle
│   ├── inventory_replenishment_trajectory.json # Perishable inventory 31-gen records
│   └── fleet_routing_trajectory.json  # Fleet routing 31-gen records & 50-stop spatial topology
├── server.py                          # Production HTTP server, live /api/simulate & Gemini webhooks
├── cloudbuild.yaml                    # Declarative Google Cloud Build & Cloud Run pipeline
├── Dockerfile                         # Non-root hardened container (uv frozen dependencies)
├── .github/workflows/
│   ├── ci.yml                         # Automated quality, lint, typecheck & test matrix
│   └── deploy.yml                     # Automated Cloud Run & agent webhook deployment
├── scripts/
│   └── deploy_cloud_run.sh            # Automated Cloud Build & Cloud Run deployment script
├── docs/
│   ├── USER_GUIDE.md                  # This document
│   ├── architecture/                  # High-resolution architectural diagrams
│   └── notes/                         # Technical session notes and wire specifications
├── CODE_STANDARDS.md                  # Development rules (uv, ruff, ty, pytest, git)
└── pyproject.toml                     # Modern PEP 621/735 project configuration
```

---

## 7. Further Reading & Documentation

- [**Candidate Execution Sandboxing**](notes/candidate_sandboxing.md): Process isolation architecture, OS-level `RLIMIT_AS` memory capping, and SIGKILL termination escalation.
- [**Abstract Evaluator Protocol**](notes/abstract_evaluator_protocol.md): Multi-tier evaluation design, short-circuiting architecture, lifecycle hooks, and authoring guide.
- [**Inventory Replenishment Dataset Specification**](../examples/inventory_replenishment/DATASET.md): Full breakdown of SKU distributions, Poisson demand, promo lifts, and cost parameters.
- [**Dynamic Fleet Routing (VRPTW) Guide**](../examples/fleet_routing/README.md): Problem formulation, 3-tier `VehicleRoutingEvaluator` scoring function, and execution walkthrough.
- [**Architecture Diagrams**](architecture/README.md): Reference diagrams for the hybrid evolutionary architecture, Cloud Run integration, and digital twin loop.
- [**AlphaEvolve REST Wire Specification**](notes/alphaevolve_api_wire_spec.md): Complete HTTP wire schemas for Discovery Engine v1alpha.
- [**Cloud Run Hosting & Agent Grounding**](notes/google_cloud_run_hosting.md): Deployment architecture, IAM roles, and Gemini Enterprise agent webhook registration.
