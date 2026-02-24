#!/bin/bash
# Nexus AI — Automated Google Cloud Run Deployment
# Usage: bash deploy/deploy.sh [PROJECT_ID] [REGION]
#
# Prerequisites:
#   1. gcloud CLI installed: https://cloud.google.com/sdk/docs/install
#   2. Authenticated: gcloud auth login
#   3. GEMINI_API_KEY set in environment

set -e

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${2:-us-central1}"
SERVICE_NAME="nexus-ai"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "================================================"
echo "  Nexus AI — Cloud Run Deployment"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
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
echo "[1/5] Enabling Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  aiplatform.googleapis.com \
  --project="${PROJECT_ID}" --quiet

# Build container image using Cloud Build
echo ""
echo "[2/5] Building container image with Cloud Build..."
gcloud builds submit \
  --tag "${IMAGE}" \
  --project="${PROJECT_ID}" \
  .

# Deploy to Cloud Run
echo ""
echo "[3/5] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --port 8000 \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars "GOOGLE_CLOUD_LOCATION=${REGION}" \
  --project="${PROJECT_ID}" \
  --quiet

# Get service URL
echo ""
echo "[4/5] Fetching service URL..."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

# Health check
echo ""
echo "[5/5] Verifying deployment..."
sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/")
if [ "$HTTP_STATUS" = "200" ]; then
  echo "  Health check passed (HTTP ${HTTP_STATUS})"
else
  echo "  Warning: Health check returned HTTP ${HTTP_STATUS}"
fi

echo ""
echo "================================================"
echo "  Deployment complete!"
echo "  Web UI:    ${SERVICE_URL}"
echo "  Dashboard: ${SERVICE_URL}/dashboard"
echo "================================================"
