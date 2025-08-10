"""
TalkGPT Environment Loader

Centralized environment variable loading from .env files with fallback handling.
"""

import os
from pathlib import Path
from typing import Optional


def load_environment_variables(env_file_path: Optional[Path] = None) -> bool:
    """
    Load environment variables from .env file.
    
    Args:
        env_file_path: Optional path to .env file. If None, searches for .env in project root.
        
    Returns:
        True if .env file was loaded successfully, False otherwise.
    """
    try:
        from dotenv import load_dotenv
        
        # Determine .env file path
        if env_file_path is None:
            # Try to find project root by looking for AGENTS.md or .env file
            current_path = Path(__file__).resolve()
            for parent in [current_path.parent.parent.parent, current_path.parent.parent]:
                env_candidate = parent / '.env'
                if env_candidate.exists():
                    env_file_path = env_candidate
                    break
            
            # If still not found, default to project root
            if env_file_path is None:
                env_file_path = current_path.parent.parent.parent / '.env'
        
        # Load .env file if it exists
        if env_file_path.exists():
            load_dotenv(env_file_path)
            return True
        else:
            # Create a minimal .env file if it doesn't exist
            _create_default_env_file(env_file_path)
            load_dotenv(env_file_path)
            return True
            
    except ImportError:
        # python-dotenv not available, set critical environment variables manually
        _set_fallback_environment_variables()
        return False


def _create_default_env_file(env_file_path: Path) -> None:
    """Create a default .env file with essential environment variables."""
    default_env_content = """# TalkGPT Environment Configuration
# Auto-generated default configuration

# OpenMP Configuration - Fix for multiple OpenMP runtime libraries
KMP_DUPLICATE_LIB_OK=TRUE

# PyTorch Configuration
OMP_NUM_THREADS=8
MKL_NUM_THREADS=8

# Logging Configuration
PYTHONUNBUFFERED=1
"""
    
    try:
        env_file_path.parent.mkdir(parents=True, exist_ok=True)
        env_file_path.write_text(default_env_content, encoding='utf-8')
    except Exception:
        # If we can't write the file, that's okay, we'll use fallback
        pass


def _set_fallback_environment_variables() -> None:
    """Set critical environment variables manually as fallback."""
    fallback_vars = {
        'KMP_DUPLICATE_LIB_OK': 'TRUE',
        'OMP_NUM_THREADS': '8',
        'MKL_NUM_THREADS': '8',
        'PYTHONUNBUFFERED': '1',
    }
    
    for var, value in fallback_vars.items():
        if var not in os.environ:
            os.environ[var] = value


def ensure_environment_loaded() -> None:
    """
    Ensure environment variables are loaded.
    
    This function should be called at the start of any main entry point
    to guarantee that environment variables are properly configured.
    """
    # First set critical variables immediately if not already set
    critical_vars = {
        'KMP_DUPLICATE_LIB_OK': 'TRUE',
        'OMP_NUM_THREADS': '8',
        'MKL_NUM_THREADS': '8',
        'PYTHONUNBUFFERED': '1',
    }
    
    for var, value in critical_vars.items():
        if var not in os.environ:
            os.environ[var] = value
    
    # Then try to load from .env file for additional variables
    load_environment_variables()


def set_openmp_environment() -> None:
    """
    Set OpenMP environment variables immediately.
    
    This should be called as early as possible, before any library imports
    that might use OpenMP (like PyTorch, NumPy, etc.).
    """
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    os.environ['OMP_NUM_THREADS'] = '8'
    os.environ['MKL_NUM_THREADS'] = '8'


# Auto-load critical environment variables when this module is imported
set_openmp_environment()
ensure_environment_loaded()

