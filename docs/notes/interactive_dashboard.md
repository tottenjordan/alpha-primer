# Interactive Dashboard Architecture & Web Serving

Documenting the interactive executive suite for the Multi-Echelon Perishable Inventory Replenishment Digital Twin.

## Core Design Principles

1. **Zero External Dependencies by Default**:
   - Web server (`server.py`) implements a decoupled request dispatcher `handle_api_request(path: str) -> tuple[int, dict[str, str], Any]`.
   - Runs out-of-the-box using Python's standard library `http.server.ThreadingHTTPServer` (`uv run python server.py`).
   - Seamlessly upgrades to `FastAPI` + `Uvicorn` if installed in the environment.
2. **Zero External Graphing CDNs**:
   - All charts, time-series trajectories, and Pareto convergence curves use native HTML5 Canvas 2D.
   - High-DPI Retina scaling (`ctx.scale(window.devicePixelRatio, window.devicePixelRatio)`) ensures crisp graphics across all displays.
3. **Enterprise Safe DOM Compliance**:
   - Zero `innerHTML` assignments to prevent DOM injection / XSS risks.
   - Dynamic rows, cards, and code views strictly use `document.createElement`, `textContent`, and `replaceChildren`.
4. **Instant Zero-Latency Scrubbing**:
   - 31 generational frames (Gen 0 seed baseline to Gen 30 champion) are embedded in a `<script id="master-trajectory-data" type="application/json">` data island.
   - Executive scrubber instantly updates KPIs, 90-day inventory dynamics, and spoilage indicators across 3 causal phases (Warmup 0..29, Validation 30..65, Holdout 66..89).
5. **Interactive What-If Sandbox**:
   - Client-side in-browser simulation (<2ms latency) allowing live adjustment of supplier lead time delay, promotional demand spikes, and spoilage/stockout penalty multipliers across 3 SKU archetypes.

## Running the Dashboard

```bash
uv run python server.py
```
Visit `http://127.0.0.1:8080` in any browser.
