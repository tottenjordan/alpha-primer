# Topic Note: AlphaEvolve Architecture & Environment Nuances

This document captures hard-won, non-obvious engineering insights and operational behaviors discovered while architecting this repository.

---

## 1. Standalone Example Execution & Module Paths

- **Issue**: When users clone the repo and execute `python examples/<use_case>/run_evolution.py`, Python sets `sys.path[0]` to the example subdirectory rather than the repository root. This prevents importing `examples.<use_case>.*`.
- **Solution**:
  - In each `run_evolution.py`, dynamically ensure `REPO_ROOT` is inserted into `sys.path`:
    ```python
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    ```
  - Configure `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml` with `"examples/**/run_evolution.py" = ["E402"]` so `ruff check` does not error on imports occurring after the path setup.

---

## 2. Process-Safe Evaluation Timeouts

- **Issue**: Standard UNIX `signal.alarm(seconds)` raises `ValueError: signal only works in main thread of the main interpreter` when candidate evaluation is offloaded to worker threads or subprocesses.
- **Solution**: Use `concurrent.futures.ThreadPoolExecutor` (or `ProcessPoolExecutor`) with `future.result(timeout=timeout_s)` to enforce strict wall-clock evaluation bounds without signals.

---

## 3. Causal Isolation & Multi-Period Time Indexing

- **Issue**: In time series simulations spanning $T$ days (e.g. `total_days=90`), days are 0-indexed as `[0, 89]`.
- **Validation Windows**:
  - Days `0..29`: Historical warm-up (burn-in period).
  - Days `30..65`: Active evaluation window scored during evolution.
  - Days `66..89`: Locked holdout test set evaluated strictly out-of-sample after evolution completes.
  - Attempting to evaluate index `90` results in an `IndexError`.

---

## 4. Offline Mock Simulation for Rapid Iteration

- **Benefit**: Real cloud evolution burns API quota and requires network connectivity.
- **Pattern**: `MockAlphaEvolveClient` simulates LLM mutations by perturbing constants and logic within the `# EVOLVE-BLOCK`, enabling developers to run tests and dry-run benchmarks in under 1 second without Google Cloud credentials.
