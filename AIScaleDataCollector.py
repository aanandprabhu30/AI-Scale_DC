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
        QDialog, QDialogButtonBox
    )
    from PySide6.QtCore import Qt, QTimer, Signal as pyqtSignal, QThread, QSettings
    from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QAction
except ImportError:
    print("❌ PySide6 is not installed. Please run the setup script or install it manually:")
    print("   pip install PySide6")
    sys.exit(1)

import shutil
import csv

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
        """Initialize camera with robust error handling"""
        try:
            # Try AVFoundation backend first (best for macOS)
            self.camera = cv2.VideoCapture(index, CAMERA_BACKEND)
            
            if not self.camera.isOpened():
                # Fallback to default
                self.camera = cv2.VideoCapture(index)
                
            if self.camera.isOpened():
                # Set essential camera properties, but let resolution default for stability
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
                self.camera.set(cv2.CAP_PROP_AUTOFOCUS, CAMERA_AUTOFOCUS)
                self.camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE)
                
                # Give the camera a moment to stabilize
                time.sleep(0.5)

                # Verify settings
                actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                self.statusUpdate.emit(
                    f"Camera initialized: {actual_width}x{actual_height}", 
                    "success"
                )
                return True
            
            self.statusUpdate.emit("Camera not found", "error")
            return False
            
        except Exception as e:
            self.statusUpdate.emit(f"Camera init error: {str(e)}", "error")
            return False
        
    def run(self):
        """Enhanced camera capture loop with optimized FPS monitoring"""
        self.running = True
        
        while self.running:
            if self.camera and self.camera.isOpened():
                start_time = time.time()
                ret, frame = self.camera.read()
                
                if ret and frame is not None:
                    self.current_frame = frame
                    self.frameReady.emit(frame)
                    
                    # Calculate FPS
                    self.frame_times.append(time.time() - start_time)
                    if len(self.frame_times) == 30:
                        self.fps = 1.0 / (sum(self.frame_times) / len(self.frame_times))
                        
            time.sleep(0.016)  # Target 60Hz update rate
            
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
        self.current_class = ""
        self.dataset_path = Path("data/raw")
        self.session_manager = SessionManager(self.dataset_path)
        self.settings = QSettings(ORGANIZATION, APP_NAME)
        
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

        settings_action = QAction("Camera Settings...", self)
        settings_action.triggered.connect(self.show_camera_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def show_camera_settings(self):
        """Shows a dialog to select the camera."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Camera Settings")
        
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Select active camera:"))
        
        camera_combo = QComboBox()
        self.populate_camera_list(camera_combo)
        layout.addWidget(camera_combo)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.Accepted:
            selected_index = camera_combo.currentIndex()
            self.switch_camera(selected_index)

    def populate_camera_list(self, combo_box):
        """Finds and lists all available cameras in the provided combo box."""
        combo_box.clear()
        
        self.status_bar.showMessage("Finding cameras...")
        QApplication.processEvents()

        self.available_cameras = []
        for i in range(5):
            cap = cv2.VideoCapture(i, CAMERA_BACKEND)
            if cap.isOpened():
                self.available_cameras.append(i)
                try:
                    backend_name = cap.getBackendName()
                    combo_box.addItem(f"Camera {i} ({backend_name})")
                except Exception:
                    combo_box.addItem(f"Camera {i}")
                cap.release()
        
        current_camera_index = self.settings.value("camera_index", 0, type=int)
        
        if current_camera_index in self.available_cameras:
            ui_index = self.available_cameras.index(current_camera_index)
            combo_box.setCurrentIndex(ui_index)

        self.status_bar.clearMessage()

    def switch_camera(self, ui_index):
        """Stops the current camera and starts the selected one."""
        if not hasattr(self, 'available_cameras') or ui_index >= len(self.available_cameras):
            return

        camera_device_index = self.available_cameras[ui_index]
        self.settings.setValue("camera_index", camera_device_index)

        self.status_bar.showMessage(f"Switching to Camera {camera_device_index}...")
        self.camera_thread.stop()
        if self.camera_thread.initialize_camera(camera_device_index):
            self.start_camera_feed()
            self.status_bar.showMessage("Camera switched successfully.", 3000)
        else:
            self.camera_label.setText("Failed to switch camera.")
            self.camera_label.setStyleSheet("background-color: #000; color: #FFF;")
            QMessageBox.warning(self, "Camera Error", f"Could not open Camera {camera_device_index}.")

    def create_camera_section(self, parent_layout):
        """Create large, prominent camera view"""
        # Camera container
        camera_container = QWidget()
        camera_layout = QVBoxLayout(camera_container)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.setSpacing(12)
        
        # Camera display
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(800, 500)
        self.camera_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border-radius: 12px;
                border: 2px solid #E5E5EA;
            }
        """)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setScaledContents(False)
        camera_layout.addWidget(self.camera_label)
        
        # Simple camera info bar
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("""
            QLabel {
                color: #8E8E93;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        info_layout.addWidget(self.fps_label)
        
        info_layout.addStretch()
        
        self.resolution_label = QLabel("Resolution: --")
        self.resolution_label.setStyleSheet("""
            QLabel {
                color: #8E8E93;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        info_layout.addWidget(self.resolution_label)
        
        camera_layout.addLayout(info_layout)
        parent_layout.addWidget(camera_container)
        
    def create_simple_controls(self, parent_layout):
        """Create simplified and aligned controls section using a grid."""
        controls_container = QWidget()
        layout = QGridLayout(controls_container)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 10, 0, 0)

        # --- Column 0 & 1: Produce Selection ---
        produce_label = QLabel("Produce Type:")
        produce_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(produce_label, 0, 0, 1, 2) # Span 2 columns for the label

        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(220)
        self.class_combo.setPlaceholderText("Select produce type...")
        self.class_combo.currentTextChanged.connect(self.on_class_changed)
        layout.addWidget(self.class_combo, 1, 0)

        add_btn = QPushButton("+ Add New")
        add_btn.clicked.connect(self.show_add_class_dialog)
        layout.addWidget(add_btn, 1, 1)
        
        # --- Column 2: Spacer ---
        layout.setColumnStretch(2, 1)

        # --- Column 3: Info & Settings ---
        session_label = QLabel("Session:")
        session_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(session_label, 0, 3)

        self.session_info_label = QLabel("No captures yet")
        self.session_info_label.setStyleSheet("color: #8E8E93;")
        layout.addWidget(self.session_info_label, 1, 3)

        # --- Column 5: Capture Button ---
        self.capture_button = QPushButton("Capture Image")
        self.capture_button.setMinimumHeight(55) # Match other controls height
        self.capture_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #0056CC; }
            QPushButton:pressed { background-color: #004499; }
            QPushButton:disabled {
                background-color: #E5E5EA;
                color: #8E8E93;
            }
        """)
        self.capture_button.clicked.connect(self.capture_image)
        self.capture_button.setEnabled(False)
        layout.addWidget(self.capture_button, 0, 5, 2, 1) # Span 2 rows
        
        # --- Final Stretch ---
        layout.setColumnStretch(6, 1)

        parent_layout.addWidget(controls_container)
        
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
                index = self.class_combo.findText(class_name)
                if index >= 0:
                    self.class_combo.setCurrentIndex(index)
                    
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
            self.session_info_label.setText(f"{self.session_count} images captured")
            
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
        scaled = pixmap.scaled(self.camera_label.size(),
                              Qt.KeepAspectRatio,
                              Qt.SmoothTransformation)
        self.camera_label.setPixmap(scaled)
        
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
        """Load produce classes"""
        try:
            self.dataset_path.mkdir(parents=True, exist_ok=True)
            
            classes = []
            for item in self.dataset_path.iterdir():
                if item.is_dir() and not item.name.startswith('.') and item.name != 'sessions':
                    classes.append(item.name)
                    
            self.class_combo.clear()
            self.class_combo.addItems(sorted(classes))
            
        except Exception as e:
            self.status_bar.showMessage(f"Error loading classes: {str(e)}", 5000)
            
    def setup_camera(self):
        """Initialize camera with status updates using the saved index."""
        self.camera_thread.statusUpdate.connect(self.handle_camera_status)
        
        camera_index = self.settings.value("camera_index", 0, type=int)
        
        if not self.camera_thread.initialize_camera(camera_index):
            QMessageBox.critical(self, "Camera Error", 
                               "Could not initialize camera.\n"
                               "Please check connection or select a different camera in File -> Camera Settings.")
            
    def start_camera_feed(self):
        """Connect signals and start the camera thread"""
        self.camera_thread.frameReady.connect(self.update_frame)
        self.camera_thread.start()
        
        # Setup FPS timer
        if not hasattr(self, 'fps_timer'):
            self.fps_timer = QTimer()
            self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)
            
    def handle_camera_status(self, message, severity):
        """Handle camera status updates"""
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
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show window
    window = AIScaleDataCollector()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()