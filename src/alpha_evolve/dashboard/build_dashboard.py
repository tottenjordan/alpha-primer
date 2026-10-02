"""Build the C-Suite Interactive Dashboard for AlphaEvolve Supply Chain Digital Twin.

Compiles `dashboard/index.html` from `records/master_trajectories.json` and the
static template assets under `src/alpha_evolve/dashboard/templates/`.
Strictly enforces enterprise Safe DOM construction (document.createElement, textContent,
replaceChildren) with ZERO dangerous HTML string injection.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
RECORDS_DIR = ROOT_DIR / "records"
DASHBOARD_DIR = ROOT_DIR / "dashboard"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def build_dashboard_html(
    master_path: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Compile records/master_trajectories.json into self-contained dashboard/index.html.

    Args:
        master_path: Optional path to master_trajectories.json. Defaults to records/master_trajectories.json.
        output_dir: Optional directory to save output files. Defaults to dashboard/.

    Returns:
        Path to the generated index.html file.
    """
    actual_master_path = (
        master_path if master_path is not None else (RECORDS_DIR / "master_trajectories.json")
    )
    if not actual_master_path.exists():
        raise FileNotFoundError(f"Missing {actual_master_path}. Run trajectory_generator.py first.")

    master_data = json.loads(actual_master_path.read_text(encoding="utf-8"))
    target_dir = output_dir if output_dir is not None else DASHBOARD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "data.json").write_text(json.dumps(master_data, indent=2), encoding="utf-8")

    embedded_json = json.dumps(master_data)
    styles_css = (TEMPLATES_DIR / "styles.css").read_text(encoding="utf-8").rstrip("\n")
    body_html = (TEMPLATES_DIR / "body.html").read_text(encoding="utf-8").rstrip("\n")
    app_js = (TEMPLATES_DIR / "app.js").read_text(encoding="utf-8").rstrip("\n")

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
{styles_css}
  </style>
</head>
<body>

  <!-- Telemetry Data Island (JSON parse safe) -->
  <script id="master-trajectory-data" type="application/json">
{embedded_json}
  </script>

{body_html}

  <!-- Dashboard Client-Side Controller -->
  <script>
{app_js}
  </script>
</body>
</html>
"""

    out_file = target_dir / "index.html"
    out_file.write_text(html_content, encoding="utf-8")
    return out_file


if __name__ == "__main__":
    print("Compiling dashboard index.html...")
    path = build_dashboard_html()
    print(f"Successfully generated {path}")
