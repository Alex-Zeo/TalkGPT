"""
TalkGPT Output Module

Enhanced output generation with comprehensive markdown and JSON formats
for word-gap analysis and cadence classification results.
"""

from .md_writer import MarkdownWriter, write_enhanced_markdown_report, validate_markdown_output

__all__ = [
    'MarkdownWriter',
    'write_enhanced_markdown_report', 
    'validate_markdown_output'
]
