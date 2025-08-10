"""
TalkGPT Transcription Engine

Fast Whisper transcription with confidence scoring, batch processing,
and advanced optimization features.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
import tempfile

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
import warnings
# Silence specific deprecation warning originating from ctranslate2 importing pkg_resources
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API",
    category=UserWarning,
    module=r"ctranslate2.*",
)

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from ..utils.logger import get_logger, get_file_logger
    from ..core.chunker import AudioChunk, ChunkingResult
    from ..core.resource_detector import get_device_config
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from utils.logger import get_logger, get_file_logger
    from core.chunker import AudioChunk, ChunkingResult
    from core.resource_detector import get_device_config


@dataclass
class TranscriptionSegment:
    """Single transcription segment with metadata."""
    id: int
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    words: Optional[List[Dict[str, Any]]] = None
    language: Optional[str] = None
    temperature: Optional[float] = None


@dataclass
class TranscriptionResult:
    """Complete transcription result for a single chunk or file."""
    segments: List[TranscriptionSegment]
    language: str
    language_probability: float
    duration: float
    text: str
    avg_confidence: float
    processing_time: float
    model_info: Dict[str, Any]
    chunk_info: Optional[Dict[str, Any]] = None


@dataclass
class BatchTranscriptionResult:
    """Result from batch transcription of multiple chunks."""
    original_file: Path
    chunk_results: List[TranscriptionResult]
    merged_result: TranscriptionResult
    total_processing_time: float
    chunks_processed: int
    failed_chunks: int
    performance_metrics: Dict[str, Any]


class WhisperTranscriber:
    """
    Fast Whisper transcription engine.
    
    Handles single file and batch transcription with automatic device
    selection, confidence scoring, and performance optimization.
    """
    
    def __init__(self,
                 model_size: str = "large-v3",
                 device: str = "auto",
                 compute_type: str = "auto",
                 cpu_threads: Optional[int] = None,
                 num_workers: int = 1):
        """
        Initialize the Whisper transcriber.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large, large-v3)
            device: Device to use (auto, cpu, cuda, mps)
            compute_type: Compute precision (float16, int8, float32)
            cpu_threads: Number of CPU threads (None = auto)
            num_workers: Number of parallel workers for batch processing
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers
        
        self.logger = get_logger("talkgpt.transcriber")
        self.model: Optional[WhisperModel] = None
        self.model_info: Dict[str, Any] = {}
        
        # Check dependencies
        self._check_dependencies()
        
        # Load model
        self._load_model()
    
    def _check_dependencies(self):
        """Check for required dependencies."""
        if not FASTER_WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper is required but not installed")
        
        if not TORCH_AVAILABLE:
            self.logger.warning("PyTorch not available, some features may be limited")
        
        self.logger.info(f"Initializing Whisper transcriber: {self.model_size} on {self.device}")
    
    def _load_model(self):
        """Load the Whisper model."""
        try:
            # Get device configuration
            if self.device == "auto" or self.compute_type == "auto":
                device_config = get_device_config()
                actual_device = device_config['device'] if self.device == "auto" else self.device
                actual_compute_type = device_config.get('compute_type', self.compute_type) if self.compute_type == "auto" else self.compute_type
                # Extract cpu_threads but don't pass device_config directly to avoid parameter conflicts
                cpu_threads = device_config.get('cpu_threads', self.cpu_threads) if self.cpu_threads is None else self.cpu_threads
            else:
                actual_device = self.device
                actual_compute_type = self.compute_type
                cpu_threads = self.cpu_threads
            
            self.logger.info(f"Loading Whisper model: {self.model_size}")
            self.logger.info(f"Device: {actual_device}, Compute type: {actual_compute_type}")
            
            # Load model with compatible parameters
            model_kwargs = {
                'device': actual_device,
                'compute_type': actual_compute_type
            }
            
            # Add device_index for CUDA
            if actual_device == 'cuda':
                model_kwargs['device_index'] = 0
            
            # Note: Avoid intra_threads parameter as it causes conflicts in ctranslate2
            # The library will use optimal thread count automatically
            
            # Note: num_workers is not a WhisperModel parameter, it's for batch processing
            
            self.model = WhisperModel(self.model_size, **model_kwargs)
            
            # Store model info
            self.model_info = {
                'model_size': self.model_size,
                'device': actual_device,
                'compute_type': actual_compute_type,
                'cpu_threads': cpu_threads,
                'num_workers': self.num_workers
            }
            
            self.logger.info("Whisper model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def transcribe_chunk(self, 
                        audio_chunk: AudioChunk,
                        language: Optional[str] = None,
                        temperature: float = 0.0,
                        beam_size: int = 5,
                        best_of: int = 5,
                        patience: float = 1.0,
                        word_timestamps: bool = False) -> TranscriptionResult:
        """
        Transcribe a single audio chunk.
        
        Args:
            audio_chunk: AudioChunk to transcribe
            language: Language code (None for auto-detection)
            temperature: Sampling temperature
            beam_size: Beam search size
            best_of: Number of candidates
            patience: Beam search patience
            word_timestamps: Include word-level timestamps
            
        Returns:
            TranscriptionResult for the chunk
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")
        
        start_time = time.time()
        
        file_logger = get_file_logger(str(audio_chunk.original_start))
        file_logger.info(f"Transcribing chunk {audio_chunk.chunk_id}: {audio_chunk.duration:.1f}s")
        
        try:
            # Transcribe audio
            segments, info = self.model.transcribe(
                str(audio_chunk.file_path),
                language=language,
                temperature=temperature,
                beam_size=beam_size,
                best_of=best_of,
                patience=patience,
                word_timestamps=word_timestamps
            )
            
            # Convert segments to our format
            transcription_segments = []
            full_text_parts = []
            confidence_scores = []
            
            for i, segment in enumerate(segments):
                # Adjust timestamps to account for chunk position
                adjusted_start = segment.start + audio_chunk.original_start
                adjusted_end = segment.end + audio_chunk.original_start
                
                # Extract word-level timestamps if available
                words = None
                if word_timestamps and hasattr(segment, 'words') and segment.words:
                    words = []
                    for word in segment.words:
                        word_info = {
                            'word': word.word,
                            'start': word.start + audio_chunk.original_start,
                            'end': word.end + audio_chunk.original_start,
                            'probability': getattr(word, 'probability', 1.0)
                        }
                        words.append(word_info)
                
                transcription_segment = TranscriptionSegment(
                    id=i,
                    start=adjusted_start,
                    end=adjusted_end,
                    text=segment.text.strip(),
                    avg_logprob=segment.avg_logprob,
                    no_speech_prob=segment.no_speech_prob,
                    words=words,
                    language=info.language,
                    temperature=segment.temperature if hasattr(segment, 'temperature') else temperature
                )
                
                transcription_segments.append(transcription_segment)
                full_text_parts.append(segment.text.strip())
                confidence_scores.append(segment.avg_logprob)
            
            # Calculate overall confidence
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else -5.0
            
            # Create result
            processing_time = time.time() - start_time
            full_text = " ".join(full_text_parts).strip()
            
            result = TranscriptionResult(
                segments=transcription_segments,
                language=info.language,
                language_probability=info.language_probability,
                duration=audio_chunk.duration,
                text=full_text,
                avg_confidence=avg_confidence,
                processing_time=processing_time,
                model_info=self.model_info.copy(),
                chunk_info={
                    'chunk_id': audio_chunk.chunk_id,
                    'original_start': audio_chunk.original_start,
                    'original_end': audio_chunk.original_end,
                    'overlap_prev': audio_chunk.overlap_prev,
                    'overlap_next': audio_chunk.overlap_next
                }
            )
            
            file_logger.info(f"Chunk transcription completed: {len(transcription_segments)} segments, "
                           f"confidence: {avg_confidence:.2f}, time: {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            file_logger.error(f"Chunk transcription failed: {e}")
            raise
    
    def transcribe_file(self, 
                       audio_path: Union[str, Path],
                       chunking_result: Optional[ChunkingResult] = None,
                       **transcription_options) -> BatchTranscriptionResult:
        """
        Transcribe a complete audio file, optionally using pre-computed chunks.
        
        Args:
            audio_path: Path to audio file
            chunking_result: Pre-computed chunking result (None to chunk automatically)
            **transcription_options: Options passed to transcribe_chunk
            
        Returns:
            BatchTranscriptionResult with complete transcription
        """
        audio_path = Path(audio_path)
        start_time = time.time()
        
        file_logger = get_file_logger(str(audio_path))
        file_logger.info(f"Starting file transcription: {audio_path}")
        
        try:
            # Get chunks (either provided or create them)
            if chunking_result is None:
                from .chunker import get_smart_chunker
                chunker = get_smart_chunker()
                chunking_result = chunker.chunk_audio(audio_path)
            
            chunks = chunking_result.chunks
            file_logger.info(f"Transcribing {len(chunks)} chunks")
            
            # Transcribe chunks
            chunk_results = []
            failed_chunks = 0
            
            for chunk in chunks:
                try:
                    result = self.transcribe_chunk(chunk, **transcription_options)
                    chunk_results.append(result)
                except Exception as e:
                    file_logger.error(f"Failed to transcribe chunk {chunk.chunk_id}: {e}")
                    failed_chunks += 1
            
            # Merge results
            merged_result = self._merge_chunk_results(chunk_results, chunking_result)
            
            # Calculate performance metrics
            total_processing_time = time.time() - start_time
            performance_metrics = self._calculate_performance_metrics(
                chunk_results, chunking_result, total_processing_time
            )
            
            # Create batch result
            batch_result = BatchTranscriptionResult(
                original_file=audio_path,
                chunk_results=chunk_results,
                merged_result=merged_result,
                total_processing_time=total_processing_time,
                chunks_processed=len(chunk_results),
                failed_chunks=failed_chunks,
                performance_metrics=performance_metrics
            )
            
            file_logger.info(f"File transcription completed: {len(chunk_results)}/{len(chunks)} chunks successful")
            file_logger.info(f"Total time: {total_processing_time:.2f}s, "
                           f"Speed: {performance_metrics.get('processing_speed', 0):.1f}x real-time")
            
            return batch_result
            
        except Exception as e:
            file_logger.error(f"File transcription failed: {e}")
            raise
    
    def _merge_chunk_results(self, 
                           chunk_results: List[TranscriptionResult],
                           chunking_result: ChunkingResult) -> TranscriptionResult:
        """
        Merge chunk transcription results into a single result.
        
        Args:
            chunk_results: List of chunk transcription results
            chunking_result: Original chunking information
            
        Returns:
            Merged TranscriptionResult
        """
        if not chunk_results:
            raise ValueError("No chunk results to merge")
        
        # Collect all segments
        all_segments = []
        all_text_parts = []
        confidence_scores = []
        
        segment_id = 0
        
        for chunk_result in chunk_results:
            chunk_info = chunk_result.chunk_info
            overlap_start = chunk_info['original_start'] if chunk_info else 0
            overlap_end = chunk_info['original_end'] if chunk_info else float('inf')
            
            for segment in chunk_result.segments:
                # Only include segments that fall within the original chunk boundaries
                # (exclude overlap regions to avoid duplication)
                if overlap_start <= segment.start < overlap_end:
                    segment.id = segment_id
                    all_segments.append(segment)
                    all_text_parts.append(segment.text)
                    confidence_scores.append(segment.avg_logprob)
                    segment_id += 1
        
        # Calculate merged metrics
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else -5.0
        total_duration = chunking_result.total_duration
        merged_text = " ".join(all_text_parts).strip()
        
        # Use language from first chunk (should be consistent)
        primary_language = chunk_results[0].language
        language_prob = sum(r.language_probability for r in chunk_results) / len(chunk_results)
        
        # Sum processing times
        total_processing_time = sum(r.processing_time for r in chunk_results)
        
        merged_result = TranscriptionResult(
            segments=all_segments,
            language=primary_language,
            language_probability=language_prob,
            duration=total_duration,
            text=merged_text,
            avg_confidence=avg_confidence,
            processing_time=total_processing_time,
            model_info=self.model_info.copy(),
            chunk_info=None  # Not applicable for merged result
        )
        
        return merged_result
    
    def _calculate_performance_metrics(self,
                                     chunk_results: List[TranscriptionResult],
                                     chunking_result: ChunkingResult,
                                     total_time: float) -> Dict[str, Any]:
        """Calculate performance metrics for the transcription."""
        if not chunk_results:
            return {}
        
        total_audio_duration = chunking_result.total_duration
        total_processing_time = sum(r.processing_time for r in chunk_results)
        
        # Calculate processing speed (real-time factor)
        processing_speed = total_audio_duration / total_processing_time if total_processing_time > 0 else 0
        
        # Calculate efficiency metrics
        avg_chunk_time = total_processing_time / len(chunk_results)
        avg_chunk_duration = sum(r.duration for r in chunk_results) / len(chunk_results)
        
        # Confidence statistics
        confidences = [r.avg_confidence for r in chunk_results]
        
        metrics = {
            'total_audio_duration': total_audio_duration,
            'total_processing_time': total_processing_time,
            'wall_clock_time': total_time,
            'processing_speed': processing_speed,
            'chunks_processed': len(chunk_results),
            'avg_chunk_processing_time': avg_chunk_time,
            'avg_chunk_duration': avg_chunk_duration,
            'avg_confidence': sum(confidences) / len(confidences),
            'min_confidence': min(confidences),
            'max_confidence': max(confidences),
            'parallel_efficiency': total_processing_time / total_time if total_time > 0 else 0,
            'words_per_minute': len(chunk_results[0].text.split()) / (total_audio_duration / 60) if chunk_results else 0
        }
        
        return metrics
    
    def detect_language(self, audio_path: Union[str, Path]) -> Tuple[str, float]:
        """
        Detect the language of an audio file.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Tuple of (language_code, confidence)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")
        
        try:
            # Use only the first 30 seconds for language detection
            _, info = self.model.transcribe(
                str(audio_path),
                language=None,  # Auto-detect
                condition_on_previous_text=False,
                initial_prompt=None
            )
            
            return info.language, info.language_probability
            
        except Exception as e:
            self.logger.error(f"Language detection failed: {e}")
            return "en", 0.5  # Default fallback
    
    def calculate_confidence_threshold(self, 
                                     results: List[TranscriptionResult],
                                     percentile: float = 10) -> float:
        """
        Calculate confidence threshold based on result distribution.
        
        Args:
            results: List of transcription results
            percentile: Percentile for threshold (lower = more conservative)
            
        Returns:
            Confidence threshold value
        """
        if not results:
            return -1.0
        
        all_confidences = []
        for result in results:
            for segment in result.segments:
                all_confidences.append(segment.avg_logprob)
        
        if not all_confidences:
            return -1.0
        
        import numpy as np
        threshold = np.percentile(all_confidences, percentile)
        
        self.logger.info(f"Calculated confidence threshold: {threshold:.2f} "
                        f"(based on {percentile}th percentile of {len(all_confidences)} segments)")
        
        return threshold
    
    def save_transcription_result(self, 
                                 result: Union[TranscriptionResult, BatchTranscriptionResult],
                                 output_path: Union[str, Path],
                                 format: str = "json"):
        """
        Save transcription result to file.
        
        Args:
            result: Transcription result to save
            output_path: Output file path
            format: Output format (json, txt, srt)
        """
        output_path = Path(output_path)
        
        if format == "json":
            # Convert to JSON-serializable format
            if isinstance(result, BatchTranscriptionResult):
                data = asdict(result)
            else:
                data = asdict(result)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        elif format == "txt":
            # Simple text output
            if isinstance(result, BatchTranscriptionResult):
                text = result.merged_result.text
            else:
                text = result.text
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
        
        elif format == "srt":
            # SRT subtitle format
            if isinstance(result, BatchTranscriptionResult):
                segments = result.merged_result.segments
            else:
                segments = result.segments
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    start_time = self._format_srt_time(segment.start)
                    end_time = self._format_srt_time(segment.end)
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{segment.text}\n\n")
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self.logger.info(f"Transcription saved: {output_path}")
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT subtitle format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def cleanup(self):
        """Clean up resources."""
        if self.model is not None:
            # The model cleanup is handled by faster-whisper internally
            self.model = None
        
        self.logger.info("Transcriber cleanup completed")


# Global transcriber instance
_whisper_transcriber: Optional[WhisperTranscriber] = None


def get_transcriber(**kwargs) -> WhisperTranscriber:
    """Get the global transcriber instance."""
    global _whisper_transcriber
    if _whisper_transcriber is None:
        _whisper_transcriber = WhisperTranscriber(**kwargs)
    return _whisper_transcriber


def transcribe_file(audio_path: Union[str, Path], **kwargs) -> BatchTranscriptionResult:
    """Transcribe file using the global transcriber."""
    return get_transcriber().transcribe_file(audio_path, **kwargs)

def enhanced_transcribe_with_analysis(audio_path: Union[str, Path],
                                     chunking_result,
                                     bucket_seconds: float = 4.0,
                                     gap_tolerance: float = 0.25,
                                     gap_threshold: float = 1.5,
                                     enable_overlap_detection: bool = True,
                                     **transcribe_kwargs) -> Dict[str, Any]:
    """
    Perform enhanced transcription with comprehensive word-gap analysis.
    
    This function implements the new 4-second windowing approach with
    complete cadence analysis and speaker overlap detection.
    
    Args:
        audio_path: Path to audio file
        chunking_result: Result from audio chunking
        bucket_seconds: Target bucket duration (default: 4.0s)
        gap_tolerance: Bucket duration tolerance (default: 0.25s)
        gap_threshold: Cadence classification threshold in std devs (default: 1.5)
        enable_overlap_detection: Whether to detect speaker overlaps
        **transcribe_kwargs: Additional arguments for transcription
        
    Returns:
        Dictionary with enhanced transcription results and analysis
    """
    # Get logger
    from ..utils.logger import get_logger
    logger = get_logger("talkgpt.enhanced_transcriber")
    
    logger.info("Starting enhanced transcription with word-gap analysis")
    
    try:
        # Import our new analysis modules
        from ..core.utils import flatten_segments, validate_word_timing
        from ..post.segmenter import bucketize, validate_buckets
        from ..post.cadence import create_analysis_context
        from ..post.assembler import assemble_records, validate_records
        
        # Perform standard transcription with word timestamps
        # Sanitize kwargs to avoid passing unsupported keys to transcribe_chunk
        timing_repair = transcribe_kwargs.pop('timing_repair', True)
        transcribe_kwargs.pop('device', None)
        transcribe_kwargs.pop('compute_type', None)
        transcribe_kwargs['word_timestamps'] = True
        # Ensure we don't forward unexpected keys to chunk calls
        safe_options = {
            k: v for k, v in transcribe_kwargs.items()
            if k in {"language", "temperature", "beam_size", "best_of", "patience", "word_timestamps"}
        }
        transcriber = get_transcriber()
        transcription_result = transcriber.transcribe_file(
            audio_path, chunking_result, **safe_options
        )
        
        # Extract and flatten word-level data
        if hasattr(transcription_result, 'merged_result'):
            segments = transcription_result.merged_result.segments
        else:
            segments = transcription_result.segments
        
        logger.info(f"Flattening {len(segments)} segments to word-level data")
        words = flatten_segments(segments)
        words = validate_word_timing(words, timing_repair=timing_repair)
        
        logger.info(f"Processing {len(words)} words for gap analysis")
        
        # Create 4-second timing buckets
        buckets = bucketize(words, bucket_seconds, gap_tolerance)
        
        # Validate buckets
        bucket_validation = validate_buckets(buckets, bucket_seconds, gap_tolerance)
        logger.info(f"Created {len(buckets)} timing buckets (validation: {bucket_validation['valid']})")
        
        # Create global analysis context
        context = create_analysis_context(buckets, gap_threshold)
        
        # Assemble comprehensive records
        records = assemble_records(
            buckets, 
            context, 
            Path(audio_path) if enable_overlap_detection else None,
            enable_overlap_detection
        )
        
        # Validate final records
        record_validation = validate_records(records)
        logger.info(f"Assembled {len(records)} transcription records (validation: {record_validation['valid']})")
        
        # Prepare enhanced results
        enhanced_result = {
            'original_transcription': transcription_result,
            'enhanced_records': records,
            'analysis_context': context,
            'bucket_validation': bucket_validation,
            'record_validation': record_validation,
            'processing_metadata': {
                'bucket_seconds': bucket_seconds,
                'gap_tolerance': gap_tolerance,
                'gap_threshold': gap_threshold,
                'total_words': len(words),
                'total_buckets': len(buckets),
                'total_records': len(records),
                'overlap_detection_enabled': enable_overlap_detection
            }
        }
        
        logger.info("Enhanced transcription with analysis completed successfully")
        return enhanced_result
        
    except Exception as e:
        logger.error(f"Enhanced transcription failed: {e}")
        raise