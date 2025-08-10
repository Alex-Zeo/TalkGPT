"""
TalkGPT Speaker Analysis Module

Advanced speaker diarization and overlap detection using state-of-the-art
pyannote.audio models for multi-speaker audio analysis.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
import tempfile

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from pyannote.audio import Pipeline
    from pyannote.audio.pipelines import SpeakerDiarization
    from pyannote.core import Annotation, Segment
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False

try:
    from ..utils.logger import get_logger, get_file_logger
    from ..core.transcriber import TranscriptionResult, BatchTranscriptionResult
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from utils.logger import get_logger, get_file_logger
    from core.transcriber import TranscriptionResult, BatchTranscriptionResult


@dataclass
class SpeakerSegment:
    """Speaker segment information."""
    speaker_id: str
    start_time: float
    end_time: float
    duration: float
    confidence: float = 1.0


@dataclass
class OverlapSegment:
    """Speaker overlap information."""
    start_time: float
    end_time: float
    duration: float
    speakers: List[str]
    overlap_type: str  # "partial", "complete"
    confidence: float = 1.0


@dataclass
class SpeakerStats:
    """Statistics for a single speaker."""
    speaker_id: str
    total_duration: float
    segment_count: int
    average_segment_duration: float
    speaking_percentage: float
    longest_segment: float
    shortest_segment: float


@dataclass
class DiarizationResult:
    """Complete speaker diarization result."""
    audio_file: Path
    total_duration: float
    speaker_segments: List[SpeakerSegment]
    overlap_segments: List[OverlapSegment]
    speaker_count: int
    speaker_stats: List[SpeakerStats]
    processing_time: float
    model_info: Dict[str, Any]
    confidence_threshold: float


@dataclass
class EnhancedTranscriptionResult:
    """Transcription result enhanced with speaker information."""
    original_result: Union[TranscriptionResult, BatchTranscriptionResult]
    diarization_result: DiarizationResult
    speaker_labeled_segments: List[Dict[str, Any]]
    overlap_flagged_segments: List[Dict[str, Any]]
    speaker_transcript_mapping: Dict[str, str]
    enhancement_time: float


class SpeakerAnalyzer:
    """
    Advanced speaker analysis system using pyannote.audio.
    
    Performs speaker diarization, overlap detection, and speaker-aware
    transcription enhancement for multi-speaker audio files.
    """
    
    def __init__(self,
                 model_name: str = "pyannote/speaker-diarization-3.1",
                 device: str = "auto",
                 auth_token: Optional[str] = None,
                 min_speakers: Optional[int] = None,
                 max_speakers: Optional[int] = None):
        """
        Initialize the speaker analyzer.
        
        Args:
            model_name: Pyannote model name for diarization
            device: Device to use (auto, cpu, cuda)
            auth_token: HuggingFace auth token (required for some models)
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers
        """
        self.model_name = model_name
        self.device = device
        self.auth_token = auth_token
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        
        self.logger = get_logger("talkgpt.speaker_analyzer")
        self.pipeline: Optional[Pipeline] = None
        self.model_info: Dict[str, Any] = {}
        
        # Check dependencies and load model
        self._check_dependencies()
        if PYANNOTE_AVAILABLE:
            self._load_model()
    
    def _check_dependencies(self):
        """Check for required dependencies."""
        if not PYANNOTE_AVAILABLE:
            self.logger.warning("pyannote.audio not available. Speaker analysis disabled.")
            return
        
        if not TORCH_AVAILABLE:
            self.logger.warning("PyTorch not available. Some features may be limited.")
        
        self.logger.info(f"Initializing speaker analyzer: {self.model_name}")
    
    def _load_model(self):
        """Load the pyannote diarization model."""
        if not PYANNOTE_AVAILABLE:
            return
        
        try:
            self.logger.info(f"Loading speaker diarization model: {self.model_name}")
            
            # Determine device
            if self.device == "auto":
                if TORCH_AVAILABLE and torch.cuda.is_available():
                    actual_device = "cuda"
                else:
                    actual_device = "cpu"
            else:
                actual_device = self.device
            
            # Load pipeline
            self.pipeline = Pipeline.from_pretrained(
                self.model_name,
                use_auth_token=self.auth_token
            )
            
            # Move to device
            if actual_device == "cuda" and TORCH_AVAILABLE:
                self.pipeline = self.pipeline.to(torch.device("cuda"))
            
            # Configure pipeline parameters
            if self.min_speakers is not None:
                self.pipeline.instantiate({"clustering": {"min_speakers": self.min_speakers}})
            if self.max_speakers is not None:
                self.pipeline.instantiate({"clustering": {"max_speakers": self.max_speakers}})
            
            self.model_info = {
                'model_name': self.model_name,
                'device': actual_device,
                'min_speakers': self.min_speakers,
                'max_speakers': self.max_speakers
            }
            
            self.logger.info(f"Speaker analyzer loaded successfully on {actual_device}")
            
        except Exception as e:
            self.logger.error(f"Failed to load speaker analyzer: {e}")
            self.logger.warning("Speaker analysis will be disabled")
            self.pipeline = None
    
    def perform_diarization(self, 
                          audio_path: Union[str, Path],
                          confidence_threshold: float = 0.5) -> DiarizationResult:
        """
        Perform speaker diarization on an audio file.
        
        Args:
            audio_path: Path to audio file
            confidence_threshold: Minimum confidence for speaker segments
            
        Returns:
            DiarizationResult with speaker information
        """
        if self.pipeline is None:
            raise RuntimeError("Speaker analyzer not available")
        
        audio_path = Path(audio_path)
        start_time = time.time()
        
        file_logger = get_file_logger(str(audio_path))
        file_logger.info(f"Starting speaker diarization: {audio_path}")
        
        try:
            # Perform diarization
            diarization = self.pipeline(str(audio_path))
            
            # Extract speaker segments
            speaker_segments = []
            for segment, _, speaker in diarization.itertracks(yield_label=True):
                speaker_segment = SpeakerSegment(
                    speaker_id=speaker,
                    start_time=segment.start,
                    end_time=segment.end,
                    duration=segment.duration,
                    confidence=1.0  # pyannote doesn't provide segment-level confidence
                )
                speaker_segments.append(speaker_segment)
            
            # Detect overlaps
            overlap_segments = self._detect_overlaps(diarization)
            
            # Calculate statistics
            total_duration = max(seg.end_time for seg in speaker_segments) if speaker_segments else 0.0
            speaker_count = len(set(seg.speaker_id for seg in speaker_segments))
            speaker_stats = self._calculate_speaker_stats(speaker_segments, total_duration)
            
            processing_time = time.time() - start_time
            
            result = DiarizationResult(
                audio_file=audio_path,
                total_duration=total_duration,
                speaker_segments=speaker_segments,
                overlap_segments=overlap_segments,
                speaker_count=speaker_count,
                speaker_stats=speaker_stats,
                processing_time=processing_time,
                model_info=self.model_info.copy(),
                confidence_threshold=confidence_threshold
            )
            
            file_logger.info(f"Diarization completed: {speaker_count} speakers, "
                           f"{len(speaker_segments)} segments, "
                           f"{len(overlap_segments)} overlaps in {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            file_logger.error(f"Diarization failed: {e}")
            raise
    
    def _detect_overlaps(self, diarization: Annotation) -> List[OverlapSegment]:
        """
        Detect overlapping speech segments.
        
        Args:
            diarization: Pyannote annotation object
            
        Returns:
            List of overlap segments
        """
        overlaps = []
        
        # Get all segments sorted by start time
        segments = [(segment, speaker) for segment, _, speaker in diarization.itertracks(yield_label=True)]
        segments.sort(key=lambda x: x[0].start)
        
        # Find overlaps
        for i, (seg1, spk1) in enumerate(segments):
            for j, (seg2, spk2) in enumerate(segments[i+1:], i+1):
                # Check if segments overlap
                if seg1.end > seg2.start and seg2.end > seg1.start and spk1 != spk2:
                    # Calculate overlap region
                    overlap_start = max(seg1.start, seg2.start)
                    overlap_end = min(seg1.end, seg2.end)
                    
                    if overlap_end > overlap_start:  # Valid overlap
                        overlap_duration = overlap_end - overlap_start
                        
                        # Determine overlap type
                        seg1_duration = seg1.duration
                        seg2_duration = seg2.duration
                        min_duration = min(seg1_duration, seg2_duration)
                        
                        if overlap_duration >= min_duration * 0.8:
                            overlap_type = "complete"
                        else:
                            overlap_type = "partial"
                        
                        overlap = OverlapSegment(
                            start_time=overlap_start,
                            end_time=overlap_end,
                            duration=overlap_duration,
                            speakers=[spk1, spk2],
                            overlap_type=overlap_type,
                            confidence=1.0
                        )
                        
                        overlaps.append(overlap)
        
        # Remove duplicate overlaps (same time range)
        unique_overlaps = []
        for overlap in overlaps:
            is_duplicate = False
            for existing in unique_overlaps:
                if (abs(overlap.start_time - existing.start_time) < 0.1 and
                    abs(overlap.end_time - existing.end_time) < 0.1):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_overlaps.append(overlap)
        
        return unique_overlaps
    
    def _calculate_speaker_stats(self, 
                                speaker_segments: List[SpeakerSegment],
                                total_duration: float) -> List[SpeakerStats]:
        """Calculate statistics for each speaker."""
        if not speaker_segments or total_duration == 0:
            return []
        
        # Group segments by speaker
        speaker_groups = {}
        for segment in speaker_segments:
            if segment.speaker_id not in speaker_groups:
                speaker_groups[segment.speaker_id] = []
            speaker_groups[segment.speaker_id].append(segment)
        
        # Calculate stats for each speaker
        stats = []
        for speaker_id, segments in speaker_groups.items():
            durations = [seg.duration for seg in segments]
            total_speaker_duration = sum(durations)
            
            speaker_stat = SpeakerStats(
                speaker_id=speaker_id,
                total_duration=total_speaker_duration,
                segment_count=len(segments),
                average_segment_duration=total_speaker_duration / len(segments),
                speaking_percentage=(total_speaker_duration / total_duration) * 100,
                longest_segment=max(durations),
                shortest_segment=min(durations)
            )
            
            stats.append(speaker_stat)
        
        # Sort by total speaking time (descending)
        stats.sort(key=lambda x: x.total_duration, reverse=True)
        
        return stats
    
    def enhance_transcription(self,
                            transcription_result: Union[TranscriptionResult, BatchTranscriptionResult],
                            audio_path: Union[str, Path],
                            diarization_result: Optional[DiarizationResult] = None) -> EnhancedTranscriptionResult:
        """
        Enhance transcription with speaker information.
        
        Args:
            transcription_result: Original transcription result
            audio_path: Path to original audio file
            diarization_result: Pre-computed diarization (None to compute)
            
        Returns:
            Enhanced transcription with speaker labels
        """
        start_time = time.time()
        audio_path = Path(audio_path)
        
        file_logger = get_file_logger(str(audio_path))
        file_logger.info("Enhancing transcription with speaker information")
        
        try:
            # Get diarization if not provided
            if diarization_result is None:
                diarization_result = self.perform_diarization(audio_path)
            
            # Extract segments from transcription result
            if isinstance(transcription_result, BatchTranscriptionResult):
                segments = transcription_result.merged_result.segments
            else:
                segments = transcription_result.segments
            
            # Assign speakers to transcription segments
            speaker_labeled_segments = []
            overlap_flagged_segments = []
            
            for segment in segments:
                # Find the most overlapping speaker segment
                best_speaker = self._find_speaker_for_segment(segment, diarization_result.speaker_segments)
                
                # Check for overlaps
                overlaps = self._find_overlaps_for_segment(segment, diarization_result.overlap_segments)
                
                # Create enhanced segment
                enhanced_segment = {
                    'id': segment.id,
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text,
                    'speaker': best_speaker,
                    'confidence': segment.avg_logprob,
                    'overlaps': overlaps,
                    'has_overlap': len(overlaps) > 0
                }
                
                speaker_labeled_segments.append(enhanced_segment)
                
                if overlaps:
                    overlap_flagged_segments.append(enhanced_segment)
            
            # Create speaker-specific transcripts
            speaker_transcript_mapping = self._create_speaker_transcripts(speaker_labeled_segments)
            
            enhancement_time = time.time() - start_time
            
            result = EnhancedTranscriptionResult(
                original_result=transcription_result,
                diarization_result=diarization_result,
                speaker_labeled_segments=speaker_labeled_segments,
                overlap_flagged_segments=overlap_flagged_segments,
                speaker_transcript_mapping=speaker_transcript_mapping,
                enhancement_time=enhancement_time
            )
            
            file_logger.info(f"Transcription enhancement completed: "
                           f"{len(speaker_labeled_segments)} segments labeled, "
                           f"{len(overlap_flagged_segments)} overlaps flagged in {enhancement_time:.2f}s")
            
            return result
            
        except Exception as e:
            file_logger.error(f"Transcription enhancement failed: {e}")
            raise
    
    def _find_speaker_for_segment(self, 
                                 transcription_segment,
                                 speaker_segments: List[SpeakerSegment]) -> Optional[str]:
        """Find the best matching speaker for a transcription segment."""
        best_speaker = None
        best_overlap = 0.0
        
        segment_start = transcription_segment.start
        segment_end = transcription_segment.end
        
        for speaker_seg in speaker_segments:
            # Calculate overlap
            overlap_start = max(segment_start, speaker_seg.start_time)
            overlap_end = min(segment_end, speaker_seg.end_time)
            
            if overlap_end > overlap_start:
                overlap_duration = overlap_end - overlap_start
                segment_duration = segment_end - segment_start
                
                # Calculate overlap ratio
                overlap_ratio = overlap_duration / segment_duration if segment_duration > 0 else 0
                
                if overlap_ratio > best_overlap:
                    best_overlap = overlap_ratio
                    best_speaker = speaker_seg.speaker_id
        
        return best_speaker
    
    def _find_overlaps_for_segment(self,
                                  transcription_segment,
                                  overlap_segments: List[OverlapSegment]) -> List[Dict[str, Any]]:
        """Find overlaps that affect a transcription segment."""
        segment_overlaps = []
        
        segment_start = transcription_segment.start
        segment_end = transcription_segment.end
        
        for overlap in overlap_segments:
            # Check if overlap affects this segment
            if (overlap.start_time < segment_end and overlap.end_time > segment_start):
                overlap_info = {
                    'start_time': overlap.start_time,
                    'end_time': overlap.end_time,
                    'duration': overlap.duration,
                    'speakers': overlap.speakers,
                    'type': overlap.overlap_type
                }
                segment_overlaps.append(overlap_info)
        
        return segment_overlaps
    
    def _create_speaker_transcripts(self, 
                                   labeled_segments: List[Dict[str, Any]]) -> Dict[str, str]:
        """Create separate transcripts for each speaker."""
        speaker_transcripts = {}
        
        # Group segments by speaker
        for segment in labeled_segments:
            speaker = segment.get('speaker', 'UNKNOWN')
            if speaker not in speaker_transcripts:
                speaker_transcripts[speaker] = []
            
            # Add overlap indicator if present
            text = segment['text']
            if segment['has_overlap']:
                text += " [OVERLAP]"
            
            speaker_transcripts[speaker].append(text)
        
        # Join segments for each speaker
        for speaker in speaker_transcripts:
            speaker_transcripts[speaker] = " ".join(speaker_transcripts[speaker])
        
        return speaker_transcripts
    
    def save_diarization_result(self,
                               result: DiarizationResult,
                               output_path: Union[str, Path],
                               format: str = "json"):
        """
        Save diarization result to file.
        
        Args:
            result: Diarization result to save
            output_path: Output file path
            format: Output format (json, rttm)
        """
        output_path = Path(output_path)
        
        if format == "json":
            # Convert to JSON-serializable format
            data = asdict(result)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        elif format == "rttm":
            # RTTM format for speaker diarization
            with open(output_path, 'w', encoding='utf-8') as f:
                for segment in result.speaker_segments:
                    # RTTM format: SPEAKER filename 1 start_time duration <NA> <NA> speaker_id <NA> <NA>
                    f.write(f"SPEAKER {result.audio_file.stem} 1 {segment.start_time:.3f} "
                           f"{segment.duration:.3f} <NA> <NA> {segment.speaker_id} <NA> <NA>\n")
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self.logger.info(f"Diarization result saved: {output_path}")
    
    def get_diarization_summary(self, result: DiarizationResult) -> Dict[str, Any]:
        """Get a summary of the diarization result."""
        return {
            'total_duration': result.total_duration,
            'speaker_count': result.speaker_count,
            'total_segments': len(result.speaker_segments),
            'total_overlaps': len(result.overlap_segments),
            'overlap_duration': sum(overlap.duration for overlap in result.overlap_segments),
            'overlap_percentage': (sum(overlap.duration for overlap in result.overlap_segments) / 
                                 result.total_duration * 100) if result.total_duration > 0 else 0,
            'speakers': [
                {
                    'id': stat.speaker_id,
                    'duration': stat.total_duration,
                    'percentage': stat.speaking_percentage,
                    'segments': stat.segment_count
                }
                for stat in result.speaker_stats
            ],
            'processing_time': result.processing_time
        }


# Global speaker analyzer instance
_speaker_analyzer: Optional[SpeakerAnalyzer] = None


def get_speaker_analyzer(**kwargs) -> SpeakerAnalyzer:
    """Get the global speaker analyzer instance."""
    global _speaker_analyzer
    if _speaker_analyzer is None:
        _speaker_analyzer = SpeakerAnalyzer(**kwargs)
    return _speaker_analyzer


def analyze_speakers(audio_path: Union[str, Path], **kwargs) -> DiarizationResult:
    """Perform speaker analysis using the global analyzer."""
    return get_speaker_analyzer().perform_diarization(audio_path, **kwargs)