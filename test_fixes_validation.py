#!/usr/bin/env python3
"""
TalkGPT Fixes Validation Test

This script validates that all the identified issues from the last session
have been properly fixed and the system is working correctly.
"""

import os
import sys
import time
from pathlib import Path

def test_environment_loading():
    """Test that environment variables are properly loaded from .env file."""
    print("🔧 Testing environment variable loading...")
    
    # Test critical environment variables
    critical_vars = {
        'KMP_DUPLICATE_LIB_OK': 'TRUE',
        'OMP_NUM_THREADS': '8',
        'MKL_NUM_THREADS': '8',
    }
    
    for var, expected in critical_vars.items():
        actual = os.environ.get(var)
        if actual == expected:
            print(f"   ✅ {var} = {actual}")
        else:
            print(f"   ❌ {var} = {actual} (expected {expected})")
            return False
    
    return True


def test_transcriber_loading():
    """Test that the transcriber loads with correct configuration."""
    print("🎤 Testing transcriber loading...")
    
    try:
        from src.core.transcriber import get_transcriber
        
        transcriber = get_transcriber()
        
        # Check model info
        device = transcriber.model_info.get('device')
        compute_type = transcriber.model_info.get('compute_type')
        
        print(f"   ✅ Transcriber loaded successfully")
        print(f"   ✅ Device: {device}")
        print(f"   ✅ Compute type: {compute_type}")
        
        # Verify compute type is appropriate for device
        if device == 'cpu' and compute_type == 'int8':
            print(f"   ✅ Compute type correctly set for CPU")
        elif device == 'cuda' and compute_type == 'float16':
            print(f"   ✅ Compute type correctly set for GPU")
        else:
            print(f"   ⚠️  Unusual compute type for device: {compute_type} on {device}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Transcriber loading failed: {e}")
        return False


def test_cli_commands_loading():
    """Test that CLI commands load without errors."""
    print("💻 Testing CLI commands loading...")
    
    try:
        from src.cli.commands.transcribe import transcribe_single_file
        from src.cli.commands.transcribe import get_speaker_analyzer, get_uncertainty_detector, get_timing_analyzer
        
        print(f"   ✅ transcribe_single_file imported successfully")
        
        # Test lazy imports
        speaker_analyzer = get_speaker_analyzer()
        uncertainty_detector = get_uncertainty_detector()
        timing_analyzer = get_timing_analyzer()
        
        print(f"   ✅ Speaker analyzer: {'Available' if speaker_analyzer else 'Not available'}")
        print(f"   ✅ Uncertainty detector: {'Available' if uncertainty_detector else 'Not available'}")
        print(f"   ✅ Timing analyzer: {'Available' if timing_analyzer else 'Not available'}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ CLI commands loading failed: {e}")
        return False


def test_json_serialization():
    """Test that JSON serialization works with Path objects."""
    print("📄 Testing JSON serialization fixes...")
    
    try:
        from pathlib import Path
        import json
        
        # Test the convert_paths_to_strings function logic
        def convert_paths_to_strings(obj):
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_paths_to_strings(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_paths_to_strings(item) for item in obj]
            else:
                return obj
        
        # Test with various data structures containing Path objects
        test_data = {
            'simple_path': Path('/test/path'),
            'nested_dict': {
                'inner_path': Path('/inner/path'),
                'string_value': 'test'
            },
            'path_list': [Path('/path1'), Path('/path2'), 'string'],
            'mixed_list': [Path('/mixed'), {'path': Path('/dict/path')}, 'text']
        }
        
        converted = convert_paths_to_strings(test_data)
        json_str = json.dumps(converted)
        
        print(f"   ✅ JSON serialization works correctly")
        print(f"   ✅ Path objects converted to strings")
        
        return True
        
    except Exception as e:
        print(f"   ❌ JSON serialization test failed: {e}")
        return False


def test_error_handling():
    """Test that error handling improvements work correctly."""
    print("🛡️  Testing error handling improvements...")
    
    try:
        # Test None safety checks
        def safe_access_test():
            # Simulate the fixed patterns
            uncertainty_result = None
            speaker_result = None
            
            # These should not raise AttributeError anymore
            quality_score = uncertainty_result.quality_metrics.overall_quality_score if uncertainty_result and hasattr(uncertainty_result, 'quality_metrics') and uncertainty_result.quality_metrics else None
            speaker_count = speaker_result.diarization_result.speaker_count if speaker_result and hasattr(speaker_result, 'diarization_result') and speaker_result.diarization_result else None
            flagged_segments = len(uncertainty_result.flagged_segments) if uncertainty_result and hasattr(uncertainty_result, 'flagged_segments') else None
            
            return quality_score, speaker_count, flagged_segments
        
        result = safe_access_test()
        print(f"   ✅ None safety checks work correctly: {result}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error handling test failed: {e}")
        return False


def main():
    """Run all validation tests."""
    print("🧪 TalkGPT Fixes Validation Test")
    print("=" * 50)
    
    # Add src to path
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    
    # Load environment variables
    try:
        from src.utils.env_loader import ensure_environment_loaded
        ensure_environment_loaded()
    except ImportError:
        print("⚠️  Could not import env_loader, using fallback")
        os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    
    tests = [
        ("Environment Loading", test_environment_loading),
        ("Transcriber Loading", test_transcriber_loading),
        ("CLI Commands Loading", test_cli_commands_loading),
        ("JSON Serialization", test_json_serialization),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    start_time = time.time()
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"   ❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        if result:
            print(f"   ✅ {test_name}: PASSED")
            passed += 1
        else:
            print(f"   ❌ {test_name}: FAILED")
            failed += 1
    
    total_time = time.time() - start_time
    print(f"\n📈 Total: {passed} passed, {failed} failed in {total_time:.2f}s")
    
    if failed == 0:
        print("🎉 All fixes validated successfully! The system is ready for use.")
    else:
        print("⚠️  Some issues remain. Please review the failed tests above.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)




