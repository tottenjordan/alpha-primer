# Fully Automate Deployment of Web Dashboard & Gemini Enterprise Agent Webhook to Google Cloud Run

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Provide end-to-end, reproducible automation for packaging, deploying, and verifying the AlphaEvolve interactive web dashboard and Gemini Enterprise agent webhook on Google Cloud Run, with bidirectional integration into Discovery Engine v1alpha and full CI/CD deployment automation.

**Architecture:** A multi-stage, non-root Docker container (`python:3.12-slim` + `uv`) hosts `server.py`, serving the Safe DOM Retina Canvas 2D dashboard and the `/api/agent/replenish-query` webhook. Deployment is automated via an idempotent shell utility (`scripts/deploy_cloud_run.sh`) supporting both Cloud Build and direct image deployment, optional automated registration of the Cloud Run endpoint as an External Agent in Discovery Engine v1alpha (`projects/.../assistants/default_assistant/agents/`), a declarative `cloudbuild.yaml` build pipeline, a GitHub Actions deployment workflow (`.github/workflows/deploy.yml`), and dedicated automated tests verifying deployment configurations and webhook contract adherence.

**Tech Stack:** Google Cloud Run, Google Cloud Build, Google Discovery Engine v1alpha (Gemini Enterprise), Docker, GitHub Actions, Python 3.12, `uv`, `pytest`, `ruff`, `ty`.

---

## User Review Required

> [!IMPORTANT]
> **Cloud Run IAM & Public vs. Private Ingress**:
> - By default, `scripts/deploy_cloud_run.sh` sets `--allow-unauthenticated` so the interactive C-Suite dashboard is immediately viewable in a browser.
> - For enterprise VPC-SC or strictly internal environments, the deployment script accepts `ALLOW_UNAUTHENTICATED=false`, requiring Google Cloud IAM (`roles/run.invoker`) or Identity-Aware Proxy (IAP) authentication.

> [!IMPORTANT]
> **Discovery Engine External Agent Registration**:
> - Registration of the Cloud Run endpoint (`/api/agent/replenish-query`) with Discovery Engine v1alpha requires an existing Discovery Engine instance (`projects/{PROJECT_ID}/locations/global/collections/default_collection/engines/{ENGINE_ID}`).
> - When `ENGINE_ID` is provided (or configured via environment variables), the deployment automation will automatically register or update the agent via the REST API `POST/PATCH .../assistants/default_assistant/agents?agentId=inventory-replenishment-twin`.
> - If `ENGINE_ID` is not specified, this step gracefully skips with clear instructions, preventing pipeline failures in environments without an active Discovery Engine instance.

---

## Proposed Changes & File Layout

### Component 1: Deployment Engine & CLI Automation (`scripts/` and root)

#### [MODIFY] `scripts/deploy_cloud_run.sh`
- Enhance with:
  - Robust option parsing (`--project`, `--region`, `--service-name`, `--image-tag`, `--engine-id`, `--register-agent`, `--dry-run`, `--no-allow-unauthenticated`).
  - Pre-flight validation verifying `gcloud` authentication, project access, and required API enablement (`run.googleapis.com`, `cloudbuild.googleapis.com`, `artifactregistry.googleapis.com`, `discoveryengine.googleapis.com`).
  - Automatic creation of an Artifact Registry repository (`alpha-evolve-repo` in region) if GCR is deprecated in target project.
  - Automated deployment of Cloud Run with tuned serverless concurrency (`--concurrency=80`, `--memory=512Mi`, `--cpu=1`, `--min-instances=0`, `--max-instances=5`, `--timeout=60s`).
  - Automated post-deployment health verification (`/health`, `/api/cloud-status`, security headers).
  - Automated Gemini Enterprise Assistant Agent registration via `curl` with ADC access token if `ENGINE_ID` is supplied.
  - Formatted output reporting service URL, dashboard link, agent webhook URL, and registration status.

#### [NEW] `cloudbuild.yaml`
- Declarative Google Cloud Build configuration file:
  - Step 1: Pre-build test & typecheck step via `uv run` or lint verification.
  - Step 2: Build container image using Kaniko / Docker build cache.
  - Step 3: Push image to Google Artifact Registry.
  - Step 4: Deploy to Google Cloud Run.
  - Step 5: (Optional) Register External Agent in Discovery Engine.

#### [NEW] `.github/workflows/deploy.yml`
- Automated GitHub Actions CD workflow:
  - Triggers on: manual dispatch (`workflow_dispatch`) with inputs (`environment`, `project_id`, `region`, `register_agent`) or release tag creation.
  - Authenticates to Google Cloud using Workload Identity Federation (WIF) or service account key secret.
  - Builds and deploys the Cloud Run service, runs smoke tests on the deployed service URL, and posts a GitHub Deployment Summary.

---

### Component 2: Gemini Enterprise Agent Webhook Contract (`server.py`)

#### [MODIFY] `server.py`
- Enhance `/api/agent/replenish-query` endpoint:
  - Support both `GET` and `POST` with JSON body queries (e.g. `{"query": "summary"}`, `{"query": "kpis"}`, `{"query": "what-if", "lead_time_delay": 2, "promo_spike": 0.2}`).
  - Return rich Markdown grounding cards formatted specifically for Gemini Enterprise StreamAssist reasoning bubbles and agent tool responses.
  - Include metadata: `agent_id`, `version`, `model_grounding`, and timestamp.
  - Add explicit Discovery Engine webhook schema verification helper for tests.

---

### Component 3: Makefile & Developer Automation

#### [MODIFY] `Makefile`
- Add frozen targets:
  - `deploy`: Runs `scripts/deploy_cloud_run.sh`.
  - `deploy-dry-run`: Runs `scripts/deploy_cloud_run.sh --dry-run`.
  - `docker-build`: Builds local Docker image `alpha-evolve-primer-ui:local`.
  - `docker-run`: Runs local container on port 8080.

---

### Component 4: Testing & Verification (`tests/`)

#### [NEW] `tests/test_deploy_automation.py`
- Unit tests validating:
  - `scripts/deploy_cloud_run.sh` syntax, flags, and dry-run output using bash check / execution.
  - `cloudbuild.yaml` YAML syntax and structure validity.
  - `.github/workflows/deploy.yml` YAML syntax and required GitHub Actions steps.
  - Dockerfile structural integrity (ensures non-root user, frozen uv sync, correct ports).
  - Enhanced `/api/agent/replenish-query` POST queries with dynamic parameter payloads.

---

### Component 5: Documentation & Architecture Notes (`docs/`)

#### [MODIFY] `docs/notes/google_cloud_run_hosting.md`
- Document the fully automated deployment script flags, `cloudbuild.yaml`, GitHub Actions CD pipeline, and Gemini Enterprise agent webhook registration flow.

#### [MODIFY] `docs/USER_GUIDE.md`
- Update Mode D: Serverless Cloud Run Deployment with the enhanced flags, automated verification, and agent registration examples.

---

## Detailed Task Breakdown

### Task 1: Enhance `server.py` Agent Webhook for Rich Gemini Enterprise Query Grounding
**Files:**
- Modify: `server.py:129-168`
- Modify: `tests/test_server.py:74-84`
- Test: `tests/test_server.py`

**Steps:**
1. Enhance `/api/agent/replenish-query` in `server.py` to handle query payloads (`query`, `lead_time_delay`, `promo_spike`) and return grounding cards.
2. Update `tests/test_server.py` to test POST payloads and dynamic agent responses.
3. Run `uv run --frozen pytest tests/test_server.py -v`.
4. Commit: `git commit -m "feat(server): expand Gemini Enterprise agent webhook grounding endpoint"`.

---

### Task 2: Build Declarative `cloudbuild.yaml` for Google Cloud Build
**Files:**
- Create: `cloudbuild.yaml`
- Modify: `Dockerfile` (verify cache friendliness and labels)

**Steps:**
1. Create `cloudbuild.yaml` with substitutions (`_SERVICE_NAME`, `_REGION`, `_ALLOW_UNAUTHENTICATED`).
2. Add steps for Docker build, Artifact Registry push, and Cloud Run deployment.
3. Validate YAML syntax.
4. Commit: `git commit -m "ci(cloudbuild): add declarative Cloud Build pipeline for Cloud Run"`.

---

### Task 3: Enhance `scripts/deploy_cloud_run.sh` with Pre-flight Checks, Agent Registration & Dry-Run Mode
**Files:**
- Modify: `scripts/deploy_cloud_run.sh`

**Steps:**
1. Add robust argument parsing (`--dry-run`, `--engine-id`, `--register-agent`, `--region`, `--project`).
2. Implement pre-flight checks: `gcloud` installed, project set, APIs enabled (`run`, `cloudbuild`, `artifactregistry`, `discoveryengine`).
3. Add automated post-deployment health check (`curl -f "${SERVICE_URL}/health"`).
4. Add Discovery Engine External Agent registration logic via `curl` to `POST /v1alpha/.../assistants/default_assistant/agents?agentId=inventory-replenishment-twin`.
5. Support `--dry-run` to print the exact execution plan without invoking cloud mutating commands.
6. Commit: `git commit -m "feat(deploy): enhance Cloud Run deployment script with preflights and agent registration"`.

---

### Task 4: Add GitHub Actions Deployment Workflow (`.github/workflows/deploy.yml`)
**Files:**
- Create: `.github/workflows/deploy.yml`
- Modify: `Makefile` (add `deploy`, `deploy-dry-run`, `docker-build`, `docker-run` targets)

**Steps:**
1. Create `.github/workflows/deploy.yml` with `workflow_dispatch` trigger, security permissions, GCP auth, and smoke verification.
2. Update `Makefile` with targets for deployment and Docker operations.
3. Commit: `git commit -m "ci(github): add automated Cloud Run deployment workflow and Makefile targets"`.

---

### Task 5: Add Automated Test Suite for Deployment Automation (`tests/test_deploy_automation.py`)
**Files:**
- Create: `tests/test_deploy_automation.py`

**Steps:**
1. Implement tests validating `cloudbuild.yaml` structure, `.github/workflows/deploy.yml` structure, `scripts/deploy_cloud_run.sh --help` and `--dry-run`, and Dockerfile configuration.
2. Run `uv run --frozen pytest tests/test_deploy_automation.py -v`.
3. Commit: `git commit -m "test(deploy): add unit tests for Cloud Run and agent webhook automation"`.

---

### Task 6: Update Documentation (`docs/USER_GUIDE.md` & `docs/notes/google_cloud_run_hosting.md`)
**Files:**
- Modify: `docs/USER_GUIDE.md`
- Modify: `docs/notes/google_cloud_run_hosting.md`

**Steps:**
1. Update `docs/USER_GUIDE.md` Section 3 (Mode D) and Section 5 (Repository Map).
2. Update `docs/notes/google_cloud_run_hosting.md` with CLI options and agent registration details.
3. Commit: `git commit -m "docs: document automated Cloud Run deployment and agent registration"`.

---

### Task 7: Full Verification & Quality Suite (`make check`)
**Steps:**
1. Run `make check` (ruff check, ruff format --check, ty check, pytest).
2. Run `scripts/deploy_cloud_run.sh --dry-run` to verify end-to-end output.
3. Verify clean git working tree and commit state.

---

## Verification Plan

### Automated Tests
- `uv run --frozen pytest tests/test_server.py tests/test_deploy_automation.py -v`
- `uv run --frozen ruff check .`
- `uv run --frozen ruff format --check .`
- `uv run --frozen ty check src/`
- `make check`

### Manual Verification
- Run `bash scripts/deploy_cloud_run.sh --dry-run --project=hybrid-vertex --region=us-central1 --engine-id=alpha-evolve-experiment-engine` to verify synthesized gcloud commands and REST agent registration payloads without side effects.
