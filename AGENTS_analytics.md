# Analytics Module - Agent Documentation

## Module Overview
- Timing analysis (4-second windows), cadence stats, uncertainty detection, speaker diarization

## API Reference
- `src/analytics/timing_analyzer.py`
  - `TimingAnalyzer.analyze_timing(transcription_result, speaker_timeline=None) -> (buckets, cadence)`
- `src/post/segmenter.py` / `src/post/cadence.py` / `src/post/assembler.py`
  - Bucketing, gap stats, records assembly
- `src/analytics/uncertainty_detector.py`
  - `UncertaintyDetector.analyze_uncertainty(transcription_result, audio_path=None) -> UncertaintyAnalysis`
- `src/analytics/speaker_analyzer.py`
  - `SpeakerAnalyzer.perform_diarization(audio_path) -> DiarizationResult`

## Configuration
- `config/default.yaml` → `analytics` section: enable flags, thresholds, timing settings

## Usage Examples
- CLI enhanced analysis: `--enhanced-analysis` to produce enhanced outputs
- CLI `analyze quality` and `analyze speakers` commands

## Implementation Details
- Population variance (ddof=0) for gap analysis
- Fallbacks when pyannote is unavailable (Windows/dev env)

## Testing
- Unit tests for gap stats, classification, record validation

## Troubleshooting
- Ensure word timestamps are enabled for timing analysis
- pyannote may require HF token on non-Windows platforms

