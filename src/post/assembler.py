"""
TalkGPT Post-Processing: Record Assembler

Assembles comprehensive transcription records with all analysis data including
text, gap statistics, cadence classification, and overlap detection.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path

from ..core.utils import Word, extract_text_from_words
from .segmenter import TimingBucket
from .cadence import GapStatistics, AnalysisContext, analyze_bucket_cadence, format_gaps_for_output
from .overlap import detect_speaker_overlaps, batch_detect_overlaps

logger = logging.getLogger(__name__)

@dataclass
class TranscriptionRecord:
    """
    Complete transcription record for a timing bucket.
    
    Contains all analysis results including text, timing, gaps, cadence,
    and speaker overlap information for comprehensive output generation.
    """
    # Basic information
    bucket_index: int
    start_time: float
    end_time: float
    duration: float
    
    # Text content
    text: str
    word_count: int
    
    # Word gap analysis
    word_gap_count: int
    word_gaps: List[float]
    word_gap_mean: float
    word_gap_var: float
    
    # Cadence classification
    cadence: str  # 'slow', 'fast', 'normal'
    
    # Speaker analysis
    speaker_overlap: str  # 'overlap', 'single', 'unknown check pyannote'
    
    # Quality metrics
    confidence_score: float
    
    # Raw data (for advanced processing)
    words: List[Word]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for serialization."""
        record_dict = asdict(self)
        # Convert Word objects to dictionaries
        record_dict['words'] = [
            {
                'word': w.word,
                'start': w.start,
                'end': w.end,
                'probability': w.probability
            }
            for w in self.words
        ]
        return record_dict
    
    def format_time_range(self) -> str:
        """Format time range as MM:SS–MM:SS."""
        def format_time(seconds: float) -> str:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        
        return f"{format_time(self.start_time)}–{format_time(self.end_time)}"
    
    def format_gaps_string(self, precision: int = 4, max_gaps: Optional[int] = None) -> str:
        """Format word gaps as comma-separated string."""
        return format_gaps_for_output(self.word_gaps, max_gaps, precision)

def assemble_records(buckets: List[TimingBucket],
                    context: AnalysisContext,
                    audio_path: Optional[Path] = None,
                    enable_overlap_detection: bool = True) -> List[TranscriptionRecord]:
    """
    Assemble complete transcription records from timing buckets.
    
    Creates comprehensive records with all analysis data for each timing bucket,
    including gap statistics, cadence classification, and optional overlap detection.
    
    Args:
        buckets: List of TimingBucket objects to process
        context: AnalysisContext with global statistics
        audio_path: Path to audio file for overlap detection (optional)
        enable_overlap_detection: Whether to perform overlap detection
        
    Returns:
        List of TranscriptionRecord objects with complete analysis
        
    Example:
        >>> buckets = create_test_buckets()
        >>> context = create_test_context()
        >>> records = assemble_records(buckets, context)
        >>> len(records) == len(buckets)
        True
        >>> all(hasattr(r, 'cadence') for r in records)
        True
    """
    if not buckets:
        return []
    
    records = []
    
    # Batch overlap detection if enabled and audio path provided
    overlap_results = {}
    if enable_overlap_detection and audio_path and audio_path.exists():
        try:
            bucket_data = [
                {'start': bucket.start_time, 'end': bucket.end_time}
                for bucket in buckets
            ]
            overlap_results = batch_detect_overlaps(audio_path, bucket_data)
            logger.info(f"Completed batch overlap detection for {len(buckets)} buckets")
        except Exception as e:
            logger.warning(f"Batch overlap detection failed: {e}")
    
    # Process each bucket
    for i, bucket in enumerate(buckets):
        try:
            # Analyze cadence
            gap_stats, cadence = analyze_bucket_cadence(bucket, context)
            
            # Get overlap status
            if i in overlap_results:
                speaker_overlap = overlap_results[i]
            elif enable_overlap_detection and audio_path and audio_path.exists():
                # Fallback to individual detection
                speaker_overlap = detect_speaker_overlaps(audio_path, bucket.start_time, bucket.end_time)
            else:
                speaker_overlap = 'unknown check pyannote'
            
            # Calculate average confidence
            confidence_scores = [word.probability for word in bucket.words if word.probability > 0]
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            # Create comprehensive record
            record = TranscriptionRecord(
                bucket_index=i,
                start_time=bucket.start_time,
                end_time=bucket.end_time,
                duration=bucket.duration,
                text=extract_text_from_words(bucket.words),
                word_count=len(bucket.words),
                word_gap_count=gap_stats.count,
                word_gaps=gap_stats.gaps,
                word_gap_mean=gap_stats.mean,
                word_gap_var=gap_stats.variance,
                cadence=cadence,
                speaker_overlap=speaker_overlap,
                confidence_score=avg_confidence,
                words=bucket.words.copy()
            )
            
            records.append(record)
            
            logger.debug(f"Assembled record {i}: {record.duration:.1f}s, {record.word_count} words, cadence={cadence}")
            
        except Exception as e:
            logger.error(f"Failed to assemble record for bucket {i}: {e}")
            # Create minimal record as fallback
            fallback_record = TranscriptionRecord(
                bucket_index=i,
                start_time=bucket.start_time,
                end_time=bucket.end_time,
                duration=bucket.duration,
                text=extract_text_from_words(bucket.words),
                word_count=len(bucket.words),
                word_gap_count=0,
                word_gaps=[],
                word_gap_mean=0.0,
                word_gap_var=0.0,
                cadence='normal',
                speaker_overlap='unknown check pyannote',
                confidence_score=0.0,
                words=bucket.words.copy()
            )
            records.append(fallback_record)
    
    logger.info(f"Assembled {len(records)} transcription records")
    return records

def validate_records(records: List[TranscriptionRecord]) -> Dict[str, Any]:
    """
    Validate assembled transcription records for quality assurance.
    
    Args:
        records: List of TranscriptionRecord objects to validate
        
    Returns:
        Dictionary with validation results and quality metrics
    """
    if not records:
        return {
            'valid': True,
            'record_count': 0,
            'validation_errors': [],
            'quality_metrics': {}
        }
    
    validation_errors = []
    
    # Check record consistency
    for i, record in enumerate(records):
        # Validate timing
        if record.start_time >= record.end_time:
            validation_errors.append(f"Record {i}: Invalid time range")
        
        # Validate word count consistency
        if record.word_count != len(record.words):
            validation_errors.append(f"Record {i}: Word count mismatch")
        
        # Validate gap count consistency
        expected_gaps = max(0, record.word_count - 1)
        if record.word_gap_count != len(record.word_gaps):
            validation_errors.append(f"Record {i}: Gap count mismatch")
        
        # Validate cadence classification
        if record.cadence not in ['slow', 'fast', 'normal']:
            validation_errors.append(f"Record {i}: Invalid cadence classification")
        
        # Validate overlap status
        if record.speaker_overlap not in ['overlap', 'single', 'unknown check pyannote']:
            validation_errors.append(f"Record {i}: Invalid speaker overlap status")
    
    # Calculate quality metrics
    total_duration = sum(record.duration for record in records)
    total_words = sum(record.word_count for record in records)
    total_gaps = sum(record.word_gap_count for record in records)
    
    cadence_distribution = {'slow': 0, 'normal': 0, 'fast': 0}
    overlap_distribution = {'overlap': 0, 'single': 0, 'unknown check pyannote': 0}
    
    for record in records:
        cadence_distribution[record.cadence] += 1
        overlap_distribution[record.speaker_overlap] += 1
    
    avg_confidence = sum(record.confidence_score for record in records) / len(records)
    
    quality_metrics = {
        'total_records': len(records),
        'total_duration': total_duration,
        'total_words': total_words,
        'total_gaps': total_gaps,
        'average_confidence': avg_confidence,
        'cadence_distribution': cadence_distribution,
        'overlap_distribution': overlap_distribution,
        'words_per_second': total_words / total_duration if total_duration > 0 else 0,
        'gaps_per_record': total_gaps / len(records)
    }
    
    return {
        'valid': len(validation_errors) == 0,
        'record_count': len(records),
        'validation_errors': validation_errors,
        'quality_metrics': quality_metrics
    }

def export_records_summary(records: List[TranscriptionRecord]) -> Dict[str, Any]:
    """
    Export summary statistics from transcription records.
    
    Args:
        records: List of TranscriptionRecord objects
        
    Returns:
        Dictionary with summary statistics and analysis results
    """
    if not records:
        return {'summary': 'No records to analyze'}
    
    # Aggregate statistics
    total_duration = sum(r.duration for r in records)
    total_words = sum(r.word_count for r in records)
    total_gaps = sum(r.word_gap_count for r in records)
    
    # Cadence analysis
    cadence_counts = {'slow': 0, 'normal': 0, 'fast': 0}
    for record in records:
        cadence_counts[record.cadence] += 1
    
    # Overlap analysis
    overlap_counts = {'overlap': 0, 'single': 0, 'unknown check pyannote': 0}
    for record in records:
        overlap_counts[record.speaker_overlap] += 1
    
    # Quality metrics
    confidence_scores = [r.confidence_score for r in records if r.confidence_score > 0]
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
    
    return {
        'summary': {
            'record_count': len(records),
            'total_duration': round(total_duration, 2),
            'total_words': total_words,
            'total_gaps': total_gaps,
            'average_confidence': round(avg_confidence, 3)
        },
        'cadence_analysis': {
            'distribution': cadence_counts,
            'percentages': {
                k: round(v / len(records) * 100, 1) 
                for k, v in cadence_counts.items()
            }
        },
        'speaker_analysis': {
            'distribution': overlap_counts,
            'overlap_detected': overlap_counts['overlap'] > 0,
            'detection_available': overlap_counts['unknown check pyannote'] == 0
        },
        'performance': {
            'words_per_second': round(total_words / total_duration, 2) if total_duration > 0 else 0,
            'average_bucket_duration': round(total_duration / len(records), 2),
            'average_words_per_bucket': round(total_words / len(records), 1)
        }
    }
