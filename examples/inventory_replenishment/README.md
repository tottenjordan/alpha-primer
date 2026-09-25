# Multi-Echelon & Perishable Inventory Replenishment Digital Twin

[![Evaluation Paradigm: Simulation](https://img.shields.io/badge/paradigm-Simulation-purple.svg)](#)
[![Vertical: Grocery & Ag](https://img.shields.io/badge/vertical-Retail%20%2F%20Grocery%20%2F%20Ag-green.svg)](#)
[![Reference: BASF](https://img.shields.io/badge/reference-BASF%20Agricultural-blue.svg)](#)

This example demonstrates how to use **AlphaEvolve with Gemini Enterprise** to synthesize adaptive replenishment policies within a stateful, causal supply chain digital twin.

---

## 1. Executive Summary & Customer Proof Point

This use case directly mirrors the **BASF Agricultural Solutions** AlphaEvolve reference engagement:
- **Challenge**: Perishable inventories suffer from dual risks: over-ordering causes catastrophic FIFO spoilage waste, while under-ordering causes censored stockouts, lost sales, and service level penalties.
- **Why Exact Solvers Fail**: Stochastic non-stationary customer demand, multi-day lead times, case-pack / MOQ constraints, and FIFO shelf-life cohort dynamics induce a state-space explosion that overwhelms dynamic programming and MILP solvers.
- **Classical Heuristics Fail**: Static $(s, S)$ order-up-to policies with standard Gaussian safety stock ($z\sigma\sqrt{L}$) cannot anticipate expiry cohorts or promo spikes, leading to 12%–18% spoilage rates and missed SLAs.

---

## 2. The Solution: AlphaEvolve Policy Synthesis

AlphaEvolve evolves the constructive decision policy inside [`src/program.py`](src/program.py):

```python
# EVOLVE-BLOCK-START
def compute_replenishment_orders(
    state: dict[str, np.ndarray],
    config: dict[str, np.ndarray],
) -> np.ndarray: ...


# EVOLVE-BLOCK-END
```

### The 3-Tier Evaluation Harness ([`src/evaluate.py`](src/evaluate.py))

1. **Tier 1 (Fast Smoke Check, <0.1s)**: Verifies finite, non-negative order outputs and shape consistency over 5 days across 10 SKUs.
2. **Tier 2 (Validation Rollout, ~1.2s)**: Executes a 35-day vectorized FIFO simulation across 50 SKU-store nodes, evaluating:
   $$\text{cost\_reduction\_pct} = \frac{C_{\text{baseline}} - C_{\text{candidate}}}{C_{\text{baseline}}} \times 100 - 50.0 \times \max(0, 0.95 - \text{FR})^2$$
   Alongside numerical scores, the evaluator returns structured diagnostic **Insights** explaining whether losses arose from spoilage cohorts or stockouts.
3. **Locked Holdout Test (Days 66–90)**: Evaluated only once after evolution finishes in [`src/report.py`](src/report.py) to prove that the discovered heuristic generalizes out-of-sample.

---

## 3. How to Run

### Option A: Local Offline Dry-Run (No Cloud Setup Required)

Run the entire evolutionary pipeline locally using synthetic candidate mutations:

```bash
uv run python examples/inventory_replenishment/run_evolution.py --dry-run --max-programs 5
```

### Option B: Cloud Optimization with Gemini Enterprise

Ensure `.env` contains your Google Cloud `PROJECT_ID` and `ENGINE_ID`, then run:

```bash
uv run python examples/inventory_replenishment/run_evolution.py --max-programs 25 --workers 4
```

---

## 4. Expected Outcome

- **Discovered Heuristic**: An age-aware, censored-demand-corrected replenishment policy that projects lead-time cohort expiration $\hat{W}_{t:t+L}$ before computing net inventory position and scales safety stock asymmetrically based on critical fractiles.
- **Business Impact**:
  - **15%–28% reduction** in total supply chain cost.
  - **30%–45% reduction** in perishable spoilage waste.
  - Lift in customer service fill rate from **~91% to >96.5%**.
