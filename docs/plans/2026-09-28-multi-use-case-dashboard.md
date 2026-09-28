# Multi-Use-Case Switcher for Executive Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable seamless switching between multiple domain use cases (`inventory_replenishment` and `fleet_routing`) in the executive web dashboard with dynamic KPI cards, Pareto curves, trajectory charts, and code diff milestones.

**Architecture:** Update `records/master_trajectories.json` to bundle both `inventory_replenishment` and `fleet_routing` use-case payloads. Enhance `src/alpha_evolve/dashboard/build_dashboard.py` to add a header use-case switcher with Safe DOM event handlers, dynamic KPI label/value rebinding, use-case-specific Pareto/trajectory charts, milestone ribbons, and code diff steppers while preserving 100% Safe DOM compliance (zero `innerHTML`).

**Tech Stack:** Python 3.12, Vanilla HTML5 / Retina Canvas 2D / CSS3, Safe DOM (`document.createElement`, `textContent`, `replaceChildren`), Pytest, Ruff.

---

### Task 1: Master Bundle Multi-Use-Case Aggregation

**Files:**
- Modify: `src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py`
- Modify: `src/alpha_evolve/dashboard/trajectory_generator.py`
- Test: `tests/test_dashboard_builder.py`

**Step 1: Write the failing test**
In `tests/test_dashboard_builder.py`:
```python
def test_master_trajectories_contains_all_use_cases(tmp_path: Path) -> None:
    """Verify master_trajectories.json bundles both inventory_replenishment and fleet_routing."""
    from alpha_evolve.dashboard.trajectory_generator import generate_inventory_trajectory_dataset
    from alpha_evolve.dashboard.fleet_routing_trajectory_generator import (
        generate_fleet_routing_trajectory_dataset,
    )

    # Generate both into tmp_path
    inv_bundle = generate_inventory_trajectory_dataset(output_dir=tmp_path)
    fleet_data = generate_fleet_routing_trajectory_dataset(output_dir=tmp_path)

    # Master bundle must contain both use cases
    master_path = tmp_path / "master_trajectories.json"
    assert master_path.exists()
    master = json.loads(master_path.read_text(encoding="utf-8"))
    assert "use_cases" in master
    assert "inventory_replenishment" in master["use_cases"]
    assert "fleet_routing" in master["use_cases"]
```

**Step 2: Run test to verify it fails**
Run: `uv run --frozen pytest tests/test_dashboard_builder.py::test_master_trajectories_contains_all_use_cases -v`
Expected: FAIL with `AssertionError: assert 'fleet_routing' in master['use_cases']`

**Step 3: Write minimal implementation**
1. In `src/alpha_evolve/dashboard/trajectory_generator.py`:
   - If `records/fleet_routing_trajectory.json` exists, load and include it in `master_bundle["use_cases"]["fleet_routing"]`.
2. In `src/alpha_evolve/dashboard/fleet_routing_trajectory_generator.py`:
   - When writing `fleet_routing_trajectory.json`, also update `master_trajectories.json` so that `master_bundle["use_cases"]["fleet_routing"] = use_case_data`.
3. Re-run generators to update `records/master_trajectories.json`.

**Step 4: Run test to verify it passes**
Run: `uv run --frozen pytest tests/test_dashboard_builder.py::test_master_trajectories_contains_all_use_cases -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/alpha_evolve/dashboard/ records/master_trajectories.json tests/test_dashboard_builder.py
git commit -m "feat(dashboard): bundle inventory and fleet routing in master_trajectories.json"
```

---

### Task 2: Multi-Use-Case Switcher Header Markup & Safe DOM Styling

**Files:**
- Modify: `src/alpha_evolve/dashboard/build_dashboard.py:100-300` and `1100-1150`
- Test: `tests/test_dashboard_builder.py`

**Step 1: Write the failing test**
In `tests/test_dashboard_builder.py`:
```python
def test_dashboard_multi_use_case_switcher_elements(tmp_path: Path) -> None:
    """Verify index.html contains use-case switcher pills and dropdown elements."""
    html_path = build_dashboard_html(output_dir=tmp_path)
    content = html_path.read_text(encoding="utf-8")

    assert 'id="use-case-switcher"' in content
    assert 'data-use-case="inventory_replenishment"' in content
    assert 'data-use-case="fleet_routing"' in content
    assert 'id="active-use-case-title"' in content
```

**Step 2: Run test to verify it fails**
Run: `uv run --frozen pytest tests/test_dashboard_builder.py::test_dashboard_multi_use_case_switcher_elements -v`
Expected: FAIL with missing element IDs.

**Step 3: Write minimal implementation**
In `src/alpha_evolve/dashboard/build_dashboard.py`:
- Add CSS for `.use-case-switcher`, `.use-case-btn`, `.use-case-btn.active`.
- In `<header>`, add a dedicated use-case navigation pill container next to the platform title or in top meta:
```html
<div class="use-case-selector-bar">
  <span class="use-case-label">DOMAIN DIGITAL TWIN:</span>
  <div class="use-case-switcher" id="use-case-switcher">
    <button class="use-case-btn active" data-use-case="inventory_replenishment">
      📦 Retail &amp; Perishable Inventory
    </button>
    <button class="use-case-btn" data-use-case="fleet_routing">
      🚚 Dynamic Fleet Routing (VRPTW)
    </button>
  </div>
</div>
```

**Step 4: Run test to verify it passes**
Run: `uv run --frozen pytest tests/test_dashboard_builder.py::test_dashboard_multi_use_case_switcher_elements -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/alpha_evolve/dashboard/build_dashboard.py tests/test_dashboard_builder.py
git commit -m "feat(dashboard): add use-case switcher header markup and styling"
```

---

### Task 3: Client-Side Dynamic Use-Case Switching Engine (Safe DOM)

**Files:**
- Modify: `src/alpha_evolve/dashboard/build_dashboard.py:1480-2800`
- Test: `tests/test_dashboard_builder.py`

**Step 1: Write the failing test**
In `tests/test_dashboard_builder.py`:
```python
def test_dashboard_client_use_case_switching_logic(tmp_path: Path) -> None:
    """Verify JavaScript includes switchUseCase function and Safe DOM re-binding."""
    html_path = build_dashboard_html(output_dir=tmp_path)
    content = html_path.read_text(encoding="utf-8")

    assert "switchUseCase" in content
    assert "currentUseCaseId" in content
    assert "innerHTML" not in content  # Strict enterprise rule
```

**Step 2: Run test to verify it fails**
Run: `uv run --frozen pytest tests/test_dashboard_builder.py::test_dashboard_client_use_case_switching_logic -v`
Expected: FAIL with missing `switchUseCase`.

**Step 3: Write minimal implementation**
In `src/alpha_evolve/dashboard/build_dashboard.py` JavaScript:
1. Define `currentUseCaseId = "inventory_replenishment"`.
2. Encapsulate use-case data references into a dynamic `getUseCaseData(id)` helper:
   - Trajectories, milestones, ribbonMilestones, paretoFrontier, championSummary, baselineSummary.
3. Implement `switchUseCase(useCaseId)`:
   - Update active class on `.use-case-btn`.
   - Update header subtitle and horizon pill ("90 Days (Causal)" for inventory, "12 Hours (Traffic)" for fleet).
   - Re-label KPI cards:
     - Card 1: "Total Supply Chain Cost" (inventory) vs "Total Fleet Cost" (fleet).
     - Card 2: "Perishable Spoilage Waste" (inventory) vs "Fleet Distance Traveled" (fleet).
     - Card 3: "Service Fill Rate" (inventory) vs "On-Time Delivery Rate" (fleet).
     - Card 4: "Optimization Score" (inventory: cost reduction % vs fleet: composite score).
   - Reset scrubber range to use case `maxGen`.
   - Re-render Milestone Ribbon nodes.
   - Re-populate Code Diff Stepper options with the active use case's milestone ASTs.
   - Re-draw Retina Canvas 2D (Pareto Frontier & Trajectory curves).
   - Re-render What-If sandbox or show domain-specific sandbox banner.
4. Bind click events on `.use-case-btn` buttons to `switchUseCase(id)`.

**Step 4: Run test to verify it passes**
Run: `uv run --frozen pytest tests/test_dashboard_builder.py::test_dashboard_client_use_case_switching_logic -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/alpha_evolve/dashboard/build_dashboard.py tests/test_dashboard_builder.py
git commit -m "feat(dashboard): implement dynamic client-side use-case switching engine"
```

---

### Task 4: Recompile Dashboard Artifacts & Verify Node.js Evaluation

**Files:**
- Modify: `dashboard/index.html`
- Modify: `dashboard/data.json`
- Test: `tests/test_dashboard_builder.py`

**Step 1: Write the failing test**
Run: `uv run --frozen pytest tests/test_dashboard_builder.py::test_diff_engine_robustness_and_client_js_execution -v`
(Verifies client-side JS syntax without errors via Node.js execution).

**Step 2: Run test to verify it passes / compile dashboard**
Run: `uv run --frozen python -c "from alpha_evolve.dashboard.build_dashboard import build_dashboard_html; build_dashboard_html()"`
Run: `uv run --frozen pytest tests/test_dashboard_builder.py -v`
Expected: ALL PASS

**Step 3: Commit**
```bash
git add dashboard/index.html dashboard/data.json
git commit -m "build(dashboard): recompile index.html and data.json with multi-use-case support"
```

---

### Task 5: End-to-End Verification & Documentation

**Files:**
- Modify: `docs/notes/interactive_dashboard.md`
- Modify: `docs/USER_GUIDE.md`
- Test: `make check`

**Step 1: Update documentation**
Document the multi-use-case switcher in `docs/notes/interactive_dashboard.md` and `docs/USER_GUIDE.md`.

**Step 2: Run make check**
Run: `make check`
Expected: 100% green across linters (`ruff`), type checker (`ty check src/`), and all unit tests (`pytest`).

**Step 3: Commit**
```bash
git add docs/
git commit -m "docs(dashboard): document multi-use-case switcher in USER_GUIDE and dashboard notes"
```

---

### Task 6: Push Branch, Open PR, and Deploy to Cloud Run

**Files:**
- GitHub PR: `feat/multi-use-case-dashboard` -> `main`

**Step 1: Push branch**
```bash
git push -u origin feat/multi-use-case-dashboard
```

**Step 2: Open PR**
```bash
gh pr create --title "feat(dashboard): add interactive multi-use-case switcher for inventory and fleet routing" --body "..."
```

**Step 3: Await approval, merge to main, and deploy Cloud Run**
```bash
./scripts/deploy_cloud_run.sh
```
