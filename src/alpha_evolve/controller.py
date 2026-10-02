"""Controller coordinating the evolutionary optimization loop between API and local evaluators."""

from __future__ import annotations

import datetime
import logging
import time
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.table import Table

from .client import AlphaEvolveClient, MockAlphaEvolveClient
from .dashboard.telemetry_broker import LiveTelemetryBroker, get_global_broker
from .evaluators import BaseEvaluator, resolve_evaluator
from .models import (
    AlphaEvolveEvaluationSubmission,
    AlphaEvolveProgramEvaluation,
    EvaluationResult,
    ExperimentConfig,
    ProgramCandidate,
)
from .utils import extract_evolve_blocks
from .workers import SandboxConfig, WorkerPool

logger = logging.getLogger(__name__)
console = Console()


class EvolutionController:
    """Orchestrates candidate acquisition, parallel evaluation, score submission, and tracking."""

    def __init__(
        self,
        config: ExperimentConfig,
        client: AlphaEvolveClient | MockAlphaEvolveClient,
        evaluator: BaseEvaluator | Callable[[Any], EvaluationResult] | None = None,
        evaluator_fn: Callable[[Any], EvaluationResult] | None = None,
        target_function_name: str | None = None,
        primary_metric: str | None = None,
        telemetry_broker: LiveTelemetryBroker | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.telemetry_broker = (
            telemetry_broker if telemetry_broker is not None else get_global_broker()
        )

        (
            self.evaluator,
            self.evaluator_fn,
            self.target_function_name,
            self.primary_metric,
            self.higher_is_better,
        ) = resolve_evaluator(
            evaluator=evaluator,
            evaluator_fn=evaluator_fn,
            target_function_name=target_function_name,
            primary_metric=primary_metric,
        )

        self.worker_pool = WorkerPool(
            max_workers=config.run_settings.parallel_workers,
            timeout_s=config.run_settings.max_evaluation_time_s,
            sandbox_config=SandboxConfig(
                timeout_s=config.run_settings.max_evaluation_time_s,
                max_memory_mb=config.run_settings.max_memory_mb,
                sandbox_mode=config.run_settings.sandbox_mode,
            ),
        )

        self.candidates_history: list[ProgramCandidate] = []
        self.best_candidate: ProgramCandidate | None = None
        self.best_score: float = -float("inf") if self.higher_is_better else float("inf")

    def _is_better(self, candidate_score: float, reference_score: float) -> bool:
        """Compare candidate_score against reference_score honoring higher_is_better."""
        if self.higher_is_better:
            return candidate_score > reference_score
        return candidate_score < reference_score

    def _format_score(self, score: float) -> str:
        """Format metric value with '%' suffix only when metric name ends with '_pct'."""
        suffix = "%" if self.primary_metric.endswith("_pct") else ""
        return f"{score:+.2f}{suffix}"

    def run(self) -> ProgramCandidate:
        """Execute the end-to-end evolutionary search loop."""
        if isinstance(self.evaluator, BaseEvaluator):
            self.evaluator.setup()

        console.print(
            f"[bold cyan]🚀 Starting AlphaEvolve Optimization:[/bold cyan] {self.config.experiment_name}"
        )
        console.print(
            f"   Target Metric: [bold green]{self.primary_metric}[/bold green] | "
            f"Max Programs: [bold yellow]{self.config.run_settings.max_programs}[/bold yellow] | "
            f"Workers: [bold magenta]{self.config.run_settings.parallel_workers}[/bold magenta]"
        )

        session_name = self.client.create_session()
        exp_name = self.client.create_experiment(session_name, self.config)
        console.print(f"   Created Experiment: [dim]{exp_name}[/dim]")

        # Broadcast run_started event
        self.telemetry_broker.publish(
            {
                "event_type": "run_started",
                "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                "data": {
                    "experiment_name": self.config.experiment_name,
                    "experiment_id": exp_name,
                    "max_programs": self.config.run_settings.max_programs,
                    "primary_metric": self.primary_metric,
                    "target_function_name": self.target_function_name,
                },
            }
        )

        # Step 1: Evaluate baseline seed program
        console.print(
            "\n[bold yellow]Step 1: Evaluating Initial Seed Program Baseline...[/bold yellow]"
        )
        seed_candidate = ProgramCandidate(
            program_id=f"{exp_name}/alphaEvolvePrograms/seed_program",
            code=self.config.seed_code,
            iteration=0,
        )
        seed_eval = self.worker_pool.evaluate_candidate(
            seed_candidate, self.evaluator_fn, self.target_function_name
        )
        seed_candidate.evaluation_result = seed_eval
        self.candidates_history.append(seed_candidate)

        baseline_score = seed_eval.scores.to_dict().get(self.primary_metric, 0.0)
        self.best_candidate = seed_candidate
        self.best_score = baseline_score

        console.print(
            f"   Baseline {self.primary_metric}: [bold]{self._format_score(baseline_score)}[/bold] "
            f"(Runtime: {seed_eval.execution_time_s:.2f}s)"
        )

        seed_blocks = extract_evolve_blocks(self.config.seed_code)
        self.telemetry_broker.publish(
            {
                "event_type": "candidate_evaluated",
                "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                "data": {
                    "iteration": 0,
                    "program_id": seed_candidate.program_id,
                    "status": seed_eval.status,
                    "score": baseline_score,
                    "scores": seed_eval.scores.to_dict(),
                    "insights": seed_eval.insights.to_dict(),
                    "execution_time_s": seed_eval.execution_time_s,
                    "is_best": True,
                    "is_baseline": True,
                    "evolve_block": seed_blocks[0] if seed_blocks else "",
                },
            }
        )

        # Register seed program and start experiment
        initial_prog_name = self.client.create_initial_program(
            exp_name, self.config.seed_code, baseline_score=baseline_score
        )
        self.client.start_experiment(exp_name, initial_prog_name)

        # Step 2: Evolutionary Candidate Loop
        console.print("\n[bold green]Step 2: Entering Evolutionary Loop...[/bold green]")
        evaluated_count = 1  # includes seed
        consecutive_empty = 0

        table = Table(title="AlphaEvolve Progress")
        table.add_column("Iter", justify="right", style="cyan")
        table.add_column("Program ID", style="dim")
        table.add_column("Status", justify="center")
        table.add_column(f"{self.primary_metric}", justify="right")
        table.add_column("Best So Far", justify="right", style="bold green")
        table.add_column("Time (s)", justify="right")

        table.add_row(
            "0",
            "seed_program",
            f"[{'green' if seed_eval.status == 'SUCCESS' else 'red'}]{seed_eval.status}[/]",
            self._format_score(baseline_score),
            self._format_score(self.best_score),
            f"{seed_eval.execution_time_s:.2f}",
        )

        try:
            while evaluated_count < self.config.run_settings.max_programs:
                batch_size = min(
                    self.config.run_settings.parallel_workers,
                    self.config.run_settings.max_programs - evaluated_count,
                )
                candidates = self.client.acquire_programs(exp_name, count=batch_size)

                if not candidates:
                    consecutive_empty += 1
                    if consecutive_empty * 5 > self.config.run_settings.idle_timeout_s:
                        console.print(
                            "[yellow]Idle timeout reached while waiting for new candidates.[/yellow]"
                        )
                        break
                    time.sleep(5.0)
                    continue

                consecutive_empty = 0
                submissions: list[AlphaEvolveEvaluationSubmission] = []

                for cand in candidates:
                    eval_res = self.worker_pool.evaluate_candidate(
                        cand, self.evaluator_fn, self.target_function_name
                    )
                    cand.evaluation_result = eval_res
                    self.candidates_history.append(cand)
                    evaluated_count += 1

                    score_map = eval_res.scores.to_dict()
                    fallback_score = -1e9 if self.higher_is_better else 1e9
                    has_valid_score = (
                        eval_res.status == "SUCCESS" and self.primary_metric in score_map
                    )
                    curr_score = (
                        score_map[self.primary_metric] if has_valid_score else fallback_score
                    )

                    is_new_best = has_valid_score and self._is_better(curr_score, self.best_score)
                    if is_new_best:
                        self.best_score = curr_score
                        self.best_candidate = cand

                    table.add_row(
                        str(evaluated_count - 1),
                        cand.program_id.split("/")[-1],
                        f"[{'green' if eval_res.status == 'SUCCESS' else 'red'}]{eval_res.status}[/]",
                        self._format_score(curr_score) if has_valid_score else "ERR",
                        self._format_score(self.best_score),
                        f"{eval_res.execution_time_s:.2f}",
                    )

                    cand_blocks = extract_evolve_blocks(cand.code)
                    self.telemetry_broker.publish(
                        {
                            "event_type": "candidate_evaluated",
                            "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                            "data": {
                                "iteration": evaluated_count - 1,
                                "program_id": cand.program_id,
                                "status": eval_res.status,
                                "score": curr_score,
                                "scores": score_map,
                                "insights": eval_res.insights.to_dict(),
                                "execution_time_s": eval_res.execution_time_s,
                                "is_best": is_new_best,
                                "best_score": self.best_score,
                                "is_baseline": False,
                                "evolve_block": cand_blocks[0] if cand_blocks else "",
                            },
                        }
                    )

                    submissions.append(
                        AlphaEvolveEvaluationSubmission(
                            program=cand.program_id,
                            lockToken=cand.lock_token,
                            evaluation=AlphaEvolveProgramEvaluation(
                                scores=eval_res.scores,
                                insights=eval_res.insights,
                            ),
                        )
                    )

                self.client.submit_evaluations(exp_name, submissions)
                time.sleep(1.0)

        finally:
            self.worker_pool.shutdown()
            if isinstance(self.evaluator, BaseEvaluator):
                self.evaluator.teardown()

        self.telemetry_broker.publish(
            {
                "event_type": "run_completed",
                "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                "data": {
                    "experiment_id": exp_name,
                    "best_score": self.best_score,
                    "best_program_id": self.best_candidate.program_id
                    if self.best_candidate
                    else None,
                    "evaluated_count": evaluated_count,
                },
            }
        )

        console.print(table)
        console.print(
            f"\n[bold green]✅ Evolution Completed![/bold green] Total Evaluated: {evaluated_count} programs."
        )
        console.print(
            f"🏆 Best {self.primary_metric}: [bold green]{self._format_score(self.best_score)}[/bold green] "
            f"(Candidate: {self.best_candidate.program_id if self.best_candidate else 'None'})"
        )

        return self.best_candidate or seed_candidate
