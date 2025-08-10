"""
TalkGPT Post-Processing: Overlap Detection

Safe wrapper for pyannote.audio speaker overlap detection with graceful fallbacks.
"""

from typing import Dict, Any, Optional, List
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def detect_speaker_overlaps(audio_path: Path,
                          bucket_start: float,
                          bucket_end: float) -> str:
    """
    Detect speaker overlaps in audio segment using pyannote.audio.
    
    This function provides a safe wrapper around pyannote.audio speaker
    diarization to detect overlapping speech within timing buckets.
    
    Args:
        audio_path: Path to the audio file
        bucket_start: Start time of the bucket in seconds
        bucket_end: End time of the bucket in seconds
        
    Returns:
        Overlap status: 'overlap', 'single', or 'unknown check pyannote'
        
    Example:
        >>> status = detect_speaker_overlaps(Path('audio.wav'), 0.0, 4.0)
        >>> status in ['overlap', 'single', 'unknown check pyannote']
        True
    """
    try:
        # Try to import pyannote.audio
        from pyannote.audio import Pipeline
        
        # Check if we have a cached pipeline
        pipeline = _get_or_create_pipeline()
        
        if pipeline is None:
            return 'unknown check pyannote'
        
        # Perform diarization on the audio segment
        diarization = pipeline(str(audio_path))
        
        # Check for overlaps in the specified time range
        has_overlap = _check_overlap_in_range(diarization, bucket_start, bucket_end)
        
        return 'overlap' if has_overlap else 'single'
        
    except ImportError:
        logger.debug("pyannote.audio not available for overlap detection")
        return 'unknown check pyannote'
    except Exception as e:
        logger.warning(f"Speaker overlap detection failed: {e}")
        return 'unknown check pyannote'

def _get_or_create_pipeline() -> Optional[Any]:
    """
    Get or create pyannote.audio pipeline with caching.
    
    Returns:
        Pipeline instance or None if unavailable
    """
    # Global cache for pipeline to avoid reloading
    if not hasattr(_get_or_create_pipeline, '_cached_pipeline'):
        try:
            from pyannote.audio import Pipeline
            
            # Try to load speaker diarization pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=None  # May require HuggingFace token for some models
            )
            
            _get_or_create_pipeline._cached_pipeline = pipeline
            logger.info("Speaker diarization pipeline loaded successfully")
            
        except Exception as e:
            logger.warning(f"Failed to load speaker diarization pipeline: {e}")
            _get_or_create_pipeline._cached_pipeline = None
    
    return getattr(_get_or_create_pipeline, '_cached_pipeline', None)

def _check_overlap_in_range(diarization: Any,
                           start_time: float,
                           end_time: float) -> bool:
    """
    Check if there are speaker overlaps within a time range.
    
    Args:
        diarization: pyannote diarization result
        start_time: Start of time range to check
        end_time: End of time range to check
        
    Returns:
        True if overlaps detected, False otherwise
    """
    try:
        # Get timeline of overlapping speech
        overlaps = diarization.get_overlap()
        
        # Check if any overlap intersects with our time range
        for overlap_segment in overlaps:
            overlap_start = overlap_segment.start
            overlap_end = overlap_segment.end
            
            # Check for intersection with our bucket
            if (overlap_start < end_time and overlap_end > start_time):
                return True
        
        return False
        
    except Exception as e:
        logger.warning(f"Error checking overlaps in range: {e}")
        return False

def batch_detect_overlaps(audio_path: Path,
                         buckets: List[Dict[str, Any]]) -> Dict[int, str]:
    """
    Detect overlaps for multiple timing buckets efficiently.
    
    Performs batch overlap detection to minimize repeated pipeline
    initialization and audio processing.
    
    Args:
        audio_path: Path to the audio file
        buckets: List of bucket dictionaries with 'start' and 'end' times
        
    Returns:
        Dictionary mapping bucket index to overlap status
        
    Example:
        >>> buckets = [{'start': 0.0, 'end': 4.0}, {'start': 4.0, 'end': 8.0}]
        >>> results = batch_detect_overlaps(Path('audio.wav'), buckets)
        >>> len(results) == len(buckets)
        True
    """
    results = {}
    
    try:
        # Try to get the pipeline once for all buckets
        pipeline = _get_or_create_pipeline()
        
        if pipeline is None:
            # Return 'unknown' for all buckets
            return {i: 'unknown check pyannote' for i in range(len(buckets))}
        
        # Perform diarization once for the entire file
        diarization = pipeline(str(audio_path))
        
        # Check each bucket
        for i, bucket in enumerate(buckets):
            start_time = bucket.get('start', 0.0)
            end_time = bucket.get('end', 0.0)
            
            has_overlap = _check_overlap_in_range(diarization, start_time, end_time)
            results[i] = 'overlap' if has_overlap else 'single'
        
        logger.info(f"Batch overlap detection completed for {len(buckets)} buckets")
        
    except Exception as e:
        logger.warning(f"Batch overlap detection failed: {e}")
        # Return 'unknown' for all buckets
        results = {i: 'unknown check pyannote' for i in range(len(buckets))}
    
    return results

def validate_overlap_detection() -> Dict[str, Any]:
    """
    Validate overlap detection capability and return system status.
    
    Returns:
        Dictionary with validation results and capability information
    """
    try:
        from pyannote.audio import Pipeline
        
        # Try to create a pipeline to test availability
        pipeline = _get_or_create_pipeline()
        
        if pipeline is not None:
            return {
                'available': True,
                'status': 'ready',
                'backend': 'pyannote.audio',
                'message': 'Speaker overlap detection is available'
            }
        else:
            return {
                'available': False,
                'status': 'pipeline_failed',
                'backend': 'pyannote.audio',
                'message': 'pyannote.audio pipeline could not be loaded'
            }
            
    except ImportError:
        return {
            'available': False,
            'status': 'missing_dependency',
            'backend': None,
            'message': 'pyannote.audio not installed - run: pip install pyannote.audio'
        }
    except Exception as e:
        return {
            'available': False,
            'status': 'error',
            'backend': 'pyannote.audio',
            'message': f'Overlap detection error: {e}'
        }

def get_overlap_status_explanation() -> Dict[str, str]:
    """
    Get explanations for overlap status values.
    
    Returns:
        Dictionary mapping status values to human-readable explanations
    """
    return {
        'overlap': 'Multiple speakers detected simultaneously',
        'single': 'Single speaker detected',
        'unknown check pyannote': 'Speaker overlap detection unavailable - install pyannote.audio'
    }
