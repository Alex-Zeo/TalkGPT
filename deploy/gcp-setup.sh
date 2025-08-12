#!/bin/bash

# GCP Project Setup for TalkGPT
# Run this script to set up your GCP project with required APIs and permissions

set -e

# Variables - Update these for your deployment
PROJECT_ID="talkgpt-production"
REGION="us-central1"
ZONE="us-central1-a"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up GCP project for TalkGPT deployment...${NC}"

# Set default project
echo -e "${BLUE}Setting default project to ${PROJECT_ID}...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "${BLUE}Enabling required GCP APIs...${NC}"
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  redis.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com

# Set default region and zone
echo -e "${BLUE}Setting default compute region and zone...${NC}"
gcloud config set compute/region $REGION
gcloud config set compute/zone $ZONE

# Create service account for TalkGPT
echo -e "${BLUE}Creating TalkGPT service account...${NC}"
gcloud iam service-accounts create talkgpt-service \
  --description="Service account for TalkGPT application" \
  --display-name="TalkGPT Service Account" || true

# Grant necessary permissions to service account
echo -e "${BLUE}Granting permissions to service account...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/redis.editor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/monitoring.metricWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

echo -e "${GREEN}✓ GCP project setup completed!${NC}"
echo -e "${BLUE}Next steps:${NC}"
echo "1. Configure Artifact Registry: ./configure-registry.sh"
echo "2. Set up Cloud Storage: ./setup-storage.sh"
echo "3. Deploy Redis: ./setup-redis.sh"
echo "4. Create GKE cluster: ./create-cluster.sh"