#!/usr/bin/env python3
"""
Timing Analysis Module for TalkGPT

Provides advanced word-level timing analysis including:
- Word bucketization (4-second segments)
- Gap statistics and cadence analysis
- Anomaly detection for speech patterns
- Detailed timing metadata for transcription enhancement
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from pathlib import Path

# Import project modules
from utils.logger import get_logger


class WordTiming(NamedTuple):
    """Individual word timing information."""
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TimingBucket:
    """A time-based bucket of words with analysis metrics."""
    bucket_id: int
    start_ts: float
    end_ts: float
    words: List[WordTiming]
    text: str
    
    # Gap statistics
    word_gap_count: int
    word_gaps: List[float]
    word_gap_mean: float
    word_gap_var: float
    
    # Quality metrics
    confidence: float
    speaker_overlap: Optional[bool]
    cadence_anomaly: bool
    cadence_severity: str  # 'normal', 'mild', 'moderate', 'severe'
    
    # Additional metrics
    words_per_second: float
    total_speech_time: float
    total_silence_time: float


@dataclass
class CadenceAnalysis:
    """Global cadence analysis results."""
    global_gap_mean: float
    global_gap_std: float
    total_words: int
    total_gaps: int
    anomaly_threshold: float
    anomalous_buckets: int
    
    # Distribution statistics
    gap_percentiles: Dict[str, float]  # 25th, 50th, 75th, 90th, 95th
    cadence_summary: str


class TimingAnalyzer:
    """Advanced timing analysis for transcription results."""
    
    def __init__(self, 
                 bucket_seconds: float = 4.0,
                 bucket_tolerance: float = 0.25,
                 gap_threshold: float = 1.5,
                 gap_list_max: int = 20,
                 variance_threshold: float = 1.5):
        """
        Initialize timing analyzer.
        
        Args:
            bucket_seconds: Target bucket duration in seconds
            bucket_tolerance: Tolerance for bucket length (±seconds)
            gap_threshold: Threshold multiplier for gap anomaly detection
            gap_list_max: Maximum gaps to store per bucket for readability
            variance_threshold: Threshold multiplier for variance anomaly detection
        """
        self.bucket_seconds = bucket_seconds
        self.bucket_tolerance = bucket_tolerance
        self.gap_threshold = gap_threshold
        self.gap_list_max = gap_list_max
        self.variance_threshold = variance_threshold
        
        self.logger = get_logger(__name__)
        self.logger.info(f"Timing analyzer initialized: {bucket_seconds}s buckets, "
                        f"±{bucket_tolerance}s tolerance, {gap_threshold}x gap threshold")
    
    def analyze_timing(self, 
                      transcription_result,
                      speaker_timeline: Optional[Any] = None) -> Tuple[List[TimingBucket], CadenceAnalysis]:
        """
        Perform comprehensive timing analysis on transcription results.
        
        Args:
            transcription_result: Transcription result with word-level timestamps
            speaker_timeline: Optional speaker overlap timeline from pyannote
            
        Returns:
            Tuple of (timing buckets, global cadence analysis)
        """
        self.logger.info("Starting comprehensive timing analysis")
        
        # Extract word-level timings
        words = self._extract_word_timings(transcription_result)
        self.logger.info(f"Extracted {len(words)} words with timing data")
        
        # Create time-based buckets
        buckets = self._bucketize_words(words)
        self.logger.info(f"Created {len(buckets)} timing buckets")
        
        # Calculate gap statistics for all buckets
        all_gaps = []
        for bucket in buckets:
            bucket_gaps = self._calculate_gap_statistics(bucket)
            all_gaps.extend(bucket_gaps)
        
        # Perform global cadence analysis
        cadence_analysis = self._analyze_global_cadence(all_gaps, buckets)
        self.logger.info(f"Global cadence analysis: {cadence_analysis.anomalous_buckets}/{len(buckets)} "
                        f"buckets flagged as anomalous")
        
        # Flag cadence anomalies in buckets
        self._flag_cadence_anomalies(buckets, cadence_analysis)
        
        # Add speaker overlap information if available
        if speaker_timeline:
            self._add_speaker_overlap_info(buckets, speaker_timeline)
        else:
            # Mark as unknown if speaker analysis unavailable
            for bucket in buckets:
                bucket.speaker_overlap = None
        
        self.logger.info("Timing analysis completed successfully")
        return buckets, cadence_analysis
    
    def _extract_word_timings(self, transcription_result) -> List[WordTiming]:
        """Extract word-level timing information from transcription result."""
        words = []
        
        # Handle different result structures
        if hasattr(transcription_result, 'merged_result'):
            segments = transcription_result.merged_result.segments
        else:
            segments = transcription_result.segments
        
        for segment in segments:
            if hasattr(segment, 'words') and segment.words:
                for word_data in segment.words:
                    # Handle different word data structures
                    if hasattr(word_data, 'word'):
                        # faster-whisper format
                        word_timing = WordTiming(
                            word=word_data.word.strip(),
                            start=word_data.start,
                            end=word_data.end,
                            probability=getattr(word_data, 'probability', 1.0)
                        )
                    elif isinstance(word_data, dict):
                        # Dictionary format
                        word_timing = WordTiming(
                            word=word_data.get('word', '').strip(),
                            start=word_data.get('start', 0.0),
                            end=word_data.get('end', 0.0),
                            probability=word_data.get('probability', 1.0)
                        )
                    else:
                        continue
                    
                    if word_timing.word:  # Skip empty words
                        words.append(word_timing)
        
        return sorted(words, key=lambda w: w.start)
    
    def _bucketize_words(self, words: List[WordTiming]) -> List[TimingBucket]:
        """Create time-based buckets of approximately bucket_seconds duration."""
        if not words:
            return []
        
        buckets = []
        current_bucket_words = []
        bucket_start = words[0].start
        bucket_id = 0
        
        for word in words:
            current_duration = word.end - bucket_start
            
            # Check if we should start a new bucket
            should_split = (
                current_duration >= self.bucket_seconds - self.bucket_tolerance and
                len(current_bucket_words) > 0
            )
            
            # Allow tolerance to avoid splitting words awkwardly
            if should_split and current_duration <= self.bucket_seconds + self.bucket_tolerance:
                # Finalize current bucket
                bucket = self._create_bucket(bucket_id, bucket_start, current_bucket_words)
                buckets.append(bucket)
                
                # Start new bucket
                bucket_id += 1
                current_bucket_words = [word]
                bucket_start = word.start
            else:
                current_bucket_words.append(word)
        
        # Handle remaining words
        if current_bucket_words:
            bucket = self._create_bucket(bucket_id, bucket_start, current_bucket_words)
            buckets.append(bucket)
        
        return buckets
    
    def _create_bucket(self, bucket_id: int, start_time: float, words: List[WordTiming]) -> TimingBucket:
        """Create a timing bucket from a list of words."""
        if not words:
            raise ValueError("Cannot create bucket from empty word list")
        
        end_time = words[-1].end
        text = " ".join(word.word for word in words)
        
        # Calculate basic metrics
        total_duration = end_time - start_time
        speech_time = sum(word.end - word.start for word in words)
        silence_time = total_duration - speech_time
        words_per_second = len(words) / total_duration if total_duration > 0 else 0
        
        # Calculate average confidence
        avg_confidence = np.mean([word.probability for word in words]) if words else 0.0
        
        # Initialize bucket (gap statistics will be calculated later)
        return TimingBucket(
            bucket_id=bucket_id,
            start_ts=start_time,
            end_ts=end_time,
            words=words,
            text=text,
            word_gap_count=0,
            word_gaps=[],
            word_gap_mean=0.0,
            word_gap_var=0.0,
            confidence=avg_confidence,
            speaker_overlap=None,
            cadence_anomaly=False,
            cadence_severity='normal',
            words_per_second=words_per_second,
            total_speech_time=speech_time,
            total_silence_time=silence_time
        )
    
    def _calculate_gap_statistics(self, bucket: TimingBucket) -> List[float]:
        """Calculate word gap statistics for a bucket."""
        if len(bucket.words) < 2:
            bucket.word_gap_count = 0
            bucket.word_gaps = []
            bucket.word_gap_mean = 0.0
            bucket.word_gap_var = 0.0
            return []
        
        # Calculate gaps between consecutive words (true silence)
        gaps = []
        for i in range(1, len(bucket.words)):
            gap = bucket.words[i].start - bucket.words[i-1].end
            gaps.append(max(0.0, gap))  # Ensure non-negative gaps
        
        # Store limited number of gaps for readability
        bucket.word_gaps = gaps[:self.gap_list_max]
        bucket.word_gap_count = len(gaps)
        
        if gaps:
            bucket.word_gap_mean = np.mean(gaps)
            bucket.word_gap_var = np.var(gaps, ddof=1) if len(gaps) > 1 else 0.0
        else:
            bucket.word_gap_mean = 0.0
            bucket.word_gap_var = 0.0
        
        return gaps
    
    def _analyze_global_cadence(self, all_gaps: List[float], buckets: List[TimingBucket]) -> CadenceAnalysis:
        """Perform global cadence analysis across all buckets."""
        if not all_gaps:
            return CadenceAnalysis(
                global_gap_mean=0.0,
                global_gap_std=0.0,
                total_words=sum(len(b.words) for b in buckets),
                total_gaps=0,
                anomaly_threshold=self.gap_threshold,
                anomalous_buckets=0,
                gap_percentiles={},
                cadence_summary="No gaps detected"
            )
        
        global_mean = np.mean(all_gaps)
        global_std = np.std(all_gaps, ddof=1) if len(all_gaps) > 1 else 0.0
        
        # Calculate percentiles for distribution analysis
        percentiles = [25, 50, 75, 90, 95]
        gap_percentiles = {
            f"p{p}": float(np.percentile(all_gaps, p)) for p in percentiles
        }
        
        # Generate summary
        cadence_summary = self._generate_cadence_summary(global_mean, global_std, gap_percentiles)
        
        return CadenceAnalysis(
            global_gap_mean=global_mean,
            global_gap_std=global_std,
            total_words=sum(len(b.words) for b in buckets),
            total_gaps=len(all_gaps),
            anomaly_threshold=self.gap_threshold,
            anomalous_buckets=0,  # Will be calculated in flagging step
            gap_percentiles=gap_percentiles,
            cadence_summary=cadence_summary
        )
    
    def _flag_cadence_anomalies(self, buckets: List[TimingBucket], cadence_analysis: CadenceAnalysis):
        """Flag buckets with anomalous cadence patterns."""
        anomalous_count = 0
        
        for bucket in buckets:
            if bucket.word_gap_count < 2:
                continue
            
            # Check for mean gap anomaly
            mean_deviation = abs(bucket.word_gap_mean - cadence_analysis.global_gap_mean)
            mean_threshold = self.gap_threshold * cadence_analysis.global_gap_std
            
            # Check for variance anomaly
            var_threshold = self.variance_threshold * (cadence_analysis.global_gap_std ** 2)
            
            is_anomalous = (
                mean_deviation > mean_threshold or
                bucket.word_gap_var > var_threshold
            )
            
            if is_anomalous:
                bucket.cadence_anomaly = True
                anomalous_count += 1
                
                # Determine severity
                if mean_deviation > 3 * mean_threshold or bucket.word_gap_var > 3 * var_threshold:
                    bucket.cadence_severity = 'severe'
                elif mean_deviation > 2 * mean_threshold or bucket.word_gap_var > 2 * var_threshold:
                    bucket.cadence_severity = 'moderate'
                else:
                    bucket.cadence_severity = 'mild'
        
        cadence_analysis.anomalous_buckets = anomalous_count
    
    def _add_speaker_overlap_info(self, buckets: List[TimingBucket], speaker_timeline):
        """Add speaker overlap information to buckets."""
        try:
            for bucket in buckets:
                # Check if any overlap intersects with bucket timespan
                if hasattr(speaker_timeline, 'crop'):
                    overlap_in_bucket = speaker_timeline.crop(bucket.start_ts, bucket.end_ts)
                    bucket.speaker_overlap = len(overlap_in_bucket) > 0
                else:
                    # Fallback for different timeline formats
                    bucket.speaker_overlap = False
        except Exception as e:
            self.logger.warning(f"Failed to add speaker overlap info: {e}")
            for bucket in buckets:
                bucket.speaker_overlap = None
    
    def _generate_cadence_summary(self, mean: float, std: float, percentiles: Dict[str, float]) -> str:
        """Generate human-readable cadence summary."""
        if mean < 0.05:
            pace = "very fast"
        elif mean < 0.1:
            pace = "fast"
        elif mean < 0.2:
            pace = "normal"
        elif mean < 0.4:
            pace = "slow"
        else:
            pace = "very slow"
        
        if std < 0.02:
            consistency = "very consistent"
        elif std < 0.05:
            consistency = "consistent"
        elif std < 0.1:
            consistency = "variable"
        else:
            consistency = "highly variable"
        
        return f"{pace} speech with {consistency} pacing (μ={mean:.3f}s, σ={std:.3f}s)"


def get_timing_analyzer(config: Optional[Dict[str, Any]] = None) -> TimingAnalyzer:
    """Factory function to create timing analyzer with configuration."""
    if config is None:
        config = {}
    
    return TimingAnalyzer(
        bucket_seconds=config.get('bucket_seconds', 4.0),
        bucket_tolerance=config.get('bucket_tolerance', 0.25),
        gap_threshold=config.get('gap_threshold', 1.5),
        gap_list_max=config.get('gap_list_max', 20),
        variance_threshold=config.get('variance_threshold', 1.5)
    )