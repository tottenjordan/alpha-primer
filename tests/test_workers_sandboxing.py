"""Unit tests for process and subprocess sandboxing in WorkerPool."""

from __future__ import annotations

import time
from typing import Any

from alpha_evolve.models import (
    AlphaEvolveEvaluationInsights,
    AlphaEvolveEvaluationScores,
    EvaluationResult,
    ProgramCandidate,
)
from alpha_evolve.workers import SandboxConfig, WorkerPool


def _simple_evaluator(candidate_callable: Any) -> EvaluationResult:
    """Module-level picklable evaluator for testing."""
    val = float(candidate_callable(10))
    return EvaluationResult(
        status="SUCCESS",
        scores=AlphaEvolveEvaluationScores.from_dict({"score": val}),
        insights=AlphaEvolveEvaluationInsights.from_dict({"diag": "ok"}),
        execution_time_s=0.01,
    )


def test_process_sandbox_normal_execution() -> None:
    pool = WorkerPool(
        max_workers=2,
        timeout_s=5.0,
        sandbox_config=SandboxConfig(timeout_s=5.0, sandbox_mode="process"),
    )
    try:
        cand = ProgramCandidate(
            program_id="test/cand_01",
            code="def compute(x: int) -> int:\n    return x * 3\n",
        )
        result = pool.evaluate_candidate(cand, _simple_evaluator, "compute")
        assert result.status == "SUCCESS"
        assert result.scores.to_dict()["score"] == 30.0
        assert result.insights.to_dict()["diag"] == "ok"
    finally:
        pool.shutdown()


def test_process_sandbox_infinite_loop_timeout_and_kill() -> None:
    pool = WorkerPool(
        max_workers=2,
        timeout_s=0.5,
        sandbox_config=SandboxConfig(timeout_s=0.5, sandbox_mode="process"),
    )
    try:
        cand = ProgramCandidate(
            program_id="test/infinite_loop",
            code="""
def compute(x: int) -> int:
    while True:
        pass
    return x
""",
        )
        start = time.perf_counter()
        result = pool.evaluate_candidate(cand, _simple_evaluator, "compute")
        elapsed = time.perf_counter() - start

        assert result.status == "TIMEOUT"
        assert result.scores.to_dict()["score"] == -1e9
        assert "timeout" in (result.error_message or "").lower()
        # Ensure it didn't block significantly past timeout
        assert elapsed < 2.5
    finally:
        pool.shutdown()


def test_process_sandbox_hard_crash_exit_isolation() -> None:
    pool = WorkerPool(
        max_workers=2,
        timeout_s=5.0,
        sandbox_config=SandboxConfig(timeout_s=5.0, sandbox_mode="process"),
    )
    try:
        cand = ProgramCandidate(
            program_id="test/hard_crash",
            code="""
import os
def compute(x: int) -> int:
    os._exit(42)
""",
        )
        result = pool.evaluate_candidate(cand, _simple_evaluator, "compute")
        assert result.status == "FAILED"
        assert "42" in (result.error_message or "") or "42" in result.insights.to_dict().get(
            "exitcode", ""
        )
        assert result.insights.to_dict().get("tier") == "sandbox_crash"
    finally:
        pool.shutdown()


def test_process_sandbox_memory_limit() -> None:
    # 100MB memory limit
    pool = WorkerPool(
        max_workers=1,
        timeout_s=5.0,
        sandbox_config=SandboxConfig(timeout_s=5.0, max_memory_mb=100, sandbox_mode="process"),
    )
    try:
        cand = ProgramCandidate(
            program_id="test/oom",
            code="""
def compute(x: int) -> int:
    # Attempt allocating 300MB
    data = bytearray(300 * 1024 * 1024)
    return len(data)
""",
        )
        result = pool.evaluate_candidate(cand, _simple_evaluator, "compute")
        # On Linux with RLIMIT_AS, should raise MemoryError or exit abnormal
        assert result.status == "FAILED"
        assert "memory" in (result.error_message or "").lower() or result.insights.to_dict().get(
            "tier"
        ) in {"sandbox_crash", "sandbox_memory"}
    finally:
        pool.shutdown()


def test_unpicklable_evaluator_fallback_to_thread() -> None:
    pool = WorkerPool(
        max_workers=1,
        timeout_s=5.0,
        sandbox_config=SandboxConfig(timeout_s=5.0, sandbox_mode="process"),
    )
    try:
        offset = 7

        def local_closure_evaluator(candidate_callable: Any) -> EvaluationResult:
            # References local closure variable 'offset' (unpicklable in standard pickle)
            val = float(candidate_callable(5)) + offset
            return EvaluationResult(
                status="SUCCESS",
                scores=AlphaEvolveEvaluationScores.from_dict({"score": val}),
                insights=AlphaEvolveEvaluationInsights.from_dict({"type": "closure"}),
                execution_time_s=0.01,
            )

        cand = ProgramCandidate(
            program_id="test/closure",
            code="def compute(x: int) -> int:\n    return x + 1\n",
        )
        # Should gracefully detect unpicklable closure and evaluate in fallback thread
        result = pool.evaluate_candidate(cand, local_closure_evaluator, "compute")
        assert result.status == "SUCCESS"
        assert result.scores.to_dict()["score"] == 13.0
    finally:
        pool.shutdown()


def test_worker_pool_parallel_sandboxing() -> None:
    pool = WorkerPool(
        max_workers=3,
        timeout_s=5.0,
        sandbox_config=SandboxConfig(timeout_s=5.0, sandbox_mode="process"),
    )
    try:
        candidates = [
            ProgramCandidate(
                program_id=f"test/cand_{i}",
                code=f"def compute(x: int) -> int:\n    return x + {i}\n",
            )
            for i in range(3)
        ]
        results = [pool.evaluate_candidate(c, _simple_evaluator, "compute") for c in candidates]
        for i, res in enumerate(results):
            assert res.status == "SUCCESS"
            assert res.scores.to_dict()["score"] == 10.0 + i
    finally:
        pool.shutdown()
