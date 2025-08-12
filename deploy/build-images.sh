#!/bin/bash

# Build and push optimized Docker images for TalkGPT GCP deployment

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
REPOSITORY_NAME="talkgpt-images"
REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"

# Image tags
APP_IMAGE="${REGISTRY_URL}/talkgpt-app"
MCP_IMAGE="${REGISTRY_URL}/talkgpt-mcp"
WORKER_IMAGE="${REGISTRY_URL}/talkgpt-worker"
GPU_IMAGE="${REGISTRY_URL}/talkgpt-gpu"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Building and pushing Docker images for TalkGPT...${NC}"

# Build CPU-based core application image
echo -e "${BLUE}Building TalkGPT core application image (CPU)...${NC}"
docker build -t $APP_IMAGE:latest \
  --build-arg BUILDPLATFORM=linux/amd64 \
  -f Dockerfile .

# Build MCP server image
echo -e "${BLUE}Building TalkGPT MCP server image...${NC}"
docker build -t $MCP_IMAGE:latest \
  --build-arg BUILDPLATFORM=linux/amd64 \
  -f Dockerfile.mcp .

# Build worker image (same as core but optimized for background tasks)
echo -e "${BLUE}Building TalkGPT worker image...${NC}"
docker build -t $WORKER_IMAGE:latest \
  --build-arg BUILDPLATFORM=linux/amd64 \
  -f Dockerfile .

# Build GPU-enabled image
echo -e "${BLUE}Building TalkGPT GPU image...${NC}"
cat > Dockerfile.gpu << 'EOF'
# TalkGPT GPU Dockerfile
FROM nvidia/cuda:12.1-devel-ubuntu20.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    CUDA_VISIBLE_DEVICES=all

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3-pip \
    ffmpeg \
    git \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set python3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

WORKDIR /app

# Install CUDA-compatible PyTorch first
RUN pip install torch==2.4.0+cu121 torchaudio==2.4.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html

# Copy and install requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install CUDA-compatible ctranslate2
RUN pip install ctranslate2==4.5.0

# Copy application
COPY . /app

# Set GPU-specific environment variables
ENV CUDA_VISIBLE_DEVICES=all
ENV OMP_NUM_THREADS=8
ENV MKL_NUM_THREADS=8
ENV KMP_DUPLICATE_LIB_OK=TRUE

CMD ["python", "-m", "src.cli.main", "--help"]
EOF

docker build -t $GPU_IMAGE:latest \
  --build-arg BUILDPLATFORM=linux/amd64 \
  -f Dockerfile.gpu .

# Tag images with version
VERSION=$(date +%Y%m%d-%H%M%S)
docker tag $APP_IMAGE:latest $APP_IMAGE:$VERSION
docker tag $MCP_IMAGE:latest $MCP_IMAGE:$VERSION
docker tag $WORKER_IMAGE:latest $WORKER_IMAGE:$VERSION
docker tag $GPU_IMAGE:latest $GPU_IMAGE:$VERSION

# Push all images to Artifact Registry
echo -e "${BLUE}Pushing images to Artifact Registry...${NC}"

echo -e "${BLUE}Pushing app image...${NC}"
docker push $APP_IMAGE:latest
docker push $APP_IMAGE:$VERSION

echo -e "${BLUE}Pushing MCP image...${NC}"
docker push $MCP_IMAGE:latest
docker push $MCP_IMAGE:$VERSION

echo -e "${BLUE}Pushing worker image...${NC}"
docker push $WORKER_IMAGE:latest
docker push $WORKER_IMAGE:$VERSION

echo -e "${BLUE}Pushing GPU image...${NC}"
docker push $GPU_IMAGE:latest
docker push $GPU_IMAGE:$VERSION

# Clean up
rm -f Dockerfile.gpu

# Create image manifest file for reference
cat > deploy/image-manifest.yaml << EOF
# TalkGPT Docker Images Manifest
# Generated: $(date)

images:
  app:
    repository: $APP_IMAGE
    latest: $APP_IMAGE:latest
    version: $APP_IMAGE:$VERSION
    description: "CPU-based core application"
    
  mcp:
    repository: $MCP_IMAGE
    latest: $MCP_IMAGE:latest
    version: $MCP_IMAGE:$VERSION
    description: "MCP server for agent integration"
    
  worker:
    repository: $WORKER_IMAGE
    latest: $WORKER_IMAGE:latest
    version: $WORKER_IMAGE:$VERSION
    description: "Background task worker"
    
  gpu:
    repository: $GPU_IMAGE
    latest: $GPU_IMAGE:latest
    version: $GPU_IMAGE:$VERSION
    description: "GPU-enabled transcription service"

registry: $REGISTRY_URL
build_date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
version: $VERSION
EOF

echo -e "${GREEN}✓ All Docker images built and pushed successfully!${NC}"
echo -e "${BLUE}Images pushed to Artifact Registry:${NC}"
echo "  - $APP_IMAGE:latest"
echo "  - $MCP_IMAGE:latest"
echo "  - $WORKER_IMAGE:latest"
echo "  - $GPU_IMAGE:latest"
echo ""
echo -e "${BLUE}Image manifest saved to: deploy/image-manifest.yaml${NC}"
echo -e "${BLUE}Next: Create Kubernetes manifests with create-k8s-manifests.sh${NC}"