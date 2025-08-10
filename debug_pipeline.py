#!/usr/bin/env python3
"""
Debug script to isolate the pipeline issue step by step.
"""

import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test all imports step by step."""
    print("🔍 Testing imports...")
    
    try:
        print("  ✓ Basic imports...")
        import os
        import time
        import json
        
        print("  ✓ Config system...")
        from utils.config import load_config
        config = load_config("default")
        print(f"    Config loaded: {config.transcription.model_size}")
        
        print("  ✓ Logging system...")
        from utils.logger import setup_logging
        logger = setup_logging(config.logging)
        print("    Logger initialized")
        
        print("  ✓ Resource detector...")
        from core.resource_detector import detect_hardware
        hardware = detect_hardware()
        print(f"    Hardware: {hardware.cpu_cores} cores, {hardware.recommended_device}")
        
        print("  ✓ File processor...")
        from core.file_processor import FileProcessor
        processor = FileProcessor()
        print("    File processor ready")
        
        print("  ✓ Chunker...")
        from core.chunker import SmartChunker
        chunker = SmartChunker()
        print("    Chunker ready")
        
        print("  ⚠️  Testing transcriber (this might fail)...")
        from core.transcriber import WhisperTranscriber
        print("    Transcriber imported")
        
        # This is where the error likely occurs
        print("  🔥 Creating transcriber instance...")
        transcriber = WhisperTranscriber(
            model_size="base",      # Use smaller model for testing
            device="cpu",           # Force CPU to avoid GPU issues
            compute_type="int8"     # Use CPU-compatible compute type
        )
        print("    ✅ Transcriber created successfully!")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Error: {e}")
        print(f"    📍 Error type: {type(e).__name__}")
        traceback.print_exc()
        return False

def test_faster_whisper_directly():
    """Test faster-whisper directly."""
    print("\n🔍 Testing faster-whisper directly...")
    
    try:
        print("  ✓ Importing faster_whisper...")
        from faster_whisper import WhisperModel
        
        print("  🔥 Creating WhisperModel...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        print("    ✅ WhisperModel created successfully!")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Error: {e}")
        print(f"    📍 Error type: {type(e).__name__}")
        traceback.print_exc()
        return False

def test_ctranslate2():
    """Test CTranslate2 directly."""
    print("\n🔍 Testing CTranslate2 directly...")
    
    try:
        print("  ✓ Importing ctranslate2...")
        import ctranslate2
        print(f"    Version: {ctranslate2.__version__}")
        
        print("  ✓ Checking available devices...")
        devices = ctranslate2.get_supported_compute_types("cpu")
        print(f"    CPU compute types: {devices}")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Error: {e}")
        print(f"    📍 Error type: {type(e).__name__}")
        traceback.print_exc()
        return False

def test_video_file():
    """Test if we can access the video file."""
    print("\n🔍 Testing video file access...")
    
    video_path = Path("processing/x.com_elder_plinius_status_1945128977766441106_01.mp4")
    
    if not video_path.exists():
        print(f"    ❌ Video file not found: {video_path}")
        return False
    
    print(f"    ✅ Video file found: {video_path}")
    print(f"    📊 Size: {video_path.stat().st_size / (1024*1024):.1f} MB")
    
    # Test if we can access it with ffmpeg
    try:
        print("  ✓ Testing ffmpeg access...")
        import ffmpeg
        probe = ffmpeg.probe(str(video_path))
        duration = float(probe['format']['duration'])
        print(f"    ✅ Video duration: {duration:.1f} seconds")
        return True
        
    except Exception as e:
        print(f"    ❌ ffmpeg error: {e}")
        return False

def main():
    """Run all debug tests."""
    print("🚀 TalkGPT Pipeline Debug")
    print("=" * 50)
    
    tests = [
        ("Video File Access", test_video_file),
        ("CTranslate2", test_ctranslate2),
        ("Faster-Whisper Direct", test_faster_whisper_directly),
        ("Pipeline Imports", test_imports),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"    💥 Test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Debug Results:")
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    passed = sum(1 for _, success in results if success)
    print(f"\n🎯 Summary: {passed}/{len(results)} tests passed")
    
    if passed < len(results):
        print("\n💡 Next steps:")
        print("  1. Check Windows Visual C++ Redistributables")
        print("  2. Try reinstalling faster-whisper")
        print("  3. Check for conflicting DLL versions")

if __name__ == "__main__":
    main()