# Core Module - Agent Documentation

## Module Overview
- File preprocessing, smart chunking, transcription engine
- Integration points: used by CLI, MCP, analytics, and output layers

## API Reference
- `src/core/file_processor.py`
  - `class FileProcessor`
    - `scan_directory(directory, recursive=True, extensions=None) -> List[Path]`
    - `get_file_info(file_path) -> AudioFileInfo`
    - `process_file(input_path, output_dir, speed_multiplier=1.75, remove_silence=True, normalize=True, target_sample_rate=16000, target_channels=1) -> ProcessingResult`
- `src/core/chunker.py`
  - `class SmartChunker`
    - `chunk_audio(audio_path, output_dir=None, remove_silence=True) -> ChunkingResult`
    - `load_chunks_from_metadata(metadata_file) -> ChunkingResult`
- `src/core/transcriber.py`
  - `class WhisperTranscriber`
    - `transcribe_chunk(audio_chunk, ..., word_timestamps=False) -> TranscriptionResult`
    - `transcribe_file(audio_path, chunking_result=None, **opts) -> BatchTranscriptionResult`
    - `get_transcriber(**kwargs) -> WhisperTranscriber`
  - `enhanced_transcribe_with_analysis(audio_path, chunking_result, bucket_seconds=4.0, gap_tolerance=0.25, gap_threshold=1.5, enable_overlap_detection=True, **kwargs) -> Dict[str, Any]`

## Configuration
- Driven by `config/default.yaml` and `config/production.yaml`
- Processing: speed, chunking, silence detection
- Transcription: model, device, compute_type, language

## Usage Examples
- CLI transcribe invokes file processor → chunker → transcriber
- Enhanced path triggers 4s window analysis after transcription

## Implementation Details
- Overlap-aware merging of chunk segments
- Device/compute auto-routing via `ResourceDetector`
- Optional word timestamps for analysis

## Testing
- Core tests recommended: chunk boundaries, merging, confidence calc

## Troubleshooting
- If ffmpeg not found, install and add to PATH (Windows)
- If faster-whisper/torch missing, install CPU-only first for quick tests

