"""
TalkGPT File Processing Module

Handles audio/video file discovery, format conversion, and preprocessing
including speed optimization and volume normalization.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import shutil

try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

try:
    from pydub import AudioSegment
    from pydub.utils import which
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    from ..utils.logger import get_logger, get_file_logger
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from utils.logger import get_logger, get_file_logger


@dataclass
class AudioFileInfo:
    """Audio file information container."""
    path: Path
    duration: float
    sample_rate: int
    channels: int
    format: str
    size_bytes: int
    bitrate: Optional[int] = None


@dataclass
class ProcessingResult:
    """File processing result container."""
    original_path: Path
    processed_path: Path
    processing_time: float
    original_info: AudioFileInfo
    processed_info: AudioFileInfo
    applied_operations: List[str]


class FileProcessor:
    """
    Audio and video file processing system.
    
    Handles file discovery, format conversion, speed optimization,
    and audio preprocessing for optimal transcription performance.
    """
    
    # Supported audio and video formats
    AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma', '.aiff'}
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    
    def __init__(self, temp_dir: Optional[Path] = None):
        """
        Initialize the file processor.
        
        Args:
            temp_dir: Temporary directory for processing files
        """
        self.logger = get_logger("talkgpt.fileprocessor")
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "talkgpt"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Check dependencies
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check for required dependencies."""
        # Check for FFmpeg
        ffmpeg_path = which("ffmpeg")
        if not ffmpeg_path and not FFMPEG_AVAILABLE:
            self.logger.warning("FFmpeg not found. Audio conversion capabilities limited.")
        else:
            self.logger.info(f"FFmpeg available at: {ffmpeg_path}")
        
        if not PYDUB_AVAILABLE:
            self.logger.warning("Pydub not available. Some audio processing features disabled.")
    
    def scan_directory(self, 
                      directory: Union[str, Path], 
                      recursive: bool = True,
                      extensions: Optional[List[str]] = None) -> List[Path]:
        """
        Scan directory for audio and video files.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            extensions: Custom file extensions to look for
            
        Returns:
            List of found audio/video file paths
        """
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if extensions is None:
            extensions = self.AUDIO_EXTENSIONS | self.VIDEO_EXTENSIONS
        else:
            extensions = {ext.lower() for ext in extensions}
        
        files = []
        scan_pattern = "**/*" if recursive else "*"
        
        self.logger.info(f"Scanning directory: {directory} (recursive={recursive})")
        
        for file_path in directory.glob(scan_pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                files.append(file_path)
        
        self.logger.info(f"Found {len(files)} files to process")
        return sorted(files)
    
    def get_file_info(self, file_path: Union[str, Path]) -> AudioFileInfo:
        """
        Get detailed information about an audio/video file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            AudioFileInfo object with file details
        """
        file_path = Path(file_path)
        
        try:
            # Use ffprobe to get file information
            probe = ffmpeg.probe(str(file_path))
            
            # Find audio stream
            audio_stream = None
            for stream in probe['streams']:
                if stream['codec_type'] == 'audio':
                    audio_stream = stream
                    break
            
            if not audio_stream:
                raise ValueError("No audio stream found in file")
            
            # Extract information
            duration = float(probe['format']['duration'])
            sample_rate = int(audio_stream['sample_rate'])
            channels = int(audio_stream['channels'])
            format_name = probe['format']['format_name']
            size_bytes = int(probe['format']['size'])
            
            # Try to get bitrate
            bitrate = None
            if 'bit_rate' in probe['format']:
                bitrate = int(probe['format']['bit_rate'])
            elif 'bit_rate' in audio_stream:
                bitrate = int(audio_stream['bit_rate'])
            
            return AudioFileInfo(
                path=file_path,
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                format=format_name,
                size_bytes=size_bytes,
                bitrate=bitrate
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get file info for {file_path}: {e}")
            raise
    
    def convert_to_wav(self, 
                      input_path: Union[str, Path], 
                      output_path: Optional[Union[str, Path]] = None,
                      sample_rate: int = 16000,
                      channels: int = 1,
                      normalize: bool = True) -> Path:
        """
        Convert audio/video file to WAV format.
        
        Args:
            input_path: Input file path
            output_path: Output file path (auto-generated if None)
            sample_rate: Target sample rate
            channels: Number of audio channels (1=mono, 2=stereo)
            normalize: Whether to normalize audio volume
            
        Returns:
            Path to converted WAV file
        """
        input_path = Path(input_path)
        
        if output_path is None:
            output_path = self.temp_dir / f"{input_path.stem}_converted.wav"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_logger = get_file_logger(str(input_path))
        file_logger.info(f"Converting to WAV: {input_path} -> {output_path}")
        
        try:
            # Build ffmpeg command
            input_stream = ffmpeg.input(str(input_path))
            
            # Audio processing options
            audio_options = {
                'acodec': 'pcm_s16le',  # 16-bit PCM
                'ar': sample_rate,      # Sample rate
                'ac': channels,         # Channel count
            }
            
            # Add normalization if requested
            if normalize:
                # Apply audio normalization filter
                input_stream = input_stream.audio.filter('loudnorm')
            
            # Output stream
            output_stream = ffmpeg.output(input_stream, str(output_path), **audio_options)
            
            # Run conversion
            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)
            
            file_logger.info(f"Conversion completed: {output_path}")
            return output_path
            
        except Exception as e:
            file_logger.error(f"Conversion failed: {e}")
            raise
    
    def apply_speed_multiplier(self, 
                             input_path: Union[str, Path], 
                             speed_multiplier: float = 1.75,
                             output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Apply speed multiplier to audio without changing pitch.
        
        Args:
            input_path: Input audio file path
            speed_multiplier: Speed multiplier (1.0 = normal, 2.0 = 2x speed)
            output_path: Output file path (auto-generated if None)
            
        Returns:
            Path to speed-adjusted audio file
        """
        input_path = Path(input_path)
        
        if output_path is None:
            output_path = self.temp_dir / f"{input_path.stem}_speed_{speed_multiplier:.1f}x.wav"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_logger = get_file_logger(str(input_path))
        file_logger.info(f"Applying speed multiplier {speed_multiplier}x: {input_path}")
        
        try:
            # Use atempo filter for speed adjustment without pitch change
            input_stream = ffmpeg.input(str(input_path))
            
            # atempo filter has limitations (0.5-100.0), so we may need to chain filters
            if speed_multiplier <= 2.0:
                # Single atempo filter
                audio_stream = input_stream.audio.filter('atempo', speed_multiplier)
            else:
                # Chain multiple atempo filters for higher speeds
                audio_stream = input_stream.audio
                remaining_speed = speed_multiplier
                
                while remaining_speed > 2.0:
                    audio_stream = audio_stream.filter('atempo', 2.0)
                    remaining_speed /= 2.0
                
                if remaining_speed > 1.0:
                    audio_stream = audio_stream.filter('atempo', remaining_speed)
            
            # Output
            output_stream = ffmpeg.output(audio_stream, str(output_path))
            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)
            
            file_logger.info(f"Speed adjustment completed: {output_path}")
            return output_path
            
        except Exception as e:
            file_logger.error(f"Speed adjustment failed: {e}")
            raise
    
    def remove_silence(self, 
                      input_path: Union[str, Path],
                      silence_threshold: float = -40,
                      min_silence_duration: float = 1.0,
                      output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Remove long silence segments from audio.
        
        Args:
            input_path: Input audio file path
            silence_threshold: Silence threshold in dB
            min_silence_duration: Minimum silence duration to remove (seconds)
            output_path: Output file path (auto-generated if None)
            
        Returns:
            Path to silence-removed audio file
        """
        input_path = Path(input_path)
        
        if output_path is None:
            output_path = self.temp_dir / f"{input_path.stem}_no_silence.wav"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_logger = get_file_logger(str(input_path))
        file_logger.info(f"Removing silence: threshold={silence_threshold}dB, min_duration={min_silence_duration}s")
        
        try:
            # Use silenceremove filter
            input_stream = ffmpeg.input(str(input_path))
            
            # Configure silence removal
            # start_periods=1: remove silence at the beginning
            # start_duration: minimum silence duration to trigger removal
            # start_threshold: silence threshold
            # stop_periods=1: remove silence at the end
            audio_stream = input_stream.audio.filter(
                'silenceremove',
                start_periods=1,
                start_duration=min_silence_duration,
                start_threshold=f'{silence_threshold}dB',
                stop_periods=-1,
                stop_duration=min_silence_duration,
                stop_threshold=f'{silence_threshold}dB'
            )
            
            # Output
            output_stream = ffmpeg.output(audio_stream, str(output_path))
            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)
            
            file_logger.info(f"Silence removal completed: {output_path}")
            return output_path
            
        except Exception as e:
            file_logger.error(f"Silence removal failed: {e}")
            raise
    
    def normalize_volume(self, 
                        input_path: Union[str, Path],
                        target_lufs: float = -23.0,
                        output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Normalize audio volume using loudness normalization.
        
        Args:
            input_path: Input audio file path
            target_lufs: Target loudness in LUFS
            output_path: Output file path (auto-generated if None)
            
        Returns:
            Path to normalized audio file
        """
        input_path = Path(input_path)
        
        if output_path is None:
            output_path = self.temp_dir / f"{input_path.stem}_normalized.wav"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_logger = get_file_logger(str(input_path))
        file_logger.info(f"Normalizing volume: target={target_lufs} LUFS")
        
        try:
            # Use loudnorm filter for EBU R128 loudness normalization
            input_stream = ffmpeg.input(str(input_path))
            audio_stream = input_stream.audio.filter('loudnorm', I=target_lufs)
            
            output_stream = ffmpeg.output(audio_stream, str(output_path))
            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)
            
            file_logger.info(f"Volume normalization completed: {output_path}")
            return output_path
            
        except Exception as e:
            file_logger.error(f"Volume normalization failed: {e}")
            raise
    
    def process_file(self, 
                    input_path: Union[str, Path],
                    output_dir: Union[str, Path],
                    speed_multiplier: float = 1.75,
                    remove_silence: bool = True,
                    normalize: bool = True,
                    target_sample_rate: int = 16000,
                    target_channels: int = 1) -> ProcessingResult:
        """
        Process a single file with all optimizations.
        
        Args:
            input_path: Input file path
            output_dir: Output directory
            speed_multiplier: Audio speed multiplier
            remove_silence: Whether to remove silence
            normalize: Whether to normalize volume
            target_sample_rate: Target sample rate
            target_channels: Target channel count
            
        Returns:
            ProcessingResult with processing information
        """
        import time
        start_time = time.time()
        
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_logger = get_file_logger(str(input_path))
        file_logger.info(f"Starting file processing: {input_path}")
        
        # Get original file info
        original_info = self.get_file_info(input_path)
        applied_operations = []
        
        try:
            current_file = input_path
            
            # Step 1: Convert to WAV with normalization
            if input_path.suffix.lower() != '.wav' or normalize:
                current_file = self.convert_to_wav(
                    current_file,
                    sample_rate=target_sample_rate,
                    channels=target_channels,
                    normalize=normalize
                )
                applied_operations.append("format_conversion")
                if normalize:
                    applied_operations.append("volume_normalization")
            
            # Step 2: Remove silence (if requested)
            if remove_silence:
                current_file = self.remove_silence(current_file)
                applied_operations.append("silence_removal")
            
            # Step 3: Apply speed multiplier (if not 1.0)
            if speed_multiplier != 1.0:
                current_file = self.apply_speed_multiplier(current_file, speed_multiplier)
                applied_operations.append(f"speed_adjustment_{speed_multiplier}x")
            
            # Step 4: Move to final output location
            final_output = output_dir / f"{input_path.stem}_processed.wav"
            if current_file != final_output:
                shutil.move(str(current_file), str(final_output))
            
            # Get processed file info
            processed_info = self.get_file_info(final_output)
            
            processing_time = time.time() - start_time
            
            result = ProcessingResult(
                original_path=input_path,
                processed_path=final_output,
                processing_time=processing_time,
                original_info=original_info,
                processed_info=processed_info,
                applied_operations=applied_operations
            )
            
            file_logger.info(f"File processing completed in {processing_time:.2f}s")
            file_logger.info(f"Applied operations: {', '.join(applied_operations)}")
            
            return result
            
        except Exception as e:
            file_logger.error(f"File processing failed: {e}")
            raise
    
    def process_batch(self, 
                     input_files: List[Union[str, Path]],
                     output_dir: Union[str, Path],
                     **processing_options) -> List[ProcessingResult]:
        """
        Process multiple files in batch.
        
        Args:
            input_files: List of input file paths
            output_dir: Output directory
            **processing_options: Options passed to process_file
            
        Returns:
            List of ProcessingResult objects
        """
        results = []
        output_dir = Path(output_dir)
        
        self.logger.info(f"Starting batch processing: {len(input_files)} files")
        
        for i, input_file in enumerate(input_files, 1):
            self.logger.info(f"Processing file {i}/{len(input_files)}: {Path(input_file).name}")
            
            try:
                result = self.process_file(input_file, output_dir, **processing_options)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to process {input_file}: {e}")
                # Continue with other files
        
        self.logger.info(f"Batch processing completed: {len(results)}/{len(input_files)} successful")
        return results
    
    def cleanup_temp_files(self):
        """Clean up temporary files."""
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(exist_ok=True)
                self.logger.info("Temporary files cleaned up")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temp files: {e}")
    
    def get_processing_stats(self, results: List[ProcessingResult]) -> Dict[str, Any]:
        """
        Get statistics from processing results.
        
        Args:
            results: List of processing results
            
        Returns:
            Statistics dictionary
        """
        if not results:
            return {}
        
        total_files = len(results)
        total_processing_time = sum(r.processing_time for r in results)
        total_original_duration = sum(r.original_info.duration for r in results)
        total_processed_duration = sum(r.processed_info.duration for r in results)
        
        # Calculate compression ratio
        compression_ratio = total_processed_duration / total_original_duration if total_original_duration > 0 else 1.0
        
        # Calculate processing speed
        processing_speed = total_original_duration / total_processing_time if total_processing_time > 0 else 0
        
        # Count operations
        operation_counts = {}
        for result in results:
            for op in result.applied_operations:
                operation_counts[op] = operation_counts.get(op, 0) + 1
        
        return {
            'total_files': total_files,
            'total_processing_time': total_processing_time,
            'total_original_duration': total_original_duration,
            'total_processed_duration': total_processed_duration,
            'compression_ratio': compression_ratio,
            'processing_speed': processing_speed,
            'average_processing_time': total_processing_time / total_files,
            'operations_applied': operation_counts
        }


# Global file processor instance
_file_processor: Optional[FileProcessor] = None


def get_file_processor() -> FileProcessor:
    """Get the global file processor instance."""
    global _file_processor
    if _file_processor is None:
        _file_processor = FileProcessor()
    return _file_processor