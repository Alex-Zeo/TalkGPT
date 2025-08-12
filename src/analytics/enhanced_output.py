#!/usr/bin/env python3
"""
Enhanced Output Generation with Timing Analysis

Provides advanced output generation with detailed timing analysis including:
- Word-level bucket analysis
- Gap statistics and cadence information
- Enhanced markdown reports with timing metrics
- Comprehensive JSON with timing data
"""

import json
import csv
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from analytics.timing_analyzer import TimingBucket, CadenceAnalysis
from utils.logger import get_logger
from output.md_writer import write_timing_analysis_outputs


class EnhancedOutputGenerator:
    """Generate enhanced outputs with timing analysis."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def generate_enhanced_outputs(self,
                                transcription_result,
                                timing_buckets: List[TimingBucket],
                                cadence_analysis: CadenceAnalysis,
                                speaker_result=None,
                                uncertainty_result=None,
                                output_dir: Path = None,
                                base_name: str = "transcription") -> Dict[str, str]:
        """
        Generate enhanced output files with timing analysis.
        
        Args:
            transcription_result: Original transcription result
            timing_buckets: List of timing analysis buckets
            cadence_analysis: Global cadence analysis results
            speaker_result: Optional speaker analysis results
            uncertainty_result: Optional uncertainty analysis results
            output_dir: Output directory
            base_name: Base filename for outputs
            
        Returns:
            Dictionary mapping format names to file paths
        """
        if output_dir is None:
            output_dir = Path(".")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Generating enhanced outputs with {len(timing_buckets)} timing buckets")
        return write_timing_analysis_outputs(
            transcription_result,
            timing_buckets,
            cadence_analysis,
            speaker_result,
            uncertainty_result,
            output_dir,
            base_name,
        )
    
    
    def _generate_timing_json(self,
                            transcription_result,
                            timing_buckets: List[TimingBucket],
                            cadence_analysis: CadenceAnalysis,
                            speaker_result,
                            uncertainty_result,
                            output_file: Path):
        """Generate comprehensive JSON with timing analysis data."""
        # Convert timing buckets to serializable format
        buckets_data = []
        for bucket in timing_buckets:
            bucket_dict = {
                'bucket_id': bucket.bucket_id,
                'start_ts': bucket.start_ts,
                'end_ts': bucket.end_ts,
                'duration': bucket.end_ts - bucket.start_ts,
                'text': bucket.text,
                'word_count': len(bucket.words),
                'words': [
                    {
                        'word': word.word,
                        'start': word.start,
                        'end': word.end,
                        'probability': word.probability
                    }
                    for word in bucket.words
                ],
                'timing_metrics': {
                    'word_gap_count': bucket.word_gap_count,
                    'word_gaps': bucket.word_gaps,
                    'word_gap_mean': bucket.word_gap_mean,
                    'word_gap_var': bucket.word_gap_var,
                    'words_per_second': bucket.words_per_second,
                    'total_speech_time': bucket.total_speech_time,
                    'total_silence_time': bucket.total_silence_time
                },
                'quality_metrics': {
                    'confidence': bucket.confidence,
                    'speaker_overlap': bucket.speaker_overlap,
                    'cadence_anomaly': bucket.cadence_anomaly,
                    'cadence_severity': bucket.cadence_severity
                }
            }
            buckets_data.append(bucket_dict)
        
        # Create comprehensive data structure
        data = {
            'metadata': {
                'version': '0.2.0',
                'format': 'TalkGPT Enhanced JSON with Timing Analysis v1.0',
                'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'features': ['word_timestamps', 'timing_analysis', 'cadence_analysis']
            },
            'transcription': {
                'language': getattr(transcription_result, 'language', 'unknown'),
                'language_probability': getattr(transcription_result, 'language_probability', 0.0),
                'total_duration': timing_buckets[-1].end_ts if timing_buckets else 0.0
            },
            'timing_analysis': {
                'bucket_count': len(timing_buckets),
                'buckets': buckets_data,
                'global_cadence': {
                    'gap_mean': cadence_analysis.global_gap_mean,
                    'gap_std': cadence_analysis.global_gap_std,
                    'total_words': cadence_analysis.total_words,
                    'total_gaps': cadence_analysis.total_gaps,
                    'anomaly_threshold': cadence_analysis.anomaly_threshold,
                    'anomalous_buckets': cadence_analysis.anomalous_buckets,
                    'gap_percentiles': cadence_analysis.gap_percentiles,
                    'cadence_summary': cadence_analysis.cadence_summary
                }
            }
        }
        
        # Add speaker analysis if available
        if speaker_result:
            data['speaker_analysis'] = {
                'enabled': True,
                'speaker_count': getattr(speaker_result.diarization_result, 'speaker_count', 0),
                'overlaps_detected': len(getattr(speaker_result.diarization_result, 'overlap_segments', []))
            }
        
        # Add uncertainty analysis if available
        if uncertainty_result:
            data['uncertainty_analysis'] = {
                'enabled': True,
                'overall_score': uncertainty_result.quality_metrics.overall_quality_score,
                'flagged_segments': uncertainty_result.flagged_segments,
                'flagged_percentage': uncertainty_result.flagged_percentage
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _generate_timing_srt(self, timing_buckets: List[TimingBucket], output_file: Path):
        """Generate SRT file with timing analysis indicators."""
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, bucket in enumerate(timing_buckets, 1):
                start_time = self._format_srt_time(bucket.start_ts)
                end_time = self._format_srt_time(bucket.end_ts)
                
                text = bucket.text
                
                # Add timing indicators
                indicators = []
                if bucket.cadence_anomaly:
                    indicators.append(f"[{bucket.cadence_severity.upper()}_CADENCE]")
                
                if bucket.speaker_overlap:
                    indicators.append("[OVERLAP]")
                
                if bucket.confidence < 0.5:
                    indicators.append("[LOW_CONF]")
                
                if indicators:
                    text += " " + " ".join(indicators)
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
    
    def _generate_timing_csv(self,
                           timing_buckets: List[TimingBucket],
                           cadence_analysis: CadenceAnalysis,
                           output_file: Path):
        """Generate detailed CSV for timing analysis."""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            headers = [
                'bucket_id', 'start_time', 'end_time', 'duration', 'text', 'word_count',
                'confidence', 'speaker_overlap', 'word_gap_count', 'word_gap_mean',
                'word_gap_var', 'words_per_second', 'speech_time', 'silence_time',
                'cadence_anomaly', 'cadence_severity', 'gap_deviation_from_global'
            ]
            writer.writerow(headers)
            
            # Data rows
            for bucket in timing_buckets:
                gap_deviation = abs(bucket.word_gap_mean - cadence_analysis.global_gap_mean)
                
                row = [
                    bucket.bucket_id,
                    bucket.start_ts,
                    bucket.end_ts,
                    bucket.end_ts - bucket.start_ts,
                    bucket.text,
                    len(bucket.words),
                    bucket.confidence,
                    bucket.speaker_overlap,
                    bucket.word_gap_count,
                    bucket.word_gap_mean,
                    bucket.word_gap_var,
                    bucket.words_per_second,
                    bucket.total_speech_time,
                    bucket.total_silence_time,
                    bucket.cadence_anomaly,
                    bucket.cadence_severity,
                    gap_deviation
                ]
                
                writer.writerow(row)
    
    def _generate_cadence_report(self,
                               cadence_analysis: CadenceAnalysis,
                               timing_buckets: List[TimingBucket],
                               output_file: Path):
        """Generate detailed cadence analysis report."""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Cadence Analysis Report\n\n")
            f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**Analysis Summary:** {cadence_analysis.cadence_summary}  \n\n")
            
            f.write("## Global Statistics\n\n")
            f.write(f"- **Total Words:** {cadence_analysis.total_words:,}  \n")
            f.write(f"- **Total Word Gaps:** {cadence_analysis.total_gaps:,}  \n")
            f.write(f"- **Global Gap Mean:** {cadence_analysis.global_gap_mean:.4f}s  \n")
            f.write(f"- **Global Gap Std:** {cadence_analysis.global_gap_std:.4f}s  \n")
            f.write(f"- **Anomaly Threshold:** {cadence_analysis.anomaly_threshold}x std deviation  \n")
            f.write(f"- **Anomalous Buckets:** {cadence_analysis.anomalous_buckets}/{len(timing_buckets)} "
                   f"({cadence_analysis.anomalous_buckets/len(timing_buckets)*100:.1f}%)  \n\n")
            
            if cadence_analysis.gap_percentiles:
                f.write("## Gap Distribution\n\n")
                f.write("| Percentile | Gap Duration |\n")
                f.write("|------------|-------------|\n")
                for percentile, value in cadence_analysis.gap_percentiles.items():
                    f.write(f"| {percentile.upper()} | {value:.4f}s |\n")
                f.write("\n")
            
            # Anomalous buckets details
            anomalous_buckets = [b for b in timing_buckets if b.cadence_anomaly]
            if anomalous_buckets:
                f.write("## Anomalous Cadence Segments\n\n")
                f.write("| Time Range | Severity | Gap Mean | Gap Var | Deviation |\n")
                f.write("|------------|----------|----------|---------|----------|\n")
                
                for bucket in anomalous_buckets:
                    time_range = f"{self._format_time(bucket.start_ts)}–{self._format_time(bucket.end_ts)}"
                    deviation = abs(bucket.word_gap_mean - cadence_analysis.global_gap_mean)
                    
                    f.write(f"| {time_range} | {bucket.cadence_severity} | "
                           f"{bucket.word_gap_mean:.4f}s | {bucket.word_gap_var:.6f} | "
                           f"{deviation:.4f}s |\n")
                
                f.write("\n")
            
            # Recommendations
            f.write("## Recommendations\n\n")
            if cadence_analysis.anomalous_buckets == 0:
                f.write("✅ **Excellent cadence consistency** - No anomalous segments detected.  \n")
            elif cadence_analysis.anomalous_buckets / len(timing_buckets) < 0.1:
                f.write("✅ **Good cadence consistency** - Only minor anomalies detected.  \n")
            elif cadence_analysis.anomalous_buckets / len(timing_buckets) < 0.3:
                f.write("⚠️ **Moderate cadence variation** - Consider reviewing flagged segments.  \n")
            else:
                f.write("🔴 **High cadence variation** - Significant pacing inconsistencies detected.  \n")
            
            if cadence_analysis.global_gap_mean > 0.3:
                f.write("- Consider speech coaching for faster delivery  \n")
            elif cadence_analysis.global_gap_mean < 0.05:
                f.write("- Consider slowing down for better clarity  \n")
            
            if cadence_analysis.global_gap_std > 0.1:
                f.write("- Work on consistent pacing throughout speech  \n")
    
    def _format_time(self, seconds: float) -> str:
        """Format time as MM:SS.mmm"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:06.3f}"
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT subtitle format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


def get_enhanced_output_generator() -> EnhancedOutputGenerator:
    """Factory function to create enhanced output generator."""
    return EnhancedOutputGenerator()