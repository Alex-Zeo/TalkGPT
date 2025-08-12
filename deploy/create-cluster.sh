#!/bin/bash

# Create Google Kubernetes Engine cluster for TalkGPT with GPU support

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
CLUSTER_NAME="talkgpt-cluster"
CPU_NODE_POOL="cpu-pool"
GPU_NODE_POOL="gpu-pool"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Creating GKE cluster for TalkGPT...${NC}"

# Create the GKE cluster with basic CPU nodes
echo -e "${BLUE}Creating GKE cluster with CPU node pool...${NC}"
gcloud container clusters create $CLUSTER_NAME \
  --region=$REGION \
  --num-nodes=1 \
  --min-nodes=1 \
  --max-nodes=10 \
  --enable-autoscaling \
  --machine-type=e2-standard-4 \
  --disk-size=50GB \
  --disk-type=pd-ssd \
  --enable-autorepair \
  --enable-autoupgrade \
  --enable-ip-alias \
  --network=default \
  --subnetwork=default \
  --enable-shielded-nodes \
  --shielded-secure-boot \
  --shielded-integrity-monitoring \
  --enable-network-policy \
  --addons=HorizontalPodAutoscaling,HttpLoadBalancing,NetworkPolicy \
  --workload-pool=$PROJECT_ID.svc.id.goog \
  --logging=SYSTEM,WORKLOAD \
  --monitoring=SYSTEM \
  --node-pool-name=$CPU_NODE_POOL || echo "Cluster already exists"

# Get cluster credentials
echo -e "${BLUE}Getting cluster credentials...${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION

# Create GPU node pool for transcription workloads
echo -e "${BLUE}Creating GPU node pool...${NC}"
gcloud container node-pools create $GPU_NODE_POOL \
  --cluster=$CLUSTER_NAME \
  --region=$REGION \
  --num-nodes=0 \
  --min-nodes=0 \
  --max-nodes=5 \
  --enable-autoscaling \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --disk-size=100GB \
  --disk-type=pd-ssd \
  --enable-autorepair \
  --enable-autoupgrade \
  --node-taints=nvidia.com/gpu=present:NoSchedule \
  --node-labels=accelerator=nvidia-tesla-t4 || echo "GPU node pool already exists"

# Install NVIDIA GPU device driver
echo -e "${BLUE}Installing NVIDIA GPU drivers...${NC}"
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded-latest.yaml

# Create namespace for TalkGPT
echo -e "${BLUE}Creating TalkGPT namespace...${NC}"
kubectl create namespace talkgpt || echo "Namespace already exists"

# Set up Workload Identity for secure access to GCP services
echo -e "${BLUE}Setting up Workload Identity...${NC}"

# Create Kubernetes service account
kubectl create serviceaccount talkgpt-ksa --namespace=talkgpt || echo "Service account already exists"

# Bind GCP service account to Kubernetes service account
gcloud iam service-accounts add-iam-policy-binding \
  talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:$PROJECT_ID.svc.id.goog[talkgpt/talkgpt-ksa]"

# Annotate Kubernetes service account
kubectl annotate serviceaccount talkgpt-ksa \
  --namespace=talkgpt \
  iam.gke.io/gcp-service-account=talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com \
  --overwrite

# Create configmap for TalkGPT configuration
echo -e "${BLUE}Creating configuration ConfigMap...${NC}"
kubectl create configmap talkgpt-config \
  --namespace=talkgpt \
  --from-literal=GCP_PROJECT_ID=$PROJECT_ID \
  --from-literal=INPUT_BUCKET=$PROJECT_ID-audio-input \
  --from-literal=OUTPUT_BUCKET=$PROJECT_ID-transcription-output \
  --from-literal=MODELS_BUCKET=$PROJECT_ID-models-cache \
  --from-literal=REGION=$REGION \
  --dry-run=client -o yaml | kubectl apply -f -

# Install ingress controller
echo -e "${BLUE}Installing ingress controller...${NC}"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

echo -e "${GREEN}✓ GKE cluster setup completed!${NC}"
echo -e "${BLUE}Cluster Details:${NC}"
echo "  Name: $CLUSTER_NAME"
echo "  Region: $REGION"
echo "  CPU Pool: $CPU_NODE_POOL (e2-standard-4)"
echo "  GPU Pool: $GPU_NODE_POOL (n1-standard-4 + Tesla T4)"
echo "  Namespace: talkgpt"
echo ""
echo -e "${BLUE}Next: Build Docker images with build-images.sh${NC}"