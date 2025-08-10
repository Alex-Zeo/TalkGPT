"""
TalkGPT Smart Audio Chunking Module

Intelligent audio segmentation with silence detection and overlap handling
for optimal transcription accuracy and performance.
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import tempfile
import json

try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    import librosa
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

try:
    from ..utils.logger import get_logger, get_file_logger
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from utils.logger import get_logger, get_file_logger


@dataclass
class AudioChunk:
    """Audio chunk information container."""
    chunk_id: int
    start_time: float
    end_time: float
    duration: float
    file_path: Path
    original_start: float  # Start time in original file
    original_end: float    # End time in original file
    has_speech: bool = True
    confidence: float = 1.0
    overlap_prev: float = 0.0  # Overlap with previous chunk
    overlap_next: float = 0.0  # Overlap with next chunk


@dataclass
class ChunkingResult:
    """Chunking operation result."""
    original_file: Path
    chunks: List[AudioChunk]
    total_duration: float
    total_chunks: int
    processing_time: float
    silence_removed: float
    compression_ratio: float
    chunking_strategy: str


class SmartChunker:
    """
    Intelligent audio chunking system.
    
    Splits audio files into optimally-sized chunks at natural boundaries
    (silence points) with configurable overlap for seamless transcription.
    """
    
    def __init__(self, 
                 chunk_size: int = 30,
                 overlap_duration: int = 5,
                 silence_threshold: float = -40,
                 min_silence_len: int = 1000,
                 min_chunk_length: int = 5,
                 max_chunk_length: int = 300):
        """
        Initialize the smart chunker.
        
        Args:
            chunk_size: Target chunk size in seconds
            overlap_duration: Overlap between chunks in seconds
            silence_threshold: Silence detection threshold in dB
            min_silence_len: Minimum silence length in milliseconds
            min_chunk_length: Minimum chunk length in seconds
            max_chunk_length: Maximum chunk length in seconds
        """
        self.chunk_size = chunk_size
        self.overlap_duration = overlap_duration
        self.silence_threshold = silence_threshold
        self.min_silence_len = min_silence_len
        self.min_chunk_length = min_chunk_length
        self.max_chunk_length = max_chunk_length
        
        self.logger = get_logger("talkgpt.chunker")
        self.temp_dir = Path(tempfile.gettempdir()) / "talkgpt_chunks"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Check dependencies
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check for required audio processing libraries."""
        if not PYDUB_AVAILABLE:
            self.logger.warning("Pydub not available. Basic chunking only.")
        
        if not LIBROSA_AVAILABLE:
            self.logger.warning("Librosa not available. Advanced audio analysis disabled.")
        else:
            self.logger.info("Librosa available for advanced audio processing")
    
    def chunk_audio(self, 
                   audio_path: Union[str, Path],
                   output_dir: Optional[Union[str, Path]] = None,
                   remove_silence: bool = True) -> ChunkingResult:
        """
        Chunk audio file into segments with smart boundary detection.
        
        Args:
            audio_path: Path to input audio file
            output_dir: Output directory for chunks (temp dir if None)
            remove_silence: Whether to remove long silence segments
            
        Returns:
            ChunkingResult with chunking information
        """
        import time
        start_time = time.time()
        
        audio_path = Path(audio_path)
        if output_dir is None:
            output_dir = self.temp_dir / audio_path.stem
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_logger = get_file_logger(str(audio_path))
        file_logger.info(f"Starting smart chunking: {audio_path}")
        file_logger.info(f"Chunk size: {self.chunk_size}s, Overlap: {self.overlap_duration}s")
        
        try:
            # Load audio
            audio = self._load_audio(audio_path)
            original_duration = len(audio) / 1000.0  # Convert to seconds
            
            # Remove silence if requested
            silence_removed = 0.0
            if remove_silence:
                audio, silence_removed = self._remove_silence(audio)
            
            # Detect optimal split points
            split_points = self._find_split_points(audio)
            
            # Create chunks
            chunks = self._create_chunks(audio, split_points, audio_path, output_dir)
            
            processing_time = time.time() - start_time
            compression_ratio = (original_duration - silence_removed) / original_duration
            
            result = ChunkingResult(
                original_file=audio_path,
                chunks=chunks,
                total_duration=original_duration,
                total_chunks=len(chunks),
                processing_time=processing_time,
                silence_removed=silence_removed,
                compression_ratio=compression_ratio,
                chunking_strategy="silence_aware"
            )
            
            file_logger.info(f"Chunking completed: {len(chunks)} chunks in {processing_time:.2f}s")
            file_logger.info(f"Silence removed: {silence_removed:.1f}s ({(1-compression_ratio)*100:.1f}%)")
            
            # Save chunk metadata
            self._save_chunk_metadata(result, output_dir)
            
            return result
            
        except Exception as e:
            file_logger.error(f"Chunking failed: {e}")
            raise
    
    def _load_audio(self, audio_path: Path) -> AudioSegment:
        """Load audio file using pydub."""
        if not PYDUB_AVAILABLE:
            raise RuntimeError("Pydub required for audio loading")
        
        try:
            audio = AudioSegment.from_file(str(audio_path))
            self.logger.debug(f"Loaded audio: {len(audio)}ms, {audio.frame_rate}Hz, {audio.channels} channels")
            return audio
        except Exception as e:
            self.logger.error(f"Failed to load audio {audio_path}: {e}")
            raise
    
    def _remove_silence(self, audio: AudioSegment) -> Tuple[AudioSegment, float]:
        """
        Remove long silence segments from audio.
        
        Args:
            audio: Input audio segment
            
        Returns:
            Tuple of (processed_audio, silence_duration_removed)
        """
        if not PYDUB_AVAILABLE:
            return audio, 0.0
        
        original_length = len(audio)
        
        try:
            # Detect non-silent segments
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_len,
                silence_thresh=self.silence_threshold
            )
            
            if not nonsilent_ranges:
                self.logger.warning("No speech detected in audio")
                return audio, 0.0
            
            # Combine non-silent segments with small gaps
            processed_audio = AudioSegment.empty()
            
            for start_ms, end_ms in nonsilent_ranges:
                segment = audio[start_ms:end_ms]
                
                # Add small padding to avoid cutting words
                padding = min(100, start_ms, len(audio) - end_ms)  # 100ms padding
                if start_ms > padding:
                    segment = audio[start_ms - padding:end_ms + padding]
                
                processed_audio += segment
            
            silence_removed = (original_length - len(processed_audio)) / 1000.0
            
            self.logger.info(f"Silence removal: {original_length/1000:.1f}s -> {len(processed_audio)/1000:.1f}s")
            
            return processed_audio, silence_removed
            
        except Exception as e:
            self.logger.warning(f"Silence removal failed: {e}")
            return audio, 0.0
    
    def _find_split_points(self, audio: AudioSegment) -> List[float]:
        """
        Find optimal split points in audio based on silence detection.
        
        Args:
            audio: Audio segment to analyze
            
        Returns:
            List of split points in seconds
        """
        if not PYDUB_AVAILABLE:
            # Fallback to time-based splitting
            return self._time_based_split_points(len(audio) / 1000.0)
        
        audio_length_s = len(audio) / 1000.0
        target_chunk_ms = self.chunk_size * 1000
        
        # If audio is shorter than chunk size, no splitting needed
        if audio_length_s <= self.chunk_size:
            return [0.0, audio_length_s]
        
        split_points = [0.0]  # Always start at beginning
        
        try:
            # Detect silence segments
            silent_ranges = []
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_len // 2,  # More sensitive for split detection
                silence_thresh=self.silence_threshold
            )
            
            # Convert non-silent ranges to silent ranges
            if nonsilent_ranges:
                for i in range(len(nonsilent_ranges) - 1):
                    silent_start = nonsilent_ranges[i][1]
                    silent_end = nonsilent_ranges[i + 1][0]
                    if silent_end - silent_start >= self.min_silence_len // 2:
                        silent_ranges.append((silent_start, silent_end))
            
            # Find split points
            current_pos = 0
            
            while current_pos < len(audio):
                target_end = current_pos + target_chunk_ms
                
                # If we're near the end, just use the end
                if target_end >= len(audio) - (self.min_chunk_length * 1000):
                    split_points.append(audio_length_s)
                    break
                
                # Find the best silence point near the target
                best_split = None
                search_start = max(current_pos + (self.min_chunk_length * 1000), 
                                 target_end - (5 * 1000))  # Search 5s before target
                search_end = min(target_end + (5 * 1000), len(audio))  # Search 5s after target
                
                # Look for silence in the search window
                for silent_start, silent_end in silent_ranges:
                    if search_start <= silent_start <= search_end:
                        # Use middle of silence as split point
                        split_point = (silent_start + silent_end) / 2
                        if best_split is None or abs(split_point - target_end) < abs(best_split - target_end):
                            best_split = split_point
                
                # If no silence found, use target position
                if best_split is None:
                    best_split = target_end
                
                split_points.append(best_split / 1000.0)  # Convert to seconds
                current_pos = int(best_split - (self.overlap_duration * 1000))  # Account for overlap
            
            # Ensure we end at the actual end
            if split_points[-1] < audio_length_s:
                split_points.append(audio_length_s)
            
            self.logger.debug(f"Found {len(split_points)-1} split points: {split_points}")
            
            return split_points
            
        except Exception as e:
            self.logger.warning(f"Smart split detection failed: {e}. Using time-based splitting.")
            return self._time_based_split_points(audio_length_s)
    
    def _time_based_split_points(self, duration_s: float) -> List[float]:
        """Fallback time-based splitting."""
        split_points = []
        current = 0.0
        
        while current < duration_s:
            split_points.append(current)
            current += self.chunk_size - self.overlap_duration
        
        split_points.append(duration_s)
        return split_points
    
    def _create_chunks(self, 
                      audio: AudioSegment, 
                      split_points: List[float],
                      original_path: Path,
                      output_dir: Path) -> List[AudioChunk]:
        """
        Create audio chunks from split points.
        
        Args:
            audio: Audio segment
            split_points: List of split points in seconds
            original_path: Original file path
            output_dir: Output directory for chunk files
            
        Returns:
            List of AudioChunk objects
        """
        chunks = []
        
        for i in range(len(split_points) - 1):
            start_time = split_points[i]
            end_time = split_points[i + 1]
            
            # Add overlap
            overlap_start = max(0, start_time - self.overlap_duration)
            overlap_end = min(len(audio) / 1000.0, end_time + self.overlap_duration)
            
            # Extract audio segment
            start_ms = int(overlap_start * 1000)
            end_ms = int(overlap_end * 1000)
            chunk_audio = audio[start_ms:end_ms]
            
            # Skip very short chunks
            if len(chunk_audio) < self.min_chunk_length * 1000:
                continue
            
            # Save chunk to file
            chunk_filename = f"chunk_{i:03d}_{start_time:.1f}s-{end_time:.1f}s.wav"
            chunk_path = output_dir / chunk_filename
            
            chunk_audio.export(str(chunk_path), format="wav")
            
            # Calculate overlaps
            overlap_prev = start_time - overlap_start if i > 0 else 0.0
            overlap_next = overlap_end - end_time if i < len(split_points) - 2 else 0.0
            
            # Create chunk object
            chunk = AudioChunk(
                chunk_id=i,
                start_time=overlap_start,
                end_time=overlap_end,
                duration=overlap_end - overlap_start,
                file_path=chunk_path,
                original_start=start_time,
                original_end=end_time,
                has_speech=True,  # Assume all chunks have speech after silence removal
                confidence=1.0,
                overlap_prev=overlap_prev,
                overlap_next=overlap_next
            )
            
            chunks.append(chunk)
        
        self.logger.info(f"Created {len(chunks)} audio chunks")
        return chunks
    
    def _save_chunk_metadata(self, result: ChunkingResult, output_dir: Path):
        """Save chunk metadata to JSON file."""
        metadata = {
            'original_file': str(result.original_file),
            'total_duration': result.total_duration,
            'total_chunks': result.total_chunks,
            'processing_time': result.processing_time,
            'silence_removed': result.silence_removed,
            'compression_ratio': result.compression_ratio,
            'chunking_strategy': result.chunking_strategy,
            'chunking_config': {
                'chunk_size': self.chunk_size,
                'overlap_duration': self.overlap_duration,
                'silence_threshold': self.silence_threshold,
                'min_silence_len': self.min_silence_len
            },
            'chunks': [
                {
                    'chunk_id': chunk.chunk_id,
                    'start_time': chunk.start_time,
                    'end_time': chunk.end_time,
                    'duration': chunk.duration,
                    'file_path': str(chunk.file_path),
                    'original_start': chunk.original_start,
                    'original_end': chunk.original_end,
                    'overlap_prev': chunk.overlap_prev,
                    'overlap_next': chunk.overlap_next
                }
                for chunk in result.chunks
            ]
        }
        
        metadata_file = output_dir / "chunks_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.debug(f"Saved chunk metadata: {metadata_file}")
    
    def load_chunks_from_metadata(self, metadata_file: Union[str, Path]) -> ChunkingResult:
        """
        Load chunking result from metadata file.
        
        Args:
            metadata_file: Path to metadata JSON file
            
        Returns:
            ChunkingResult object
        """
        metadata_file = Path(metadata_file)
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Reconstruct chunks
        chunks = []
        for chunk_data in metadata['chunks']:
            chunk = AudioChunk(
                chunk_id=chunk_data['chunk_id'],
                start_time=chunk_data['start_time'],
                end_time=chunk_data['end_time'],
                duration=chunk_data['duration'],
                file_path=Path(chunk_data['file_path']),
                original_start=chunk_data['original_start'],
                original_end=chunk_data['original_end'],
                overlap_prev=chunk_data['overlap_prev'],
                overlap_next=chunk_data['overlap_next']
            )
            chunks.append(chunk)
        
        # Reconstruct result
        result = ChunkingResult(
            original_file=Path(metadata['original_file']),
            chunks=chunks,
            total_duration=metadata['total_duration'],
            total_chunks=metadata['total_chunks'],
            processing_time=metadata['processing_time'],
            silence_removed=metadata['silence_removed'],
            compression_ratio=metadata['compression_ratio'],
            chunking_strategy=metadata['chunking_strategy']
        )
        
        return result
    
    def get_chunking_stats(self, result: ChunkingResult) -> Dict[str, Any]:
        """
        Get statistics from chunking result.
        
        Args:
            result: ChunkingResult to analyze
            
        Returns:
            Statistics dictionary
        """
        if not result.chunks:
            return {}
        
        chunk_durations = [chunk.duration for chunk in result.chunks]
        
        stats = {
            'total_chunks': result.total_chunks,
            'total_duration': result.total_duration,
            'average_chunk_duration': np.mean(chunk_durations),
            'min_chunk_duration': np.min(chunk_durations),
            'max_chunk_duration': np.max(chunk_durations),
            'std_chunk_duration': np.std(chunk_durations),
            'silence_removed': result.silence_removed,
            'compression_ratio': result.compression_ratio,
            'processing_time': result.processing_time,
            'chunks_per_minute': result.total_chunks / (result.total_duration / 60),
            'overlap_efficiency': self._calculate_overlap_efficiency(result.chunks)
        }
        
        return stats
    
    def _calculate_overlap_efficiency(self, chunks: List[AudioChunk]) -> float:
        """Calculate overlap efficiency (how well overlaps are distributed)."""
        if len(chunks) < 2:
            return 1.0
        
        overlaps = []
        for chunk in chunks:
            if chunk.overlap_prev > 0:
                overlaps.append(chunk.overlap_prev)
            if chunk.overlap_next > 0:
                overlaps.append(chunk.overlap_next)
        
        if not overlaps:
            return 0.0
        
        target_overlap = self.overlap_duration
        efficiency = 1.0 - (np.std(overlaps) / target_overlap)
        return max(0.0, min(1.0, efficiency))
    
    def cleanup_chunks(self, result: ChunkingResult):
        """Clean up chunk files."""
        for chunk in result.chunks:
            try:
                if chunk.file_path.exists():
                    chunk.file_path.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to cleanup chunk {chunk.file_path}: {e}")
        
        # Remove chunk directory if empty
        chunk_dir = result.chunks[0].file_path.parent if result.chunks else None
        if chunk_dir and chunk_dir.exists():
            try:
                chunk_dir.rmdir()
            except OSError:
                pass  # Directory not empty


# Global chunker instance
_smart_chunker: Optional[SmartChunker] = None


def get_smart_chunker(**kwargs) -> SmartChunker:
    """Get the global smart chunker instance."""
    global _smart_chunker
    if _smart_chunker is None:
        _smart_chunker = SmartChunker(**kwargs)
    return _smart_chunker


def chunk_audio(audio_path: Union[str, Path], **kwargs) -> ChunkingResult:
    """Chunk audio using the global chunker."""
    return get_smart_chunker().chunk_audio(audio_path, **kwargs)