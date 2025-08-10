"""
TalkGPT Uncertainty Detection Module

Advanced uncertainty detection and quality assessment for transcription results
using confidence scoring, statistical analysis, and quality metrics.
"""

import numpy as np
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
import statistics

try:
    from ..utils.logger import get_logger, get_file_logger
    from ..core.transcriber import TranscriptionResult, BatchTranscriptionResult, TranscriptionSegment
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from utils.logger import get_logger, get_file_logger
    from core.transcriber import TranscriptionResult, BatchTranscriptionResult, TranscriptionSegment


@dataclass
class UncertaintySegment:
    """Segment with uncertainty information."""
    segment_id: int
    start_time: float
    end_time: float
    text: str
    confidence_score: float
    uncertainty_level: str  # "low", "medium", "high"
    uncertainty_reasons: List[str]
    suggested_review: bool
    quality_indicators: Dict[str, Any]


@dataclass
class ConfidenceStatistics:
    """Statistical analysis of confidence scores."""
    mean_confidence: float
    median_confidence: float
    std_confidence: float
    min_confidence: float
    max_confidence: float
    confidence_distribution: Dict[str, int]  # Binned distribution
    low_confidence_count: int
    medium_confidence_count: int
    high_confidence_count: int


@dataclass
class QualityMetrics:
    """Quality assessment metrics."""
    overall_quality_score: float  # 0-1 scale
    transcription_reliability: float
    estimated_accuracy: float
    problematic_segments_ratio: float
    average_segment_confidence: float
    consistency_score: float
    language_consistency: float
    temporal_consistency: float


@dataclass
class UncertaintyAnalysis:
    """Complete uncertainty analysis result."""
    original_result: Union[TranscriptionResult, BatchTranscriptionResult]
    uncertain_segments: List[UncertaintySegment]
    confidence_stats: ConfidenceStatistics
    quality_metrics: QualityMetrics
    uncertainty_threshold: float
    total_segments: int
    flagged_segments: int
    flagged_percentage: float
    recommendations: List[str]
    analysis_time: float


class UncertaintyDetector:
    """
    Advanced uncertainty detection and quality assessment system.
    
    Analyzes transcription results to identify low-confidence segments,
    calculate quality metrics, and provide recommendations for improvement.
    """
    
    def __init__(self,
                 confidence_threshold: float = -1.0,
                 quality_threshold: float = 0.7,
                 enable_statistical_analysis: bool = True,
                 enable_linguistic_analysis: bool = True):
        """
        Initialize the uncertainty detector.
        
        Args:
            confidence_threshold: Threshold for flagging low-confidence segments
            quality_threshold: Minimum quality score for acceptable transcription
            enable_statistical_analysis: Enable statistical confidence analysis
            enable_linguistic_analysis: Enable linguistic pattern analysis
        """
        self.confidence_threshold = confidence_threshold
        self.quality_threshold = quality_threshold
        self.enable_statistical_analysis = enable_statistical_analysis
        self.enable_linguistic_analysis = enable_linguistic_analysis
        
        self.logger = get_logger("talkgpt.uncertainty_detector")
        
        # Quality indicators patterns
        self.problematic_patterns = {
            'repetition': [r'\b(\w+)\s+\1\b', r'\b(\w{2,})\s+\1\b'],
            'filler_words': ['uh', 'um', 'er', 'ah', 'like', 'you know'],
            'incomplete_words': [r'\b\w{1,2}\b', r'\b[a-z]+\-\b'],
            'unusual_punctuation': [r'\.{2,}', r'\?{2,}', r'!{2,}'],
            'mixed_languages': [],  # Will be populated based on detection
            'incoherent_text': [r'\b[bcdfghjklmnpqrstvwxyz]{4,}\b']  # Consonant clusters
        }
        
        self.logger.info("Uncertainty detector initialized")
    
    def analyze_uncertainty(self,
                          transcription_result: Union[TranscriptionResult, BatchTranscriptionResult],
                          audio_path: Optional[Union[str, Path]] = None) -> UncertaintyAnalysis:
        """
        Perform comprehensive uncertainty analysis on transcription results.
        
        Args:
            transcription_result: Transcription result to analyze
            audio_path: Optional path to original audio file
            
        Returns:
            UncertaintyAnalysis with detailed uncertainty information
        """
        import time
        start_time = time.time()
        
        if audio_path:
            file_logger = get_file_logger(str(audio_path))
            file_logger.info("Starting uncertainty analysis")
        
        try:
            # Extract segments from result
            if isinstance(transcription_result, BatchTranscriptionResult):
                segments = transcription_result.merged_result.segments
                language = transcription_result.merged_result.language
            else:
                segments = transcription_result.segments
                language = transcription_result.language
            
            # Analyze each segment for uncertainty
            uncertain_segments = []
            confidence_scores = []
            
            for segment in segments:
                uncertainty_segment = self._analyze_segment_uncertainty(segment, language)
                uncertain_segments.append(uncertainty_segment)
                confidence_scores.append(segment.avg_logprob)
            
            # Calculate confidence statistics
            confidence_stats = self._calculate_confidence_statistics(confidence_scores)
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(uncertain_segments, confidence_stats)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(uncertain_segments, quality_metrics)
            
            # Count flagged segments
            flagged_segments = sum(1 for seg in uncertain_segments if seg.suggested_review)
            flagged_percentage = (flagged_segments / len(uncertain_segments) * 100) if uncertain_segments else 0
            
            analysis_time = time.time() - start_time
            
            result = UncertaintyAnalysis(
                original_result=transcription_result,
                uncertain_segments=uncertain_segments,
                confidence_stats=confidence_stats,
                quality_metrics=quality_metrics,
                uncertainty_threshold=self.confidence_threshold,
                total_segments=len(segments),
                flagged_segments=flagged_segments,
                flagged_percentage=flagged_percentage,
                recommendations=recommendations,
                analysis_time=analysis_time
            )
            
            if audio_path:
                file_logger.info(f"Uncertainty analysis completed: {flagged_segments}/{len(segments)} segments flagged "
                               f"({flagged_percentage:.1f}%), quality score: {quality_metrics.overall_quality_score:.2f}")
            
            return result
            
        except Exception as e:
            if audio_path:
                file_logger.error(f"Uncertainty analysis failed: {e}")
            raise
    
    def _analyze_segment_uncertainty(self, 
                                   segment: TranscriptionSegment,
                                   language: str) -> UncertaintySegment:
        """Analyze uncertainty for a single segment."""
        confidence_score = segment.avg_logprob
        text = segment.text.strip()
        
        # Determine uncertainty level based on confidence
        if confidence_score >= -0.5:
            uncertainty_level = "low"
        elif confidence_score >= -1.5:
            uncertainty_level = "medium"
        else:
            uncertainty_level = "high"
        
        # Analyze uncertainty reasons
        uncertainty_reasons = []
        quality_indicators = {}
        
        # 1. Confidence-based reasons
        if confidence_score < self.confidence_threshold:
            uncertainty_reasons.append("low_model_confidence")
        
        # 2. No-speech probability
        if segment.no_speech_prob > 0.5:
            uncertainty_reasons.append("high_no_speech_probability")
        
        # 3. Text-based analysis
        if self.enable_linguistic_analysis:
            text_issues = self._analyze_text_quality(text, language)
            uncertainty_reasons.extend(text_issues['issues'])
            quality_indicators.update(text_issues['indicators'])
        
        # 4. Statistical analysis
        if self.enable_statistical_analysis:
            statistical_issues = self._analyze_statistical_patterns(segment)
            uncertainty_reasons.extend(statistical_issues)
        
        # Determine if review is suggested
        suggested_review = (
            uncertainty_level == "high" or
            len(uncertainty_reasons) >= 2 or
            "low_model_confidence" in uncertainty_reasons
        )
        
        return UncertaintySegment(
            segment_id=segment.id,
            start_time=segment.start,
            end_time=segment.end,
            text=text,
            confidence_score=confidence_score,
            uncertainty_level=uncertainty_level,
            uncertainty_reasons=uncertainty_reasons,
            suggested_review=suggested_review,
            quality_indicators=quality_indicators
        )
    
    def _analyze_text_quality(self, text: str, language: str) -> Dict[str, Any]:
        """Analyze text for quality indicators."""
        issues = []
        indicators = {}
        
        if not text or len(text.strip()) == 0:
            issues.append("empty_text")
            return {'issues': issues, 'indicators': indicators}
        
        text_lower = text.lower()
        
        # Check for repetitive patterns
        import re
        for pattern in self.problematic_patterns['repetition']:
            if re.search(pattern, text_lower):
                issues.append("repetitive_text")
                break
        
        # Check for excessive filler words
        filler_count = sum(1 for filler in self.problematic_patterns['filler_words'] 
                          if filler in text_lower)
        filler_ratio = filler_count / len(text.split()) if text.split() else 0
        
        if filler_ratio > 0.2:  # More than 20% filler words
            issues.append("excessive_fillers")
        
        indicators['filler_ratio'] = filler_ratio
        
        # Check for incomplete words
        incomplete_count = 0
        for pattern in self.problematic_patterns['incomplete_words']:
            incomplete_count += len(re.findall(pattern, text))
        
        if incomplete_count > 2:
            issues.append("incomplete_words")
        
        indicators['incomplete_words'] = incomplete_count
        
        # Check for unusual punctuation
        unusual_punct = 0
        for pattern in self.problematic_patterns['unusual_punctuation']:
            unusual_punct += len(re.findall(pattern, text))
        
        if unusual_punct > 0:
            issues.append("unusual_punctuation")
        
        indicators['unusual_punctuation'] = unusual_punct
        
        # Check for very short or very long segments
        word_count = len(text.split())
        if word_count < 2:
            issues.append("very_short_segment")
        elif word_count > 50:
            issues.append("very_long_segment")
        
        indicators['word_count'] = word_count
        
        # Check for incoherent text (consonant clusters)
        incoherent_matches = 0
        for pattern in self.problematic_patterns['incoherent_text']:
            incoherent_matches += len(re.findall(pattern, text_lower))
        
        if incoherent_matches > 0:
            issues.append("incoherent_text")
        
        indicators['incoherent_matches'] = incoherent_matches
        
        return {'issues': issues, 'indicators': indicators}
    
    def _analyze_statistical_patterns(self, segment: TranscriptionSegment) -> List[str]:
        """Analyze segment for statistical anomalies."""
        issues = []
        
        # Check segment duration vs text length
        duration = segment.end - segment.start
        text_length = len(segment.text.split())
        
        if duration > 0:
            words_per_second = text_length / duration
            
            # Typical speech is 2-4 words per second
            if words_per_second > 6:
                issues.append("speech_too_fast")
            elif words_per_second < 0.5 and text_length > 1:
                issues.append("speech_too_slow")
        
        # Check for very short segments with complex text
        if duration < 1.0 and text_length > 10:
            issues.append("duration_text_mismatch")
        
        return issues
    
    def _calculate_confidence_statistics(self, confidence_scores: List[float]) -> ConfidenceStatistics:
        """Calculate statistical measures of confidence scores."""
        if not confidence_scores:
            return ConfidenceStatistics(
                mean_confidence=0.0,
                median_confidence=0.0,
                std_confidence=0.0,
                min_confidence=0.0,
                max_confidence=0.0,
                confidence_distribution={},
                low_confidence_count=0,
                medium_confidence_count=0,
                high_confidence_count=0
            )
        
        scores = np.array(confidence_scores)
        
        # Basic statistics
        mean_conf = float(np.mean(scores))
        median_conf = float(np.median(scores))
        std_conf = float(np.std(scores))
        min_conf = float(np.min(scores))
        max_conf = float(np.max(scores))
        
        # Binned distribution
        bins = [-np.inf, -2.0, -1.0, -0.5, 0.0]
        bin_labels = ["very_low", "low", "medium", "high"]
        hist, _ = np.histogram(scores, bins=bins)
        distribution = dict(zip(bin_labels, hist.tolist()))
        
        # Count by confidence levels
        low_count = int(np.sum(scores < -1.5))
        medium_count = int(np.sum((scores >= -1.5) & (scores < -0.5)))
        high_count = int(np.sum(scores >= -0.5))
        
        return ConfidenceStatistics(
            mean_confidence=mean_conf,
            median_confidence=median_conf,
            std_confidence=std_conf,
            min_confidence=min_conf,
            max_confidence=max_conf,
            confidence_distribution=distribution,
            low_confidence_count=low_count,
            medium_confidence_count=medium_count,
            high_confidence_count=high_count
        )
    
    def _calculate_quality_metrics(self,
                                 uncertain_segments: List[UncertaintySegment],
                                 confidence_stats: ConfidenceStatistics) -> QualityMetrics:
        """Calculate overall quality metrics."""
        if not uncertain_segments:
            return QualityMetrics(
                overall_quality_score=0.0,
                transcription_reliability=0.0,
                estimated_accuracy=0.0,
                problematic_segments_ratio=0.0,
                average_segment_confidence=0.0,
                consistency_score=0.0,
                language_consistency=1.0,
                temporal_consistency=1.0
            )
        
        total_segments = len(uncertain_segments)
        
        # Count problematic segments
        problematic_segments = sum(1 for seg in uncertain_segments 
                                 if seg.uncertainty_level in ["medium", "high"] or seg.suggested_review)
        
        problematic_ratio = problematic_segments / total_segments
        
        # Calculate reliability based on confidence distribution
        reliability = 1.0 - (confidence_stats.low_confidence_count / total_segments)
        
        # Estimate accuracy based on confidence scores
        # Map log probabilities to accuracy estimates
        avg_confidence = confidence_stats.mean_confidence
        if avg_confidence >= -0.5:
            estimated_accuracy = 0.95
        elif avg_confidence >= -1.0:
            estimated_accuracy = 0.90
        elif avg_confidence >= -1.5:
            estimated_accuracy = 0.80
        else:
            estimated_accuracy = 0.70
        
        # Calculate consistency scores
        consistency_score = self._calculate_consistency_score(uncertain_segments)
        language_consistency = self._calculate_language_consistency(uncertain_segments)
        temporal_consistency = self._calculate_temporal_consistency(uncertain_segments)
        
        # Overall quality score (weighted average)
        overall_quality = (
            reliability * 0.3 +
            estimated_accuracy * 0.3 +
            (1.0 - problematic_ratio) * 0.2 +
            consistency_score * 0.1 +
            language_consistency * 0.05 +
            temporal_consistency * 0.05
        )
        
        return QualityMetrics(
            overall_quality_score=overall_quality,
            transcription_reliability=reliability,
            estimated_accuracy=estimated_accuracy,
            problematic_segments_ratio=problematic_ratio,
            average_segment_confidence=avg_confidence,
            consistency_score=consistency_score,
            language_consistency=language_consistency,
            temporal_consistency=temporal_consistency
        )
    
    def _calculate_consistency_score(self, segments: List[UncertaintySegment]) -> float:
        """Calculate consistency score based on confidence variation."""
        if len(segments) < 2:
            return 1.0
        
        confidences = [seg.confidence_score for seg in segments]
        std_dev = statistics.stdev(confidences)
        
        # Lower standard deviation = higher consistency
        # Normalize to 0-1 scale (assuming std_dev rarely exceeds 2.0)
        consistency = max(0.0, 1.0 - (std_dev / 2.0))
        
        return consistency
    
    def _calculate_language_consistency(self, segments: List[UncertaintySegment]) -> float:
        """Calculate language consistency score."""
        # For now, assume high consistency (would need language detection per segment)
        # This is a placeholder for more sophisticated language consistency analysis
        
        # Check for mixed language indicators in text
        mixed_language_count = sum(1 for seg in segments 
                                 if "mixed_languages" in seg.uncertainty_reasons)
        
        if not segments:
            return 1.0
        
        consistency = 1.0 - (mixed_language_count / len(segments))
        return consistency
    
    def _calculate_temporal_consistency(self, segments: List[UncertaintySegment]) -> float:
        """Calculate temporal consistency score."""
        if len(segments) < 2:
            return 1.0
        
        # Check for temporal anomalies (gaps, overlaps, etc.)
        temporal_issues = 0
        
        for i in range(len(segments) - 1):
            current_end = segments[i].end_time
            next_start = segments[i + 1].start_time
            
            # Check for large gaps (> 5 seconds)
            if next_start - current_end > 5.0:
                temporal_issues += 1
            
            # Check for overlaps
            if next_start < current_end:
                temporal_issues += 1
        
        consistency = 1.0 - (temporal_issues / (len(segments) - 1))
        return max(0.0, consistency)
    
    def _generate_recommendations(self,
                                uncertain_segments: List[UncertaintySegment],
                                quality_metrics: QualityMetrics) -> List[str]:
        """Generate recommendations for improving transcription quality."""
        recommendations = []
        
        # Overall quality recommendations
        if quality_metrics.overall_quality_score < 0.7:
            recommendations.append("Consider using a higher quality audio source or different model settings")
        
        if quality_metrics.problematic_segments_ratio > 0.3:
            recommendations.append("High number of problematic segments detected - manual review recommended")
        
        # Specific issue recommendations
        issue_counts = {}
        for segment in uncertain_segments:
            for reason in segment.uncertainty_reasons:
                issue_counts[reason] = issue_counts.get(reason, 0) + 1
        
        total_segments = len(uncertain_segments)
        
        if issue_counts.get("low_model_confidence", 0) > total_segments * 0.2:
            recommendations.append("Consider using a larger model or different compute settings for better confidence")
        
        if issue_counts.get("high_no_speech_probability", 0) > total_segments * 0.1:
            recommendations.append("Audio may contain significant silence or noise - consider preprocessing")
        
        if issue_counts.get("repetitive_text", 0) > 0:
            recommendations.append("Repetitive text detected - may indicate model hallucination")
        
        if issue_counts.get("excessive_fillers", 0) > 0:
            recommendations.append("Excessive filler words detected - consider post-processing cleanup")
        
        if quality_metrics.consistency_score < 0.8:
            recommendations.append("Low consistency detected - check for audio quality variations")
        
        if quality_metrics.temporal_consistency < 0.9:
            recommendations.append("Temporal inconsistencies detected - check audio segmentation")
        
        # If no specific issues, provide general recommendations
        if not recommendations:
            if quality_metrics.overall_quality_score < 0.9:
                recommendations.append("Good quality transcription with minor areas for improvement")
            else:
                recommendations.append("High quality transcription - minimal issues detected")
        
        return recommendations
    
    def flag_uncertain_segments(self,
                              analysis: UncertaintyAnalysis,
                              custom_threshold: Optional[float] = None) -> List[UncertaintySegment]:
        """
        Flag segments that exceed uncertainty threshold.
        
        Args:
            analysis: Uncertainty analysis result
            custom_threshold: Custom confidence threshold (overrides default)
            
        Returns:
            List of flagged uncertain segments
        """
        threshold = custom_threshold if custom_threshold is not None else self.confidence_threshold
        
        flagged = []
        for segment in analysis.uncertain_segments:
            if (segment.confidence_score < threshold or 
                segment.uncertainty_level == "high" or
                len(segment.uncertainty_reasons) >= 2):
                flagged.append(segment)
        
        return flagged
    
    def save_uncertainty_analysis(self,
                                analysis: UncertaintyAnalysis,
                                output_path: Union[str, Path],
                                format: str = "json"):
        """
        Save uncertainty analysis to file.
        
        Args:
            analysis: Uncertainty analysis to save
            output_path: Output file path
            format: Output format (json, csv, txt)
        """
        output_path = Path(output_path)
        
        if format == "json":
            # Convert to JSON-serializable format
            data = asdict(analysis)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        elif format == "csv":
            # CSV format for segment analysis
            import csv
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header
                writer.writerow([
                    'segment_id', 'start_time', 'end_time', 'text', 
                    'confidence_score', 'uncertainty_level', 
                    'uncertainty_reasons', 'suggested_review'
                ])
                
                # Data
                for segment in analysis.uncertain_segments:
                    writer.writerow([
                        segment.segment_id,
                        segment.start_time,
                        segment.end_time,
                        segment.text,
                        segment.confidence_score,
                        segment.uncertainty_level,
                        '; '.join(segment.uncertainty_reasons),
                        segment.suggested_review
                    ])
        
        elif format == "txt":
            # Human-readable text report
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("TalkGPT Uncertainty Analysis Report\n")
                f.write("=" * 40 + "\n\n")
                
                f.write(f"Overall Quality Score: {analysis.quality_metrics.overall_quality_score:.2f}\n")
                f.write(f"Flagged Segments: {analysis.flagged_segments}/{analysis.total_segments} ({analysis.flagged_percentage:.1f}%)\n")
                f.write(f"Average Confidence: {analysis.confidence_stats.mean_confidence:.2f}\n\n")
                
                f.write("Recommendations:\n")
                for i, rec in enumerate(analysis.recommendations, 1):
                    f.write(f"{i}. {rec}\n")
                
                f.write("\nFlagged Segments:\n")
                f.write("-" * 20 + "\n")
                
                for segment in analysis.uncertain_segments:
                    if segment.suggested_review:
                        f.write(f"\nSegment {segment.segment_id} ({segment.start_time:.1f}s - {segment.end_time:.1f}s)\n")
                        f.write(f"Text: {segment.text}\n")
                        f.write(f"Confidence: {segment.confidence_score:.2f}\n")
                        f.write(f"Issues: {', '.join(segment.uncertainty_reasons)}\n")
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self.logger.info(f"Uncertainty analysis saved: {output_path}")


# Global uncertainty detector instance
_uncertainty_detector: Optional[UncertaintyDetector] = None


def get_uncertainty_detector(**kwargs) -> UncertaintyDetector:
    """Get the global uncertainty detector instance."""
    global _uncertainty_detector
    if _uncertainty_detector is None:
        _uncertainty_detector = UncertaintyDetector(**kwargs)
    return _uncertainty_detector


def analyze_uncertainty(transcription_result: Union[TranscriptionResult, BatchTranscriptionResult], 
                       **kwargs) -> UncertaintyAnalysis:
    """Analyze uncertainty using the global detector."""
    return get_uncertainty_detector().analyze_uncertainty(transcription_result, **kwargs)