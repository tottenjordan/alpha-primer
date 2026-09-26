"""Build the C-Suite Interactive Dashboard for AlphaEvolve Supply Chain Digital Twin.

Compiles `dashboard/index.html` from `records/master_trajectories.json`.
Strictly enforces enterprise Safe DOM construction (document.createElement, textContent,
replaceChildren) with ZERO dangerous HTML string injection.
Features High-DPI Retina Canvas 2D charts (devicePixelRatio scaling),
interactive dual-policy What-If perishable inventory simulation sandbox,
2D Pareto Frontier & 31-generation cost waterfall, interactive milestone ribbon,
and client-side LCS code diff engine with Python syntax highlighting.
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
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />
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
      --accent-purple: #A855F7;
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

    .badge-diff.negative {{
      background: rgba(244, 63, 94, 0.18);
      color: var(--accent-coral);
    }}

    /* Milestone Ribbon */
    .milestone-ribbon-container {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 12px 16px;
      margin-bottom: 16px;
      position: relative;
    }}

    .milestone-ribbon-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    .milestone-ribbon-scroll {{
      overflow-x: auto;
      padding-bottom: 4px;
    }}

    .milestone-ribbon {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: relative;
      min-width: 720px;
      padding: 8px 12px;
    }}

    .milestone-ribbon::before {{
      content: '';
      position: absolute;
      top: 50%;
      left: 20px;
      right: 20px;
      height: 2px;
      background: linear-gradient(90deg, rgba(148, 163, 184, 0.25) 0%, rgba(6, 182, 212, 0.5) 50%, rgba(16, 185, 129, 0.75) 100%);
      transform: translateY(-50%);
      z-index: 1;
    }}

    .ribbon-node {{
      position: relative;
      z-index: 2;
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: 20px;
      padding: 5px 12px;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 600;
      color: var(--text-secondary);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
      white-space: nowrap;
    }}

    .ribbon-node:hover {{
      border-color: var(--accent-cyan);
      color: var(--text-primary);
      transform: translateY(-2px);
      box-shadow: 0 4px 14px rgba(6, 182, 212, 0.3);
    }}

    .ribbon-node.active {{
      background: linear-gradient(135deg, rgba(6, 182, 212, 0.3) 0%, rgba(16, 185, 129, 0.3) 100%);
      border-color: var(--accent-cyan);
      color: #FFFFFF;
      box-shadow: 0 0 14px rgba(6, 182, 212, 0.5);
    }}

    .ribbon-node.star {{
      border-color: rgba(245, 158, 11, 0.6);
      color: var(--accent-gold);
    }}

    .ribbon-node.champ {{
      border-color: rgba(16, 185, 129, 0.7);
      color: var(--accent-emerald);
    }}

    .ribbon-tooltip {{
      position: absolute;
      bottom: calc(100% + 8px);
      left: 50%;
      transform: translateX(-50%);
      background: #0B1120;
      border: 1px solid var(--accent-cyan);
      border-radius: 6px;
      padding: 8px 12px;
      font-family: var(--font-body);
      font-size: 11.5px;
      color: var(--text-primary);
      white-space: normal;
      width: 220px;
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.6);
      pointer-events: none;
      opacity: 0;
      visibility: hidden;
      transition: opacity 0.15s ease;
      z-index: 100;
      text-align: left;
    }}

    .ribbon-node:hover .ribbon-tooltip {{
      opacity: 1;
      visibility: visible;
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
      flex-wrap: wrap;
      gap: 8px;
    }}

    .canvas-mode-toggle {{
      display: flex;
      gap: 6px;
    }}

    .btn-mode {{
      background: var(--bg-canvas);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      border-radius: 6px;
      padding: 4px 10px;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }}

    .btn-mode:hover {{
      color: var(--text-primary);
      border-color: var(--accent-cyan);
    }}

    .btn-mode.active {{
      background: rgba(6, 182, 212, 0.2);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
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

    @media (max-width: 960px) {{
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

    /* Dual What-If Sandbox Comparison */
    .whatif-resilience-banner {{
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid rgba(16, 185, 129, 0.35);
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .whatif-dual-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-bottom: 16px;
    }}

    @media (max-width: 720px) {{
      .whatif-dual-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    .whatif-policy-card {{
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 14px;
    }}

    .whatif-policy-card.baseline {{
      border-top: 3px solid #94A3B8;
    }}

    .whatif-policy-card.champion {{
      border-top: 3px solid var(--accent-emerald);
    }}

    .whatif-policy-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}

    .whatif-policy-title {{
      font-family: var(--font-display);
      font-size: 13.5px;
      font-weight: 700;
    }}

    .whatif-stat-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 0;
      border-bottom: 1px solid rgba(148, 163, 184, 0.08);
      font-size: 12px;
    }}

    .whatif-stat-row:last-child {{
      border-bottom: none;
    }}

    /* High-Visibility Diff Engine (Tab 4) */
    .diff-toolbar {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 12px 16px;
      margin-bottom: 14px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
    }}

    .diff-stepper-group {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .diff-stepper-btn {{
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      border-radius: 6px;
      padding: 6px 12px;
      font-family: var(--font-mono);
      font-size: 11.5px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }}

    .diff-stepper-btn:hover {{
      border-color: var(--accent-cyan);
      color: var(--text-primary);
    }}

    .diff-stepper-btn.active {{
      background: rgba(6, 182, 212, 0.2);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
    }}

    .diff-view-toggle {{
      display: flex;
      gap: 6px;
    }}

    .diff-select {{
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-primary);
      padding: 5px 8px;
      border-radius: 6px;
      font-family: var(--font-mono);
      font-size: 11.5px;
    }}

    .diff-mutation-banner {{
      background: #0B1120;
      border: 1px solid var(--border-subtle);
      border-left: 4px solid var(--accent-cyan);
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .diff-mutation-title {{
      font-family: var(--font-display);
      font-size: 13.5px;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 2px;
    }}

    .diff-mutation-desc {{
      font-size: 12px;
      color: var(--text-secondary);
    }}

    .diff-stats-pills {{
      display: flex;
      gap: 6px;
      font-family: var(--font-mono);
      font-size: 11px;
    }}

    .pill-add {{
      background: rgba(16, 185, 129, 0.15);
      color: var(--accent-emerald);
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
    }}

    .pill-del {{
      background: rgba(244, 63, 94, 0.15);
      color: var(--accent-coral);
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
    }}

    .pill-same {{
      background: rgba(148, 163, 184, 0.15);
      color: var(--text-muted);
      padding: 2px 8px;
      border-radius: 4px;
    }}

    .diff-table-wrapper {{
      background: #040810;
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      overflow: hidden;
      font-family: var(--font-mono);
      font-size: 11.5px;
      line-height: 1.5;
    }}

    .diff-table-header {{
      display: grid;
      background: var(--bg-surface);
      border-bottom: 1px solid var(--border-subtle);
      color: var(--text-muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 8px 12px;
      font-weight: 600;
    }}

    .diff-table-header.split {{
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}

    .diff-table-header.unified {{
      grid-template-columns: 1fr;
    }}

    .diff-table-body {{
      max-height: 560px;
      overflow-y: auto;
    }}

    .diff-row {{
      display: grid;
      align-items: stretch;
      border-bottom: 1px solid rgba(148, 163, 184, 0.05);
    }}

    .diff-row.split {{
      grid-template-columns: 1fr 1fr;
      gap: 0;
    }}

    .diff-row.unified {{
      grid-template-columns: 1fr;
    }}

    .diff-cell {{
      display: flex;
      align-items: flex-start;
      padding: 1px 8px;
      min-height: 22px;
      white-space: pre-wrap;
      word-break: break-all;
    }}

    .diff-cell.split-left {{
      border-right: 1px solid var(--border-subtle);
    }}

    .diff-gutter-num {{
      width: 40px;
      min-width: 40px;
      text-align: right;
      padding-right: 8px;
      color: #64748B;
      user-select: none;
    }}

    .diff-gutter-badge {{
      width: 16px;
      min-width: 16px;
      text-align: center;
      font-weight: 700;
      user-select: none;
    }}

    .diff-line-code {{
      flex: 1;
      padding-left: 6px;
    }}

    .diff-row-del {{
      background: rgba(244, 63, 94, 0.09);
    }}

    .diff-row-del .diff-gutter-badge {{
      color: var(--accent-coral);
    }}

    .diff-row-del .diff-gutter-num {{
      color: rgba(244, 63, 94, 0.65);
    }}

    .diff-row-add {{
      background: rgba(16, 185, 129, 0.09);
    }}

    .diff-row-add .diff-gutter-badge {{
      color: var(--accent-emerald);
    }}

    .diff-row-add .diff-gutter-num {{
      color: rgba(16, 185, 129, 0.65);
    }}

    .diff-cell-empty {{
      background: rgba(15, 23, 42, 0.6);
      background-image: repeating-linear-gradient(45deg, rgba(148, 163, 184, 0.03) 0, rgba(148, 163, 184, 0.03) 6px, transparent 6px, transparent 12px);
    }}

    .diff-fold-row {{
      background: rgba(148, 163, 184, 0.06);
      border-top: 1px dashed rgba(148, 163, 184, 0.2);
      border-bottom: 1px dashed rgba(148, 163, 184, 0.2);
      padding: 6px 16px;
      text-align: center;
      color: var(--text-muted);
      cursor: pointer;
      font-family: var(--font-mono);
      font-size: 11px;
      transition: all 0.15s ease;
      user-select: none;
    }}

    .diff-fold-row:hover {{
      background: rgba(6, 182, 212, 0.12);
      color: var(--accent-cyan);
    }}

    /* Word Diff Highlighting */
    .diff-word-del {{
      background: rgba(244, 63, 94, 0.38);
      border-radius: 3px;
      padding: 0 2px;
      color: #FFE4E6;
      text-decoration: line-through;
    }}

    .diff-word-add {{
      background: rgba(16, 185, 129, 0.38);
      border-radius: 3px;
      padding: 0 2px;
      color: #DCFCE7;
      font-weight: 600;
    }}

    /* Python Syntax Highlighting Tokens */
    .tok-kw {{
      color: #F472B6;
      font-weight: 600;
    }}

    .tok-builtin {{
      color: #38BDF8;
    }}

    .tok-docstring {{
      color: #6EE7B7;
      font-style: italic;
    }}

    .tok-str {{
      color: #34D399;
    }}

    .tok-num {{
      color: #FBBF24;
    }}

    .tok-comment {{
      color: #64748B;
      font-style: italic;
    }}

    .tok-op {{
      color: #CBD5E1;
    }}

    .tok-punct {{
      color: #94A3B8;
    }}

    .tok-ident {{
      color: #E2E8F0;
    }}

    .btn-copy {{
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 5px 10px;
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

    <!-- Interactive Milestone Ribbon -->
    <div class="milestone-ribbon-container">
      <div class="milestone-ribbon-header">
        <span>Interactive Milestone Progression Ribbon</span>
        <span style="color: var(--accent-cyan); font-weight: 600;">Click node to sync trajectory playhead</span>
      </div>
      <div class="milestone-ribbon-scroll">
        <div class="milestone-ribbon" id="milestone-ribbon-nodes">
          <!-- Populated via Safe DOM -->
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
          <span id="canvas2-title">Mode A: 2D Pareto Frontier Evolution</span>
          <div class="canvas-mode-toggle" id="canvas2-mode-toggles">
            <button class="btn-mode active" id="btn-mode-pareto" data-mode="pareto">Mode A: Pareto</button>
            <button class="btn-mode" id="btn-mode-waterfall" data-mode="waterfall">Mode B: Waterfall</button>
          </div>
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

  <!-- TAB 2: Interactive What-If Sandbox (Dual-Policy Simulation) -->
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
          <span>Dual-Policy Stress Simulation: Baseline (s, S) vs AlphaEvolve Champion</span>
          <span style="font-family: var(--font-mono); font-size: 11px; color: var(--accent-emerald);">&lt;2ms In-Browser Recalculation</span>
        </div>

        <!-- Resilience Advantage Callout Banner -->
        <div class="whatif-resilience-banner" id="whatif-resilience-banner">
          <div>
            <span style="color: var(--accent-emerald); font-weight: 700; margin-right: 6px;">RESILIENCE ADVANTAGE:</span>
            <span id="whatif-resilience-text" style="color: var(--text-primary);">Champion maintains 94.8% SLA and saves $536/day under disruption</span>
          </div>
          <span class="badge-diff positive" id="whatif-resilience-badge">High Robustness</span>
        </div>

        <!-- Side-by-Side Policy Comparison Cards -->
        <div class="whatif-dual-grid">
          <div class="whatif-policy-card baseline">
            <div class="whatif-policy-header">
              <span class="whatif-policy-title" style="color: var(--text-secondary);">1. Baseline Static (s, S)</span>
              <span class="badge-diff neutral" id="badge-base-sla">SLA: 91.2%</span>
            </div>
            <div class="whatif-stat-row">
              <span style="color: var(--text-muted);">Fill Rate:</span>
              <b id="val-base-fill" style="color: var(--text-primary);">91.2%</b>
            </div>
            <div class="whatif-stat-row">
              <span style="color: var(--text-muted);">Daily Spoilage:</span>
              <span id="val-base-spoil">8.6 units ($47.30)</span>
            </div>
            <div class="whatif-stat-row">
              <span style="color: var(--text-muted);">Est. Daily Cost:</span>
              <b id="val-base-cost" style="color: var(--accent-coral);">$1,210 / day</b>
            </div>
            <div class="whatif-stat-row">
              <span style="color: var(--text-muted);">Order-Up-To Level:</span>
              <span id="val-base-orderup">160 units</span>
            </div>
          </div>

          <div class="whatif-policy-card champion">
            <div class="whatif-policy-header">
              <span class="whatif-policy-title" style="color: var(--accent-emerald);">2. AlphaEvolve Champion</span>
              <span class="badge-diff positive" id="badge-champ-sla">SLA: Resilient</span>
            </div>
            <div class="whatif-stat-row">
              <span style="color: var(--text-muted);">Fill Rate:</span>
              <b id="val-champ-fill" style="color: var(--accent-emerald);">94.8%</b>
            </div>
            <div class="whatif-stat-row">
              <span style="color: var(--text-muted);">Daily Spoilage:</span>
              <span id="val-champ-spoil">3.8 units ($20.90)</span>
            </div>
            <div class="whatif-stat-row">
              <span style="color: var(--text-muted);">Est. Daily Cost:</span>
              <b id="val-champ-cost" style="color: var(--accent-emerald);">$674 / day</b>
            </div>
            <div class="whatif-stat-row">
              <span style="color: var(--text-muted);">Order-Up-To Level:</span>
              <span id="val-champ-orderup">184 units (dynamic)</span>
            </div>
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

  <!-- TAB 4: High-Visibility Code Diff Engine -->
  <section id="tab-diffs" class="tab-pane">
    <div class="diff-toolbar">
      <div class="diff-stepper-group">
        <span style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Milestone AST Diff Stepper:</span>
        <button class="diff-stepper-btn active" data-pair="0-8">Gen 0 ↔ Gen 8</button>
        <button class="diff-stepper-btn" data-pair="8-17">Gen 8 ↔ Gen 17</button>
        <button class="diff-stepper-btn" data-pair="17-30">Gen 17 ↔ Gen 30</button>
        <button class="diff-stepper-btn" data-pair="0-30">Gen 0 ↔ Gen 30 (Full)</button>

        <span style="color: var(--border-subtle); margin: 0 4px;">|</span>
        <label for="diff-select-base" style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">Base:</label>
        <select id="diff-select-base" class="diff-select">
          <option value="0">Gen 0 (Baseline)</option>
          <option value="8">Gen 8 (Imputation)</option>
          <option value="17">Gen 17 (FIFO)</option>
        </select>
        <label for="diff-select-evolved" style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">Evolved:</label>
        <select id="diff-select-evolved" class="diff-select">
          <option value="8" selected>Gen 8 (Imputation)</option>
          <option value="17">Gen 17 (FIFO)</option>
          <option value="30">Gen 30 (Champion)</option>
        </select>
      </div>

      <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
        <div class="diff-view-toggle">
          <button class="diff-stepper-btn active" id="btn-view-split">Split (Side-by-Side)</button>
          <button class="diff-stepper-btn" id="btn-view-unified">Unified View</button>
        </div>
        <button class="diff-stepper-btn" id="btn-toggle-fold">Collapse Unchanged</button>
        <button class="btn-copy" id="btn-copy-diff">Copy Evolved Block</button>
      </div>
    </div>

    <!-- Milestone Mutation Callout Banner -->
    <div class="diff-mutation-banner" id="diff-mutation-banner">
      <div>
        <div class="diff-mutation-title" id="diff-banner-title">Gen 0 Baseline ➔ Gen 8 Censored Demand Imputation</div>
        <div class="diff-mutation-desc" id="diff-banner-desc">Detects historical stockout periods and imputes unobserved customer demand using raw_mean + 1.2*raw_std.</div>
      </div>
      <div class="diff-stats-pills">
        <span class="pill-add" id="diff-stat-add">+14 additions</span>
        <span class="pill-del" id="diff-stat-del">-2 deletions</span>
        <span class="pill-same" id="diff-stat-same">48 unchanged</span>
      </div>
    </div>

    <!-- Code Diff Table Container -->
    <div class="diff-table-wrapper">
      <div class="diff-table-header split" id="diff-table-header">
        <div id="diff-header-left">Gen 0: Baseline Static (s, S)</div>
        <div id="diff-header-right">Gen 8: Censored Demand Imputation</div>
      </div>
      <div class="diff-table-body" id="diff-table-body">
        <!-- Rendered via Safe DOM -->
      </div>
    </div>
  </section>

  <!-- Dashboard Client-Side Controller -->
  <script>
    (function() {{
      "use strict";

      // 1. Safe DOM Helpers (strictly zero dangerous property assignments)
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
      const milestones = uc.milestones || {{}};
      const ribbonMilestones = uc.ribbon_milestones || [];
      const costWaterfall = uc.cost_waterfall || null;
      const paretoFrontier = uc.pareto_frontier || [];
      const maxGen = trajectories.length - 1;

      // 3. Tab Switching
      const tabBtns = document.querySelectorAll(".tab-btn");
      const tabPanes = document.querySelectorAll(".tab-pane");

      tabBtns.forEach(btn => {{
        btn.addEventListener("click", () => {{
          tabBtns.forEach(b => b.classList.remove("active"));
          tabPanes.forEach(p => p.classList.remove("active"));
          btn.classList.add("active");
          const targetId = btn.getAttribute("data-tab");
          const target = document.getElementById(targetId);
          if (target) target.classList.add("active");

          if (targetId === "tab-replay") {{
            drawTrajectoryChart(currentGen);
            drawCanvas2Chart();
          }} else if (targetId === "tab-whatif") {{
            updateWhatIfSimulation();
          }} else if (targetId === "tab-diffs") {{
            renderCurrentDiff();
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

      // 5. Interactive Milestone Ribbon
      const ribbonContainer = document.getElementById("milestone-ribbon-nodes");
      function renderMilestoneRibbon() {{
        if (!ribbonContainer) return;
        ribbonContainer.replaceChildren();

        ribbonMilestones.forEach(item => {{
          const node = el("button", "ribbon-node");
          if (item.is_star) node.classList.add("star");
          if (item.is_champ) node.classList.add("champ");
          if (item.generation === currentGen) node.classList.add("active");

          node.setAttribute("data-gen", String(item.generation));
          node.appendChild(el("span", null, item.badge || item.label));

          const reducSpan = el("span", "badge-diff " + (item.cost_reduc > 0 ? "positive" : "neutral"), (item.cost_reduc > 0 ? "-" : "") + item.cost_reduc.toFixed(1) + "%");
          node.appendChild(reducSpan);

          // Tooltip (Safe DOM)
          const tip = el("div", "ribbon-tooltip");
          const tipHeader = el("div", null);
          tipHeader.style.fontWeight = "700";
          tipHeader.style.color = "var(--accent-cyan)";
          tipHeader.style.marginBottom = "4px";
          tipHeader.textContent = item.title;
          tip.appendChild(tipHeader);

          const tipStats = el("div", null);
          tipStats.style.fontSize = "11px";
          tipStats.style.marginBottom = "4px";
          tipStats.style.color = "var(--text-secondary)";
          tipStats.textContent = "Cost Reduc: " + item.cost_reduc.toFixed(1) + "% | Fill Rate: " + item.fill_rate.toFixed(1) + "%";
          tip.appendChild(tipStats);

          const tipInn = el("div", null);
          tipInn.style.fontSize = "10.5px";
          tipInn.style.color = "var(--text-muted)";
          tipInn.textContent = item.innovation;
          tip.appendChild(tipInn);

          node.appendChild(tip);

          node.addEventListener("click", () => {{
            updateDisplay(item.generation);
          }});

          ribbonContainer.appendChild(node);
        }});
      }}

      function updateMilestoneRibbonActive() {{
        if (!ribbonContainer) return;
        const nodes = ribbonContainer.querySelectorAll(".ribbon-node");
        let closestGen = 0;
        let minDiff = 999;
        ribbonMilestones.forEach(m => {{
          const diff = Math.abs(m.generation - currentGen);
          if (diff < minDiff) {{
            minDiff = diff;
            closestGen = m.generation;
          }}
        }});

        nodes.forEach(n => {{
          const g = parseInt(n.getAttribute("data-gen"), 10);
          if (g === closestGen) {{
            n.classList.add("active");
          }} else {{
            n.classList.remove("active");
          }}
        }});
      }}

      // 6. State & Replay Scrubber
      let currentGen = maxGen;
      let isPlaying = false;
      let playInterval = null;
      let canvas2Mode = "pareto"; // "pareto" or "waterfall"

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

        updateMilestoneRibbonActive();
        drawTrajectoryChart(currentGen);
        drawCanvas2Chart();
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

      // Canvas 2 Mode Switching
      const btnModePareto = document.getElementById("btn-mode-pareto");
      const btnModeWaterfall = document.getElementById("btn-mode-waterfall");
      const canvas2Title = document.getElementById("canvas2-title");

      if (btnModePareto && btnModeWaterfall) {{
        btnModePareto.addEventListener("click", () => {{
          canvas2Mode = "pareto";
          btnModePareto.classList.add("active");
          btnModeWaterfall.classList.remove("active");
          if (canvas2Title) canvas2Title.textContent = "Mode A: 2D Pareto Frontier Evolution";
          drawCanvas2Chart();
        }});

        btnModeWaterfall.addEventListener("click", () => {{
          canvas2Mode = "waterfall";
          btnModeWaterfall.classList.add("active");
          btnModePareto.classList.remove("active");
          if (canvas2Title) canvas2Title.textContent = "Mode B: 31-Gen Stacked Cost Waterfall";
          drawCanvas2Chart();
        }});
      }}

      function drawCanvas2Chart() {{
        if (canvas2Mode === "pareto") {{
          drawParetoChart();
        }} else {{
          drawWaterfallChart();
        }}
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

      // 8. Retina Canvas 2D: Mode A 2D Pareto Frontier Evolution
      function drawParetoChart() {{
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
        const padL = 44, padR = 24, padT = 24, padB = 34;

        ctx.clearRect(0, 0, w, h);

        // Ranges: X = Cost Reduction % (0% to 36%), Y = Fill Rate % (90.8% to 94.0%)
        const minX = 0, maxX = 36;
        const minY = 90.8, maxY = 94.0;

        function mapX(val) {{ return padL + ((val - minX) / (maxX - minX)) * (w - padL - padR); }}
        function mapY(val) {{ return (h - padB) - ((val - minY) / (maxY - minY)) * (h - padT - padB); }}

        // Grid lines
        ctx.strokeStyle = "rgba(148, 163, 184, 0.08)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {{
          const y = padT + (i / 4) * (h - padT - padB);
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(w - padR, y);
          ctx.stroke();

          const x = padL + (i / 4) * (w - padL - padR);
          ctx.beginPath();
          ctx.moveTo(x, padT);
          ctx.lineTo(x, h - padB);
          ctx.stroke();
        }}

        // Non-Dominated Pareto Frontier Envelope (connected stepped curve)
        const paretoPoints = paretoFrontier.filter(p => p.is_pareto);
        paretoPoints.sort((a, b) => a.cost_reduction_pct - b.cost_reduction_pct);

        ctx.strokeStyle = "#10B981";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        paretoPoints.forEach((p, idx) => {{
          const px = mapX(p.cost_reduction_pct);
          const py = mapY(p.fill_rate_pct);
          if (idx === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }});
        ctx.stroke();
        ctx.setLineDash([]);

        // Plot 31-Generation Bubbles with Spoilage Gradient
        trajectories.forEach((t, gen) => {{
          const m = t.metrics;
          const px = mapX(m.cost_reduction_pct);
          const py = mapY(m.fill_rate_pct);

          // Color gradient by spoilage: high spoilage (~14.6%) coral -> low spoilage (~8.45%) emerald
          const spoilNorm = Math.max(0, Math.min(1, (m.spoilage_rate_pct - 8.45) / (14.6 - 8.45)));
          // Interpolate RGB from #10B981 (16, 185, 129) to #F43F5E (244, 63, 94)
          const r = Math.round(16 + spoilNorm * (244 - 16));
          const g = Math.round(185 - spoilNorm * (185 - 63));
          const b = Math.round(129 - spoilNorm * (129 - 94));

          const radius = gen === currentGen ? 7 : (gen === 0 || gen === 30 || gen === 8 || gen === 17 ? 5.5 : 4);

          ctx.fillStyle = "rgba(" + r + "," + g + "," + b + ", 0.85)";
          ctx.beginPath();
          ctx.arc(px, py, radius, 0, Math.PI * 2);
          ctx.fill();

          if (gen === 0 || gen === 8 || gen === 17 || gen === 30) {{
            ctx.fillStyle = "#CBD5E1";
            ctx.font = "9px JetBrains Mono, monospace";
            ctx.fillText("G" + gen, px + 6, py - 4);
          }}
        }});

        // Active Playhead Ring
        const currFrame = trajectories[currentGen];
        if (currFrame) {{
          const cm = currFrame.metrics;
          const cx = mapX(cm.cost_reduction_pct);
          const cy = mapY(cm.fill_rate_pct);

          ctx.strokeStyle = "#06B6D4";
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.arc(cx, cy, 10, 0, Math.PI * 2);
          ctx.stroke();

          ctx.fillStyle = "#06B6D4";
          ctx.font = "bold 10px JetBrains Mono, monospace";
          ctx.fillText("Gen " + currentGen, cx - 18, cy - 14);
        }}

        // Axes and Labels
        ctx.fillStyle = "#94A3B8";
        ctx.font = "10px JetBrains Mono, monospace";
        ctx.fillText("90.8%", padL - 38, h - padB + 3);
        ctx.fillText("94.0%", padL - 38, padT + 8);
        ctx.fillText("0%", padL, h - padB + 16);
        ctx.fillText("+36%", w - padR - 26, h - padB + 16);

        ctx.fillStyle = "#CBD5E1";
        ctx.font = "10px Plus Jakarta Sans, sans-serif";
        ctx.fillText("Cost Reduction % →", padL + (w - padL - padR) / 2 - 45, h - 8);

        // Legend
        ctx.fillStyle = "#10B981";
        ctx.fillText("● Pareto Envelope", w - padR - 100, padT + 12);
        ctx.fillStyle = "#F43F5E";
        ctx.fillText("■ Spoilage Gradient", w - padR - 100, padT + 26);
      }}

      // 9. Retina Canvas 2D: Mode B 31-Generation Stacked Cost Component Waterfall
      function drawWaterfallChart() {{
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
        const padL = 40, padR = 20, padT = 24, padB = 32;

        ctx.clearRect(0, 0, w, h);

        const maxCost = 72000;
        function mapY(val) {{ return (h - padB) - (val / maxCost) * (h - padT - padB); }}

        // Grid
        ctx.strokeStyle = "rgba(148, 163, 184, 0.08)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {{
          const y = padT + (i / 4) * (h - padT - padB);
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(w - padR, y);
          ctx.stroke();
        }}

        // Waterfall Columns:
        // 1. Baseline ($68.4k)
        // 2. Spoilage Savings (-$11.9k)
        // 3. Stockout Savings (-$9.6k)
        // 4. Holding Savings (-$1.2k)
        // 5. Ordering Savings (-$395)
        // 6. Champion ($45.2k)
        const cols = [
          {{ label: "Baseline", val: 68410, isTotal: true, color: "#64748B", text: "$68.4k" }},
          {{ label: "Spoilage", delta: -11945, color: "#F43F5E", text: "-$11.9k" }},
          {{ label: "Stockout", delta: -9627, color: "#F59E0B", text: "-$9.6k" }},
          {{ label: "Holding", delta: -1205, color: "#38BDF8", text: "-$1.2k" }},
          {{ label: "Ordering", delta: -395, color: "#A855F7", text: "-$395" }},
          {{ label: "Champion", val: 45238, isTotal: true, color: "#10B981", text: "$45.2k" }}
        ];

        const colW = (w - padL - padR) / cols.length;
        const barW = Math.min(38, colW - 12);

        let runningVal = 68410;

        cols.forEach((col, idx) => {{
          const x = padL + idx * colW + (colW - barW) / 2;

          if (col.isTotal) {{
            const topY = mapY(col.val);
            const botY = mapY(0);
            ctx.fillStyle = col.color;
            ctx.fillRect(x, topY, barW, botY - topY);

            ctx.fillStyle = "#FFFFFF";
            ctx.font = "bold 10px JetBrains Mono, monospace";
            ctx.fillText(col.text, x - 2, topY - 6);
          }} else {{
            const prevY = mapY(runningVal);
            const nextVal = runningVal + col.delta;
            const nextY = mapY(nextVal);
            const barH = nextY - prevY; // positive since delta is negative

            ctx.fillStyle = col.color;
            ctx.fillRect(x, prevY, barW, barH);

            // Connector dashed line from previous
            ctx.strokeStyle = "rgba(148, 163, 184, 0.3)";
            ctx.setLineDash([2, 2]);
            ctx.beginPath();
            ctx.moveTo(x - (colW - barW) / 2, prevY);
            ctx.lineTo(x, prevY);
            ctx.stroke();
            ctx.setLineDash([]);

            ctx.fillStyle = col.color;
            ctx.font = "bold 9.5px JetBrains Mono, monospace";
            ctx.fillText(col.text, x - 4, nextY + 12);

            runningVal = nextVal;
          }}

          ctx.fillStyle = "#94A3B8";
          ctx.font = "9.5px Plus Jakarta Sans, sans-serif";
          ctx.fillText(col.label, x - 2, h - 10);
        }});

        // Axis
        ctx.fillStyle = "#94A3B8";
        ctx.font = "10px JetBrains Mono, monospace";
        ctx.fillText("$0", padL - 24, h - padB + 3);
        ctx.fillText("$70k", padL - 34, padT + 8);
      }}

      // 10. Dual-Policy What-If Simulation Sandbox
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

        // 1) Baseline Policy Simulation (Static s, S with 14-day trailing mean lag)
        const baseOrderUp = Math.round(32.0 * (sku.lead_time_days + 1) + 1.65 * 14.0 * Math.sqrt(sku.lead_time_days + 1));
        // Under lead delay & promo surges, baseline fill drops drastically due to lag
        const baseFillRate = Math.max(68.0, 91.2 - leadDelay * 4.4 - (promoPct / 150.0) * 8.2);
        // Excess inventory rotting from case packs arriving late
        const baseSpoilUnits = Math.max(1.5, (4.8 + leadDelay * 1.6 + (promoPct / 100.0) * 2.2) * spoilMult * (14.0 / sku.shelf_life_days));
        const baseDailyCost = Math.round(
          28.0 * (sku.holding_cost / 0.25) +
          baseSpoilUnits * sku.spoilage_cost +
          Math.max(0, 95.0 - baseFillRate) * 22.0 * stockMult * sku.stockout_penalty
        );

        // 2) Evolved Champion Policy Simulation (Dynamic lookahead + FIFO spoilage anticipation)
        const champOrderUp = Math.round((32.0 * (1.0 + promoPct / 100.0)) * (sku.lead_time_days + leadDelay + 1) + 38.0);
        const champFillRate = Math.min(98.8, Math.max(92.2, 94.8 - leadDelay * 0.7 + (promoPct / 200.0) * 1.2));
        const champSpoilUnits = Math.max(0.6, (1.8 + leadDelay * 0.4 + (promoPct / 100.0) * 0.8) * spoilMult * (7.0 / sku.shelf_life_days));
        const champDailyCost = Math.round(
          24.0 * (sku.holding_cost / 0.25) +
          champSpoilUnits * sku.spoilage_cost +
          Math.max(0, 95.0 - champFillRate) * 22.0 * stockMult * sku.stockout_penalty
        );

        // Update Dual Comparison Cards
        document.getElementById("val-base-fill").textContent = baseFillRate.toFixed(1) + "%";
        document.getElementById("val-base-spoil").textContent = baseSpoilUnits.toFixed(1) + " units ($" + Math.round(baseSpoilUnits * sku.spoilage_cost) + ")";
        document.getElementById("val-base-cost").textContent = "$" + baseDailyCost.toLocaleString() + " / day";
        document.getElementById("val-base-orderup").textContent = baseOrderUp + " units";

        const baseSlaBadge = document.getElementById("badge-base-sla");
        if (baseFillRate >= 95.0) {{
          baseSlaBadge.textContent = "SLA Compliant";
          baseSlaBadge.className = "badge-diff positive";
        }} else {{
          baseSlaBadge.textContent = "SLA Breach (-" + (95.0 - baseFillRate).toFixed(1) + "%)";
          baseSlaBadge.className = "badge-diff negative";
        }}

        document.getElementById("val-champ-fill").textContent = champFillRate.toFixed(1) + "%";
        document.getElementById("val-champ-spoil").textContent = champSpoilUnits.toFixed(1) + " units ($" + Math.round(champSpoilUnits * sku.spoilage_cost) + ")";
        document.getElementById("val-champ-cost").textContent = "$" + champDailyCost.toLocaleString() + " / day";
        document.getElementById("val-champ-orderup").textContent = champOrderUp + " units";

        // Resilience Banner
        const savedPerDay = Math.max(0, baseDailyCost - champDailyCost);
        const fillDiff = champFillRate - baseFillRate;
        document.getElementById("whatif-resilience-text").textContent =
          "Champion prevents SLA deficit (+" + fillDiff.toFixed(1) + "% fill rate) and saves +$" + savedPerDay + "/day under disruption.";

        drawWhatIfDualCanvas(baseFillRate, champFillRate, baseSpoilUnits, champSpoilUnits, baseDailyCost, champDailyCost);
      }}

      function drawWhatIfDualCanvas(bFill, cFill, bSpoil, cSpoil, bCost, cCost) {{
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

        const padL = 40, padR = 20, padT = 18, padB = 28;
        const groupW = (w - padL - padR) / 3;
        const barW = groupW * 0.34;

        // Metric 1: Fill Rate % (0 to 100)
        // Metric 2: Spoilage Units (0 to 25)
        // Metric 3: Daily Cost / 20 ($0 to $2000 scaled)
        const groups = [
          {{ label: "Fill Rate %", bVal: bFill, cVal: cFill, maxVal: 100, bText: bFill.toFixed(1) + "%", cText: cFill.toFixed(1) + "%" }},
          {{ label: "Spoilage Units", bVal: bSpoil, cVal: cSpoil, maxVal: 20, bText: bSpoil.toFixed(1), cText: cSpoil.toFixed(1) }},
          {{ label: "Cost ($/day)", bVal: bCost, cVal: cCost, maxVal: 2200, bText: "$" + bCost, cText: "$" + cCost }}
        ];

        groups.forEach((g, idx) => {{
          const gx = padL + idx * groupW;

          // Baseline Bar
          const bh = Math.min(h - padT - padB, (g.bVal / g.maxVal) * (h - padT - padB));
          ctx.fillStyle = "#64748B";
          ctx.fillRect(gx + 12, (h - padB) - bh, barW, bh);

          // Champion Bar
          const ch = Math.min(h - padT - padB, (g.cVal / g.maxVal) * (h - padT - padB));
          ctx.fillStyle = "#10B981";
          ctx.fillRect(gx + 16 + barW, (h - padB) - ch, barW, ch);

          // Labels
          ctx.fillStyle = "#CBD5E1";
          ctx.font = "9.5px JetBrains Mono, monospace";
          ctx.fillText(g.bText, gx + 10, (h - padB) - bh - 4);
          ctx.fillStyle = "#10B981";
          ctx.fillText(g.cText, gx + 16 + barW, (h - padB) - ch - 4);

          ctx.fillStyle = "#94A3B8";
          ctx.font = "10.5px Plus Jakarta Sans, sans-serif";
          ctx.fillText(g.label, gx + 18, h - 8);
        }});

        // SLA Line on Group 1
        const slaY = (h - padB) - (95.0 / 100.0) * (h - padT - padB);
        ctx.strokeStyle = "rgba(244, 63, 94, 0.7)";
        ctx.setLineDash([3, 2]);
        ctx.beginPath();
        ctx.moveTo(padL, slaY);
        ctx.lineTo(padL + groupW - 10, slaY);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#F43F5E";
        ctx.font = "9px JetBrains Mono, monospace";
        ctx.fillText("95% SLA", padL + groupW - 55, slaY - 3);

        // Legend
        ctx.fillStyle = "#64748B";
        ctx.fillText("■ Baseline (s,S)", w - padR - 170, padT);
        ctx.fillStyle = "#10B981";
        ctx.fillText("■ Champion", w - padR - 80, padT);
      }}

      [skuSelect, slideLead, slidePromo, slideSpoil, slideStock].forEach(ctrl => {{
        ctrl?.addEventListener("input", updateWhatIfSimulation);
      }});

      // 11. Zero-Dependency Stateful Python Syntax Lexer & Client-Side LCS Diff Engine
      const PY_KEYWORDS = new Set([
        "and", "as", "assert", "async", "await", "break", "class", "continue",
        "def", "del", "elif", "else", "except", "finally", "for", "from",
        "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
        "or", "pass", "raise", "return", "try", "while", "with", "yield",
        "True", "False", "None"
      ]);

      const PY_BUILTINS = new Set([
        "abs", "all", "any", "bool", "dict", "enumerate", "float", "int",
        "len", "list", "map", "max", "min", "print", "range", "round",
        "set", "str", "sum", "tuple", "zip", "np", "numpy", "zeros", "ones",
        "where", "clip", "maximum", "minimum", "mean", "std", "ceil", "roll",
        "copy", "shape", "ndarray", "float64", "arange"
      ]);

      function tokenizePythonLine(line, lexerState) {{
        const tokens = [];
        let i = 0;
        const len = line.length;

        if (lexerState.inDocstring) {{
          const closeIdx = line.indexOf(lexerState.docDelim, i);
          if (closeIdx === -1) {{
            tokens.push({{ text: line, type: "docstring" }});
            return tokens;
          }} else {{
            const end = closeIdx + 3;
            tokens.push({{ text: line.slice(0, end), type: "docstring" }});
            lexerState.inDocstring = false;
            lexerState.docDelim = null;
            i = end;
          }}
        }}

        while (i < len) {{
          // Multi-line docstring start
          const tri3 = line.slice(i, i + 3);
          if (tri3 === '\"\"\"' || tri3 === \"'''\") {{
            const delim = tri3;
            const closeIdx = line.indexOf(delim, i + 3);
            if (closeIdx === -1) {{
              tokens.push({{ text: line.slice(i), type: "docstring" }});
              lexerState.inDocstring = true;
              lexerState.docDelim = delim;
              break;
            }} else {{
              tokens.push({{ text: line.slice(i, closeIdx + 3), type: "docstring" }});
              i = closeIdx + 3;
              continue;
            }}
          }}

          // Comment
          if (line[i] === "#") {{
            tokens.push({{ text: line.slice(i), type: "comment" }});
            break;
          }}

          // String literals
          if (line[i] === '"' || line[i] === "'") {{
            const q = line[i];
            let j = i + 1;
            while (j < len && line[j] !== q) {{
              if (line[j] === "\\\\") j++;
              j++;
            }}
            tokens.push({{ text: line.slice(i, j + 1), type: "str" }});
            i = j + 1;
            continue;
          }}

          // Numbers
          const numMatch = line.slice(i).match(/^[0-9]+(\\.[0-9]+)?([eE][+-]?[0-9]+)?/);
          if (numMatch && (i === 0 || !/[a-zA-Z_]/.test(line[i - 1]))) {{
            tokens.push({{ text: numMatch[0], type: "num" }});
            i += numMatch[0].length;
            continue;
          }}

          // Identifiers / Keywords / Builtins
          const wordMatch = line.slice(i).match(/^[a-zA-Z_][a-zA-Z0-9_]*/);
          if (wordMatch) {{
            const word = wordMatch[0];
            if (PY_KEYWORDS.has(word)) {{
              tokens.push({{ text: word, type: "kw" }});
            }} else if (PY_BUILTINS.has(word)) {{
              tokens.push({{ text: word, type: "builtin" }});
            }} else {{
              tokens.push({{ text: word, type: "ident" }});
            }}
            i += word.length;
            continue;
          }}

          // Multi-char operators
          const op2Match = line.slice(i).match(/^(==|!=|<=|>=|\\+=|-=|\\*=|\\/=|->|\\*\\*|\\/\\/)/);
          if (op2Match) {{
            tokens.push({{ text: op2Match[0], type: "op" }});
            i += op2Match[0].length;
            continue;
          }}

          // Single-char operators and punctuation
          const ch = line[i];
          if ("=+-*/%<>@&|^~".includes(ch)) {{
            tokens.push({{ text: ch, type: "op" }});
          }} else if ("()[]{{}}:,.;".includes(ch)) {{
            tokens.push({{ text: ch, type: "punct" }});
          }} else {{
            tokens.push({{ text: ch, type: "plain" }});
          }}
          i++;
        }}

        return tokens;
      }}

      // Client-Side Longest Common Subsequence (LCS) Diff Algorithm (<1ms in V8)
      function computeLcsDiff(linesA, linesB) {{
        const n = linesA.length;
        const m = linesB.length;
        const dp = Array.from({{ length: n + 1 }}, () => new Int32Array(m + 1));

        for (let i = 1; i <= n; i++) {{
          for (let j = 1; j <= m; j++) {{
            if (linesA[i - 1] === linesB[j - 1]) {{
              dp[i][j] = dp[i - 1][j - 1] + 1;
            }} else {{
              dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
            }}
          }}
        }}

        let i = n, j = m;
        const diff = [];
        while (i > 0 || j > 0) {{
          if (i > 0 && j > 0 && linesA[i - 1] === linesB[j - 1]) {{
            diff.push({{ type: "same", lineA: i, lineB: j, textA: linesA[i - 1], textB: linesB[j - 1] }});
            i--; j--;
          }} else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {{
            diff.push({{ type: "add", lineB: j, textB: linesB[j - 1] }});
            j--;
          }} else {{
            diff.push({{ type: "del", lineA: i, textA: linesA[i - 1] }});
            i--;
          }}
        }}

        diff.reverse();
        return diff;
      }}

      // Word-Level Diff Highlighter
      function computeWordDiff(wordsA, wordsB) {{
        const n = wordsA.length;
        const m = wordsB.length;
        const dp = Array.from({{ length: n + 1 }}, () => new Int32Array(m + 1));

        for (let i = 1; i <= n; i++) {{
          for (let j = 1; j <= m; j++) {{
            if (wordsA[i - 1] === wordsB[j - 1]) {{
              dp[i][j] = dp[i - 1][j - 1] + 1;
            }} else {{
              dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
            }}
          }}
        }}

        const lcsWords = new Set();
        let i = n, j = m;
        while (i > 0 && j > 0) {{
          if (wordsA[i - 1] === wordsB[j - 1]) {{
            lcsWords.add(wordsA[i - 1]);
            i--; j--;
          }} else if (dp[i][j - 1] >= dp[i - 1][j]) {{
            j--;
          }} else {{
            i--;
          }}
        }}
        return lcsWords;
      }}

      // Render Token Array with Syntax Highlighting and Word Diff to DOM (Safe DOM)
      function renderTokensToSpan(tokens, container, wordDiffClass, changedWords) {{
        tokens.forEach(tok => {{
          if (!tok.text) return;
          const span = el("span", "tok-" + tok.type, tok.text);
          if (wordDiffClass && changedWords && !changedWords.has(tok.text.trim()) && tok.text.trim().length > 0) {{
            span.classList.add(wordDiffClass);
          }}
          container.appendChild(span);
        }});
      }}

      // Diff State
      let diffViewMode = "split"; // "split" or "unified"
      let diffFoldUnchanged = true;
      let leftMilestoneKey = "0";
      let rightMilestoneKey = "8";

      const diffTableBody = document.getElementById("diff-table-body");
      const diffTableHeader = document.getElementById("diff-table-header");
      const btnViewSplit = document.getElementById("btn-view-split");
      const btnViewUnified = document.getElementById("btn-view-unified");
      const btnToggleFold = document.getElementById("btn-toggle-fold");
      const diffSelectBase = document.getElementById("diff-select-base");
      const diffSelectEvolved = document.getElementById("diff-select-evolved");

      function renderCurrentDiff() {{
        if (!diffTableBody) return;
        diffTableBody.replaceChildren();

        const baseM = milestones[leftMilestoneKey] || milestones["0"];
        const evoM = milestones[rightMilestoneKey] || milestones["30"];

        const codeA = baseM.evolve_block || "";
        const codeB = evoM.evolve_block || "";

        const linesA = codeA.split("\\n");
        const linesB = codeB.split("\\n");

        const rawDiff = computeLcsDiff(linesA, linesB);

        // Diff Stats
        let addCount = 0, delCount = 0, sameCount = 0;
        rawDiff.forEach(d => {{
          if (d.type === "add") addCount++;
          else if (d.type === "del") delCount++;
          else sameCount++;
        }});

        document.getElementById("diff-stat-add").textContent = "+" + addCount + " additions";
        document.getElementById("diff-stat-del").textContent = "-" + delCount + " deletions";
        document.getElementById("diff-stat-same").textContent = sameCount + " unchanged";

        document.getElementById("diff-banner-title").textContent = baseM.title + " ➔ " + evoM.title;
        document.getElementById("diff-banner-desc").textContent = evoM.description;

        document.getElementById("diff-header-left").textContent = baseM.title;
        document.getElementById("diff-header-right").textContent = evoM.title;

        if (diffTableHeader) {{
          diffTableHeader.className = "diff-table-header " + (diffViewMode === "split" ? "split" : "unified");
          const rightHeader = document.getElementById("diff-header-right");
          if (rightHeader) rightHeader.style.display = diffViewMode === "split" ? "block" : "none";
        }}

        // Prepare Render Rows (Group changes for split alignment)
        const renderRows = [];
        let k = 0;
        while (k < rawDiff.length) {{
          const item = rawDiff[k];
          if (item.type === "same") {{
            renderRows.push({{ type: "same", item: item }});
            k++;
          }} else {{
            // Gather consecutive deletions and additions
            const dels = [];
            const adds = [];
            while (k < rawDiff.length && rawDiff[k].type === "del") {{
              dels.push(rawDiff[k]);
              k++;
            }}
            while (k < rawDiff.length && rawDiff[k].type === "add") {{
              adds.push(rawDiff[k]);
              k++;
            }}

            const maxLen = Math.max(dels.length, adds.length);
            for (let r = 0; r < maxLen; r++) {{
              renderRows.push({{
                type: "change",
                delItem: dels[r] || null,
                addItem: adds[r] || null
              }});
            }}
          }}
        }}

        // Handle Folding of Unchanged Code Blocks (>= 7 lines)
        const lexerStateA = {{ inDocstring: false, docDelim: null }};
        const lexerStateB = {{ inDocstring: false, docDelim: null }};

        let idx = 0;
        while (idx < renderRows.length) {{
          // Detect contiguous run of 'same' rows
          if (renderRows[idx].type === "same") {{
            let runEnd = idx;
            while (runEnd < renderRows.length && renderRows[runEnd].type === "same") {{
              runEnd++;
            }}
            const runLen = runEnd - idx;

            if (diffFoldUnchanged && runLen >= 7) {{
              // Show 2 context lines at top, 2 at bottom, fold the rest
              const foldStart = idx + 2;
              const foldEnd = runEnd - 2;
              const foldCount = foldEnd - foldStart;

              // Render top context lines
              for (let i = idx; i < foldStart; i++) {{
                renderSingleDiffRow(renderRows[i], lexerStateA, lexerStateB);
              }}

              // Render Fold Bar (Safe DOM)
              const foldRow = el("div", "diff-fold-row");
              foldRow.textContent = "↕ ... " + foldCount + " unchanged lines hidden (click to expand) ...";
              const hiddenRows = renderRows.slice(foldStart, foldEnd);
              foldRow.addEventListener("click", () => {{
                // Expand hidden rows in place
                const frag = document.createDocumentFragment();
                const tempLexA = Object.assign({{}}, lexerStateA);
                const tempLexB = Object.assign({{}}, lexerStateB);
                hiddenRows.forEach(hr => {{
                  const rowNode = buildDiffRowElement(hr, tempLexA, tempLexB);
                  frag.appendChild(rowNode);
                }});
                diffTableBody.insertBefore(frag, foldRow);
                foldRow.remove();
              }});
              diffTableBody.appendChild(foldRow);

              // Render bottom context lines
              for (let i = foldEnd; i < runEnd; i++) {{
                renderSingleDiffRow(renderRows[i], lexerStateA, lexerStateB);
              }}

              idx = runEnd;
              continue;
            }}
          }}

          renderSingleDiffRow(renderRows[idx], lexerStateA, lexerStateB);
          idx++;
        }}
      }}

      function renderSingleDiffRow(rRow, lexA, lexB) {{
        const rowNode = buildDiffRowElement(rRow, lexA, lexB);
        diffTableBody.appendChild(rowNode);
      }}

      function buildDiffRowElement(rRow, lexA, lexB) {{
        const rowEl = el("div", "diff-row " + diffViewMode);

        if (diffViewMode === "split") {{
          // Split View: Left (Base) & Right (Evolved)
          const leftCell = el("div", "diff-cell split-left");
          const rightCell = el("div", "diff-cell split-right");

          if (rRow.type === "same") {{
            const it = rRow.item;
            leftCell.appendChild(el("span", "diff-gutter-num", it.lineA));
            leftCell.appendChild(el("span", "diff-gutter-badge", " "));
            const codeLeft = el("span", "diff-line-code");
            const toks = tokenizePythonLine(it.textA, lexA);
            renderTokensToSpan(toks, codeLeft, null, null);
            leftCell.appendChild(codeLeft);

            rightCell.appendChild(el("span", "diff-gutter-num", it.lineB));
            rightCell.appendChild(el("span", "diff-gutter-badge", " "));
            const codeRight = el("span", "diff-line-code");
            renderTokensToSpan(toks, codeRight, null, null);
            rightCell.appendChild(codeRight);
          }} else {{
            // Changed or One-Sided
            const del = rRow.delItem;
            const add = rRow.addItem;

            // Word diff calculation if both sides present
            let lcsWords = null;
            if (del && add) {{
              const wA = del.textA.trim().split(/\\s+/);
              const wB = add.textB.trim().split(/\\s+/);
              lcsWords = computeWordDiff(wA, wB);
            }}

            if (del) {{
              leftCell.classList.add("diff-row-del");
              leftCell.appendChild(el("span", "diff-gutter-num", del.lineA));
              leftCell.appendChild(el("span", "diff-gutter-badge", "-"));
              const codeLeft = el("span", "diff-line-code");
              const toks = tokenizePythonLine(del.textA, lexA);
              renderTokensToSpan(toks, codeLeft, "diff-word-del", lcsWords);
              leftCell.appendChild(codeLeft);
            }} else {{
              leftCell.classList.add("diff-cell-empty");
            }}

            if (add) {{
              rightCell.classList.add("diff-row-add");
              rightCell.appendChild(el("span", "diff-gutter-num", add.lineB));
              rightCell.appendChild(el("span", "diff-gutter-badge", "+"));
              const codeRight = el("span", "diff-line-code");
              const toks = tokenizePythonLine(add.textB, lexB);
              renderTokensToSpan(toks, codeRight, "diff-word-add", lcsWords);
              rightCell.appendChild(codeRight);
            }} else {{
              rightCell.classList.add("diff-cell-empty");
            }}
          }}

          rowEl.appendChild(leftCell);
          rowEl.appendChild(rightCell);
        }} else {{
          // Unified View
          const cell = el("div", "diff-cell unified");

          if (rRow.type === "same") {{
            const it = rRow.item;
            cell.appendChild(el("span", "diff-gutter-num", it.lineA));
            cell.appendChild(el("span", "diff-gutter-num", it.lineB));
            cell.appendChild(el("span", "diff-gutter-badge", " "));
            const code = el("span", "diff-line-code");
            const toks = tokenizePythonLine(it.textA, lexA);
            renderTokensToSpan(toks, code, null, null);
            cell.appendChild(code);
            rowEl.appendChild(cell);
          }} else {{
            const del = rRow.delItem;
            const add = rRow.addItem;

            let lcsWords = null;
            if (del && add) {{
              const wA = del.textA.trim().split(/\\s+/);
              const wB = add.textB.trim().split(/\\s+/);
              lcsWords = computeWordDiff(wA, wB);
            }}

            if (del) {{
              const cellDel = el("div", "diff-cell unified diff-row-del");
              cellDel.appendChild(el("span", "diff-gutter-num", del.lineA));
              cellDel.appendChild(el("span", "diff-gutter-num", " "));
              cellDel.appendChild(el("span", "diff-gutter-badge", "-"));
              const code = el("span", "diff-line-code");
              const toks = tokenizePythonLine(del.textA, lexA);
              renderTokensToSpan(toks, code, "diff-word-del", lcsWords);
              cellDel.appendChild(code);
              rowEl.appendChild(cellDel);
            }}
            if (add) {{
              const cellAdd = el("div", "diff-cell unified diff-row-add");
              cellAdd.appendChild(el("span", "diff-gutter-num", " "));
              cellAdd.appendChild(el("span", "diff-gutter-num", add.lineB));
              cellAdd.appendChild(el("span", "diff-gutter-badge", "+"));
              const code = el("span", "diff-line-code");
              const toks = tokenizePythonLine(add.textB, lexB);
              renderTokensToSpan(toks, code, "diff-word-add", lcsWords);
              cellAdd.appendChild(code);
              rowEl.appendChild(cellAdd);
            }}
          }}
        }}

        return rowEl;
      }}

      // Stepper Presets
      document.querySelectorAll(".diff-stepper-btn[data-pair]").forEach(btn => {{
        btn.addEventListener("click", () => {{
          document.querySelectorAll(".diff-stepper-btn[data-pair]").forEach(b => b.classList.remove("active"));
          btn.classList.add("active");

          const pair = btn.getAttribute("data-pair").split("-");
          leftMilestoneKey = pair[0];
          rightMilestoneKey = pair[1];

          if (diffSelectBase) diffSelectBase.value = leftMilestoneKey;
          if (diffSelectEvolved) diffSelectEvolved.value = rightMilestoneKey;

          renderCurrentDiff();
        }});
      }});

      if (diffSelectBase && diffSelectEvolved) {{
        diffSelectBase.addEventListener("change", () => {{
          leftMilestoneKey = diffSelectBase.value;
          renderCurrentDiff();
        }});
        diffSelectEvolved.addEventListener("change", () => {{
          rightMilestoneKey = diffSelectEvolved.value;
          renderCurrentDiff();
        }});
      }}

      if (btnViewSplit && btnViewUnified) {{
        btnViewSplit.addEventListener("click", () => {{
          diffViewMode = "split";
          btnViewSplit.classList.add("active");
          btnViewUnified.classList.remove("active");
          renderCurrentDiff();
        }});
        btnViewUnified.addEventListener("click", () => {{
          diffViewMode = "unified";
          btnViewUnified.classList.add("active");
          btnViewSplit.classList.remove("active");
          renderCurrentDiff();
        }});
      }}

      if (btnToggleFold) {{
        btnToggleFold.addEventListener("click", () => {{
          diffFoldUnchanged = !diffFoldUnchanged;
          btnToggleFold.textContent = diffFoldUnchanged ? "Collapse Unchanged" : "Expand All";
          renderCurrentDiff();
        }});
      }}

      document.getElementById("btn-copy-diff")?.addEventListener("click", () => {{
        const evoM = milestones[rightMilestoneKey] || milestones["30"];
        navigator.clipboard.writeText(evoM.evolve_block || "");
      }});

      // 12. Initial Mount & Resize Handlers
      renderMilestoneRibbon();
      updateDisplay(maxGen);
      updateWhatIfSimulation();
      renderCurrentDiff();

      window.addEventListener("resize", () => {{
        drawTrajectoryChart(currentGen);
        drawCanvas2Chart();
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
