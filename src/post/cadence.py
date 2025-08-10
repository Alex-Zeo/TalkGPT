"""
TalkGPT Post-Processing: Cadence Analysis

Implements word-gap statistics and cadence classification using population variance
and statistical thresholds for speech rhythm analysis.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import logging
import statistics
from ..core.utils import Word, calculate_word_gaps
from .segmenter import TimingBucket

logger = logging.getLogger(__name__)

@dataclass
class GapStatistics:
    """
    Statistical analysis of word gaps within a timing bucket.
    
    Contains comprehensive gap analysis including population variance
    and descriptive statistics for cadence classification.
    """
    gaps: List[float]
    mean: float
    variance: float  # Population variance (ddof=0)
    std_dev: float
    count: int
    min_gap: float
    max_gap: float
    
    def __str__(self) -> str:
        return f"GapStats(mean={self.mean:.4f}, var={self.variance:.6f}, n={self.count})"

@dataclass
class AnalysisContext:
    """
    Global analysis context containing file-level statistics.
    
    Stores population statistics used for cadence classification
    and comparative analysis across timing buckets.
    """
    global_mean: float
    global_std_dev: float
    global_variance: float
    total_gaps: int
    gap_threshold: float = 1.5  # Standard deviations for classification
    
    @property
    def slow_threshold(self) -> float:
        """Threshold for 'slow' cadence classification."""
        return self.global_mean + (self.gap_threshold * self.global_std_dev)
    
    @property
    def fast_threshold(self) -> float:
        """Threshold for 'fast' cadence classification."""
        return self.global_mean - (self.gap_threshold * self.global_std_dev)
    
    def __str__(self) -> str:
        return f"AnalysisContext(μ={self.global_mean:.4f}, σ={self.global_std_dev:.4f})"

def gap_stats(bucket: TimingBucket) -> GapStatistics:
    """
    Calculate comprehensive gap statistics for a timing bucket.
    
    Computes word gaps and their statistical properties using population
    variance (ddof=0) as specified in the requirements.
    
    Args:
        bucket: TimingBucket containing words for analysis
        
    Returns:
        GapStatistics object with comprehensive gap analysis
        
    Example:
        >>> words = [Word('a', 0, 0.5), Word('b', 0.6, 1.0), Word('c', 1.3, 1.8)]
        >>> bucket = TimingBucket(0, 1.8, words)
        >>> stats = gap_stats(bucket)
        >>> stats.count
        2
        >>> round(stats.mean, 3)
        0.2
    """
    if len(bucket.words) < 2:
        # Return empty statistics for buckets with insufficient words
        return GapStatistics(
            gaps=[],
            mean=0.0,
            variance=0.0,
            std_dev=0.0,
            count=0,
            min_gap=0.0,
            max_gap=0.0
        )
    
    # Calculate word gaps
    gaps = calculate_word_gaps(bucket.words)
    
    if not gaps:
        return GapStatistics(
            gaps=[],
            mean=0.0,
            variance=0.0,
            std_dev=0.0,
            count=0,
            min_gap=0.0,
            max_gap=0.0
        )
    
    # Calculate statistics using population variance (ddof=0)
    mean_gap = statistics.mean(gaps)
    
    # Population variance calculation
    variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
    std_dev = variance ** 0.5
    
    return GapStatistics(
        gaps=gaps.copy(),
        mean=mean_gap,
        variance=variance,
        std_dev=std_dev,
        count=len(gaps),
        min_gap=min(gaps),
        max_gap=max(gaps)
    )

def create_analysis_context(buckets: List[TimingBucket],
                          gap_threshold: float = 1.5) -> AnalysisContext:
    """
    Create global analysis context from all timing buckets.
    
    Computes file-level statistics (μ, σ) used for cadence classification
    across all words in the transcription.
    
    Args:
        buckets: List of TimingBucket objects
        gap_threshold: Standard deviations for cadence thresholds
        
    Returns:
        AnalysisContext with global statistics
    """
    all_gaps = []
    
    # Collect all gaps from all buckets
    for bucket in buckets:
        if len(bucket.words) >= 2:
            gaps = calculate_word_gaps(bucket.words)
            all_gaps.extend(gaps)
    
    if not all_gaps:
        logger.warning("No word gaps found in any bucket")
        return AnalysisContext(
            global_mean=0.0,
            global_std_dev=0.0,
            global_variance=0.0,
            total_gaps=0,
            gap_threshold=gap_threshold
        )
    
    # Calculate global statistics using population variance
    global_mean = statistics.mean(all_gaps)
    global_variance = sum((gap - global_mean) ** 2 for gap in all_gaps) / len(all_gaps)
    global_std_dev = global_variance ** 0.5
    
    # Always emit ASCII for console safety on Windows
    logger.info(f"Global gap analysis: mu={global_mean:.4f}, sigma={global_std_dev:.4f}, n={len(all_gaps)}")
    
    return AnalysisContext(
        global_mean=global_mean,
        global_std_dev=global_std_dev,
        global_variance=global_variance,
        total_gaps=len(all_gaps),
        gap_threshold=gap_threshold
    )

def classify_cadence(gap_stats: GapStatistics, 
                    context: AnalysisContext) -> str:
    """
    Classify cadence as 'slow', 'fast', or 'normal' using ±1.5σ rule.
    
    Uses the global analysis context to determine if a bucket's average
    gap duration indicates slow, normal, or fast speech cadence.
    
    Args:
        gap_stats: GapStatistics for the bucket to classify
        context: AnalysisContext with global thresholds
        
    Returns:
        Cadence classification: 'slow', 'fast', or 'normal'
        
    Example:
        >>> context = AnalysisContext(0.1, 0.05, 0.0025, 100)
        >>> stats = GapStatistics([0.2], 0.2, 0.0, 0.0, 1, 0.2, 0.2)
        >>> classify_cadence(stats, context)
        'slow'
    """
    if gap_stats.count == 0:
        return 'normal'  # Default for buckets without gaps
    
    mean_gap = gap_stats.mean
    
    if mean_gap > context.slow_threshold:
        return 'slow'
    elif mean_gap < context.fast_threshold:
        return 'fast'
    else:
        return 'normal'

def analyze_bucket_cadence(bucket: TimingBucket,
                          context: AnalysisContext) -> Tuple[GapStatistics, str]:
    """
    Perform complete cadence analysis on a timing bucket.
    
    Combines gap statistics calculation with cadence classification
    to provide comprehensive rhythm analysis.
    
    Args:
        bucket: TimingBucket to analyze
        context: AnalysisContext with global statistics
        
    Returns:
        Tuple of (GapStatistics, cadence_classification)
    """
    stats = gap_stats(bucket)
    cadence = classify_cadence(stats, context)
    
    logger.debug(f"Bucket cadence analysis: {stats} → {cadence}")
    
    return stats, cadence

def format_gaps_for_output(gaps: List[float], 
                          max_gaps: Optional[int] = None,
                          precision: int = 4) -> str:
    """
    Format gap list for output with specified precision.
    
    According to the requirements, we should output ALL gaps (no truncation)
    unless a specific limit is configured.
    
    Args:
        gaps: List of gap durations
        max_gaps: Maximum number of gaps to include (None = unlimited)
        precision: Decimal precision for gap values
        
    Returns:
        Comma-separated string of gap values
    """
    if not gaps:
        return ""
    
    # Apply limit if specified
    output_gaps = gaps[:max_gaps] if max_gaps else gaps
    
    # Format with specified precision
    formatted_gaps = [f"{gap:.{precision}f}" for gap in output_gaps]
    
    return ", ".join(formatted_gaps)

def validate_gap_analysis(buckets: List[TimingBucket],
                         context: AnalysisContext) -> Dict[str, Any]:
    """
    Validate gap analysis results for quality assurance.
    
    Args:
        buckets: List of analyzed TimingBucket objects
        context: AnalysisContext with global statistics
        
    Returns:
        Dictionary with validation results and quality metrics
    """
    total_words = sum(len(bucket.words) for bucket in buckets)
    total_gaps = sum(max(0, len(bucket.words) - 1) for bucket in buckets)
    buckets_with_gaps = sum(1 for bucket in buckets if len(bucket.words) >= 2)
    
    # Analyze cadence distribution
    cadence_counts = {'slow': 0, 'normal': 0, 'fast': 0}
    
    for bucket in buckets:
        stats = gap_stats(bucket)
        cadence = classify_cadence(stats, context)
        cadence_counts[cadence] += 1
    
    return {
        'total_buckets': len(buckets),
        'total_words': total_words,
        'total_gaps': total_gaps,
        'buckets_with_gaps': buckets_with_gaps,
        'cadence_distribution': cadence_counts,
        'global_statistics': {
            'mean': context.global_mean,
            'std_dev': context.global_std_dev,
            'variance': context.global_variance
        },
        'quality_score': buckets_with_gaps / len(buckets) if buckets else 0.0
    }
