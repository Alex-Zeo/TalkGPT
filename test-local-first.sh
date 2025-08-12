#!/bin/bash

# Test TalkGPT locally first, then test GCP deployment

set -e

# Variables
INPUT_FILE="process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav"
TEST_FILE="test_audio_1min.wav"
OUTPUT_DIR="local-test-output"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Testing TalkGPT Locally Before GCP Deployment${NC}"
echo -e "${BLUE}=============================================${NC}"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}✗ Input file not found: $INPUT_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Input file found: $INPUT_FILE${NC}"

# Extract first minute
echo -e "${BLUE}Extracting first minute of audio...${NC}"
ffmpeg -i "$INPUT_FILE" -t 60 -c copy "$TEST_FILE" -y -loglevel quiet
echo -e "${GREEN}✓ Created 1-minute test file: $TEST_FILE${NC}"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Test local transcription
echo -e "${BLUE}Testing local transcription...${NC}"
python -m src.cli.main transcribe "$TEST_FILE" \
    --output "$OUTPUT_DIR" \
    --format srt,json,txt \
    --model-size base \
    --log-level INFO

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Local transcription completed${NC}"
else
    echo -e "${RED}✗ Local transcription failed${NC}"
    exit 1
fi

# Display results
echo -e "${BLUE}Local Transcription Results:${NC}"
echo "==========================="

# Show text output
TXT_FILE=$(find "$OUTPUT_DIR" -name "*.txt" | head -1)
if [ -f "$TXT_FILE" ]; then
    echo -e "${GREEN}Transcript:${NC}"
    cat "$TXT_FILE"
    echo ""
fi

# Show SRT sample
SRT_FILE=$(find "$OUTPUT_DIR" -name "*.srt" | head -1)
if [ -f "$SRT_FILE" ]; then
    echo -e "${GREEN}Subtitle Sample (first 10 lines):${NC}"
    head -10 "$SRT_FILE"
    echo ""
fi

echo -e "${GREEN}✓ Local test successful! Now ready to test GCP deployment.${NC}"
echo ""
echo -e "${BLUE}Next: Run the GCP test with:${NC}"
echo "./test-gcp-transcription.sh"

# Clean up
rm -f "$TEST_FILE"