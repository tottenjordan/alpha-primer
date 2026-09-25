# Code Standards & Engineering Guidelines

This repository hosts end-to-end code examples demonstrating how to architect and implement AlphaEvolve with Gemini Enterprise to solve practical use cases (e.g., multi-echelon and perishable inventory replenishment digital twins). All code, contributions, and environment management in this repository must strictly adhere to the following standards.

---

## 1. Python Environment & Package Management

We adhere to the modern Python ecosystem standards (based on the `modern-python` skill):

- **Build & Package Management (`uv`)**:
  - Always use `uv` for all package and dependency management.
  - **NEVER** use bare `pip install` or bare `python`.
  - Add/remove dependencies using `uv add <package>` and `uv remove <package>`. Never manually hand-edit dependency blocks in `pyproject.toml`.
  - Use `[dependency-groups]` (PEP 735) for development, testing, and linting dependencies (e.g., `dev`, `test`), **not** `[project.optional-dependencies]`.
  - **Never** manually activate virtual environments (`source .venv/bin/activate`). Run all commands, scripts, and tools using `uv run <cmd>` (or `uv run --with <pkg> <cmd>` for ad-hoc scripts).
  - Target Python version: Modern Python `>=3.11`.
  - Standard repository layout: `src/` layout for packages, `tests/` for tests.

---

## 2. Code Quality, Linting, & Formatting

- **Linter & Formatter (`ruff`)**:
  - Use `ruff` exclusively for both linting and formatting.
  - **NEVER** use `black`, `flake8`, or `isort`.
  - Check code: `uv run ruff check .`
  - Format code: `uv run ruff format .`
  - Auto-fix issues: `uv run ruff check --fix .`
  - Maintain line length of 100 characters and target Python `>=3.11`.

---

## 3. Type Checking & Testing

- **Type Checking (`ty`)**:
  - Use `ty` (from Astral) for fast, modern type checking.
  - **NEVER** use `mypy` or `pyright`.
  - Check types: `uv run ty check src/`
- **Testing Framework (`pytest`)**:
  - Use `pytest` for all unit and integration testing.
  - Run test suite: `uv run pytest`
  - Enforce code coverage where applicable (`pytest-cov`).
  - Keep test files in `tests/` matching module hierarchy.

---

## 4. Git & Commit Guidelines

- **Branching & PRs**:
  - Always work on a branch; `main` is merged exclusively via pull request.
- **Commit Frequency & Quality**:
  - Commit frequently, one logical change per commit.
  - A commit must always leave the test suite green (`uv run pytest`, `make check`).
- **Authorization & Workflow**:
  - You do not need permission to commit and push changes to a feature branch or open PR designated for review.
  - **NEVER** push directly to `main` without explicit approval; `main` is merged strictly via PR.

- **Commit Trailers**:
  - **NEVER** add `Co-Authored-By` trailers when making commits or submitting pull requests.
- **Commit Messages**:
  - Follow the Conventional Commits specification (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
  - Keep summaries concise and imperative.

---

## 5. Collaboration & Session Notes

- **Location**: Store session notes under `docs/notes/`. Subfolders may be used for organization if needed.
- **Topic Organization**:
  - Organize notes by topic; each note file should focus on a single topic and cross-link related topics.
  - Maintain the top-level index at `docs/notes/README.md` (must remain under 200 lines).
- **Maintenance**:
  - Check for existing notes on a topic before creating new ones; update or prune stale/incorrect notes.
  - Re-verify file paths and CLI flags before acting on notes.
  - Capture non-obvious, hard-won insights (gotchas, API quirks, environment nuances) that outlive a single conversation and are not readily derivable from repo docs, git history, or `GEMINI.md`.
