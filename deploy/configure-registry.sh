#!/bin/bash

# Configure Google Artifact Registry for TalkGPT Docker images

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
REPOSITORY_NAME="talkgpt-images"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Configuring Artifact Registry for TalkGPT...${NC}"

# Create Artifact Registry repository
echo -e "${BLUE}Creating Artifact Registry repository...${NC}"
gcloud artifacts repositories create $REPOSITORY_NAME \
  --repository-format=docker \
  --location=$REGION \
  --description="TalkGPT Docker images repository" || echo "Repository already exists"

# Configure Docker to use gcloud as credential helper
echo -e "${BLUE}Configuring Docker authentication...${NC}"
gcloud auth configure-docker $REGION-docker.pkg.dev

# Grant Cloud Build service account access to Artifact Registry
echo -e "${BLUE}Granting Cloud Build access to Artifact Registry...${NC}"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Grant GKE nodes access to pull images
echo -e "${BLUE}Granting GKE access to pull images...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"

echo -e "${GREEN}✓ Artifact Registry configuration completed!${NC}"
echo -e "${BLUE}Registry URL: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}${NC}"
echo -e "${BLUE}Next: Build and push Docker images using build-images.sh${NC}"