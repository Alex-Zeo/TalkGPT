"""
TalkGPT Post-Processing: Segmentation

Implements 4-second windowing with tolerance for comprehensive word-gap analysis.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import logging
from ..core.utils import Word

logger = logging.getLogger(__name__)

@dataclass
class TimingBucket:
    """
    A time window containing words for analysis.
    
    Represents a ~4-second window of speech with word-level timing data
    for gap analysis and cadence detection.
    """
    start_time: float
    end_time: float
    words: List[Word]
    
    @property
    def duration(self) -> float:
        """Duration of the bucket in seconds."""
        return self.end_time - self.start_time
    
    @property
    def word_count(self) -> int:
        """Number of words in this bucket."""
        return len(self.words)
    
    @property
    def text(self) -> str:
        """Text content of the bucket."""
        return " ".join(word.word for word in self.words)
    
    def __str__(self) -> str:
        return f"TimingBucket({self.start_time:.1f}-{self.end_time:.1f}s, {self.word_count} words)"

def bucketize(words: List[Word], 
              bucket_seconds: float = 4.0,
              tolerance: float = 0.25) -> List[TimingBucket]:
    """
    Create 4-second content windows with ±0.25s tolerance.
    
    This function implements the core windowing strategy for word-gap analysis.
    Each bucket aims for the target duration but can extend within tolerance
    to include complete words.
    
    Args:
        words: List of Word objects in chronological order
        bucket_seconds: Target bucket duration in seconds (default: 4.0)
        tolerance: Acceptable deviation from target duration (default: 0.25)
        
    Returns:
        List of TimingBucket objects, each containing ~4s of speech
        
    Example:
        >>> words = create_test_words()  # 12 seconds of words
        >>> buckets = bucketize(words, bucket_seconds=4.0)
        >>> len(buckets)
        3
        >>> all(3.75 <= bucket.duration <= 4.25 for bucket in buckets[:-1])
        True
    """
    if not words:
        return []
    
    buckets = []
    current_bucket_words = []
    bucket_start = words[0].start
    target_end = bucket_start + bucket_seconds
    min_duration = bucket_seconds - tolerance
    max_duration = bucket_seconds + tolerance
    
    for word in words:
        current_bucket_words.append(word)
        current_duration = word.end - bucket_start
        
        # Check if we should close the current bucket
        should_close = False
        
        if current_duration >= min_duration:
            # We've reached minimum duration
            if current_duration >= max_duration:
                # We've exceeded maximum duration, must close
                should_close = True
            elif word.end >= target_end:
                # We've reached target duration, close at word boundary
                should_close = True
        
        if should_close and current_bucket_words:
            # Create bucket from accumulated words
            bucket_end = current_bucket_words[-1].end
            buckets.append(TimingBucket(
                start_time=bucket_start,
                end_time=bucket_end,
                words=current_bucket_words.copy()
            ))
            
            # Start new bucket
            current_bucket_words = []
            bucket_start = word.end  # Start next bucket at end of current word
            target_end = bucket_start + bucket_seconds
    
    # Handle remaining words in final bucket
    if current_bucket_words:
        bucket_end = current_bucket_words[-1].end
        buckets.append(TimingBucket(
            start_time=bucket_start,
            end_time=bucket_end,
            words=current_bucket_words
        ))
    
    logger.info(f"Created {len(buckets)} timing buckets from {len(words)} words")
    
    # Log bucket statistics
    for i, bucket in enumerate(buckets):
        logger.debug(f"Bucket {i}: {bucket.duration:.2f}s, {bucket.word_count} words")
    
    return buckets

def validate_buckets(buckets: List[TimingBucket],
                    target_duration: float = 4.0,
                    tolerance: float = 0.25) -> Dict[str, Any]:
    """
    Validate that buckets meet timing requirements.
    
    Args:
        buckets: List of TimingBucket objects to validate
        target_duration: Expected bucket duration
        tolerance: Acceptable deviation
        
    Returns:
        Dictionary with validation results and statistics
    """
    if not buckets:
        return {
            'valid': True,
            'bucket_count': 0,
            'duration_violations': [],
            'statistics': {}
        }
    
    min_duration = target_duration - tolerance
    max_duration = target_duration + tolerance
    duration_violations = []
    
    # Check all buckets except the last one (which may be shorter)
    for i, bucket in enumerate(buckets[:-1]):
        if bucket.duration < min_duration or bucket.duration > max_duration:
            duration_violations.append({
                'bucket_index': i,
                'duration': bucket.duration,
                'expected_range': (min_duration, max_duration)
            })
    
    # Calculate statistics
    durations = [bucket.duration for bucket in buckets]
    word_counts = [bucket.word_count for bucket in buckets]
    
    statistics = {
        'bucket_count': len(buckets),
        'total_duration': sum(durations),
        'average_duration': sum(durations) / len(durations) if durations else 0,
        'average_word_count': sum(word_counts) / len(word_counts) if word_counts else 0,
        'min_duration': min(durations) if durations else 0,
        'max_duration': max(durations) if durations else 0
    }
    
    return {
        'valid': len(duration_violations) == 0,
        'bucket_count': len(buckets),
        'duration_violations': duration_violations,
        'statistics': statistics
    }

def merge_short_buckets(buckets: List[TimingBucket],
                       min_duration: float = 2.0) -> List[TimingBucket]:
    """
    Merge buckets that are too short with adjacent buckets.
    
    This function handles edge cases where buckets end up being too short
    due to sparse speech or timing issues.
    
    Args:
        buckets: List of TimingBucket objects
        min_duration: Minimum acceptable bucket duration
        
    Returns:
        List of TimingBucket objects with short buckets merged
    """
    if len(buckets) <= 1:
        return buckets
    
    merged_buckets = []
    i = 0
    
    while i < len(buckets):
        current_bucket = buckets[i]
        
        if current_bucket.duration < min_duration and i < len(buckets) - 1:
            # Merge with next bucket
            next_bucket = buckets[i + 1]
            merged_words = current_bucket.words + next_bucket.words
            
            merged_bucket = TimingBucket(
                start_time=current_bucket.start_time,
                end_time=next_bucket.end_time,
                words=merged_words
            )
            
            merged_buckets.append(merged_bucket)
            i += 2  # Skip the next bucket as it's been merged
            
            logger.debug(f"Merged short bucket ({current_bucket.duration:.2f}s) with next bucket")
        else:
            merged_buckets.append(current_bucket)
            i += 1
    
    return merged_buckets
