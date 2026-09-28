# Dataset Specification: Multi-Echelon & Perishable Inventory Replenishment Digital Twin

This document provides a comprehensive technical reference for the dataset used across the simulation engine, evaluation harness, and AlphaEvolve heuristic synthesis experiments in `examples/inventory_replenishment/`.

---

## 1. Overview & Real-World Provenance

- **Reference Architecture**: Modeled on and calibrated against the empirical demand and network distributions of **FreshRetailNet-50K** (large-scale perishable retail replenishment benchmark).
- **Enterprise Use Case**: Directly reflects real-world supply chain engagements—such as **BASF Agricultural Solutions** and grocery retail distribution—where inventory decisions must balance severe FIFO spoilage costs against stockout SLA penalties under stochastic customer demand and lead-time delays.
- **Generator Implementation**: Programmatically constructed via [`generate_benchmark_dataset()`](src/simulator.py#L40-L102) in `examples/inventory_replenishment/src/simulator.py`.

---

## 2. Dataset Scale & Evaluation Splits

The simulation spans **50 SKU-store nodes** across a **90-day** operational horizon with daily discrete-event time steps ($t = 0, 1, \dots, 89$).

| Phase | Days | Purpose | Notes |
| :--- | :--- | :--- | :--- |
| **Warmup Phase** | **Days 0–30** (30 days) | Initialize digital twin state | Warms up the system under a standard order policy to populate realistic FIFO shelf-life cohorts and in-transit pipelines. |
| **Validation Window** | **Days 31–65** (35 days) | Tier 2 Policy Evaluation | The primary scoring window used during evolutionary search to calculate cost reduction, fill rates, and spoilage. |
| **Holdout Test Set** | **Days 66–90** (25 days) | Tier 3 Out-of-Sample Verification | Locked test window evaluated only after evolution completes to verify generalization on unseen demand and promo patterns. |
| **Smoke Test Slice** | **Days 30–34** (5 days, 10 SKUs) | Tier 1 Fast Verification | Rapid health check (<0.1s, seed `99`) ensuring policies produce valid, non-negative, non-NaN arrays of correct shape. |

---

## 3. SKU Catalog & Shelf-Life Categorization

The 50 SKU catalog is partitioned into two distinct product categories with differing physical degradation rates:

### A. Short-Life Perishables (60% of Catalog, ~30 SKUs)
- **Shelf Life**: Uniformly distributed between **3 and 7 days** ($\sim \text{Uniform}\{3, \dots, 7\}$).
- **Operational Risk**: High susceptibility to FIFO cohort expiration and waste if orders exceed near-term demand.
- **Representative Products**: Fresh dairy, berries, prepared deli items, active biological agricultural inputs.

### B. Ambient / Medium-Life Products (40% of Catalog, ~20 SKUs)
- **Shelf Life**: Uniformly distributed between **10 and 21 days** ($\sim \text{Uniform}\{10, \dots, 21\}$).
- **Operational Risk**: Lower spoilage hazard, but susceptible to excessive holding costs and working capital lockup if minimum order quantities (MOQs) force over-replenishment.
- **Representative Products**: Packaged staples, shelf-stable goods, ambient dry inputs.

---

## 4. Demand Generation & Stochastic Properties

Customer demand is non-stationary, combining base item velocity, day-of-week seasonality, promotional lifts, and Poisson arrival noise.

### Mathematical Formulation

$$\text{Demand}_{i,t} \sim \text{Poisson}\left(\mu_i \cdot M_{\text{dow}}(t) \cdot L_{\text{promo}}(i, t)\right)$$

Where:
1. **Base Mean Demand ($\mu_i$)**: Drawn independently per SKU from $\text{Uniform}(8.0, 35.0)$ units/day.
2. **Weekly Day-of-Week Seasonality ($M_{\text{dow}}$)**:
   - Weekdays (Monday–Friday): $M_{\text{dow}} = 0.90$
   - Weekends (Saturday–Sunday): $M_{\text{dow}} = 1.45$
3. **Promotions & Demand Lift ($L_{\text{promo}}$)**:
   - Each SKU has 4 to 12 scheduled promotional discount periods across the 90 days.
   - Planned discount depths range from $15\%$ to $35\%$ ($d_{i,t} \in [0.15, 0.35]$).
   - Demand lift is modeled as:
     $$L_{\text{promo}}(i, t) = 1.0 + 2.5 \cdot d_{i,t}$$
     (Yielding demand surges up to $1.875\times$ base volume).

### Censored Demand Dynamics

In physical retail and distribution networks, unfulfilled demand during stockouts is lost and unobserved at point-of-sale (POS) registers. The simulation models this causal reality:
- Observed sales: $S_{i,t} = \min(\text{Available Inventory}_{i,t}, \text{True Demand}_{i,t})$.
- If inventory reaches zero, a stockout flag is triggered ($\text{Stockout}_{i,t} = 1$).
- Policies receive only observed sales $S_{i,t}$ and the binary stockout flag, requiring advanced policies to impute true latent customer demand rather than treating zero sales as zero demand.

---

## 5. Physical Supply Chain Constraints & Unit Economics

Each SKU is parameterized with realistic supply chain frictions and cost parameters:

| Parameter | Symbol | Range / Value | Operational Meaning |
| :--- | :---: | :--- | :--- |
| **Supplier Lead Time** | $L_i$ | $\text{Uniform}\{1, 2, 3\}$ days | Discrete transit delay between order placement and inventory arrival. |
| **Case Pack Size** | $Q_i^{\text{pack}}$ | $\{6, 12, 24\}$ units | Packaging multiple; all order quantities must round up to whole packs. |
| **Minimum Order Qty** | $\text{MOQ}_i$ | $1\times \text{to } 3\times Q_i^{\text{pack}}$ | Minimum batch size required by the vendor before an order is accepted. |
| **Holding Cost** | $c_i^{\text{hold}}$ | $\$0.05 \dots \$0.20$ / unit / day | Carrying cost of capital, refrigeration, and warehouse space. |
| **Spoilage Cost** | $c_i^{\text{spoil}}$ | $\$2.50 \dots \$6.00$ / spoiled unit | Direct loss when a FIFO cohort reaches age 0 without being sold. |
| **Stockout Penalty** | $p_i$ | $\$3.00 \dots \$8.00$ / unit short | Customer SLA penalty, lost gross margin, and contractual service penalties. |
| **Order Fixed Cost** | $K_i$ | $\$2.00$ / order event | Administrative cost per purchase order placed, incentivizing batch consolidation. |

---

## 6. Runtime State & Configuration Schema

Candidate replenishment policies implement the function:

```python
def compute_replenishment_orders(
    state: dict[str, np.ndarray],
    config: dict[str, np.ndarray],
) -> np.ndarray: ...
```

### `state` Dictionary (Causal Information up to Day $t$)

| Key | Type / Shape | Description |
| :--- | :--- | :--- |
| `on_hand_by_age` | `np.ndarray (50, max_shelf_life)` | Inventory count partitioned by days of remaining shelf life (index 0 expires at day end). |
| `in_transit_pipeline` | `np.ndarray (50, max_lead_time)` | Orders in transit arriving on days $t+1, t+2, \dots$ |
| `demand_history` | `np.ndarray (50, lookback_days)` | Trailing observed daily sales (censored during stockout events). |
| `stockout_history` | `np.ndarray (50, lookback_days)` | Binary array where `1.0` denotes a stockout occurred on that day. |
| `promo_schedule_lookahead` | `np.ndarray (50, 7)` | Known planned promotional discount depths for the upcoming 7 days. |
| `day_of_week` | `int` | Current day of week ($0 = \text{Monday}, \dots, 6 = \text{Sunday}$). |

### `config` Dictionary (Static Parameters)

| Key | Type / Shape | Description |
| :--- | :--- | :--- |
| `lead_time_days` | `np.ndarray (50,)` | Supplier lead time in days for each SKU. |
| `shelf_life_days` | `np.ndarray (50,)` | Total shelf life in days upon arrival for each SKU. |
| `holding_cost` | `np.ndarray (50,)` | Daily holding cost per unit. |
| `spoilage_cost` | `np.ndarray (50,)` | Cost per spoiled unit. |
| `stockout_penalty` | `np.ndarray (50,)` | Penalty per unfulfilled demand unit. |
| `order_fixed_cost` | `np.ndarray (50,)` | Fixed transaction cost per purchase order. |
| `moq` | `np.ndarray (50,)` | Minimum Order Quantity in units. |
| `case_pack_size` | `np.ndarray (50,)` | Packaging unit multiplier. |

---

## 7. Deterministic Seeds & Reproducibility

To ensure scientific comparability across AlphaEvolve generations, random number generators in the benchmark suite use fixed seeds:

- **Benchmark Dataset (Validation & Holdout)**: `seed=42` (`numpy.random.default_rng(42)`)
- **Smoke Test Harness**: `seed=99` (`numpy.random.default_rng(99)`)
