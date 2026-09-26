# Google Cloud Run Hosting & Gemini Enterprise Integration Guide

This guide describes how to deploy the **AlphaEvolve Supply Chain & Digital Twin Intelligence Suite** interactive dashboard to **Google Cloud Run** and register it with **Gemini Enterprise (Discovery Engine v1alpha)**.

---

## 1. Architecture Overview

- **Compute**: Google Cloud Run (Serverless, scales to 0, sub-second cold starts, managed HTTPS/TLS).
- **Runtime**: Python 3.12-slim in a hardened non-root container (`uv`-managed frozen dependencies).
- **Interface**: Decoupled dual-mode server ([`server.py`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/server.py)) delivering both the rich interactive dashboard ([`dashboard/index.html`](file:///usr/local/google/home/jordantotten/alpha/alpha-primer/dashboard/index.html)) and structured REST telemetry APIs.
- **Enterprise Grounding**: Direct REST API integration with Gemini Enterprise / Discovery Engine Assistants.

---

## 2. Prerequisites & IAM Setup

Ensure your Google Cloud identity or Cloud Build service account has the following IAM roles:
- `roles/run.admin` (Cloud Run administration)
- `roles/iam.serviceAccountUser` (Act as Cloud Run runtime service account)
- `roles/artifactregistry.admin` or `roles/storage.admin` (Container registry storage)
- `roles/discoveryengine.viewer` or `roles/discoveryengine.admin` (Discovery Engine telemetry audit & assistant registration)

Enable required services:
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  discoveryengine.googleapis.com
```

---

## 3. Deploying to Cloud Run

### Option A: Using the Automated Deployment Script
```bash
PROJECT_ID="your-gcp-project-id" ./scripts/deploy_cloud_run.sh
```

### Option B: Step-by-Step Manual Deployment

1. **Submit Build to Google Cloud Build**:
   ```bash
   gcloud builds submit --tag gcr.io/${PROJECT_ID}/alpha-evolve-primer-ui:latest .
   ```

2. **Deploy Container to Cloud Run**:
   ```bash
   gcloud run deploy alpha-evolve-primer-ui \
     --image gcr.io/${PROJECT_ID}/alpha-evolve-primer-ui:latest \
     --platform managed \
     --region us-central1 \
     --port 8080 \
     --memory 512Mi \
     --cpu 1 \
     --concurrency 80 \
     --min-instances 0 \
     --max-instances 5 \
     --allow-unauthenticated
   ```

3. **Verify Deployment & Security**:
   ```bash
   SERVICE_URL=$(gcloud run services describe alpha-evolve-primer-ui --region us-central1 --format="value(status.url)")
   
   # Health check
   curl -s ${SERVICE_URL}/health
   
   # Verify security headers
   curl -I ${SERVICE_URL}
   ```

---

## 4. Connecting to Gemini Enterprise (Discovery Engine v1alpha)

### Integration Vector 1: Register as an External Agent Webhook
Discovery Engine v1alpha allows registering Cloud Run endpoints as assistant agents:

```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)
BASE_URL="https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/global/collections/default_collection"

curl -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${BASE_URL}/engines/${ENGINE_ID}/assistants/default_assistant/agents?agentId=inventory-replenishment-twin" \
  -d '{
    "displayName": "Autonomous Inventory Replenishment Digital Twin",
    "description": "Provides live AlphaEvolve simulation metrics, spoilage reductions, and evolved heuristic code.",
    "agentEndpoint": {
      "endpointUri": "'"${SERVICE_URL}"'/api/agent/replenish-query"
    }
  }'
```

When users query the Gemini Enterprise Assistant (e.g., *"What was our spoilage reduction in Generation 30?"*), the query is routed to `/api/agent/replenish-query` on Cloud Run, returning verified metrics and program references.

### Integration Vector 2: Grounded Assistant Ingestion via Data Store
To make the optimization trajectories searchable across your enterprise:
1. Export trajectory data (`records/inventory_replenishment_trajectory.json`) and README documentation to a Cloud Storage bucket: `gs://${PROJECT_ID}-alpha-evolve-docs/`.
2. Connect the GCS bucket to a Discovery Engine Data Store (`dataStores/inventory-replenishment-store`).
3. Internal conversational agents can search this store using `DiscoveryEngineSearchTool` or query via `StreamAssist`, citing the live Cloud Run dashboard URL.

### Integration Vector 3: Real-Time Discovery Engine Telemetry Audit
The Cloud Run dashboard backend calls `Discovery Engine`'s REST API at runtime using Application Default Credentials (ADC) to display live experiment sessions and program candidates in the UI header.
