"""
TalkGPT Post-Processing Module

Advanced post-processing capabilities including 4-second windowing,
word-gap analysis, cadence classification, and speaker overlap detection.
"""

from .segmenter import bucketize, TimingBucket, validate_buckets
from .cadence import gap_stats, create_analysis_context, classify_cadence, GapStatistics, AnalysisContext
from .overlap import detect_speaker_overlaps, batch_detect_overlaps, validate_overlap_detection
from .assembler import assemble_records, TranscriptionRecord, validate_records

__all__ = [
    # Segmentation
    'bucketize',
    'TimingBucket', 
    'validate_buckets',
    
    # Cadence analysis
    'gap_stats',
    'create_analysis_context',
    'classify_cadence',
    'GapStatistics',
    'AnalysisContext',
    
    # Overlap detection
    'detect_speaker_overlaps',
    'batch_detect_overlaps',
    'validate_overlap_detection',
    
    # Record assembly
    'assemble_records',
    'TranscriptionRecord',
    'validate_records'
]
