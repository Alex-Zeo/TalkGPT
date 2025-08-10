"""
TalkGPT Core Utilities

Core utility functions for processing transcription data, including
word-level analysis, segmentation, and data structure conversions.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class Word:
    """
    Single word with timing and confidence information.
    
    This is the fundamental unit for word-gap analysis and cadence detection.
    """
    word: str
    start: float
    end: float
    probability: float = 0.0
    timing_repaired: bool = False
    
    @property
    def duration(self) -> float:
        """Duration of the word in seconds."""
        return self.end - self.start
    
    def __str__(self) -> str:
        return f"Word('{self.word}', {self.start:.3f}-{self.end:.3f})"

def flatten_segments(segments: List[Any]) -> List[Word]:
    """
    Convert nested Whisper segments to a flat list of Word objects.
    
    This function extracts individual words from Whisper's hierarchical segment
    structure, creating a flat timeline of words with precise timing data.
    
    Args:
        segments: List of Whisper transcription segments, each containing
                 multiple words with timing information
                 
    Returns:
        List of Word objects in chronological order
        
    Example:
        >>> segments = [
        ...     Segment(words=[
        ...         {'word': 'Hello', 'start': 0.0, 'end': 0.5, 'probability': 0.95},
        ...         {'word': 'world', 'start': 0.6, 'end': 1.0, 'probability': 0.90}
        ...     ])
        ... ]
        >>> words = flatten_segments(segments)
        >>> len(words)
        2
        >>> words[0].word
        'Hello'
    """
    words = []
    
    for segment in segments:
        # Handle different segment formats
        if hasattr(segment, 'words') and segment.words:
            segment_words = segment.words
        elif isinstance(segment, dict) and 'words' in segment:
            segment_words = segment['words']
        else:
            # Fallback: create word from segment text
            if hasattr(segment, 'text'):
                words.append(Word(
                    word=segment.text.strip(),
                    start=getattr(segment, 'start', 0.0),
                    end=getattr(segment, 'end', 0.0),
                    probability=getattr(segment, 'avg_logprob', 0.0)
                ))
            continue
        
        # Process individual words within the segment
        for word_data in segment_words:
            if isinstance(word_data, dict):
                word_text = word_data.get('word', '').strip()
                word_start = word_data.get('start', 0.0)
                word_end = word_data.get('end', 0.0)
                word_prob = word_data.get('probability', 0.0)
            else:
                # Handle word objects
                word_text = getattr(word_data, 'word', '').strip()
                word_start = getattr(word_data, 'start', 0.0)
                word_end = getattr(word_data, 'end', 0.0)
                word_prob = getattr(word_data, 'probability', 0.0)
            
            # Skip empty words
            if word_text:
                words.append(Word(
                    word=word_text,
                    start=float(word_start),
                    end=float(word_end),
                    probability=float(word_prob)
                ))
    
    # Sort by start time to ensure chronological order
    words.sort(key=lambda w: w.start)
    
    logger.debug(f"Flattened {len(words)} words from {len(segments)} segments")
    return words

def calculate_word_gaps(words: List[Word]) -> List[float]:
    """
    Calculate inter-word gaps (pauses) between consecutive words.
    
    Word gap is defined as: gap_i = start_i - end_{i-1}
    This represents the true silence/pause between words.
    
    Args:
        words: List of Word objects in chronological order
        
    Returns:
        List of gap durations in seconds. Length is len(words) - 1.
        
    Example:
        >>> words = [
        ...     Word('Hello', 0.0, 0.5),
        ...     Word('world', 0.7, 1.2)
        ... ]
        >>> gaps = calculate_word_gaps(words)
        >>> gaps[0]
        0.2
    """
    if len(words) < 2:
        return []
    
    gaps = []
    for i in range(1, len(words)):
        gap = words[i].start - words[i-1].end
        # Ensure non-negative gaps (handle potential timing errors)
        gaps.append(max(0.0, gap))
    
    return gaps

def validate_word_timing(words: List[Word], timing_repair: bool = True) -> List[Word]:
    """
    Validate and clean word timing data.
    
    This function checks for timing inconsistencies and fixes common issues:
    - Ensures start < end for each word
    - Fixes overlapping words
    - Removes words with invalid timing
    
    Args:
        words: List of Word objects
        
    Returns:
        List of validated Word objects
    """
    if not words:
        return []
    
    valid_words = []
    
    for word in words:
        # Repair or skip words with invalid timing
        if word.start < 0 or word.end < 0:
            logger.warning(f"Skipping word with negative timing: {word}")
            continue
        if word.end <= word.start:
            # Repair with epsilon (20ms) matching Whisper frame stride
            if timing_repair:
                eps = 0.02
                word.end = word.start + eps
                word.timing_repaired = True
            else:
                logger.warning(f"Skipping zero-length word timing (repair disabled): {word}")
                continue
        else:
            word.timing_repaired = False

        valid_words.append(word)
    
    # Sort by start time
    valid_words.sort(key=lambda w: w.start)
    
    # Fix overlapping words
    fixed_words = []
    for i, word in enumerate(valid_words):
        if i > 0 and word.start < fixed_words[-1].end:
            # Adjust start time to avoid overlap
            word.start = fixed_words[-1].end + 0.001
            
        fixed_words.append(word)
    
    logger.debug(f"Validated {len(fixed_words)} words from {len(words)} input words")
    return fixed_words

def extract_text_from_words(words: List[Word]) -> str:
    """
    Extract clean text from a list of words.
    
    Args:
        words: List of Word objects
        
    Returns:
        Concatenated text with proper spacing
    """
    if not words:
        return ""
    
    return " ".join(word.word for word in words)
