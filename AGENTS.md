# Alpha Primer — AI Agent Instructions & Repository Context

> [!IMPORTANT]
> **Always refer to [CODE_STANDARDS.md](CODE_STANDARDS.md) before writing code, modifying dependencies, adding tests, or making environment changes.** All contributions must strictly comply with the guidelines defined there.

---

## 1. Repository Architecture & Key Paths

- **Core SDK (`src/alpha_evolve/`)**:
  - `client.py`, `controller.py`, `experiment.py`, `models.py`, `utils.py` — Discovery Engine (`v1alpha`) AlphaEvolve client, evaluation controller, and candidate compilation utilities.
  - `evaluators/base.py` — `EvaluatorProtocol`, `BaseEvaluator` (3-tier evaluation cascade), and `resolve_evaluator`.
  - `workers.py` — Sandboxed process and subprocess worker pool with memory and timeout enforcement.
  - `dashboard/` — `telemetry_broker.py` (SSE pub/sub), `trajectory_utils.py`, `trajectory_generator.py`, `fleet_routing_trajectory_generator.py`, `build_dashboard.py`, and template assets under `src/alpha_evolve/dashboard/templates/` (`styles.css`, `body.html`, `app.js`).
- **Digital Twin Use Cases (`examples/`)**:
  - `examples/inventory_replenishment/` — Autonomous Multi-Echelon & Perishable Inventory Replenishment (`src/program.py`, `src/simulator.py`, `src/evaluate.py`, `run_evolution.py`).
  - `examples/fleet_routing/` — Dynamic Fleet Routing & Dispatch with Time Windows (`src/program.py`, `src/simulator.py`, `src/evaluate.py`, `run_evolution.py`).
- **Dashboard & Cloud Run Server**:
  - `server.py` — Production HTTP server (FastAPI + stdlib fallback) serving the interactive UI, SSE telemetry stream (`/api/stream/events`), and Gemini Enterprise StreamAssist webhook (`/api/agent/replenish-query`).
  - `dashboard/` — Compiled static bundle (`index.html`, `data.json`).
  - `records/` — Trajectory datasets (`master_trajectories.json`, `inventory_replenishment_trajectory.json`, `fleet_routing_trajectory.json`).
- **Tests (`tests/` & `examples/*/tests/`)**:
  - Top-level SDK, dashboard, deployment, and server tests in `tests/`.
  - Domain simulator, seed policy, and evaluator tests in `examples/inventory_replenishment/tests/` and `examples/fleet_routing/tests/`.

---

## 2. Tech Stack & Tooling Constraints

1. **Python & Package Management (`uv`)**:
   - Target Python `>=3.11`.
   - Use `uv` exclusively (`uv add`, `uv remove`, `uv sync`). **Never** use bare `pip` or bare `python`.
   - **Never** manually activate virtual environments (`source .venv/bin/activate`). Run all commands via `uv run --frozen <cmd>`.
   - Manage development and test dependencies via `[dependency-groups]` (PEP 735) in `pyproject.toml`.
2. **Linting & Formatting (`ruff`)**:
   - Use `ruff` exclusively (`line-length = 100`, `target-version = "py311"`). **Never** use `black`, `flake8`, or `isort`.
3. **Type Checking (`ty`) & Testing (`pytest`)**:
   - Use `ty` for static type checking (`uv run --frozen ty check src/`). **Never** use `mypy` or `pyright`.
   - Use `pytest` for all test execution (`uv run --frozen pytest -v`).
4. **Frontend Safe DOM Standard**:
   - Dashboard UI code (`src/alpha_evolve/dashboard/templates/app.js` and `dashboard/index.html`) must strictly use Safe DOM APIs (`document.createElement`, `textContent`, `replaceChildren`) with **zero `innerHTML`**.

---

## 3. Build, Verification & Deployment Commands

```bash
# Sync all dependencies
uv sync --frozen --all-groups

# Lint & format check
uv run --frozen ruff check src/ tests/ examples/ server.py
uv run --frozen ruff format --check src/ tests/ examples/ server.py

# Type check
uv run --frozen ty check src/

# Run full test suite (tests/ + examples/*/tests/)
uv run --frozen pytest -v

# Run all quality gates via Makefile
make check

# Regenerate trajectory datasets & compile dashboard/index.html
PYTHONPATH=.:src uv run --frozen python -m alpha_evolve.dashboard.trajectory_generator
PYTHONPATH=.:src uv run --frozen python -m alpha_evolve.dashboard.fleet_routing_trajectory_generator
PYTHONPATH=.:src uv run --frozen python -m alpha_evolve.dashboard.build_dashboard

# Cloud Run deployment (dry-run or live)
bash scripts/deploy_cloud_run.sh --dry-run
bash scripts/deploy_cloud_run.sh
```

---

## 4. Git Operations & Collaboration

- **Branching**: Always work on a feature branch; `main` is merged exclusively via pull request.
- **Commits**: Commit frequently (one logical change per commit), ensuring every commit leaves the test suite green. Follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`).
- **PRs & Push Policy**:
  - You do not need permission to commit and push to a feature branch or open a PR for review.
  - **Never** push directly to `main` without explicit approval.
  - **Never** add `Co-Authored-By` trailers in commits or pull request descriptions.
- **Session Notes**:
  - Document cross-session, non-recoverable insights under `docs/notes/` organized by topic.
  - Keep the top-level index [docs/notes/README.md](docs/notes/README.md) under 200 lines and verify files/flags exist before documenting or acting on them.
