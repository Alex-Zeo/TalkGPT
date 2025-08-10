"""
TalkGPT CLI Transcription Commands

Implementation of single-file transcription command with all advanced features.
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from ...core.file_processor import get_file_processor
    from ...core.chunker import get_smart_chunker
    from ...core.transcriber import get_transcriber
    from ...utils.config import TalkGPTConfig
    from ...utils.logger import TalkGPTLogger
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from core.file_processor import get_file_processor
    from core.chunker import get_smart_chunker
    from core.transcriber import get_transcriber
    from utils.config import TalkGPTConfig
    from utils.logger import TalkGPTLogger

# Import analytics modules only when needed to avoid DLL issues
def get_speaker_analyzer():
    """Lazy import of speaker analyzer to avoid DLL issues."""
    import sys
    import platform
    try:
        # On Windows, some dependencies may have signal handling issues
        if platform.system() == 'Windows':
            import signal
            # Ensure SIGKILL is available or provide fallback
            if not hasattr(signal, 'SIGKILL'):
                signal.SIGKILL = signal.SIGTERM
        
        # Try relative imports first, then fallback to absolute
        try:
            from ...analytics.speaker_analyzer import get_speaker_analyzer as _get_speaker_analyzer
            return _get_speaker_analyzer()
        except ImportError:
            # Fallback for direct execution
            sys.path.append(str(Path(__file__).parent.parent.parent))
            from analytics.speaker_analyzer import get_speaker_analyzer as _get_speaker_analyzer
            return _get_speaker_analyzer()
            
    except (ImportError, AttributeError, ModuleNotFoundError) as e:
        print(f"Warning: Speaker analysis not available: {e}")
        return None

def get_uncertainty_detector():
    """Lazy import of uncertainty detector."""
    import sys
    try:
        # Try relative imports first, then fallback to absolute
        try:
            from ...analytics.uncertainty_detector import get_uncertainty_detector as _get_uncertainty_detector
            return _get_uncertainty_detector
        except ImportError:
            # Fallback for direct execution
            sys.path.append(str(Path(__file__).parent.parent.parent))
            from analytics.uncertainty_detector import get_uncertainty_detector as _get_uncertainty_detector
            return _get_uncertainty_detector
    except (ImportError, ModuleNotFoundError) as e:
        print(f"Warning: Uncertainty detection not available: {e}")
        return None

def get_timing_analyzer():
    """Lazy import of timing analyzer."""
    import sys
    try:
        # Try relative imports first, then fallback to absolute
        try:
            from ...analytics.timing_analyzer import get_timing_analyzer as _get_timing_analyzer
            return _get_timing_analyzer
        except ImportError:
            # Fallback for direct execution
            sys.path.append(str(Path(__file__).parent.parent.parent))
            from analytics.timing_analyzer import get_timing_analyzer as _get_timing_analyzer
            return _get_timing_analyzer
    except (ImportError, ModuleNotFoundError) as e:
        print(f"Warning: Timing analysis not available: {e}")
        return None

def get_enhanced_output_generator():
    """Lazy import of enhanced output generator."""
    import sys
    try:
        # Try relative imports first, then fallback to absolute
        try:
            from ...analytics.enhanced_output import get_enhanced_output_generator as _get_enhanced_output_generator
            return _get_enhanced_output_generator()
        except ImportError:
            # Fallback for direct execution
            sys.path.append(str(Path(__file__).parent.parent.parent))
            from analytics.enhanced_output import get_enhanced_output_generator as _get_enhanced_output_generator
            return _get_enhanced_output_generator()
    except (ImportError, ModuleNotFoundError) as e:
        print(f"Warning: Enhanced output generation not available: {e}")
        return None


def transcribe_single_file(input_path: Path,
                          output_dir: Optional[Path],
                          config: TalkGPTConfig,
                          logger: TalkGPTLogger,
                          **options) -> Dict[str, Any]:
    """
    Transcribe a single audio/video file with all features.
    
    Args:
        input_path: Path to input file
        output_dir: Output directory (None for same as input)
        config: TalkGPT configuration
        logger: Logger instance
        **options: Override options from CLI
        
    Returns:
        Dictionary with transcription results and metadata
    """
    start_time = time.time()
    
    # Determine output directory
    if output_dir is None:
        output_dir = input_path.parent / f"{input_path.stem}_transcription"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get file logger
    file_logger = logger.get_file_logger(str(input_path))
    file_logger.info(f"Starting single file transcription: {input_path}")
    
    try:
        # Apply configuration overrides
        effective_config = _apply_options_to_config(config, options)
        
        # Step 1: File Processing
        file_logger.info("Step 1: Processing audio file")
        processor = get_file_processor()
        
        # Accuracy-first: default speed 1.0; allow CLI override
        eff_speed = options.get('speed_multiplier', 1.0 if options.get('enhanced_analysis', False) else effective_config.processing.speed_multiplier)
        processing_result = processor.process_file(
            input_path,
            output_dir / "processed",
            speed_multiplier=eff_speed,
            remove_silence=effective_config.processing.remove_silence,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1
        )
        
        file_logger.info(f"File processing completed: {processing_result.processing_time:.2f}s")
        
        # Step 2: Smart Chunking
        file_logger.info("Step 2: Smart audio chunking")
        chunker = get_smart_chunker(
            chunk_size=effective_config.processing.chunk_size,
            overlap_duration=effective_config.processing.overlap_duration,
            silence_threshold=effective_config.processing.silence_threshold,
            min_silence_len=effective_config.processing.min_silence_len
        )
        
        chunking_result = chunker.chunk_audio(
            processing_result.processed_path,
            output_dir / "chunks",
            remove_silence=False  # Already done in processing
        )
        
        file_logger.info(f"Chunking completed: {chunking_result.total_chunks} chunks in {chunking_result.processing_time:.2f}s")
        
        # Step 3: Enhanced Transcription with Analysis
        enhanced_analysis = options.get('enhanced_analysis', False)
        
        if enhanced_analysis:
            file_logger.info("Step 3: Enhanced Whisper transcription with word-gap analysis")
            
            # Import enhanced transcription function
            try:
                from ...core.transcriber import enhanced_transcribe_with_analysis
                from ...core.resource_detector import get_device_config
                device_cfg = get_device_config(
                    force_device=effective_config.transcription.device if effective_config.transcription.device != 'auto' else None
                )

                enhanced_result = enhanced_transcribe_with_analysis(
                    processing_result.processed_path,
                    chunking_result,
                    bucket_seconds=options.get('bucket_seconds', 4.0),
                    gap_tolerance=options.get('gap_tolerance', 0.25),
                    gap_threshold=options.get('gap_threshold', 1.5),
                    enable_overlap_detection=True,
                    language=options.get('language'),
                    temperature=effective_config.transcription.temperature,
                    beam_size=effective_config.transcription.beam_size,
                    timing_repair=options.get('timing_repair', True)
                )
                
                # Extract standard transcription result for compatibility
                transcription_result = enhanced_result['original_transcription']
                
                # Store enhanced data for output generation
                enhanced_records = enhanced_result['enhanced_records']
                analysis_context = enhanced_result['analysis_context']
                
                file_logger.info(f"Enhanced transcription completed: {len(enhanced_records)} timing buckets created")
                
            except ImportError as e:
                file_logger.warning(f"Enhanced analysis not available, falling back to standard: {e}")
                enhanced_analysis = False
        
        if not enhanced_analysis:
            file_logger.info("Step 3: Standard Whisper transcription")
            from ...core.resource_detector import get_device_config
            device_cfg = get_device_config(
                force_device=effective_config.transcription.device if effective_config.transcription.device != 'auto' else None
            )
            transcriber = get_transcriber(
                model_size=effective_config.transcription.model_size,
                device=device_cfg['device'],
                compute_type=device_cfg['compute_type']
            )
            
            transcription_result = transcriber.transcribe_file(
                processing_result.processed_path,
                chunking_result,
                language=options.get('language'),
                temperature=effective_config.transcription.temperature,
                beam_size=effective_config.transcription.beam_size,
                word_timestamps=effective_config.output.word_timestamps
            )
            
            enhanced_records = None
            analysis_context = None
        
        file_logger.info(f"Transcription completed: {transcription_result.chunks_processed} chunks, "
                        f"speed: {transcription_result.performance_metrics['processing_speed']:.1f}x real-time")
        
        # Step 4: Speaker Analysis (if enabled)
        speaker_result = None
        if effective_config.analytics.enable_speaker_diarization:
            file_logger.info("Step 4: Speaker diarization")
            try:
                # Auto-route backend by CLI option and platform
                backend = options.get('diarization_backend', 'auto')
                import platform
                if backend == 'auto':
                    backend = 'pyannote' if platform.system().lower() != 'windows' else 'speechbrain'

                if backend == 'none':
                    speaker_analyzer = None
                else:
                    speaker_analyzer = get_speaker_analyzer()
                if speaker_analyzer and hasattr(speaker_analyzer, 'pipeline') and speaker_analyzer.pipeline is not None:
                    speaker_result = speaker_analyzer.enhance_transcription(
                        transcription_result,
                        processing_result.processed_path
                    )
                    file_logger.info(f"Speaker analysis completed: {speaker_result.diarization_result.speaker_count} speakers")
                else:
                    file_logger.warning("Speaker analyzer not available, skipping")
            except Exception as e:
                file_logger.warning(f"Speaker analysis failed: {e}")
        
        # Step 5: Uncertainty Analysis (if enabled)
        uncertainty_result = None
        if effective_config.analytics.enable_uncertainty_detection:
            file_logger.info("Step 5: Uncertainty detection")
            try:
                uncertainty_detector_factory = get_uncertainty_detector()
                if uncertainty_detector_factory:
                    # Create uncertainty detector with proper configuration
                    try:
                        uncertainty_detector = uncertainty_detector_factory(
                            confidence_threshold=effective_config.analytics.confidence_threshold
                        )
                    except TypeError:
                        # Fallback if factory doesn't accept arguments
                        uncertainty_detector = uncertainty_detector_factory()
                    
                    uncertainty_result = uncertainty_detector.analyze_uncertainty(
                        transcription_result,
                        processing_result.processed_path
                    )
                    
                    # Handle different types of uncertainty results
                    if uncertainty_result:
                        if hasattr(uncertainty_result, 'flagged_segments'):
                            flagged_segments = uncertainty_result.flagged_segments
                            if isinstance(flagged_segments, int):
                                flagged_count = flagged_segments
                            else:
                                try:
                                    flagged_count = len(flagged_segments)
                                except TypeError:
                                    flagged_count = 0
                        else:
                            flagged_count = 0
                        file_logger.info(f"Uncertainty analysis completed: {flagged_count} flagged segments")
                    else:
                        file_logger.info("Uncertainty analysis completed")
                else:
                    file_logger.warning("Uncertainty detector not available")
            except Exception as e:
                file_logger.warning(f"Uncertainty analysis failed: {e}")
        
        # Step 6: Advanced Timing Analysis (Default)
        timing_buckets = None
        cadence_analysis = None
        if effective_config.analytics.enable_timing_analysis:
            file_logger.info("Step 6: Advanced timing analysis")
            try:
                timing_analyzer_factory = get_timing_analyzer()
                if timing_analyzer_factory:
                    timing_analyzer = timing_analyzer_factory(effective_config.analytics.timing.dict())
                    overlap_segments = None
                    if speaker_result and hasattr(speaker_result, 'diarization_result') and speaker_result.diarization_result:
                        overlap_segments = speaker_result.diarization_result.overlap_segments
                    timing_buckets, cadence_analysis = timing_analyzer.analyze_timing(
                        transcription_result,
                        overlap_segments
                    )
                    if timing_buckets and cadence_analysis:
                        file_logger.info(f"Timing analysis completed: {len(timing_buckets)} buckets, "
                                       f"{cadence_analysis.anomalous_buckets} anomalies detected")
                    else:
                        file_logger.info("Timing analysis completed")
                else:
                    file_logger.warning("Timing analyzer not available")
            except Exception as e:
                file_logger.warning(f"Timing analysis failed: {e}")
        
        # Step 7: Generate Enhanced Output Files
        file_logger.info("Step 7: Generating output files")
        
        if enhanced_analysis and enhanced_records:
            # Generate enhanced outputs with new analysis
            output_files = _generate_enhanced_output_files(
                enhanced_records,
                analysis_context,
                transcription_result,
                speaker_result,
                uncertainty_result,
                output_dir,
                effective_config.output.formats,
                input_path.stem
            )
            file_logger.info("Enhanced outputs with word-gap analysis generated")
        elif timing_buckets and cadence_analysis:
            # Use legacy enhanced output generator with timing analysis
            enhanced_generator = get_enhanced_output_generator()
            if enhanced_generator:
                output_files = enhanced_generator.generate_enhanced_outputs(
                    transcription_result,
                    timing_buckets,
                    cadence_analysis,
                    speaker_result,
                    uncertainty_result,
                    output_dir,
                    input_path.stem
                )
                file_logger.info("Enhanced outputs with timing analysis generated")
            else:
                # Fallback to standard outputs
                output_files = _generate_output_files(
                    transcription_result,
                    speaker_result,
                    uncertainty_result,
                    output_dir,
                    effective_config.output.formats,
                    input_path.stem
                )
                file_logger.warning("Enhanced output generator not available, using standard outputs")
        else:
            # Standard output generation
            output_files = _generate_output_files(
                transcription_result,
                speaker_result,
                uncertainty_result,
                output_dir,
                effective_config.output.formats,
                input_path.stem
            )
        
        # Calculate final metrics
        total_time = time.time() - start_time
        
        # Convert any Path objects to strings for JSON serialization
        def convert_paths_to_strings(obj):
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_paths_to_strings(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_paths_to_strings(item) for item in obj]
            else:
                return obj
        
        result = {
            'input_file': str(input_path),
            'output_directory': str(output_dir),
            'output_files': convert_paths_to_strings(output_files),
            'processing_time': total_time,
            'transcription_time': transcription_result.total_processing_time,
            'processing_speed': transcription_result.performance_metrics.get('processing_speed', 0),
            'quality_score': uncertainty_result.quality_metrics.overall_quality_score if uncertainty_result and hasattr(uncertainty_result, 'quality_metrics') and uncertainty_result.quality_metrics else None,
            'speaker_count': speaker_result.diarization_result.speaker_count if speaker_result and hasattr(speaker_result, 'diarization_result') and speaker_result.diarization_result else None,
            'flagged_segments': (
                (uncertainty_result.flagged_segments if isinstance(getattr(uncertainty_result, 'flagged_segments', None), int)
                 else (len(getattr(uncertainty_result, 'flagged_segments', []) or [])
                      if hasattr(uncertainty_result, 'flagged_segments') else None))
                if uncertainty_result else None
            ),
            'chunks_processed': transcription_result.chunks_processed,
            'performance_metrics': convert_paths_to_strings(transcription_result.performance_metrics),
            # Timing analysis metrics
            'timing_analysis': {
                'enabled': timing_buckets is not None,
                'bucket_count': len(timing_buckets) if timing_buckets else 0,
                'anomalous_buckets': cadence_analysis.anomalous_buckets if cadence_analysis else 0,
                'global_gap_mean': cadence_analysis.global_gap_mean if cadence_analysis else None,
                'cadence_summary': cadence_analysis.cadence_summary if cadence_analysis else None,
                'enhanced_outputs': timing_buckets is not None
            }
        }
        
        file_logger.info(f"Single file transcription completed successfully in {total_time:.2f}s")
        
        # Cleanup temporary files
        processor.cleanup_temp_files()
        if chunking_result.chunks:
            chunker.cleanup_chunks(chunking_result)
        
        return result
        
    except Exception as e:
        file_logger.error(f"Single file transcription failed: {e!r}")
        raise


def _apply_options_to_config(config: TalkGPTConfig, options: Dict[str, Any]) -> TalkGPTConfig:
    """Apply CLI options to configuration."""
    # Create a copy to avoid modifying the original
    import copy
    effective_config = copy.deepcopy(config)
    
    # Apply processing options
    if 'speed_multiplier' in options:
        effective_config.processing.speed_multiplier = options['speed_multiplier']
    
    if 'workers' in options:
        effective_config.processing.max_workers = options['workers']
    
    if 'remove_silence' in options:
        effective_config.processing.remove_silence = options['remove_silence']
    
    # Apply transcription options
    if 'device' in options:
        effective_config.transcription.device = options['device']
    
    if 'language' in options:
        effective_config.transcription.language = options['language']
    
    # Apply output options
    if 'formats' in options:
        effective_config.output.formats = options['formats']
    
    # Apply analytics options
    if 'analyze_speakers' in options:
        effective_config.analytics.enable_speaker_diarization = options['analyze_speakers']
    
    if 'analyze_uncertainty' in options:
        effective_config.analytics.enable_uncertainty_detection = options['analyze_uncertainty']
    
    return effective_config


def _generate_output_files(transcription_result,
                          speaker_result,
                          uncertainty_result,
                          output_dir: Path,
                          formats: List[str],
                          base_name: str) -> Dict[str, str]:
    """Generate all requested output files."""
    output_files = {}
    
    # Use enhanced result if available, otherwise use original
    if speaker_result:
        primary_result = speaker_result.original_result
        segments = speaker_result.speaker_labeled_segments
    else:
        primary_result = transcription_result
        segments = None
    
    for format_type in formats:
        output_file = output_dir / f"{base_name}.{format_type}"
        
        if format_type == "srt":
            _generate_srt_file(primary_result, output_file, segments)
        elif format_type == "json":
            _generate_json_file(primary_result, speaker_result, uncertainty_result, output_file)
        elif format_type == "txt":
            _generate_txt_file(primary_result, output_file, segments)
        elif format_type == "csv":
            _generate_csv_file(primary_result, output_file, segments)
        
        output_files[format_type] = str(output_file)
    
    return output_files


def _generate_srt_file(transcription_result, output_file: Path, speaker_segments=None):
    """Generate SRT subtitle file."""
    if hasattr(transcription_result, 'merged_result'):
        segments = transcription_result.merged_result.segments
    else:
        segments = transcription_result.segments
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments, 1):
            start_time = _format_srt_time(segment.start)
            end_time = _format_srt_time(segment.end)
            
            # Add speaker label if available
            text = segment.text
            if speaker_segments:
                speaker_seg = next((s for s in speaker_segments if s['id'] == segment.id), None)
                if speaker_seg and speaker_seg.get('speaker'):
                    text = f"[{speaker_seg['speaker']}] {text}"
                
                # Add overlap indicator
                if speaker_seg and speaker_seg.get('has_overlap'):
                    text += " [OVERLAP]"
            
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")


def _generate_json_file(transcription_result, speaker_result, uncertainty_result, output_file: Path):
    """Generate comprehensive JSON file."""
    import json
    from dataclasses import asdict
    from pathlib import Path
    
    def convert_paths_to_strings(obj):
        """Convert Path objects to strings for JSON serialization."""
        if isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_paths_to_strings(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_paths_to_strings(item) for item in obj]
        else:
            return obj
    
    # Safely convert dataclasses to dicts, handling Path objects
    try:
        transcription_data = convert_paths_to_strings(asdict(transcription_result)) if transcription_result else None
    except Exception as e:
        # Fallback: create basic transcription data
        transcription_data = {
            'language': getattr(transcription_result, 'language', 'unknown'),
            'segments_count': len(getattr(transcription_result, 'segments', [])),
            'processing_time': getattr(transcription_result, 'total_processing_time', 0)
        }
    
    try:
        speaker_data = convert_paths_to_strings(asdict(speaker_result)) if speaker_result else None
    except Exception:
        speaker_data = {'speaker_count': getattr(speaker_result, 'speaker_count', 0)} if speaker_result else None
    
    try:
        uncertainty_data = convert_paths_to_strings(asdict(uncertainty_result)) if uncertainty_result else None
    except Exception:
        uncertainty_data = {'flagged_segments': 0} if uncertainty_result else None
    
    data = {
        'transcription': transcription_data,
        'speaker_analysis': speaker_data,
        'uncertainty_analysis': uncertainty_data,
        'metadata': {
            'version': '0.1.0',
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'format': 'TalkGPT JSON v1.0'
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _generate_txt_file(transcription_result, output_file: Path, speaker_segments=None):
    """Generate plain text file."""
    if hasattr(transcription_result, 'merged_result'):
        segments = transcription_result.merged_result.segments
    else:
        segments = transcription_result.segments
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for segment in segments:
            # Add timestamp
            timestamp = f"[{_format_timestamp(segment.start)}]"
            
            # Add speaker label if available
            text = segment.text
            if speaker_segments:
                speaker_seg = next((s for s in speaker_segments if s['id'] == segment.id), None)
                if speaker_seg and speaker_seg.get('speaker'):
                    text = f"[{speaker_seg['speaker']}] {text}"
            
            f.write(f"{timestamp} {text}\n")


def _generate_csv_file(transcription_result, output_file: Path, speaker_segments=None):
    """Generate CSV file with detailed segment information."""
    import csv
    
    if hasattr(transcription_result, 'merged_result'):
        segments = transcription_result.merged_result.segments
    else:
        segments = transcription_result.segments
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        headers = ['segment_id', 'start_time', 'end_time', 'duration', 'text', 'confidence']
        if speaker_segments:
            headers.extend(['speaker', 'has_overlap'])
        writer.writerow(headers)
        
        # Data
        for segment in segments:
            duration = segment.end - segment.start
            row = [
                segment.id,
                segment.start,
                segment.end,
                duration,
                segment.text,
                segment.avg_logprob
            ]
            
            if speaker_segments:
                speaker_seg = next((s for s in speaker_segments if s['id'] == segment.id), None)
                if speaker_seg:
                    row.extend([
                        speaker_seg.get('speaker', ''),
                        speaker_seg.get('has_overlap', False)
                    ])
                else:
                    row.extend(['', False])
            
            writer.writerow(row)


def _format_srt_time(seconds: float) -> str:
    """Format time for SRT subtitle format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


def _format_timestamp(seconds: float) -> str:
    """Format timestamp for text output."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def _generate_enhanced_output_files(enhanced_records,
                                   analysis_context,
                                   transcription_result,
                                   speaker_result,
                                   uncertainty_result,
                                   output_dir: Path,
                                   formats: List[str],
                                   base_name: str) -> Dict[str, str]:
    """Generate enhanced output files with comprehensive word-gap analysis."""
    output_files = {}
    
    # Generate standard formats first
    standard_files = _generate_output_files(
        transcription_result,
        speaker_result,
        uncertainty_result,
        output_dir,
        formats,
        base_name
    )
    output_files.update(standard_files)
    
    # Generate enhanced markdown with complete analysis
    try:
        from ...output.md_writer import write_enhanced_markdown_report
        
        enhanced_md_file = output_dir / f"{base_name}_enhanced.md"
        
        # Prepare metadata
        metadata = {
            'processing_method': '4-second timing buckets with word-gap analysis',
            'bucket_count': len(enhanced_records),
            'total_words': sum(r.word_count for r in enhanced_records),
            'total_gaps': sum(r.word_gap_count for r in enhanced_records),
            'global_gap_mean': f"{analysis_context.global_mean:.4f}s",
            'global_gap_std': f"{analysis_context.global_std_dev:.4f}s",
            'cadence_thresholds': f"±{analysis_context.gap_threshold}σ"
        }
        
        write_enhanced_markdown_report(
            enhanced_records,
            enhanced_md_file,
            title=f"Enhanced Transcription: {base_name}",
            metadata=metadata,
            precision=4,
            max_gaps_per_line=None  # Show all gaps as per requirements
        )
        
        output_files['enhanced_markdown'] = str(enhanced_md_file)
        
    except ImportError as e:
        print(f"Warning: Enhanced markdown output not available: {e}")
    
    # Generate enhanced JSON with complete analysis data
    try:
        enhanced_json_file = output_dir / f"{base_name}_enhanced.json"
        
        # Prepare comprehensive data
        enhanced_data = {
            'metadata': {
                'version': '0.4.0',
                'format': 'TalkGPT Enhanced JSON v2.0',
                'processing_method': '4-second windowing with comprehensive word-gap analysis',
                'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'analysis_context': {
                'global_mean': analysis_context.global_mean,
                'global_std_dev': analysis_context.global_std_dev,
                'global_variance': analysis_context.global_variance,
                'total_gaps': analysis_context.total_gaps,
                'gap_threshold': analysis_context.gap_threshold,
                'slow_threshold': analysis_context.slow_threshold,
                'fast_threshold': analysis_context.fast_threshold
            },
            'timing_buckets': [record.to_dict() for record in enhanced_records],
            'original_transcription': {
                'language': getattr(transcription_result, 'language', 'unknown'),
                'segments_count': len(getattr(transcription_result, 'segments', [])),
                'processing_time': getattr(transcription_result, 'total_processing_time', 0)
            },
            'summary': {
                'total_buckets': len(enhanced_records),
                'total_duration': sum(r.duration for r in enhanced_records),
                'total_words': sum(r.word_count for r in enhanced_records),
                'total_gaps': sum(r.word_gap_count for r in enhanced_records),
                'cadence_distribution': {
                    'slow': sum(1 for r in enhanced_records if r.cadence == 'slow'),
                    'normal': sum(1 for r in enhanced_records if r.cadence == 'normal'),
                    'fast': sum(1 for r in enhanced_records if r.cadence == 'fast')
                },
                'overlap_distribution': {
                    'overlap': sum(1 for r in enhanced_records if r.speaker_overlap == 'overlap'),
                    'single': sum(1 for r in enhanced_records if r.speaker_overlap == 'single'),
                    'unknown': sum(1 for r in enhanced_records if r.speaker_overlap == 'unknown check pyannote')
                }
            }
        }
        
        import json
        with open(enhanced_json_file, 'w', encoding='utf-8') as f:
            json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
        
        output_files['enhanced_json'] = str(enhanced_json_file)
        
    except Exception as e:
        print(f"Warning: Enhanced JSON output failed: {e}")
    
    return output_files