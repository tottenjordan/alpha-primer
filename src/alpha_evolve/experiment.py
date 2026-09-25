"""High-level Experiment API for building and launching AlphaEvolve runs."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .client import AlphaEvolveClient, MockAlphaEvolveClient
from .controller import EvolutionController
from .models import EvaluationResult, ExperimentConfig, ProgramCandidate, RunSettings
from .utils import export_artifact

logger = logging.getLogger(__name__)


class AlphaEvolveExperiment:
    """High-level orchestrator for defining and running an AlphaEvolve optimization experiment."""

    def __init__(
        self,
        config: ExperimentConfig,
        evaluator_fn: Callable[[Any], EvaluationResult],
        target_function_name: str,
        primary_metric: str = "cost_reduction_pct",
    ) -> None:
        self.config = config
        self.evaluator_fn = evaluator_fn
        self.target_function_name = target_function_name
        self.primary_metric = primary_metric

    @classmethod
    def from_files(
        cls,
        experiment_name: str,
        instructions_path: str | Path,
        seed_program_path: str | Path,
        evaluator_fn: Callable[[Any], EvaluationResult],
        target_function_name: str,
        primary_metric: str = "cost_reduction_pct",
        max_programs: int = 20,
        parallel_workers: int = 4,
        dry_run: bool | None = None,
    ) -> AlphaEvolveExperiment:
        """Construct an experiment from files and local environment configuration."""
        load_dotenv()

        project_id = os.getenv("PROJECT_ID", "hybrid-vertex")
        location = os.getenv("LOCATION", "global")
        collection = os.getenv("COLLECTION", "default_collection")
        engine_id = os.getenv("ENGINE_ID", "alpha-evolve-experiment-engine")
        assistant_id = os.getenv("ASSISTANT_ID", "default_assistant")
        sa_email = os.getenv("SERVICE_ACCOUNT_EMAIL")

        env_mock = os.getenv("MOCK_ALPHAEVOLVE", "false").lower() in {"1", "true", "yes"}
        mock_mode = dry_run if dry_run is not None else env_mock

        instructions = Path(instructions_path).read_text(encoding="utf-8")
        seed_code = Path(seed_program_path).read_text(encoding="utf-8")

        config = ExperimentConfig(
            project_id=project_id,
            location=location,
            collection=collection,
            engine_id=engine_id,
            assistant_id=assistant_id,
            service_account_email=sa_email,
            experiment_name=experiment_name,
            user_instructions=instructions,
            seed_code=seed_code,
            run_settings=RunSettings(
                max_programs=max_programs,
                parallel_workers=parallel_workers,
                mock_mode=mock_mode,
            ),
        )

        return cls(
            config=config,
            evaluator_fn=evaluator_fn,
            target_function_name=target_function_name,
            primary_metric=primary_metric,
        )

    def run(self, output_dir: str | Path = "artifacts") -> ProgramCandidate:
        """Run the experiment and save the best evolved program to artifacts."""
        if self.config.run_settings.mock_mode:
            client = MockAlphaEvolveClient(seed_code=self.config.seed_code)
        else:
            client = AlphaEvolveClient(
                project_id=self.config.project_id,
                location=self.config.location,
                collection=self.config.collection,
                engine_id=self.config.engine_id,
                assistant_id=self.config.assistant_id,
            )

        controller = EvolutionController(
            config=self.config,
            client=client,
            evaluator_fn=self.evaluator_fn,
            target_function_name=self.target_function_name,
            primary_metric=self.primary_metric,
        )

        best_candidate = controller.run()

        # Save best program artifact
        out_dir = Path(output_dir)
        export_artifact(out_dir, "best_evolved_program.py", best_candidate.code)
        if best_candidate.evaluation_result:
            summary = {
                "program_id": best_candidate.program_id,
                "scores": best_candidate.evaluation_result.scores.to_dict(),
                "insights": best_candidate.evaluation_result.insights.to_dict(),
                "execution_time_s": best_candidate.evaluation_result.execution_time_s,
            }
            import json

            export_artifact(out_dir, "best_evaluation_summary.json", json.dumps(summary, indent=2))

        return best_candidate
