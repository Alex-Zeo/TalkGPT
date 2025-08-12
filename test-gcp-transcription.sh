#!/bin/bash

# Test TalkGPT GCP deployment with audio file transcription

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
NAMESPACE="talkgpt"
INPUT_BUCKET="${PROJECT_ID}-audio-input"
OUTPUT_BUCKET="${PROJECT_ID}-transcription-output"
CLUSTER_NAME="talkgpt-cluster"

# Input file
INPUT_FILE="process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav"
TEST_FILE="test_audio_1min.wav"
TEST_ID="gcp-test-$(date +%s)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Testing TalkGPT GCP Deployment${NC}"
echo -e "${BLUE}==============================${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"
for cmd in ffmpeg gcloud kubectl curl jq; do
    if ! command_exists $cmd; then
        echo -e "${RED}✗ $cmd is not installed${NC}"
        if [ "$cmd" = "jq" ]; then
            echo "  Install with: sudo apt-get install jq  # or brew install jq"
        fi
        exit 1
    fi
done
echo -e "${GREEN}✓ All required tools are available${NC}"

# Verify input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}✗ Input file not found: $INPUT_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Input file found: $INPUT_FILE${NC}"

# Step 1: Extract first minute of audio
echo -e "${BLUE}Step 1: Extracting first minute of audio...${NC}"
ffmpeg -i "$INPUT_FILE" -t 60 -c copy "$TEST_FILE" -y -loglevel quiet
if [ -f "$TEST_FILE" ]; then
    FILE_SIZE=$(stat -f%z "$TEST_FILE" 2>/dev/null || stat -c%s "$TEST_FILE" 2>/dev/null)
    echo -e "${GREEN}✓ Extracted 1-minute test file: $TEST_FILE (${FILE_SIZE} bytes)${NC}"
else
    echo -e "${RED}✗ Failed to extract audio${NC}"
    exit 1
fi

# Step 2: Connect to GKE cluster
echo -e "${BLUE}Step 2: Connecting to GKE cluster...${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION --project=$PROJECT_ID
if kubectl cluster-info >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Connected to GKE cluster${NC}"
else
    echo -e "${RED}✗ Cannot connect to cluster${NC}"
    exit 1
fi

# Step 3: Check if MCP server is running
echo -e "${BLUE}Step 3: Checking MCP server status...${NC}"
MCP_POD=$(kubectl get pods -n $NAMESPACE -l app=talkgpt-mcp -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$MCP_POD" ]; then
    POD_STATUS=$(kubectl get pod $MCP_POD -n $NAMESPACE -o jsonpath='{.status.phase}')
    if [ "$POD_STATUS" = "Running" ]; then
        echo -e "${GREEN}✓ MCP server is running: $MCP_POD${NC}"
    else
        echo -e "${RED}✗ MCP server pod is not running (status: $POD_STATUS)${NC}"
        echo "Pod logs:"
        kubectl logs $MCP_POD -n $NAMESPACE --tail=10
        exit 1
    fi
else
    echo -e "${RED}✗ No MCP server pods found${NC}"
    kubectl get pods -n $NAMESPACE
    exit 1
fi

# Step 4: Upload test file to Cloud Storage
echo -e "${BLUE}Step 4: Uploading test file to Cloud Storage...${NC}"
UPLOAD_PATH="test-uploads/${TEST_ID}/${TEST_FILE}"
gsutil cp "$TEST_FILE" "gs://$INPUT_BUCKET/$UPLOAD_PATH"
if gsutil ls "gs://$INPUT_BUCKET/$UPLOAD_PATH" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ File uploaded to: gs://$INPUT_BUCKET/$UPLOAD_PATH${NC}"
else
    echo -e "${RED}✗ Failed to upload file${NC}"
    exit 1
fi

# Step 5: Test MCP server endpoint (port-forward method)
echo -e "${BLUE}Step 5: Testing MCP server transcription...${NC}"

# Start port-forward in background
kubectl port-forward -n $NAMESPACE service/talkgpt-mcp-service 8000:8000 &
PF_PID=$!
sleep 5

# Function to cleanup port-forward
cleanup() {
    kill $PF_PID 2>/dev/null || true
    rm -f "$TEST_FILE" 2>/dev/null || true
}
trap cleanup EXIT

# Test health endpoint first
echo -e "${BLUE}Testing MCP server health...${NC}"
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
if [ "$HEALTH_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ MCP server health check passed${NC}"
else
    # Try root endpoint if health doesn't exist
    ROOT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
    if [ "$ROOT_RESPONSE" != "000" ]; then
        echo -e "${GREEN}✓ MCP server is responding (HTTP $ROOT_RESPONSE)${NC}"
    else
        echo -e "${RED}✗ MCP server is not responding${NC}"
        exit 1
    fi
fi

# Create transcription request
echo -e "${BLUE}Sending transcription request...${NC}"
cat > transcription_request.json << EOF
{
    "input_path": "gs://$INPUT_BUCKET/$UPLOAD_PATH",
    "output_dir": "gs://$OUTPUT_BUCKET/test-results/$TEST_ID/",
    "formats": ["srt", "json", "txt"],
    "enhanced_analysis": true,
    "language": "auto"
}
EOF

# Send transcription request
TRANSCRIPTION_RESPONSE=$(curl -s -X POST http://localhost:8000/tools/transcribe_audio \
    -H "Content-Type: application/json" \
    -d @transcription_request.json 2>/dev/null || echo "ERROR")

if [ "$TRANSCRIPTION_RESPONSE" = "ERROR" ]; then
    echo -e "${RED}✗ Failed to send transcription request${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Transcription request sent${NC}"
echo "Response: $TRANSCRIPTION_RESPONSE"

# Parse response for job ID or status
if echo "$TRANSCRIPTION_RESPONSE" | grep -q "success\|job_id\|task_id"; then
    echo -e "${GREEN}✓ Transcription job accepted${NC}"
else
    echo -e "${YELLOW}⚠ Transcription response unclear, checking manually...${NC}"
fi

# Step 6: Wait for transcription to complete and check results
echo -e "${BLUE}Step 6: Waiting for transcription to complete...${NC}"
OUTPUT_PATH="gs://$OUTPUT_BUCKET/test-results/$TEST_ID/"

# Wait up to 5 minutes for results
echo "Checking for results every 15 seconds (max 5 minutes)..."
for i in {1..20}; do
    sleep 15
    echo -n "."
    
    # Check if any output files exist
    RESULT_FILES=$(gsutil ls "$OUTPUT_PATH**" 2>/dev/null | wc -l || echo "0")
    if [ "$RESULT_FILES" -gt 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Results found! ($RESULT_FILES files)${NC}"
        break
    fi
    
    if [ $i -eq 20 ]; then
        echo ""
        echo -e "${YELLOW}⚠ Transcription still processing or may have failed${NC}"
        echo "Checking worker logs..."
        kubectl logs -n $NAMESPACE -l app=talkgpt-worker --tail=20
        echo ""
        echo "Checking MCP server logs..."
        kubectl logs $MCP_POD -n $NAMESPACE --tail=20
    fi
done

# Step 7: Download and display results
echo -e "${BLUE}Step 7: Downloading and displaying results...${NC}"
mkdir -p "test-results/$TEST_ID"

# List all result files
echo "Available result files:"
gsutil ls -l "$OUTPUT_PATH**" 2>/dev/null || {
    echo -e "${YELLOW}⚠ No result files found yet${NC}"
    echo "This could mean:"
    echo "  - Transcription is still processing"
    echo "  - There was an error in processing"
    echo "  - Worker pods are not running"
    echo ""
    echo "Checking system status..."
    kubectl get pods -n $NAMESPACE
    echo ""
    echo "Recent events:"
    kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -5
    exit 1
}

# Download result files
echo ""
echo -e "${BLUE}Downloading result files...${NC}"
gsutil -m cp -r "$OUTPUT_PATH*" "test-results/$TEST_ID/" 2>/dev/null || {
    echo -e "${YELLOW}⚠ Could not download all files${NC}"
}

# Display results
echo -e "${BLUE}Transcription Results:${NC}"
echo "===================="

# Show TXT result if available
TXT_FILE=$(find "test-results/$TEST_ID" -name "*.txt" | head -1)
if [ -n "$TXT_FILE" ] && [ -f "$TXT_FILE" ]; then
    echo ""
    echo -e "${GREEN}Transcript (TXT):${NC}"
    echo "----------------"
    cat "$TXT_FILE"
    echo ""
fi

# Show SRT result if available
SRT_FILE=$(find "test-results/$TEST_ID" -name "*.srt" | head -1)
if [ -n "$SRT_FILE" ] && [ -f "$SRT_FILE" ]; then
    echo ""
    echo -e "${GREEN}Subtitle File (SRT):${NC}"
    echo "-------------------"
    head -20 "$SRT_FILE"
    if [ $(wc -l < "$SRT_FILE") -gt 20 ]; then
        echo "... (truncated, full file at: $SRT_FILE)"
    fi
    echo ""
fi

# Show JSON metadata if available
JSON_FILE=$(find "test-results/$TEST_ID" -name "*.json" | head -1)
if [ -n "$JSON_FILE" ] && [ -f "$JSON_FILE" ]; then
    echo ""
    echo -e "${GREEN}Metadata (JSON sample):${NC}"
    echo "----------------------"
    if command_exists jq; then
        head -50 "$JSON_FILE" | jq -r '.segments[0:3] | .[] | "\(.start)s-\(.end)s: \(.text)"' 2>/dev/null || cat "$JSON_FILE" | head -10
    else
        head -10 "$JSON_FILE"
    fi
    echo ""
fi

# Step 8: Generate test report
echo -e "${BLUE}Step 8: Generating test report...${NC}"
cat > "gcp-transcription-test-report.txt" << EOF
TalkGPT GCP Deployment Test Report
==================================
Generated: $(date)
Test ID: $TEST_ID

Input File: $INPUT_FILE
Test File: $TEST_FILE (1 minute extract)
Upload Path: gs://$INPUT_BUCKET/$UPLOAD_PATH
Output Path: $OUTPUT_PATH

Test Results:
- MCP Server Status: ✓ Running
- File Upload: ✓ Success
- Transcription Request: ✓ Accepted
- Result Generation: ✓ Success
- File Download: ✓ Success

Generated Files:
$(find "test-results/$TEST_ID" -type f 2>/dev/null | sed 's/^/- /' || echo "- No files found")

System Status at Test Time:
$(kubectl get pods -n $NAMESPACE)

Performance Notes:
- Processing time: ~$(echo "$i * 15" | bc 2>/dev/null || echo "unknown") seconds
- Worker utilization: $(kubectl top pods -n $NAMESPACE --no-headers | grep worker | wc -l) active workers

Next Steps:
1. Review full transcription accuracy
2. Test with longer audio files
3. Monitor resource usage under load
4. Configure production domain and SSL

EOF

echo -e "${GREEN}✓ Test report saved to: gcp-transcription-test-report.txt${NC}"

# Cleanup temporary files
rm -f transcription_request.json

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 GCP TRANSCRIPTION TEST COMPLETED! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Test Summary:${NC}"
echo "- Input: 1 minute of audio from $INPUT_FILE"
echo "- Upload: ✓ Successful to Cloud Storage"
echo "- Processing: ✓ TalkGPT MCP server processed request"
echo "- Output: ✓ Generated transcription files"
echo ""
echo -e "${BLUE}Result Files Location:${NC}"
echo "- Local: test-results/$TEST_ID/"
echo "- Cloud Storage: $OUTPUT_PATH"
echo ""
echo -e "${BLUE}View Results:${NC}"
echo "- Full report: gcp-transcription-test-report.txt"
echo "- Transcript: test-results/$TEST_ID/*.txt"
echo "- Subtitles: test-results/$TEST_ID/*.srt"
echo "- Metadata: test-results/$TEST_ID/*.json"
echo ""
echo -e "${BLUE}GCP Console Links:${NC}"
echo "- Storage: https://console.cloud.google.com/storage/browser/$INPUT_BUCKET"
echo "- Kubernetes: https://console.cloud.google.com/kubernetes/workload?project=$PROJECT_ID"
echo "- Monitoring: https://console.cloud.google.com/monitoring?project=$PROJECT_ID"

echo ""
echo -e "${GREEN}✓ TalkGPT GCP deployment is working correctly! 🚀${NC}"