"""Unit tests for AlphaEvolve data models and serialization."""

from __future__ import annotations

from alpha_evolve.models import (
    AlphaEvolveEvaluationInsights,
    AlphaEvolveEvaluationScores,
    AlphaEvolveEvaluationSubmission,
    AlphaEvolveProgramEvaluation,
    EvaluationResult,
    ExperimentConfig,
    RunSettings,
)


def test_scores_serialization() -> None:
    scores = AlphaEvolveEvaluationScores.from_dict({"cost_reduction_pct": 18.5, "fill_rate": 96.2})
    score_dict = scores.to_dict()
    assert score_dict["cost_reduction_pct"] == 18.5
    assert score_dict["fill_rate"] == 96.2


def test_insights_serialization() -> None:
    insights = AlphaEvolveEvaluationInsights.from_dict(
        {
            "fill_rate": "Target met",
            "spoilage": "Reduced by 30%",
        }
    )
    insight_dict = insights.to_dict()
    assert insight_dict["fill_rate"] == "Target met"
    assert insight_dict["spoilage"] == "Reduced by 30%"


def test_evaluation_result_failure_helper() -> None:
    result = EvaluationResult.failure("Syntax error in line 4", insights={"tier": "tier_0"})
    assert result.status == "FAILED"
    assert result.scores.to_dict()["score"] == -1e9
    assert "failure_reason" in result.insights.to_dict()
    assert result.insights.to_dict()["tier"] == "tier_0"


def test_evaluation_submission_wire_format() -> None:
    eval_res = EvaluationResult(
        status="SUCCESS",
        scores=AlphaEvolveEvaluationScores.from_dict({"score": 25.0}),
        insights=AlphaEvolveEvaluationInsights.from_dict({"status": "optimal"}),
    )
    submission = AlphaEvolveEvaluationSubmission(
        program="experiments/123/programs/prog_01",
        evaluation=AlphaEvolveProgramEvaluation(
            scores=eval_res.scores,
            insights=eval_res.insights,
        ),
    )
    payload = submission.model_dump()
    assert payload["program"] == "experiments/123/programs/prog_01"
    assert payload["evaluation"]["scores"]["scores"][0]["metric"] == "score"
    assert payload["evaluation"]["scores"]["scores"][0]["score"] == 25.0


def test_experiment_config() -> None:
    cfg = ExperimentConfig(
        project_id="test-project",
        engine_id="test-engine",
        experiment_name="Unit Test Exp",
        user_instructions="Optimize this code",
        seed_code="def func(): pass",
        run_settings=RunSettings(max_programs=5, mock_mode=True),
    )
    assert cfg.project_id == "test-project"
    assert cfg.run_settings.mock_mode is True
