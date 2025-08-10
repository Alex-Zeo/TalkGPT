#!/usr/bin/env python3
"""
TalkGPT Startup Script

This script ensures proper environment setup before running any TalkGPT functionality.
It should be used as the entry point for all TalkGPT operations to prevent OpenMP
and other library conflicts.
"""

# CRITICAL: Set environment variables FIRST, before any other imports
import os

# Set OpenMP environment variables to prevent library conflicts
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['MKL_NUM_THREADS'] = '8'
os.environ['PYTHONUNBUFFERED'] = '1'

# Additional PyTorch/NumPy optimizations
os.environ['MKL_SERVICE_FORCE_INTEL'] = '1'
os.environ['MKL_THREADING_LAYER'] = 'INTEL'

import sys
import subprocess
from pathlib import Path

def run_cli_with_args():
    """Run the CLI with proper environment setup."""
    # Add src to Python path
    src_path = Path(__file__).parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    # Import and run CLI
    try:
        from src.cli.main import main
        main()
    except ImportError:
        # Fallback: run as subprocess
        python_cmd = [sys.executable, "-m", "src.cli.main"] + sys.argv[1:]
        subprocess.run(python_cmd, cwd=Path(__file__).parent)

def run_advanced_transcription():
    """Run advanced transcription with proper environment setup."""
    # Add src to Python path
    src_path = Path(__file__).parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    # Import and run advanced transcription
    try:
        from advanced_transcription import main
        return main()
    except ImportError as e:
        print(f"Failed to import advanced transcription: {e}")
        return False

def main():
    """Main entry point that determines what to run based on arguments."""
    if len(sys.argv) > 1 and sys.argv[1] == "advanced":
        # Run advanced transcription
        success = run_advanced_transcription()
        sys.exit(0 if success else 1)
    else:
        # Run CLI
        run_cli_with_args()

if __name__ == "__main__":
    main()
