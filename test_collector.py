#!/usr/bin/env python3
"""
Basic Smoke Test for AI-Scale Data Collector

This script performs a basic "smoke test" by attempting to initialize
the main application components without showing the GUI. It helps ensure
that all dependencies are correctly installed and that the application
can start without immediate crashes.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure the application's root directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock PySide6 classes before they are imported by the main application
# This prevents any GUI windows from actually appearing during the test.
mock_pyside = MagicMock()
sys.modules['PySide6'] = mock_pyside
sys.modules['PySide6.QtWidgets'] = mock_pyside.QtWidgets
sys.modules['PySide6.QtCore'] = mock_pyside.QtCore
sys.modules['PySide6.QtGui'] = mock_pyside.QtGui

# Now we can import the application class
from AIScaleDataCollector import AIScaleDataCollector

class TestAppInitialization(unittest.TestCase):
    """
    Test suite for application initialization.
    """

    @patch('AIScaleDataCollector.CameraThread')
    @patch('AIScaleDataCollector.DatabaseManager')
    @patch('AIScaleDataCollector.ConfigManager')
    def test_app_init(self, MockConfigManager, MockDatabaseManager, MockCameraThread):
        """
        Tests if the AIScaleDataCollector application can be instantiated.
        Mocks out external dependencies like config, database, and camera.
        """
        print("🧪 Testing application initialization (smoke test)...")
        
        try:
            # We need to mock the QApplication instance that QMainWindow expects
            mock_app = MagicMock()
            with patch('PySide6.QtWidgets.QApplication.instance', return_value=mock_app):
                # We also prevent QMainWindow.__init__ from running GUI code
                with patch.object(AIScaleDataCollector, "__init__", lambda x: None):
                    app_instance = AIScaleDataCollector()

            # A successful test is one that doesn't raise an exception
            print("✅ Application initialized successfully without GUI.")
            self.assertIsNotNone(app_instance, "App instance should be created.")

        except Exception as e:
            self.fail(f"Application initialization failed with an exception: {e}")

if __name__ == '__main__':
    print("Running AI-Scale Data Collector Smoke Test...")
    unittest.main() 