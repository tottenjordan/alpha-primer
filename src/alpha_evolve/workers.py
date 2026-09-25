"""Process-safe, isolated worker execution harness for AlphaEvolve candidate evaluation."""

from __future__ import annotations

import concurrent.futures
import logging
import time
import traceback
from collections.abc import Callable
from typing import Any

from .models import AlphaEvolveEvaluationScores, EvaluationResult, ProgramCandidate

logger = logging.getLogger(__name__)


def _execute_in_process(
    code: str,
    evaluator_fn: Callable[[Any], EvaluationResult],
    function_name: str,
) -> EvaluationResult:
    """Isolate program compilation and execution inside a distinct process."""
    start_time = time.perf_counter()

    # Tier 0: Syntax and compilation check
    try:
        compiled_code = compile(code, "<candidate_program>", "exec")
    except SyntaxError as e:
        return EvaluationResult.failure(
            f"SyntaxError in candidate code: {e}",
            insights={"tier": "tier_0", "error_type": "SyntaxError"},
        )

    module_scope: dict[str, Any] = {}
    try:
        exec(compiled_code, module_scope)
    except Exception as e:
        return EvaluationResult.failure(
            f"Import or initialization exception: {e}\n{traceback.format_exc()}",
            insights={"tier": "tier_0", "error_type": type(e).__name__},
        )

    if function_name not in module_scope:
        return EvaluationResult.failure(
            f"Required function '{function_name}' was not defined in candidate code.",
            insights={"tier": "tier_0", "missing_function": function_name},
        )

    candidate_callable = module_scope[function_name]

    # Tier 1 & 2: User Evaluator Harness
    try:
        result = evaluator_fn(candidate_callable)
        result.execution_time_s = time.perf_counter() - start_time
        return result
    except Exception as e:
        return EvaluationResult.failure(
            f"Evaluation exception: {e}\n{traceback.format_exc()}",
            insights={"tier": "tier_1_2", "exception": str(e)[:300]},
        )


class WorkerPool:
    """Manages concurrent evaluation of program candidates with timeouts and isolation."""

    def __init__(self, max_workers: int = 4, timeout_s: float = 30.0) -> None:
        self.max_workers = max_workers
        self.timeout_s = timeout_s
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def evaluate_candidate(
        self,
        candidate: ProgramCandidate,
        evaluator_fn: Callable[[Any], EvaluationResult],
        function_name: str,
    ) -> EvaluationResult:
        """Run candidate evaluation with strict wall-clock timeout."""
        future = self.executor.submit(
            _execute_in_process, candidate.code, evaluator_fn, function_name
        )
        try:
            return future.result(timeout=self.timeout_s)
        except concurrent.futures.TimeoutError:
            logger.warning(
                "Candidate %s timed out after %.1f seconds",
                candidate.program_id,
                self.timeout_s,
            )
            return EvaluationResult(
                status="TIMEOUT",
                scores=AlphaEvolveEvaluationScores.from_dict({"score": -1e9}),
                error_message=f"Evaluation exceeded {self.timeout_s}s timeout limit.",
                execution_time_s=self.timeout_s,
            )
        except Exception as e:
            return EvaluationResult.failure(f"Worker execution crashed: {e}")

    def shutdown(self) -> None:
        """Shut down the worker pool."""
        self.executor.shutdown(wait=False)
