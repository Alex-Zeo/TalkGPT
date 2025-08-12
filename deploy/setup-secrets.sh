#!/bin/bash

# Set up Google Secret Manager for TalkGPT environment variables

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
NAMESPACE="talkgpt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up secrets for TalkGPT...${NC}"

# Get Redis connection URL
echo -e "${BLUE}Retrieving Redis connection URL...${NC}"
REDIS_HOST=$(gcloud redis instances describe talkgpt-redis --region=$REGION --format="value(host)")
REDIS_PORT=$(gcloud redis instances describe talkgpt-redis --region=$REGION --format="value(port)")
REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"

# Create secrets in Google Secret Manager
echo -e "${BLUE}Creating secrets in Secret Manager...${NC}"

# Redis URL
echo $REDIS_URL | gcloud secrets create talkgpt-redis-url --data-file=- || \
echo $REDIS_URL | gcloud secrets versions add talkgpt-redis-url --data-file=-

# Create service account key for workload identity
echo -e "${BLUE}Creating service account key...${NC}"
gcloud iam service-accounts keys create /tmp/talkgpt-key.json \
  --iam-account=talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com || true

# Store service account key in Secret Manager
if [ -f /tmp/talkgpt-key.json ]; then
  gcloud secrets create talkgpt-service-key --data-file=/tmp/talkgpt-key.json || \
  gcloud secrets versions add talkgpt-service-key --data-file=/tmp/talkgpt-key.json
  rm /tmp/talkgpt-key.json
fi

# Create database credentials (if using external database)
echo -e "${BLUE}Creating additional secrets...${NC}"

# Create dummy API keys for external services (update these with real values)
echo "your-openai-api-key-here" | gcloud secrets create talkgpt-openai-key --data-file=- || \
echo "your-openai-api-key-here" | gcloud secrets versions add talkgpt-openai-key --data-file=-

echo "your-webhook-secret-here" | gcloud secrets create talkgpt-webhook-secret --data-file=- || \
echo "your-webhook-secret-here" | gcloud secrets versions add talkgpt-webhook-secret --data-file=-

# Grant Secret Manager access to GKE service account
echo -e "${BLUE}Granting Secret Manager access to service accounts...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Create Kubernetes secrets from Secret Manager
echo -e "${BLUE}Creating Kubernetes secrets...${NC}"

# Get Redis URL from Secret Manager
REDIS_URL_SECRET=$(gcloud secrets versions access latest --secret="talkgpt-redis-url")

# Create Kubernetes secret
kubectl create secret generic talkgpt-secrets \
  --namespace=$NAMESPACE \
  --from-literal=redis-url="$REDIS_URL_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

# Create secret for service account key
if gcloud secrets describe talkgpt-service-key >/dev/null 2>&1; then
  gcloud secrets versions access latest --secret="talkgpt-service-key" > /tmp/key.json
  kubectl create secret generic talkgpt-gcp-key \
    --namespace=$NAMESPACE \
    --from-file=key.json=/tmp/key.json \
    --dry-run=client -o yaml | kubectl apply -f -
  rm /tmp/key.json
fi

# Create external secrets operator configuration
echo -e "${BLUE}Setting up External Secrets Operator...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: talkgpt-secret-store
  namespace: $NAMESPACE
spec:
  provider:
    gcpsm:
      projectId: $PROJECT_ID
      auth:
        workloadIdentity:
          clusterLocation: $REGION
          clusterName: talkgpt-cluster
          serviceAccountRef:
            name: talkgpt-ksa
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: talkgpt-external-secrets
  namespace: $NAMESPACE
spec:
  refreshInterval: 30s
  secretStoreRef:
    name: talkgpt-secret-store
    kind: SecretStore
  target:
    name: talkgpt-external-secrets
    creationPolicy: Owner
  data:
  - secretKey: redis-url
    remoteRef:
      key: talkgpt-redis-url
  - secretKey: openai-key
    remoteRef:
      key: talkgpt-openai-key
  - secretKey: webhook-secret
    remoteRef:
      key: talkgpt-webhook-secret
EOF

# Install External Secrets Operator if not already installed
kubectl apply -f https://raw.githubusercontent.com/external-secrets/external-secrets/main/deploy/crds/bundle.yaml || true
helm repo add external-secrets https://charts.external-secrets.io || true
helm repo update || true
helm upgrade --install external-secrets \
  external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace || echo "External Secrets already installed"

# Create pod disruption budgets
echo -e "${BLUE}Creating Pod Disruption Budgets...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: talkgpt-mcp-pdb
  namespace: $NAMESPACE
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: talkgpt-mcp
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: talkgpt-worker-cpu-pdb
  namespace: $NAMESPACE
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: talkgpt-worker
      type: cpu
EOF

echo -e "${GREEN}✓ Secrets setup completed!${NC}"
echo -e "${BLUE}Secrets created in Secret Manager:${NC}"
echo "  - talkgpt-redis-url"
echo "  - talkgpt-service-key"
echo "  - talkgpt-openai-key (placeholder)"
echo "  - talkgpt-webhook-secret (placeholder)"
echo ""
echo -e "${RED}IMPORTANT: Update placeholder secrets with real values:${NC}"
echo "  gcloud secrets versions add talkgpt-openai-key --data-file=<your-key-file>"
echo "  gcloud secrets versions add talkgpt-webhook-secret --data-file=<your-secret-file>"
echo ""
echo -e "${BLUE}Next: Configure monitoring with setup-monitoring.sh${NC}"