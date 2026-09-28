# True Process/Subprocess Sandboxing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement true process/subprocess sandboxing for candidate execution with hard unblockable timeouts, memory limits (`resource.setrlimit`), crash/segfault detection, and zero zombie CPU loops.

**Architecture:** Refactor `src/alpha_evolve/workers.py` to replace unsafe `ThreadPoolExecutor` with a modular sandboxing subsystem (`ProcessSandbox`, `SubprocessSandbox`, and `ThreadSandbox` fallback) orchestrated by `WorkerPool`. Child processes run in isolated memory spaces, apply POSIX memory limits, trap fatal crashes/signals, and are terminated with unblockable `kill()` on timeout.

**Tech Stack:** Python 3.12+, `multiprocessing.get_context("spawn")`, `subprocess`, `resource` (POSIX rlimits), Pydantic v2, pytest.

---

### Task 1: Update RunSettings Model with Sandboxing Parameters
- **Files**:
  - Modify: `src/alpha_evolve/models.py:133-152`
  - Modify: `tests/test_models.py`
- **Step 1: Write failing test** for new fields `max_memory_mb` and `sandbox_mode` in `RunSettings`.
- **Step 2: Run test** to verify failure.
- **Step 3: Update `RunSettings`** in `src/alpha_evolve/models.py`.
- **Step 4: Run test** to verify pass.
- **Step 5: Commit**: `feat(models): add max_memory_mb and sandbox_mode to RunSettings`.

---

### Task 2: Implement Sandbox Subsystem in `src/alpha_evolve/workers.py`
- **Files**:
  - Modify: `src/alpha_evolve/workers.py`
  - Create: `tests/test_workers_sandboxing.py`
- **Step 1: Write tests** for `ProcessSandbox` (normal execution, timeout termination of infinite CPU loops, memory limit enforcement, hard crash `os._exit()` isolation).
- **Step 2: Run test** to verify failure.
- **Step 3: Implement `ProcessSandbox`**, `SandboxConfig`, and entrypoint function in `src/alpha_evolve/workers.py`.
- **Step 4: Run test** to verify pass.
- **Step 5: Commit**: `feat(workers): implement ProcessSandbox with unblockable timeout and crash isolation`.

---

### Task 3: Integrate Sandbox Configuration with WorkerPool & EvolutionController
- **Files**:
  - Modify: `src/alpha_evolve/workers.py`
  - Modify: `src/alpha_evolve/controller.py`
  - Modify: `tests/test_controller_evaluator.py`
- **Step 1: Write test** verifying controller passes `sandbox_mode` and `max_memory_mb` to worker pool.
- **Step 2: Update `WorkerPool.__init__`** and `EvolutionController.__init__` to wire `RunSettings`.
- **Step 3: Run tests** to verify all pass.
- **Step 4: Commit**: `feat(controller): wire sandbox configuration from RunSettings into WorkerPool`.

---

### Task 4: Subprocess Runner Support & Fallback Resilience
- **Files**:
  - Modify: `src/alpha_evolve/workers.py`
  - Modify: `tests/test_workers_sandboxing.py`
- **Step 1: Write tests** for unpicklable closures (fallback to thread mode with warning) and subprocess execution mode.
- **Step 2: Implement fallback logic** and CLI runner module entrypoint.
- **Step 3: Run tests** to verify 100% pass across all existing and new test suites.
- **Step 4: Commit**: `feat(workers): add unpicklable closure fallback and subprocess runner`.

---

### Task 5: Documentation & Session Notes
- **Files**:
  - Create: `docs/notes/candidate_sandboxing.md`
  - Modify: `docs/notes/README.md`
  - Modify: `docs/USER_GUIDE.md`
- **Step 1: Write `docs/notes/candidate_sandboxing.md`** explaining isolation guarantees, resource limits, signals, and security model.
- **Step 2: Update `docs/notes/README.md`** and `docs/USER_GUIDE.md`.
- **Step 3: Format and verify documentation**.
- **Step 4: Commit**: `docs: document process sandboxing and security model`.

---

### Task 6: Full Verification, Make Check, and Pull Request
- **Files**: All repository files
- **Step 1: Run `make check`** (all 38+ tests pass, linters clean, types clean).
- **Step 2: Run dry-run E2E validation**: `uv run python examples/inventory_replenishment/run_evolution.py --dry-run --max-programs 2`.
- **Step 3: Push branch and create PR** via `gh pr create`.
- **Step 4: Watch CI checks** until 100% green.
