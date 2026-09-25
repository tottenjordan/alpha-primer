"""Unit tests for AlphaEvolve client and mock execution."""

from __future__ import annotations

from alpha_evolve.client import MockAlphaEvolveClient
from alpha_evolve.models import (
    AlphaEvolveEvaluationScores,
    AlphaEvolveEvaluationSubmission,
    AlphaEvolveProgramEvaluation,
    ExperimentConfig,
    RunSettings,
)


def test_mock_client_lifecycle() -> None:
    seed_code = "def compute(): return 1\n"
    client = MockAlphaEvolveClient(seed_code=seed_code)

    session = client.create_session()
    assert "mock-session" in session

    cfg = ExperimentConfig(
        project_id="test",
        engine_id="test",
        experiment_name="test",
        user_instructions="test",
        seed_code=seed_code,
        run_settings=RunSettings(mock_mode=True),
    )
    exp = client.create_experiment(session, cfg)
    assert "alphaEvolveExperiments" in exp

    initial_prog = client.create_initial_program(exp, seed_code)
    assert "seed" in initial_prog

    client.start_experiment(exp)

    candidates = client.acquire_programs(exp, count=2)
    assert len(candidates) == 2
    assert "candidate_001" in candidates[0].program_id
    assert candidates[0].code != ""

    sub = AlphaEvolveEvaluationSubmission(
        program=candidates[0].program_id,
        evaluation=AlphaEvolveProgramEvaluation(
            scores=AlphaEvolveEvaluationScores.from_dict({"score": 10.0}),
        ),
    )
    client.submit_evaluations(exp, [sub])
    assert client.evaluated_count == 1
