"""Automated tests for Cloud Run deployment automation, scripts, and container specs."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_deploy_script_help_flag() -> None:
    """Verify scripts/deploy_cloud_run.sh prints help and exits with status 0."""
    script_path = ROOT_DIR / "scripts" / "deploy_cloud_run.sh"
    assert script_path.exists()
    assert script_path.is_file()

    result = subprocess.run(
        ["bash", str(script_path), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Usage: deploy_cloud_run.sh" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--register-agent" in result.stdout
    assert "--engine-id" in result.stdout


def test_deploy_script_dry_run_execution() -> None:
    """Verify scripts/deploy_cloud_run.sh --dry-run synthesizes correct gcloud commands."""
    script_path = ROOT_DIR / "scripts" / "deploy_cloud_run.sh"
    result = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--project=test-project-123",
            "--region=us-central1",
            "--service-name=test-alpha-ui",
            "--engine-id=test-engine-999",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    output = result.stdout
    assert "Project:        test-project-123" in output
    assert "Region:         us-central1" in output
    assert "Service:        test-alpha-ui" in output
    assert "Engine ID:      test-engine-999" in output
    assert "Dry Run Mode:   true" in output

    # Check key synthesized gcloud and curl lines
    assert "gcloud artifacts repositories describe alpha-evolve-repo" in output
    assert "gcloud builds submit --project=test-project-123" in output
    assert "gcloud run deploy test-alpha-ui" in output
    assert "--memory=512Mi" in output
    assert "--concurrency=80" in output
    assert "discoveryengine.googleapis.com/v1alpha/projects/test-project-123" in output
    assert "agentId=inventory-replenishment-twin" in output


def test_cloudbuild_yaml_structure() -> None:
    """Verify cloudbuild.yaml exists and defines expected build and deploy steps."""
    cloudbuild_path = ROOT_DIR / "cloudbuild.yaml"
    assert cloudbuild_path.exists()

    content = cloudbuild_path.read_text(encoding="utf-8")
    assert "build-image" in content
    assert "deploy-cloud-run" in content
    assert "alpha-evolve-repo" in content
    assert "_SERVICE_NAME" in content
    assert "_REGION" in content
    assert "_ALLOW_UNAUTHENTICATED" in content


def test_github_deploy_workflow_structure() -> None:
    """Verify .github/workflows/deploy.yml exists and defines correct dispatch triggers."""
    workflow_path = ROOT_DIR / ".github" / "workflows" / "deploy.yml"
    assert workflow_path.exists()

    content = workflow_path.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "google-github-actions/auth" in content
    assert "google-github-actions/setup-gcloud" in content
    assert "deploy_cloud_run.sh" in content
    assert "Pre-Deployment Verification" in content


def test_dockerfile_security_and_non_root() -> None:
    """Verify Dockerfile uses non-root user and installs uv frozen dependencies."""
    dockerfile_path = ROOT_DIR / "Dockerfile"
    assert dockerfile_path.exists()

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in content
    assert "uv sync --frozen --no-dev" in content
    assert "useradd -m -u 1000 appuser" in content
    assert "USER appuser" in content
    assert "EXPOSE 8080" in content
    assert 'CMD ["python", "server.py"]' in content
