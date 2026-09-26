#!/usr/bin/env bash
# Deploy the AlphaEvolve Supply Chain & Digital Twin Intelligence Suite to Google Cloud Run.
set -euo pipefail

# Configuration defaults (override with environment variables)
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-alpha-evolve-primer-ui}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-true}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: PROJECT_ID is not set and could not be detected from gcloud." >&2
  echo "Usage: PROJECT_ID=my-project-id $0" >&2
  exit 1
fi

IMAGE_URI="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "=========================================================="
echo "Deploying ${SERVICE_NAME} to Google Cloud Run"
echo "Project:  ${PROJECT_ID}"
echo "Region:   ${REGION}"
echo "Image:    ${IMAGE_URI}"
echo "=========================================================="

echo "Step 1: Submitting build to Google Cloud Build..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE_URI}" \
  .

AUTH_FLAG="--no-allow-unauthenticated"
if [[ "${ALLOW_UNAUTHENTICATED}" == "true" ]]; then
  AUTH_FLAG="--allow-unauthenticated"
fi

echo "Step 2: Deploying container image to Cloud Run..."
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
echo "Deployment Successful!"
echo "Service URL: ${SERVICE_URL}"
echo "Health Check: ${SERVICE_URL}/health"
echo "Gemini Agent Webhook: ${SERVICE_URL}/api/agent/replenish-query"
echo "=========================================================="
