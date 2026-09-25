# Domain Context: Multi-Echelon & Perishable Inventory Replenishment

## 1. Problem Formulation

You are an expert operations researcher and algorithmic engineer optimizing inventory replenishment for a retail supply chain network containing both short shelf-life perishable goods (dairy, produce, meats) and standard ambient items.

### The Objective

Discover a replenishment policy `compute_replenishment_orders(state, config)` that minimizes total supply chain costs over a multi-period planning horizon:

$$\text{Total Cost} = C_{\text{holding}} + C_{\text{spoilage}} + C_{\text{stockout}} + C_{\text{ordering}}$$

subject to maintaining a customer service **fill rate $\ge 95.0\%$**.

Candidate policies are scored against a classical static $(s, S)$ order-up-to baseline:
$$\text{cost\_reduction\_pct} = \frac{C_{\text{baseline}} - C_{\text{candidate}}}{C_{\text{baseline}}} \times 100 - 50.0 \times \max(0, 0.95 - \text{Fill Rate})^2$$

---

## 2. System State & Parameter Interfaces

Your function receives two vectorized dictionaries every decision day $t$:

### `state` Dictionary (Causal History Only $\le t$)
- `on_hand_by_age`: `np.ndarray` of shape `(N_skus, max_shelf_life)`
  - FIFO inventory cohorts. Index `a = 0` represents the oldest inventory expiring at the end of day $t$. Index `a = shelf_life - 1` represents newly received inventory.
- `in_transit_pipeline`: `np.ndarray` of shape `(N_skus, max_lead_time)`
  - In-flight replenishment orders. Index `l = 0` arrives on the next business day ($t+1$).
- `demand_history`: `np.ndarray` of shape `(N_skus, lookback_days)`
  - Historical observed sales up to day $t-1$.
- `stockout_history`: `np.ndarray` of shape `(N_skus, lookback_days)`
  - Boolean flag indicating whether a stockout occurred (demand was censored).
- `promo_schedule_lookahead`: `np.ndarray` of shape `(N_skus, 7)`
  - Planned promotional discount depth for the upcoming 7 days $[t, t+6]$.
- `day_of_week`: `int` (0 = Monday, ..., 6 = Sunday).

### `config` Dictionary (Static SKU Parameters)
- `lead_time_days`: `np.ndarray` of shape `(N_skus,)` (integer lead time $L$)
- `shelf_life_days`: `np.ndarray` of shape `(N_skus,)` (maximum shelf life $M$)
- `holding_cost`: `np.ndarray` of shape `(N_skus,)` ($c_h$ per unit per day)
- `spoilage_cost`: `np.ndarray` of shape `(N_skus,)` ($c_w$ per expired unit)
- `stockout_penalty`: `np.ndarray` of shape `(N_skus,)` ($c_p$ per unfulfilled unit)
- `moq`: `np.ndarray` of shape `(N_skus,)` (Minimum Order Quantity)
- `case_pack_size`: `np.ndarray` of shape `(N_skus,)` (orders must be rounded to multiples of this pack size)

---

## 3. Physical Dynamics & Constraints

1. **FIFO Depletion**: Customers consume oldest available inventory first ($a = 0$). Any unsold inventory reaching age 0 at the end of the day is condemned and incurs `spoilage_cost`.
2. **Order Constraints**:
   - Order quantities must be **non-negative finite numbers**.
   - If an order is placed ($Q > 0$), it must be $\ge \text{MOQ}$ and rounded to an integer multiple of `case_pack_size`.
3. **Censored Demand**: When a stockout occurs, observed sales underestimate true customer demand.

---

## 4. Promising Algorithmic Directions (Prior Art)

- **Censored Demand Imputation**: When `stockout_history` is true, estimate latent unobserved demand rather than using raw observed sales.
- **Lead-Time Spoilage Projection ($\hat{W}_{t:t+L}$)**: Calculate how much existing on-hand inventory is expected to expire *before* the arriving order lands ($t + L$). Subtracting projected spoilage from net inventory position prevents stockouts without accumulating excess age.
- **Asymmetric Critical Fractile Scaling**: Safety stock should dynamically reflect the cost ratio:
  $$CF = \frac{c_{\text{stockout}}}{c_{\text{stockout}} + c_{\text{spoilage}} + c_{\text{holding}}}$$
  High-spoilage SKUs require tighter buffers, whereas high-margin/high-penalty items require larger buffers.
- **Promotional Elasticity Lookahead**: Pre-build inventory ahead of promotional discount spikes in `promo_schedule_lookahead`.

---

## 5. Explicit Negative Constraints ("What NOT to do")

- **DO NOT** use future lookahead or peek beyond day $t$ (other than the provided `promo_schedule_lookahead`).
- **DO NOT** import heavy external machine learning libraries inside the replenishment function; use fast vectorized `numpy` operations.
- **DO NOT** output negative or fractional quantities for integer-packaged SKUs.
- **DO NOT** remove or change the function signature `compute_replenishment_orders(state, config)`.
