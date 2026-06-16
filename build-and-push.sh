#!/bin/bash
# Quick script to build and push backend Docker image

set -e

PROJECT_ID="bulkpoddesigns"
REGION="asia-south1"
REGISTRY="${REGION}-docker.pkg.dev"
IMAGE_NAME="${REGISTRY}/${PROJECT_ID}/mokshagpt/backend:latest"

echo "=========================================="
echo "Building Backend Docker Image"
echo "=========================================="

# Navigate to backend directory
cd backend

# Build the image
echo "Building image: ${IMAGE_NAME}"
docker build -t ${IMAGE_NAME} .

echo ""
echo "=========================================="
echo "Pushing to Artifact Registry"
echo "=========================================="

# Push to registry
docker push ${IMAGE_NAME}

echo ""
echo "=========================================="
echo "Build & Push Complete!"
echo "=========================================="
echo ""
echo "Image: ${IMAGE_NAME}"
echo ""
echo "Next steps:"
echo "  1. Deploy to Cloud Run:"
echo "     gcloud run deploy mokshagpt-backend --image=${IMAGE_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "  2. Update Cloud Run Jobs (if they exist):"
echo "     gcloud run jobs update precompute-nifty100-incremental --image=${IMAGE_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo "     gcloud run jobs update precompute-nifty100-full --image=${IMAGE_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
