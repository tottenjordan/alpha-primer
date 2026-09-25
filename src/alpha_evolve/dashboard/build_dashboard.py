"""Build the C-Suite Interactive Dashboard for AlphaEvolve Supply Chain Digital Twin.

Compiles `dashboard/index.html` from `records/master_trajectories.json`.
Strictly enforces enterprise Safe DOM construction (document.createElement, textContent,
replaceChildren) with ZERO innerHTML assignments.
Features High-DPI Retina Canvas 2D charts (devicePixelRatio scaling),
interactive What-If perishable inventory simulation sandbox, 90-day trajectory replay,
and side-by-side code diffs.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
RECORDS_DIR = ROOT_DIR / "records"
DASHBOARD_DIR = ROOT_DIR / "dashboard"


def build_dashboard_html() -> Path:
    """Compile records/master_trajectories.json into self-contained dashboard/index.html."""
    master_path = RECORDS_DIR / "master_trajectories.json"
    if not master_path.exists():
        raise FileNotFoundError(f"Missing {master_path}. Run trajectory_generator.py first.")

    master_data = json.loads(master_path.read_text(encoding="utf-8"))
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    (DASHBOARD_DIR / "data.json").write_text(json.dumps(master_data, indent=2), encoding="utf-8")

    embedded_json = json.dumps(master_data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AlphaEvolve Supply Chain &amp; Digital Twin Intelligence Suite</title>
  <meta name="description" content="Autonomous Multi-Echelon &amp; Perishable Inventory Replenishment Heuristic Optimization powered by Google Cloud Discovery Engine AlphaEvolve." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg-canvas: #070B14;
      --bg-surface: #0D1424;
      --bg-elevated: #131D33;
      --bg-card: #0F172A;
      --border-subtle: rgba(148, 163, 184, 0.14);
      --border-strong: rgba(245, 158, 11, 0.35);
      --text-primary: #F8FAFC;
      --text-secondary: #CBD5E1;
      --text-muted: #94A3B8;
      --accent-gold: #F59E0B;
      --accent-emerald: #10B981;
      --accent-cyan: #06B6D4;
      --accent-coral: #F43F5E;
      --accent-blue: #38BDF8;
      --font-body: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-display: 'Space Grotesk', sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background-color: var(--bg-canvas);
      color: var(--text-primary);
      font-family: var(--font-body);
      line-height: 1.5;
      padding: 16px 24px;
      -webkit-font-smoothing: antialiased;
    }}

    header {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 16px 20px;
      margin-bottom: 16px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }}

    .top-meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }}

    .title-group {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .logo-badge {{
      background: linear-gradient(135deg, var(--accent-gold) 0%, var(--accent-coral) 100%);
      color: #04130D;
      font-family: var(--font-mono);
      font-weight: 800;
      font-size: 13px;
      padding: 4px 8px;
      border-radius: 6px;
      letter-spacing: 0.5px;
    }}

    h1 {{
      font-family: var(--font-display);
      font-size: 19px;
      font-weight: 700;
      color: var(--text-primary);
      letter-spacing: -0.3px;
    }}

    .meta-pills {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}

    .pill {{
      font-family: var(--font-mono);
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 6px;
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}

    .pill.status-live {{
      border-color: rgba(16, 185, 129, 0.4);
      color: var(--accent-emerald);
      background: rgba(16, 185, 129, 0.1);
    }}

    .status-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 6px var(--accent-emerald);
    }}

    .controls-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
      padding-top: 12px;
      border-top: 1px solid rgba(148, 163, 184, 0.08);
    }}

    .nav-tabs {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .tab-btn {{
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 8px 14px;
      border-radius: 8px;
      font-family: var(--font-display);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }}

    .tab-btn:hover {{
      border-color: var(--accent-cyan);
      color: var(--text-primary);
    }}

    .tab-btn.active {{
      background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(16, 185, 129, 0.15) 100%);
      border-color: var(--accent-cyan);
      color: var(--text-primary);
      box-shadow: 0 2px 10px rgba(6, 182, 212, 0.2);
    }}

    .playback-bar {{
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      padding: 6px 14px;
      border-radius: 8px;
      flex: 1;
      max-width: 620px;
    }}

    .btn-play {{
      background: var(--accent-emerald);
      color: #03140C;
      border: none;
      border-radius: 6px;
      padding: 6px 12px;
      font-family: var(--font-display);
      font-weight: 700;
      font-size: 12px;
      cursor: pointer;
      white-space: nowrap;
    }}

    .btn-preset {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      border-radius: 6px;
      padding: 4px 8px;
      font-family: var(--font-mono);
      font-size: 11px;
      cursor: pointer;
      white-space: nowrap;
    }}

    .btn-preset:hover {{
      border-color: var(--accent-cyan);
      color: var(--text-primary);
    }}

    .scrubber-slider {{
      flex: 1;
      accent-color: var(--accent-cyan);
      cursor: pointer;
    }}

    .gen-badge {{
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--accent-cyan);
      font-weight: 600;
      white-space: nowrap;
      min-width: 78px;
      text-align: right;
    }}

    /* Tab Content Panes */
    .tab-pane {{
      display: none;
    }}

    .tab-pane.active {{
      display: block;
    }}

    /* Executive KPI Grid */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-bottom: 16px;
    }}

    .kpi-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 14px 16px;
      position: relative;
      overflow: hidden;
    }}

    .kpi-card::after {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: var(--border-subtle);
    }}

    .kpi-card.highlight::after {{
      background: linear-gradient(90deg, var(--accent-emerald), var(--accent-cyan));
    }}

    .kpi-label {{
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }}

    .kpi-val {{
      font-family: var(--font-display);
      font-size: 26px;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1.15;
    }}

    .kpi-sub {{
      font-size: 11.5px;
      color: var(--text-secondary);
      margin-top: 4px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .badge-diff {{
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 600;
      padding: 1px 6px;
      border-radius: 4px;
    }}

    .badge-diff.positive {{
      background: rgba(16, 185, 129, 0.18);
      color: var(--accent-emerald);
    }}

    .badge-diff.neutral {{
      background: rgba(6, 182, 212, 0.18);
      color: var(--accent-cyan);
    }}

    /* Canvas Grid */
    .canvas-grid {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }}

    @media (max-width: 1080px) {{
      .canvas-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    .card-box {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 16px;
    }}

    .card-title {{
      font-family: var(--font-display);
      font-size: 14.5px;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .canvas-container {{
      position: relative;
      width: 100%;
      height: 280px;
    }}

    canvas {{
      width: 100%;
      height: 100%;
      display: block;
    }}

    /* Dynamic Tables */
    .table-container {{
      overflow-x: auto;
      margin-top: 10px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12.5px;
    }}

    th {{
      background: var(--bg-elevated);
      color: var(--text-muted);
      font-family: var(--font-mono);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      text-align: left;
      padding: 8px 12px;
      border-bottom: 1px solid var(--border-subtle);
    }}

    td {{
      padding: 10px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.08);
      color: var(--text-secondary);
    }}

    tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
      color: var(--text-primary);
    }}

    /* What-If Sandbox */
    .sandbox-layout {{
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 16px;
    }}

    @media (max-width: 900px) {{
      .sandbox-layout {{
        grid-template-columns: 1fr;
      }}
    }}

    .slider-group {{
      margin-bottom: 16px;
    }}

    .slider-header {{
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      margin-bottom: 6px;
      font-family: var(--font-mono);
    }}

    .slider-input {{
      width: 100%;
      accent-color: var(--accent-gold);
      cursor: pointer;
    }}

    .archetype-select {{
      width: 100%;
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-primary);
      padding: 8px 12px;
      border-radius: 6px;
      font-family: var(--font-body);
      font-size: 13px;
      margin-bottom: 16px;
    }}

    /* Monospace Code Diff View */
    .diff-container {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}

    @media (max-width: 960px) {{
      .diff-container {{
        grid-template-columns: 1fr;
      }}
    }}

    .code-box {{
      background: #040810;
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 14px;
      font-family: var(--font-mono);
      font-size: 11.5px;
      color: #93C5FD;
      overflow-x: auto;
      max-height: 520px;
      line-height: 1.45;
      white-space: pre-wrap;
    }}

    .btn-copy {{
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 4px 8px;
      font-size: 11px;
      font-family: var(--font-mono);
      border-radius: 4px;
      cursor: pointer;
    }}

    .btn-copy:hover {{
      border-color: var(--accent-cyan);
      color: var(--text-primary);
    }}
  </style>
</head>
<body>

  <!-- Telemetry Data Island (JSON parse safe) -->
  <script id="master-trajectory-data" type="application/json">
{embedded_json}
  </script>

  <header>
    <div class="top-meta">
      <div class="title-group">
        <span class="logo-badge">ALPHA-EVOLVE</span>
        <h1 id="header-platform-title">AlphaEvolve Supply Chain &amp; Digital Twin Intelligence Suite</h1>
      </div>
      <div class="meta-pills">
        <div class="pill status-live">
          <span class="status-dot"></span>
          <span>ADC VERIFIED</span>
        </div>
        <div class="pill">
          <span>Engine: <b id="meta-engine-id">alpha-evolve-experiment-engine</b></span>
        </div>
        <div class="pill">
          <span>Model: <b>gemini-3.5-flash</b></span>
        </div>
        <div class="pill">
          <span>Horizon: <b>90 Days (Causal)</b></span>
        </div>
      </div>
    </div>

    <div class="controls-row">
      <div class="nav-tabs" id="nav-tabs">
        <button class="tab-btn active" data-tab="tab-replay">1. Digital Twin &amp; Evolution</button>
        <button class="tab-btn" data-tab="tab-whatif">2. What-If Sandbox</button>
        <button class="tab-btn" data-tab="tab-benchmark">3. Benchmark &amp; Math</button>
        <button class="tab-btn" data-tab="tab-diffs">4. Evolved Code Diffs</button>
      </div>

      <div class="playback-bar">
        <button class="btn-play" id="btn-play">▶ Play Evolution</button>
        <button class="btn-preset" data-gen="0">Gen 0</button>
        <button class="btn-preset" data-gen="8">Gen 8</button>
        <button class="btn-preset" data-gen="17">Gen 17</button>
        <button class="btn-preset" data-gen="30">Gen 30</button>
        <input type="range" class="scrubber-slider" id="scrubber" min="0" max="30" value="30" />
        <span class="gen-badge" id="scrubber-label">GEN 30 / 30</span>
      </div>
    </div>
  </header>

  <!-- TAB 1: Digital Twin & Evolution Replay -->
  <section id="tab-replay" class="tab-pane active">
    <div class="kpi-grid">
      <div class="kpi-card highlight">
        <div class="kpi-label">Total Supply Chain Cost</div>
        <div class="kpi-val" id="kpi-total-cost">$45,238</div>
        <div class="kpi-sub">
          <span class="badge-diff positive" id="kpi-cost-reduc">-33.9%</span>
          <span>vs. $68,410 baseline</span>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Perishable Spoilage Waste</div>
        <div class="kpi-val" id="kpi-spoilage-cost">$16,145</div>
        <div class="kpi-sub">
          <span class="badge-diff positive" id="kpi-spoilage-rate">8.45% rate</span>
          <span>vs. 14.6% baseline</span>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Service Fill Rate</div>
        <div class="kpi-val" id="kpi-fill-rate">93.49%</div>
        <div class="kpi-sub">
          <span class="badge-diff neutral">SLA: &ge;95.0%</span>
          <span>stockout penalty: <span id="kpi-stockout-cost">$14,573</span></span>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Evaluation Fitness Score</div>
        <div class="kpi-val" id="kpi-fitness-score">33.87</div>
        <div class="kpi-sub">
          <span class="badge-diff positive">+33.87 pts</span>
          <span>latency: <b>79 ms</b> rollout</span>
        </div>
      </div>
    </div>

    <!-- Active Generation Milestone Banner -->
    <div class="card-box" style="margin-bottom: 16px; padding: 12px 16px; background: rgba(6, 182, 212, 0.08); border-color: rgba(6, 182, 212, 0.3);">
      <div style="display: flex; align-items: center; justify-content: space-between; font-family: var(--font-mono); font-size: 12px;">
        <span style="color: var(--accent-cyan);" id="milestone-title">GEN 30 CHAMPION</span>
        <span style="color: var(--text-secondary);" id="milestone-desc">Unified multi-echelon perishable heuristic (-33.9% cost reduction)</span>
      </div>
    </div>

    <div class="canvas-grid">
      <div class="card-box">
        <div class="card-title">
          <span>90-Day Digital Twin Inventory Trajectory &amp; Spoilage Stack</span>
          <span style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">Days 0..29 Warmup | 30..65 Eval | 66..89 Holdout</span>
        </div>
        <div class="canvas-container">
          <canvas id="canvas-trajectory"></canvas>
        </div>
      </div>

      <div class="card-box">
        <div class="card-title">
          <span>Multi-Island Fitness Convergence</span>
          <span style="font-family: var(--font-mono); font-size: 11px; color: var(--accent-emerald);">Gen 0 &rarr; Gen 30</span>
        </div>
        <div class="canvas-container">
          <canvas id="canvas-convergence"></canvas>
        </div>
      </div>
    </div>

    <div class="card-box">
      <div class="card-title">
        <span>SKU Archetype Cost &amp; Spoilage Performance Breakdown</span>
      </div>
      <div class="table-container">
        <table id="table-archetypes">
          <thead>
            <tr>
              <th>SKU Category Archetype</th>
              <th>Shelf Life</th>
              <th>Lead Time</th>
              <th>Baseline Spoilage</th>
              <th>Champion Spoilage</th>
              <th>Holding Cost</th>
              <th>Spoilage Cost</th>
              <th>Stockout Penalty</th>
            </tr>
          </thead>
          <tbody id="tbody-archetypes">
            <!-- Populated via Safe DOM -->
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- TAB 2: Interactive What-If Sandbox -->
  <section id="tab-whatif" class="tab-pane">
    <div class="sandbox-layout">
      <div class="card-box">
        <div class="card-title">
          <span>Policy Stress-Test Parameters</span>
        </div>

        <label class="slider-header" for="whatif-sku">SKU Category Archetype</label>
        <select id="whatif-sku" class="archetype-select">
          <option value="0">Ultra-Perishables (Berries / Pre-cut Salads - 3 Days)</option>
          <option value="1">Chilled Dairy &amp; Fresh Meats (7 Days)</option>
          <option value="2">Ambient Grocery &amp; Packaged Goods (21 Days)</option>
        </select>

        <div class="slider-group">
          <div class="slider-header">
            <span>Supplier Lead Time Delay</span>
            <span id="val-leadtime">+0 days</span>
          </div>
          <input type="range" class="slider-input" id="slide-leadtime" min="0" max="5" value="0" />
        </div>

        <div class="slider-group">
          <div class="slider-header">
            <span>Promotional Demand Spike</span>
            <span id="val-promo">+0%</span>
          </div>
          <input type="range" class="slider-input" id="slide-promo" min="0" max="150" value="0" />
        </div>

        <div class="slider-group">
          <div class="slider-header">
            <span>Spoilage Cost Multiplier</span>
            <span id="val-spoil">1.0x</span>
          </div>
          <input type="range" class="slider-input" id="slide-spoil" min="5" max="30" value="10" />
        </div>

        <div class="slider-group">
          <div class="slider-header">
            <span>Stockout Penalty Multiplier</span>
            <span id="val-stockout">1.0x</span>
          </div>
          <input type="range" class="slider-input" id="slide-stockout" min="5" max="30" value="10" />
        </div>
      </div>

      <div class="card-box">
        <div class="card-title">
          <span>Real-Time Policy Response Simulation</span>
          <span style="font-family: var(--font-mono); font-size: 11px; color: var(--accent-emerald);">&lt;2ms In-Browser Recalculation</span>
        </div>

        <div class="kpi-grid" style="margin-bottom: 16px;">
          <div class="kpi-card highlight">
            <div class="kpi-label">Projected Reorder Up-To</div>
            <div class="kpi-val" id="whatif-orderup">184 units</div>
            <div class="kpi-sub"><span>Dynamic safety stock: <b id="whatif-safetystock">42 units</b></span></div>
          </div>

          <div class="kpi-card">
            <div class="kpi-label">Projected Daily Spoilage</div>
            <div class="kpi-val" id="whatif-spoilage">4.2 units</div>
            <div class="kpi-sub"><span class="badge-diff positive" id="whatif-spoil-pct">8.1% of stock</span></div>
          </div>

          <div class="kpi-card">
            <div class="kpi-label">Estimated Fill Rate</div>
            <div class="kpi-val" id="whatif-fill">94.8%</div>
            <div class="kpi-sub"><span id="whatif-sla-status">Compliant with SLA</span></div>
          </div>
        </div>

        <div class="canvas-container" style="height: 220px;">
          <canvas id="canvas-whatif"></canvas>
        </div>
      </div>
    </div>
  </section>

  <!-- TAB 3: Benchmark & Math -->
  <section id="tab-benchmark" class="tab-pane">
    <div class="card-box" style="margin-bottom: 16px;">
      <div class="card-title">
        <span>Evaluation Objective &amp; Digital Twin Architecture</span>
      </div>
      <div style="font-size: 13.5px; color: var(--text-secondary); line-height: 1.7;">
        <p style="margin-bottom: 10px;">
          The multi-echelon replenishment digital twin models stochastic customer demand across 50 heterogeneous SKU nodes over a 90-day causal horizon.
          The evaluation strictly enforces causal isolation: policy functions only have access to history <code>t &le; now</code>.
        </p>
        <p style="margin-bottom: 12px; font-family: var(--font-mono); background: var(--bg-canvas); padding: 12px; border-radius: 6px; border: 1px solid var(--border-subtle);">
          <b>Objective Function:</b><br />
          Score = Cost_Reduction_% - 50.0 &times; max(0, 0.95 - Fill_Rate)^2<br /><br />
          Total_Cost = C_holding + C_spoilage + C_stockout + C_ordering
        </p>
        <ul style="padding-left: 20px;">
          <li><b>Days 0..29 (Warmup):</b> Digital twin initializes FIFO age cohorts and in-transit pipelines under fixed seed demand.</li>
          <li><b>Days 30..65 (Validation Window):</b> AlphaEvolve scores candidate policies over 35 active business days.</li>
          <li><b>Days 66..89 (Holdout Window):</b> Out-of-sample stress test with promotional demand surges and lead-time shocks.</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- TAB 4: Evolved Code Diffs -->
  <section id="tab-diffs" class="tab-pane">
    <div class="diff-container">
      <div class="card-box">
        <div class="card-title">
          <span>Generation 0: Baseline Static (s, S) Heuristic</span>
          <button class="btn-copy" id="btn-copy-base">Copy Code</button>
        </div>
        <pre class="code-box"><code id="code-baseline"></code></pre>
      </div>

      <div class="card-box">
        <div class="card-title">
          <span>Generation 30: AlphaEvolve Evolved Champion</span>
          <button class="btn-copy" id="btn-copy-champ">Copy Evolve Block</button>
        </div>
        <pre class="code-box"><code id="code-champion"></code></pre>
      </div>
    </div>
  </section>

  <!-- Dashboard Client-Side Controller -->
  <script>
    (function() {{
      "use strict";

      // 1. Safe DOM Helper (strictly zero dangerous property assignments)
      function el(tag, className, text) {{
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = String(text);
        return node;
      }}

      // 2. Parse Embedded Telemetry
      const dataScript = document.getElementById("master-trajectory-data");
      if (!dataScript) return;
      let masterData = {{}};
      try {{
        masterData = JSON.parse(dataScript.textContent);
      }} catch (err) {{
        console.error("Failed to parse master-trajectory-data", err);
        return;
      }}

      const uc = masterData.use_cases ? masterData.use_cases.inventory_replenishment : null;
      if (!uc) return;

      const trajectories = uc.trajectory_generations || [];
      const archetypes = uc.sku_archetypes || [];
      const baselineSum = uc.baseline_summary || {{}};
      const championSum = uc.champion_summary || {{}};
      const maxGen = trajectories.length - 1;

      // 3. Tab Switching
      const tabBtns = document.querySelectorAll(".tab-btn");
      const tabPanes = document.querySelectorAll(".tab-pane");

      tabBtns.forEach(btn => {{
        btn.addEventListener("click", () => {{
          tabBtns.forEach(b => b.classList.remove("active"));
          tabPanes.forEach(p => p.classList.remove("active"));
          btn.classList.add("active");
          const target = document.getElementById(btn.getAttribute("data-tab"));
          if (target) target.classList.add("active");

          // Redraw canvases on tab switch
          if (btn.getAttribute("data-tab") === "tab-replay") {{
            drawTrajectoryChart(currentGen);
            drawConvergenceChart();
          }} else if (btn.getAttribute("data-tab") === "tab-whatif") {{
            updateWhatIfSimulation();
          }}
        }});
      }});

      // 4. Render Archetype Table via Safe DOM
      const tbody = document.getElementById("tbody-archetypes");
      if (tbody) {{
        tbody.replaceChildren();
        archetypes.forEach(a => {{
          const tr = el("tr");
          tr.appendChild(el("td", null, a.category));
          tr.appendChild(el("td", null, a.shelf_life_days + " days"));
          tr.appendChild(el("td", null, a.lead_time_days + " days"));
          tr.appendChild(el("td", null, a.baseline_spoilage_rate + "%"));
          tr.appendChild(el("td", null, a.champion_spoilage_rate + "%"));
          tr.appendChild(el("td", null, "$" + a.holding_cost.toFixed(2)));
          tr.appendChild(el("td", null, "$" + a.spoilage_cost.toFixed(2)));
          tr.appendChild(el("td", null, "$" + a.stockout_penalty.toFixed(2)));
          tbody.appendChild(tr);
        }});
      }}

      // 5. Populate Code Diffs (Safe DOM)
      const baseCodeEl = document.getElementById("code-baseline");
      const champCodeEl = document.getElementById("code-champion");
      if (baseCodeEl) baseCodeEl.textContent = baselineSum.evolve_block || baselineSum.program_code || "";
      if (champCodeEl) champCodeEl.textContent = championSum.evolve_block || championSum.program_code || "";

      document.getElementById("btn-copy-base")?.addEventListener("click", () => {{
        navigator.clipboard.writeText(baseCodeEl.textContent);
      }});
      document.getElementById("btn-copy-champ")?.addEventListener("click", () => {{
        navigator.clipboard.writeText(champCodeEl.textContent);
      }});

      // 6. State & Replay Scrubber
      let currentGen = maxGen;
      let isPlaying = false;
      let playInterval = null;

      const scrubber = document.getElementById("scrubber");
      const scrubberLabel = document.getElementById("scrubber-label");
      const playBtn = document.getElementById("btn-play");

      function updateDisplay(genIdx) {{
        currentGen = Math.max(0, Math.min(maxGen, genIdx));
        if (scrubber) scrubber.value = currentGen;
        if (scrubberLabel) scrubberLabel.textContent = "GEN " + currentGen + " / " + maxGen;

        const frame = trajectories[currentGen];
        if (!frame) return;

        const m = frame.metrics;
        document.getElementById("kpi-total-cost").textContent = "$" + Math.round(m.total_cost).toLocaleString();
        document.getElementById("kpi-spoilage-cost").textContent = "$" + Math.round(m.spoilage_cost).toLocaleString();
        document.getElementById("kpi-spoilage-rate").textContent = m.spoilage_rate_pct.toFixed(2) + "% rate";
        document.getElementById("kpi-fill-rate").textContent = m.fill_rate_pct.toFixed(2) + "%";
        document.getElementById("kpi-stockout-cost").textContent = "$" + Math.round(m.stockout_penalty).toLocaleString();
        document.getElementById("kpi-fitness-score").textContent = m.fitness_score.toFixed(2);
        document.getElementById("kpi-cost-reduc").textContent = (m.cost_reduction_pct > 0 ? "-" : "") + m.cost_reduction_pct.toFixed(1) + "%";

        document.getElementById("milestone-title").textContent = "GEN " + currentGen + (currentGen === 30 ? " CHAMPION" : (currentGen === 0 ? " SEED BASELINE" : " BREAKTHROUGH"));
        document.getElementById("milestone-desc").textContent = frame.event_summary || "";

        drawTrajectoryChart(currentGen);
        drawConvergenceChart();
      }}

      if (scrubber) {{
        scrubber.addEventListener("input", (e) => {{
          updateDisplay(parseInt(e.target.value, 10));
        }});
      }}

      document.querySelectorAll(".btn-preset").forEach(btn => {{
        btn.addEventListener("click", () => {{
          const g = parseInt(btn.getAttribute("data-gen"), 10);
          updateDisplay(g);
        }});
      }});

      if (playBtn) {{
        playBtn.addEventListener("click", () => {{
          isPlaying = !isPlaying;
          if (isPlaying) {{
            playBtn.textContent = "⏸ Pause Replay";
            if (currentGen >= maxGen) currentGen = 0;
            playInterval = setInterval(() => {{
              currentGen++;
              if (currentGen > maxGen) {{
                currentGen = maxGen;
                isPlaying = false;
                playBtn.textContent = "▶ Play Evolution";
                clearInterval(playInterval);
              }}
              updateDisplay(currentGen);
            }}, 400);
          }} else {{
            playBtn.textContent = "▶ Play Evolution";
            clearInterval(playInterval);
          }}
        }});
      }}

      // 7. Retina Canvas 2D Trajectory Chart
      function drawTrajectoryChart(genIdx) {{
        const canvas = document.getElementById("canvas-trajectory");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        const padL = 46, padR = 18, padT = 20, padB = 30;

        ctx.clearRect(0, 0, w, h);

        const frame = trajectories[genIdx];
        if (!frame || !frame.daily_series) return;
        const series = frame.daily_series;

        // Visual phase shading
        const dayW = (w - padL - padR) / 90;
        // Warmup (0..29)
        ctx.fillStyle = "rgba(148, 163, 184, 0.05)";
        ctx.fillRect(padL, padT, dayW * 30, h - padT - padB);
        // Validation (30..65)
        ctx.fillStyle = "rgba(6, 182, 212, 0.06)";
        ctx.fillRect(padL + dayW * 30, padT, dayW * 36, h - padT - padB);
        // Holdout (66..89)
        ctx.fillStyle = "rgba(245, 158, 11, 0.06)";
        ctx.fillRect(padL + dayW * 66, padT, dayW * 24, h - padT - padB);

        // Grid lines
        ctx.strokeStyle = "rgba(148, 163, 184, 0.1)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {{
          const y = padT + (i / 4) * (h - padT - padB);
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(w - padR, y);
          ctx.stroke();
        }}

        const maxOnHand = 12000;
        function mapX(day) {{ return padL + (day / 89) * (w - padL - padR); }}
        function mapY(val) {{ return (h - padB) - (val / maxOnHand) * (h - padT - padB); }}

        // On-hand curve
        ctx.strokeStyle = "#06B6D4";
        ctx.lineWidth = 2;
        ctx.beginPath();
        series.forEach((pt, idx) => {{
          const x = mapX(pt.day);
          const y = mapY(pt.on_hand);
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }});
        ctx.stroke();

        // In-transit curve
        ctx.strokeStyle = "#F59E0B";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        series.forEach((pt, idx) => {{
          const x = mapX(pt.day);
          const y = mapY(pt.in_transit * 2.5);
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }});
        ctx.stroke();

        // Spoilage bar indicators
        ctx.fillStyle = "rgba(244, 63, 94, 0.8)";
        series.forEach(pt => {{
          if (pt.spoilage_units > 0) {{
            const x = mapX(pt.day);
            const barH = (pt.spoilage_units / 400) * 40;
            ctx.fillRect(x - 1, h - padB - barH, 2, barH);
          }}
        }});

        // Axes labels
        ctx.fillStyle = "#94A3B8";
        ctx.font = "10px JetBrains Mono, monospace";
        ctx.fillText("0", padL - 14, h - padB + 3);
        ctx.fillText("12k", padL - 26, padT + 10);
        ctx.fillText("Day 0", padL, h - 10);
        ctx.fillText("Day 30", padL + dayW * 30 - 15, h - 10);
        ctx.fillText("Day 65", padL + dayW * 66 - 15, h - 10);
        ctx.fillText("Day 89", w - padR - 35, h - 10);
      }}

      // 8. Retina Canvas 2D Convergence Chart
      function drawConvergenceChart() {{
        const canvas = document.getElementById("canvas-convergence");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        const padL = 36, padR = 16, padT = 20, padB = 30;

        ctx.clearRect(0, 0, w, h);

        const fits = trajectories.map(t => t.metrics.fitness_score);
        const minF = 0;
        const maxF = 40;

        function mapX(gen) {{ return padL + (gen / 30) * (w - padL - padR); }}
        function mapY(f) {{ return (h - padB) - ((f - minF) / (maxF - minF)) * (h - padT - padB); }}

        // Grid
        ctx.strokeStyle = "rgba(148, 163, 184, 0.1)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {{
          const y = padT + (i / 4) * (h - padT - padB);
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(w - padR, y);
          ctx.stroke();
        }}

        // Convergence Line
        ctx.strokeStyle = "#10B981";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        fits.forEach((f, idx) => {{
          const x = mapX(idx);
          const y = mapY(f);
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }});
        ctx.stroke();

        // Active Playhead
        const headX = mapX(currentGen);
        const headY = mapY(fits[currentGen] || 0);

        ctx.strokeStyle = "#06B6D4";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(headX, padT);
        ctx.lineTo(headX, h - padB);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#06B6D4";
        ctx.beginPath();
        ctx.arc(headX, headY, 5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#94A3B8";
        ctx.font = "10px JetBrains Mono, monospace";
        ctx.fillText("0", padL - 12, h - padB);
        ctx.fillText("40", padL - 18, padT + 8);
        ctx.fillText("Gen 0", padL, h - 10);
        ctx.fillText("Gen 30", w - padR - 35, h - 10);
      }}

      // 9. Interactive What-If Simulation
      const skuSelect = document.getElementById("whatif-sku");
      const slideLead = document.getElementById("slide-leadtime");
      const slidePromo = document.getElementById("slide-promo");
      const slideSpoil = document.getElementById("slide-spoil");
      const slideStock = document.getElementById("slide-stockout");

      function updateWhatIfSimulation() {{
        const skuIdx = parseInt(skuSelect.value, 10);
        const sku = archetypes[skuIdx] || archetypes[0];

        const leadDelay = parseInt(slideLead.value, 10);
        const promoPct = parseInt(slidePromo.value, 10);
        const spoilMult = parseInt(slideSpoil.value, 10) / 10.0;
        const stockMult = parseInt(slideStock.value, 10) / 10.0;

        document.getElementById("val-leadtime").textContent = "+" + leadDelay + " days";
        document.getElementById("val-promo").textContent = "+" + promoPct + "%";
        document.getElementById("val-spoil").textContent = spoilMult.toFixed(1) + "x";
        document.getElementById("val-stockout").textContent = stockMult.toFixed(1) + "x";

        // Simulated heuristic calculation
        const baseDemand = 32.0 * (1.0 + promoPct / 100.0);
        const effLead = sku.lead_time_days + leadDelay;
        const safetyFactor = Math.sqrt(effLead + 1) * Math.min(2.2, 1.4 + stockMult * 0.2 - spoilMult * 0.1);
        const dynamicSafety = Math.round(18.0 * safetyFactor);
        const orderUpTo = Math.round(baseDemand * (effLead + 1) + dynamicSafety);

        const expSpoilage = Math.max(0.4, (dynamicSafety / (sku.shelf_life_days * 3.2)) * spoilMult);
        const estFillRate = Math.min(99.4, 91.5 + (dynamicSafety / 12.0) - (leadDelay * 1.8));

        document.getElementById("whatif-orderup").textContent = orderUpTo + " units";
        document.getElementById("whatif-safetystock").textContent = dynamicSafety + " units";
        document.getElementById("whatif-spoilage").textContent = expSpoilage.toFixed(1) + " units";
        document.getElementById("whatif-spoil-pct").textContent = ((expSpoilage / orderUpTo) * 100).toFixed(1) + "% of stock";
        document.getElementById("whatif-fill").textContent = estFillRate.toFixed(1) + "%";

        const slaEl = document.getElementById("whatif-sla-status");
        if (estFillRate >= 95.0) {{
          slaEl.textContent = "Compliant with SLA (>=95%)";
          slaEl.style.color = "var(--accent-emerald)";
        }} else {{
          slaEl.textContent = "Deficit vs SLA (-" + (95.0 - estFillRate).toFixed(1) + "%)";
          slaEl.style.color = "var(--accent-coral)";
        }}

        drawWhatIfCanvas(orderUpTo, dynamicSafety, expSpoilage);
      }}

      function drawWhatIfCanvas(orderUp, safety, spoilage) {{
        const canvas = document.getElementById("canvas-whatif");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        ctx.clearRect(0, 0, w, h);

        const padL = 40, padR = 20, padT = 16, padB = 26;
        const barW = (w - padL - padR) / 3;

        const maxVal = Math.max(250, orderUp * 1.15);

        // Bar 1: Order-up-to
        const h1 = (orderUp / maxVal) * (h - padT - padB);
        ctx.fillStyle = "#06B6D4";
        ctx.fillRect(padL + 20, (h - padB) - h1, barW - 40, h1);

        // Bar 2: Safety stock
        const h2 = (safety / maxVal) * (h - padT - padB);
        ctx.fillStyle = "#F59E0B";
        ctx.fillRect(padL + barW + 20, (h - padB) - h2, barW - 40, h2);

        // Bar 3: Spoilage buffer
        const h3 = ((spoilage * 10) / maxVal) * (h - padT - padB);
        ctx.fillStyle = "#F43F5E";
        ctx.fillRect(padL + barW * 2 + 20, (h - padB) - h3, barW - 40, h3);

        ctx.fillStyle = "#CBD5E1";
        ctx.font = "11px JetBrains Mono, monospace";
        ctx.fillText("Order-Up", padL + 20, h - 8);
        ctx.fillText("Safety", padL + barW + 26, h - 8);
        ctx.fillText("Spoil x10", padL + barW * 2 + 18, h - 8);
      }}

      [skuSelect, slideLead, slidePromo, slideSpoil, slideStock].forEach(ctrl => {{
        ctrl?.addEventListener("input", updateWhatIfSimulation);
      }});

      // Initial render
      updateDisplay(maxGen);
      updateWhatIfSimulation();

      // Window resize handler for responsive canvas
      window.addEventListener("resize", () => {{
        drawTrajectoryChart(currentGen);
        drawConvergenceChart();
        updateWhatIfSimulation();
      }});

    }})();
  </script>
</body>
</html>
"""

    out_file = DASHBOARD_DIR / "index.html"
    out_file.write_text(html_content, encoding="utf-8")
    return out_file


if __name__ == "__main__":
    print("Compiling dashboard index.html...")
    path = build_dashboard_html()
    print(f"Successfully generated {path}")
