"""
Advanced TalkGPT Transcription with Full Pipeline

Implements the complete advanced pipeline with:
- Word-level timestamps
- Sentence-level confidence scoring  
- Speaker overlap detection
- Uncertainty analysis
- Multi-format output with rich metadata
"""

# CRITICAL: Set environment variables BEFORE any other imports to prevent OpenMP conflicts
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['MKL_NUM_THREADS'] = '8'
os.environ['PYTHONUNBUFFERED'] = '1'

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add src to path first
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load environment variables from .env file
try:
    from src.utils.env_loader import ensure_environment_loaded
    ensure_environment_loaded()
except ImportError:
    # Fallback: load manually
    try:
        from dotenv import load_dotenv
        env_file = Path(__file__).parent / '.env'
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        # Final fallback: set manually
        os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

def advanced_transcription(video_path: Path, output_dir: Path) -> Dict[str, Any]:
    """
    Perform advanced transcription with all features enabled.
    
    Args:
        video_path: Path to input video/audio file
        output_dir: Output directory for results
        
    Returns:
        Dictionary with complete transcription results
    """
    print("🚀 Advanced TalkGPT Transcription Pipeline")
    print("=" * 60)
    
    start_time = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        'input_file': str(video_path),
        'output_directory': str(output_dir),
        'processing_stages': {},
        'final_outputs': {},
        'performance_metrics': {},
        'errors': []
    }
    
    try:
        # Stage 1: Configuration and Setup
        print("📋 Stage 1: Loading configuration and setup...")
        from utils.config import load_config
        from utils.logger import setup_logging
        from core.resource_detector import detect_hardware
        
        config = load_config("default")
        logger = setup_logging(config.logging)
        hardware = detect_hardware()
        
        results['processing_stages']['setup'] = {
            'status': 'completed',
            'config_model': config.transcription.model_size,
            'device': hardware.recommended_device,
            'workers': hardware.optimal_workers,
            'duration': time.time() - start_time
        }
        print(f"   ✅ Setup complete: {hardware.recommended_device} device, {hardware.optimal_workers} workers")
        
        # Stage 2: File Processing
        print("📋 Stage 2: Audio/video processing...")
        stage_start = time.time()
        
        from core.file_processor import FileProcessor
        processor = FileProcessor()
        
        processing_result = processor.process_file(
            video_path,
            output_dir / "processed",
            speed_multiplier=config.processing.speed_multiplier,
            remove_silence=config.processing.remove_silence,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1
        )
        
        results['processing_stages']['file_processing'] = {
            'status': 'completed',
            'original_duration': processing_result.original_info.duration,
            'processed_duration': processing_result.processed_info.duration,
            'operations': processing_result.applied_operations,
            'duration': time.time() - stage_start
        }
        print(f"   ✅ File processed: {processing_result.original_info.duration:.1f}s → {processing_result.processed_info.duration:.1f}s")
        
        # Stage 3: Smart Chunking
        print("📋 Stage 3: Intelligent audio chunking...")
        stage_start = time.time()
        
        from core.chunker import SmartChunker
        chunker = SmartChunker(
            chunk_size=config.processing.chunk_size,
            overlap_duration=config.processing.overlap_duration,
            silence_threshold=config.processing.silence_threshold,
            min_silence_len=config.processing.min_silence_len
        )
        
        chunking_result = chunker.chunk_audio(
            processing_result.processed_path,
            output_dir / "chunks",
            remove_silence=False  # Already done in processing
        )
        
        results['processing_stages']['chunking'] = {
            'status': 'completed',
            'total_chunks': chunking_result.total_chunks,
            'silence_removed': chunking_result.silence_removed,
            'compression_ratio': chunking_result.compression_ratio,
            'duration': time.time() - stage_start
        }
        print(f"   ✅ Audio chunked: {chunking_result.total_chunks} chunks, {chunking_result.silence_removed:.1f}s silence removed")
        
        # Stage 4: Advanced Transcription with Word Timestamps
        print("📋 Stage 4: Advanced Whisper transcription...")
        stage_start = time.time()
        
        from core.transcriber import WhisperTranscriber
        
        # Use optimal settings based on hardware
        transcriber = WhisperTranscriber(
            model_size=config.transcription.model_size,
            device=config.transcription.device,  # Will auto-select
            compute_type=config.transcription.compute_type  # Will auto-select
        )
        
        # Transcribe with word timestamps enabled
        transcription_result = transcriber.transcribe_file(
            processing_result.processed_path,
            chunking_result,
            language=config.transcription.language,
            temperature=config.transcription.temperature,
            beam_size=config.transcription.beam_size,
            word_timestamps=True  # Enable word-level timestamps
        )
        
        results['processing_stages']['transcription'] = {
            'status': 'completed',
            'chunks_processed': transcription_result.chunks_processed,
            'processing_speed': transcription_result.performance_metrics.get('processing_speed', 0),
            'language_detected': transcription_result.merged_result.language,
            'language_confidence': transcription_result.merged_result.language_probability,
            'duration': time.time() - stage_start
        }
        print(f"   ✅ Transcription complete: {transcription_result.chunks_processed} chunks, "
              f"{transcription_result.performance_metrics.get('processing_speed', 0):.1f}x real-time")
        
        # Stage 5: Speaker Analysis (if enabled)
        speaker_result = None
        if config.analytics.enable_speaker_diarization:
            print("📋 Stage 5: Speaker diarization analysis...")
            stage_start = time.time()
            
            try:
                from analytics.speaker_analyzer import SpeakerAnalyzer
                
                speaker_analyzer = SpeakerAnalyzer()
                if speaker_analyzer.pipeline is not None:
                    speaker_result = speaker_analyzer.enhance_transcription(
                        transcription_result,
                        processing_result.processed_path
                    )
                    
                    results['processing_stages']['speaker_analysis'] = {
                        'status': 'completed',
                        'speaker_count': speaker_result.diarization_result.speaker_count,
                        'segments_labeled': len(speaker_result.speaker_labeled_segments),
                        'overlaps_detected': len(speaker_result.diarization_result.overlap_segments),
                        'duration': time.time() - stage_start
                    }
                    print(f"   ✅ Speaker analysis: {speaker_result.diarization_result.speaker_count} speakers, "
                          f"{len(speaker_result.diarization_result.overlap_segments)} overlaps")
                else:
                    results['processing_stages']['speaker_analysis'] = {
                        'status': 'skipped',
                        'reason': 'Speaker analyzer not available'
                    }
                    print("   ⚠️  Speaker analysis skipped: pyannote.audio not available")
                    
            except Exception as e:
                results['processing_stages']['speaker_analysis'] = {
                    'status': 'failed',
                    'error': str(e)
                }
                results['errors'].append(f"Speaker analysis failed: {e}")
                print(f"   ⚠️  Speaker analysis failed: {e}")
        
        # Stage 6: Uncertainty Detection
        uncertainty_result = None
        if config.analytics.enable_uncertainty_detection:
            print("📋 Stage 6: Uncertainty and quality analysis...")
            stage_start = time.time()
            
            try:
                from analytics.uncertainty_detector import UncertaintyDetector
                
                uncertainty_detector = UncertaintyDetector(
                    confidence_threshold=config.analytics.confidence_threshold
                )
                
                uncertainty_result = uncertainty_detector.analyze_uncertainty(
                    transcription_result,
                    processing_result.processed_path
                )
                
                results['processing_stages']['uncertainty_analysis'] = {
                    'status': 'completed',
                    'quality_score': uncertainty_result.quality_metrics.overall_quality_score,
                    'flagged_segments': uncertainty_result.flagged_segments,
                    'flagged_percentage': uncertainty_result.flagged_percentage,
                    'recommendations_count': len(uncertainty_result.recommendations),
                    'duration': time.time() - stage_start
                }
                print(f"   ✅ Quality analysis: {uncertainty_result.quality_metrics.overall_quality_score:.2f} score, "
                      f"{uncertainty_result.flagged_segments} flagged segments")
                
            except Exception as e:
                results['processing_stages']['uncertainty_analysis'] = {
                    'status': 'failed',
                    'error': str(e)
                }
                results['errors'].append(f"Uncertainty analysis failed: {e}")
                print(f"   ⚠️  Uncertainty analysis failed: {e}")
        
        # Stage 7: Advanced Timing Analysis
        print("📋 Stage 7: Advanced timing analysis...")
        stage_start = time.time()
        
        timing_buckets = []
        cadence_analysis = None
        
        if config.analytics.enable_timing_analysis:
            try:
                from analytics.timing_analyzer import get_timing_analyzer
                
                timing_analyzer = get_timing_analyzer(config.analytics.timing.dict())
                timing_buckets, cadence_analysis = timing_analyzer.analyze_timing(
                    transcription_result,
                    speaker_result.diarization_result.overlap_segments if speaker_result else None
                )
                
                results['processing_stages']['timing_analysis'] = {
                    'status': 'completed',
                    'buckets_created': len(timing_buckets),
                    'anomalous_buckets': cadence_analysis.anomalous_buckets,
                    'global_gap_mean': cadence_analysis.global_gap_mean,
                    'cadence_summary': cadence_analysis.cadence_summary,
                    'duration': time.time() - stage_start
                }
                print(f"   ✅ Timing analysis: {len(timing_buckets)} buckets, "
                      f"{cadence_analysis.anomalous_buckets} anomalies, "
                      f"cadence: {cadence_analysis.cadence_summary}")
                
            except Exception as e:
                results['processing_stages']['timing_analysis'] = {
                    'status': 'failed',
                    'error': str(e)
                }
                results['errors'].append(f"Timing analysis failed: {e}")
                print(f"   ⚠️  Timing analysis failed: {e}")
        else:
            results['processing_stages']['timing_analysis'] = {
                'status': 'skipped',
                'reason': 'Timing analysis disabled'
            }
        
        # Stage 8: Enhanced Output Generation with Timing Data
        print("📋 Stage 8: Generating enhanced outputs with timing analysis...")
        stage_start = time.time()
        
        if timing_buckets and cadence_analysis:
            # Use enhanced output generator with timing analysis
            from analytics.enhanced_output import get_enhanced_output_generator
            
            output_generator = get_enhanced_output_generator()
            output_files = output_generator.generate_enhanced_outputs(
                transcription_result,
                timing_buckets,
                cadence_analysis,
                speaker_result,
                uncertainty_result,
                output_dir,
                video_path.stem
            )
        else:
            # Fallback to standard outputs
            output_files = generate_advanced_outputs(
                transcription_result,
                speaker_result,
                uncertainty_result,
                output_dir,
                video_path.stem
            )
        
        results['processing_stages']['output_generation'] = {
            'status': 'completed',
            'formats_generated': list(output_files.keys()),
            'enhanced_with_timing': timing_buckets is not None,
            'duration': time.time() - stage_start
        }
        results['final_outputs'] = output_files
        
        print(f"   ✅ Enhanced outputs generated: {', '.join(output_files.keys())}")
        
        # Final Performance Metrics
        total_time = time.time() - start_time
        results['performance_metrics'] = {
            'total_processing_time': total_time,
            'audio_duration': processing_result.original_info.duration,
            'processing_speed_factor': processing_result.original_info.duration / total_time,
            'stages_completed': sum(1 for stage in results['processing_stages'].values() 
                                  if stage.get('status') == 'completed'),
            'stages_failed': sum(1 for stage in results['processing_stages'].values() 
                               if stage.get('status') == 'failed'),
            'success_rate': (sum(1 for stage in results['processing_stages'].values() 
                               if stage.get('status') == 'completed') / 
                           len(results['processing_stages'])) * 100
        }
        
        print("\n" + "=" * 60)
        print("🎉 Advanced Transcription Complete!")
        print(f"📊 Processing Speed: {results['performance_metrics']['processing_speed_factor']:.1f}x real-time")
        print(f"📁 Outputs: {len(output_files)} files generated")
        print(f"⏱️  Total Time: {total_time:.2f}s")
        
        return results
        
    except Exception as e:
        results['processing_stages']['fatal_error'] = {
            'status': 'failed',
            'error': str(e),
            'duration': time.time() - start_time
        }
        results['errors'].append(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return results

def generate_advanced_outputs(transcription_result, 
                            speaker_result, 
                            uncertainty_result,
                            output_dir: Path, 
                            base_name: str) -> Dict[str, str]:
    """Generate advanced output files with rich metadata."""
    output_files = {}
    
    # Use enhanced result if available
    if speaker_result:
        segments = speaker_result.speaker_labeled_segments
        primary_result = speaker_result.original_result
    else:
        segments = None
        primary_result = transcription_result
    
    # 1. Advanced SRT with Speaker Labels and Confidence
    srt_file = output_dir / f"{base_name}_advanced.srt"
    generate_advanced_srt(primary_result, segments, uncertainty_result, srt_file)
    output_files['advanced_srt'] = str(srt_file)
    
    # 2. Comprehensive JSON with All Metadata
    json_file = output_dir / f"{base_name}_complete.json"
    generate_comprehensive_json(transcription_result, speaker_result, uncertainty_result, json_file)
    output_files['comprehensive_json'] = str(json_file)
    
    # 3. Markdown Report with Timestamps and Flags
    md_file = output_dir / f"{base_name}_report.md"
    generate_markdown_report(primary_result, segments, uncertainty_result, md_file)
    output_files['markdown_report'] = str(md_file)
    
    # 4. CSV for Data Analysis
    csv_file = output_dir / f"{base_name}_analysis.csv"
    generate_analysis_csv(primary_result, segments, uncertainty_result, csv_file)
    output_files['analysis_csv'] = str(csv_file)
    
    return output_files

def generate_advanced_srt(result, segments, uncertainty_result, output_file: Path):
    """Generate SRT with speaker labels and confidence indicators."""
    if hasattr(result, 'merged_result'):
        transcript_segments = result.merged_result.segments
    else:
        transcript_segments = result.segments
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(transcript_segments, 1):
            start_time = format_srt_time(segment.start)
            end_time = format_srt_time(segment.end)
            
            text = segment.text
            
            # Add speaker label if available
            if segments:
                speaker_seg = next((s for s in segments if s['id'] == segment.id), None)
                if speaker_seg and speaker_seg.get('speaker'):
                    text = f"[{speaker_seg['speaker']}] {text}"
                
                # Add overlap indicator
                if speaker_seg and speaker_seg.get('has_overlap'):
                    text += " [OVERLAP]"
            
            # Add confidence indicator
            if segment.avg_logprob < -1.0:
                text += " [LOW_CONF]"
            
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")

def generate_comprehensive_json(transcription_result, speaker_result, uncertainty_result, output_file: Path):
    """Generate comprehensive JSON with all analysis data."""
    data = {
        'metadata': {
            'version': '0.1.0',
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'format': 'TalkGPT Advanced JSON v1.0'
        },
        'transcription': {
            'language': transcription_result.merged_result.language if hasattr(transcription_result, 'merged_result') else transcription_result.language,
            'language_probability': transcription_result.merged_result.language_probability if hasattr(transcription_result, 'merged_result') else transcription_result.language_probability,
            'segments': [
                {
                    'id': seg.id,
                    'start': seg.start,
                    'end': seg.end,
                    'text': seg.text,
                    'avg_logprob': seg.avg_logprob,
                    'no_speech_prob': seg.no_speech_prob,
                    'words': seg.words if hasattr(seg, 'words') else None
                }
                for seg in (transcription_result.merged_result.segments if hasattr(transcription_result, 'merged_result') else transcription_result.segments)
            ]
        },
        'speaker_analysis': {
            'enabled': speaker_result is not None,
            'speaker_count': speaker_result.diarization_result.speaker_count if speaker_result else 0,
            'overlaps_detected': len(speaker_result.diarization_result.overlap_segments) if speaker_result else 0,
            'labeled_segments': speaker_result.speaker_labeled_segments if speaker_result else []
        } if speaker_result else None,
        'quality_analysis': {
            'enabled': uncertainty_result is not None,
            'overall_score': uncertainty_result.quality_metrics.overall_quality_score if uncertainty_result else None,
            'flagged_segments': uncertainty_result.flagged_segments if uncertainty_result else 0,
            'recommendations': uncertainty_result.recommendations if uncertainty_result else []
        } if uncertainty_result else None
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_markdown_report(result, segments, uncertainty_result, output_file: Path):
    """Generate markdown report with timestamps and quality flags."""
    if hasattr(result, 'merged_result'):
        transcript_segments = result.merged_result.segments
        language = result.merged_result.language
    else:
        transcript_segments = result.segments
        language = result.language
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# TalkGPT Advanced Transcription Report\n\n")
        f.write(f"**Language:** {language}  \n")
        f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Segments:** {len(transcript_segments)}\n\n")
        
        if uncertainty_result:
            f.write(f"**Quality Score:** {uncertainty_result.quality_metrics.overall_quality_score:.2f}  \n")
            f.write(f"**Flagged Segments:** {uncertainty_result.flagged_segments}\n\n")
        
        f.write("## Transcript\n\n")
        
        for i, segment in enumerate(transcript_segments, 1):
            ts = f"{segment.start:.2f}–{segment.end:.2f}"
            text = segment.text
            
            # Add speaker label
            if segments:
                speaker_seg = next((s for s in segments if s['id'] == segment.id), None)
                if speaker_seg and speaker_seg.get('speaker'):
                    text = f"**[{speaker_seg['speaker']}]** {text}"
            
            # Add quality flags
            flags = []
            if segments:
                speaker_seg = next((s for s in segments if s['id'] == segment.id), None)
                if speaker_seg and speaker_seg.get('has_overlap'):
                    flags.append("⚠️ OVERLAP")
            
            if segment.avg_logprob < -1.0:
                flags.append("🔍 LOW_CONF")
            
            flag_str = " " + " ".join(flags) if flags else ""
            
            f.write(f"{i}. **[{ts}]** {text}{flag_str}  \n")
            f.write(f"    <sub>confidence {segment.avg_logprob:.2f}</sub>\n\n")

def generate_analysis_csv(result, segments, uncertainty_result, output_file: Path):
    """Generate CSV for detailed analysis."""
    import csv
    
    if hasattr(result, 'merged_result'):
        transcript_segments = result.merged_result.segments
    else:
        transcript_segments = result.segments
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        headers = ['segment_id', 'start_time', 'end_time', 'duration', 'text', 
                  'confidence', 'no_speech_prob', 'speaker', 'has_overlap', 
                  'uncertainty_level', 'quality_flag']
        writer.writerow(headers)
        
        # Data
        for segment in transcript_segments:
            duration = segment.end - segment.start
            
            # Get speaker info
            speaker = ""
            has_overlap = False
            if segments:
                speaker_seg = next((s for s in segments if s['id'] == segment.id), None)
                if speaker_seg:
                    speaker = speaker_seg.get('speaker', '')
                    has_overlap = speaker_seg.get('has_overlap', False)
            
            # Get uncertainty info
            uncertainty_level = "medium"
            quality_flag = ""
            if uncertainty_result:
                uncertain_seg = next((s for s in uncertainty_result.uncertain_segments 
                                    if s.segment_id == segment.id), None)
                if uncertain_seg:
                    uncertainty_level = uncertain_seg.uncertainty_level
                    if uncertain_seg.suggested_review:
                        quality_flag = "REVIEW_NEEDED"
            
            row = [
                segment.id,
                segment.start,
                segment.end,
                duration,
                segment.text,
                segment.avg_logprob,
                segment.no_speech_prob,
                speaker,
                has_overlap,
                uncertainty_level,
                quality_flag
            ]
            
            writer.writerow(row)

def format_srt_time(seconds: float) -> str:
    """Format time for SRT subtitle format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

def main():
    """Main execution function."""
    video_path = Path("processing/x.com_elder_plinius_status_1945128977766441106_01.mp4")
    output_dir = Path("processing/advanced_results")
    
    if not video_path.exists():
        print(f"❌ Video file not found: {video_path}")
        return False
    
    results = advanced_transcription(video_path, output_dir)
    
    # Save processing report
    report_file = output_dir / "processing_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📋 Processing report saved: {report_file}")
    
    success = results['performance_metrics'].get('success_rate', 0) >= 80
    print(f"🎯 Overall Success: {'PASS' if success else 'PARTIAL'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)