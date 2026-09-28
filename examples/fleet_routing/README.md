# Dynamic Fleet Routing & Dispatch with Time Windows (VRPTW)

[![Evaluation Paradigm: Simulation](https://img.shields.io/badge/paradigm-Simulation-purple.svg)](#)
[![Vertical: Logistics & Transportation](https://img.shields.io/badge/vertical-Logistics%20%2F%20Transportation-blue.svg)](#)
[![Reference: Last-Mile Delivery](https://img.shields.io/badge/reference-Urban%20Fleet%20Dispatch-teal.svg)](#)

This example demonstrates how to use **AlphaEvolve with Gemini Enterprise** to synthesize adaptive vehicle routing and dynamic dispatch policies within an urban last-mile delivery digital twin.

---

## 1. Executive Summary & Customer Problem

Last-mile urban delivery fleets operate under high uncertainty and tight customer commitments:
- **Challenge**: Vehicles must fulfill customer delivery orders across spatial clusters while respecting narrow customer delivery time windows $[e_i, l_i]$, vehicle payload capacity limits, dynamic order arrivals throughout the shift, and time-varying traffic congestion during morning and evening rush hours.
- **Why Exact Solvers Fail**: Mixed Integer Linear Programming (MILP) and standard branch-and-cut solvers take hours on 100-stop instances and cannot react in real time when new dynamic orders arrive mid-shift or when traffic spikes.
- **Classical Heuristics Fail**: Greedy nearest-neighbor heuristics suffer from route crisscrossing, miss urgent time windows late in the shift, and fail to anticipate rush hour travel bottlenecks, resulting in severe late penalties ($45/hr) and idle driver wait costs.

---

## 2. The Solution: AlphaEvolve Policy Synthesis

AlphaEvolve evolves the constructive dispatch policy inside [`src/program.py`](src/program.py):

```python
# EVOLVE-BLOCK-START
def assign_and_sequence_routes(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]: ...


# EVOLVE-BLOCK-END
```

### The 3-Tier Evaluation Harness ([`src/evaluate.py`](src/evaluate.py))

1. **Tier 1 (Fast Smoke Check, <0.1s)**: Verifies valid dictionary route returns and non-crashing execution on 15 customers and 2 vehicles.
2. **Tier 2 (Validation Rollout, ~0.6s)**: Executes a 12-hour operational shift simulation with dynamic traffic across 50 customers and 5 vehicles, evaluating cost reduction, SLA penalties, and unserved penalties:
   $$\text{score} = \text{cost\_reduction\_pct} - 1.5 \times \max(0, 95.0 - \text{On-Time \%})^{1.5} - 50.0 \times \left(\frac{\text{Unserved Orders}}{N_{\text{customers}}}\right)$$
   Alongside numerical fitness, the evaluator provides structured **Insights** on SLA tardiness warnings, traffic bottlenecks, and capacity utilization.
3. **Locked Holdout Test (100 Customers / Dynamic Traffic)**: Evaluated out-of-sample in [`src/report.py`](src/report.py) to prove generalizability.

---

## 3. How to Run

### Option A: Local Offline Dry-Run (No Cloud Setup Required)

Run the evolutionary pipeline locally using synthetic candidate mutations:

```bash
uv run python examples/fleet_routing/run_evolution.py --dry-run --max-programs 5
```

### Option B: Cloud Optimization with Gemini Enterprise

Ensure your `.env` contains your Google Cloud credentials, then run:

```bash
uv run python examples/fleet_routing/run_evolution.py --max-programs 30 --workers 4
```

### Option C: Live Streaming to Executive Dashboard

Broadcast candidate evaluations live to the dashboard:

```bash
uv run python examples/fleet_routing/run_evolution.py --dry-run --max-programs 10 --stream-to-dashboard
```
