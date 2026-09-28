# Domain Context: Dynamic Fleet Routing & Dispatch with Time Windows (VRPTW)

## 1. Problem Formulation

You are an expert operations researcher and algorithmic engineer optimizing dynamic vehicle routing and dispatch for an urban last-mile delivery fleet with customer delivery time windows, dynamic traffic congestion, and stochastic order arrival.

### The Objective

Discover a route assignment and stop sequencing policy `assign_and_sequence_routes(state, config)` that minimizes total fleet operational costs over a 12-hour operational shift:

$$\text{Total Cost} = C_{\text{distance}} + C_{\text{vehicles}} + C_{\text{tardiness}} + C_{\text{idle\_wait}} + C_{\text{unserved}}$$

subject to satisfying customer delivery time windows $[e_i, l_i]$ and vehicle capacity constraints $Q_{\text{max}}$.

Candidate policies are scored against a greedy nearest-neighbor baseline:
$$\text{score} = \text{cost\_reduction\_pct} - 1.5 \times \max(0, 95.0 - \text{On-Time \%})^{1.5} - 50.0 \times \left(\frac{\text{Unserved Orders}}{N_{\text{customers}}}\right)$$

---

## 2. System State & Parameter Interfaces

Your function receives two dictionaries at every dispatch cycle:

### `state` Dictionary (Current Network Snapshot)
- `current_time`: `float` (current shift time in hours, $0.0 \le t \le 12.0$).
- `visible_order_indices`: `list[int]` (indices of customer orders placed by $t$).
- `traffic_factor`: `float` (current speed divisor, $>1.0$ during peak morning/evening rush hours).
- `vehicle_positions`: `np.ndarray` of shape `(N_vehicles, 2)` (coordinates of fleet vehicles).
- `vehicle_remaining_capacities`: `np.ndarray` of shape `(N_vehicles,)` (available capacity units).
- `customer_locations`: `np.ndarray` of shape `(N_visible, 2)` (2D spatial coordinates).
- `demands`: `np.ndarray` of shape `(N_visible,)` (demand units for visible orders).
- `time_windows`: `np.ndarray` of shape `(N_visible, 2)` (earliest delivery hour, latest deadline hour).
- `service_times`: `np.ndarray` of shape `(N_visible,)` (service duration in hours at customer site).
- `depot_location`: `np.ndarray` of shape `(2,)` (central warehouse coordinates).

### `config` Dictionary (Static Fleet Parameters)
- `n_customers`: `int` (total orders in scenario).
- `n_vehicles`: `int` (fleet size).
- `vehicle_capacity`: `float` (maximum capacity per vehicle).
- `cost_per_km`: `float` ($1.75/km fuel and wear).
- `fixed_vehicle_cost`: `float` ($120.00 driver day wage).
- `late_penalty_per_hour`: `float` ($45.00/hr late fee).
- `wait_cost_per_hour`: `float` ($15.00/hr driver idle wait).
- `unserved_order_penalty`: `float` ($150.00 per unserved customer).

---

## 3. Physical Dynamics & Constraints

1. **Causal Isolation**: You only observe orders whose `order_time <= current_time`. Future dynamic orders are strictly unobservable until they arrive.
2. **Dynamic Traffic**: Travel time between $(x_1, y_1)$ and $(x_2, y_2)$ is $\text{distance} / (\text{base\_speed} / \text{traffic\_factor}(t))$. Congestion peaks at $t \in [1.0, 3.0]$ and $t \in [8.0, 10.5]$.
3. **Vehicle Capacity**: The sum of customer demands on any vehicle's route sequence must not exceed `vehicle_capacity`.
4. **Time Windows**: Arriving before $e_i$ incurs idle wait time. Arriving after $l_i$ incurs a heavy linear tardiness penalty ($45.00/hr).

---

## 4. Promising Algorithmic Directions (Prior Art)

- **Time-Window Slack Slackness Ranking**: Rather than ordering purely by Euclidean distance, rank customers by remaining slack $l_i - t - \text{travel\_time}$ to avoid late delivery penalties.
- **Traffic Congestion Avoidance**: Route distant perimeter deliveries during mid-day troughs ($t \in [4.0, 7.5]$) and cluster dense depot-adjacent stops during rush hours.
- **Dynamic Insertion & Regret Heuristics**: Re-sequence existing routes when new emergency dynamic orders arrive at $t > 0$ using 2-opt or regret-based insertion.
- **Capacity Clustering (Sweep / K-Means)**: Partition spatial coordinates into angular clusters to avoid vehicle path crisscrossing.
