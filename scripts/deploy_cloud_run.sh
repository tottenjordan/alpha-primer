#!/usr/bin/env bash
# Deploy the AlphaEvolve Supply Chain & Digital Twin Intelligence Suite to Google Cloud Run
# and optionally register as an external agent with Gemini Enterprise (Discovery Engine v1alpha).
set -euo pipefail

# Configuration defaults (override with environment variables or CLI flags)
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-alpha-evolve-primer-ui}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-true}"
ENGINE_ID="${ENGINE_ID:-alpha-evolve-experiment-engine}"
REGISTER_AGENT="${REGISTER_AGENT:-auto}" # auto | true | false
DRY_RUN="${DRY_RUN:-false}"

show_help() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Automated deployment of AlphaEvolve UI & Gemini Enterprise Agent Webhook to Google Cloud Run.

Options:
  --project=PROJECT_ID        Google Cloud Project ID (default: active gcloud project)
  --region=REGION             Deployment region (default: us-central1)
  --service-name=NAME         Cloud Run service name (default: alpha-evolve-primer-ui)
  --image-tag=TAG             Container image tag (default: latest)
  --engine-id=ENGINE_ID       Discovery Engine ID for Gemini Enterprise (default: alpha-evolve-experiment-engine)
  --register-agent            Force register Cloud Run webhook as Discovery Engine agent
  --no-register-agent         Skip Discovery Engine agent registration
  --no-allow-unauthenticated  Require Google Cloud IAM authentication (disable public ingress)
  --dry-run                   Print deployment plan and commands without executing cloud mutations
  -h, --help                  Show this help message and exit

Environment Variables:
  PROJECT_ID, REGION, SERVICE_NAME, IMAGE_TAG, ALLOW_UNAUTHENTICATED, ENGINE_ID, REGISTER_AGENT, DRY_RUN
EOF
}

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project=*)
      PROJECT_ID="${1#*=}"
      shift
      ;;
    --region=*)
      REGION="${1#*=}"
      shift
      ;;
    --service-name=*)
      SERVICE_NAME="${1#*=}"
      shift
      ;;
    --image-tag=*)
      IMAGE_TAG="${1#*=}"
      shift
      ;;
    --engine-id=*)
      ENGINE_ID="${1#*=}"
      shift
      ;;
    --register-agent)
      REGISTER_AGENT="true"
      shift
      ;;
    --no-register-agent)
      REGISTER_AGENT="false"
      shift
      ;;
    --no-allow-unauthenticated)
      ALLOW_UNAUTHENTICATED="false"
      shift
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      show_help >&2
      exit 1
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: PROJECT_ID is not set and could not be detected from gcloud." >&2
  echo "Usage: PROJECT_ID=my-project-id $0 or $(basename "$0") --project=my-project-id" >&2
  exit 1
fi

REPO_NAME="alpha-evolve-repo"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "=========================================================="
echo "AlphaEvolve Cloud Run & Agent Automation"
echo "Project:        ${PROJECT_ID}"
echo "Region:         ${REGION}"
echo "Service:        ${SERVICE_NAME}"
echo "Image URI:      ${IMAGE_URI}"
echo "Engine ID:      ${ENGINE_ID}"
echo "Public Access:  ${ALLOW_UNAUTHENTICATED}"
echo "Register Agent: ${REGISTER_AGENT}"
echo "Dry Run Mode:   ${DRY_RUN}"
echo "=========================================================="

if [[ "${DRY_RUN}" == "true" ]]; then
  echo ""
  echo "[DRY-RUN] Step 0: Pre-flight Checks (Skipped mutation)"
  echo "[DRY-RUN] Checking required Google Cloud APIs:"
  echo "  - run.googleapis.com"
  echo "  - cloudbuild.googleapis.com"
  echo "  - artifactregistry.googleapis.com"
  echo "  - discoveryengine.googleapis.com"
  echo ""
  echo "[DRY-RUN] Step 1: Ensure Artifact Registry Repository Exists"
  echo "  gcloud artifacts repositories describe ${REPO_NAME} --project=${PROJECT_ID} --location=${REGION} || \\"
  echo "  gcloud artifacts repositories create ${REPO_NAME} --repository-format=docker --project=${PROJECT_ID} --location=${REGION} --description=\"AlphaEvolve Container Registry\""
  echo ""
  echo "[DRY-RUN] Step 2: Build & Push Container Image via Cloud Build"
  echo "  gcloud builds submit --project=${PROJECT_ID} --tag=${IMAGE_URI} ."
  echo ""
  AUTH_FLAG="--no-allow-unauthenticated"
  if [[ "${ALLOW_UNAUTHENTICATED}" == "true" ]]; then
    AUTH_FLAG="--allow-unauthenticated"
  fi
  echo "[DRY-RUN] Step 3: Deploy to Google Cloud Run"
  echo "  gcloud run deploy ${SERVICE_NAME} \\"
  echo "    --project=${PROJECT_ID} \\"
  echo "    --region=${REGION} \\"
  echo "    --image=${IMAGE_URI} \\"
  echo "    --platform=managed \\"
  echo "    --port=8080 \\"
  echo "    --memory=512Mi \\"
  echo "    --cpu=1 \\"
  echo "    --concurrency=80 \\"
  echo "    --min-instances=0 \\"
  echo "    --max-instances=5 \\"
  echo "    --timeout=60s \\"
  echo "    ${AUTH_FLAG}"
  echo ""
  echo "[DRY-RUN] Step 4: Health Check Verification"
  echo "  curl -f -s \${SERVICE_URL}/health"
  echo ""
  echo "[DRY-RUN] Step 5: Gemini Enterprise External Agent Webhook Registration"
  echo "  curl -X POST \\"
  echo "    -H \"Authorization: Bearer \$(gcloud auth print-access-token)\" \\"
  echo "    -H \"Content-Type: application/json\" \\"
  echo "    -H \"X-Goog-User-Project: ${PROJECT_ID}\" \\"
  echo "    \"https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/global/collections/default_collection/engines/${ENGINE_ID}/assistants/default_assistant/agents?agentId=inventory-replenishment-twin\" \\"
  echo "    -d '{\"displayName\":\"Autonomous Inventory Replenishment Digital Twin\",\"description\":\"Provides live AlphaEvolve simulation metrics, spoilage reductions, and evolved heuristic code.\",\"agentEndpoint\":{\"endpointUri\":\"\${SERVICE_URL}/api/agent/replenish-query\"}}'"
  echo ""
  echo "[DRY-RUN] Plan verification complete. Run without --dry-run to execute."
  exit 0
fi

# Real Execution: Step 0 Pre-flight Checks
echo "Step 0: Checking Google Cloud Environment & Authentication..."
if ! command -v gcloud &>/dev/null; then
  echo "ERROR: gcloud CLI not found in PATH." >&2
  exit 1
fi

# Step 1: Ensure Artifact Registry Repository Exists
echo "Step 1: Ensuring Artifact Registry repository '${REPO_NAME}' exists..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" --project="${PROJECT_ID}" --location="${REGION}" &>/dev/null; then
  echo "Creating repository '${REPO_NAME}' in region '${REGION}'..."
  gcloud artifacts repositories create "${REPO_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --repository-format=docker \
    --description="AlphaEvolve Container Registry"
fi

# Step 2: Build & Push Container Image
echo "Step 2: Submitting build to Google Cloud Build..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE_URI}" \
  .

AUTH_FLAG="--no-allow-unauthenticated"
if [[ "${ALLOW_UNAUTHENTICATED}" == "true" ]]; then
  AUTH_FLAG="--allow-unauthenticated"
fi

# Step 3: Deploy to Cloud Run
echo "Step 3: Deploying container image to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --platform=managed \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=5 \
  --timeout=60s \
  ${AUTH_FLAG}

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(status.url)")

echo ""
echo "=========================================================="
echo "Step 4: Running Post-Deployment Health Verification..."
echo "Service URL: ${SERVICE_URL}"

if curl -f -s "${SERVICE_URL}/health" >/dev/null; then
  echo "✅ Health check passed (${SERVICE_URL}/health)"
else
  echo "⚠️  Health check returned non-200. Please inspect logs."
fi

# Step 5: External Agent Registration with Gemini Enterprise (Discovery Engine v1alpha)
if [[ "${REGISTER_AGENT}" != "false" && -n "${ENGINE_ID}" ]]; then
  echo "Step 5: Registering / Updating External Agent on Discovery Engine..."
  ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null || echo '')
  if [[ -n "${ACCESS_TOKEN}" ]]; then
    AGENT_URL="https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/global/collections/default_collection/engines/${ENGINE_ID}/assistants/default_assistant/agents?agentId=inventory-replenishment-twin"
    AGENT_PAYLOAD=$(cat <<JSON
{
  "displayName": "Autonomous Inventory Replenishment Digital Twin",
  "description": "Provides live AlphaEvolve simulation metrics, spoilage reductions, and evolved heuristic code.",
  "agentEndpoint": {
    "endpointUri": "${SERVICE_URL}/api/agent/replenish-query"
  }
}
JSON
    )

    HTTP_STATUS=$(curl -s -o /tmp/agent_reg_resp.json -w "%{http_code}" \
      -X POST \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -H "Content-Type: application/json" \
      -H "X-Goog-User-Project: ${PROJECT_ID}" \
      "${AGENT_URL}" \
      -d "${AGENT_PAYLOAD}" || echo "000")

    if [[ "${HTTP_STATUS}" =~ ^20[0-9]$ ]]; then
      echo "✅ Successfully registered agent 'inventory-replenishment-twin' with Discovery Engine."
    elif [[ "${HTTP_STATUS}" == "409" ]]; then
      echo "ℹ️  Agent 'inventory-replenishment-twin' already exists in Discovery Engine (HTTP 409)."
    else
      echo "⚠️  Discovery Engine agent registration returned HTTP ${HTTP_STATUS} (Optional step). Details:"
      cat /tmp/agent_reg_resp.json 2>/dev/null || true
      echo ""
    fi
  else
    echo "⚠️  Could not obtain gcloud access token. Skipping Discovery Engine agent registration."
  fi
fi

echo ""
echo "=========================================================="
echo "🚀 Deployment Successful!"
echo "Dashboard UI:        ${SERVICE_URL}"
echo "Health Check:        ${SERVICE_URL}/health"
echo "Cloud Status API:    ${SERVICE_URL}/api/cloud-status"
echo "Gemini Agent Webhook:${SERVICE_URL}/api/agent/replenish-query"
echo "=========================================================="
