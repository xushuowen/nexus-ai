#!/bin/bash
# Google Cloud Run — build and deploy script
# Usage: ./startup.sh [project-id] [region]
#
# Prerequisites:
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID

PROJECT_ID=${1:-$(gcloud config get-value project 2>/dev/null)}
REGION=${2:-"asia-east1"}
SERVICE_NAME="nexus-ai"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: ./startup.sh [project-id] [region]"
  echo "  or:  gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "Deploying $SERVICE_NAME to Cloud Run..."
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300 \
  --min-instances 1 \
  --update-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}" \
  --project "$PROJECT_ID"

echo ""
echo "Done! Visit the Cloud Run URL above to access Nexus AI."
