# Alpha Primer Project Context & Agent Rules

## Core Rule: Code Standards Compliance

> [!IMPORTANT]
> **Always refer to [CODE_STANDARDS.md](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/CODE_STANDARDS.md) before writing code, modifying dependencies, adding tests, or making environment changes.** All contributions must strictly comply with the guidelines defined there.

---

## Key Constraints & Tooling

1. **Python & Package Management**:
   - Use `uv` for all dependency management (`uv add`, `uv remove`, `uv sync`). Never use bare `pip` or bare `python`.
   - Never activate virtual environments manually (`source .venv/bin/activate`). Run all commands via `uv run <cmd>`.
   - Manage development dependencies via `[dependency-groups]` (PEP 735) in `pyproject.toml`.
2. **Linting & Formatting**:
   - Use `ruff` exclusively for both linting and formatting (`uv run ruff check .`, `uv run ruff format .`). Never use `black`, `flake8`, or `isort`.
3. **Type Checking & Testing**:
   - Use `ty` for type checking (`uv run ty check src/`). Never use `mypy` or `pyright`.
   - Use `pytest` for all test execution (`uv run pytest`).
4. **Git Operations**:
   - Work on a branch; `main` is merged via PR.
   - Commit frequently (one logical change per commit), ensuring every commit leaves the test suite green.
   - Commit or push **only when explicitly asked**.
   - **Never** add `Co-Authored-By` trailers in commits or PR descriptions.
   - Follow Conventional Commits formatting.
5. **Session Notes & Collaboration**:
   - Document cross-session, non-recoverable insights under `docs/notes/` organized by topic.
   - Keep the top-level index [docs/notes/README.md](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/docs/notes/README.md) under 200 lines and link key files and single-topic note files.
   - Verify files/flags exist before documenting or acting on them.
