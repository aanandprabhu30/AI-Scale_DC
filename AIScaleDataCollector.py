#!/usr/bin/env python3
"""
AI-Scale Data Collector v2.0
Optimized for M2 MacBook Air with Arducam IMX219 USB Camera
Production-ready tool for capturing produce images for AI training
"""

import sys
import os
import cv2
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import deque
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, List

# Try PySide6 first (better macOS compatibility), fallback to PyQt6
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QMessageBox, QInputDialog, QGridLayout,
        QDialog, QDialogButtonBox, QStyleFactory, QTextEdit
    )
    from PySide6.QtCore import Qt, QTimer, Signal as pyqtSignal, QThread, QSettings
    from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QAction

    # Add a dedicated function to check for Qt plugin paths
    from PySide6.QtCore import QLibraryInfo
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    def check_qt_plugins():
        """Helper function to diagnose Qt plugin issues."""
        logger.info("---- Checking Qt Plugin Paths ----")
        paths = QLibraryInfo.location(QLibraryInfo.PluginsPath)
        logger.info(f"Expected Qt Plugins Path: {paths}")
        if not os.path.isdir(paths):
            logger.warning("Qt Plugins path does not exist!")
        else:
            logger.info(f"Platform plugins found: {[d for d in os.listdir(paths) if 'platforms' in d]}")
        logger.info("---------------------------------")

except ImportError:
    print("❌ PySide6 is not installed. Please run the setup script or install it manually:")
    print("   pip install PySide6")
    sys.exit(1)

# --- App-specific Imports ---
import shutil
import csv
from tools.data_processing.quick_validate import quick_validate_dataset


# Constants
APP_NAME = "AI-Scale Data Collector"
APP_VERSION = "2.0.0"
ORGANIZATION = "AI-Scale"

# IMX219 sensor specifications
IMX219_CONFIGS = {
    "preview": {"width": 1920, "height": 1080, "fps": 30},
    "capture_high": {"width": 3280, "height": 2464, "fps": 15},
    "capture_medium": {"width": 1920, "height": 1080, "fps": 30},
    "capture_low": {"width": 1280, "height": 720, "fps": 30}
}

# Target model input size for reference
MODEL_INPUT_SIZE = (224, 224)

# Camera configuration constants
CAMERA_BACKEND = cv2.CAP_AVFOUNDATION  # Best for macOS
CAMERA_FOURCC = cv2.VideoWriter_fourcc(*'MJPG')
CAMERA_BUFFER_SIZE = 1
CAMERA_AUTOFOCUS = 1
CAMERA_AUTO_EXPOSURE = 0.25

@dataclass
class CaptureMetadata:
    """Metadata for each captured image"""
    filename: str
    class_name: str
    timestamp: str
    resolution: Tuple[int, int]
    file_size: int
    camera_settings: dict
    session_id: str
    
class SaveWorker(QThread):
    """Worker thread for saving images without blocking the UI"""
    finished = pyqtSignal(bool, str, object) # success, message, metadata_tuple

    def __init__(self, frame, class_path, filename, options, cam_info, session_id):
        super().__init__()
        self.frame = frame
        self.class_path = class_path
        self.filename = filename
        self.options = options
        self.cam_info = cam_info
        self.session_id = session_id
        
    def run(self):
        """Perform the file I/O operations in the background"""
        try:
            filepath = self.class_path / self.filename
            
            # Save main image with error checking
            success = cv2.imwrite(str(filepath), self.frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            if not success:
                raise IOError("cv2.imwrite returned False. Check file path, permissions, and image format.")

            if not filepath.exists() or filepath.stat().st_size == 0:
                raise IOError("File not found or is empty after saving. Check disk space and permissions.")

            file_size = filepath.stat().st_size
            
            # Create preview if requested
            if self.options['create_preview']:
                preview = cv2.resize(self.frame, MODEL_INPUT_SIZE, interpolation=cv2.INTER_AREA)
                preview_path = self.class_path / f"preview_{self.filename}"
                cv2.imwrite(str(preview_path), preview, [cv2.IMWRITE_JPEG_QUALITY, 90])
                
            metadata = None
            if self.options['create_metadata']:
                metadata_tuple = (
                    self.filename,
                    self.class_path.name,
                    datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3],
                    (self.frame.shape[1], self.frame.shape[0]),
                    file_size,
                    self.cam_info,
                    self.session_id
                )
                metadata = CaptureMetadata(*metadata_tuple)
                meta_path = filepath.with_suffix('.json')
                with open(meta_path, 'w') as f:
                    json.dump(asdict(metadata), f, indent=2)

            self.finished.emit(True, str(filepath), metadata)

        except Exception as e:
            self.finished.emit(False, str(e), None)


class ValidationReportDialog(QDialog):
    """A dialog to display the results of the quick validation."""
    def __init__(self, report_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Validation Report")
        self.setMinimumSize(550, 450)

        layout = QVBoxLayout(self)

        report_text_edit = QTextEdit()
        report_text_edit.setReadOnly(True)
        report_text_edit.setFontFamily("monospace")
        report_text_edit.setText(self.format_report(report_data))
        
        layout.addWidget(report_text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def format_report(self, report: dict) -> str:
        """Formats the report dictionary into a readable string."""
        lines = []
        if report.get("valid", False):
            lines.append("✅ Status: Looks Good!")
        else:
            lines.append("❌ Status: Issues Found!")
        
        lines.append("\n--- Summary ---")
        lines.append(f"  - Total Classes: {report.get('total_classes', 0)}")
        lines.append(f"  - Total Images: {report.get('total_images', 0)}")
        lines.append(f"  - Total Size: {report.get('total_size_mb', 0):.2f} MB")

        if report.get("issues"):
            lines.append("\n--- Issues ---")
            top_level_issues = sorted({issue for issue in report["issues"] if ":" not in issue})
            for issue in top_level_issues:
                lines.append(f"  - {issue}")
        
        lines.append("\n--- Class Details ---")
        class_summary = report.get("class_summary", {})
        if not class_summary:
            lines.append("  - No classes found to detail.")
        else:
            for name, summary in sorted(class_summary.items()):
                lines.append(f"  - {name}: {summary['count']} images ({summary['size_mb']:.2f} MB)")
                if summary['issues']:
                    for issue in summary['issues']:
                        lines.append(f"    - ⚠️ {issue}")
        
        return "\n".join(lines)


class SessionManager:
    """Minimal session manager for tracking captures"""
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.captures = []
        
    def add_capture(self, metadata):
        """Add capture to session"""
        self.captures.append(metadata)


class CameraThread(QThread):
    """Dedicated thread for camera operations with enhanced error handling"""
    frameReady = pyqtSignal(np.ndarray)
    statusUpdate = pyqtSignal(str, str)  # message, severity
    
    def __init__(self):
        super().__init__()
        self.camera = None
        self.running = False
        self.current_frame = None
        self.frame_times = deque(maxlen=30)
        self.fps = 0.0
        
    def initialize_camera(self, index=0) -> bool:
        """Initialize camera with robust error handling, aiming for 8MP resolution."""
        logger.info(f"Attempting to initialize camera at index {index}...")
        try:
            # On macOS, AVFoundation is preferred.
            self.camera = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
            logger.info(f"Camera backend set to AVFoundation.")

            if not self.camera or not self.camera.isOpened():
                logger.warning(f"Failed to open camera with AVFoundation. Trying default backend...")
                self.camera = cv2.VideoCapture(index) # Fallback to default
                if not self.camera or not self.camera.isOpened():
                    self.statusUpdate.emit(f"Camera at index {index} could not be opened.", "error")
                    return False

            logger.info("Camera opened successfully. Requesting 8MP resolution...")
            
            # Request 8MP (3280x2464) resolution
            high_res_config = IMX219_CONFIGS["capture_high"]
            target_width = high_res_config["width"]
            target_height = high_res_config["height"]
            target_fps = high_res_config["fps"]
            
            self.camera.set(cv2.CAP_PROP_FOURCC, CAMERA_FOURCC)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
            self.camera.set(cv2.CAP_PROP_FPS, target_fps)

            # We can still set other useful defaults.
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
            self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 1) # Default to autofocus on
            self.camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) # Default to auto exposure on
            
            # Allow time for the camera to stabilize before reading properties
            time.sleep(1.0) 

            width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if width == 0 or height == 0:
                logger.error("Camera returned 0x0 resolution. It might be in use or drivers are faulty.")
                self.camera.release()
                self.statusUpdate.emit("Camera resolution is 0x0. Is it in use?", "error")
                return False

            self.statusUpdate.emit(f"Camera initialized: {width}x{height}", "success")
            logger.info(f"Camera successfully initialized with default resolution: {width}x{height}.")
            return True
            
        except Exception as e:
            error_msg = f"Exception during camera init: {str(e)}"
            self.statusUpdate.emit(error_msg, "error")
            logger.exception(error_msg)
            return False
        
    def run(self):
        """Enhanced camera capture loop with optimized FPS monitoring"""
        self.running = True
        no_frame_count = 0
        
        while self.running:
            if self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                
                if ret and frame is not None:
                    no_frame_count = 0
                    self.current_frame = frame
                    
                    # Correct FPS calculation over a rolling window
                    self.frame_times.append(time.perf_counter())
                    if len(self.frame_times) > 1:
                        time_span = self.frame_times[-1] - self.frame_times[0]
                        if time_span > 0:
                            self.fps = (len(self.frame_times) - 1) / time_span
                    
                    self.frameReady.emit(frame)

                else:
                    no_frame_count += 1
                    if no_frame_count > 100: # After ~1.6s of no frames
                        self.statusUpdate.emit("No frames received from camera.", "warning")
                        no_frame_count = 0 # Reset to avoid spamming
                        
            time.sleep(0.016)  # Target ~60Hz update rate
            
    def capture_image(self, quality="high") -> Optional[np.ndarray]:
        """
        Captures the most recent frame from the preview stream.
        This is more stable than reconfiguring the camera on the fly.
        """
        if self.current_frame is not None:
            return self.current_frame.copy()  # Return a copy to prevent data races
        
        # Fallback for when the stream might be slow to start
        if self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret and frame is not None:
                return frame
        
        return None
            
    def get_camera_info(self) -> dict:
        """Get current camera settings"""
        if not self.camera:
            return {}
            
        return {
            "width": int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": int(self.camera.get(cv2.CAP_PROP_FPS)),
            "brightness": self.camera.get(cv2.CAP_PROP_BRIGHTNESS),
            "contrast": self.camera.get(cv2.CAP_PROP_CONTRAST),
            "saturation": self.camera.get(cv2.CAP_PROP_SATURATION),
            "exposure": self.camera.get(cv2.CAP_PROP_EXPOSURE)
        }
        
    def stop(self):
        """Clean camera shutdown"""
        self.running = False
        self.wait()
        if self.camera:
            self.camera.release()

class AIScaleDataCollector(QMainWindow):
    """Enhanced main application with better error handling and features"""
    
    def __init__(self):
        super().__init__()
        self.camera_thread = CameraThread()
        self.camera_thread.frameReady.connect(self.update_frame)
        self.camera_thread.statusUpdate.connect(self.handle_camera_status)
        self.current_class = ""
        self.dataset_path = Path("data/raw")
        self.session_manager = SessionManager(self.dataset_path)
        self.settings = QSettings(ORGANIZATION, APP_NAME)
        
        # Timer for UI updates like FPS
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_fps)

        # Statistics
        self.session_count = 0
        self.class_counts = {}
        self.capture_times = deque(maxlen=10)
        
        self.init_ui()
        self.setup_camera()
        self.load_classes()
        self.restore_settings()
        
    def init_ui(self):
        """Initialize Apple-inspired simple user interface"""
        self.setWindowTitle(f"{APP_NAME}")
        self.setMinimumSize(1000, 700)
        
        # Apple-inspired styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 14px;
            }
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: 500;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #0056CC;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
            QPushButton:disabled {
                background-color: #E5E5EA;
                color: #8E8E93;
            }
            QComboBox {
                border: 1px solid #E5E5EA;
                border-radius: 8px;
                padding: 8px 12px;
                background-color: white;
                font-size: 14px;
                color: #1D1D1F; /* Explicitly set text color */
            }
            QComboBox:hover {
                 border-color: #C7C7CC; /* Subtle border change on hover */
            }
            QComboBox:focus {
                border-color: #007AFF;
            }
            QComboBox QAbstractItemView { /* Style for the dropdown list */
                background-color: white;
                color: #1D1D1F;
                border: 1px solid #E5E5EA;
                selection-background-color: #007AFF;
                selection-color: white;
            }
            QLabel {
                color: #1D1D1F;
            }
        """)
        
        # Create central widget with simple layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - vertical with camera on top, controls below
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # Camera view (large and prominent)
        self.create_camera_section(main_layout)
        
        # Simple controls section
        self.create_simple_controls(main_layout)
        
        # Add menu bar for settings
        self.create_menu_bar()

        # Minimal status bar
        self.create_minimal_status_bar()
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
    def create_menu_bar(self):
        """Creates the main menu bar."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        # Add Camera Settings Dialog
        settings_action = QAction("Camera &Settings", self)
        settings_action.triggered.connect(self.show_camera_settings)
        file_menu.addAction(settings_action)
        
        # Add a "Validate Dataset" action
        validate_action = QAction("&Validate Dataset", self)
        validate_action.triggered.connect(self.run_quick_validation)
        file_menu.addAction(validate_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def show_camera_settings(self):
        """Shows a dialog to select the camera."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Camera Settings")
        layout = QGridLayout()
        
        # --- Camera Selection ---
        layout.addWidget(QLabel("Select Camera:"), 0, 0)
        camera_combo = QComboBox()
        self.populate_camera_list(camera_combo)
        layout.addWidget(camera_combo, 0, 1)

        # Connect the signal AFTER populating
        camera_combo.currentIndexChanged.connect(self.switch_camera)
        
        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box, 2, 0, 1, 2)
        
        dialog.setLayout(layout)
        dialog.exec()

    def run_quick_validation(self):
        """Runs the quick validation script and displays a report in a dialog."""
        self.status_bar.showMessage("Running validation...", 3000)
        QApplication.processEvents()  # Ensure the message is shown immediately

        try:
            report = quick_validate_dataset(self.dataset_path)
            dialog = ValidationReportDialog(report, self)
            dialog.exec()
            self.status_bar.showMessage("Validation complete.", 3000)
        except Exception as e:
            logger.error(f"Failed to run validation script: {e}", exc_info=True)
            QMessageBox.critical(
                self, 
                "Validation Error", 
                f"Could not run the validation script.\n\nError: {e}"
            )

    def list_available_cameras(self) -> List[Tuple[int, str]]:
        """Detects and lists available cameras, returning their index and a basic name."""
        available_cameras = []
        logger.info("Searching for available cameras...")
        # Check first 10 indices, which is plenty for most systems.
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
            if cap.isOpened():
                # On macOS, we can't get a device name easily, so we just name them generically.
                available_cameras.append((i, f"Camera {i}"))
                logger.info(f"Found usable camera at index {i}")
                cap.release()
        
        if not available_cameras:
            logger.warning("No cameras found by OpenCV.")
        return available_cameras

    def populate_camera_list(self, combo_box):
        """Populates the given QComboBox with available cameras."""
        combo_box.clear()
        self.available_cameras = self.list_available_cameras()
        
        if not self.available_cameras:
            combo_box.addItem("No cameras found")
            combo_box.setEnabled(False)
            return

        for index, name in self.available_cameras:
            combo_box.addItem(name, userData=index)
            
        # Try to restore the last used camera index
        last_cam_index = self.settings.value("last_camera_index", 0, type=int)
        
        # Find the corresponding item in the combobox
        for i in range(combo_box.count()):
            if combo_box.itemData(i) == last_cam_index:
                combo_box.setCurrentIndex(i)
                break

    def switch_camera(self, ui_index):
        """Switches the camera feed to the selected device."""
        if not self.available_cameras or ui_index < 0:
            return

        # Get the actual camera index from the combobox userData
        camera_index = self.camera_combo.itemData(ui_index)
        
        if camera_index is None:
            return
            
        logger.info(f"Switching to camera index: {camera_index}")
        
        # Stop the current camera thread
        self.camera_thread.stop()
        
        # Re-initialize and start with the new index
        if self.camera_thread.initialize_camera(camera_index):
            self.start_camera_feed()
            self.settings.setValue("last_camera_index", camera_index)
        else:
            self.handle_camera_status(f"Failed to switch to Camera {camera_index}", "error")

    def create_camera_section(self, parent_layout):
        """Creates the main camera view and its associated controls."""
        # Camera container
        camera_container = QWidget()
        camera_layout = QVBoxLayout(camera_container)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.setSpacing(12)
        
        # Camera display
        self.camera_view = QLabel("Initializing Camera...")
        self.camera_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_view.setStyleSheet("""
            QLabel {
                background-color: black;
                border: 1px solid #444;
                border-radius: 8px;
                color: white;
            }
        """)
        self.camera_view.setMinimumSize(640, 480)
        camera_layout.addWidget(self.camera_view, 1) # Add stretch factor of 1

        # Status bar for FPS and Resolution
        status_layout = QHBoxLayout()
        self.fps_label = QLabel("FPS: --")
        self.resolution_label = QLabel("Resolution: --")
        status_layout.addWidget(self.fps_label)
        status_layout.addStretch()
        status_layout.addWidget(self.resolution_label)
        camera_layout.addLayout(status_layout)
        
        parent_layout.addWidget(camera_container, 5) # Give more stretch factor
        
    def create_simple_controls(self, parent_layout):
        """Create simplified and aligned controls section using a grid."""
        controls_layout = QVBoxLayout()
        controls_grid = QGridLayout()
        
        # --- Camera Selection ---
        controls_grid.addWidget(QLabel("Camera:"), 0, 0)
        self.camera_combo = QComboBox()
        # We will populate this in setup_camera after the UI is built
        controls_grid.addWidget(self.camera_combo, 0, 1, 1, 2)

        # --- Produce Selection ---
        controls_grid.addWidget(QLabel("Produce Type:"), 1, 0)
        self.class_selector = QComboBox()
        self.class_selector.setPlaceholderText("Select produce type...")
        self.class_selector.currentIndexChanged.connect(
            lambda: self.on_class_changed(self.class_selector.currentText())
        )
        controls_grid.addWidget(self.class_selector, 1, 1)

        self.add_class_button = QPushButton("+ Add New")
        self.add_class_button.clicked.connect(self.show_add_class_dialog)
        controls_grid.addWidget(self.add_class_button, 1, 2)
        
        # Set column stretch for a balanced layout
        controls_grid.setColumnStretch(1, 2)
        controls_grid.setColumnStretch(2, 1)

        # --- Capture Button ---
        capture_box = QHBoxLayout()
        self.capture_button = QPushButton("Capture Image")
        self.capture_button.clicked.connect(self.capture_image)
        self.capture_button.setStyleSheet("padding: 10px;")
        self.capture_button.setMinimumHeight(40)
        self.capture_button.setEnabled(False) # Disabled until class is selected
        capture_box.addWidget(self.capture_button)

        # --- Session Info ---
        session_info_box = QVBoxLayout()
        session_info_box.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.session_label = QLabel("<b>Session:</b> No captures yet")
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        session_info_box.addWidget(self.session_label)

        controls_layout.addLayout(controls_grid)
        controls_layout.addStretch()
        controls_layout.addLayout(capture_box)
        controls_layout.addLayout(session_info_box)
        controls_layout.addStretch()

        parent_layout.addLayout(controls_layout, 2) # Give less stretch factor
        
    def create_minimal_status_bar(self):
        """Create minimal status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #F2F2F7;
                border-top: 1px solid #E5E5EA;
                color: #8E8E93;
                font-size: 12px;
            }
        """)
        
        # Simple session counter
        self.session_counter = QLabel("Captures: 0")
        self.status_bar.addPermanentWidget(self.session_counter)
        
    def show_add_class_dialog(self):
        """Show simple dialog to add new class"""
        class_name, ok = QInputDialog.getText(
            self, 
            "Add New Produce Type", 
            "Enter produce type name:",
            text=""
        )
        
        if ok and class_name.strip():
            self.add_class_from_dialog(class_name.strip())
            
    def add_class_from_dialog(self, class_name):
        """Add new class from dialog input"""
        # Validate and sanitize name
        class_name = class_name.lower().replace(' ', '_').replace('-', '_')
        
        if not all(c.isalnum() or c == '_' for c in class_name):
            QMessageBox.warning(self, "Invalid Name",
                              "Please use only letters, numbers, and underscores.")
            return
            
        # Create directory
        class_path = self.dataset_path / class_name
        if not class_path.exists():
            try:
                class_path.mkdir(parents=True)
                self.load_classes()
                
                # Select new class
                index = self.class_selector.findText(class_name)
                if index >= 0:
                    self.class_selector.setCurrentIndex(index)
                    
                self.status_bar.showMessage(f"Added: {class_name}", 3000)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create: {str(e)}")
        else:
            QMessageBox.information(self, "Exists", f"'{class_name}' already exists.")
            
    def on_class_changed(self, class_name):
        """Handle class selection with simple feedback"""
        self.current_class = class_name
        if class_name:
            count = len(list((self.dataset_path / class_name).glob("*.jpg")))
            self.capture_button.setEnabled(True)
            self.status_bar.showMessage(f"Selected: {class_name} ({count} images)", 2000)
        else:
            self.capture_button.setEnabled(False)
            
    def capture_image(self):
        """Simple capture with immediate feedback"""
        if not self.current_class:
            QMessageBox.warning(self, "No Selection", "Please select a produce type first.")
            return
            
        # Capture frame
        frame = self.camera_thread.capture_image()
        if frame is None:
            QMessageBox.critical(self, "Capture Error", "Failed to capture image.")
            return
            
        # Save image
        self.save_image_async(frame)
        
        # Visual feedback
        self.capture_button.setText("Capturing...")
        self.capture_button.setEnabled(False)
        QTimer.singleShot(500, self.reset_capture_button)
        
    def reset_capture_button(self):
        """Reset capture button after capture"""
        self.capture_button.setText("Capture Image")
        self.capture_button.setEnabled(True)
        
    def on_save_finished(self, success, result, metadata):
        """Handle save completion with simple feedback"""
        if success:
            filename = Path(result).name
            self.session_count += 1
            self.session_counter.setText(f"Captures: {self.session_count}")
            self.session_label.setText(f"<b>Session:</b> {self.session_count} captures")
            
            if metadata:
                self.session_manager.add_capture(metadata)
                
            self.status_bar.showMessage(f"Saved: {filename}", 3000)
        else:
            QMessageBox.critical(self, "Save Error", f"Failed to save: {result}")
            
    def update_fps(self):
        """Update FPS display"""
        fps = self.camera_thread.fps
        self.fps_label.setText(f"FPS: {fps:.1f}")
        
    def update_frame(self, frame):
        """Update camera display"""
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        
        # Convert to QImage
        q_image = QImage(frame.data, width, height, bytes_per_line,
                        QImage.Format_BGR888).rgbSwapped()
        
        # Create pixmap and scale
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(self.camera_view.size(),
                              Qt.KeepAspectRatio,
                              Qt.SmoothTransformation)
        self.camera_view.setPixmap(scaled)
        
        # Update resolution
        self.resolution_label.setText(f"Resolution: {width}x{height}")
        
    def setup_shortcuts(self):
        """Setup essential keyboard shortcuts"""
        shortcuts = [
            ("Space", self.capture_image),
            ("Ctrl+Q", self.close),
        ]
        
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            
    def load_classes(self):
        self.class_selector.clear()
        self.class_selector.addItem("Select produce type...")
        
        data_path = Path('data/raw')
        if not data_path.exists():
            return

        # Filter for directories only and exclude common non-class dirs
        excluded_dirs = {'sessions', '__pycache__', '.DS_Store'}
        classes = sorted([d.name for d in data_path.iterdir() if d.is_dir() and d.name not in excluded_dirs])
        
        self.class_selector.addItems(classes)

    def setup_camera(self):
        """Initializes and configures the camera and related UI elements."""
        self.populate_camera_list(self.camera_combo)
        self.camera_combo.currentIndexChanged.connect(self.switch_camera)
        
        # Automatically start with the default (or last used) camera
        if self.available_cameras:
            initial_cam_index = self.camera_combo.itemData(self.camera_combo.currentIndex())
            if self.camera_thread.initialize_camera(initial_cam_index):
                self.start_camera_feed()
            else:
                self.handle_camera_status("Failed to initialize the default camera.", "error")
        else:
            self.handle_camera_status("No cameras found.", "error")
            # Disable camera-dependent UI
            self.capture_button.setEnabled(False)
            self.camera_view.setText("No Camera Detected")


    def start_camera_feed(self):
        """Starts the camera thread if it's not already running."""
        if not self.camera_thread.isRunning():
            self.camera_thread.start()
            self.update_timer.start(300) # Update FPS ~3 times/sec
            logger.info("Camera thread started.")

    def handle_camera_status(self, message, severity):
        """Display camera status messages to the user."""
        if severity == "error":
            self.status_bar.showMessage(f"❌ {message}", 5000)
        elif severity == "warning":
            self.status_bar.showMessage(f"⚠️ {message}", 3000)
        else:
            self.status_bar.showMessage(f"✅ {message}", 2000)
            
    def save_image_async(self, frame):
        """Save image asynchronously using a worker thread."""
        try:
            class_path = self.dataset_path / self.current_class
            class_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            count = len(list(class_path.glob("*.jpg"))) + 1
            filename = f"{self.current_class}_{count:04d}_{timestamp}.jpg"
            
            options = {
                'create_preview': False,
                'create_metadata': True
            }
            cam_info = self.camera_thread.get_camera_info()
            
            self.save_worker = SaveWorker(frame, class_path, filename, options, cam_info, self.session_manager.session_id)
            self.save_worker.finished.connect(self.on_save_finished)
            self.save_worker.start()
            
            self.status_bar.showMessage(f"💾 Saving {filename}...", 2000)

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to start save process: {str(e)}")
            
    def restore_settings(self):
        """Restore saved settings"""
        # Window geometry
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
    def closeEvent(self, event):
        """Clean shutdown"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.camera_thread.stop()
        event.accept()

def main():
    """Main entry point for the application."""
    # Run Qt plugin check for diagnostic purposes
    check_qt_plugins()

    app = QApplication(sys.argv)
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationName(APP_NAME)
    
    # Set a modern style if available
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")

    main_win = AIScaleDataCollector()
    main_win.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()