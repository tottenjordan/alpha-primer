.PHONY: dev lint format typecheck test check clean

dev:
	uv sync --all-groups

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run ty check src/

test:
	uv run pytest -v

check: lint format typecheck test

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
