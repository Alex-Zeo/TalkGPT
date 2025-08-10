#!/usr/bin/env python3
"""
Simple test script to verify TalkGPT basic functionality.
"""

import sys
import os
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def test_config():
    """Test configuration system."""
    print("🔧 Testing configuration system...")
    
    try:
        from utils.config import ConfigManager
        
        # Create config manager with explicit path
        config_dir = project_root / "config"
        config_manager = ConfigManager(config_dir)
        
        # Load default config
        config = config_manager.load_config("default")
        
        print(f"✅ Model size: {config.transcription.model_size}")
        print(f"✅ Speed multiplier: {config.processing.speed_multiplier}")
        print(f"✅ Output formats: {config.output.formats}")
        print(f"✅ Log level: {config.logging.level}")
        
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_resource_detection():
    """Test resource detection."""
    print("\n🔍 Testing resource detection...")
    
    try:
        from core.resource_detector import ResourceDetector
        
        detector = ResourceDetector()
        hardware = detector.detect_hardware()
        
        print(f"✅ CPU Cores: {hardware.cpu_cores}")
        print(f"✅ Memory: {hardware.memory_gb:.1f} GB")
        print(f"✅ Platform: {hardware.platform}")
        print(f"✅ GPU Available: {hardware.gpu_available}")
        print(f"✅ Recommended Device: {hardware.recommended_device}")
        print(f"✅ Optimal Workers: {hardware.optimal_workers}")
        
        if hardware.gpu_available:
            print(f"✅ GPU Count: {hardware.gpu_count}")
            for i, name in enumerate(hardware.gpu_names):
                memory_gb = hardware.gpu_memory[i] / (1024**3)
                print(f"   GPU {i}: {name} ({memory_gb:.1f} GB)")
        
        return True
    except Exception as e:
        print(f"❌ Resource detection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_processor():
    """Test file processor basic functionality."""
    print("\n📁 Testing file processor...")
    
    try:
        from core.file_processor import FileProcessor
        
        processor = FileProcessor()
        
        # Test directory scanning (use current directory)
        test_dir = project_root
        files = processor.scan_directory(test_dir, recursive=False, extensions=['.py', '.md'])
        
        print(f"✅ Found {len(files)} Python/Markdown files in project root")
        
        # Test supported formats
        audio_formats = processor.AUDIO_EXTENSIONS
        video_formats = processor.VIDEO_EXTENSIONS
        
        print(f"✅ Supported audio formats: {len(audio_formats)}")
        print(f"✅ Supported video formats: {len(video_formats)}")
        
        return True
    except Exception as e:
        print(f"❌ File processor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_directory_structure():
    """Test that all required directories exist."""
    print("\n📂 Testing directory structure...")
    
    required_dirs = [
        "src/core",
        "src/analytics", 
        "src/utils",
        "src/workers",
        "src/cli",
        "src/mcp",
        "config",
        "tests",
        "docs"
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} - missing")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests."""
    print("🚀 TalkGPT Basic Setup Verification")
    print("=" * 50)
    
    tests = [
        ("Directory Structure", test_directory_structure),
        ("Configuration System", test_config),
        ("Resource Detection", test_resource_detection),
        ("File Processor", test_file_processor),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"📊 Final Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Core TalkGPT modules are working.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)