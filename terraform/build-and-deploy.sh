#!/bin/bash
# Builds Docker images via Cloud Build, then applies Terraform
set -e

PROJECT_ID=$(grep 'project_id' terraform.tfvars | awk -F'"' '{print $2}')
REGION=$(grep 'region' terraform.tfvars | awk -F'"' '{print $2}')
REGION=${REGION:-"asia-south1"}

echo "🔨 Building images for project: $PROJECT_ID"

# Build backend
gcloud builds submit ../backend \
  --tag "gcr.io/${PROJECT_ID}/mokshagpt-backend:latest" \
  --project "$PROJECT_ID"

# Build frontend
gcloud builds submit ../gui \
  --tag "gcr.io/${PROJECT_ID}/mokshagpt-frontend:latest" \
  --project "$PROJECT_ID"

echo "🏗️  Applying Terraform..."
terraform init
terraform apply -auto-approve

echo ""
echo "🎉 Done!"
terraform output
