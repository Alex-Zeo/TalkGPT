# TalkGPT Production Schema & Database Documentation

## Overview
This document contains the complete schema definitions for TalkGPT production deployment, including JSON output schemas, content bucket structures, and database schemas for the timing analysis system.

## JSON Schema Definitions

### 1. Core Transcription Output Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TalkGPT Enhanced Transcription Output",
  "type": "object",
  "required": ["metadata", "transcription", "timing_analysis"],
  "properties": {
    "metadata": {
      "type": "object",
      "properties": {
        "version": { "type": "string", "example": "0.2.0" },
        "format": { "type": "string", "example": "TalkGPT Enhanced JSON with Timing Analysis v1.0" },
        "generated_at": { "type": "string", "format": "date-time" },
        "features": {
          "type": "array",
          "items": { "type": "string" },
          "example": ["word_timestamps", "timing_analysis", "cadence_analysis"]
        }
      }
    },
    "transcription": {
      "type": "object",
      "properties": {
        "language": { "type": "string", "example": "en" },
        "language_probability": { "type": "number", "minimum": 0, "maximum": 1 },
        "total_duration": { "type": "number", "minimum": 0 }
      }
    },
    "timing_analysis": {
      "type": "object",
      "properties": {
        "bucket_count": { "type": "integer", "minimum": 0 },
        "buckets": {
          "type": "array",
          "items": { "$ref": "#/definitions/TimingBucket" }
        },
        "global_cadence": { "$ref": "#/definitions/GlobalCadence" }
      }
    },
    "speaker_analysis": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "speaker_count": { "type": "integer", "minimum": 0 },
        "overlaps_detected": { "type": "integer", "minimum": 0 }
      }
    },
    "uncertainty_analysis": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "overall_score": { "type": "number", "minimum": 0, "maximum": 1 },
        "flagged_segments": { "type": "integer", "minimum": 0 },
        "flagged_percentage": { "type": "number", "minimum": 0, "maximum": 100 }
      }
    },
    "confidence_reprocessing": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "total_segments": { "type": "integer", "minimum": 0 },
        "reprocessed_segments": { "type": "integer", "minimum": 0 },
        "reprocessing_rate": { "type": "number", "minimum": 0, "maximum": 1 },
        "average_confidence_improvement": { "type": "number" },
        "max_confidence_improvement": { "type": "number" },
        "confidence_threshold_used": { "type": "number" },
        "slow_speed_multiplier": { "type": "number", "minimum": 0.1, "maximum": 1.0 },
        "context_padding_seconds": { "type": "number", "minimum": 0 }
      }
    }
  },
  "definitions": {
    "TimingBucket": {
      "type": "object",
      "properties": {
        "bucket_id": { "type": "string" },
        "start_ts": { "type": "number", "minimum": 0 },
        "end_ts": { "type": "number", "minimum": 0 },
        "duration": { "type": "number", "minimum": 0 },
        "text": { "type": "string" },
        "word_count": { "type": "integer", "minimum": 0 },
        "words": {
          "type": "array",
          "items": { "$ref": "#/definitions/WordTimestamp" }
        },
        "timing_metrics": { "$ref": "#/definitions/TimingMetrics" },
        "quality_metrics": { "$ref": "#/definitions/QualityMetrics" },
        "reprocessed": { "type": "boolean", "default": false },
        "original_confidence": { "type": "number", "description": "Original confidence before reprocessing" }
      }
    },
    "WordTimestamp": {
      "type": "object",
      "properties": {
        "word": { "type": "string" },
        "start": { "type": "number", "minimum": 0 },
        "end": { "type": "number", "minimum": 0 },
        "probability": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "TimingMetrics": {
      "type": "object",
      "properties": {
        "word_gap_count": { "type": "integer", "minimum": 0 },
        "word_gaps": {
          "type": "array",
          "items": { "type": "number", "minimum": 0 }
        },
        "word_gap_mean": { "type": "number", "minimum": 0 },
        "word_gap_var": { "type": "number", "minimum": 0 },
        "words_per_second": { "type": "number", "minimum": 0 },
        "total_speech_time": { "type": "number", "minimum": 0 },
        "total_silence_time": { "type": "number", "minimum": 0 }
      }
    },
    "QualityMetrics": {
      "type": "object",
      "properties": {
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "speaker_overlap": { "type": "boolean" },
        "cadence_anomaly": { "type": "boolean" },
        "cadence_severity": {
          "type": "string",
          "enum": ["low", "medium", "high", "critical"]
        }
      }
    },
    "GlobalCadence": {
      "type": "object",
      "properties": {
        "gap_mean": { "type": "number", "minimum": 0 },
        "gap_std": { "type": "number", "minimum": 0 },
        "total_words": { "type": "integer", "minimum": 0 },
        "total_gaps": { "type": "integer", "minimum": 0 },
        "anomaly_threshold": { "type": "number" },
        "anomalous_buckets": { "type": "integer", "minimum": 0 },
        "gap_percentiles": {
          "type": "object",
          "properties": {
            "p50": { "type": "number" },
            "p75": { "type": "number" },
            "p90": { "type": "number" },
            "p95": { "type": "number" },
            "p99": { "type": "number" }
          }
        },
        "cadence_summary": { "type": "string" }
      }
    }
  }
}
```

### 2. MCP Server API Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TalkGPT MCP API Schema",
  "type": "object",
  "definitions": {
    "TranscriptionRequest": {
      "type": "object",
      "required": ["input_path"],
      "properties": {
        "input_path": {
          "type": "string",
          "description": "Path to audio file (local path or GCS URI)"
        },
        "output_dir": {
          "type": "string",
          "description": "Output directory (local path or GCS URI)"
        },
        "formats": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["srt", "json", "txt", "csv", "md"]
          },
          "default": ["srt", "json", "txt"]
        },
        "enhanced_analysis": {
          "type": "boolean",
          "default": false,
          "description": "Enable timing and cadence analysis"
        },
        "speaker_diarization": {
          "type": "boolean",
          "default": false
        },
        "language": {
          "type": "string",
          "default": "auto",
          "description": "Language code or 'auto' for detection"
        },
        "model_size": {
          "type": "string",
          "enum": ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
          "default": "large-v3"
        },
        "speed_multiplier": {
          "type": "number",
          "minimum": 0.5,
          "maximum": 3.0,
          "default": 1.75,
          "description": "Processing speed optimization (1.75x recommended)"
        }
      }
    },
    "TranscriptionResponse": {
      "type": "object",
      "properties": {
        "job_id": { "type": "string" },
        "status": {
          "type": "string",
          "enum": ["queued", "processing", "completed", "failed"]
        },
        "progress": {
          "type": "number",
          "minimum": 0,
          "maximum": 100
        },
        "output_files": {
          "type": "array",
          "items": { "type": "string" }
        },
        "processing_time": { "type": "number" },
        "error_message": { "type": "string" }
      }
    }
  }
}
```

## Content Bucket Definitions

### 1. Timing Analysis Buckets

TalkGPT uses intelligent content buckets for timing analysis:

```python
class TimingBucket:
    """Content bucket for timing analysis"""
    bucket_id: str              # Unique identifier (e.g., "bucket_0001")
    start_ts: float             # Start timestamp in seconds
    end_ts: float               # End timestamp in seconds
    text: str                   # Transcribed text content
    words: List[WordTimestamp]  # Word-level timestamps
    
    # Timing Metrics
    word_gap_count: int         # Number of gaps between words
    word_gaps: List[float]      # Individual gap durations
    word_gap_mean: float        # Average gap duration
    word_gap_var: float         # Gap variance
    words_per_second: float     # Speaking rate
    total_speech_time: float    # Time spent speaking
    total_silence_time: float   # Time spent in silence
    
    # Quality Metrics
    confidence: float           # Transcription confidence (0-1)
    speaker_overlap: bool       # Multiple speakers detected
    cadence_anomaly: bool       # Unusual pacing detected
    cadence_severity: str       # Severity: "low", "medium", "high", "critical"
```

### 2. Content Categories

```yaml
# Content bucket categories for classification
categories:
  primary:
    - speech: "Primary spoken content"
    - silence: "Gaps and pauses"
    - music: "Musical content"
    - noise: "Background noise"
    
  speech_subcategories:
    - monologue: "Single speaker continuous"
    - dialogue: "Multiple speakers alternating"
    - overlap: "Multiple speakers simultaneous"
    - interruption: "Speaker interruptions"
    
  quality_levels:
    - excellent: "confidence >= 0.95"
    - good: "confidence >= 0.85" 
    - fair: "confidence >= 0.70"
    - poor: "confidence < 0.70"
    
  cadence_types:
    - steady: "Consistent pacing"
    - variable: "Normal variation"
    - irregular: "Unusual patterns"
    - anomalous: "Significant timing issues"
```

### 3. Processing Buckets

```yaml
# GPU processing optimization buckets
processing_buckets:
  chunk_sizes:
    small: 
      duration: 15  # seconds
      use_case: "Real-time processing"
      
    medium:
      duration: 30  # seconds  
      use_case: "Balanced processing"
      
    large:
      duration: 45  # seconds
      use_case: "GPU optimization (default)"
      
    xlarge:
      duration: 60  # seconds
      use_case: "Memory-constrained systems"
      
  priority_levels:
    high: "Speech-heavy content (>70% speech)"
    medium: "Mixed content (30-70% speech)"  
    low: "Silence-heavy content (<30% speech)"
    background: "Music/noise only"
```

## Database Schema

### 1. Core Tables

```sql
-- Main transcription jobs table
CREATE TABLE transcription_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(255) UNIQUE NOT NULL,
    input_path TEXT NOT NULL,
    output_path TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    model_size VARCHAR(20) DEFAULT 'large-v3',
    language VARCHAR(10) DEFAULT 'auto',
    speed_multiplier DECIMAL(3,2) DEFAULT 1.75,
    enhanced_analysis BOOLEAN DEFAULT false,
    speaker_diarization BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    processing_time_seconds INTEGER,
    file_size_bytes BIGINT,
    duration_seconds DECIMAL(10,3),
    error_message TEXT,
    
    -- Indexes for performance
    INDEX idx_job_id (job_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- Timing analysis buckets
CREATE TABLE timing_buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(255) NOT NULL REFERENCES transcription_jobs(job_id),
    bucket_id VARCHAR(50) NOT NULL,
    start_timestamp DECIMAL(10,3) NOT NULL,
    end_timestamp DECIMAL(10,3) NOT NULL,
    duration DECIMAL(10,3) GENERATED ALWAYS AS (end_timestamp - start_timestamp) STORED,
    text TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    
    -- Timing metrics
    word_gap_count INTEGER DEFAULT 0,
    word_gap_mean DECIMAL(8,6),
    word_gap_variance DECIMAL(10,8),
    words_per_second DECIMAL(6,3),
    total_speech_time DECIMAL(8,3),
    total_silence_time DECIMAL(8,3),
    
    -- Quality metrics  
    confidence DECIMAL(4,3) CHECK (confidence >= 0 AND confidence <= 1),
    speaker_overlap BOOLEAN DEFAULT false,
    cadence_anomaly BOOLEAN DEFAULT false,
    cadence_severity VARCHAR(20) CHECK (cadence_severity IN ('low', 'medium', 'high', 'critical')),
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Indexes for analysis queries
    INDEX idx_job_bucket (job_id, bucket_id),
    INDEX idx_timestamps (start_timestamp, end_timestamp),
    INDEX idx_cadence_anomaly (cadence_anomaly, cadence_severity),
    INDEX idx_confidence (confidence)
);

-- Word-level timestamps
CREATE TABLE word_timestamps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bucket_id UUID NOT NULL REFERENCES timing_buckets(id) ON DELETE CASCADE,
    word_index INTEGER NOT NULL,
    word TEXT NOT NULL,
    start_timestamp DECIMAL(10,3) NOT NULL,
    end_timestamp DECIMAL(10,3) NOT NULL, 
    duration DECIMAL(8,3) GENERATED ALWAYS AS (end_timestamp - start_timestamp) STORED,
    probability DECIMAL(4,3) CHECK (probability >= 0 AND probability <= 1),
    
    -- Indexes for word-level analysis
    INDEX idx_bucket_word (bucket_id, word_index),
    INDEX idx_word_timestamps (start_timestamp, end_timestamp),
    INDEX idx_word_text (word),
    UNIQUE(bucket_id, word_index)
);

-- Global cadence analysis results
CREATE TABLE cadence_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(255) NOT NULL REFERENCES transcription_jobs(job_id),
    gap_mean DECIMAL(8,6) NOT NULL,
    gap_std DECIMAL(8,6) NOT NULL,
    total_words INTEGER NOT NULL,
    total_gaps INTEGER NOT NULL,
    anomaly_threshold DECIMAL(4,2) NOT NULL,
    anomalous_buckets INTEGER NOT NULL,
    
    -- Percentiles for gap distribution
    gap_p50 DECIMAL(8,6),
    gap_p75 DECIMAL(8,6),
    gap_p90 DECIMAL(8,6),
    gap_p95 DECIMAL(8,6),
    gap_p99 DECIMAL(8,6),
    
    cadence_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_job_cadence (job_id),
    UNIQUE(job_id)  -- One cadence analysis per job
);

-- Speaker analysis results (optional)
CREATE TABLE speaker_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(255) NOT NULL REFERENCES transcription_jobs(job_id),
    speaker_count INTEGER NOT NULL DEFAULT 0,
    overlaps_detected INTEGER NOT NULL DEFAULT 0,
    confidence_score DECIMAL(4,3),
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_job_speaker (job_id),
    UNIQUE(job_id)
);

-- Processing performance metrics
CREATE TABLE processing_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(255) NOT NULL REFERENCES transcription_jobs(job_id),
    
    -- Resource usage
    gpu_workers_used INTEGER,
    cpu_workers_used INTEGER, 
    peak_memory_mb INTEGER,
    chunks_processed INTEGER,
    chunks_failed INTEGER,
    
    -- Timing breakdown
    chunking_time_seconds INTEGER,
    transcription_time_seconds INTEGER,
    assembly_time_seconds INTEGER,
    total_processing_time_seconds INTEGER,
    
    -- Optimization metrics
    speed_multiplier_applied DECIMAL(3,2),
    original_duration_seconds DECIMAL(10,3),
    processed_duration_seconds DECIMAL(10,3),
    time_saved_seconds INTEGER GENERATED ALWAYS AS (
        original_duration_seconds - processed_duration_seconds
    ) STORED,
    
    cost_estimate_usd DECIMAL(8,2),
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_job_metrics (job_id),
    UNIQUE(job_id)
);
```

### 2. Views for Analysis

```sql
-- Comprehensive job status view
CREATE VIEW job_status_summary AS
SELECT 
    tj.job_id,
    tj.status,
    tj.created_at,
    tj.processing_time_seconds,
    tj.file_size_bytes,
    tj.duration_seconds,
    COUNT(tb.id) as total_buckets,
    COUNT(CASE WHEN tb.cadence_anomaly THEN 1 END) as anomalous_buckets,
    AVG(tb.confidence) as avg_confidence,
    ca.gap_mean,
    ca.cadence_summary,
    pm.cost_estimate_usd
FROM transcription_jobs tj
LEFT JOIN timing_buckets tb ON tj.job_id = tb.job_id
LEFT JOIN cadence_analysis ca ON tj.job_id = ca.job_id
LEFT JOIN processing_metrics pm ON tj.job_id = pm.job_id
GROUP BY tj.job_id, ca.gap_mean, ca.cadence_summary, pm.cost_estimate_usd;

-- Performance analytics view
CREATE VIEW processing_performance AS
SELECT 
    DATE_TRUNC('day', tj.created_at) as processing_date,
    COUNT(*) as jobs_processed,
    AVG(tj.processing_time_seconds) as avg_processing_time,
    AVG(pm.chunks_processed) as avg_chunks_per_job,
    AVG(pm.time_saved_seconds) as avg_time_saved,
    SUM(pm.cost_estimate_usd) as total_cost_usd,
    AVG(pm.speed_multiplier_applied) as avg_speed_multiplier
FROM transcription_jobs tj
JOIN processing_metrics pm ON tj.job_id = pm.job_id
WHERE tj.status = 'completed'
GROUP BY DATE_TRUNC('day', tj.created_at)
ORDER BY processing_date DESC;
```

### 3. Indexes for Performance

```sql
-- Additional performance indexes
CREATE INDEX idx_jobs_status_created ON transcription_jobs(status, created_at DESC);
CREATE INDEX idx_buckets_job_timestamp ON timing_buckets(job_id, start_timestamp);
CREATE INDEX idx_words_bucket_start ON word_timestamps(bucket_id, start_timestamp);

-- Composite indexes for common queries
CREATE INDEX idx_jobs_enhanced_analysis ON transcription_jobs(enhanced_analysis, status, created_at);
CREATE INDEX idx_buckets_anomaly_confidence ON timing_buckets(cadence_anomaly, confidence, job_id);

-- Full-text search for transcription content
CREATE INDEX idx_buckets_text_search ON timing_buckets USING gin(to_tsvector('english', text));
CREATE INDEX idx_words_text_search ON word_timestamps USING gin(to_tsvector('english', word));
```

## Configuration Schema

### 1. Application Configuration

```yaml
# config/production.yaml
processing:
  speed_multiplier: 1.75          # Default processing speed optimization
  chunk_size: 45                  # Seconds per chunk (optimal for GPU)
  overlap_duration: 3             # Seconds of overlap between chunks
  max_workers: 6                  # Maximum GPU workers
  enhanced_analysis: true         # Enable timing analysis by default
  
transcription:
  model_size: "large-v3"          # Default Whisper model
  compute_type: "float16"         # GPU precision
  beam_size: 5                    # Search beam size
  language: "auto"                # Auto-detect language
  
timing_analysis:
  bucket_size: 30                 # Seconds per timing bucket
  cadence_threshold: 2.0          # Standard deviations for anomaly detection
  confidence_threshold: 0.7       # Minimum confidence for analysis
  
gcp:
  project_id: "talkgpt-production"
  region: "us-central1"
  input_bucket: "talkgpt-production-audio-input"
  output_bucket: "talkgpt-production-transcription-output"
  models_bucket: "talkgpt-production-models-cache"
  
database:
  host: "${DATABASE_HOST}"
  port: 5432
  name: "talkgpt_production"
  user: "${DATABASE_USER}" 
  password: "${DATABASE_PASSWORD}"
  ssl_mode: "require"
  connection_pool_size: 20
  
monitoring:
  enabled: true
  metrics_port: 9090
  health_check_interval: 30
  log_level: "INFO"
```

This comprehensive schema documentation provides the complete structure for TalkGPT's production deployment, including all JSON schemas, content bucket definitions, and database schemas needed for the timing analysis system.