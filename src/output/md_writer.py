"""
TalkGPT Output: Enhanced Markdown Writer

Generates comprehensive markdown output with full word-gap analytics,
cadence classification, and speaker overlap detection.
"""

from typing import List, Dict, Any, Optional, TextIO
import json
import csv
import time
import logging
from pathlib import Path

from ..post.assembler import TranscriptionRecord

logger = logging.getLogger(__name__)

class MarkdownWriter:
    """
    Enhanced markdown writer for comprehensive transcription output.
    
    Generates markdown reports with complete word-gap analysis, cadence
    classification, and speaker overlap information according to the
    new 4-second windowing specification.
    """
    
    def __init__(self, 
                 precision: int = 4,
                 max_gaps_per_line: Optional[int] = None,
                 include_confidence: bool = True,
                 include_overlap: bool = True,
                 include_word_count: bool = True):
        """
        Initialize markdown writer with formatting options.
        
        Args:
            precision: Decimal precision for gap values
            max_gaps_per_line: Maximum gaps to show per line (None = unlimited)
            include_confidence: Whether to include confidence scores
            include_overlap: Whether to include speaker overlap info
            include_word_count: Whether to include word counts
        """
        self.precision = precision
        self.max_gaps_per_line = max_gaps_per_line
        self.include_confidence = include_confidence
        self.include_overlap = include_overlap
        self.include_word_count = include_word_count
    
    def write_enhanced_markdown(self,
                               records: List[TranscriptionRecord],
                               output_path: Path,
                               title: str = "TalkGPT Enhanced Transcription",
                               metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Write enhanced markdown output with complete analysis data.
        
        Args:
            records: List of TranscriptionRecord objects
            output_path: Path to write markdown file
            title: Document title
            metadata: Optional metadata to include in header
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                self._write_header(f, title, metadata, records)
                self._write_transcript_sections(f, records)
                self._write_analysis_summary(f, records)
            
            logger.info(f"Enhanced markdown written to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to write enhanced markdown: {e}")
            raise
    
    def _write_header(self,
                     f: TextIO,
                     title: str,
                     metadata: Optional[Dict[str, Any]],
                     records: List[TranscriptionRecord]) -> None:
        """Write markdown header with metadata and summary."""
        f.write(f"# {title}\n\n")
        
        # Write metadata if provided
        if metadata:
            f.write("## Transcription Metadata\n\n")
            for key, value in metadata.items():
                f.write(f"**{key.replace('_', ' ').title()}:** {value}  \n")
            f.write("\n")
        
        # Write processing summary
        if records:
            total_duration = sum(r.duration for r in records)
            total_words = sum(r.word_count for r in records)
            total_gaps = sum(r.word_gap_count for r in records)
            
            f.write("## Processing Summary\n\n")
            f.write(f"**Total Duration:** {total_duration:.1f} seconds  \n")
            f.write(f"**Total Words:** {total_words}  \n")
            f.write(f"**Total Word Gaps:** {total_gaps}  \n")
            f.write(f"**Timing Buckets:** {len(records)} (4-second windows)  \n")
            f.write(f"**Analysis Method:** Population variance with ±1.5σ cadence thresholds  \n")
            f.write("\n")
    
    def _write_transcript_sections(self,
                                  f: TextIO,
                                  records: List[TranscriptionRecord]) -> None:
        """Write transcript sections with complete analysis data."""
        f.write("## Enhanced Transcript\n\n")
        f.write("*Each section represents a ~4-second timing window with comprehensive word-gap analysis.*\n\n")
        
        for i, record in enumerate(records, 1):
            self._write_record_section(f, i, record)
    
    def _write_record_section(self,
                             f: TextIO,
                             section_number: int,
                             record: TranscriptionRecord) -> None:
        """
        Write a single transcript section with all analysis data.
        
        Follows the specified format:
        2. **[04:06–08:21]** A full commitment's what I'm thinking of …
        <sub>confidence -0.26</sub>
        <sub>speaker_overlap unknown check pyannote</sub>
        <sub>word_gap_count 14</sub>
        <sub>word_gaps 0.0742, 0.0736, ...</sub>
        <sub>word_gap_mean 0.0739</sub>
        <sub>word_gap_var 0.00018</sub>
        <sub>cadence fast</sub>
        """
        # Main transcript line
        time_range = record.format_time_range()
        f.write(f"{section_number}. **[{time_range}]** {record.text}\n")
        
        # Analysis metadata lines
        if self.include_confidence:
            f.write(f"<sub>confidence {record.confidence_score:.2f}</sub>\n")
        
        if self.include_overlap:
            f.write(f"<sub>speaker_overlap {record.speaker_overlap}</sub>\n")
        
        if self.include_word_count:
            f.write(f"<sub>word_gap_count {record.word_gap_count}</sub>\n")
        
        # Word gaps - show ALL gaps (no truncation per requirements)
        if record.word_gaps:
            gaps_str = record.format_gaps_string(
                precision=self.precision,
                max_gaps=self.max_gaps_per_line
            )
            f.write(f"<sub>word_gaps {gaps_str}</sub>\n")
        else:
            f.write("<sub>word_gaps </sub>\n")
        
        # Gap statistics
        f.write(f"<sub>word_gap_mean {record.word_gap_mean:.{self.precision}f}</sub>\n")
        f.write(f"<sub>word_gap_var {record.word_gap_var:.{self.precision + 2}f}</sub>\n")
        
        # Cadence classification
        f.write(f"<sub>cadence {record.cadence}</sub>\n")
        
        f.write("\n")
    
    def _write_analysis_summary(self,
                               f: TextIO,
                               records: List[TranscriptionRecord]) -> None:
        """Write analysis summary section."""
        if not records:
            return
        
        f.write("## Analysis Summary\n\n")
        
        # Cadence distribution
        cadence_counts = {'slow': 0, 'normal': 0, 'fast': 0}
        for record in records:
            cadence_counts[record.cadence] += 1
        
        f.write("### Cadence Distribution\n\n")
        for cadence, count in cadence_counts.items():
            percentage = (count / len(records)) * 100
            f.write(f"- **{cadence.title()}:** {count} segments ({percentage:.1f}%)  \n")
        f.write("\n")
        
        # Speaker overlap analysis
        overlap_counts = {'overlap': 0, 'single': 0, 'unknown check pyannote': 0}
        for record in records:
            overlap_counts[record.speaker_overlap] += 1
        
        f.write("### Speaker Overlap Analysis\n\n")
        for status, count in overlap_counts.items():
            percentage = (count / len(records)) * 100
            f.write(f"- **{status.replace('_', ' ').title()}:** {count} segments ({percentage:.1f}%)  \n")
        f.write("\n")
        
        # Quality metrics
        total_words = sum(r.word_count for r in records)
        total_gaps = sum(r.word_gap_count for r in records)
        avg_confidence = sum(r.confidence_score for r in records) / len(records)
        
        f.write("### Quality Metrics\n\n")
        f.write(f"- **Average Confidence:** {avg_confidence:.3f}  \n")
        f.write(f"- **Words per Segment:** {total_words / len(records):.1f}  \n")
        f.write(f"- **Gaps per Segment:** {total_gaps / len(records):.1f}  \n")
        f.write("\n")
        
        # Gap statistics
        all_gaps = []
        for record in records:
            all_gaps.extend(record.word_gaps)
        
        if all_gaps:
            import statistics
            global_mean = statistics.mean(all_gaps)
            global_var = sum((gap - global_mean) ** 2 for gap in all_gaps) / len(all_gaps)
            global_std = global_var ** 0.5
            
            f.write("### Global Gap Statistics\n\n")
            f.write(f"- **Total Gaps Analyzed:** {len(all_gaps)}  \n")
            f.write(f"- **Global Mean:** {global_mean:.{self.precision}f}s  \n")
            f.write(f"- **Global Variance:** {global_var:.{self.precision + 2}f}  \n")
            f.write(f"- **Global Std Dev:** {global_std:.{self.precision}f}s  \n")
            f.write(f"- **Cadence Thresholds:** Fast < {global_mean - 1.5 * global_std:.3f}s, "
                   f"Slow > {global_mean + 1.5 * global_std:.3f}s  \n")

def write_enhanced_markdown_report(records: List[TranscriptionRecord],
                                  output_path: Path,
                                  title: str = "TalkGPT Enhanced Transcription",
                                  metadata: Optional[Dict[str, Any]] = None,
                                  **writer_options) -> None:
    """
    Convenience function to write enhanced markdown report.
    
    Args:
        records: List of TranscriptionRecord objects
        output_path: Path to write markdown file
        title: Document title
        metadata: Optional metadata dictionary
        **writer_options: Additional options for MarkdownWriter
    """
    writer = MarkdownWriter(**writer_options)
    writer.write_enhanced_markdown(records, output_path, title, metadata)


# --- Unified timing-analysis outputs (migrated from analytics.enhanced_output) ---

def write_timing_analysis_outputs(
    transcription_result: Any,
    timing_buckets: List[Any],
    cadence_analysis: Any,
    speaker_result: Optional[Any],
    uncertainty_result: Optional[Any],
    output_dir: Path,
    base_name: str,
) -> Dict[str, str]:
    """
    Generate timing-analysis based outputs (markdown, json, srt, csv, cadence report)
    using a unified interface colocated with markdown writers.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_files: Dict[str, str] = {}

    # 1) Enhanced Markdown with Timing Analysis
    md_file = output_dir / f"{base_name}_enhanced.md"
    _generate_enhanced_markdown_with_timing(timing_buckets, cadence_analysis, uncertainty_result, md_file)
    output_files["enhanced_markdown"] = str(md_file)

    # 2) Comprehensive JSON with Timing Data
    json_file = output_dir / f"{base_name}_timing.json"
    _generate_timing_json(transcription_result, timing_buckets, cadence_analysis, speaker_result, uncertainty_result, json_file)
    output_files["timing_json"] = str(json_file)

    # 3) SRT with timing indicators
    srt_file = output_dir / f"{base_name}_timing.srt"
    _generate_timing_srt(timing_buckets, srt_file)
    output_files["timing_srt"] = str(srt_file)

    # 4) Detailed CSV
    csv_file = output_dir / f"{base_name}_timing_analysis.csv"
    _generate_timing_csv(timing_buckets, cadence_analysis, csv_file)
    output_files["timing_csv"] = str(csv_file)

    # 5) Cadence Analysis Report
    cadence_file = output_dir / f"{base_name}_cadence_report.md"
    _generate_cadence_report(cadence_analysis, timing_buckets, cadence_file)
    output_files["cadence_report"] = str(cadence_file)

    return output_files


def _generate_enhanced_markdown_with_timing(
    timing_buckets: List[Any],
    cadence_analysis: Any,
    uncertainty_result: Optional[Any],
    output_file: Path,
) -> None:
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# TalkGPT Enhanced Transcription with Timing Analysis\n\n")
        f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Timing Buckets:** {len(timing_buckets)}  \n")
        f.write(f"**Total Words:** {getattr(cadence_analysis, 'total_words', 0)}  \n")
        f.write(f"**Total Gaps:** {getattr(cadence_analysis, 'total_gaps', 0)}  \n")
        f.write(f"**Cadence Summary:** {getattr(cadence_analysis, 'cadence_summary', {})}  \n")

        if getattr(cadence_analysis, 'anomalous_buckets', 0) > 0:
            total = len(timing_buckets) or 1
            ab = getattr(cadence_analysis, 'anomalous_buckets', 0)
            f.write(f"**Anomalous Buckets:** {ab}/{total} ({ab/total*100:.1f}%)  \n")

        f.write("\n## Cadence Statistics\n\n")
        f.write(f"- **Global Gap Mean:** {getattr(cadence_analysis, 'global_gap_mean', 0.0):.3f}s  \n")
        f.write(f"- **Global Gap Std:** {getattr(cadence_analysis, 'global_gap_std', 0.0):.3f}s  \n")
        f.write(f"- **Anomaly Threshold:** {getattr(cadence_analysis, 'anomaly_threshold', 0)}x standard deviation  \n")

        gp = getattr(cadence_analysis, 'gap_percentiles', None)
        if gp:
            f.write("\n### Gap Distribution Percentiles\n\n")
            for percentile, value in gp.items():
                f.write(f"- **{percentile.upper()}:** {value:.3f}s  \n")

        f.write("\n## Detailed Transcript with Timing Analysis\n\n")
        for i, bucket in enumerate(timing_buckets, 1):
            start_time = _format_time_mmssms(getattr(bucket, 'start_ts', getattr(bucket, 'start_time', 0.0)))
            end_time = _format_time_mmssms(getattr(bucket, 'end_ts', getattr(bucket, 'end_time', 0.0)))
            text = getattr(bucket, 'text', '')
            f.write(f"{i}. **[{start_time}–{end_time}]** {text}  \n")
            f.write(f"    <sub>confidence {getattr(bucket, 'confidence', 0.0):.2f}</sub>  \n")
            overlap_val = getattr(bucket, 'speaker_overlap', None)
            if overlap_val is None:
                overlap_status = "unknown"
            else:
                overlap_status = str(overlap_val).lower() if isinstance(overlap_val, bool) else str(overlap_val)
            f.write(f"    <sub>speaker_overlap {overlap_status}</sub>  \n")
            f.write(f"    <sub>word_gap_count {getattr(bucket, 'word_gap_count', 0)}</sub>  \n")
            gaps = getattr(bucket, 'word_gaps', []) or []
            if gaps:
                gaps_str = ",".join(f"{gap:.4f}" for gap in gaps)
                f.write(f"    <sub>word_gaps {gaps_str}</sub>  \n")
            f.write(f"    <sub>word_gap_mean {getattr(bucket, 'word_gap_mean', 0.0):.4f}</sub>  \n")
            f.write(f"    <sub>word_gap_var {getattr(bucket, 'word_gap_var', 0.0):.6f}</sub>  \n\n")


def _generate_timing_json(
    transcription_result: Any,
    timing_buckets: List[Any],
    cadence_analysis: Any,
    speaker_result: Optional[Any],
    uncertainty_result: Optional[Any],
    output_file: Path,
) -> None:
    buckets_data = []
    for bucket in timing_buckets:
        start_ts = getattr(bucket, 'start_ts', getattr(bucket, 'start_time', 0.0))
        end_ts = getattr(bucket, 'end_ts', getattr(bucket, 'end_time', 0.0))
        words = getattr(bucket, 'words', []) or []
        bucket_dict = {
            'bucket_id': getattr(bucket, 'bucket_id', getattr(bucket, 'id', None)),
            'start_ts': start_ts,
            'end_ts': end_ts,
            'duration': end_ts - start_ts,
            'text': getattr(bucket, 'text', ''),
            'word_count': len(words),
            'words': [
                {
                    'word': getattr(w, 'word', ''),
                    'start': getattr(w, 'start', 0.0),
                    'end': getattr(w, 'end', 0.0),
                    'probability': getattr(w, 'probability', 0.0),
                } for w in words
            ],
            'timing_metrics': {
                'word_gap_count': getattr(bucket, 'word_gap_count', 0),
                'word_gaps': getattr(bucket, 'word_gaps', []) or [],
                'word_gap_mean': getattr(bucket, 'word_gap_mean', 0.0),
                'word_gap_var': getattr(bucket, 'word_gap_var', 0.0),
                'words_per_second': getattr(bucket, 'words_per_second', 0.0),
                'total_speech_time': getattr(bucket, 'total_speech_time', 0.0),
                'total_silence_time': getattr(bucket, 'total_silence_time', 0.0),
            },
            'quality_metrics': {
                'confidence': getattr(bucket, 'confidence', 0.0),
                'speaker_overlap': getattr(bucket, 'speaker_overlap', None),
                'cadence_anomaly': getattr(bucket, 'cadence_anomaly', False),
                'cadence_severity': getattr(bucket, 'cadence_severity', None),
            }
        }
        buckets_data.append(bucket_dict)

    data: Dict[str, Any] = {
        'metadata': {
            'version': '0.2.0',
            'format': 'TalkGPT Enhanced JSON with Timing Analysis v1.0',
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'features': ['word_timestamps', 'timing_analysis', 'cadence_analysis'],
        },
        'transcription': {
            'language': getattr(transcription_result, 'language', 'unknown'),
            'language_probability': getattr(transcription_result, 'language_probability', 0.0),
            'total_duration': timing_buckets[-1].end_ts if timing_buckets else 0.0,
        },
        'timing_analysis': {
            'bucket_count': len(timing_buckets),
            'buckets': buckets_data,
            'global_cadence': {
                'gap_mean': getattr(cadence_analysis, 'global_gap_mean', 0.0),
                'gap_std': getattr(cadence_analysis, 'global_gap_std', 0.0),
                'total_words': getattr(cadence_analysis, 'total_words', 0),
                'total_gaps': getattr(cadence_analysis, 'total_gaps', 0),
                'anomaly_threshold': getattr(cadence_analysis, 'anomaly_threshold', 0),
                'anomalous_buckets': getattr(cadence_analysis, 'anomalous_buckets', 0),
                'gap_percentiles': getattr(cadence_analysis, 'gap_percentiles', {}),
                'cadence_summary': getattr(cadence_analysis, 'cadence_summary', {}),
            },
        },
    }

    if speaker_result is not None:
        data['speaker_analysis'] = {
            'enabled': True,
            'speaker_count': getattr(getattr(speaker_result, 'diarization_result', None), 'speaker_count', 0),
            'overlaps_detected': len(getattr(getattr(speaker_result, 'diarization_result', None), 'overlap_segments', []) or []),
        }

    if uncertainty_result is not None:
        data['uncertainty_analysis'] = {
            'enabled': True,
            'overall_score': getattr(getattr(uncertainty_result, 'quality_metrics', None), 'overall_quality_score', None),
            'flagged_segments': getattr(uncertainty_result, 'flagged_segments', []),
            'flagged_percentage': getattr(uncertainty_result, 'flagged_percentage', None),
        }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _generate_timing_srt(timing_buckets: List[Any], output_file: Path) -> None:
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, bucket in enumerate(timing_buckets, 1):
            start_ts = getattr(bucket, 'start_ts', getattr(bucket, 'start_time', 0.0))
            end_ts = getattr(bucket, 'end_ts', getattr(bucket, 'end_time', 0.0))
            start_time = _format_srt_time(start_ts)
            end_time = _format_srt_time(end_ts)
            text = getattr(bucket, 'text', '')
            indicators = []
            if getattr(bucket, 'cadence_anomaly', False):
                indicators.append(f"[{str(getattr(bucket, 'cadence_severity', 'CADENCE')).upper()}_CADENCE]")
            if getattr(bucket, 'speaker_overlap', False):
                indicators.append("[OVERLAP]")
            if getattr(bucket, 'confidence', 1.0) < 0.5:
                indicators.append("[LOW_CONF]")
            if indicators:
                text += " " + " ".join(indicators)
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")


def _generate_timing_csv(timing_buckets: List[Any], cadence_analysis: Any, output_file: Path) -> None:
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        headers = [
            'bucket_id', 'start_time', 'end_time', 'duration', 'text', 'word_count',
            'confidence', 'speaker_overlap', 'word_gap_count', 'word_gap_mean',
            'word_gap_var', 'words_per_second', 'speech_time', 'silence_time',
            'cadence_anomaly', 'cadence_severity', 'gap_deviation_from_global',
        ]
        writer.writerow(headers)
        for bucket in timing_buckets:
            start_ts = getattr(bucket, 'start_ts', getattr(bucket, 'start_time', 0.0))
            end_ts = getattr(bucket, 'end_ts', getattr(bucket, 'end_time', 0.0))
            gap_mean = getattr(bucket, 'word_gap_mean', 0.0)
            global_mean = getattr(cadence_analysis, 'global_gap_mean', 0.0)
            row = [
                getattr(bucket, 'bucket_id', getattr(bucket, 'id', None)),
                start_ts,
                end_ts,
                end_ts - start_ts,
                getattr(bucket, 'text', ''),
                len(getattr(bucket, 'words', []) or []),
                getattr(bucket, 'confidence', 0.0),
                getattr(bucket, 'speaker_overlap', False),
                getattr(bucket, 'word_gap_count', 0),
                gap_mean,
                getattr(bucket, 'word_gap_var', 0.0),
                getattr(bucket, 'words_per_second', 0.0),
                getattr(bucket, 'total_speech_time', 0.0),
                getattr(bucket, 'total_silence_time', 0.0),
                getattr(bucket, 'cadence_anomaly', False),
                getattr(bucket, 'cadence_severity', None),
                abs(gap_mean - global_mean),
            ]
            writer.writerow(row)


def _generate_cadence_report(cadence_analysis: Any, timing_buckets: List[Any], output_file: Path) -> None:
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Cadence Analysis Report\n\n")
        f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Analysis Summary:** {getattr(cadence_analysis, 'cadence_summary', {})}  \n\n")
        f.write("## Global Statistics\n\n")
        f.write(f"- **Total Words:** {getattr(cadence_analysis, 'total_words', 0):,}  \n")
        f.write(f"- **Total Word Gaps:** {getattr(cadence_analysis, 'total_gaps', 0):,}  \n")
        f.write(f"- **Global Gap Mean:** {getattr(cadence_analysis, 'global_gap_mean', 0.0):.4f}s  \n")
        f.write(f"- **Global Gap Std:** {getattr(cadence_analysis, 'global_gap_std', 0.0):.4f}s  \n")
        f.write(f"- **Anomaly Threshold:** {getattr(cadence_analysis, 'anomaly_threshold', 0)}x std deviation  \n")
        ab = getattr(cadence_analysis, 'anomalous_buckets', 0)
        total = len(timing_buckets) or 1
        f.write(f"- **Anomalous Buckets:** {ab}/{total} ({ab/total*100:.1f}%)  \n\n")
        gp = getattr(cadence_analysis, 'gap_percentiles', None)
        if gp:
            f.write("## Gap Distribution\n\n")
            f.write("| Percentile | Gap Duration |\n")
            f.write("|------------|-------------|\n")
            for percentile, value in gp.items():
                f.write(f"| {percentile.upper()} | {value:.4f}s |\n")
            f.write("\n")
        # Anomalous bucket details
        anomalous = [b for b in timing_buckets if getattr(b, 'cadence_anomaly', False)]
        if anomalous:
            f.write("## Anomalous Cadence Segments\n\n")
            f.write("| Time Range | Severity | Gap Mean | Gap Var | Deviation |\n")
            f.write("|------------|----------|----------|---------|----------|\n")
            gm = getattr(cadence_analysis, 'global_gap_mean', 0.0)
            for bucket in anomalous:
                start_ts = getattr(bucket, 'start_ts', getattr(bucket, 'start_time', 0.0))
                end_ts = getattr(bucket, 'end_ts', getattr(bucket, 'end_time', 0.0))
                tr = f"{_format_time_mmssms(start_ts)}–{_format_time_mmssms(end_ts)}"
                dev = abs(getattr(bucket, 'word_gap_mean', 0.0) - gm)
                f.write(f"| {tr} | {getattr(bucket, 'cadence_severity', '')} | {getattr(bucket, 'word_gap_mean', 0.0):.4f}s | {getattr(bucket, 'word_gap_var', 0.0):.6f} | {dev:.4f}s |\n")
            f.write("\n")
        # Recommendations
        f.write("## Recommendations\n\n")
        gmean = getattr(cadence_analysis, 'global_gap_mean', 0.0)
        gstd = getattr(cadence_analysis, 'global_gap_std', 0.0)
        ratio = gstd
        if getattr(cadence_analysis, 'anomalous_buckets', 0) == 0:
            f.write("✅ **Excellent cadence consistency** - No anomalous segments detected.  \n")
        elif (getattr(cadence_analysis, 'anomalous_buckets', 0) / (len(timing_buckets) or 1)) < 0.1:
            f.write("✅ **Good cadence consistency** - Only minor anomalies detected.  \n")
        elif (getattr(cadence_analysis, 'anomalous_buckets', 0) / (len(timing_buckets) or 1)) < 0.3:
            f.write("⚠️ **Moderate cadence variation** - Consider reviewing flagged segments.  \n")
        else:
            f.write("🔴 **High cadence variation** - Significant pacing inconsistencies detected.  \n")
        if gmean > 0.3:
            f.write("- Consider speech coaching for faster delivery  \n")
        elif gmean < 0.05:
            f.write("- Consider slowing down for better clarity  \n")
        if ratio > 0.1:
            f.write("- Work on consistent pacing throughout speech  \n")


def _format_time_mmssms(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:06.3f}"


def _format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

def validate_markdown_output(output_path: Path) -> Dict[str, Any]:
    """
    Validate generated markdown output for quality assurance.
    
    Args:
        output_path: Path to markdown file to validate
        
    Returns:
        Dictionary with validation results
    """
    try:
        if not output_path.exists():
            return {
                'valid': False,
                'error': 'File does not exist',
                'file_size': 0
            }
        
        content = output_path.read_text(encoding='utf-8')
        
        # Basic validation checks
        has_title = content.startswith('#')
        has_transcript = '## Enhanced Transcript' in content
        has_summary = '## Analysis Summary' in content
        has_cadence_info = 'cadence' in content
        has_gap_info = 'word_gaps' in content
        
        # Count sections
        import re
        sections = re.findall(r'^\d+\.\s\*\*\[', content, re.MULTILINE)
        
        return {
            'valid': all([has_title, has_transcript, has_summary, has_cadence_info, has_gap_info]),
            'file_size': len(content),
            'section_count': len(sections),
            'has_title': has_title,
            'has_transcript': has_transcript,
            'has_summary': has_summary,
            'has_cadence_info': has_cadence_info,
            'has_gap_info': has_gap_info,
            'content_preview': content[:200] + '...' if len(content) > 200 else content
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'file_size': 0
        }
