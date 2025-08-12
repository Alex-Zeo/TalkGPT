#!/bin/bash

# Set up Cloud Storage buckets for TalkGPT

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
INPUT_BUCKET="${PROJECT_ID}-audio-input"
OUTPUT_BUCKET="${PROJECT_ID}-transcription-output"
MODELS_BUCKET="${PROJECT_ID}-models-cache"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up Cloud Storage buckets for TalkGPT...${NC}"

# Create input bucket for audio files
echo -e "${BLUE}Creating audio input bucket...${NC}"
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$INPUT_BUCKET/ || echo "Input bucket already exists"

# Create output bucket for transcription results
echo -e "${BLUE}Creating transcription output bucket...${NC}"
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$OUTPUT_BUCKET/ || echo "Output bucket already exists"

# Create models cache bucket for faster-whisper models
echo -e "${BLUE}Creating models cache bucket...${NC}"
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$MODELS_BUCKET/ || echo "Models bucket already exists"

# Set lifecycle policies for cost optimization
echo -e "${BLUE}Setting up lifecycle policies...${NC}"

# Input bucket: move to coldline after 30 days, delete after 90 days
cat > /tmp/input-lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 30}
      },
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90}
      }
    ]
  }
}
EOF

# Output bucket: move to nearline after 7 days, coldline after 30 days
cat > /tmp/output-lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {"age": 7}
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 30}
      }
    ]
  }
}
EOF

# Models bucket: keep as standard (frequently accessed)
cat > /tmp/models-lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 365}
      }
    ]
  }
}
EOF

# Apply lifecycle policies
gsutil lifecycle set /tmp/input-lifecycle.json gs://$INPUT_BUCKET/
gsutil lifecycle set /tmp/output-lifecycle.json gs://$OUTPUT_BUCKET/
gsutil lifecycle set /tmp/models-lifecycle.json gs://$MODELS_BUCKET/

# Set appropriate permissions
echo -e "${BLUE}Setting bucket permissions...${NC}"

# Grant TalkGPT service account access to buckets
gsutil iam ch serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com:roles/storage.admin gs://$INPUT_BUCKET/
gsutil iam ch serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com:roles/storage.admin gs://$OUTPUT_BUCKET/
gsutil iam ch serviceAccount:talkgpt-service@$PROJECT_ID.iam.gserviceaccount.com:roles/storage.admin gs://$MODELS_BUCKET/

# Enable uniform bucket-level access for better security
gsutil uniformbucketlevelaccess set on gs://$INPUT_BUCKET/
gsutil uniformbucketlevelaccess set on gs://$OUTPUT_BUCKET/
gsutil uniformbucketlevelaccess set on gs://$MODELS_BUCKET/

# Create directory structure in buckets
echo -e "${BLUE}Creating directory structure...${NC}"
echo "Directory structure placeholder" | gsutil cp - gs://$INPUT_BUCKET/uploads/.keep
echo "Directory structure placeholder" | gsutil cp - gs://$OUTPUT_BUCKET/results/.keep
echo "Directory structure placeholder" | gsutil cp - gs://$MODELS_BUCKET/whisper-models/.keep

# Clean up temp files
rm -f /tmp/*-lifecycle.json

echo -e "${GREEN}✓ Cloud Storage setup completed!${NC}"
echo -e "${BLUE}Buckets created:${NC}"
echo "  - Input: gs://$INPUT_BUCKET/"
echo "  - Output: gs://$OUTPUT_BUCKET/"
echo "  - Models: gs://$MODELS_BUCKET/"
echo -e "${BLUE}Next: Set up Redis with setup-redis.sh${NC}"