"""
TalkGPT Logging System

Comprehensive logging setup with Rich console output, file logging,
per-file logs, and structured logging for production environments.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel
import structlog

try:
    from .config import LoggingConfig, get_config
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from config import LoggingConfig, get_config


class TalkGPTLogger:
    """
    Centralized logging system for TalkGPT.
    
    Provides console logging with Rich formatting, file logging,
    per-file processing logs, and structured logging capabilities.
    """
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Initialize the logging system.
        
        Args:
            config: Logging configuration, uses global config if None
        """
        if config is None:
            try:
                self.config = get_config().logging
            except RuntimeError:
                # Fallback to default logging config if global config not loaded
                from .config import LoggingConfig
                self.config = LoggingConfig()
        else:
            self.config = config
        self.console = Console()
        self.loggers: Dict[str, logging.Logger] = {}
        self.progress: Optional[Progress] = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup the main logging configuration."""
        # Create log directory
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.level))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Setup console handler
        if self.config.console_format == "rich":
            console_handler = RichHandler(
                console=self.console,
                show_time=True,
                show_path=True,
                markup=True,
                rich_tracebacks=True
            )
            console_format = "%(message)s"
        else:
            console_handler = logging.StreamHandler(sys.stdout)
            if self.config.console_format == "json":
                console_format = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
            else:
                console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        console_handler.setFormatter(logging.Formatter(console_format))
        root_logger.addHandler(console_handler)
        
        # Setup main file handler
        main_log_file = log_dir / "talkgpt.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=self.config.max_log_files
        )
        
        if self.config.file_format == "json":
            file_format = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d, "message": "%(message)s"}'
        else:
            file_format = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
        
        file_handler.setFormatter(logging.Formatter(file_format))
        root_logger.addHandler(file_handler)
        
        # Setup structured logging
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module.
        
        Args:
            name: Logger name (usually module name)
            
        Returns:
            Configured logger instance
        """
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]
    
    def get_file_logger(self, filename: str, task_id: Optional[str] = None) -> logging.Logger:
        """
        Get a dedicated logger for specific file processing.
        
        Args:
            filename: Name of the file being processed
            task_id: Optional task ID for tracking
            
        Returns:
            File-specific logger instance
        """
        if not self.config.per_file_logs:
            return self.get_logger("talkgpt.file")
        
        # Create unique logger name
        safe_filename = Path(filename).stem.replace(" ", "_").replace("-", "_")
        logger_name = f"talkgpt.file.{safe_filename}"
        if task_id:
            logger_name += f".{task_id}"
        
        if logger_name not in self.loggers:
            logger = logging.getLogger(logger_name)
            
            # Create file-specific handler
            log_dir = Path(self.config.log_dir)
            log_file = log_dir / f"{safe_filename}.log"
            
            file_handler = logging.FileHandler(log_file, mode='w')
            
            if self.config.file_format == "json":
                file_format = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "stage": "%(message)s"}'
            else:
                file_format = "%(asctime)s - %(levelname)s - %(message)s"
            
            file_handler.setFormatter(logging.Formatter(file_format))
            logger.addHandler(file_handler)
            logger.setLevel(getattr(logging, self.config.level))
            
            self.loggers[logger_name] = logger
        
        return self.loggers[logger_name]
    
    def log_system_info(self, hardware_info: Dict[str, Any]):
        """Log system hardware information."""
        logger = self.get_logger("talkgpt.system")
        
        table = Table(title="System Information")
        table.add_column("Component", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("CPU Cores", str(hardware_info.get('cpu_cores', 'Unknown')))
        table.add_row("Memory (GB)", f"{hardware_info.get('memory_gb', 0):.1f}")
        table.add_row("GPU Available", str(hardware_info.get('gpu_available', False)))
        table.add_row("GPU Count", str(hardware_info.get('gpu_count', 0)))
        table.add_row("Platform", hardware_info.get('platform', 'Unknown'))
        
        self.console.print(table)
        logger.info("System hardware detected", extra={"hardware_info": hardware_info})
    
    def log_transcription_start(self, file_path: str, settings: Dict[str, Any]):
        """
        Log the start of a transcription job.
        
        Args:
            file_path: Path to the audio file
            settings: Transcription settings
        """
        file_logger = self.get_file_logger(file_path)
        main_logger = self.get_logger("talkgpt.transcription")
        
        file_logger.info(f"Starting transcription of: {file_path}")
        file_logger.info(f"Settings: {json.dumps(settings, indent=2)}")
        
        main_logger.info(f"Started transcription: {Path(file_path).name}")
        
        # Rich console output
        panel = Panel(
            f"🎵 [bold blue]Starting Transcription[/bold blue]\n"
            f"File: [green]{Path(file_path).name}[/green]\n"
            f"Model: [yellow]{settings.get('model_size', 'unknown')}[/yellow]\n"
            f"Device: [cyan]{settings.get('device', 'unknown')}[/cyan]",
            title="TalkGPT"
        )
        self.console.print(panel)
    
    def log_transcription_complete(self, file_path: str, 
                                 duration: float, 
                                 output_files: Dict[str, str],
                                 metrics: Optional[Dict[str, Any]] = None):
        """
        Log completion of a transcription job.
        
        Args:
            file_path: Path to the audio file
            duration: Processing duration in seconds
            output_files: Dictionary of format -> output file path
            metrics: Optional performance metrics
        """
        file_logger = self.get_file_logger(file_path)
        main_logger = self.get_logger("talkgpt.transcription")
        
        file_logger.info(f"Transcription completed in {duration:.2f} seconds")
        file_logger.info(f"Output files: {json.dumps(output_files, indent=2)}")
        
        if metrics:
            file_logger.info(f"Performance metrics: {json.dumps(metrics, indent=2)}")
        
        main_logger.info(f"Completed transcription: {Path(file_path).name} ({duration:.2f}s)")
        
        # Rich console output
        panel = Panel(
            f"✅ [bold green]Transcription Complete[/bold green]\n"
            f"File: [green]{Path(file_path).name}[/green]\n"
            f"Duration: [yellow]{duration:.2f}s[/yellow]\n"
            f"Outputs: [cyan]{', '.join(output_files.keys())}[/cyan]",
            title="TalkGPT"
        )
        self.console.print(panel)
    
    def log_error(self, file_path: str, error: Exception, stage: str = "unknown"):
        """
        Log an error during processing.
        
        Args:
            file_path: Path to the file being processed
            error: Exception that occurred
            stage: Processing stage where error occurred
        """
        file_logger = self.get_file_logger(file_path)
        main_logger = self.get_logger("talkgpt.error")
        
        error_msg = f"Error in {stage}: {str(error)}"
        file_logger.error(error_msg, exc_info=True)
        main_logger.error(f"Processing error: {Path(file_path).name} - {error_msg}")
        
        # Rich console output
        self.console.print(f"❌ [bold red]Error:[/bold red] {error_msg}")
    
    def create_progress_bar(self, description: str = "Processing") -> Progress:
        """
        Create a Rich progress bar for long-running operations.
        
        Args:
            description: Description of the operation
            
        Returns:
            Progress bar instance
        """
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console
        )
        return self.progress
    
    def log_performance_metrics(self, metrics: Dict[str, Any]):
        """
        Log performance metrics.
        
        Args:
            metrics: Performance metrics dictionary
        """
        logger = self.get_logger("talkgpt.performance")
        logger.info("Performance metrics", extra={"metrics": metrics})
        
        # Rich table output
        table = Table(title="Performance Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in metrics.items():
            if isinstance(value, float):
                value_str = f"{value:.2f}"
            else:
                value_str = str(value)
            table.add_row(key.replace("_", " ").title(), value_str)
        
        self.console.print(table)
    
    def cleanup(self):
        """Clean up logging resources."""
        if self.progress:
            self.progress.stop()
        
        # Close all file handlers
        for logger in self.loggers.values():
            for handler in logger.handlers[:]:
                if isinstance(handler, (logging.FileHandler, logging.handlers.RotatingFileHandler)):
                    handler.close()
                    logger.removeHandler(handler)


# Global logger instance
_global_logger: Optional[TalkGPTLogger] = None


def get_logger(name: str = "talkgpt") -> logging.Logger:
    """Get a logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = TalkGPTLogger()
    return _global_logger.get_logger(name)


def get_file_logger(filename: str, task_id: Optional[str] = None) -> logging.Logger:
    """Get a file-specific logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = TalkGPTLogger()
    return _global_logger.get_file_logger(filename, task_id)


def setup_logging(config: Optional[LoggingConfig] = None) -> TalkGPTLogger:
    """Setup the global logging system."""
    global _global_logger
    _global_logger = TalkGPTLogger(config)
    return _global_logger


def get_talkgpt_logger() -> TalkGPTLogger:
    """Get the global TalkGPT logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = TalkGPTLogger()
    return _global_logger