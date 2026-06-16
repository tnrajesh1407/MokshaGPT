#!/bin/bash
# Standalone Cloud Scheduler Setup for Nifty 100 Precompute
# Works with existing Docker-deployed Cloud Run services

set -e

PROJECT_ID="bulkpoddesigns"
REGION="us-central1"
BACKEND_IMAGE="us-central1-docker.pkg.dev/bulkpoddesigns/mokshagpt/backend:latest"
SUPABASE_URL="https://juxudzuyaixpbgsmdccf.supabase.co"
SUPABASE_SERVICE_KEY="YOUR_SUPABASE_SERVICE_KEY"  # Replace with actual key

echo "=========================================="
echo "Setting up Cloud Scheduler for Nifty 100"
echo "=========================================="

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID
gcloud services enable run.googleapis.com --project=$PROJECT_ID

# Create service account for jobs
echo "Creating service account..."
gcloud iam service-accounts create precompute-job-sa \
  --display-name="Precompute Job Service Account" \
  --project=$PROJECT_ID || echo "Service account already exists"

SA_EMAIL="precompute-job-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant permissions
echo "Granting permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker" \
  --condition=None

# Create Cloud Run Job for 15-minute incremental updates
echo "Creating Cloud Run Job: precompute-incremental..."
gcloud run jobs create precompute-nifty100-incremental \
  --image=$BACKEND_IMAGE \
  --region=$REGION \
  --project=$PROJECT_ID \
  --service-account=$SA_EMAIL \
  --max-retries=1 \
  --task-timeout=15m \
  --cpu=2 \
  --memory=2Gi \
  --set-env-vars="SUPABASE_URL=${SUPABASE_URL},SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}" \
  --command=python \
  --args=precompute_nifty100.py \
  || echo "Job already exists, updating..."

# Update if already exists
gcloud run jobs update precompute-nifty100-incremental \
  --image=$BACKEND_IMAGE \
  --region=$REGION \
  --project=$PROJECT_ID \
  --set-env-vars="SUPABASE_URL=${SUPABASE_URL},SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}" \
  || true

# Create Cloud Run Job for daily full refresh
echo "Creating Cloud Run Job: precompute-full..."
gcloud run jobs create precompute-nifty100-full \
  --image=$BACKEND_IMAGE \
  --region=$REGION \
  --project=$PROJECT_ID \
  --service-account=$SA_EMAIL \
  --max-retries=1 \
  --task-timeout=30m \
  --cpu=2 \
  --memory=2Gi \
  --set-env-vars="SUPABASE_URL=${SUPABASE_URL},SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}" \
  --command=python \
  --args=precompute_nifty100.py,--full \
  || echo "Job already exists, updating..."

# Update if already exists
gcloud run jobs update precompute-nifty100-full \
  --image=$BACKEND_IMAGE \
  --region=$REGION \
  --project=$PROJECT_ID \
  --set-env-vars="SUPABASE_URL=${SUPABASE_URL},SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}" \
  || true

# Create Cloud Scheduler: Every 15 minutes
echo "Creating Cloud Scheduler: 15-minute job..."
gcloud scheduler jobs create http precompute-15min \
  --location=$REGION \
  --schedule="*/15 * * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/precompute-nifty100-incremental:run" \
  --http-method=POST \
  --oauth-service-account-email=$SA_EMAIL \
  --project=$PROJECT_ID \
  || echo "Scheduler job already exists, updating..."

# Update if already exists
gcloud scheduler jobs update http precompute-15min \
  --location=$REGION \
  --schedule="*/15 * * * *" \
  --time-zone="Asia/Kolkata" \
  --project=$PROJECT_ID \
  || true

# Create Cloud Scheduler: Daily at 6 AM IST
echo "Creating Cloud Scheduler: daily job..."
gcloud scheduler jobs create http precompute-daily \
  --location=$REGION \
  --schedule="0 6 * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/precompute-nifty100-full:run" \
  --http-method=POST \
  --oauth-service-account-email=$SA_EMAIL \
  --project=$PROJECT_ID \
  || echo "Scheduler job already exists, updating..."

# Update if already exists
gcloud scheduler jobs update http precompute-daily \
  --location=$REGION \
  --schedule="0 6 * * *" \
  --time-zone="Asia/Kolkata" \
  --project=$PROJECT_ID \
  || true

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Created resources:"
echo "  - Service Account: $SA_EMAIL"
echo "  - Cloud Run Job: precompute-nifty100-incremental"
echo "  - Cloud Run Job: precompute-nifty100-full"
echo "  - Scheduler: precompute-15min (every 15 minutes)"
echo "  - Scheduler: precompute-daily (daily at 6 AM IST)"
echo ""
echo "Test manually:"
echo "  gcloud run jobs execute precompute-nifty100-incremental --region=$REGION --project=$PROJECT_ID"
echo "  gcloud run jobs execute precompute-nifty100-full --region=$REGION --project=$PROJECT_ID"
echo ""
echo "View logs:"
echo "  gcloud logging read 'resource.type=cloud_run_job' --limit=50 --project=$PROJECT_ID"
echo ""
