"""Utility functions for code parsing, AST complexity analysis, and artifact export."""

from __future__ import annotations

import ast
import re
from pathlib import Path


def extract_evolve_blocks(code: str) -> list[str]:
    """Extract code chunks marked between # EVOLVE-BLOCK-START and # EVOLVE-BLOCK-END."""
    pattern = re.compile(
        r"#\s*EVOLVE-BLOCK-START\s*\n(.*?)\n\s*#\s*EVOLVE-BLOCK-END",
        re.DOTALL,
    )
    return pattern.findall(code)


def compute_code_complexity(code: str) -> dict[str, int]:
    """Calculate structural complexity metrics (AST node count, line count, function count).

    Returns:
        Dictionary with 'ast_nodes', 'line_count', and 'function_count'.
    """
    lines = [
        line.strip() for line in code.splitlines() if line.strip() and not line.startswith("#")
    ]
    line_count = len(lines)

    try:
        tree = ast.parse(code)
        ast_nodes = sum(1 for _ in ast.walk(tree))
        function_count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    except SyntaxError:
        ast_nodes = -1
        function_count = 0

    return {
        "ast_nodes": ast_nodes,
        "line_count": line_count,
        "function_count": function_count,
    }


def load_file_content(path: str | Path) -> str:
    """Read full text from a given file path."""
    return Path(path).read_text(encoding="utf-8")


def export_artifact(output_dir: str | Path, filename: str, content: str) -> Path:
    """Save text content to an artifact directory, creating parent directories if needed."""
    out_path = Path(output_dir) / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path
