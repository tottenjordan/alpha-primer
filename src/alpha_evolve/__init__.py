"""AlphaEvolve on Google Cloud.

Architecting and implementing AlphaEvolve with Gemini Enterprise for practical enterprise use cases.
"""

from .client import AlphaEvolveClient, MockAlphaEvolveClient
from .controller import EvolutionController
from .experiment import AlphaEvolveExperiment
from .models import (
    AlphaEvolveEvaluationInsight,
    AlphaEvolveEvaluationInsights,
    AlphaEvolveEvaluationScore,
    AlphaEvolveEvaluationScores,
    AlphaEvolveEvaluationSubmission,
    AlphaEvolveProgramEvaluation,
    EvaluationResult,
    ExperimentConfig,
    ProgramCandidate,
    RunSettings,
)
from .utils import compute_code_complexity, export_artifact, extract_evolve_blocks

__version__ = "0.1.0"

__all__ = [
    "AlphaEvolveClient",
    "AlphaEvolveEvaluationInsight",
    "AlphaEvolveEvaluationInsights",
    "AlphaEvolveEvaluationScore",
    "AlphaEvolveEvaluationScores",
    "AlphaEvolveEvaluationSubmission",
    "AlphaEvolveExperiment",
    "AlphaEvolveProgramEvaluation",
    "EvaluationResult",
    "EvolutionController",
    "ExperimentConfig",
    "MockAlphaEvolveClient",
    "ProgramCandidate",
    "RunSettings",
    "compute_code_complexity",
    "export_artifact",
    "extract_evolve_blocks",
]
