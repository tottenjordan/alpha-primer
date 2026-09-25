"""Unit tests for AST complexity analysis and evolve block extraction."""

from __future__ import annotations

from alpha_evolve.utils import compute_code_complexity, extract_evolve_blocks


def test_extract_evolve_blocks() -> None:
    sample_code = """
import numpy as np

# EVOLVE-BLOCK-START
def target_func():
    return 42
# EVOLVE-BLOCK-END

def other_func():
    pass
"""
    blocks = extract_evolve_blocks(sample_code)
    assert len(blocks) == 1
    assert "def target_func():" in blocks[0]
    assert "return 42" in blocks[0]


def test_compute_code_complexity() -> None:
    valid_code = """
def func_a(x):
    return x * 2

def func_b(y):
    return y + 1
"""
    complexity = compute_code_complexity(valid_code)
    assert complexity["ast_nodes"] > 0
    assert complexity["function_count"] == 2
    assert complexity["line_count"] == 4

    invalid_code = "def syntax_error("
    bad_complexity = compute_code_complexity(invalid_code)
    assert bad_complexity["ast_nodes"] == -1
