# TalkGPT GCP Transcription Test Guide

This guide demonstrates how to test your TalkGPT GCP deployment using the provided audio file.

## Audio File Information

**File:** `process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav`
- **Size:** 4.4 GB (very large file)
- **Format:** WAV audio
- **Estimated Duration:** ~6-8 hours (based on file size)

## Testing Options

### Option 1: Quick Test with File Segment (Recommended)

For initial testing, extract a smaller segment to avoid long processing times and high costs:

```bash
# Extract first 5 minutes for testing (requires ffmpeg)
ffmpeg -i process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav -t 300 -c copy test_5min.wav

# Or extract 30 seconds for quick validation
ffmpeg -i process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav -t 30 -c copy test_30sec.wav
```

### Option 2: Full File Processing (Production Test)

For complete transcription of the full file:

**⚠️ Important Considerations:**
- **Processing Time:** 6-8 hours estimated
- **Cost:** $50-100+ in GCP charges (GPU usage, storage, compute)
- **Resources:** Will heavily utilize GPU workers and storage

## Step-by-Step Test Procedure

### Prerequisites

1. **GCP Deployment Completed**
   ```bash
   # Verify deployment
   kubectl get pods -n talkgpt
   kubectl get services -n talkgpt
   ```

2. **Authentication Setup**
   ```bash
   gcloud auth login
   gcloud config set project talkgpt-production
   ```

3. **Tools Installed**
   - `gcloud` CLI
   - `kubectl`
   - `gsutil`
   - `ffmpeg` (for file segmentation)

### Test Execution

#### Step 1: Prepare Test File

```bash
# For quick test (30 seconds)
ffmpeg -i process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav -t 30 -c copy test_sample.wav

# Check file size (should be much smaller)
ls -lh test_sample.wav
```

#### Step 2: Upload to Cloud Storage

```bash
# Upload to input bucket
TEST_ID="transcription-test-$(date +%s)"
gsutil cp test_sample.wav gs://talkgpt-production-audio-input/test/$TEST_ID/
```

#### Step 3: Connect to GKE Cluster

```bash
gcloud container clusters get-credentials talkgpt-cluster --region=us-central1
kubectl get pods -n talkgpt
```

#### Step 4: Run Transcription Test

**Method A: Via MCP API Endpoint**

```bash
# Port forward to MCP server
kubectl port-forward -n talkgpt service/talkgpt-mcp-service 8000:8000 &

# Send transcription request
curl -X POST http://localhost:8000/tools/transcribe_audio \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "gs://talkgpt-production-audio-input/test/'$TEST_ID'/test_sample.wav",
    "output_dir": "gs://talkgpt-production-transcription-output/test/'$TEST_ID'/",
    "formats": ["srt", "json", "txt"],
    "enhanced_analysis": true,
    "language": "auto"
  }'
```

**Method B: Direct Pod Execution**

```bash
# Get MCP pod name
MCP_POD=$(kubectl get pods -n talkgpt -l app=talkgpt-mcp -o jsonpath='{.items[0].metadata.name}')

# Run transcription directly in pod
kubectl exec $MCP_POD -n talkgpt -- python -m src.cli.main transcribe \
  gs://talkgpt-production-audio-input/test/$TEST_ID/test_sample.wav \
  --output gs://talkgpt-production-transcription-output/test/$TEST_ID/ \
  --format srt,json,txt
```

#### Step 5: Monitor Processing

```bash
# Check worker pod logs
kubectl logs -n talkgpt -l app=talkgpt-worker -f

# Check resource usage
kubectl top pods -n talkgpt
kubectl get hpa -n talkgpt
```

#### Step 6: Retrieve Results

```bash
# Wait for completion (30 seconds should process quickly)
sleep 60

# Download results
mkdir -p results/$TEST_ID
gsutil -m cp -r gs://talkgpt-production-transcription-output/test/$TEST_ID/* results/$TEST_ID/

# View transcript
cat results/$TEST_ID/*.txt
```

## Expected Results

### For 30-second Sample:
- **Processing Time:** 1-3 minutes
- **Cost:** <$1
- **Files Generated:**
  - `transcript.txt` - Plain text transcript
  - `transcript.srt` - Subtitle file with timestamps
  - `transcript.json` - Detailed metadata with confidence scores

### Sample Output Structure:

**Text Transcript (`transcript.txt`):**
```
[Sample transcript text will appear here based on audio content]
```

**SRT Subtitle (`transcript.srt`):**
```
1
00:00:00,000 --> 00:00:05,000
[First segment of speech]

2
00:00:05,000 --> 00:00:10,000
[Second segment of speech]
```

**JSON Metadata (`transcript.json`):**
```json
{
  "text": "Full transcript text...",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 5.0,
      "text": "First segment",
      "confidence": 0.95
    }
  ],
  "language": "en",
  "duration": 30.0
}
```

## Full File Processing (Production Test)

### When to Run Full File:
- After successful testing with smaller segments
- When you need the complete transcript
- For production workload validation

### Full File Procedure:

```bash
# Upload full file (will take 10-15 minutes)
gsutil -m cp process/x.com_i_spaces_1BRJjmgNDPLGw_01.wav \
  gs://talkgpt-production-audio-input/production/full-audio.wav

# Submit transcription job
FULL_TEST_ID="full-transcription-$(date +%s)"
kubectl exec $MCP_POD -n talkgpt -- python -m src.cli.main transcribe \
  gs://talkgpt-production-audio-input/production/full-audio.wav \
  --output gs://talkgpt-production-transcription-output/production/$FULL_TEST_ID/ \
  --format srt,json,txt \
  --enhanced-analysis

# Monitor progress (will take several hours)
kubectl logs -n talkgpt -l app=talkgpt-worker -f
```

### Expected Full File Results:
- **Processing Time:** 4-8 hours
- **Cost:** $50-150 (depending on GPU usage)
- **Output Size:** 10-50 MB (text files)
- **Accuracy:** High-quality transcript with timestamps

## Monitoring & Troubleshooting

### Check System Health:
```bash
kubectl get pods -n talkgpt
kubectl get hpa -n talkgpt
kubectl top nodes
kubectl get events -n talkgpt --sort-by=.lastTimestamp
```

### Common Issues:

1. **Pod Out of Memory:**
   - Large files may exceed pod memory limits
   - Solution: Increase worker resource limits

2. **Processing Timeout:**
   - Very long files may timeout
   - Solution: Increase job timeout settings

3. **Storage Errors:**
   - Check bucket permissions
   - Verify service account access

### Resource Monitoring:
```bash
# Check GPU utilization
kubectl logs -n talkgpt -l app=talkgpt-worker-gpu

# Monitor costs
gcloud billing budgets list
```

## Cost Optimization Tips

1. **Use CPU workers for shorter files** (<30 min)
2. **Reserve GPU workers for long files** (>1 hour)
3. **Delete processed files** from storage after download
4. **Scale down cluster** when not in use
5. **Use preemptible nodes** for non-urgent jobs

## Cleanup

```bash
# Remove test files
gsutil -m rm -r gs://talkgpt-production-audio-input/test/$TEST_ID/
gsutil -m rm -r gs://talkgpt-production-transcription-output/test/$TEST_ID/

# Stop port forwarding
killall kubectl
```

## Next Steps

After successful testing:

1. **Configure production domain** and SSL certificate
2. **Set up automated backup** of transcriptions
3. **Implement API authentication** for security
4. **Configure monitoring alerts** for failures
5. **Document user API** for client integration

## API Integration Example

Once tested, clients can use the API programmatically:

```python
import requests

def transcribe_audio(file_path, output_format=['txt', 'srt']):
    response = requests.post('https://your-domain.com/tools/transcribe_audio', 
                           json={
                               'input_path': file_path,
                               'formats': output_format,
                               'enhanced_analysis': True
                           })
    return response.json()

# Usage
result = transcribe_audio('gs://your-bucket/audio.wav')
print(result)
```

This completes the comprehensive testing guide for your TalkGPT GCP deployment using the provided audio file.