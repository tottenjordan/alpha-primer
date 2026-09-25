### Candidate Use Case: Multi-Echelon & Perishable Inventory Replenishment Digital Twin

#### 1. Why It Is a Top Candidate

- **Direct Customer Proof Point**: Mirrors the **BASF Agricultural Solutions** AlphaEvolve reference case (evolving production consolidation rules and dynamic safety stock policies inside a stateful supply chain digital twin) and showcases the official **"Simulation"** evaluation method.
- **Why Exact Solvers Fall Short**: Under stochastic non-stationary demand, promotional spikes, multi-day lead times, MOQ/case-pack constraints, censored stockouts, and **FIFO shelf-life expiration (spoilage)**, exact dynamic programming suffers from state-space explosion. Classic $(s, S)$ policies with static safety stock ($z\sigma\sqrt{L}$) suffer simultaneously from high perishable waste during low-demand periods and severe stockouts during promotions.

#### 2. Public Datasets & Anti-Overfitting Split

- **Primary Perishable Retail Dataset**: **[`Dingdong-Inc/FreshRetailNet-50K` (HuggingFace)](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K)** — Apache-2.0 dataset with `50,000` store-SKU daily/hourly time series across 898 stores and 863 perishable SKUs over 90 days, including observed sales, censored stockout hours, discount schedules, and weather/holiday covariates.
- **Primary Multi-Echelon Industrial BOM Benchmark**: **[`stockpyl` (Graves & Willems 38 Industrial Supply Chains)](https://github.com/LarrySnyder/stockpyl)** — Open-source supply chain simulation library bundling the **38 real-world industrial multi-echelon BOM networks** from Graves & Willems (2000, 2008).
- **Alternative Retail Benchmark**: **[`M5 Forecasting` (Walmart / HuggingFace)](https://huggingface.co/datasets/kashif/M5)** (`30,490` hierarchical retail series).
- **Data Partitioning**:
  - Deterministic stratified subset of **200 SKU-store trajectories** from `FreshRetailNet-50K`.
  - **Days 1–30**: Historical warm-up window.
  - **Days 31–65 (Validation Rollout)**: Used inside `src/evaluate.py` to score candidate policies (`~1.2s`).
  - **Days 66–90 (Locked Holdout Test Rollout)**: Used only in `src/utils/report.py` after evolution.

#### 3. End-to-End Workflow & Code Architecture

- **Seed Program (`src/program.py`)**: ~65-line baseline implementing a classic $(s, S)$ order-up-to policy using trailing 14-day mean demand and static $z=1.65$ safety stock:

  ```python
  # EVOLVE-BLOCK-START
  def compute_replenishment_orders(
      state: dict[str, np.ndarray],
      config: dict[str, np.ndarray],
  ) -> np.ndarray:
      """Computes vectorized daily order quantities across all SKU-store nodes.

      Args:
          state: Vectorized dictionary for day t containing ONLY causal history (<= t):
              - 'on_hand_by_age': shape (N_skus, max_shelf_life), FIFO inventory cohorts
              - 'in_transit_pipeline': shape (N_skus, max_lead_time), arriving orders
              - 'demand_history': shape (N_skus, lookback_days), past observed sales
              - 'stockout_history': shape (N_skus, lookback_days), past censored stockout flags
              - 'promo_schedule_lookahead': shape (N_skus, 7), known planned discounts
              - 'day_of_week': int (0..6)
          config: Static SKU parameters:
              - 'lead_time_days', 'shelf_life_days', 'unit_margin',
              - 'holding_cost', 'spoilage_cost', 'stockout_penalty', 'moq', 'case_pack_size'

      Returns:
          order_quantities: 1D np.ndarray of non-negative order quantities of shape (N_skus,).
      """


  # EVOLVE-BLOCK-END
  ```

- **3-Tier Evaluator (`src/evaluate.py` + `src/simulator.py`)**:
  - **Causal Isolation**: At each simulation step $t \in [31, 65]$, `simulator.py` slices `demand_history[:, :t]` so candidate policies cannot peek at future demand.
  - **Tier 1**: 5-day smoke rollout on 10 SKUs verifying non-negative finite orders and MOQ/case-pack compliance.
  - **Tier 2**: Vectorized 35-day rollout across 200 SKUs computing total supply chain cost (holding + FIFO spoilage + stockout penalty + ordering cost) with a smooth quadratic penalty if fill rate $FR < 95.0\%$:
    $$\text{cost\_reduction\_pct} = \frac{C_{\text{baseline}} - C_{\text{candidate}}}{C_{\text{baseline}}} \times 100 - 50.0 \times \max(0, 0.95 - FR)^2$$
    Returns `cost_reduction_pct`, `fill_rate_pct`, `spoilage_rate_pct`, and `inventory_turnover` in `scores.scores`, plus per-shelf-life-tier spoilage/stockout diagnostics in `insights.insights`.

#### 4. Example Desired Outcome

- **Discovered Policy**: Evolves a **censored-demand-corrected, FIFO-age-aware replenishment heuristic** that imputes latent demand on historical stockout days, projects FIFO cohort expiration over the lead-time horizon $\hat{W}_{t:t+L}$ before computing net inventory position, and scales safety stock asymmetrically based on $\frac{c_{\text{stockout}}}{c_{\text{spoil}} + c_{\text{hold}}}$ and upcoming promotional elasticity.
- **Quantified Impact**: **15%–28% reduction in total supply chain cost**, cutting perishable spoilage by **30%–45%** while lifting service fill rate from **~91% to >96.5%**.
