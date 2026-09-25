"""Controller coordinating the evolutionary optimization loop between API and local evaluators."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.table import Table

from .client import AlphaEvolveClient, MockAlphaEvolveClient
from .models import (
    AlphaEvolveEvaluationSubmission,
    AlphaEvolveProgramEvaluation,
    EvaluationResult,
    ExperimentConfig,
    ProgramCandidate,
)
from .workers import WorkerPool

logger = logging.getLogger(__name__)
console = Console()


class EvolutionController:
    """Orchestrates candidate acquisition, parallel evaluation, score submission, and tracking."""

    def __init__(
        self,
        config: ExperimentConfig,
        client: AlphaEvolveClient | MockAlphaEvolveClient,
        evaluator_fn: Callable[[Any], EvaluationResult],
        target_function_name: str,
        primary_metric: str = "cost_reduction_pct",
    ) -> None:
        self.config = config
        self.client = client
        self.evaluator_fn = evaluator_fn
        self.target_function_name = target_function_name
        self.primary_metric = primary_metric

        self.worker_pool = WorkerPool(
            max_workers=config.run_settings.parallel_workers,
            timeout_s=config.run_settings.max_evaluation_time_s,
        )

        self.candidates_history: list[ProgramCandidate] = []
        self.best_candidate: ProgramCandidate | None = None
        self.best_score: float = -float("inf")

    def run(self) -> ProgramCandidate:
        """Execute the end-to-end evolutionary search loop."""
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
            f"   Baseline {self.primary_metric}: [bold]{baseline_score:+.2f}%[/bold] "
            f"(Runtime: {seed_eval.execution_time_s:.2f}s)"
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
            f"{baseline_score:+.2f}%",
            f"{self.best_score:+.2f}%",
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
                    curr_score = score_map.get(self.primary_metric, -1e9)

                    is_new_best = curr_score > self.best_score
                    if is_new_best:
                        self.best_score = curr_score
                        self.best_candidate = cand

                    table.add_row(
                        str(evaluated_count - 1),
                        cand.program_id.split("/")[-1],
                        f"[{'green' if eval_res.status == 'SUCCESS' else 'red'}]{eval_res.status}[/]",
                        f"{curr_score:+.2f}%" if curr_score > -1e8 else "ERR",
                        f"{self.best_score:+.2f}%",
                        f"{eval_res.execution_time_s:.2f}",
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

        console.print(table)
        console.print(
            f"\n[bold green]✅ Evolution Completed![/bold green] Total Evaluated: {evaluated_count} programs."
        )
        console.print(
            f"🏆 Best {self.primary_metric}: [bold green]{self.best_score:+.2f}%[/bold green] "
            f"(Candidate: {self.best_candidate.program_id if self.best_candidate else 'None'})"
        )

        return self.best_candidate or seed_candidate
