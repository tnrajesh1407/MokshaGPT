#!/bin/bash
# ─────────────────────────────────────────────
# MokshaGPT — GCP Cloud Run Deploy Script
# ─────────────────────────────────────────────
# Usage: ./deploy.sh YOUR_GCP_PROJECT_ID

set -e

PROJECT_ID=${1:-"mokshagpt"}
REGION="asia-south1"   # Mumbai — closest to India
BACKEND_SERVICE="mokshagpt-backend"
FRONTEND_SERVICE="mokshagpt-frontend"
REGISTRY="gcr.io/${PROJECT_ID}"

echo "🚀 Deploying MokshaGPT to GCP Cloud Run"
echo "   Project : $PROJECT_ID"
echo "   Region  : $REGION"
echo ""

# ── 1. Backend ────────────────────────────────
echo "📦 Building & deploying backend..."
gcloud builds submit ./backend \
  --tag "${REGISTRY}/${BACKEND_SERVICE}" \
  --project "$PROJECT_ID"

gcloud run deploy "$BACKEND_SERVICE" \
  --image "${REGISTRY}/${BACKEND_SERVICE}" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY},LLM_PROVIDER=gemini,LLM_MODEL=gemini-2.5-flash,USE_SEARCH=true" \
  --memory 1Gi \
  --cpu 1 \
  --project "$PROJECT_ID"

# Get backend URL
BACKEND_URL=$(gcloud run services describe "$BACKEND_SERVICE" \
  --platform managed --region "$REGION" \
  --format "value(status.url)" \
  --project "$PROJECT_ID")

echo "✅ Backend deployed: $BACKEND_URL"
echo ""

# ── 2. Frontend ───────────────────────────────
echo "📦 Building & deploying frontend..."

# Inject the backend URL so the frontend points to the live API
export NEXT_PUBLIC_API_URL="$BACKEND_URL"

gcloud builds submit ./gui \
  --tag "${REGISTRY}/${FRONTEND_SERVICE}" \
  --project "$PROJECT_ID" \
  --substitutions "_BACKEND_URL=${BACKEND_URL}"

gcloud run deploy "$FRONTEND_SERVICE" \
  --image "${REGISTRY}/${FRONTEND_SERVICE}" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_API_URL=${BACKEND_URL}" \
  --memory 512Mi \
  --cpu 1 \
  --project "$PROJECT_ID"

FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SERVICE" \
  --platform managed --region "$REGION" \
  --format "value(status.url)" \
  --project "$PROJECT_ID")

echo "✅ Frontend deployed: $FRONTEND_URL"
echo ""
echo "🎉 Done! MokshaGPT is live at: $FRONTEND_URL"
