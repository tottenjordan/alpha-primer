.PHONY: dev lint format format-check typecheck test check clean build-dashboard deploy deploy-dry-run docker-build docker-run

dev:
	uv sync --frozen --all-groups

lint:
	uv run --frozen ruff check .

format:
	uv run --frozen ruff format .

format-check:
	uv run --frozen ruff format --check .

typecheck:
	uv run --frozen ty check src/

test:
	uv run --frozen pytest -v

check: lint format-check typecheck test

build-dashboard:
	uv run --frozen python -m alpha_evolve.dashboard.trajectory_generator
	uv run --frozen python -m alpha_evolve.dashboard.build_dashboard

deploy:
	bash scripts/deploy_cloud_run.sh

deploy-dry-run:
	bash scripts/deploy_cloud_run.sh --dry-run

docker-build:
	docker build -t alpha-evolve-primer-ui:local .

docker-run:
	docker run -p 8080:8080 -e PORT=8080 alpha-evolve-primer-ui:local

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
