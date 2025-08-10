"""
TalkGPT - AI-Powered Transcription Pipeline

A modular, high-performance transcription system built on OpenAI Whisper Fast Large.
"""

__version__ = "0.1.0"
__author__ = "TalkGPT Team"

# Core imports
from .utils.config import ConfigManager, TalkGPTConfig, get_config, load_config
from .utils.logger import TalkGPTLogger, get_logger, setup_logging
from .core.resource_detector import ResourceDetector, detect_hardware, get_device_config
from .core.file_processor import FileProcessor, get_file_processor

__all__ = [
    "ConfigManager", "TalkGPTConfig", "get_config", "load_config",
    "TalkGPTLogger", "get_logger", "setup_logging", 
    "ResourceDetector", "detect_hardware", "get_device_config",
    "FileProcessor", "get_file_processor"
]
