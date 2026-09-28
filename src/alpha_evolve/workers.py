"""Process-safe, isolated worker execution harness for AlphaEvolve candidate evaluation."""

from __future__ import annotations

import concurrent.futures
import logging
import multiprocessing
import os
import pickle
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .models import (
    AlphaEvolveEvaluationInsights,
    AlphaEvolveEvaluationScores,
    EvaluationResult,
    ProgramCandidate,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for candidate execution sandboxing."""

    timeout_s: float = 30.0
    max_memory_mb: int = 2048
    sandbox_mode: Literal["process", "subprocess", "thread"] = "process"


def _sandbox_child_worker(
    code: str,
    evaluator_bytes: bytes,
    function_name: str,
    max_memory_mb: int,
    result_queue: Any,
) -> None:
    """Isolated child process entrypoint executed under spawn context."""
    # Apply virtual memory limit on POSIX systems
    if max_memory_mb > 0:
        try:
            import resource

            bytes_limit = max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))
        except (ImportError, ValueError, OSError):
            pass

    start_time = time.perf_counter()

    # Tier 0: Syntax and compilation check
    try:
        compiled_code = compile(code, "<candidate_program>", "exec")
    except SyntaxError as e:
        res = EvaluationResult.failure(
            f"SyntaxError in candidate code: {e}",
            insights={"tier": "tier_0", "error_type": "SyntaxError"},
        )
        result_queue.put(pickle.dumps(res))
        return

    module_scope: dict[str, Any] = {}
    try:
        exec(compiled_code, module_scope)
    except MemoryError:
        res = EvaluationResult.failure(
            f"MemoryError during candidate initialization (exceeded {max_memory_mb}MB limit).",
            insights={"tier": "sandbox_memory", "error_type": "MemoryError"},
        )
        result_queue.put(pickle.dumps(res))
        return
    except Exception as e:
        res = EvaluationResult.failure(
            f"Import or initialization exception: {e}\n{traceback.format_exc()}",
            insights={"tier": "tier_0", "error_type": type(e).__name__},
        )
        result_queue.put(pickle.dumps(res))
        return

    if function_name not in module_scope:
        res = EvaluationResult.failure(
            f"Required function '{function_name}' was not defined in candidate code.",
            insights={"tier": "tier_0", "missing_function": function_name},
        )
        result_queue.put(pickle.dumps(res))
        return

    candidate_callable = module_scope[function_name]

    try:
        evaluator_fn = pickle.loads(evaluator_bytes)
    except Exception as e:
        res = EvaluationResult.failure(
            f"Failed to unpickle evaluator in child process: {e}",
            insights={"tier": "sandbox_ipc", "error": str(e)},
        )
        result_queue.put(pickle.dumps(res))
        return

    # Tier 1 & 2: User Evaluator Harness
    try:
        result = evaluator_fn(candidate_callable)
        result.execution_time_s = time.perf_counter() - start_time
        result_queue.put(pickle.dumps(result))
    except MemoryError:
        res = EvaluationResult.failure(
            f"MemoryError during candidate evaluation (exceeded {max_memory_mb}MB limit).",
            insights={"tier": "sandbox_memory", "error_type": "MemoryError"},
        )
        result_queue.put(pickle.dumps(res))
    except Exception as e:
        res = EvaluationResult.failure(
            f"Evaluation exception: {e}\n{traceback.format_exc()}",
            insights={"tier": "tier_1_2", "exception": str(e)[:300]},
        )
        result_queue.put(pickle.dumps(res))


def _execute_in_thread(
    code: str,
    evaluator_fn: Callable[[Any], EvaluationResult],
    function_name: str,
) -> EvaluationResult:
    """Execute evaluation in-thread (used for unpicklable closures or thread mode)."""
    start_time = time.perf_counter()

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

    try:
        result = evaluator_fn(candidate_callable)
        result.execution_time_s = time.perf_counter() - start_time
        return result
    except Exception as e:
        return EvaluationResult.failure(
            f"Evaluation exception: {e}\n{traceback.format_exc()}",
            insights={"tier": "tier_1_2", "exception": str(e)[:300]},
        )


def _run_in_process_sandbox(
    code: str,
    evaluator_fn: Callable[[Any], EvaluationResult],
    function_name: str,
    config: SandboxConfig,
) -> EvaluationResult:
    """Execute candidate in a dedicated spawned child process with unblockable timeout."""
    try:
        evaluator_bytes = pickle.dumps(evaluator_fn)
    except Exception as e:
        logger.debug("Evaluator callable cannot be pickled (%s); falling back to thread.", e)
        return _execute_in_thread(code, evaluator_fn, function_name)

    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()

    proc = ctx.Process(
        target=_sandbox_child_worker,
        args=(
            code,
            evaluator_bytes,
            function_name,
            config.max_memory_mb,
            result_queue,
        ),
    )
    proc.start()
    proc.join(timeout=config.timeout_s)

    if proc.is_alive():
        logger.warning(
            "Candidate process %s exceeded timeout of %.1fs; terminating...",
            proc.pid,
            config.timeout_s,
        )
        proc.terminate()
        proc.join(timeout=0.3)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=0.3)

        return EvaluationResult(
            status="TIMEOUT",
            scores=AlphaEvolveEvaluationScores.from_dict({"score": -1e9}),
            error_message=f"Evaluation exceeded {config.timeout_s}s timeout limit.",
            execution_time_s=config.timeout_s,
            insights=AlphaEvolveEvaluationInsights.from_dict(
                {"tier": "sandbox_timeout", "timeout_s": str(config.timeout_s)}
            ),
        )

    # Process terminated. Verify exit code
    exitcode = proc.exitcode
    if exitcode is not None and exitcode != 0:
        sig_info = f"signal {-exitcode}" if exitcode < 0 else f"exitcode {exitcode}"
        return EvaluationResult.failure(
            f"Candidate process terminated abnormally ({sig_info}).",
            insights={
                "tier": "sandbox_crash",
                "exitcode": str(exitcode),
            },
        )

    try:
        if not result_queue.empty():
            serialized_res = result_queue.get_nowait()
            res = pickle.loads(serialized_res)
            if isinstance(res, EvaluationResult):
                return res
    except Exception as e:
        return EvaluationResult.failure(
            f"Failed to read result from sandbox queue: {e}",
            insights={"tier": "sandbox_ipc"},
        )

    return EvaluationResult.failure(
        "Candidate process completed without returning an evaluation result.",
        insights={"tier": "sandbox_empty"},
    )


def _subprocess_runner_main() -> None:
    """CLI runner entrypoint invoked inside an isolated subprocess via stdin/stdout."""
    try:
        raw_input = sys.stdin.buffer.read()
        payload = pickle.loads(raw_input)

        code: str = payload["code"]
        evaluator_bytes: bytes = payload["evaluator_bytes"]
        function_name: str = payload["function_name"]
        max_memory_mb: int = payload.get("max_memory_mb", 0)

        # Apply memory limit on POSIX
        if max_memory_mb > 0:
            try:
                import resource

                bytes_limit = max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))
            except (ImportError, ValueError, OSError):
                pass

        start_time = time.perf_counter()

        # Compile and execute
        compiled_code = compile(code, "<candidate_program>", "exec")
        module_scope: dict[str, Any] = {}
        exec(compiled_code, module_scope)

        if function_name not in module_scope:
            res = EvaluationResult.failure(
                f"Required function '{function_name}' was not defined in candidate code.",
                insights={"tier": "tier_0", "missing_function": function_name},
            )
            sys.stdout.buffer.write(pickle.dumps(res))
            return

        candidate_callable = module_scope[function_name]
        evaluator_fn = pickle.loads(evaluator_bytes)
        result = evaluator_fn(candidate_callable)
        result.execution_time_s = time.perf_counter() - start_time
        sys.stdout.buffer.write(pickle.dumps(result))
    except MemoryError:
        res = EvaluationResult.failure(
            "MemoryError during subprocess candidate execution.",
            insights={"tier": "sandbox_memory", "error_type": "MemoryError"},
        )
        sys.stdout.buffer.write(pickle.dumps(res))
    except Exception as e:
        res = EvaluationResult.failure(
            f"Subprocess candidate exception: {e}\n{traceback.format_exc()}",
            insights={"tier": "tier_0_or_1", "exception": str(e)[:300]},
        )
        sys.stdout.buffer.write(pickle.dumps(res))


def _run_in_subprocess_sandbox(
    code: str,
    evaluator_fn: Callable[[Any], EvaluationResult],
    function_name: str,
    config: SandboxConfig,
) -> EvaluationResult:
    """Execute candidate in a dedicated OS subprocess with unblockable timeout."""
    try:
        evaluator_bytes = pickle.dumps(evaluator_fn)
    except Exception as e:
        logger.debug("Evaluator callable cannot be pickled (%s); falling back to thread.", e)
        return _execute_in_thread(code, evaluator_fn, function_name)

    payload = pickle.dumps(
        {
            "code": code,
            "evaluator_bytes": evaluator_bytes,
            "function_name": function_name,
            "max_memory_mb": config.max_memory_mb,
        }
    )

    cmd = [
        sys.executable,
        "-c",
        "from alpha_evolve.workers import _subprocess_runner_main; _subprocess_runner_main()",
    ]

    env = os.environ.copy()
    repo_root = str(Path.cwd().resolve())
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{repo_root}:{repo_root}/tests:{pythonpath}".rstrip(":")

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except Exception as e:
        return EvaluationResult.failure(f"Failed to spawn subprocess: {e}")

    try:
        stdout_data, stderr_data = proc.communicate(input=payload, timeout=config.timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return EvaluationResult(
            status="TIMEOUT",
            scores=AlphaEvolveEvaluationScores.from_dict({"score": -1e9}),
            error_message=f"Evaluation exceeded {config.timeout_s}s timeout limit.",
            execution_time_s=config.timeout_s,
            insights=AlphaEvolveEvaluationInsights.from_dict(
                {"tier": "sandbox_timeout", "timeout_s": str(config.timeout_s)}
            ),
        )

    if proc.returncode != 0:
        stderr_text = stderr_data.decode("utf-8", errors="replace")[:300]
        return EvaluationResult.failure(
            f"Candidate subprocess terminated abnormally (exitcode {proc.returncode}). {stderr_text}",
            insights={
                "tier": "sandbox_crash",
                "exitcode": str(proc.returncode),
            },
        )

    try:
        res = pickle.loads(stdout_data)
        if isinstance(res, EvaluationResult):
            return res
    except Exception as e:
        return EvaluationResult.failure(
            f"Failed to deserialize evaluation result from subprocess: {e}",
            insights={"tier": "sandbox_ipc"},
        )

    return EvaluationResult.failure(
        "Candidate subprocess completed without returning a valid evaluation result.",
        insights={"tier": "sandbox_empty"},
    )


class WorkerPool:
    """Manages concurrent evaluation of program candidates with timeouts and isolation."""

    def __init__(
        self,
        max_workers: int = 4,
        timeout_s: float = 30.0,
        sandbox_config: SandboxConfig | None = None,
    ) -> None:
        self.max_workers = max_workers
        self.timeout_s = timeout_s
        self.sandbox_config = sandbox_config or SandboxConfig(timeout_s=timeout_s)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def evaluate_candidate(
        self,
        candidate: ProgramCandidate,
        evaluator_fn: Callable[[Any], EvaluationResult],
        function_name: str,
    ) -> EvaluationResult:
        """Run candidate evaluation in an isolated sandbox with strict wall-clock timeout."""
        if self.sandbox_config.sandbox_mode == "thread":
            future = self.executor.submit(
                _execute_in_thread, candidate.code, evaluator_fn, function_name
            )
            try:
                return future.result(timeout=self.timeout_s)
            except concurrent.futures.TimeoutError:
                return EvaluationResult(
                    status="TIMEOUT",
                    scores=AlphaEvolveEvaluationScores.from_dict({"score": -1e9}),
                    error_message=f"Evaluation exceeded {self.timeout_s}s timeout limit.",
                    execution_time_s=self.timeout_s,
                    insights=AlphaEvolveEvaluationInsights.from_dict(
                        {"tier": "sandbox_timeout", "timeout_s": str(self.timeout_s)}
                    ),
                )
            except Exception as e:
                return EvaluationResult.failure(f"Worker execution crashed: {e}")

        if self.sandbox_config.sandbox_mode == "subprocess":
            future = self.executor.submit(
                _run_in_subprocess_sandbox,
                candidate.code,
                evaluator_fn,
                function_name,
                self.sandbox_config,
            )
            try:
                return future.result(timeout=self.timeout_s + 2.0)
            except concurrent.futures.TimeoutError:
                return EvaluationResult(
                    status="TIMEOUT",
                    scores=AlphaEvolveEvaluationScores.from_dict({"score": -1e9}),
                    error_message=f"Worker supervisor exceeded {self.timeout_s}s timeout limit.",
                    execution_time_s=self.timeout_s,
                )
            except Exception as e:
                return EvaluationResult.failure(f"Worker execution crashed: {e}")

        # Process sandbox execution (default)
        future = self.executor.submit(
            _run_in_process_sandbox,
            candidate.code,
            evaluator_fn,
            function_name,
            self.sandbox_config,
        )
        try:
            return future.result(timeout=self.timeout_s + 2.0)
        except concurrent.futures.TimeoutError:
            return EvaluationResult(
                status="TIMEOUT",
                scores=AlphaEvolveEvaluationScores.from_dict({"score": -1e9}),
                error_message=f"Worker supervisor exceeded {self.timeout_s}s timeout limit.",
                execution_time_s=self.timeout_s,
            )
        except Exception as e:
            return EvaluationResult.failure(f"Worker execution crashed: {e}")

    def shutdown(self) -> None:
        """Shut down the worker pool."""
        self.executor.shutdown(wait=False, cancel_futures=True)
