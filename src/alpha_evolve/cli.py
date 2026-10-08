"""Unified command-line interface and use-case scaffolder for AlphaEvolve.

Provides subcommands for inspecting registered digital twin domains, executing
offline dry-run or live AlphaEvolve evolutionary loops, and scaffolding new
3-tier digital twin use cases:

    alpha-evolve list
    alpha-evolve run <use_case> [--dry-run] [--max-programs N]
    alpha-evolve init <new_use_case> [--output-dir ...]
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import keyword
import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from rich.console import Console
from rich.table import Table

from alpha_evolve.dashboard.telemetry_broker import get_global_broker
from alpha_evolve.evaluators.base import BaseEvaluator
from alpha_evolve.experiment import AlphaEvolveExperiment
from alpha_evolve.models import ProgramCandidate
from alpha_evolve.utils import compile_candidate_callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXAMPLES_DIR = REPO_ROOT / "examples"


@dataclass(frozen=True)
class UseCaseInfo:
    """Metadata describing an available AlphaEvolve digital twin use case."""

    name: str
    title: str
    description: str
    path: Path
    target_function: str
    primary_metric: str
    evaluator_class: str

    def to_dict(self) -> dict[str, str]:
        """Serialize metadata to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "path": str(self.path),
            "target_function": self.target_function,
            "primary_metric": self.primary_metric,
            "evaluator_class": self.evaluator_class,
        }


_BUILTIN_USE_CASES: dict[str, dict[str, str]] = {
    "inventory_replenishment": {
        "title": "Inventory Replenishment Digital Twin (BASF Reference)",
        "description": (
            "Autonomous multi-echelon & perishable FIFO inventory replenishment "
            "with promotional demand spikes and supplier lead times."
        ),
        "target_function": "compute_replenishment_orders",
        "primary_metric": "cost_reduction_pct",
        "evaluator_class": "InventoryReplenishmentEvaluator",
    },
    "fleet_routing": {
        "title": "Dynamic Fleet Routing & Dispatch Digital Twin",
        "description": (
            "Capacitated vehicle routing with customer time windows (VRPTW), "
            "stochastic dynamic order arrivals, and rush-hour congestion."
        ),
        "target_function": "assign_and_sequence_routes",
        "primary_metric": "score",
        "evaluator_class": "VehicleRoutingEvaluator",
    },
}


def normalize_use_case_name(raw_name: str) -> str:
    """Normalize and validate a use-case identifier slug.

    Converts hyphens and spaces to underscores and verifies the resulting name
    is a safe, valid Python identifier.
    """
    cleaned = raw_name.strip()
    if not cleaned:
        raise ValueError("Use-case name must not be empty.")
    if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise ValueError(
            f"Invalid use-case name '{raw_name}': path separators and '..' are not allowed."
        )
    slug = re.sub(r"[-\s]+", "_", cleaned.lower())
    if not slug.isidentifier() or keyword.iskeyword(slug) or slug.startswith("_"):
        raise ValueError(
            f"Invalid use-case name '{raw_name}': must be a valid Python identifier "
            "(letters, digits, underscores, starting with a letter)."
        )
    return slug


def _to_pascal_case(slug: str) -> str:
    """Convert a snake_case slug into PascalCase."""
    return "".join(part.capitalize() for part in slug.split("_") if part)


def _to_title_case(slug: str) -> str:
    """Convert a snake_case slug into human-readable Title Case."""
    return " ".join(part.capitalize() for part in slug.split("_") if part)


def _inspect_use_case_dir(use_case_dir: Path) -> UseCaseInfo | None:
    """Inspect a candidate directory and return UseCaseInfo if it is a valid use case."""
    if not use_case_dir.is_dir():
        return None

    slug = use_case_dir.name
    program_path = use_case_dir / "src" / "program.py"
    evaluate_path = use_case_dir / "src" / "evaluate.py"
    if not program_path.is_file() or not evaluate_path.is_file():
        return None

    if slug in _BUILTIN_USE_CASES:
        meta = _BUILTIN_USE_CASES[slug]
        return UseCaseInfo(
            name=slug,
            title=meta["title"],
            description=meta["description"],
            path=use_case_dir.resolve(),
            target_function=meta["target_function"],
            primary_metric=meta["primary_metric"],
            evaluator_class=meta["evaluator_class"],
        )

    eval_source = evaluate_path.read_text(encoding="utf-8")
    target_match = re.search(
        r'target_function_name(?:\s*:\s*str)?\s*=\s*["\']([^"\']+)["\']', eval_source
    )
    metric_match = re.search(
        r'primary_metric(?:\s*:\s*str)?\s*=\s*["\']([^"\']+)["\']', eval_source
    )
    class_match = re.search(r"class\s+(\w+)\s*\(\s*BaseEvaluator\s*\)", eval_source)

    target_fn = target_match.group(1) if target_match else "solve_policy"
    primary_metric = metric_match.group(1) if metric_match else "score"
    evaluator_class = class_match.group(1) if class_match else f"{_to_pascal_case(slug)}Evaluator"

    title = f"{_to_title_case(slug)} Digital Twin"
    instructions_path = use_case_dir / "instructions.md"
    description = f"Custom AlphaEvolve digital twin optimization domain ({slug})."
    if instructions_path.is_file():
        for line in instructions_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped.lstrip("# ").strip()
                break

    return UseCaseInfo(
        name=slug,
        title=title,
        description=description,
        path=use_case_dir.resolve(),
        target_function=target_fn,
        primary_metric=primary_metric,
        evaluator_class=evaluator_class,
    )


def discover_use_cases(examples_dir: str | Path | None = None) -> list[UseCaseInfo]:
    """Discover all valid AlphaEvolve use cases under examples_dir."""
    base_dir = Path(examples_dir) if examples_dir is not None else DEFAULT_EXAMPLES_DIR
    if not base_dir.is_dir():
        return []

    discovered: dict[str, UseCaseInfo] = {}
    for child in sorted(base_dir.iterdir()):
        if child.name.startswith(".") or child.name.startswith("_"):
            continue
        info = _inspect_use_case_dir(child)
        if info is not None:
            discovered[info.name] = info

    ordered: list[UseCaseInfo] = []
    for builtin_key in _BUILTIN_USE_CASES:
        if builtin_key in discovered:
            ordered.append(discovered.pop(builtin_key))
    for remaining_key in sorted(discovered):
        ordered.append(discovered[remaining_key])
    return ordered


def resolve_use_case(use_case: str, examples_dir: str | Path | None = None) -> UseCaseInfo:
    """Resolve a use case by name, hyphenated alias, or filesystem path."""
    raw = use_case.strip()
    if not raw:
        raise ValueError("Use-case name must not be empty.")

    candidate_path = Path(raw)
    if candidate_path.is_dir():
        info = _inspect_use_case_dir(candidate_path)
        if info is not None:
            return info

    base_dir = Path(examples_dir) if examples_dir is not None else DEFAULT_EXAMPLES_DIR
    slug = normalize_use_case_name(raw)
    target_dir = base_dir / slug
    info = _inspect_use_case_dir(target_dir)
    if info is not None:
        return info

    available = [u.name for u in discover_use_cases(base_dir)]
    available_str = ", ".join(available) if available else "none"
    raise ValueError(f"Unknown use case '{use_case}'. Available use cases: {available_str}.")


def _load_use_case_submodule(use_case_dir: Path, module_stem: str) -> ModuleType:
    """Import `<use_case>.src.<module_stem>` after ensuring its parent directory is on sys.path."""
    resolved_dir = use_case_dir.resolve()
    parent_str = str(resolved_dir.parent)
    if parent_str not in sys.path:
        sys.path.insert(0, parent_str)

    current_py_path = os.environ.get("PYTHONPATH", "")
    py_parts = [p for p in current_py_path.split(os.pathsep) if p]
    if parent_str not in py_parts:
        os.environ["PYTHONPATH"] = (
            f"{parent_str}{os.pathsep}{current_py_path}" if current_py_path else parent_str
        )

    module_name = f"{resolved_dir.name}.src.{module_stem}"
    if module_name in sys.modules:
        cached = sys.modules[module_name]
        cached_file = getattr(cached, "__file__", None)
        expected_file = str(resolved_dir / "src" / f"{module_stem}.py")
        if cached_file and Path(cached_file).resolve() != Path(expected_file).resolve():
            for key in list(sys.modules):
                if key == resolved_dir.name or key.startswith(f"{resolved_dir.name}."):
                    sys.modules.pop(key, None)

    return importlib.import_module(module_name)


def _instantiate_evaluator(evaluate_mod: ModuleType, expected_class_name: str) -> BaseEvaluator:
    """Find and instantiate the BaseEvaluator subclass from an evaluate module."""
    candidate_cls = getattr(evaluate_mod, expected_class_name, None)
    if inspect.isclass(candidate_cls) and issubclass(candidate_cls, BaseEvaluator):
        return candidate_cls()

    for _, obj in inspect.getmembers(evaluate_mod, inspect.isclass):
        if issubclass(obj, BaseEvaluator) and obj is not BaseEvaluator:
            return obj()

    raise ValueError(f"No BaseEvaluator subclass found in {evaluate_mod.__file__}")


def run_use_case(
    use_case: str,
    *,
    dry_run: bool = False,
    max_programs: int = 5,
    workers: int = 2,
    output_dir: str | Path | None = None,
    stream_to_dashboard: bool = False,
    skip_holdout: bool = False,
    examples_dir: str | Path | None = None,
) -> ProgramCandidate:
    """Execute an AlphaEvolve optimization run for the specified use case."""
    if max_programs < 1:
        raise ValueError(f"--max-programs must be >= 1, got {max_programs}.")
    if workers < 1:
        raise ValueError(f"--workers must be >= 1, got {workers}.")

    info = resolve_use_case(use_case, examples_dir=examples_dir)
    instructions_path = info.path / "instructions.md"
    seed_program_path = info.path / "src" / "program.py"

    if not instructions_path.is_file():
        raise FileNotFoundError(f"Missing instructions file: {instructions_path}")
    if not seed_program_path.is_file():
        raise FileNotFoundError(f"Missing seed program file: {seed_program_path}")

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    _load_use_case_submodule(info.path, "simulator")
    program_mod = _load_use_case_submodule(info.path, "program")
    evaluate_mod = _load_use_case_submodule(info.path, "evaluate")

    evaluator = _instantiate_evaluator(evaluate_mod, info.evaluator_class)
    broker = get_global_broker() if stream_to_dashboard else None
    resolved_output_dir = (
        Path(output_dir) if output_dir is not None else Path("artifacts") / info.name
    )

    experiment = AlphaEvolveExperiment.from_files(
        experiment_name=info.title,
        instructions_path=instructions_path,
        seed_program_path=seed_program_path,
        evaluator=evaluator,
        max_programs=max_programs,
        parallel_workers=workers,
        dry_run=dry_run,
        telemetry_broker=broker,
    )

    best_candidate = experiment.run(output_dir=resolved_output_dir)

    if not skip_holdout and (info.path / "src" / "report.py").is_file():
        report_mod = _load_use_case_submodule(info.path, "report")
        holdout_fn: Callable[..., Any] | None = getattr(
            report_mod, "evaluate_on_locked_holdout", None
        )
        baseline_fn: Callable[..., Any] | None = getattr(program_mod, info.target_function, None)
        if callable(holdout_fn) and callable(baseline_fn):
            best_policy_fn = compile_candidate_callable(
                best_candidate.code,
                info.target_function,
                filename="<best_candidate>",
            )
            holdout_fn(baseline_fn=baseline_fn, evolved_fn=best_policy_fn)

    return best_candidate


def scaffold_use_case(
    use_case: str,
    output_dir: str | Path | None = None,
    *,
    target_function: str = "solve_policy",
    primary_metric: str = "score",
    force: bool = False,
) -> Path:
    """Scaffold a new 3-tier AlphaEvolve Digital Twin use case directory.

    Parameters
    ----------
    use_case : str
        Name of the new use case (e.g. ``dynamic_pricing`` or ``energy-dispatch``).
    output_dir : str | Path | None
        Parent directory (default ``examples/``) or exact target directory where the
        use-case files will be generated.
    target_function : str
        Name of the candidate function inside ``src/program.py`` (default: ``solve_policy``).
    primary_metric : str
        Primary optimization metric name (default: ``score``).
    force : bool
        Overwrite files if the target directory already exists.

    Returns
    -------
    Path
        Resolved path to the newly created use-case directory.
    """
    slug = normalize_use_case_name(use_case)
    if not target_function.isidentifier() or keyword.iskeyword(target_function):
        raise ValueError(f"Invalid target function name: '{target_function}'.")
    if not primary_metric.isidentifier() or keyword.iskeyword(primary_metric):
        raise ValueError(f"Invalid primary metric name: '{primary_metric}'.")

    if output_dir is None:
        use_case_dir = DEFAULT_EXAMPLES_DIR / slug
    else:
        out_path = Path(output_dir)
        use_case_dir = out_path if out_path.name == slug else out_path / slug

    if use_case_dir.exists() and any(use_case_dir.iterdir()) and not force:
        raise FileExistsError(
            f"Target directory '{use_case_dir}' already exists and is non-empty. "
            "Pass --force to overwrite."
        )

    pascal_name = _to_pascal_case(slug)
    title_name = _to_title_case(slug)
    evaluator_class = f"{pascal_name}Evaluator"

    src_dir = use_case_dir / "src"
    tests_dir = use_case_dir / "tests"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    (use_case_dir / "__init__.py").write_text(
        f'"""{title_name} Digital Twin use case for AlphaEvolve."""\n',
        encoding="utf-8",
    )

    (use_case_dir / "README.md").write_text(
        _render_readme(slug, title_name, target_function, primary_metric, evaluator_class),
        encoding="utf-8",
    )

    (use_case_dir / "instructions.md").write_text(
        _render_instructions(slug, title_name, target_function, primary_metric),
        encoding="utf-8",
    )

    (use_case_dir / "run_evolution.py").write_text(
        _render_run_evolution(slug, title_name, target_function, evaluator_class),
        encoding="utf-8",
    )

    (src_dir / "__init__.py").write_text(
        f'"""Core simulator, seed program, and 3-tier evaluator for {title_name}."""\n',
        encoding="utf-8",
    )

    (src_dir / "program.py").write_text(
        _render_program(title_name, target_function),
        encoding="utf-8",
    )

    (src_dir / "simulator.py").write_text(
        _render_simulator(pascal_name, title_name),
        encoding="utf-8",
    )

    (src_dir / "evaluate.py").write_text(
        _render_evaluate(
            slug, pascal_name, title_name, target_function, primary_metric, evaluator_class
        ),
        encoding="utf-8",
    )

    (src_dir / "report.py").write_text(
        _render_report(pascal_name, title_name),
        encoding="utf-8",
    )

    (tests_dir / "__init__.py").write_text(
        f'"""Unit tests for the {title_name} use case."""\n',
        encoding="utf-8",
    )

    (tests_dir / f"test_{slug}.py").write_text(
        _render_tests(slug, pascal_name, target_function, primary_metric, evaluator_class),
        encoding="utf-8",
    )

    return use_case_dir.resolve()


def _render_readme(
    slug: str,
    title_name: str,
    target_function: str,
    primary_metric: str,
    evaluator_class: str,
) -> str:
    return f"""# {title_name} Digital Twin

End-to-end AlphaEvolve optimization use case for **{title_name}**.

## Overview

- **Target Policy Function**: `{target_function}(state, config)` in `src/program.py`
- **Evaluator Class**: `{evaluator_class}` in `src/evaluate.py`
- **Primary Fitness Metric**: `{primary_metric}`

## Quick Start

```bash
# Run offline dry-run evolution via unified CLI
uv run --frozen alpha-evolve run {slug} --dry-run --max-programs 5

# Run standalone evolution script
uv run --frozen python examples/{slug}/run_evolution.py --dry-run --max-programs 5

# Run domain unit tests
uv run --frozen pytest examples/{slug}/tests -v
```
"""


def _render_instructions(
    slug: str,
    title_name: str,
    target_function: str,
    primary_metric: str,
) -> str:
    return f"""# Domain Context: {title_name} Digital Twin

## 1. Problem Formulation

You are an algorithmic engineer optimizing the **{title_name}** (`{slug}`) digital twin.
Discover a policy `{target_function}(state, config)` that minimizes total operational cost
while maintaining high service reliability across all simulation steps.

Candidate policies are scored on `{primary_metric}` relative to the baseline heuristic.

---

## 2. System State & Parameter Interfaces

### `state` Dictionary (Current Step Snapshot)
- `step`: `int` (current simulation time step).
- `demands`: `list[float]` (resource demand across nodes at the current step).
- `capacities`: `list[float]` (available capacity across nodes).
- `backlog`: `list[float]` (unfulfilled backlog carried from prior steps).

### `config` Dictionary (Static Domain Parameters)
- `n_nodes`: `int` (number of operational nodes).
- `horizon`: `int` (number of steps in the rollout horizon).
- `unit_allocation_cost`: `float` (cost per unit allocated).
- `shortage_penalty`: `float` (penalty per unit of unfulfilled demand).
- `holding_cost`: `float` (cost per unit of excess allocation).

---

## 3. Physical Dynamics & Constraints

1. **Non-Negativity**: Allocations in `allocations` must be non-negative floats.
2. **Capacity Limits**: Allocations at each node are capped by available node capacity.
3. **Service Level Objective**: Maintain fulfillment rate >= 95.0% to avoid SLA penalties.
"""


def _render_program(title_name: str, target_function: str) -> str:
    return f'''"""Baseline seed policy for {title_name} with EVOLVE-BLOCK delimiters."""

from __future__ import annotations

from typing import Any


# EVOLVE-BLOCK-START
def {target_function}(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Compute resource allocations for each operational node at the current step.

    Parameters
    ----------
    state : dict[str, Any]
        Current snapshot with keys ``step``, ``demands``, ``capacities``, ``backlog``.
    config : dict[str, Any]
        Static parameters with keys ``n_nodes``, ``horizon``, ``unit_allocation_cost``,
        ``shortage_penalty``, ``holding_cost``.

    Returns
    -------
    dict[str, Any]
        Action dictionary containing ``"allocations"``: list of float quantities.
    """
    demands = [float(x) for x in state.get("demands", [])]
    capacities = [float(x) for x in state.get("capacities", [])]
    backlog = [float(x) for x in state.get("backlog", [0.0] * len(demands))]

    allocations: list[float] = []
    for idx, demand in enumerate(demands):
        cap = capacities[idx] if idx < len(capacities) else demand
        pending = backlog[idx] if idx < len(backlog) else 0.0
        target = (demand + pending) * 1.05
        allocations.append(max(0.0, min(cap, target)))

    return {{"allocations": allocations}}


# EVOLVE-BLOCK-END
'''


def _render_simulator(pascal_name: str, title_name: str) -> str:
    return f'''"""Deterministic digital twin simulator for {title_name}."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class {pascal_name}Config:
    """Configuration and deterministic demand trace for {title_name}."""

    n_nodes: int
    horizon: int
    demand_matrix: np.ndarray
    capacity_matrix: np.ndarray
    unit_allocation_cost: float = 2.5
    shortage_penalty: float = 18.0
    holding_cost: float = 1.2

    def to_dict(self) -> dict[str, Any]:
        """Convert static parameters to a plain dictionary for policy execution."""
        return {{
            "n_nodes": self.n_nodes,
            "horizon": self.horizon,
            "unit_allocation_cost": self.unit_allocation_cost,
            "shortage_penalty": self.shortage_penalty,
            "holding_cost": self.holding_cost,
        }}


@dataclass(frozen=True)
class SimulationSummary:
    """Aggregate operational metrics from a digital twin rollout."""

    total_cost: float
    allocation_cost: float
    shortage_cost: float
    holding_cost: float
    fulfillment_rate_pct: float


def generate_benchmark_dataset(
    n_nodes: int = 12,
    horizon: int = 30,
    seed: int = 42,
) -> {pascal_name}Config:
    """Generate a deterministic benchmark dataset for {title_name}."""
    rng = np.random.default_rng(seed)
    base_demand = rng.uniform(15.0, 45.0, size=(horizon, n_nodes))
    seasonal = 1.0 + 0.2 * np.sin(np.linspace(0.0, 2.0 * np.pi, horizon))[:, None]
    demand_matrix = np.round(base_demand * seasonal, 2)
    capacity_matrix = np.round(demand_matrix * rng.uniform(1.1, 1.4, size=(horizon, n_nodes)), 2)
    return {pascal_name}Config(
        n_nodes=n_nodes,
        horizon=horizon,
        demand_matrix=demand_matrix,
        capacity_matrix=capacity_matrix,
    )


class {pascal_name}DigitalTwin:
    """Step-by-step causal digital twin simulator for {title_name}."""

    def __init__(self, config: {pascal_name}Config) -> None:
        self.config = config
        self.backlog = np.zeros(config.n_nodes, dtype=float)

    def get_state(self, step: int) -> dict[str, Any]:
        """Return causal state snapshot at the given step."""
        return {{
            "step": int(step),
            "demands": self.config.demand_matrix[step].tolist(),
            "capacities": self.config.capacity_matrix[step].tolist(),
            "backlog": self.backlog.tolist(),
        }}

    def run_simulation(
        self,
        policy_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    ) -> SimulationSummary:
        """Run a full horizon rollout and compute aggregate cost and SLA metrics."""
        self.backlog = np.zeros(self.config.n_nodes, dtype=float)
        cfg_dict = self.config.to_dict()

        total_alloc_cost = 0.0
        total_shortage_cost = 0.0
        total_holding_cost = 0.0
        total_demand = 0.0
        total_fulfilled = 0.0

        for step in range(self.config.horizon):
            state = self.get_state(step)
            decision = policy_fn(state, cfg_dict)
            if not isinstance(decision, dict) or "allocations" not in decision:
                raise ValueError("Policy must return a dict containing an 'allocations' key.")

            raw_alloc = np.asarray(decision["allocations"], dtype=float)
            if raw_alloc.shape != (self.config.n_nodes,):
                raise ValueError(
                    f"Expected allocations of shape ({{self.config.n_nodes}},), got {{raw_alloc.shape}}."
                )
            if np.any(np.isnan(raw_alloc)) or np.any(np.isinf(raw_alloc)):
                raise ValueError("Allocations must not contain NaN or Inf values.")
            if np.any(raw_alloc < 0.0):
                raise ValueError("Allocations must be non-negative.")

            caps = self.config.capacity_matrix[step]
            effective_alloc = np.minimum(raw_alloc, caps)
            demands = self.config.demand_matrix[step]
            required = demands + self.backlog

            fulfilled = np.minimum(effective_alloc, required)
            shortage = np.maximum(0.0, required - effective_alloc)
            excess = np.maximum(0.0, effective_alloc - required)

            self.backlog = shortage * 0.5
            total_alloc_cost += float(np.sum(effective_alloc) * self.config.unit_allocation_cost)
            total_shortage_cost += float(np.sum(shortage) * self.config.shortage_penalty)
            total_holding_cost += float(np.sum(excess) * self.config.holding_cost)
            total_demand += float(np.sum(required))
            total_fulfilled += float(np.sum(fulfilled))

        total_cost = total_alloc_cost + total_shortage_cost + total_holding_cost
        fulfillment_rate_pct = (
            (total_fulfilled / total_demand) * 100.0 if total_demand > 0.0 else 100.0
        )

        return SimulationSummary(
            total_cost=round(total_cost, 2),
            allocation_cost=round(total_alloc_cost, 2),
            shortage_cost=round(total_shortage_cost, 2),
            holding_cost=round(total_holding_cost, 2),
            fulfillment_rate_pct=round(fulfillment_rate_pct, 2),
        )
'''


def _render_evaluate(
    slug: str,
    pascal_name: str,
    title_name: str,
    target_function: str,
    primary_metric: str,
    evaluator_class: str,
) -> str:
    return f'''"""3-Tier Evaluator subclassing BaseEvaluator for {title_name}."""

from __future__ import annotations

import time
from typing import Any

from alpha_evolve.evaluators import BaseEvaluator, EvaluationTier, TierResult

from .simulator import (
    {pascal_name}Config,
    {pascal_name}DigitalTwin,
    generate_benchmark_dataset,
)

_BASELINE_VALIDATION_COST = 35000.0


class {evaluator_class}(BaseEvaluator):
    """Tiered domain evaluator for {title_name} policies."""

    name: str = "{slug}_evaluator"
    primary_metric: str = "{primary_metric}"
    higher_is_better: bool = True
    target_function_name: str = "{target_function}"
    smoke_timeout_s: float = 2.0
    validation_timeout_s: float = 15.0

    def __init__(self) -> None:
        self._smoke_config: {pascal_name}Config | None = None
        self._val_config: {pascal_name}Config | None = None
        self._holdout_config: {pascal_name}Config | None = None
        self.setup()

    def setup(self) -> None:
        """Precompute deterministic benchmark datasets across all 3 evaluation tiers."""
        if self._smoke_config is None:
            self._smoke_config = generate_benchmark_dataset(n_nodes=4, horizon=5, seed=99)
        if self._val_config is None:
            self._val_config = generate_benchmark_dataset(n_nodes=12, horizon=30, seed=42)
        if self._holdout_config is None:
            self._holdout_config = generate_benchmark_dataset(n_nodes=20, horizon=45, seed=1337)

    def evaluate_smoke(self, candidate_callable: Any) -> TierResult:
        """Tier 1: Fast sanity check verifying output contract and basic rollout."""
        start_time = time.perf_counter()
        if self._smoke_config is None:
            self.setup()
        assert self._smoke_config is not None

        twin = {pascal_name}DigitalTwin(self._smoke_config)
        try:
            summary = twin.run_simulation(candidate_callable)
        except Exception as exc:
            return TierResult.failure(
                EvaluationTier.SMOKE,
                error_message=f"Smoke test failed: {{exc}}",
                issue="smoke_exception",
                execution_time_s=time.perf_counter() - start_time,
            )

        return TierResult.success(
            EvaluationTier.SMOKE,
            metrics={{"smoke_passed": 1.0, "smoke_cost": summary.total_cost}},
            insights={{"smoke_status": "ok"}},
            execution_time_s=time.perf_counter() - start_time,
        )

    def evaluate_validation(self, candidate_callable: Any) -> TierResult:
        """Tier 2: Full validation rollout computing primary fitness and diagnostics."""
        start_time = time.perf_counter()
        if self._val_config is None:
            self.setup()
        assert self._val_config is not None

        twin = {pascal_name}DigitalTwin(self._val_config)
        try:
            summary = twin.run_simulation(candidate_callable)
        except Exception as exc:
            return TierResult.failure(
                EvaluationTier.VALIDATION,
                error_message=f"Validation rollout failed: {{exc}}",
                issue="validation_exception",
                execution_time_s=time.perf_counter() - start_time,
            )

        cost_reduction_pct = (
            (_BASELINE_VALIDATION_COST - summary.total_cost) / _BASELINE_VALIDATION_COST
        ) * 100.0
        sla_deficit = max(0.0, 95.0 - summary.fulfillment_rate_pct)
        fitness = cost_reduction_pct - 2.0 * (sla_deficit**1.5)

        metrics = {{
            "{primary_metric}": round(float(fitness), 2),
            "cost_reduction_pct": round(float(cost_reduction_pct), 2),
            "total_cost": round(float(summary.total_cost), 2),
            "fulfillment_rate_pct": round(float(summary.fulfillment_rate_pct), 2),
        }}
        insights = {{
            "cost_summary": f"Total Cost: ${{summary.total_cost:,.2f}}",
            "service_level": f"Fulfillment Rate: {{summary.fulfillment_rate_pct:.1f}}%",
        }}

        return TierResult.success(
            EvaluationTier.VALIDATION,
            metrics=metrics,
            insights=insights,
            execution_time_s=time.perf_counter() - start_time,
        )

    def evaluate_holdout(self, candidate_callable: Any) -> TierResult:
        """Tier 3: Locked out-of-sample evaluation to verify generalization."""
        start_time = time.perf_counter()
        if self._holdout_config is None:
            self.setup()
        assert self._holdout_config is not None

        twin = {pascal_name}DigitalTwin(self._holdout_config)
        try:
            summary = twin.run_simulation(candidate_callable)
        except Exception as exc:
            return TierResult.failure(
                EvaluationTier.HOLDOUT,
                error_message=f"Holdout rollout failed: {{exc}}",
                issue="holdout_exception",
                execution_time_s=time.perf_counter() - start_time,
            )

        return TierResult.success(
            EvaluationTier.HOLDOUT,
            metrics={{
                "total_cost": round(float(summary.total_cost), 2),
                "fulfillment_rate_pct": round(float(summary.fulfillment_rate_pct), 2),
            }},
            insights={{
                "holdout_summary": (
                    f"Holdout Cost: ${{summary.total_cost:,.2f}} | "
                    f"Fulfillment: {{summary.fulfillment_rate_pct:.1f}}%"
                )
            }},
            execution_time_s=time.perf_counter() - start_time,
        )
'''


def _render_report(pascal_name: str, title_name: str) -> str:
    return f'''"""Holdout evaluation reporting for {title_name}."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.table import Table

from .simulator import (
    {pascal_name}Config,
    {pascal_name}DigitalTwin,
    generate_benchmark_dataset,
)

console = Console()


def evaluate_on_locked_holdout(
    baseline_fn: Callable[[dict[str, Any], dict[str, Any]], Any],
    evolved_fn: Callable[[dict[str, Any], dict[str, Any]], Any],
    holdout_config: {pascal_name}Config | None = None,
) -> dict[str, Any]:
    """Compare baseline and evolved policies on the locked out-of-sample holdout dataset."""
    if holdout_config is None:
        holdout_config = generate_benchmark_dataset(n_nodes=20, horizon=45, seed=1337)

    base_res = {pascal_name}DigitalTwin(holdout_config).run_simulation(baseline_fn)
    evolved_res = {pascal_name}DigitalTwin(holdout_config).run_simulation(evolved_fn)

    cost_diff_pct = (
        (base_res.total_cost - evolved_res.total_cost) / max(1.0, base_res.total_cost)
    ) * 100.0

    table = Table(title="Out-of-Sample Holdout Performance ({title_name})")
    table.add_column("Metric", style="bold")
    table.add_column("Baseline Policy", justify="right")
    table.add_column("Evolved Policy", justify="right", style="bold green")
    table.add_column("Delta", justify="right", style="cyan")

    table.add_row(
        "Total Operational Cost",
        f"${{base_res.total_cost:,.2f}}",
        f"${{evolved_res.total_cost:,.2f}}",
        f"{{cost_diff_pct:+.1f}}%",
    )
    table.add_row(
        "Fulfillment Rate",
        f"{{base_res.fulfillment_rate_pct:.1f}}%",
        f"{{evolved_res.fulfillment_rate_pct:.1f}}%",
        f"{{evolved_res.fulfillment_rate_pct - base_res.fulfillment_rate_pct:+.1f}}% pts",
    )
    console.print(table)

    return {{
        "baseline": base_res.__dict__,
        "evolved": evolved_res.__dict__,
        "cost_reduction_pct": round(cost_diff_pct, 2),
    }}
'''


def _render_run_evolution(
    slug: str,
    title_name: str,
    target_function: str,
    evaluator_class: str,
) -> str:
    return f'''#!/usr/bin/env python3
"""Run end-to-end AlphaEvolve optimization for {title_name}."""
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_DIR.parent.parent
for candidate_path in (REPO_ROOT, REPO_ROOT / "src", EXAMPLE_DIR.parent):
    if candidate_path.is_dir() and str(candidate_path) not in sys.path:
        sys.path.insert(0, str(candidate_path))

from alpha_evolve.dashboard.telemetry_broker import get_global_broker
from alpha_evolve.experiment import AlphaEvolveExperiment
from alpha_evolve.utils import compile_candidate_callable
from {slug}.src.evaluate import {evaluator_class}
from {slug}.src.program import {target_function}
from {slug}.src.report import evaluate_on_locked_holdout


def main() -> None:
    parser = argparse.ArgumentParser(description="AlphaEvolve {title_name} Optimization")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run in offline mock mode without connecting to Google Cloud.",
    )
    parser.add_argument(
        "--max-programs",
        type=int,
        default=5,
        help="Total number of programs to generate and evaluate.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of parallel evaluation workers.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/{slug}",
        help="Directory to save best candidate code and evaluation reports.",
    )
    parser.add_argument(
        "--stream-to-dashboard",
        action="store_true",
        default=False,
        help="Broadcast candidate evaluations in real-time to the executive dashboard.",
    )
    args = parser.parse_args()

    evaluator = {evaluator_class}()
    broker = get_global_broker() if args.stream_to_dashboard else None

    experiment = AlphaEvolveExperiment.from_files(
        experiment_name="{title_name} Digital Twin",
        instructions_path=EXAMPLE_DIR / "instructions.md",
        seed_program_path=EXAMPLE_DIR / "src" / "program.py",
        evaluator=evaluator,
        max_programs=args.max_programs,
        parallel_workers=args.workers,
        dry_run=args.dry_run,
        telemetry_broker=broker,
    )

    best_candidate = experiment.run(output_dir=args.output_dir)
    best_policy_fn = compile_candidate_callable(
        best_candidate.code,
        "{target_function}",
        filename="<best_candidate>",
    )
    evaluate_on_locked_holdout(
        baseline_fn={target_function},
        evolved_fn=best_policy_fn,
    )


if __name__ == "__main__":
    main()
'''


def _render_tests(
    slug: str,
    pascal_name: str,
    target_function: str,
    primary_metric: str,
    evaluator_class: str,
) -> str:
    return f'''"""Unit tests for the {slug} AlphaEvolve digital twin use case."""
# ruff: noqa: E402, I001

from __future__ import annotations

import sys
from pathlib import Path

USE_CASE_DIR = Path(__file__).resolve().parent.parent
if str(USE_CASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(USE_CASE_DIR.parent))

from alpha_evolve.utils import extract_evolve_blocks
from {slug}.src.evaluate import {evaluator_class}
from {slug}.src.program import {target_function}
from {slug}.src.report import evaluate_on_locked_holdout
from {slug}.src.simulator import (
    {pascal_name}DigitalTwin,
    generate_benchmark_dataset,
)


def test_seed_program_contains_evolve_block() -> None:
    """Verify seed program contains valid EVOLVE-BLOCK delimiters."""
    source = (USE_CASE_DIR / "src" / "program.py").read_text(encoding="utf-8")
    blocks = extract_evolve_blocks(source)
    assert len(blocks) == 1
    assert "def {target_function}" in blocks[0]


def test_simulator_and_evaluator_tiers() -> None:
    """Verify simulator determinism and 3-tier evaluator execution on baseline policy."""
    cfg = generate_benchmark_dataset(n_nodes=6, horizon=10, seed=42)
    summary = {pascal_name}DigitalTwin(cfg).run_simulation({target_function})
    assert summary.total_cost > 0.0
    assert 0.0 <= summary.fulfillment_rate_pct <= 100.0

    evaluator = {evaluator_class}()
    smoke = evaluator.evaluate_smoke({target_function})
    assert smoke.passed is True

    result = evaluator.evaluate({target_function})
    assert result.status == "SUCCESS"
    assert "{primary_metric}" in result.scores.to_dict()

    holdout = evaluator.evaluate_holdout({target_function})
    assert holdout.passed is True

    report = evaluate_on_locked_holdout({target_function}, {target_function})
    assert report["cost_reduction_pct"] == 0.0
'''


def _cmd_list(args: argparse.Namespace, stdout_console: Console) -> int:
    """Handle `alpha-evolve list`."""
    use_cases = discover_use_cases(args.examples_dir)
    if args.json:
        print(json.dumps([u.to_dict() for u in use_cases], indent=2))
        return 0

    if not use_cases:
        stdout_console.print("[yellow]No AlphaEvolve use cases found.[/yellow]")
        return 0

    table = Table(title="Available AlphaEvolve Digital Twin Use Cases", expand=False)
    table.add_column("Use Case", style="bold cyan", no_wrap=True)
    table.add_column("Target Function", style="green", no_wrap=True)
    table.add_column("Primary Metric", style="magenta", no_wrap=True)
    table.add_column("Evaluator", style="yellow", no_wrap=True)
    table.add_column("Description")

    for uc in use_cases:
        table.add_row(
            uc.name,
            uc.target_function,
            uc.primary_metric,
            uc.evaluator_class,
            uc.description,
        )

    stdout_console.print(table)
    return 0


def _cmd_run(args: argparse.Namespace, stderr_console: Console) -> int:
    """Handle `alpha-evolve run <use_case>`."""
    try:
        run_use_case(
            args.use_case,
            dry_run=args.dry_run,
            max_programs=args.max_programs,
            workers=args.workers,
            output_dir=args.output_dir,
            stream_to_dashboard=args.stream_to_dashboard,
            skip_holdout=args.skip_holdout,
            examples_dir=args.examples_dir,
        )
    except (ValueError, FileNotFoundError) as exc:
        stderr_console.print(f"[bold red]Error:[/bold red] {exc}")
        return 2
    return 0


def _cmd_init(
    args: argparse.Namespace,
    stdout_console: Console,
    stderr_console: Console,
) -> int:
    """Handle `alpha-evolve init <new_use_case>`."""
    try:
        created_dir = scaffold_use_case(
            args.new_use_case,
            output_dir=args.output_dir,
            target_function=args.target_function,
            primary_metric=args.primary_metric,
            force=args.force,
        )
    except (ValueError, FileExistsError) as exc:
        stderr_console.print(f"[bold red]Error:[/bold red] {exc}")
        return 2

    slug = created_dir.name
    stdout_console.print(
        f"[bold green]✅ Scaffolded AlphaEvolve use case '{slug}' at:[/bold green] {created_dir}"
    )
    stdout_console.print(
        f"   Next step: [cyan]uv run alpha-evolve run {created_dir} --dry-run --max-programs 5[/cyan]"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the `alpha-evolve` CLI."""
    parser = argparse.ArgumentParser(
        prog="alpha-evolve",
        description="Unified CLI and use-case scaffolder for AlphaEvolve digital twins.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. alpha-evolve list
    list_parser = subparsers.add_parser(
        "list",
        help="List all registered and discovered AlphaEvolve digital twin use cases.",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output discovered use cases as formatted JSON.",
    )
    list_parser.add_argument(
        "--examples-dir",
        type=Path,
        default=None,
        help="Override path to the examples directory.",
    )

    # 2. alpha-evolve run <use_case>
    run_parser = subparsers.add_parser(
        "run",
        help="Run an AlphaEvolve optimization experiment for a target use case.",
    )
    run_parser.add_argument(
        "use_case",
        type=str,
        help="Use case name (e.g. inventory_replenishment, fleet_routing) or directory path.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run in offline mock mode without connecting to Google Cloud.",
    )
    run_parser.add_argument(
        "--max-programs",
        type=int,
        default=5,
        help="Total number of candidate programs to generate and evaluate (default: 5).",
    )
    run_parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of parallel evaluation workers (default: 2).",
    )
    run_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to export best candidate code and evaluation summary.",
    )
    run_parser.add_argument(
        "--stream-to-dashboard",
        action="store_true",
        default=False,
        help="Broadcast candidate evaluations in real-time to the executive dashboard.",
    )
    run_parser.add_argument(
        "--skip-holdout",
        action="store_true",
        default=False,
        help="Skip out-of-sample locked holdout evaluation after evolution completes.",
    )
    run_parser.add_argument(
        "--examples-dir",
        type=Path,
        default=None,
        help="Override path to the examples directory when resolving use case by name.",
    )

    # 3. alpha-evolve init <new_use_case>
    init_parser = subparsers.add_parser(
        "init",
        help="Scaffold a new 3-tier AlphaEvolve digital twin use case.",
    )
    init_parser.add_argument(
        "new_use_case",
        type=str,
        help="Identifier for the new use case (e.g. dynamic_pricing, cold_chain).",
    )
    init_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Parent directory or target path for the scaffolded use case (default: examples/).",
    )
    init_parser.add_argument(
        "--target-function",
        type=str,
        default="solve_policy",
        help="Name of the target policy function inside src/program.py (default: solve_policy).",
    )
    init_parser.add_argument(
        "--primary-metric",
        type=str,
        default="score",
        help="Primary optimization metric name (default: score).",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing files if the target use-case directory already exists.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for `alpha-evolve`."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    stdout_console = Console(width=140)
    stderr_console = Console(stderr=True, width=140)

    if args.command == "list":
        return _cmd_list(args, stdout_console)
    if args.command == "run":
        return _cmd_run(args, stderr_console)
    if args.command == "init":
        return _cmd_init(args, stdout_console, stderr_console)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
