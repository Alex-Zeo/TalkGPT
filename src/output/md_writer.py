"""
TalkGPT Output: Enhanced Markdown Writer

Generates comprehensive markdown output with full word-gap analytics,
cadence classification, and speaker overlap detection.
"""

from typing import List, Dict, Any, Optional, TextIO
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
