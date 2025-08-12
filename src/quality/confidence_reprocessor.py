#!/usr/bin/env python3
"""
Confidence-Based Segment Reprocessor

Analyzes transcription confidence scores and reprocesses low-confidence segments
at 0.7x speed with additional context for improved accuracy.
"""

import asyncio
import os
import json
import numpy as np
import librosa
import soundfile as sf
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from pathlib import Path
import tempfile

from faster_whisper import WhisperModel
from utils.logger import get_logger


@dataclass
class SegmentConfidence:
    """Represents a segment with its confidence metrics"""
    segment_id: str
    start_time: float
    end_time: float
    text: str
    avg_logprob: float  # Average log probability (confidence score)
    no_speech_prob: float
    word_count: int
    needs_reprocessing: bool = False
    reprocessed: bool = False
    original_confidence: float = field(init=False)
    
    def __post_init__(self):
        self.original_confidence = self.avg_logprob


@dataclass 
class ReprocessingContext:
    """Context for reprocessing a segment with surrounding audio"""
    target_segment: SegmentConfidence
    previous_segment: Optional[SegmentConfidence]
    next_segment: Optional[SegmentConfidence]
    expanded_start_time: float
    expanded_end_time: float
    overlap_before: float = 0.0
    overlap_after: float = 0.0


class ConfidenceReprocessor:
    """Handles confidence-based reprocessing of low-quality segments"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.model = None
        
        # Reprocessing parameters
        self.slow_speed_multiplier = 0.7  # Slower for better accuracy
        self.normal_speed_multiplier = 1.75  # Normal fast processing
        self.confidence_threshold = -0.5  # Segments below this get reprocessed
        self.max_reprocess_segments = 10  # Maximum segments to reprocess
        self.context_padding = 2.0  # Seconds of padding on each side
        
        # Audio processing
        self.sample_rate = 16000
        
        self.logger.info(f"🔍 Confidence reprocessor initialized - Threshold: {self.confidence_threshold}, Max segments: {self.max_reprocess_segments}")
    
    async def analyze_and_reprocess(self, 
                                  segments: List[Dict], 
                                  audio_file_path: str,
                                  output_dir: Path) -> List[Dict]:
        """
        Main entry point: analyze confidence and reprocess low-quality segments
        
        Args:
            segments: List of transcribed segments with confidence scores
            audio_file_path: Path to original audio file
            output_dir: Directory for temporary files
            
        Returns:
            Updated segments list with reprocessed segments
        """
        self.logger.info(f"🔍 Analyzing confidence for {len(segments)} segments...")
        
        # Convert to SegmentConfidence objects
        segment_objects = self._convert_to_segment_objects(segments)
        
        # Identify low-confidence segments
        low_confidence_segments = self._identify_low_confidence_segments(segment_objects)
        
        if not low_confidence_segments:
            self.logger.info("✅ All segments have acceptable confidence - no reprocessing needed")
            return segments
        
        self.logger.info(f"🔄 Found {len(low_confidence_segments)} segments requiring reprocessing")
        
        # Load model for reprocessing
        await self._load_model()
        
        # Reprocess low-confidence segments
        reprocessed_segments = await self._reprocess_segments(
            low_confidence_segments, 
            segment_objects,
            audio_file_path, 
            output_dir
        )
        
        # Merge reprocessed segments back into main list
        final_segments = self._merge_reprocessed_segments(segment_objects, reprocessed_segments)
        
        # Convert back to dict format
        return self._convert_to_dict_format(final_segments)
    
    def _convert_to_segment_objects(self, segments: List[Dict]) -> List[SegmentConfidence]:
        """Convert dict segments to SegmentConfidence objects"""
        segment_objects = []
        
        for i, segment in enumerate(segments):
            seg_obj = SegmentConfidence(
                segment_id=f"seg_{i:04d}",
                start_time=segment.get('start', 0.0),
                end_time=segment.get('end', 0.0),
                text=segment.get('text', ''),
                avg_logprob=segment.get('avg_logprob', 0.0),
                no_speech_prob=segment.get('no_speech_prob', 0.0),
                word_count=len(segment.get('text', '').split())
            )
            segment_objects.append(seg_obj)
            
        return segment_objects
    
    def _identify_low_confidence_segments(self, segments: List[SegmentConfidence]) -> List[SegmentConfidence]:
        """Identify segments that need reprocessing based on confidence scores"""
        
        # Sort by confidence (lowest first)
        sorted_segments = sorted(segments, key=lambda s: s.avg_logprob)
        
        # Apply threshold filter
        low_confidence = [s for s in sorted_segments if s.avg_logprob < self.confidence_threshold]
        
        # Limit to maximum number
        candidates = low_confidence[:self.max_reprocess_segments]
        
        # Additional filtering: skip very short segments or high no_speech_prob
        filtered_candidates = []
        for segment in candidates:
            # Skip if too short (less than 1 second)
            if segment.end_time - segment.start_time < 1.0:
                continue
                
            # Skip if very likely to be non-speech
            if segment.no_speech_prob > 0.8:
                continue
                
            # Skip if no actual words
            if segment.word_count < 2:
                continue
                
            segment.needs_reprocessing = True
            filtered_candidates.append(segment)
        
        self.logger.info(f"📊 Confidence analysis:")
        self.logger.info(f"   - Total segments: {len(segments)}")
        self.logger.info(f"   - Below threshold ({self.confidence_threshold}): {len(low_confidence)}")
        self.logger.info(f"   - Selected for reprocessing: {len(filtered_candidates)}")
        
        for segment in filtered_candidates:
            self.logger.info(f"   - {segment.segment_id}: {segment.avg_logprob:.3f} confidence, \"{segment.text[:50]}...\"")
        
        return filtered_candidates
    
    async def _load_model(self):
        """Load Whisper model for reprocessing"""
        if self.model is None:
            self.logger.info("📦 Loading Whisper model for reprocessing...")
            device = "cuda" if os.system("nvidia-smi") == 0 else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            
            self.model = WhisperModel(
                "large-v3",
                device=device,
                compute_type=compute_type
            )
            self.logger.info(f"✅ Model loaded on {device}")
    
    async def _reprocess_segments(self, 
                                low_confidence_segments: List[SegmentConfidence],
                                all_segments: List[SegmentConfidence], 
                                audio_file_path: str,
                                output_dir: Path) -> Dict[str, SegmentConfidence]:
        """Reprocess low-confidence segments with expanded context"""
        
        reprocessed = {}
        
        # Load original audio
        self.logger.info("🎵 Loading original audio file...")
        audio_data, sr = librosa.load(audio_file_path, sr=self.sample_rate)
        
        for segment in low_confidence_segments:
            self.logger.info(f"🔄 Reprocessing {segment.segment_id} with expanded context...")
            
            try:
                # Create reprocessing context with surrounding segments
                context = self._create_reprocessing_context(segment, all_segments)
                
                # Extract expanded audio segment
                expanded_audio = self._extract_expanded_audio_segment(audio_data, context)
                
                # Reprocess at 0.7x speed with better parameters
                reprocessed_segment = await self._reprocess_audio_segment(
                    expanded_audio, context, output_dir
                )
                
                if reprocessed_segment:
                    reprocessed[segment.segment_id] = reprocessed_segment
                    self.logger.info(f"✅ {segment.segment_id} reprocessed: {segment.avg_logprob:.3f} → {reprocessed_segment.avg_logprob:.3f}")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to reprocess {segment.segment_id}: {e}")
                continue
        
        return reprocessed
    
    def _create_reprocessing_context(self, 
                                   target_segment: SegmentConfidence,
                                   all_segments: List[SegmentConfidence]) -> ReprocessingContext:
        """Create context with previous and next segments for reprocessing"""
        
        # Find target segment index
        target_index = None
        for i, seg in enumerate(all_segments):
            if seg.segment_id == target_segment.segment_id:
                target_index = i
                break
        
        if target_index is None:
            raise ValueError(f"Target segment {target_segment.segment_id} not found")
        
        # Get surrounding segments
        previous_segment = all_segments[target_index - 1] if target_index > 0 else None
        next_segment = all_segments[target_index + 1] if target_index < len(all_segments) - 1 else None
        
        # Calculate expanded time range
        expanded_start = target_segment.start_time - self.context_padding
        expanded_end = target_segment.end_time + self.context_padding
        
        # Include previous segment if available
        if previous_segment:
            expanded_start = min(expanded_start, previous_segment.start_time)
            
        # Include next segment if available  
        if next_segment:
            expanded_end = max(expanded_end, next_segment.end_time)
        
        # Ensure we don't go negative
        expanded_start = max(0, expanded_start)
        
        # Calculate overlaps for trimming later
        overlap_before = target_segment.start_time - expanded_start
        overlap_after = expanded_end - target_segment.end_time
        
        return ReprocessingContext(
            target_segment=target_segment,
            previous_segment=previous_segment,
            next_segment=next_segment,
            expanded_start_time=expanded_start,
            expanded_end_time=expanded_end,
            overlap_before=overlap_before,
            overlap_after=overlap_after
        )
    
    def _extract_expanded_audio_segment(self, 
                                      audio_data: np.ndarray, 
                                      context: ReprocessingContext) -> np.ndarray:
        """Extract expanded audio segment for reprocessing"""
        
        start_sample = int(context.expanded_start_time * self.sample_rate)
        end_sample = int(context.expanded_end_time * self.sample_rate)
        
        # Ensure we don't exceed audio bounds
        start_sample = max(0, start_sample)
        end_sample = min(len(audio_data), end_sample)
        
        # Extract segment
        audio_segment = audio_data[start_sample:end_sample]
        
        # Apply 0.7x speed reduction for better accuracy
        audio_segment_slow = librosa.effects.time_stretch(audio_segment, rate=self.slow_speed_multiplier)
        
        return audio_segment_slow
    
    async def _reprocess_audio_segment(self, 
                                     audio_segment: np.ndarray,
                                     context: ReprocessingContext,
                                     output_dir: Path) -> Optional[SegmentConfidence]:
        """Reprocess audio segment with enhanced parameters"""
        
        # Save audio to temporary file
        temp_file = output_dir / f"reprocess_{context.target_segment.segment_id}.wav"
        sf.write(temp_file, audio_segment, self.sample_rate)
        
        try:
            # Transcribe with enhanced settings for accuracy
            segments, info = self.model.transcribe(
                str(temp_file),
                beam_size=10,  # Increased beam size for better accuracy
                temperature=0.0,  # Deterministic output
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=100,  # More sensitive to speech
                    speech_pad_ms=200  # More padding around speech
                ),
                condition_on_previous_text=True,  # Use context
                compression_ratio_threshold=2.4,  # More strict
                logprob_threshold=-1.0,  # Accept lower confidence during reprocessing
                no_speech_threshold=0.6  # Be more permissive of speech
            )
            
            # Process results
            segment_list = list(segments)
            if not segment_list:
                return None
            
            # Find the segment that corresponds to our target (middle portion)
            target_segment_result = self._find_target_segment_in_results(
                segment_list, context, audio_segment
            )
            
            if target_segment_result:
                # Adjust timestamps back to original timescale and position
                adjusted_segment = self._adjust_timestamps_to_original(
                    target_segment_result, context
                )
                
                return adjusted_segment
            
        except Exception as e:
            self.logger.error(f"❌ Transcription failed during reprocessing: {e}")
            return None
        finally:
            # Clean up temporary file
            if temp_file.exists():
                temp_file.unlink()
        
        return None
    
    def _find_target_segment_in_results(self, 
                                      reprocessed_segments: List,
                                      context: ReprocessingContext,
                                      audio_segment: np.ndarray) -> Optional[Dict]:
        """Find the segment that corresponds to our target segment"""
        
        if not reprocessed_segments:
            return None
        
        # Calculate target position in the slowed-down audio
        target_start_in_slow_audio = context.overlap_before / self.slow_speed_multiplier
        target_end_in_slow_audio = (context.overlap_before + 
                                  (context.target_segment.end_time - context.target_segment.start_time)) / self.slow_speed_multiplier
        
        # Find segment that best overlaps with our target region
        best_segment = None
        best_overlap = 0
        
        for segment in reprocessed_segments:
            # Calculate overlap with target region
            overlap_start = max(segment.start, target_start_in_slow_audio)
            overlap_end = min(segment.end, target_end_in_slow_audio)
            overlap_duration = max(0, overlap_end - overlap_start)
            
            if overlap_duration > best_overlap:
                best_overlap = overlap_duration
                best_segment = segment
        
        if best_segment and best_overlap > 0.5:  # Require at least 0.5 second overlap
            return {
                'start': best_segment.start,
                'end': best_segment.end,
                'text': best_segment.text,
                'avg_logprob': getattr(best_segment, 'avg_logprob', 0.0),
                'no_speech_prob': getattr(best_segment, 'no_speech_prob', 0.0),
                'words': getattr(best_segment, 'words', [])
            }
        
        return None
    
    def _adjust_timestamps_to_original(self, 
                                     reprocessed_segment: Dict,
                                     context: ReprocessingContext) -> SegmentConfidence:
        """Adjust timestamps from reprocessed segment back to original timeline"""
        
        # Convert from slow timeline back to original timeline
        # The reprocessed audio was at 0.7x speed, so we need to scale up
        slow_start = reprocessed_segment['start']
        slow_end = reprocessed_segment['end']
        
        # Scale back to normal speed
        normal_start = slow_start * self.slow_speed_multiplier
        normal_end = slow_end * self.slow_speed_multiplier
        
        # Adjust to absolute timeline position
        absolute_start = context.expanded_start_time + normal_start
        absolute_end = context.expanded_start_time + normal_end
        
        # Ensure we stay within the original segment bounds (with some tolerance)
        original_start = context.target_segment.start_time
        original_end = context.target_segment.end_time
        tolerance = 1.0  # Allow 1 second variation
        
        final_start = max(original_start - tolerance, min(original_start + tolerance, absolute_start))
        final_end = max(original_end - tolerance, min(original_end + tolerance, absolute_end))
        
        return SegmentConfidence(
            segment_id=context.target_segment.segment_id,
            start_time=final_start,
            end_time=final_end,
            text=reprocessed_segment['text'],
            avg_logprob=reprocessed_segment['avg_logprob'],
            no_speech_prob=reprocessed_segment['no_speech_prob'],
            word_count=len(reprocessed_segment['text'].split()),
            reprocessed=True
        )
    
    def _merge_reprocessed_segments(self, 
                                  original_segments: List[SegmentConfidence],
                                  reprocessed_segments: Dict[str, SegmentConfidence]) -> List[SegmentConfidence]:
        """Merge reprocessed segments back into the main list"""
        
        merged_segments = []
        
        for segment in original_segments:
            if segment.segment_id in reprocessed_segments:
                # Use reprocessed version
                reprocessed = reprocessed_segments[segment.segment_id]
                self.logger.info(f"🔄 Replaced {segment.segment_id}: \"{segment.text[:30]}...\" → \"{reprocessed.text[:30]}...\"")
                merged_segments.append(reprocessed)
            else:
                # Keep original
                merged_segments.append(segment)
        
        return merged_segments
    
    def _convert_to_dict_format(self, segments: List[SegmentConfidence]) -> List[Dict]:
        """Convert SegmentConfidence objects back to dict format"""
        
        result = []
        for segment in segments:
            segment_dict = {
                'start': segment.start_time,
                'end': segment.end_time,
                'text': segment.text,
                'avg_logprob': segment.avg_logprob,
                'no_speech_prob': segment.no_speech_prob,
                'reprocessed': segment.reprocessed,
                'original_confidence': segment.original_confidence if segment.reprocessed else segment.avg_logprob
            }
            result.append(segment_dict)
        
        return result
    
    def generate_reprocessing_report(self, 
                                   original_segments: List[Dict],
                                   final_segments: List[Dict]) -> Dict[str, Any]:
        """Generate a report on the reprocessing results"""
        
        reprocessed_count = sum(1 for seg in final_segments if seg.get('reprocessed', False))
        
        # Calculate confidence improvements
        improvements = []
        for orig, final in zip(original_segments, final_segments):
            if final.get('reprocessed', False):
                improvement = final['avg_logprob'] - orig['avg_logprob']
                improvements.append(improvement)
        
        report = {
            'total_segments': len(final_segments),
            'reprocessed_segments': reprocessed_count,
            'reprocessing_rate': reprocessed_count / len(final_segments) if final_segments else 0,
            'average_confidence_improvement': np.mean(improvements) if improvements else 0,
            'max_confidence_improvement': max(improvements) if improvements else 0,
            'confidence_threshold_used': self.confidence_threshold,
            'slow_speed_multiplier': self.slow_speed_multiplier,
            'context_padding_seconds': self.context_padding
        }
        
        return report


async def reprocess_low_confidence_segments(segments: List[Dict], 
                                          audio_file_path: str,
                                          output_dir: Path) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Convenience function to reprocess low-confidence segments
    
    Args:
        segments: Original transcribed segments
        audio_file_path: Path to original audio file
        output_dir: Directory for temporary files
        
    Returns:
        Tuple of (improved_segments, reprocessing_report)
    """
    reprocessor = ConfidenceReprocessor()
    
    improved_segments = await reprocessor.analyze_and_reprocess(
        segments, audio_file_path, output_dir
    )
    
    report = reprocessor.generate_reprocessing_report(segments, improved_segments)
    
    return improved_segments, report