# AlphaEvolve Enterprise Use Cases

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20by-uv-blueviolet.svg)](https://github.com/astral-sh/uv)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked by ty](https://img.shields.io/badge/type%20checker-ty-brightgreen.svg)](https://github.com/astral-sh/ty)

A curated collection of production-grade, end-to-end **AlphaEvolve** code examples demonstrating how to architect and implement evolutionary coding agents with **Gemini Enterprise** to solve high-value enterprise optimization problems.

---

## What is AlphaEvolve?

AlphaEvolve is Google's agentic evolutionary coding capability powered by Gemini Enterprise. By combining the exploratory reasoning of Gemini models with automated closed-loop evaluation, AlphaEvolve autonomously explores, discovers, and optimizes complex algorithms, heuristics, and decision policies.

---

## Repository Structure

```
├── examples/                   # Standalone, end-to-end enterprise use cases
│   └── inventory_replenishment/# Multi-Echelon & Perishable Digital Twin
├── src/alpha_evolve/           # Shared, type-safe AlphaEvolve client & runtime
│   ├── client.py               # Discovery Engine V1alpha REST API client
│   ├── controller.py           # Evolutionary loop manager
│   ├── models.py               # Pydantic data schemas (Experiment, Program, Scores)
│   └── workers.py              # Isolated evaluation worker pool
├── docs/                       # Architectural specs and session notes
├── pyproject.toml              # Modern uv project definition (ruff, ty, pytest)
└── Makefile                    # Standard developer workflow commands
```

---

## Quickstart

### 1. Prerequisites

- Python `>=3.11`
- [`uv`](https://docs.astral.sh/uv/) package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Google Cloud SDK (`gcloud`) with access to Gemini Enterprise / Discovery Engine

### 2. Environment Setup

```bash
# Clone the repository
git clone <repo-url>
cd alpha-primer

# Install dependencies with uv
make dev
# or: uv sync --all-groups
```

### 3. Configure Google Cloud Access

Copy `.env.example` to `.env` and fill in your project credentials:

```bash
cp .env.example .env
```

To run offline in **Dry-Run Mode** without consuming Google Cloud quotas, set `MOCK_ALPHAEVOLVE=true` in `.env` or pass the `--dry-run` flag.

### 4. Running Your First Use Case

Navigate to any example directory or run directly from root:

```bash
# Run the Inventory Replenishment Digital Twin in dry-run mode
uv run python examples/inventory_replenishment/run_evolution.py --dry-run --max-programs 5

# Run with live Gemini Enterprise API
uv run python examples/inventory_replenishment/run_evolution.py --max-programs 20
```

---

## Featured Use Cases

| Example | Vertical | Method | Evaluation Paradigm | Primary Metric |
| :--- | :--- | :--- | :--- | :--- |
| [Inventory Replenishment](examples/inventory_replenishment/README.md) | Grocery, Retail, Supply Chain | Dynamic $(s, S)$ FIFO Aging | **Simulation** (Digital Twin) | Total Supply Chain Cost Reduction & Spoilage Rate |

---

## Development & Testing

We enforce strict quality and modern Python standards (see [CODE_STANDARDS.md](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/CODE_STANDARDS.md)):

```bash
make lint       # uv run ruff check .
make format     # uv run ruff format .
make typecheck  # uv run ty check src/
make test       # uv run pytest -v
make check      # runs all lint, format, typecheck, and test checks
```
