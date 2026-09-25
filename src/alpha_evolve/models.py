"""Data models and schemas for AlphaEvolve experiment orchestration and evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AlphaEvolveEvaluationScore(BaseModel):
    """A single evaluation score metric."""

    metric: str = Field(description="Name of the target metric (e.g. 'cost_reduction_pct').")
    score: float = Field(description="Numeric score value.")


class AlphaEvolveEvaluationScores(BaseModel):
    """List of numerical evaluation scores returned to AlphaEvolve API."""

    scores: list[AlphaEvolveEvaluationScore] = Field(
        default_factory=list,
        description="List of evaluation scores for the target metrics.",
    )

    @classmethod
    def from_dict(cls, score_map: dict[str, float]) -> AlphaEvolveEvaluationScores:
        """Create from a dictionary of metric names to values."""
        return cls(
            scores=[AlphaEvolveEvaluationScore(metric=k, score=v) for k, v in score_map.items()]
        )

    def to_dict(self) -> dict[str, float]:
        """Convert to a dictionary of metric names to values."""
        return {s.metric: s.score for s in self.scores}


class AlphaEvolveEvaluationInsight(BaseModel):
    """A diagnostic feedback insight string."""

    label: str = Field(description="Label or category of the insight.")
    text: str = Field(description="Diagnostic explanation or actionable feedback.")


class AlphaEvolveEvaluationInsights(BaseModel):
    """Represents diagnostic insights about the candidate for future prompt mutations."""

    insights: list[AlphaEvolveEvaluationInsight] = Field(
        default_factory=list,
        description="List of diagnostic insights.",
    )

    @classmethod
    def from_dict(cls, insight_map: dict[str, str]) -> AlphaEvolveEvaluationInsights:
        """Create from a dictionary of insight labels to text."""
        return cls(
            insights=[AlphaEvolveEvaluationInsight(label=k, text=v) for k, v in insight_map.items()]
        )

    def to_dict(self) -> dict[str, str]:
        """Convert to a dictionary of labels to text."""
        return {i.label: i.text for i in self.insights}


class AlphaEvolveProgramEvaluation(BaseModel):
    """Wire representation of program evaluation submitted to the API."""

    scores: AlphaEvolveEvaluationScores
    insights: AlphaEvolveEvaluationInsights | None = None


class AlphaEvolveEvaluationSubmission(BaseModel):
    """Submission payload for a single program evaluation."""

    program: str = Field(description="Full resource name of the program candidate.")
    lockToken: str | None = Field(
        default=None,
        description="Lock token acquired with the program.",
    )
    evaluation: AlphaEvolveProgramEvaluation


class EvaluationResult(BaseModel):
    """Result of running an evaluation on a single program candidate."""

    status: str = Field(
        default="SUCCESS",
        description="Evaluation status: SUCCESS, FAILED, or TIMEOUT.",
    )
    scores: AlphaEvolveEvaluationScores = Field(default_factory=AlphaEvolveEvaluationScores)
    insights: AlphaEvolveEvaluationInsights = Field(default_factory=AlphaEvolveEvaluationInsights)
    error_message: str | None = Field(default=None, description="Error trace or failure reason.")
    execution_time_s: float = Field(default=0.0, description="Runtime in seconds.")

    @classmethod
    def failure(
        cls, error_message: str, insights: dict[str, str] | None = None
    ) -> EvaluationResult:
        """Helper to create a failed evaluation result."""
        fail_insights = {"failure_reason": error_message[:500]}
        if insights:
            fail_insights.update(insights)

        return cls(
            status="FAILED",
            scores=AlphaEvolveEvaluationScores.from_dict({"score": -1e9}),
            insights=AlphaEvolveEvaluationInsights.from_dict(fail_insights),
            error_message=error_message,
        )


class ProgramCandidate(BaseModel):
    """A generated code candidate from AlphaEvolve."""

    program_id: str = Field(
        description="Unique identifier / resource name for the program candidate."
    )
    code: str = Field(description="Full Python source code of the candidate.")
    lock_token: str | None = Field(default=None, description="Lock token acquired from the API.")
    iteration: int = Field(default=0, description="Evolution generation / iteration index.")
    parent_id: str | None = Field(default=None, description="Parent program ID if known.")

    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Timestamp of generation.",
    )
    evaluation_result: EvaluationResult | None = Field(
        default=None,
        description="Evaluation result once computed.",
    )


class RunSettings(BaseModel):
    """Execution and stopping criteria for an AlphaEvolve run."""

    max_programs: int = Field(default=20, description="Total number of programs to generate.")
    max_evaluation_time_s: float = Field(
        default=30.0,
        description="Hard timeout per evaluation in seconds.",
    )
    parallel_workers: int = Field(default=4, description="Number of parallel evaluation workers.")
    idle_timeout_s: float = Field(
        default=300.0,
        description="Seconds to wait for new candidates before terminating.",
    )

    mock_mode: bool = Field(
        default=False,
        description="Whether to run in offline mock mode without connecting to GCP.",
    )


class ExperimentConfig(BaseModel):
    """Configuration for an AlphaEvolve experiment."""

    project_id: str = Field(description="Google Cloud Project ID.")
    location: str = Field(default="global", description="GCP region or location.")
    collection: str = Field(
        default="default_collection", description="Discovery Engine collection."
    )
    engine_id: str = Field(description="Discovery Engine app / engine ID.")
    assistant_id: str = Field(default="default_assistant", description="Assistant ID.")
    service_account_email: str | None = Field(
        default=None,
        description="Service account email for impersonation.",
    )
    experiment_name: str = Field(description="Name or title of the experiment.")
    user_instructions: str = Field(description="Domain prompt and search constraints.")
    seed_code: str = Field(description="Seed Python program containing # EVOLVE-BLOCK tags.")
    run_settings: RunSettings = Field(default_factory=RunSettings)
    metadata: dict[str, Any] = Field(default_factory=dict)
