"""Unit and integration tests for the unified `alpha-evolve` CLI and use-case scaffolder."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from alpha_evolve.cli import (
    REPO_ROOT,
    _load_use_case_submodule,
    discover_use_cases,
    main,
    normalize_use_case_name,
    resolve_use_case,
    scaffold_use_case,
)
from alpha_evolve.dashboard.telemetry_broker import get_global_broker
from alpha_evolve.utils import extract_evolve_blocks


def test_pyproject_registers_alpha_evolve_script() -> None:
    """Verify `[project.scripts]` in pyproject.toml registers `alpha-evolve`."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    scripts = data.get("project", {}).get("scripts", {})
    assert scripts.get("alpha-evolve") == "alpha_evolve.cli:main"


def test_cli_list_table_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `alpha-evolve list` outputs both built-in digital twin use cases."""
    rc = main(["list"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "inventory_replenishment" in captured.out
    assert "fleet_routing" in captured.out
    assert "compute_replenishment_orders" in captured.out
    assert "assign_and_sequence_routes" in captured.out

    rc_json = main(["list", "--json"])
    assert rc_json == 0
    json_out = capsys.readouterr().out
    parsed = json.loads(json_out)
    names = [item["name"] for item in parsed]
    assert "inventory_replenishment" in names
    assert "fleet_routing" in names


def test_cli_list_empty_examples_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `alpha-evolve list` handles an empty examples directory gracefully."""
    rc = main(["list", "--examples-dir", str(tmp_path)])
    assert rc == 0
    assert "No AlphaEvolve use cases found" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("raw_name", "expected_slug"),
    [
        ("dynamic_pricing", "dynamic_pricing"),
        ("energy-grid-dispatch", "energy_grid_dispatch"),
        ("  Cold Chain Logistics  ", "cold_chain_logistics"),
    ],
)
def test_normalize_use_case_name_valid(raw_name: str, expected_slug: str) -> None:
    """Verify valid use-case names normalize cleanly to snake_case slugs."""
    assert normalize_use_case_name(raw_name) == expected_slug


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "   ",
        "../escape",
        "nested/path",
        "nested\\path",
        "123_starts_with_digit",
        "_leading_underscore",
        "class",
        "def",
        "json",
        "time",
        "alpha_evolve",
    ],
)
def test_normalize_use_case_name_invalid(invalid_name: str) -> None:
    """Verify invalid, reserved, or unsafe use-case names raise ValueError."""
    with pytest.raises(ValueError):
        normalize_use_case_name(invalid_name)


def test_cli_init_scaffolds_complete_runnable_use_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `alpha-evolve init` scaffolds a complete 3-tier use case that can be discovered and run."""
    rc = main(
        [
            "init",
            "energy-dispatch",
            "--output-dir",
            str(tmp_path),
            "--target-function",
            "dispatch_grid_power",
            "--primary-metric",
            "grid_score",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "energy_dispatch" in out

    uc_dir = tmp_path / "energy_dispatch"
    assert uc_dir.is_dir()
    expected_files = [
        "__init__.py",
        "README.md",
        "instructions.md",
        "run_evolution.py",
        "src/__init__.py",
        "src/program.py",
        "src/simulator.py",
        "src/evaluate.py",
        "src/report.py",
        "tests/__init__.py",
        "tests/test_energy_dispatch.py",
    ]
    for rel_path in expected_files:
        assert (uc_dir / rel_path).is_file(), f"Missing scaffolded file: {rel_path}"

    # Verify EVOLVE-BLOCK markers in generated seed program
    program_source = (uc_dir / "src" / "program.py").read_text(encoding="utf-8")
    blocks = extract_evolve_blocks(program_source)
    assert len(blocks) == 1
    assert "def dispatch_grid_power" in blocks[0]

    # Verify discovery picks up the newly scaffolded use case with clean title
    discovered = discover_use_cases(tmp_path)
    assert len(discovered) == 1
    assert discovered[0].name == "energy_dispatch"
    assert discovered[0].title == "Energy Dispatch Digital Twin"
    assert discovered[0].target_function == "dispatch_grid_power"
    assert discovered[0].primary_metric == "grid_score"
    assert discovered[0].evaluator_class == "EnergyDispatchEvaluator"

    # Run the newly scaffolded use case end-to-end via `alpha-evolve run`
    artifacts_dir = tmp_path / "artifacts" / "energy_dispatch"
    rc_run = main(
        [
            "run",
            "energy_dispatch",
            "--examples-dir",
            str(tmp_path),
            "--dry-run",
            "--max-programs",
            "3",
            "--workers",
            "1",
            "--output-dir",
            str(artifacts_dir),
        ]
    )
    assert rc_run == 0
    evolved_path = artifacts_dir / "best_evolved_program.py"
    assert evolved_path.is_file()
    assert evolved_path.read_text(encoding="utf-8") != program_source

    summary_path = artifacts_dir / "best_evaluation_summary.json"
    assert summary_path.is_file()
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_data["primary_metric"] == "grid_score"
    assert summary_data["scores"]["grid_score"] > 0.0

    # Verify generated files pass ruff lint, ruff format, and ty type checks
    ruff_check = subprocess.run(
        [sys.executable, "-m", "ruff", "check", str(uc_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ruff_check.returncode == 0, (
        f"Scaffolded code failed ruff check:\n{ruff_check.stdout}\n{ruff_check.stderr}"
    )

    ruff_fmt = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", str(uc_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ruff_fmt.returncode == 0, (
        f"Scaffolded code failed ruff format:\n{ruff_fmt.stdout}\n{ruff_fmt.stderr}"
    )

    ty_res = subprocess.run(
        [
            sys.executable,
            "-m",
            "ty",
            "check",
            "--extra-search-path",
            str(tmp_path),
            str(uc_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ty_res.returncode == 0, (
        f"Scaffolded code failed ty check:\n{ty_res.stdout}\n{ty_res.stderr}"
    )

    # Verify generated unit test suite passes
    pytest_res = subprocess.run(
        [sys.executable, "-m", "pytest", str(uc_dir / "tests"), "-v"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert pytest_res.returncode == 0, (
        f"Scaffolded tests failed:\n{pytest_res.stdout}\n{pytest_res.stderr}"
    )

    # Verify generated standalone run_evolution.py executes cleanly
    standalone_out = tmp_path / "standalone_artifacts"
    run_script_res = subprocess.run(
        [
            sys.executable,
            str(uc_dir / "run_evolution.py"),
            "--dry-run",
            "--max-programs",
            "2",
            "--workers",
            "1",
            "--output-dir",
            str(standalone_out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run_script_res.returncode == 0, (
        f"Standalone run_evolution.py failed:\n{run_script_res.stdout}\n{run_script_res.stderr}"
    )
    assert (standalone_out / "best_evolved_program.py").is_file()


def test_cli_init_existing_directory_protection_and_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `alpha-evolve init` refuses to overwrite existing files unless `--force` is passed."""
    target_dir = scaffold_use_case("lot_sizing", output_dir=tmp_path)
    assert target_dir == (tmp_path / "lot_sizing").resolve()

    # Second call without --force must fail with exit code 2
    rc_conflict = main(["init", "lot_sizing", "--output-dir", str(tmp_path)])
    assert rc_conflict == 2
    assert "already exists" in capsys.readouterr().err

    # Passing --force succeeds
    rc_force = main(["init", "lot_sizing", "--output-dir", str(tmp_path), "--force"])
    assert rc_force == 0


def test_cli_init_invalid_arguments_and_filesystem_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `alpha-evolve init` rejects invalid names, target functions, metrics, or file collisions."""
    assert main(["init", "../bad_name", "--output-dir", str(tmp_path)]) == 2
    assert "Error" in capsys.readouterr().err

    assert (
        main(
            [
                "init",
                "valid_name",
                "--output-dir",
                str(tmp_path),
                "--target-function",
                "not-an-identifier",
            ]
        )
        == 2
    )
    assert "Invalid target function" in capsys.readouterr().err

    assert (
        main(
            [
                "init",
                "valid_name",
                "--output-dir",
                str(tmp_path),
                "--primary-metric",
                "123metric",
            ]
        )
        == 2
    )
    assert "Invalid primary metric" in capsys.readouterr().err

    # Target path is an existing regular file
    blocking_file = tmp_path / "file_collision"
    blocking_file.write_text("not a dir", encoding="utf-8")
    assert main(["init", "file_collision", "--output-dir", str(tmp_path), "--force"]) == 2
    assert "not a directory" in capsys.readouterr().err

    # Read-only parent directory triggers OSError -> exit code 2
    readonly_dir = tmp_path / "readonly_parent"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o555)
    try:
        rc_ro = main(["init", "locked_domain", "--output-dir", str(readonly_dir)])
        assert rc_ro == 2
        assert "Error" in capsys.readouterr().err
    finally:
        readonly_dir.chmod(0o755)


def test_cli_run_builtin_use_cases_dry_run_and_dashboard_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `alpha-evolve run` executes dry-run evolution, respects MOCK_ALPHAEVOLVE, and streams SSE."""
    broker = get_global_broker()
    broker.clear()
    sub_queue = broker.subscribe()

    try:
        inv_out = tmp_path / "inv_artifacts"
        rc_inv = main(
            [
                "run",
                "inventory-replenishment",
                "--dry-run",
                "--max-programs",
                "2",
                "--workers",
                "1",
                "--skip-holdout",
                "--stream-to-dashboard",
                "--output-dir",
                str(inv_out),
            ]
        )
        assert rc_inv == 0
        assert (inv_out / "best_evolved_program.py").is_file()
        assert (inv_out / "best_evaluation_summary.json").is_file()

        events = []
        while not sub_queue.empty():
            events.append(sub_queue.get_nowait())
        event_types = [e["event_type"] for e in events]
        assert "run_started" in event_types
        assert "candidate_evaluated" in event_types
        assert "run_completed" in event_types
    finally:
        broker.unsubscribe(sub_queue)

    # Verify MOCK_ALPHAEVOLVE=true is honored even when --dry-run flag is omitted
    monkeypatch.setenv("MOCK_ALPHAEVOLVE", "true")
    fleet_out = tmp_path / "fleet_artifacts"
    rc_fleet = main(
        [
            "run",
            "fleet_routing",
            "--max-programs",
            "2",
            "--workers",
            "1",
            "--skip-holdout",
            "--output-dir",
            str(fleet_out),
        ]
    )
    assert rc_fleet == 0
    assert (fleet_out / "best_evolved_program.py").is_file()
    assert (fleet_out / "best_evaluation_summary.json").is_file()


def test_cli_run_error_handling(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `alpha-evolve run` returns exit code 2 for unknown use cases or invalid bounds."""
    rc_unknown = main(["run", "nonexistent_domain", "--dry-run"])
    assert rc_unknown == 2
    err_out = capsys.readouterr().err
    assert "Unknown use case" in err_out
    assert "inventory_replenishment" in err_out

    rc_bad_max = main(["run", "fleet_routing", "--dry-run", "--max-programs", "0"])
    assert rc_bad_max == 2
    assert "--max-programs must be >= 1" in capsys.readouterr().err

    rc_bad_workers = main(["run", "fleet_routing", "--dry-run", "--workers", "0"])
    assert rc_bad_workers == 2
    assert "--workers must be >= 1" in capsys.readouterr().err


def test_resolve_use_case_by_path_and_relative_dot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `resolve_use_case` handles direct paths, `.`, symlinks, and invalid directory names."""
    fleet_path = REPO_ROOT / "examples" / "fleet_routing"
    info = resolve_use_case(str(fleet_path))
    assert info.name == "fleet_routing"
    assert info.target_function == "assign_and_sequence_routes"

    # Relative "." inside a built-in use case directory
    monkeypatch.chdir(fleet_path)
    dot_info = resolve_use_case(".")
    assert dot_info.name == "fleet_routing"
    assert dot_info.title == "Dynamic Fleet Routing & Dispatch Digital Twin"

    # Symlinked output directory
    real_dir = tmp_path / "real_parent"
    real_dir.mkdir()
    symlink_dir = tmp_path / "symlink_parent"
    symlink_dir.symlink_to(real_dir, target_is_directory=True)
    created = scaffold_use_case("warehouse_slotting", output_dir=symlink_dir)
    assert created.name == "warehouse_slotting"
    assert resolve_use_case(str(created)).name == "warehouse_slotting"

    # Invalid directory name (with hyphen) containing src/program.py and src/evaluate.py
    bad_dir = tmp_path / "bad-folder-name"
    (bad_dir / "src").mkdir(parents=True)
    (bad_dir / "src" / "program.py").write_text("# stub\n", encoding="utf-8")
    (bad_dir / "src" / "evaluate.py").write_text("# stub\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a valid Python identifier"):
        resolve_use_case(str(bad_dir))


def test_load_use_case_submodule_switches_cleanly_between_duplicate_basenames(
    tmp_path: Path,
) -> None:
    """Verify `_load_use_case_submodule` reloads from the right directory when switching A -> B -> A."""
    dir_a = scaffold_use_case("shared_slug", output_dir=tmp_path / "parent_a")
    dir_b = scaffold_use_case("shared_slug", output_dir=tmp_path / "parent_b")

    mod_a1 = _load_use_case_submodule(dir_a, "program")
    assert Path(mod_a1.__file__ or "").resolve() == (dir_a / "src" / "program.py").resolve()

    mod_b = _load_use_case_submodule(dir_b, "program")
    assert Path(mod_b.__file__ or "").resolve() == (dir_b / "src" / "program.py").resolve()

    mod_a2 = _load_use_case_submodule(dir_a, "program")
    assert Path(mod_a2.__file__ or "").resolve() == (dir_a / "src" / "program.py").resolve()


def test_cli_subprocess_execution() -> None:
    """Verify `alpha_evolve.cli list` executes cleanly in both JSON and dumb-terminal table modes."""
    proc_json = subprocess.run(
        [sys.executable, "-m", "alpha_evolve.cli", "list", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_json.returncode == 0
    payload = json.loads(proc_json.stdout)
    assert len(payload) >= 2

    env = {"TERM": "dumb", "PATH": ""}
    proc_table = subprocess.run(
        [sys.executable, "-m", "alpha_evolve.cli", "list"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc_table.returncode == 0
    assert "inventory_replenishment" in proc_table.stdout
    assert "compute_replenishment_orders" in proc_table.stdout
    assert "InventoryReplenishmentEvaluator" in proc_table.stdout
