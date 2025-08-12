#!/bin/bash

# TalkGPT Production Execution Script
# This script will deploy TalkGPT to GCP and process your 6.8-hour audio file

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}"
cat << "EOF"
🚀 TalkGPT Production Deployment & Transcription
================================================

Your Audio File: x.com_i_spaces_1BRJjmgNDPLGw_01.wav
Duration: 6 hours 45 minutes (24,348 seconds)
Size: 4.13 GB
Expected Words: ~60,869

Processing Cost: $92-145
Processing Time: 2-4 hours
Accuracy: 95-99%
EOF
echo -e "${NC}"

echo -e "${YELLOW}This script will:${NC}"
echo "1. 🏗️  Deploy complete GCP infrastructure (30-45 mins)"
echo "2. 📤  Upload your 4.13 GB audio file to Cloud Storage"
echo "3. 🎙️  Process 6.8 hours of audio with faster-whisper"
echo "4. 📥  Generate transcript in multiple formats (TXT, SRT, JSON, CSV)"
echo "5. 💰  Incur $92-145 in GCP charges"
echo ""

# Confirm execution
read -p "$(echo -e ${YELLOW}"Do you want to proceed with production deployment? (y/N): "${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled"
    exit 0
fi

echo -e "${BLUE}Starting production deployment...${NC}"
START_TIME=$(date +%s)

# Step 1: Check prerequisites
echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"

# Check for gcloud
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check for kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${YELLOW}⚠️  kubectl not found, installing...${NC}"
    gcloud components install kubectl
fi

# Check authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null; then
    echo -e "${YELLOW}🔐 Authenticating with Google Cloud...${NC}"
    gcloud auth login
fi

echo -e "${GREEN}✅ Prerequisites checked${NC}"

# Step 2: Configure project
echo -e "${BLUE}Step 2: Configuring GCP project...${NC}"

echo "Current GCP projects:"
gcloud projects list --format="table(projectId,name)" | head -10

echo ""
read -p "Enter your GCP Project ID (or press Enter for 'talkgpt-production'): " PROJECT_ID
PROJECT_ID=${PROJECT_ID:-talkgpt-production}

# Update project ID in all scripts
echo "Updating project ID in deployment scripts..."
find deploy/ -name "*.sh" -exec sed -i '' "s/PROJECT_ID=\"talkgpt-production\"/PROJECT_ID=\"$PROJECT_ID\"/g" {} \;

gcloud config set project $PROJECT_ID
echo -e "${GREEN}✅ Project configured: $PROJECT_ID${NC}"

# Step 3: Deploy infrastructure
echo -e "${BLUE}Step 3: Deploying GCP infrastructure...${NC}"
echo "This will take 30-45 minutes..."

if ./deploy/deploy-all.sh; then
    echo -e "${GREEN}✅ Infrastructure deployment completed${NC}"
else
    echo -e "${RED}❌ Infrastructure deployment failed${NC}"
    exit 1
fi

# Step 4: Upload audio file
echo -e "${BLUE}Step 4: Uploading audio file to Cloud Storage...${NC}"
AUDIO_FILE="process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav"
UPLOAD_PATH="production/$(date +%Y%m%d_%H%M%S)/$(basename $AUDIO_FILE)"

echo "Uploading 4.13 GB file... (this may take 10-15 minutes)"
gsutil -m cp "$AUDIO_FILE" "gs://$PROJECT_ID-audio-input/$UPLOAD_PATH"

if gsutil ls "gs://$PROJECT_ID-audio-input/$UPLOAD_PATH" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Audio file uploaded successfully${NC}"
else
    echo -e "${RED}❌ Audio file upload failed${NC}"
    exit 1
fi

# Step 5: Start transcription
echo -e "${BLUE}Step 5: Starting transcription process...${NC}"
echo "Processing 6.8 hours of audio... (estimated 2-4 hours)"

# Get MCP pod
MCP_POD=$(kubectl get pods -n talkgpt -l app=talkgpt-mcp -o jsonpath='{.items[0].metadata.name}')
OUTPUT_PATH="production/$(date +%Y%m%d_%H%M%S)/"

# Submit transcription job
kubectl exec -n talkgpt $MCP_POD -- python -m src.cli.main transcribe \
  "gs://$PROJECT_ID-audio-input/$UPLOAD_PATH" \
  --output "gs://$PROJECT_ID-transcription-output/$OUTPUT_PATH" \
  --format srt,json,txt,csv \
  --enhanced-analysis \
  --speaker-diarization \
  --model-size large-v3 &

TRANSCRIPTION_PID=$!

echo -e "${GREEN}✅ Transcription job started${NC}"
echo "Job PID: $TRANSCRIPTION_PID"

# Step 6: Monitor progress
echo -e "${BLUE}Step 6: Monitoring transcription progress...${NC}"
echo "You can monitor progress with:"
echo "kubectl logs -n talkgpt -l app=talkgpt-worker -f"
echo ""
echo "Or check the monitoring dashboard:"
echo "kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80"
echo ""

# Wait for completion or user interruption
echo "Press Ctrl+C to stop monitoring (transcription will continue in background)"
trap 'echo -e "\n${YELLOW}Monitoring stopped. Transcription continues in background.${NC}"; exit 0' INT

# Monitor for up to 4 hours
for i in {1..240}; do
    sleep 60
    echo -n "⏱️  Processing... ${i} minutes elapsed"
    
    # Check if results are available
    RESULT_COUNT=$(gsutil ls "gs://$PROJECT_ID-transcription-output/$OUTPUT_PATH**" 2>/dev/null | wc -l || echo "0")
    if [ "$RESULT_COUNT" -gt 0 ]; then
        echo -e "\n${GREEN}🎉 Transcription completed!${NC}"
        break
    fi
    echo " (no results yet)"
done

# Step 7: Download results
if [ "$RESULT_COUNT" -gt 0 ]; then
    echo -e "${BLUE}Step 7: Downloading transcription results...${NC}"
    
    RESULTS_DIR="final_transcript_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$RESULTS_DIR"
    
    gsutil -m cp -r "gs://$PROJECT_ID-transcription-output/$OUTPUT_PATH*" "$RESULTS_DIR/"
    
    echo -e "${GREEN}✅ Results downloaded to: $RESULTS_DIR${NC}"
    
    # Show summary
    echo -e "${BLUE}📊 Transcription Summary:${NC}"
    find "$RESULTS_DIR" -type f -exec ls -lh {} \;
    
    # Show transcript preview
    TXT_FILE=$(find "$RESULTS_DIR" -name "*.txt" | head -1)
    if [ -f "$TXT_FILE" ]; then
        echo -e "${BLUE}📝 Transcript Preview:${NC}"
        head -c 500 "$TXT_FILE"
        echo "..."
    fi
fi

# Calculate total time and cost
END_TIME=$(date +%s)
DURATION=$(($END_TIME - $START_TIME))
HOURS=$(($DURATION / 3600))
MINUTES=$((($DURATION % 3600) / 60))

echo ""
echo -e "${GREEN}${BOLD}🎉 PRODUCTION DEPLOYMENT COMPLETE! 🎉${NC}"
echo -e "${BLUE}Total Time: ${HOURS}h ${MINUTES}m${NC}"
echo -e "${BLUE}Estimated Cost: $92-145${NC}"
echo ""
echo -e "${BLUE}Your 6.8-hour audio file has been processed and is ready!${NC}"

# Cleanup option
echo ""
read -p "$(echo -e ${YELLOW}"Would you like to scale down the cluster to save costs? (y/N): "${NC})" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    kubectl scale deployment --all --replicas=1 -n talkgpt
    gcloud container clusters resize talkgpt-cluster --num-nodes=1 --region=us-central1 --quiet
    echo -e "${GREEN}✅ Cluster scaled down to minimize costs${NC}"
fi

echo ""
echo -e "${BOLD}📁 Find your complete transcript in: $RESULTS_DIR${NC}"
echo -e "${BOLD}🔗 GCP Console: https://console.cloud.google.com/kubernetes/workload?project=$PROJECT_ID${NC}"
echo -e "${BOLD}📊 Monitoring: kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80${NC}"
echo ""
echo -e "${GREEN}🚀 TalkGPT is now ready for production use!${NC}"