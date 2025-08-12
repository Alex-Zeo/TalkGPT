"""
TalkGPT CLI Configuration Commands

Configuration management, validation, and display commands.
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

try:
    from ...utils.config import TalkGPTConfig, ConfigManager
    from ...core.resource_detector import get_resource_detector
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from utils.config import TalkGPTConfig, ConfigManager
    from core.resource_detector import get_resource_detector


def show_config(config: TalkGPTConfig, section: str = None, quiet: bool = False):
    """Display current configuration."""
    console = Console()
    
    if quiet:
        # Simple output for quiet mode
        if section:
            section_config = getattr(config, section, None)
            if section_config:
                for key, value in section_config.__dict__.items():
                    click.echo(f"{section}.{key}={value}")
            else:
                click.echo(f"Section '{section}' not found")
        else:
            # Show all sections briefly
            click.echo(f"Model: {config.transcription.model_size}")
            click.echo(f"Device: {config.transcription.device}")
            click.echo(f"Workers: {config.processing.max_workers}")
            click.echo(f"Speed: {config.processing.speed_multiplier}x")
        return
    
    console.print("⚙️  [bold blue]TalkGPT Configuration[/bold blue]")
    
    if section:
        _show_config_section(console, config, section)
    else:
        _show_all_config_sections(console, config)


def _show_config_section(console: Console, config: TalkGPTConfig, section_name: str):
    """Show a specific configuration section."""
    section_config = getattr(config, section_name, None)
    if not section_config:
        console.print(f"❌ [red]Section '{section_name}' not found[/red]")
        console.print("Available sections: processing, transcription, output, analytics, logging, resources")
        return
    
    table = Table(title=f"{section_name.title()} Configuration")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_column("Description", style="yellow")
    
    # Get descriptions for common settings
    descriptions = _get_config_descriptions()
    
    for key, value in section_config.__dict__.items():
        desc_key = f"{section_name}.{key}"
        description = descriptions.get(desc_key, "")
        
        # Format value for display
        if isinstance(value, list):
            display_value = ", ".join(str(v) for v in value)
        elif value is None:
            display_value = "[dim]auto[/dim]"
        else:
            display_value = str(value)
        
        table.add_row(key, display_value, description)
    
    console.print(table)


def _show_all_config_sections(console: Console, config: TalkGPTConfig):
    """Show all configuration sections in a summary format."""
    
    # Processing Configuration
    proc_panel = Panel(
        f"Speed Multiplier: [green]{config.processing.speed_multiplier}x[/green]\n"
        f"Max Workers: [green]{config.processing.max_workers or 'auto'}[/green]\n"
        f"Chunk Size: [green]{config.processing.chunk_size}s[/green]\n"
        f"Overlap: [green]{config.processing.overlap_duration}s[/green]\n"
        f"Remove Silence: [green]{config.processing.remove_silence}[/green]",
        title="Processing Settings",
        border_style="blue"
    )
    console.print(proc_panel)
    
    # Transcription Configuration
    trans_panel = Panel(
        f"Model: [green]{config.transcription.model_size}[/green]\n"
        f"Device: [green]{config.transcription.device}[/green]\n"
        f"Compute Type: [green]{config.transcription.compute_type}[/green]\n"
        f"Language: [green]{config.transcription.language or 'auto-detect'}[/green]\n"
        f"Temperature: [green]{config.transcription.temperature}[/green]",
        title="Transcription Settings",
        border_style="green"
    )
    console.print(trans_panel)
    
    # Output Configuration
    output_panel = Panel(
        f"Formats: [green]{', '.join(config.output.formats)}[/green]\n"
        f"Include Timestamps: [green]{config.output.include_timestamps}[/green]\n"
        f"Include Confidence: [green]{config.output.include_confidence}[/green]\n"
        f"Speaker Labels: [green]{config.output.speaker_labels}[/green]\n"
        f"Word Timestamps: [green]{config.output.word_timestamps}[/green]",
        title="Output Settings",
        border_style="yellow"
    )
    console.print(output_panel)
    
    # Analytics Configuration
    analytics_panel = Panel(
        f"Speaker Diarization: [green]{config.analytics.enable_speaker_diarization}[/green]\n"
        f"Uncertainty Detection: [green]{config.analytics.enable_uncertainty_detection}[/green]\n"
        f"Confidence Threshold: [green]{config.analytics.confidence_threshold}[/green]\n"
        f"Min Speakers: [green]{config.analytics.min_speakers or 'auto'}[/green]\n"
        f"Max Speakers: [green]{config.analytics.max_speakers or 'auto'}[/green]",
        title="Analytics Settings",
        border_style="magenta"
    )
    console.print(analytics_panel)
    
    # Logging Configuration
    logging_panel = Panel(
        f"Level: [green]{config.logging.level}[/green]\n"
        f"Console Format: [green]{config.logging.console_format}[/green]\n"
        f"Per-File Logs: [green]{config.logging.per_file_logs}[/green]\n"
        f"Log Directory: [green]{config.logging.log_dir}[/green]",
        title="Logging Settings",
        border_style="cyan"
    )
    console.print(logging_panel)


def set_config_value(config: TalkGPTConfig, key: str, value: str, save: bool, quiet: bool = False):
    """Set a configuration value."""
    console = Console()
    
    try:
        # Parse the key (e.g., "processing.speed_multiplier")
        if '.' not in key:
            raise ValueError("Key must be in format 'section.setting' (e.g., 'processing.speed_multiplier')")
        
        section_name, setting_name = key.split('.', 1)
        
        # Get the section
        section = getattr(config, section_name, None)
        if section is None:
            raise ValueError(f"Unknown section: {section_name}")
        
        # Check if setting exists
        if not hasattr(section, setting_name):
            raise ValueError(f"Unknown setting: {setting_name} in section {section_name}")
        
        # Get current value to determine type
        current_value = getattr(section, setting_name)
        
        # Convert value to appropriate type
        converted_value = _convert_config_value(value, current_value)
        
        # Set the value
        setattr(section, setting_name, converted_value)
        
        if not quiet:
            console.print(f"✅ [green]Set {key} = {converted_value}[/green]")
        
        if save:
            # Persist to config/local.yaml by default
            try:
                manager = ConfigManager()
                manager.save_config(config, filename="local")
                if not quiet:
                    console.print("💾 [green]Saved to config/local.yaml[/green]")
            except Exception as e:
                if not quiet:
                    console.print(f"❌ [red]Failed to save config: {e}[/red]")
                raise
        else:
            if not quiet:
                console.print("ℹ️  [dim]Changes are temporary. Use --save to persist.[/dim]")
    
    except Exception as e:
        if quiet:
            click.echo(f"Error: {e}")
        else:
            console.print(f"❌ [red]Failed to set config: {e}[/red]")
        raise


def validate_config(config: TalkGPTConfig, quiet: bool = False) -> bool:
    """Validate current configuration."""
    console = Console()
    
    if not quiet:
        console.print("🔍 [bold blue]Validating Configuration[/bold blue]")
    
    errors = []
    warnings = []
    
    # Validate processing settings
    if config.processing.speed_multiplier < 1.0 or config.processing.speed_multiplier > 3.0:
        errors.append("Speed multiplier must be between 1.0 and 3.0")
    
    if config.processing.chunk_size < 5 or config.processing.chunk_size > 300:
        warnings.append("Chunk size outside recommended range (5-300 seconds)")
    
    if config.processing.overlap_duration >= config.processing.chunk_size:
        errors.append("Overlap duration must be less than chunk size")
    
    # Validate transcription settings
    valid_models = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    if config.transcription.model_size not in valid_models:
        errors.append(f"Invalid model size. Must be one of: {', '.join(valid_models)}")
    
    valid_devices = ["auto", "cpu", "cuda", "mps"]
    if config.transcription.device not in valid_devices:
        errors.append(f"Invalid device. Must be one of: {', '.join(valid_devices)}")
    
    # Validate output settings
    valid_formats = ["srt", "json", "txt", "csv"]
    for fmt in config.output.formats:
        if fmt not in valid_formats:
            errors.append(f"Invalid output format: {fmt}")
    
    # Validate analytics settings
    if config.analytics.confidence_threshold < -5.0 or config.analytics.confidence_threshold > 0.0:
        warnings.append("Confidence threshold outside typical range (-5.0 to 0.0)")
    
    # Hardware compatibility validation
    try:
        detector = get_resource_detector()
        hardware = detector.detect_hardware()
        
        # Check device compatibility
        if config.transcription.device == "cuda" and not hardware.gpu_available:
            errors.append("CUDA device specified but no GPU available")
        
        if config.transcription.device == "mps" and not hardware.mps_available:
            errors.append("MPS device specified but not available")
        
        # Check worker count
        if config.processing.max_workers and config.processing.max_workers > hardware.cpu_cores:
            warnings.append(f"Worker count ({config.processing.max_workers}) exceeds CPU cores ({hardware.cpu_cores})")
        
        # Validate configuration against hardware
        config_dict = {
            'max_workers': config.processing.max_workers or hardware.optimal_workers,
            'device': config.transcription.device,
            'model_size': config.transcription.model_size
        }
        
        is_valid, message = detector.validate_configuration(config_dict)
        if not is_valid:
            errors.append(f"Hardware validation failed: {message}")
        
    except Exception as e:
        warnings.append(f"Could not validate hardware compatibility: {e}")
    
    # Display results
    if quiet:
        if errors:
            for error in errors:
                click.echo(f"Error: {error}")
        if warnings:
            for warning in warnings:
                click.echo(f"Warning: {warning}")
        return len(errors) == 0
    
    if errors:
        error_panel = Panel(
            "\n".join(f"• {error}" for error in errors),
            title="❌ Configuration Errors",
            border_style="red"
        )
        console.print(error_panel)
    
    if warnings:
        warning_panel = Panel(
            "\n".join(f"• {warning}" for warning in warnings),
            title="⚠️  Configuration Warnings",
            border_style="yellow"
        )
        console.print(warning_panel)
    
    if not errors and not warnings:
        console.print("✅ [green]Configuration is valid![/green]")
    elif not errors:
        console.print("✅ [green]Configuration is valid with warnings[/green]")
    else:
        console.print("❌ [red]Configuration has errors that must be fixed[/red]")
    
    return len(errors) == 0


def _convert_config_value(value_str: str, current_value):
    """Convert string value to appropriate type based on current value."""
    if current_value is None:
        # Try to infer type
        if value_str.lower() in ('true', 'false'):
            return value_str.lower() == 'true'
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            return value_str
    
    # Convert based on current value type
    if isinstance(current_value, bool):
        return value_str.lower() in ('true', '1', 'yes', 'on')
    elif isinstance(current_value, int):
        return int(value_str)
    elif isinstance(current_value, float):
        return float(value_str)
    elif isinstance(current_value, list):
        # Handle comma-separated lists
        return [item.strip() for item in value_str.split(',')]
    else:
        return value_str


def _get_config_descriptions() -> dict:
    """Get descriptions for configuration settings."""
    return {
        'processing.speed_multiplier': 'Audio playback speed multiplier',
        'processing.max_workers': 'Maximum parallel workers (null = auto)',
        'processing.chunk_size': 'Audio chunk size in seconds',
        'processing.overlap_duration': 'Overlap between chunks in seconds',
        'processing.silence_threshold': 'Silence detection threshold in dB',
        'processing.remove_silence': 'Remove long silence segments',
        
        'transcription.model_size': 'Whisper model size',
        'transcription.device': 'Processing device (auto, cpu, cuda, mps)',
        'transcription.compute_type': 'Computation precision',
        'transcription.language': 'Audio language (null = auto-detect)',
        'transcription.temperature': 'Sampling temperature',
        
        'output.formats': 'Output file formats',
        'output.include_timestamps': 'Include detailed timestamps',
        'output.include_confidence': 'Include confidence scores',
        'output.speaker_labels': 'Include speaker identification',
        'output.word_timestamps': 'Include word-level timestamps',
        
        'analytics.enable_speaker_diarization': 'Enable speaker analysis',
        'analytics.enable_uncertainty_detection': 'Enable uncertainty detection',
        'analytics.confidence_threshold': 'Uncertainty threshold',
        
        'logging.level': 'Logging verbosity level',
        'logging.console_format': 'Console output format',
        'logging.per_file_logs': 'Create per-file log files',
        'logging.log_dir': 'Log file directory'
    }