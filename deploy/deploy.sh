#!/bin/bash
# Nexus AI — Automated Google Cloud Run Deployment
# Usage: bash deploy/deploy.sh [PROJECT_ID] [REGION]
#
# Prerequisites:
#   1. gcloud CLI installed & authenticated: gcloud auth login
#   2. Required env vars: GEMINI_API_KEY (GROQ_API_KEY, TELEGRAM_BOT_TOKEN optional)

set -e

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${2:-asia-east1}"
SERVICE_NAME="nexus-ai"
GCS_BUCKET="${PROJECT_ID}-nexus-uploads"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "================================================"
echo "  Nexus AI — Cloud Run Deployment"
echo "  Project : ${PROJECT_ID}"
echo "  Region  : ${REGION}"
echo "  Service : ${SERVICE_NAME}"
echo "  Bucket  : ${GCS_BUCKET}"
echo "================================================"

# Validate required env vars
if [ -z "$GEMINI_API_KEY" ]; then
  echo "ERROR: GEMINI_API_KEY is not set."
  echo "  export GEMINI_API_KEY=your_key_here"
  exit 1
fi

if [ -z "$PROJECT_ID" ]; then
  echo "ERROR: No GCP project ID found."
  echo "  Usage: bash deploy/deploy.sh YOUR_PROJECT_ID"
  exit 1
fi

# Enable required Google Cloud APIs
echo ""
echo "[1/6] Enabling Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  --project="${PROJECT_ID}" --quiet

# Create GCS bucket (ignore error if already exists)
echo ""
echo "[2/6] Setting up Cloud Storage bucket..."
gcloud storage buckets create "gs://${GCS_BUCKET}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --uniform-bucket-level-access 2>/dev/null || echo "  Bucket already exists, skipping."

# Grant Cloud Run service account access to GCS bucket
SA_EMAIL="${PROJECT_ID}@appspot.gserviceaccount.com"
echo "  Granting Storage Object Admin to ${SA_EMAIL}..."
gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin" \
  --project="${PROJECT_ID}" 2>/dev/null || echo "  IAM binding skipped (may need manual setup)."

# Build container image using Cloud Build
echo ""
echo "[3/6] Building container image with Cloud Build..."
gcloud builds submit \
  --tag "${IMAGE}" \
  --project="${PROJECT_ID}" \
  .

# Build env-vars string
ENV_VARS="GEMINI_API_KEY=${GEMINI_API_KEY}"
ENV_VARS="${ENV_VARS},GCS_BUCKET_NAME=${GCS_BUCKET}"
ENV_VARS="${ENV_VARS},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
# Force Gemini API mode on Cloud Run (no Playwright/browser available)
ENV_VARS="${ENV_VARS},NEXUS_BRAIN_MODE=gemini"
[ -n "$GROQ_API_KEY" ]          && ENV_VARS="${ENV_VARS},GROQ_API_KEY=${GROQ_API_KEY}"
[ -n "$TELEGRAM_BOT_TOKEN" ]    && ENV_VARS="${ENV_VARS},TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}"
[ -n "$TELEGRAM_CHAT_ID" ]      && ENV_VARS="${ENV_VARS},TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}"

# Deploy to Cloud Run
echo ""
echo "[4/6] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 120 \
  --set-env-vars "${ENV_VARS}" \
  --project="${PROJECT_ID}" \
  --quiet

# Get service URL
echo ""
echo "[5/6] Fetching service URL..."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

# Health check
echo ""
echo "[6/6] Verifying deployment..."
sleep 10
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/api/status")
if [ "$HTTP_STATUS" = "200" ]; then
  echo "  Health check passed (HTTP ${HTTP_STATUS})"
else
  echo "  Warning: Health check returned HTTP ${HTTP_STATUS} (app may still be initializing)"
fi

echo ""
echo "================================================"
echo "  Deployment complete!"
echo "  Web UI   : ${SERVICE_URL}"
echo "  Dashboard: ${SERVICE_URL}/dashboard"
echo "  GCS      : gs://${GCS_BUCKET}"
echo "================================================"
