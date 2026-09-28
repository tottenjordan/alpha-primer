# Dynamic Fleet Routing & Dispatch Digital Twin (VRPTW)

## 1. Overview & Business Value

The **Dynamic Fleet Routing & Dispatch with Time Windows (VRPTW)** use case (`examples/fleet_routing/`) provides an end-to-end AlphaEvolve optimization template for urban last-mile delivery fleets:
- **Objective**: Minimize total fleet operating costs (fuel, vehicle wages, late penalties, idle wait, and unserved order penalties) across an urban distribution network.
- **Physical Dynamics**:
  - **Dynamic Traffic Congestion**: Travel time varies throughout the day, spiking during morning rush hours ($t \in [1.0, 3.0]$) and evening rush hours ($t \in [8.0, 10.5]$).
  - **Causal Isolation**: The dispatch policy only observes orders placed by `current_time`. Future dynamic orders are strictly unobservable until they arrive.
  - **Hard Constraints**: Customer delivery time windows $[e_i, l_i]$ and vehicle payload capacities $Q_{\text{max}}$.
- **Baseline Heuristic**: Greedy nearest-neighbor stop sequence sorted by window start time.
- **Evolved Champion Innovations**:
  - Time-window slack urgency ordering.
  - Dynamic traffic congestion avoidance (scheduling perimeter trips during traffic troughs).
  - Adaptive regret-2 dynamic order insertion.
  - Local 2-opt path uncrossing.

---

## 2. Architecture & File Layout

```
examples/fleet_routing/
├── README.md               # Executive summary, customer problem, and execution instructions
├── instructions.md         # Domain prompt formulation and state/config interfaces for Gemini
├── run_evolution.py        # CLI entrypoint supporting --dry-run and --stream-to-dashboard
├── src/
│   ├── __init__.py
│   ├── program.py          # Baseline greedy algorithm bounded by # EVOLVE-BLOCK
│   ├── simulator.py        # Spatial digital twin with dynamic traffic & causal order isolation
│   ├── evaluate.py         # VehicleRoutingEvaluator subclassing BaseEvaluator
│   └── report.py           # Post-evolution holdout analytics and Rich tabular reporting
└── tests/
    ├── __init__.py
    ├── test_simulator.py   # Deterministic dataset generation and causal isolation tests
    ├── test_program.py     # Baseline policy validity tests
    └── test_evaluator.py   # Multi-tier evaluation and holdout tests
```

---

## 3. Evaluation Harness

The use case implements a 3-tier evaluator subclassing `BaseEvaluator`:
- **Tier 1 (Smoke Sanity Check, <0.1s)**: 15 customers, 2 vehicles. Validates route return structure and basic execution.
- **Tier 2 (Validation Rollout, ~0.6s)**: 50 customers, 5 vehicles. Simulates a 12-hour shift with dynamic rush hour congestion, computing cost reduction, SLA penalties, and diagnostic insights.
- **Tier 3 (Locked Holdout, ~1.2s)**: 100 customers, 10 vehicles. Simulates out-of-sample stress conditions to verify that discovered routing heuristics generalize without overfitting.
