#!/bin/bash

# Set up Cloud Build CI/CD pipeline for TalkGPT

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
REPOSITORY_NAME="talkgpt-images"
GITHUB_REPO="Alex-Zeo/TalkGPT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up CI/CD pipeline for TalkGPT...${NC}"

# Create bucket for build artifacts
echo -e "${BLUE}Creating build artifacts bucket...${NC}"
gsutil mb gs://$PROJECT_ID-build-artifacts || echo "Bucket already exists"

# Grant Cloud Build additional permissions
echo -e "${BLUE}Granting Cloud Build permissions...${NC}"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Grant GKE Developer role to Cloud Build
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/container.developer"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant Storage Admin for artifacts
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/storage.admin"

# Create Cloud Build trigger for main branch
echo -e "${BLUE}Creating Cloud Build trigger...${NC}"
gcloud builds triggers create github \
  --repo-name=$GITHUB_REPO \
  --repo-owner=Alex-Zeo \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --description="TalkGPT Production Deployment" \
  --name="talkgpt-main-trigger" || echo "Trigger already exists"

# Create staging trigger for develop branch
gcloud builds triggers create github \
  --repo-name=$GITHUB_REPO \
  --repo-owner=Alex-Zeo \
  --branch-pattern="^develop$" \
  --build-config=cloudbuild-staging.yaml \
  --description="TalkGPT Staging Deployment" \
  --name="talkgpt-staging-trigger" || echo "Staging trigger already exists"

# Create staging cloudbuild config
echo -e "${BLUE}Creating staging build configuration...${NC}"
cat <<EOF > cloudbuild-staging.yaml
# Cloud Build configuration for TalkGPT Staging
steps:
  # Step 1: Run tests
  - name: 'python:3.10-slim'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        pip install -r requirements.txt
        pip install -r requirements-cli.txt
        python -m pytest tests/ -v --tb=short
    id: 'run-tests'

  # Step 2: Build and push images with staging tags
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/talkgpt-app:staging-$BUILD_ID'
      - '-t'
      - '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/talkgpt-app:staging-latest'
      - '-f'
      - 'Dockerfile'
      - '.'
    id: 'build-staging-image'
    waitFor: ['run-tests']

  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '--all-tags', '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/talkgpt-app']
    id: 'push-staging-image'
    waitFor: ['build-staging-image']

  # Step 3: Deploy to staging namespace
  - name: 'gcr.io/cloud-builders/kubectl'
    args:
      - 'set'
      - 'image'
      - 'deployment/talkgpt-mcp'
      - 'mcp-server=${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/talkgpt-app:staging-$BUILD_ID'
      - '--namespace=staging'
    env:
      - 'CLOUDSDK_COMPUTE_REGION=${_REGION}'
      - 'CLOUDSDK_CONTAINER_CLUSTER=${_CLUSTER_NAME}'
    id: 'deploy-staging'
    waitFor: ['push-staging-image']

substitutions:
  _REGION: 'us-central1'
  _REPOSITORY: 'talkgpt-images'
  _CLUSTER_NAME: 'talkgpt-cluster'

options:
  machineType: 'E2_HIGHCPU_4'
  logging: CLOUD_LOGGING_ONLY

timeout: 1200s
EOF

# Create manual trigger for hotfixes
echo -e "${BLUE}Creating manual hotfix trigger...${NC}"
gcloud builds triggers create manual \
  --repo=https://github.com/$GITHUB_REPO \
  --branch=main \
  --build-config=cloudbuild-hotfix.yaml \
  --description="TalkGPT Hotfix Deployment" \
  --name="talkgpt-hotfix-trigger" || echo "Hotfix trigger already exists"

# Create hotfix build config
cat <<EOF > cloudbuild-hotfix.yaml
# Cloud Build configuration for TalkGPT Hotfix
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/talkgpt-app:hotfix-$BUILD_ID'
      - '-f'
      - 'Dockerfile'
      - '.'
    id: 'build-hotfix-image'

  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/talkgpt-app:hotfix-$BUILD_ID']
    id: 'push-hotfix-image'
    waitFor: ['build-hotfix-image']

  # Manual approval step (requires manual trigger)
  - name: 'gcr.io/cloud-builders/kubectl'
    args:
      - 'set'
      - 'image'
      - 'deployment/talkgpt-mcp'
      - 'mcp-server=${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/talkgpt-app:hotfix-$BUILD_ID'
      - '--namespace=${_NAMESPACE}'
    env:
      - 'CLOUDSDK_COMPUTE_REGION=${_REGION}'
      - 'CLOUDSDK_CONTAINER_CLUSTER=${_CLUSTER_NAME}'
    id: 'deploy-hotfix'
    waitFor: ['push-hotfix-image']

substitutions:
  _REGION: 'us-central1'
  _REPOSITORY: 'talkgpt-images'
  _CLUSTER_NAME: 'talkgpt-cluster'
  _NAMESPACE: 'talkgpt'

options:
  machineType: 'E2_HIGHCPU_4'
  logging: CLOUD_LOGGING_ONLY

timeout: 900s
EOF

# Create webhook for GitHub integration (optional)
echo -e "${BLUE}Setting up webhook secret...${NC}"
WEBHOOK_SECRET=$(openssl rand -base64 32)
echo $WEBHOOK_SECRET | gcloud secrets create talkgpt-webhook-secret --data-file=- || \
echo $WEBHOOK_SECRET | gcloud secrets versions add talkgpt-webhook-secret --data-file=-

# Create Cloud Scheduler jobs for regular builds/tests
echo -e "${BLUE}Setting up scheduled jobs...${NC}"

# Nightly build job
gcloud scheduler jobs create http nightly-build \
  --location=$REGION \
  --schedule="0 2 * * *" \
  --uri="https://cloudbuild.googleapis.com/v1/projects/$PROJECT_ID/triggers/talkgpt-main-trigger:run" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --oauth-service-account-email=$PROJECT_NUMBER@cloudbuild.gserviceaccount.com \
  --message-body='{"branchName":"main"}' \
  --description="Nightly build and test of TalkGPT main branch" || echo "Scheduler job already exists"

# Create deployment scripts for different environments
echo -e "${BLUE}Creating deployment scripts...${NC}"

# Production deployment script
cat <<'EOF' > deploy/deploy-production.sh
#!/bin/bash
set -e
PROJECT_ID="talkgpt-production"
REGION="us-central1"

echo "Starting production deployment..."

# Trigger production build
gcloud builds triggers run talkgpt-main-trigger \
  --branch=main \
  --region=$REGION

echo "Production deployment initiated. Monitor at:"
echo "https://console.cloud.google.com/cloud-build/builds"
EOF

# Staging deployment script
cat <<'EOF' > deploy/deploy-staging.sh
#!/bin/bash
set -e
PROJECT_ID="talkgpt-production"
REGION="us-central1"

echo "Starting staging deployment..."

# Trigger staging build
gcloud builds triggers run talkgpt-staging-trigger \
  --branch=develop \
  --region=$REGION

echo "Staging deployment initiated. Monitor at:"
echo "https://console.cloud.google.com/cloud-build/builds"
EOF

# Rollback script
cat <<'EOF' > deploy/rollback.sh
#!/bin/bash
set -e
PROJECT_ID="talkgpt-production"
REGION="us-central1"
NAMESPACE="talkgpt"

if [ -z "$1" ]; then
  echo "Usage: $0 <image-tag>"
  echo "Available tags:"
  gcloud container images list-tags us-central1-docker.pkg.dev/$PROJECT_ID/talkgpt-images/talkgpt-app --limit=10
  exit 1
fi

IMAGE_TAG=$1
echo "Rolling back to image tag: $IMAGE_TAG"

# Update deployment
kubectl set image deployment/talkgpt-mcp \
  mcp-server=us-central1-docker.pkg.dev/$PROJECT_ID/talkgpt-images/talkgpt-app:$IMAGE_TAG \
  --namespace=$NAMESPACE

kubectl set image deployment/talkgpt-worker-cpu \
  celery-worker=us-central1-docker.pkg.dev/$PROJECT_ID/talkgpt-images/talkgpt-app:$IMAGE_TAG \
  --namespace=$NAMESPACE

# Wait for rollout
kubectl rollout status deployment/talkgpt-mcp --namespace=$NAMESPACE
kubectl rollout status deployment/talkgpt-worker-cpu --namespace=$NAMESPACE

echo "Rollback completed successfully!"
EOF

# Make scripts executable
chmod +x deploy/deploy-production.sh
chmod +x deploy/deploy-staging.sh  
chmod +x deploy/rollback.sh

echo -e "${GREEN}✓ CI/CD pipeline setup completed!${NC}"
echo -e "${BLUE}Cloud Build Triggers:${NC}"
echo "  - Production (main): talkgpt-main-trigger"
echo "  - Staging (develop): talkgpt-staging-trigger"
echo "  - Hotfix (manual): talkgpt-hotfix-trigger"
echo ""
echo -e "${BLUE}Deployment Scripts:${NC}"
echo "  - Production: ./deploy/deploy-production.sh"
echo "  - Staging: ./deploy/deploy-staging.sh"
echo "  - Rollback: ./deploy/rollback.sh <image-tag>"
echo ""
echo -e "${BLUE}Monitoring:${NC}"
echo "  - Builds: https://console.cloud.google.com/cloud-build/builds"
echo "  - Triggers: https://console.cloud.google.com/cloud-build/triggers"
echo ""
echo -e "${BLUE}Next: Configure autoscaling with setup-autoscaling.sh${NC}"