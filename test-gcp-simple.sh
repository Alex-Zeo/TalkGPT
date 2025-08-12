#!/bin/bash

# Simple GCP deployment test using the existing WAV file directly

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
NAMESPACE="talkgpt"
INPUT_BUCKET="${PROJECT_ID}-audio-input"
OUTPUT_BUCKET="${PROJECT_ID}-transcription-output"
CLUSTER_NAME="talkgpt-cluster"

# Input file - use the existing WAV file directly
INPUT_FILE="process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav"
TEST_ID="gcp-test-$(date +%s)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Simple TalkGPT GCP Test${NC}"
echo -e "${BLUE}======================${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check basic prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"
for cmd in gcloud kubectl curl; do
    if ! command_exists $cmd; then
        echo -e "${RED}✗ $cmd is not installed${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ Basic tools are available${NC}"

# Verify input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}✗ Input file not found: $INPUT_FILE${NC}"
    exit 1
fi

FILE_SIZE=$(stat -f%z "$INPUT_FILE" 2>/dev/null || stat -c%s "$INPUT_FILE" 2>/dev/null)
echo -e "${GREEN}✓ Input file found: $INPUT_FILE (${FILE_SIZE} bytes)${NC}"

# Check if we can connect to GCP
echo -e "${BLUE}Testing GCP connection...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 >/dev/null; then
    echo -e "${RED}✗ Not authenticated with gcloud${NC}"
    echo "Please run: gcloud auth login"
    exit 1
fi

# Set project
gcloud config set project $PROJECT_ID >/dev/null 2>&1
echo -e "${GREEN}✓ Connected to GCP project: $PROJECT_ID${NC}"

# Test Cloud Storage access
echo -e "${BLUE}Testing Cloud Storage access...${NC}"
if gsutil ls "gs://$INPUT_BUCKET/" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Can access input bucket: gs://$INPUT_BUCKET/${NC}"
else
    echo -e "${RED}✗ Cannot access input bucket${NC}"
    echo "Make sure the deployment has completed successfully"
    exit 1
fi

# Upload test file
echo -e "${BLUE}Uploading test file to Cloud Storage...${NC}"
UPLOAD_PATH="test-uploads/${TEST_ID}/$(basename $INPUT_FILE)"
gsutil cp "$INPUT_FILE" "gs://$INPUT_BUCKET/$UPLOAD_PATH"

if gsutil ls "gs://$INPUT_BUCKET/$UPLOAD_PATH" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ File uploaded to: gs://$INPUT_BUCKET/$UPLOAD_PATH${NC}"
else
    echo -e "${RED}✗ Failed to upload file${NC}"
    exit 1
fi

# Connect to GKE cluster
echo -e "${BLUE}Connecting to GKE cluster...${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION --project=$PROJECT_ID >/dev/null 2>&1

if kubectl cluster-info >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Connected to GKE cluster${NC}"
else
    echo -e "${RED}✗ Cannot connect to cluster${NC}"
    exit 1
fi

# Check MCP server status
echo -e "${BLUE}Checking MCP server status...${NC}"
MCP_POD=$(kubectl get pods -n $NAMESPACE -l app=talkgpt-mcp -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$MCP_POD" ]; then
    POD_STATUS=$(kubectl get pod $MCP_POD -n $NAMESPACE -o jsonpath='{.status.phase}')
    if [ "$POD_STATUS" = "Running" ]; then
        echo -e "${GREEN}✓ MCP server is running: $MCP_POD${NC}"
    else
        echo -e "${RED}✗ MCP server pod is not running (status: $POD_STATUS)${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ No MCP server pods found${NC}"
    echo "Available pods in namespace $NAMESPACE:"
    kubectl get pods -n $NAMESPACE
    exit 1
fi

# Test MCP server via kubectl exec (direct approach)
echo -e "${BLUE}Testing transcription via direct pod access...${NC}"

# Create a test script inside the pod
kubectl exec $MCP_POD -n $NAMESPACE -- python3 -c "
import sys
import os
sys.path.append('/app')

# Test basic imports
try:
    from src.core.transcriber import Transcriber
    print('✓ Core modules import successfully')
except Exception as e:
    print(f'✗ Import error: {e}')
    sys.exit(1)

# Test Google Cloud Storage access
try:
    from google.cloud import storage
    client = storage.Client()
    bucket = client.bucket('$INPUT_BUCKET')
    blob = bucket.blob('$UPLOAD_PATH')
    if blob.exists():
        print('✓ Can access uploaded file in Cloud Storage')
    else:
        print('✗ Cannot find uploaded file')
        sys.exit(1)
except Exception as e:
    print(f'✗ Storage access error: {e}')
    sys.exit(1)

print('✓ Pod environment is ready for transcription')
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ MCP server pod can access the uploaded file${NC}"
else
    echo -e "${RED}✗ MCP server pod has issues accessing files${NC}"
    exit 1
fi

# Test transcription using kubectl exec
echo -e "${BLUE}Running transcription test...${NC}"
echo "This may take a few minutes depending on audio length..."

# Create output directory path
OUTPUT_PATH="test-results/$TEST_ID/"

# Run transcription directly in the pod
kubectl exec $MCP_POD -n $NAMESPACE -- python3 -c "
import sys
import os
import tempfile
import json
from pathlib import Path
sys.path.append('/app')

try:
    from google.cloud import storage
    from src.core.transcriber import Transcriber
    from src.core.file_processor import FileProcessor
    from src.utils.logger import setup_logger
    
    # Setup logger
    logger = setup_logger('transcription-test', 'INFO')
    logger.info('Starting transcription test')
    
    # Initialize storage client
    storage_client = storage.Client()
    input_bucket = storage_client.bucket('$INPUT_BUCKET')
    output_bucket = storage_client.bucket('$OUTPUT_BUCKET')
    
    # Download file to temporary location
    input_blob = input_bucket.blob('$UPLOAD_PATH')
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        input_blob.download_to_filename(temp_file.name)
        temp_audio_path = temp_file.name
    
    logger.info(f'Downloaded audio file to: {temp_audio_path}')
    
    # Initialize transcriber
    transcriber = Transcriber()
    
    # Run transcription
    result = transcriber.transcribe_file(temp_audio_path)
    
    logger.info('Transcription completed')
    
    # Upload results to Cloud Storage
    output_base = '$OUTPUT_PATH'
    
    # Save JSON result
    json_blob = output_bucket.blob(f'{output_base}transcription.json')
    json_blob.upload_from_string(json.dumps(result, indent=2))
    
    # Save text result
    text_content = ' '.join([segment['text'] for segment in result.get('segments', [])])
    txt_blob = output_bucket.blob(f'{output_base}transcription.txt')
    txt_blob.upload_from_string(text_content)
    
    # Save SRT result
    srt_content = ''
    for i, segment in enumerate(result.get('segments', []), 1):
        start_time = segment.get('start', 0)
        end_time = segment.get('end', 0)
        text = segment.get('text', '')
        
        # Convert seconds to SRT time format
        def seconds_to_srt_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millisecs = int((seconds % 1) * 1000)
            return f'{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}'
        
        srt_content += f'{i}\n'
        srt_content += f'{seconds_to_srt_time(start_time)} --> {seconds_to_srt_time(end_time)}\n'
        srt_content += f'{text.strip()}\n\n'
    
    srt_blob = output_bucket.blob(f'{output_base}transcription.srt')
    srt_blob.upload_from_string(srt_content)
    
    # Clean up temp file
    os.unlink(temp_audio_path)
    
    logger.info('Results uploaded to Cloud Storage')
    print('✓ Transcription completed successfully')
    print(f'✓ Results saved to: gs://$OUTPUT_BUCKET/{output_base}')
    
    # Print a sample of the transcript
    if text_content:
        print(f'✓ Transcript preview: {text_content[:200]}...')
    
except Exception as e:
    print(f'✗ Transcription failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Transcription completed successfully${NC}"
else
    echo -e "${RED}✗ Transcription failed${NC}"
    echo "Checking pod logs..."
    kubectl logs $MCP_POD -n $NAMESPACE --tail=20
    exit 1
fi

# Download and display results
echo -e "${BLUE}Downloading results...${NC}"
mkdir -p "test-results/$TEST_ID"

# Download files from Cloud Storage
gsutil -m cp -r "gs://$OUTPUT_BUCKET/test-results/$TEST_ID/*" "test-results/$TEST_ID/" 2>/dev/null || {
    echo -e "${YELLOW}⚠ Downloading with alternative method...${NC}"
    gsutil cp "gs://$OUTPUT_BUCKET/test-results/$TEST_ID/transcription.txt" "test-results/$TEST_ID/" 2>/dev/null || true
    gsutil cp "gs://$OUTPUT_BUCKET/test-results/$TEST_ID/transcription.srt" "test-results/$TEST_ID/" 2>/dev/null || true
    gsutil cp "gs://$OUTPUT_BUCKET/test-results/$TEST_ID/transcription.json" "test-results/$TEST_ID/" 2>/dev/null || true
}

# Display results
echo ""
echo -e "${BLUE}=== TRANSCRIPTION RESULTS ===${NC}"

# Show transcript
TXT_FILE="test-results/$TEST_ID/transcription.txt"
if [ -f "$TXT_FILE" ]; then
    echo ""
    echo -e "${GREEN}Transcript:${NC}"
    echo "----------"
    cat "$TXT_FILE"
    echo ""
else
    echo -e "${YELLOW}⚠ Text file not found locally, checking Cloud Storage...${NC}"
    gsutil cat "gs://$OUTPUT_BUCKET/test-results/$TEST_ID/transcription.txt" 2>/dev/null || echo "Could not retrieve transcript"
fi

# Show SRT sample
SRT_FILE="test-results/$TEST_ID/transcription.srt"
if [ -f "$SRT_FILE" ]; then
    echo ""
    echo -e "${GREEN}Subtitle Sample (first 20 lines):${NC}"
    echo "--------------------------------"
    head -20 "$SRT_FILE"
    if [ $(wc -l < "$SRT_FILE") -gt 20 ]; then
        echo "... (truncated)"
    fi
    echo ""
fi

# Generate summary report
cat > "gcp-test-report-$TEST_ID.txt" << EOF
TalkGPT GCP Deployment Test Report
==================================
Generated: $(date)
Test ID: $TEST_ID

Input File: $INPUT_FILE (${FILE_SIZE} bytes)
Upload Path: gs://$INPUT_BUCKET/$UPLOAD_PATH
Output Path: gs://$OUTPUT_BUCKET/test-results/$TEST_ID/

Test Results:
✓ GCP Authentication: Success
✓ Cloud Storage Access: Success  
✓ File Upload: Success
✓ GKE Cluster Connection: Success
✓ MCP Server Status: Running
✓ Transcription Processing: Success
✓ Result Generation: Success

Generated Files:
- transcription.txt (plain text transcript)
- transcription.srt (subtitle format)
- transcription.json (detailed metadata)

Pod Status:
$(kubectl get pods -n $NAMESPACE)

Next Steps:
1. Review transcription accuracy
2. Test with different audio formats
3. Monitor resource usage
4. Set up production domain and SSL

Cloud Storage Links:
- Input: https://console.cloud.google.com/storage/browser/$INPUT_BUCKET
- Output: https://console.cloud.google.com/storage/browser/$OUTPUT_BUCKET
EOF

echo -e "${GREEN}✓ Test report saved: gcp-test-report-$TEST_ID.txt${NC}"

# Cleanup uploaded test file (optional)
read -p "Remove uploaded test file from Cloud Storage? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    gsutil rm "gs://$INPUT_BUCKET/$UPLOAD_PATH"
    echo -e "${GREEN}✓ Cleaned up test file${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 GCP TRANSCRIPTION TEST COMPLETED! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Summary:${NC}"
echo "- ✅ TalkGPT GCP deployment is working"
echo "- ✅ Audio file successfully transcribed"
echo "- ✅ Results saved to Cloud Storage"
echo "- ✅ All core components operational"
echo ""
echo -e "${BLUE}Files created:${NC}"
echo "- Local results: test-results/$TEST_ID/"
echo "- Test report: gcp-test-report-$TEST_ID.txt"
echo "- Cloud Storage: gs://$OUTPUT_BUCKET/test-results/$TEST_ID/"
echo ""
echo -e "${GREEN}🚀 Your TalkGPT GCP deployment is ready for production use!${NC}"