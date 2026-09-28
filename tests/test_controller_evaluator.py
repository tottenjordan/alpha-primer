"""Tests for EvolutionController polymorphic evaluator integration and lifecycle."""

from __future__ import annotations

from typing import Any

import pytest

from alpha_evolve.client import MockAlphaEvolveClient
from alpha_evolve.controller import EvolutionController
from alpha_evolve.evaluators import BaseEvaluator, EvaluationTier, TierResult
from alpha_evolve.experiment import AlphaEvolveExperiment
from alpha_evolve.models import (
    AlphaEvolveEvaluationInsights,
    AlphaEvolveEvaluationScores,
    EvaluationResult,
    ExperimentConfig,
    RunSettings,
)


class DummyLifecycleEvaluator(BaseEvaluator):
    """Evaluator tracking setup and teardown calls."""

    name = "dummy_lifecycle"
    primary_metric = "custom_fitness"
    higher_is_better = True
    target_function_name = "custom_solve"

    def __init__(self) -> None:
        self.setup_called = False
        self.teardown_called = False

    def setup(self) -> None:
        self.setup_called = True

    def teardown(self) -> None:
        self.teardown_called = True

    def evaluate_smoke(self, candidate_callable: Any) -> TierResult:
        val = candidate_callable(1)
        if val < 0:
            return TierResult.failure(EvaluationTier.SMOKE, "Output is negative")
        return TierResult.success(EvaluationTier.SMOKE, {"smoke_ok": 1.0})

    def evaluate_validation(self, candidate_callable: Any) -> TierResult:
        val = float(candidate_callable(5))
        return TierResult.success(
            EvaluationTier.VALIDATION,
            metrics={"custom_fitness": val},
            insights={"val": val},
        )


def _make_config() -> ExperimentConfig:
    return ExperimentConfig(
        project_id="test-proj",
        location="global",
        collection="default",
        engine_id="test-eng",
        assistant_id="test-asst",
        experiment_name="test-exp",
        user_instructions="Solve custom problem",
        seed_code="def custom_solve(x: int) -> int:\n    return x * 2\n",
        run_settings=RunSettings(
            max_programs=3,
            parallel_workers=2,
            mock_mode=True,
        ),
    )


def test_controller_with_base_evaluator() -> None:
    config = _make_config()
    client = MockAlphaEvolveClient(seed_code=config.seed_code)
    evaluator = DummyLifecycleEvaluator()

    controller = EvolutionController(
        config=config,
        client=client,
        evaluator=evaluator,
    )

    assert controller.target_function_name == "custom_solve"
    assert controller.primary_metric == "custom_fitness"
    assert not evaluator.setup_called
    assert not evaluator.teardown_called

    best_candidate = controller.run()

    assert evaluator.setup_called
    assert evaluator.teardown_called
    assert best_candidate is not None
    assert len(controller.candidates_history) >= 2
    assert controller.best_score > 0


def test_controller_with_legacy_callable() -> None:
    config = _make_config()
    config.seed_code = "def legacy_func(x: int) -> int:\n    return x * 10\n"
    client = MockAlphaEvolveClient(seed_code=config.seed_code)

    def legacy_eval(fn: Any) -> EvaluationResult:
        score = float(fn(2))
        return EvaluationResult(
            status="SUCCESS",
            scores=AlphaEvolveEvaluationScores.from_dict({"legacy_metric": score}),
            insights=AlphaEvolveEvaluationInsights.from_dict({"source": "legacy"}),
            execution_time_s=0.01,
        )

    controller = EvolutionController(
        config=config,
        client=client,
        evaluator_fn=legacy_eval,
        target_function_name="legacy_func",
        primary_metric="legacy_metric",
    )

    assert controller.target_function_name == "legacy_func"
    assert controller.primary_metric == "legacy_metric"

    best_cand = controller.run()
    assert best_cand is not None
    assert controller.best_score == 20.0


def test_controller_requires_evaluator_or_evaluator_fn() -> None:
    config = _make_config()
    client = MockAlphaEvolveClient(seed_code=config.seed_code)

    with pytest.raises(ValueError, match="Either 'evaluator' or 'evaluator_fn' must be provided"):
        EvolutionController(
            config=config,
            client=client,
        )


def test_experiment_with_base_evaluator(tmp_path: Any) -> None:
    instructions_file = tmp_path / "instructions.md"
    instructions_file.write_text("Optimize function", encoding="utf-8")
    seed_file = tmp_path / "seed.py"
    seed_file.write_text("def custom_solve(x: int) -> int:\n    return x + 5\n", encoding="utf-8")

    evaluator = DummyLifecycleEvaluator()

    experiment = AlphaEvolveExperiment.from_files(
        experiment_name="Hermetic BaseEvaluator Experiment",
        instructions_path=instructions_file,
        seed_program_path=seed_file,
        evaluator=evaluator,
        max_programs=2,
        parallel_workers=1,
        dry_run=True,
    )

    out_dir = tmp_path / "artifacts"
    best_candidate = experiment.run(output_dir=out_dir)

    assert best_candidate is not None
    assert (out_dir / "best_evolved_program.py").exists()
    assert (out_dir / "best_evaluation_summary.json").exists()
    assert evaluator.setup_called
    assert evaluator.teardown_called


def test_controller_wires_sandbox_config() -> None:
    config = _make_config()
    config.run_settings.sandbox_mode = "process"
    config.run_settings.max_memory_mb = 1024
    config.run_settings.max_evaluation_time_s = 12.0
    client = MockAlphaEvolveClient(seed_code=config.seed_code)
    evaluator = DummyLifecycleEvaluator()

    controller = EvolutionController(
        config=config,
        client=client,
        evaluator=evaluator,
    )

    assert controller.worker_pool.sandbox_config.sandbox_mode == "process"
    assert controller.worker_pool.sandbox_config.max_memory_mb == 1024
    assert controller.worker_pool.sandbox_config.timeout_s == 12.0
