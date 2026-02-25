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

DEPLOY_CMD=(
  gcloud run deploy "$SERVICE_NAME"
  --source .
  --region "$REGION"
  --allow-unauthenticated
  --memory 1Gi
  --timeout 300
  --min-instances 1
  --max-instances 1
  --project "$PROJECT_ID"
)

# Only pass GEMINI_API_KEY if set in environment
if [ -n "$GEMINI_API_KEY" ]; then
  DEPLOY_CMD+=(--update-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}")
  echo "  Using GEMINI_API_KEY from environment"
else
  echo "  GEMINI_API_KEY not set — keeping existing Cloud Run value"
fi

"${DEPLOY_CMD[@]}"

echo ""
echo "Done! Visit the Cloud Run URL above to access Nexus AI."
