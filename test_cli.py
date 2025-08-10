#!/usr/bin/env python3
"""
Test script for TalkGPT CLI functionality.
"""

import sys
import subprocess
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def test_cli_import():
    """Test that CLI can be imported."""
    print("🧪 Testing CLI import...")
    
    try:
        from cli.main import cli
        print("✅ CLI imported successfully")
        return True
    except Exception as e:
        print(f"❌ CLI import failed: {e}")
        return False

def test_cli_help():
    """Test CLI help command."""
    print("\n🧪 Testing CLI help...")
    
    try:
        # Test main help
        result = subprocess.run([
            sys.executable, "-m", "src.cli.main", "--help"
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode == 0 and "TalkGPT" in result.stdout:
            print("✅ CLI help working")
            return True
        else:
            print(f"❌ CLI help failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI help test failed: {e}")
        return False

def test_cli_status():
    """Test CLI status command."""
    print("\n🧪 Testing CLI status...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "src.cli.main", "status", "system", "--quiet"
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode == 0:
            print("✅ CLI status working")
            print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ CLI status failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI status test failed: {e}")
        return False

def test_cli_config():
    """Test CLI config command."""
    print("\n🧪 Testing CLI config...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "src.cli.main", "config", "show", "--quiet"
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode == 0:
            print("✅ CLI config working")
            print(f"   Sample output: {result.stdout.split()[0] if result.stdout.split() else 'No output'}")
            return True
        else:
            print(f"❌ CLI config failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI config test failed: {e}")
        return False

def test_cli_version():
    """Test CLI version."""
    print("\n🧪 Testing CLI version...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "src.cli.main", "--version"
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode == 0 and "0.1.0" in result.stdout:
            print("✅ CLI version working")
            return True
        else:
            print(f"❌ CLI version failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI version test failed: {e}")
        return False

def main():
    """Run all CLI tests."""
    print("🚀 TalkGPT CLI Testing")
    print("=" * 40)
    
    tests = [
        ("CLI Import", test_cli_import),
        ("CLI Help", test_cli_help),
        ("CLI Version", test_cli_version),
        ("CLI Status", test_cli_status),
        ("CLI Config", test_cli_config),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
    
    print("\n" + "=" * 40)
    print(f"📊 CLI Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All CLI tests passed!")
    elif passed >= total * 0.8:
        print("✅ Most CLI tests passed.")
    else:
        print("⚠️  Several CLI tests failed.")
    
    return passed >= total * 0.8

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)