#!/usr/bin/env python3
"""
Quick test script to verify TalkGPT setup and core modules.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all core modules can be imported."""
    print("🧪 Testing module imports...")
    
    try:
        from utils.config import ConfigManager, TalkGPTConfig
        print("✅ Configuration system imported successfully")
    except Exception as e:
        print(f"❌ Configuration system import failed: {e}")
        return False
    
    try:
        from utils.logger import TalkGPTLogger, get_logger
        print("✅ Logging system imported successfully")
    except Exception as e:
        print(f"❌ Logging system import failed: {e}")
        return False
    
    try:
        from core.resource_detector import ResourceDetector, detect_hardware
        print("✅ Resource detector imported successfully")
    except Exception as e:
        print(f"❌ Resource detector import failed: {e}")
        return False
    
    try:
        from core.file_processor import FileProcessor
        print("✅ File processor imported successfully")
    except Exception as e:
        print(f"❌ File processor import failed: {e}")
        return False
    
    return True

def test_config_system():
    """Test configuration system."""
    print("\n🔧 Testing configuration system...")
    
    try:
        from utils.config import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.load_config("default")
        
        print(f"✅ Default config loaded: {config.transcription.model_size}")
        print(f"✅ Speed multiplier: {config.processing.speed_multiplier}")
        print(f"✅ Output formats: {config.output.formats}")
        
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_logging_system():
    """Test logging system."""
    print("\n📝 Testing logging system...")
    
    try:
        from utils.logger import setup_logging, get_logger
        
        logger_system = setup_logging()
        logger = get_logger("test")
        
        logger.info("Test log message from TalkGPT")
        print("✅ Logging system working")
        
        return True
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False

def test_resource_detection():
    """Test resource detection."""
    print("\n🔍 Testing resource detection...")
    
    try:
        from core.resource_detector import detect_hardware
        
        hardware = detect_hardware()
        
        print(f"✅ CPU Cores: {hardware.cpu_cores}")
        print(f"✅ Memory: {hardware.memory_gb:.1f} GB")
        print(f"✅ GPU Available: {hardware.gpu_available}")
        print(f"✅ Recommended Device: {hardware.recommended_device}")
        print(f"✅ Optimal Workers: {hardware.optimal_workers}")
        
        return True
    except Exception as e:
        print(f"❌ Resource detection test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 TalkGPT Setup Verification")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config_system,
        test_logging_system,
        test_resource_detection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! TalkGPT setup is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)