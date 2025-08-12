#!/bin/bash

# Set up Google Cloud Memorystore Redis instance for TalkGPT

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
REDIS_INSTANCE_ID="talkgpt-redis"
REDIS_VERSION="redis_7_0"
MEMORY_SIZE_GB="4"
NETWORK="default"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up Google Cloud Memorystore Redis for TalkGPT...${NC}"

# Create Redis instance
echo -e "${BLUE}Creating Redis instance...${NC}"
gcloud redis instances create $REDIS_INSTANCE_ID \
  --size=$MEMORY_SIZE_GB \
  --region=$REGION \
  --version=$REDIS_VERSION \
  --network=$NETWORK \
  --redis-config=maxmemory-policy=allkeys-lru \
  --display-name="TalkGPT Redis Cache" \
  --async || echo "Redis instance already exists or creation in progress"

# Wait for instance to be ready
echo -e "${BLUE}Waiting for Redis instance to be ready...${NC}"
while true; do
  STATUS=$(gcloud redis instances describe $REDIS_INSTANCE_ID --region=$REGION --format="value(state)")
  if [ "$STATUS" = "READY" ]; then
    echo -e "${GREEN}✓ Redis instance is ready!${NC}"
    break
  elif [ "$STATUS" = "CREATING" ]; then
    echo -e "${BLUE}  Status: Creating... (checking again in 30s)${NC}"
    sleep 30
  else
    echo -e "${RED}Unexpected status: $STATUS${NC}"
    break
  fi
done

# Get Redis connection details
echo -e "${BLUE}Retrieving Redis connection details...${NC}"
REDIS_HOST=$(gcloud redis instances describe $REDIS_INSTANCE_ID --region=$REGION --format="value(host)")
REDIS_PORT=$(gcloud redis instances describe $REDIS_INSTANCE_ID --region=$REGION --format="value(port)")

# Create auth string (if auth is enabled)
REDIS_AUTH=$(gcloud redis instances describe $REDIS_INSTANCE_ID --region=$REGION --format="value(authString)" 2>/dev/null || echo "")

# Output connection information
echo -e "${GREEN}✓ Redis setup completed!${NC}"
echo -e "${BLUE}Redis Connection Details:${NC}"
echo "  Host: $REDIS_HOST"
echo "  Port: $REDIS_PORT"
if [ ! -z "$REDIS_AUTH" ]; then
  echo "  Auth: [REDACTED - check Secret Manager]"
  REDIS_URL="redis://:${REDIS_AUTH}@${REDIS_HOST}:${REDIS_PORT}/0"
else
  REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"
fi

# Store Redis URL in Secret Manager
echo -e "${BLUE}Storing Redis URL in Secret Manager...${NC}"
echo $REDIS_URL | gcloud secrets create talkgpt-redis-url --data-file=- || \
echo $REDIS_URL | gcloud secrets versions add talkgpt-redis-url --data-file=-

echo -e "${GREEN}✓ Redis URL stored in Secret Manager as 'talkgpt-redis-url'${NC}"
echo -e "${BLUE}Next: Create GKE cluster with create-cluster.sh${NC}"