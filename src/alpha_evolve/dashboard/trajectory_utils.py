"""Shared S-curve interpolation and master trajectory bundle utilities."""

from __future__ import annotations

import contextlib
import datetime
import json
from pathlib import Path
from typing import Any


def s_curve_progress(gen: int, max_gen: int = 30) -> float:
    """Compute normalized S-curve progression factor in [0.0, 1.0] for generation `gen`."""
    if gen <= 0:
        return 0.0
    if gen >= max_gen:
        return 1.0
    t = gen / float(max_gen)
    return (t**1.45) / ((t**1.45) + ((1.0 - t) ** 1.65))


def interpolate_s_curve(
    start_val: float,
    end_val: float,
    gen: int,
    max_gen: int = 30,
) -> float:
    """Smoothly interpolate a metric between baseline (gen 0) and champion (max_gen)."""
    factor = s_curve_progress(gen, max_gen=max_gen)
    return start_val + (end_val - start_val) * factor


def update_master_trajectories_bundle(
    use_case_id: str,
    use_case_data: dict[str, Any],
    target_dir: Path,
    default_records_dir: Path,
    use_case_filename: str,
    companion_use_cases: dict[str, str] | None = None,
    write_files: bool = True,
) -> dict[str, Any]:
    """Assemble and optionally persist the multi-use-case master_trajectories.json bundle."""
    master_bundle: dict[str, Any] = {
        "platform_title": "AlphaEvolve Supply Chain & Digital Twin Intelligence Suite",
        "generated_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "engine_info": {
            "project_id": "934903580331",
            "engine_id": "alpha-evolve-experiment-engine",
            "collection_id": "default_collection",
            "location": "global",
            "api_endpoint": "https://discoveryengine.googleapis.com",
            "auth_mode": "Application Default Credentials (ADC - google.auth.default)",
        },
        "use_cases": {
            use_case_id: use_case_data,
        },
    }

    master_path = target_dir / "master_trajectories.json"
    if not master_path.exists() and (default_records_dir / "master_trajectories.json").exists():
        master_path = default_records_dir / "master_trajectories.json"

    if master_path.exists():
        with contextlib.suppress(Exception):
            existing = json.loads(master_path.read_text(encoding="utf-8"))
            if isinstance(existing.get("use_cases"), dict):
                for k, v in existing["use_cases"].items():
                    if k != use_case_id:
                        master_bundle["use_cases"][k] = v

    for comp_id, comp_filename in (companion_use_cases or {}).items():
        if comp_id in master_bundle["use_cases"]:
            continue
        comp_path = target_dir / comp_filename
        if not comp_path.exists():
            comp_path = default_records_dir / comp_filename
        if comp_path.exists():
            with contextlib.suppress(Exception):
                master_bundle["use_cases"][comp_id] = json.loads(
                    comp_path.read_text(encoding="utf-8")
                )

    if write_files:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / use_case_filename).write_text(
            json.dumps(use_case_data, indent=2), encoding="utf-8"
        )
        (target_dir / "master_trajectories.json").write_text(
            json.dumps(master_bundle, indent=2), encoding="utf-8"
        )

    return master_bundle
