#!/bin/bash

# Create and apply Kubernetes manifests for TalkGPT

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

echo -e "${BLUE}Creating Kubernetes manifests for TalkGPT...${NC}"

# Ensure we're connected to the cluster
gcloud container clusters get-credentials talkgpt-cluster --region=$REGION

# Create namespace if it doesn't exist
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Apply all Kubernetes manifests
echo -e "${BLUE}Applying Kubernetes manifests...${NC}"

# Apply MCP deployment
echo -e "${BLUE}Deploying MCP server...${NC}"
kubectl apply -f k8s/mcp-deployment.yaml

# Apply worker deployments
echo -e "${BLUE}Deploying workers...${NC}"
kubectl apply -f k8s/worker-deployment.yaml

# Apply monitoring
echo -e "${BLUE}Deploying monitoring...${NC}"
kubectl apply -f k8s/monitoring.yaml

# Reserve static IP for ingress
echo -e "${BLUE}Reserving static IP...${NC}"
gcloud compute addresses create talkgpt-ip --global || echo "IP already reserved"

# Apply ingress
echo -e "${BLUE}Deploying ingress...${NC}"
kubectl apply -f k8s/ingress.yaml

# Create persistent volume for models cache
echo -e "${BLUE}Creating persistent volume for model cache...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: talkgpt-models-pv
  namespace: $NAMESPACE
spec:
  capacity:
    storage: 20Gi
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  gcePersistentDisk:
    pdName: talkgpt-models-disk
    fsType: ext4
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: talkgpt-models-pvc
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 20Gi
  storageClassName: ""
EOF

# Create the disk if it doesn't exist
gcloud compute disks create talkgpt-models-disk \
  --size=20GB \
  --zone=us-central1-a \
  --type=pd-ssd || echo "Disk already exists"

# Wait for deployments to be ready
echo -e "${BLUE}Waiting for deployments to be ready...${NC}"
kubectl rollout status deployment/talkgpt-mcp -n $NAMESPACE --timeout=300s
kubectl rollout status deployment/talkgpt-worker-cpu -n $NAMESPACE --timeout=300s

# Get status
echo -e "${GREEN}✓ Kubernetes manifests applied successfully!${NC}"
echo -e "${BLUE}Getting deployment status...${NC}"
kubectl get pods -n $NAMESPACE
kubectl get services -n $NAMESPACE
kubectl get ingress -n $NAMESPACE

# Get external IP
echo -e "${BLUE}Getting external IP address...${NC}"
EXTERNAL_IP=$(gcloud compute addresses describe talkgpt-ip --global --format="value(address)")
echo -e "${GREEN}External IP: $EXTERNAL_IP${NC}"

echo -e "${BLUE}Next steps:${NC}"
echo "1. Update your DNS to point talkgpt.yourdomain.com to $EXTERNAL_IP"
echo "2. Update ingress.yaml with your actual domain name"
echo "3. Apply ingress again: kubectl apply -f k8s/ingress.yaml"
echo "4. Set up secrets with setup-secrets.sh"