#!/usr/bin/env python3
"""
Test script for AI-Scale Data Collector
Tests basic functionality without requiring camera hardware
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        import cv2
        print("✅ OpenCV imported successfully")
    except ImportError as e:
        print(f"❌ OpenCV import failed: {e}")
        return False
    
    try:
        import numpy as np
        print("✅ NumPy imported successfully")
    except ImportError as e:
        print(f"❌ NumPy import failed: {e}")
        return False
    
    # Test Qt library (PySide6)
    try:
        from PySide6.QtWidgets import QApplication
        print("✅ PySide6 imported successfully")
    except ImportError as e:
        print(f"❌ PySide6 is not installed: {e}")
        print("   Please run the setup script or install it manually: pip install PySide6")
        return False
    
    return True

def test_data_structures():
    """Test data structures and classes"""
    print("\nTesting data structures...")
    
    try:
        from AIScaleDataCollector import CaptureMetadata, SessionManager
        print("✅ Data classes imported successfully")
        
        # Test metadata creation
        metadata = CaptureMetadata(
            filename="test.jpg",
            class_name="test_class",
            timestamp="20240120_120000",
            resolution=(1920, 1080),
            file_size=1024,
            camera_settings={},
            session_id="test_session"
        )
        print("✅ Metadata creation successful")
        
        # Test session manager
        test_path = Path("test_data")
        session_mgr = SessionManager(test_path)
        print("✅ Session manager creation successful")
        
        # Cleanup
        if test_path.exists():
            import shutil
            shutil.rmtree(test_path)
        
    except Exception as e:
        print(f"❌ Data structure test failed: {e}")
        return False
    
    return True

def test_validation_tools():
    """Test validation tools"""
    print("\nTesting validation tools...")
    
    try:
        from tools.data_processing.quick_validate import quick_validate_dataset, get_dataset_stats
        print("✅ Validation tools imported successfully")
        
        # Test with non-existent path
        result = quick_validate_dataset(Path("non_existent"))
        if not result["valid"]:
            print("✅ Validation correctly identified invalid path")
        else:
            print("❌ Validation failed to identify invalid path")
            return False
            
    except Exception as e:
        print(f"❌ Validation tools test failed: {e}")
        return False
    
    return True

def test_file_operations():
    """Test file operations"""
    print("\nTesting file operations...")
    
    try:
        # Test directory creation
        test_dir = Path("test_output")
        test_dir.mkdir(exist_ok=True)
        
        # Test class directory creation
        class_dir = test_dir / "test_class"
        class_dir.mkdir(exist_ok=True)
        
        # Test file writing
        test_file = class_dir / "test.txt"
        test_file.write_text("test content")
        
        if test_file.exists():
            print("✅ File operations successful")
        else:
            print("❌ File creation failed")
            return False
        
        # Cleanup
        import shutil
        shutil.rmtree(test_dir)
        
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🧪 AI-Scale Data Collector Test Suite")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_data_structures,
        test_validation_tools,
        test_file_operations
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"❌ Test {test.__name__} failed")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The data collector is ready to use.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 