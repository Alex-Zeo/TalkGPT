"""
TalkGPT Command Line Interface

Main CLI entry point providing comprehensive command-line access
to all TalkGPT transcription pipeline features.
"""

# CRITICAL: Set environment variables BEFORE any other imports
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['MKL_NUM_THREADS'] = '8'
os.environ['PYTHONUNBUFFERED'] = '1'

import sys
import click
from pathlib import Path
from typing import Optional, List

try:
    from ..utils.config import ConfigManager, load_config
    from ..utils.logger import setup_logging, get_talkgpt_logger
    from ..core.resource_detector import detect_hardware
    # Ensure console is UTF-8 friendly on Windows terminals
    from ..utils.encoding import force_utf8_stdio
except ImportError:
    # Fallback for direct execution
    sys.path.append(str(Path(__file__).parent.parent))
    from utils.config import ConfigManager, load_config
    from utils.logger import setup_logging, get_talkgpt_logger
    from core.resource_detector import detect_hardware


# Global context for CLI
class CLIContext:
    """CLI context for sharing state between commands."""
    def __init__(self):
        self.config = None
        self.logger = None
        self.verbose = False
        self.quiet = False


pass_context = click.make_pass_decorator(CLIContext, ensure=True)


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='Configuration file path')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              default='INFO', help='Logging level')
@click.option('--quiet', '-q', is_flag=True, help='Suppress console output')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.version_option(version='0.1.0', prog_name='TalkGPT')
@pass_context
def cli(ctx: CLIContext, config: Optional[str], log_level: str, quiet: bool, verbose: bool):
    """
    TalkGPT - AI-Powered Transcription Pipeline
    
    A high-performance transcription system built on OpenAI Whisper Fast Large
    with advanced features for speaker analysis and quality assessment.
    """
    # Force UTF-8 stdio early for Windows console safety
    try:
        force_utf8_stdio()
    except Exception:
        pass

    ctx.quiet = quiet
    ctx.verbose = verbose
    
    try:
        # Load configuration
        if config:
            config_manager = ConfigManager()
            ctx.config = config_manager.load_config(Path(config).stem)
        else:
            ctx.config = load_config("default")
        
        # Override log level if specified
        if log_level != 'INFO':
            ctx.config.logging.level = log_level
        
        if quiet:
            ctx.config.logging.level = 'ERROR'
        elif verbose:
            ctx.config.logging.level = 'DEBUG'
        
        # Setup logging
        ctx.logger = setup_logging(ctx.config.logging)
        
        if not quiet:
            click.echo("TalkGPT v0.1.0 - Transcription Pipeline")
            if verbose:
                click.echo(f"Config: {ctx.config.transcription.model_size} model on {ctx.config.transcription.device}")
        
    except Exception as e:
        click.echo(f"Initialization failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), 
              help='Output directory (default: same as input)')
@click.option('--format', '-f', 'formats', multiple=True, 
              type=click.Choice(['srt', 'json', 'txt', 'csv']),
              help='Output formats (can be used multiple times)')
@click.option('--speed-multiplier', '-s', type=float, 
              help='Audio speed multiplier (1.0-3.0)')
@click.option('--workers', '-w', type=int, 
              help='Number of parallel workers')
@click.option('--device', type=click.Choice(['auto', 'cpu', 'cuda', 'mps']),
              help='Processing device (auto-routes compute type for accuracy)')
@click.option('--language', '-l', type=str, 
              help='Audio language (auto-detect if not specified)')
@click.option('--analyze-speakers/--no-analyze-speakers', default=None,
              help='Enable/disable speaker analysis')
@click.option('--analyze-uncertainty/--no-analyze-uncertainty', default=None,
              help='Enable/disable uncertainty detection')
@click.option('--remove-silence/--keep-silence', default=None,
              help='Remove silence from audio')
@click.option('--bucket-seconds', type=float, default=4.0,
              help='Target duration for timing buckets in seconds (default: 4.0)')
@click.option('--gap-tolerance', type=float, default=0.25,
              help='Tolerance for bucket duration in seconds (default: 0.25)')
@click.option('--gap-threshold', type=float, default=1.5,
              help='Standard deviations for cadence classification (default: 1.5)')
@click.option('--enhanced-analysis/--standard-analysis', default=False,
              help='Enable enhanced word-gap analysis with 4-second windows')
@click.option('--timing-repair/--no-timing-repair', default=True,
              help='Repair zero-length word timings with 20ms epsilon')
@click.option('--diarization-backend', type=click.Choice(['auto','pyannote','speechbrain','none']), default='auto',
              help='Diarization backend selection (auto routes by OS and availability)')
@pass_context
def transcribe(ctx: CLIContext, input_path: str, output: Optional[str], 
               formats: List[str], speed_multiplier: Optional[float],
               workers: Optional[int], device: Optional[str], 
               language: Optional[str], analyze_speakers: Optional[bool],
               analyze_uncertainty: Optional[bool], remove_silence: Optional[bool],
               bucket_seconds: float, gap_tolerance: float, gap_threshold: float,
               enhanced_analysis: bool, timing_repair: bool,
               diarization_backend: str):
    """
    Transcribe a single audio or video file.
    
    INPUT_PATH can be any supported audio/video file format.
    The transcription will be saved in the specified output formats.
    """
    from .commands.transcribe import transcribe_single_file
    
    # Prepare options
    options = {
        'formats': list(formats) if formats else None,
        'speed_multiplier': speed_multiplier,
        'workers': workers,
        'device': device,
        'language': language,
        'analyze_speakers': analyze_speakers,
        'analyze_uncertainty': analyze_uncertainty,
        'remove_silence': remove_silence,
        'bucket_seconds': bucket_seconds,
        'gap_tolerance': gap_tolerance,
        'gap_threshold': gap_threshold,
        'enhanced_analysis': enhanced_analysis,
        'timing_repair': timing_repair,
        'diarization_backend': diarization_backend
    }
    
    # Remove None values
    options = {k: v for k, v in options.items() if v is not None}
    
    try:
        result = transcribe_single_file(
            input_path=Path(input_path),
            output_dir=Path(output) if output else None,
            config=ctx.config,
            logger=ctx.logger,
            **options
        )
        
        if not ctx.quiet:
            click.echo(f"Transcription completed: {result['output_files']}")
            if ctx.verbose:
                click.echo(f"Processing time: {result['processing_time']:.2f}s")
                click.echo(f"Quality score: {result.get('quality_score', 'N/A')}")
        
    except Exception as e:
        click.echo(f"Transcription failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False))
@click.option('--output', '-o', type=click.Path(), required=True,
              help='Output directory for all transcriptions')
@click.option('--format', '-f', 'formats', multiple=True,
              type=click.Choice(['srt', 'json', 'txt', 'csv']),
              help='Output formats (can be used multiple times)')
@click.option('--pattern', '-p', type=str, default='*',
              help='File pattern to match (e.g., "*.mp3")')
@click.option('--recursive/--no-recursive', default=True,
              help='Search subdirectories recursively')
@click.option('--workers', '-w', type=int,
              help='Number of parallel workers')
@click.option('--max-files', type=int,
              help='Maximum number of files to process')
@click.option('--continue-on-error/--stop-on-error', default=True,
              help='Continue processing if individual files fail')
@click.option('--queue/--no-queue', default=False,
              help='Enqueue jobs to Celery instead of inline processing')
@pass_context
def batch(ctx: CLIContext, input_dir: str, output: str, formats: List[str],
          pattern: str, recursive: bool, workers: Optional[int],
          max_files: Optional[int], continue_on_error: bool, queue: bool):
    """
    Process multiple audio/video files in batch.
    
    INPUT_DIR should contain audio/video files to process.
    All transcriptions will be saved to the OUTPUT directory.
    """
    from .commands.batch import process_batch
    
    options = {
        'formats': list(formats) if formats else None,
        'pattern': pattern,
        'recursive': recursive,
        'workers': workers,
        'max_files': max_files,
        'continue_on_error': continue_on_error,
        'queue': queue
    }
    
    # Remove None values
    options = {k: v for k, v in options.items() if v is not None}
    
    try:
        result = process_batch(
            input_dir=Path(input_dir),
            output_dir=Path(output),
            config=ctx.config,
            logger=ctx.logger,
            **options
        )
        
        if not ctx.quiet:
            click.echo("Batch processing completed:")
            click.echo(f"   Files processed: {result['successful']}/{result['total']}")
            click.echo(f"   Total time: {result['total_time']:.2f}s")
            if result['failed'] > 0:
                click.echo(f"   Failed: {result['failed']}")
            if result.get('queued'):
                click.echo(f"   Queued jobs: {len(result['queued'])}")
        
    except Exception as e:
        click.echo(f"Batch processing failed: {e}", err=True)
        sys.exit(1)


@cli.group()
@pass_context
def config(ctx: CLIContext):
    """Configuration management commands."""
    pass


@config.command('show')
@click.option('--section', type=str, help='Show specific configuration section')
@click.option('--quiet', '-q', is_flag=True, help='Quiet output')
@pass_context
def config_show(ctx: CLIContext, section: Optional[str], quiet: bool):
    """Show current configuration."""
    from .commands.config import show_config
    
    try:
        show_config(ctx.config, section, quiet or ctx.quiet)
    except Exception as e:
        click.echo(f"Failed to show config: {e}", err=True)
        sys.exit(1)


@config.command('set')
@click.argument('key')
@click.argument('value')
@click.option('--save', is_flag=True, help='Save changes to config file')
@pass_context
def config_set(ctx: CLIContext, key: str, value: str, save: bool):
    """Set a configuration value."""
    from .commands.config import set_config_value
    
    try:
        set_config_value(ctx.config, key, value, save, ctx.quiet)
    except Exception as e:
        click.echo(f"Failed to set config: {e}", err=True)
        sys.exit(1)


@config.command('validate')
@pass_context
def config_validate(ctx: CLIContext):
    """Validate current configuration."""
    from .commands.config import validate_config
    
    try:
        is_valid = validate_config(ctx.config, ctx.quiet)
        if not is_valid:
            sys.exit(1)
    except Exception as e:
        click.echo(f"Config validation failed: {e}", err=True)
        sys.exit(1)


@cli.group()
@pass_context
def status(ctx: CLIContext):
    """System status and monitoring commands."""
    pass


@status.command('system')
@click.option('--quiet', '-q', is_flag=True, help='Quiet output')
@pass_context
def status_system(ctx: CLIContext, quiet: bool):
    """Show system hardware and capabilities."""
    from .commands.status import show_system_status
    
    try:
        show_system_status(quiet or ctx.quiet)
    except Exception as e:
        click.echo(f"Failed to get system status: {e}", err=True)
        sys.exit(1)


@status.command('jobs')
@pass_context
def status_jobs(ctx: CLIContext):
    """Show active transcription jobs (if using workers)."""
    from .commands.status import show_job_status
    
    try:
        show_job_status(ctx.quiet)
    except Exception as e:
        click.echo(f"Failed to get job status: {e}", err=True)
        sys.exit(1)


@cli.group()
@pass_context
def analyze(ctx: CLIContext):
    """Advanced analysis commands."""
    pass


@cli.command()
@pass_context
def doctor(ctx: CLIContext):
    """Run environment preflight checks (Windows & cross-platform)."""
    import platform, shutil, os
    from .commands.transcribe import get_speaker_analyzer
    from ..core.resource_detector import detect_hardware
    from ..utils.encoding import safe_console_text

    ok = True
    # FFmpeg
    if not shutil.which("ffmpeg"):
        click.echo("FFmpeg: MISSING (install and add to PATH)")
        ok = False
    else:
        click.echo("FFmpeg: OK")

    # Hardware
    hw = detect_hardware()
    click.echo(safe_console_text(f"Device: {hw.recommended_device}, CPU cores: {hw.cpu_cores}, RAM: {hw.memory_gb:.1f} GB"))

    # Console encoding
    enc = (getattr(sys.stdout, 'encoding', '') or '').lower()
    click.echo(f"Console encoding: {enc or 'unknown'}")

    # HF token check on non-Windows for pyannote
    if platform.system().lower() != 'windows':
        token = os.getenv('HUGGINGFACE_TOKEN')
        if not token:
            click.echo("HuggingFace token: MISSING (set HUGGINGFACE_TOKEN for pyannote)")
        else:
            click.echo("HuggingFace token: PRESENT")

    click.echo("Doctor: " + ("PASS" if ok else "ISSUES FOUND"))


@analyze.command('speakers')
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), 
              help='Output file for speaker analysis')
@click.option('--format', type=click.Choice(['json', 'rttm']), default='json',
              help='Output format')
@pass_context
def analyze_speakers(ctx: CLIContext, input_path: str, output: Optional[str], format: str):
    """Perform speaker diarization analysis on an audio file."""
    from .commands.analyze import analyze_speakers_command
    
    try:
        result = analyze_speakers_command(
            input_path=Path(input_path),
            output_path=Path(output) if output else None,
            format=format,
            config=ctx.config,
            logger=ctx.logger
        )
        
        if not ctx.quiet:
            click.echo("Speaker analysis completed:")
            click.echo(f"   Speakers detected: {result['speaker_count']}")
            click.echo(f"   Segments: {result['segments']}")
            click.echo(f"   Overlaps: {result['overlaps']}")
        
    except Exception as e:
        click.echo(f"Speaker analysis failed: {e}", err=True)
        sys.exit(1)


@analyze.command('quality')
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(),
              help='Output file for quality analysis')
@click.option('--threshold', type=float, default=-1.0,
              help='Confidence threshold for flagging segments')
@pass_context
def analyze_quality(ctx: CLIContext, input_path: str, output: Optional[str], threshold: float):
    """Analyze transcription quality and uncertainty."""
    from .commands.analyze import analyze_quality_command
    
    try:
        result = analyze_quality_command(
            input_path=Path(input_path),
            output_path=Path(output) if output else None,
            threshold=threshold,
            config=ctx.config,
            logger=ctx.logger
        )
        
        if not ctx.quiet:
            click.echo("Quality analysis completed:")
            try:
                click.echo(f"   Quality score: {result['quality_score']:.2f}")
            except Exception:
                click.echo(f"   Quality score: {result.get('quality_score','N/A')}")
            click.echo(f"   Flagged segments: {result.get('flagged_segments','N/A')}")
            if 'flagged_percentage' in result:
                click.echo(f"   Flagged percentage: {result['flagged_percentage']:.1f}%")
        
    except Exception as e:
        click.echo(f"Quality analysis failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--duration', type=int, default=30, help='Benchmark duration in seconds')
@click.option('--sample-files', type=click.Path(exists=True, file_okay=False),
              help='Directory with sample audio files for testing')
@pass_context
def benchmark(ctx: CLIContext, duration: int, sample_files: Optional[str]):
    """Run performance benchmarks."""
    from .commands.benchmark import run_benchmark
    
    try:
        result = run_benchmark(
            duration=duration,
            sample_dir=Path(sample_files) if sample_files else None,
            config=ctx.config,
            logger=ctx.logger
        )
        
        if not ctx.quiet:
            click.echo("Benchmark completed:")
            click.echo(f"   Processing speed: {result['processing_speed']:.1f}x real-time")
            click.echo(f"   Memory usage: {result['memory_usage']:.1f}%")
            click.echo(f"   CPU usage: {result['cpu_usage']:.1f}%")
        
    except Exception as e:
        click.echo(f"Benchmark failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--duration', type=int, default=60, help='Stream duration in seconds')
@click.option('--device', type=int, default=None, help='Input device index (optional)')
@click.option('--language', type=str, default=None, help='Language code (optional)')
@click.option('--chunk-seconds', type=float, default=5.0, help='Chunk size in seconds')
@click.option('--overlap-seconds', type=float, default=1.0, help='Overlap between chunks (context)')
@pass_context
def stream(ctx: CLIContext, duration: int, device: Optional[int], language: Optional[str], chunk_seconds: float, overlap_seconds: float):
    """Real-time streaming transcription (microphone)."""
    from .commands.stream import stream_transcription

    try:
        ok = stream_transcription(
            duration=duration,
            device=device,
            language=language,
            chunk_seconds=chunk_seconds,
            overlap_seconds=overlap_seconds,
            config=ctx.config,
            logger=ctx.logger,
        )
        if not ok:
            sys.exit(1)
    except Exception as e:
        click.echo(f"Streaming failed: {e}", err=True)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()