"""
TalkGPT Configuration Management System

Handles loading, validation, and management of configuration settings
from YAML files with environment variable overrides and validation.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from dataclasses import dataclass


class ProcessingConfig(BaseModel):
    """Processing configuration settings."""
    # Accuracy-first: avoid speed-up by default
    speed_multiplier: float = Field(default=1.0, ge=1.0, le=3.0)
    max_workers: Optional[int] = Field(default=None, ge=1)
    chunk_size: int = Field(default=30, ge=5, le=300)
    overlap_duration: int = Field(default=5, ge=0, le=30)
    silence_threshold: float = Field(default=-40, ge=-60, le=-20)
    min_silence_len: int = Field(default=1000, ge=100)
    remove_silence: bool = True


class TranscriptionConfig(BaseModel):
    """Transcription engine configuration."""
    model_size: str = Field(default="large-v3")
    device: str = Field(default="auto")
    # Accuracy-first: CPU float32, GPU float16 (auto-routed at runtime)
    compute_type: str = Field(default="float32")
    language: Optional[str] = None
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    beam_size: int = Field(default=5, ge=1, le=10)
    best_of: int = Field(default=5, ge=1, le=10)
    patience: float = Field(default=1.0, ge=0.0, le=2.0)
    
    @validator('model_size')
    def validate_model_size(cls, v):
        valid_models = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
        if v not in valid_models:
            raise ValueError(f"Invalid model size. Must be one of: {valid_models}")
        return v
    
    @validator('device')
    def validate_device(cls, v):
        valid_devices = ["auto", "cpu", "cuda", "mps"]
        if v not in valid_devices:
            raise ValueError(f"Invalid device. Must be one of: {valid_devices}")
        return v
    
    @validator('compute_type')
    def validate_compute_type(cls, v):
        valid_types = ["auto", "float16", "int8", "float32"]
        if v not in valid_types:
            raise ValueError(f"Invalid compute type. Must be one of: {valid_types}")
        return v


class OutputConfig(BaseModel):
    """Output generation configuration."""
    formats: list = Field(default=["srt", "json", "txt"])
    include_timestamps: bool = True
    include_confidence: bool = True
    speaker_labels: bool = True
    word_timestamps: bool = False
    
    @validator('formats')
    def validate_formats(cls, v):
        valid_formats = ["srt", "json", "txt", "csv"]
        for fmt in v:
            if fmt not in valid_formats:
                raise ValueError(f"Invalid format '{fmt}'. Must be one of: {valid_formats}")
        return v


class TimingAnalysisConfig(BaseModel):
    """Timing analysis configuration."""
    bucket_seconds: float = Field(default=4.0, ge=1.0, le=10.0)
    bucket_tolerance: float = Field(default=0.25, ge=0.0, le=1.0)
    gap_threshold: float = Field(default=1.5, ge=0.5, le=5.0)
    gap_list_max: int = Field(default=20, ge=5, le=100)
    variance_threshold: float = Field(default=1.5, ge=0.5, le=5.0)


class AnalyticsConfig(BaseModel):
    """Analytics and advanced features configuration."""
    enable_speaker_diarization: bool = True
    enable_uncertainty_detection: bool = True
    enable_timing_analysis: bool = True
    confidence_threshold: float = Field(default=-1.0, ge=-5.0, le=0.0)
    min_speakers: Optional[int] = Field(default=None, ge=1)
    max_speakers: Optional[int] = Field(default=None, ge=1)
    timing: TimingAnalysisConfig = TimingAnalysisConfig()


class LoggingConfig(BaseModel):
    """Logging system configuration."""
    level: str = Field(default="INFO")
    console_format: str = Field(default="rich")
    file_format: str = Field(default="detailed")
    per_file_logs: bool = True
    log_dir: str = "logs"
    max_log_files: int = Field(default=100, ge=1)
    
    @validator('level')
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v.upper()
    
    @validator('console_format')
    def validate_console_format(cls, v):
        valid_formats = ["rich", "simple", "json"]
        if v not in valid_formats:
            raise ValueError(f"Invalid console format. Must be one of: {valid_formats}")
        return v


class ResourcesConfig(BaseModel):
    """Resource management configuration."""
    max_memory_gb: Optional[float] = Field(default=None, ge=1.0)
    gpu_memory_fraction: float = Field(default=0.9, ge=0.1, le=1.0)
    cpu_threads: Optional[int] = Field(default=None, ge=1)


class TalkGPTConfig(BaseModel):
    """Main TalkGPT configuration model."""
    processing: ProcessingConfig = ProcessingConfig()
    transcription: TranscriptionConfig = TranscriptionConfig()
    output: OutputConfig = OutputConfig()
    analytics: AnalyticsConfig = AnalyticsConfig()
    logging: LoggingConfig = LoggingConfig()
    resources: ResourcesConfig = ResourcesConfig()


class ConfigManager:
    """
    Configuration manager for TalkGPT.
    
    Handles loading configuration from YAML files, environment variables,
    and provides validation and access to configuration settings.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir or Path(__file__).parent.parent.parent / "config"
        self._config: Optional[TalkGPTConfig] = None
        self._config_cache: Dict[str, Any] = {}
    
    def load_config(self, 
                   config_name: str = "default",
                   overrides: Optional[Dict[str, Any]] = None) -> TalkGPTConfig:
        """
        Load configuration from YAML file with optional overrides.
        
        Args:
            config_name: Name of config file (without .yaml extension)
            overrides: Dictionary of configuration overrides
            
        Returns:
            Validated TalkGPT configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        config_file = self.config_dir / f"{config_name}.yaml"
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        # Load base configuration
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Apply environment variable overrides
        config_data = self._apply_env_overrides(config_data)
        
        # Apply manual overrides
        if overrides:
            config_data = self._merge_config(config_data, overrides)
        
        # Validate and create configuration object
        try:
            self._config = TalkGPTConfig(**config_data)
            return self._config
        except Exception as e:
            raise ValueError(f"Invalid configuration: {e}")
    
    def get_config(self) -> TalkGPTConfig:
        """
        Get current configuration.
        
        Returns:
            Current TalkGPT configuration
            
        Raises:
            RuntimeError: If no configuration is loaded
        """
        if self._config is None:
            raise RuntimeError("No configuration loaded. Call load_config() first.")
        return self._config
    
    def save_config(self, config: TalkGPTConfig, filename: str):
        """
        Save configuration to YAML file.
        
        Args:
            config: Configuration to save
            filename: Output filename (without .yaml extension)
        """
        output_file = self.config_dir / f"{filename}.yaml"
        
        # Convert to dictionary
        config_dict = config.dict()
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
    
    def validate_config(self, config_data: Dict[str, Any]) -> bool:
        """
        Validate configuration data.
        
        Args:
            config_data: Configuration dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            TalkGPTConfig(**config_data)
            return True
        except Exception:
            return False
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        env_mappings = {
            'TALKGPT_WORKERS': ('processing', 'max_workers'),
            'TALKGPT_DEVICE': ('transcription', 'device'),
            'TALKGPT_MODEL': ('transcription', 'model_size'),
            'TALKGPT_SPEED': ('processing', 'speed_multiplier'),
            'TALKGPT_LOG_LEVEL': ('logging', 'level'),
        }
        
        for env_var, (section, key) in env_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                
                # Type conversion
                if key in ['max_workers', 'cpu_threads']:
                    value = int(value) if value.lower() != 'null' else None
                elif key in ['speed_multiplier', 'confidence_threshold', 'gpu_memory_fraction']:
                    value = float(value)
                elif key in ['remove_silence', 'include_timestamps', 'speaker_labels']:
                    value = value.lower() in ('true', '1', 'yes', 'on')
                
                if section not in config_data:
                    config_data[section] = {}
                config_data[section][key] = value
        
        return config_data
    
    def _merge_config(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries."""
        result = base.copy()
        
        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result


# Global configuration manager instance
config_manager = ConfigManager()


def get_config() -> TalkGPTConfig:
    """Get the global configuration instance."""
    return config_manager.get_config()


def load_config(config_name: str = "default", **overrides) -> TalkGPTConfig:
    """Load configuration with the global manager."""
    return config_manager.load_config(config_name, overrides)