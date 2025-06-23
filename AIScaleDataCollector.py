#!/usr/bin/env python3
"""
AI-Scale Data Collector v2.1
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
from typing import Optional, Tuple, List, Dict, Any

from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import QPoint, QPropertyAnimation
from PySide6.QtWidgets import QSlider, QCheckBox, QScrollArea

# Try PySide6 first (better macOS compatibility), fallback to PyQt6
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QMessageBox, QInputDialog, QGridLayout,
        QDialog, QDialogButtonBox, QStyleFactory, QTextEdit
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QThread
    from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QAction

    # Add a dedicated function to check for Qt plugin paths
    from PySide6.QtCore import QLibraryInfo
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    import sqlite3


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
APP_VERSION = "2.2.0"
ORGANIZATION = "AI-Scale"
CONFIG_FILE = "config.json"
DATABASE_FILE = "data/metadata.db"
MIN_DISK_SPACE_MB = 100


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
    
class DatabaseManager:
    """Manages all interactions with the SQLite metadata database."""
    def __init__(self, db_file: str):
        self.db_path = Path(db_file)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._cursor = self._connection.cursor()
        self._create_table()

    def _create_table(self):
        """Creates the captures table if it doesn't exist."""
        self._cursor.execute("""
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                class_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                file_size INTEGER NOT NULL,
                camera_settings TEXT,
                session_id TEXT NOT NULL
            )
        """)
        self._connection.commit()
    
    def add_capture(self, metadata: CaptureMetadata):
        """Adds a new capture record to the database."""
        settings_json = json.dumps(metadata.camera_settings)
        try:
            self._cursor.execute("""
                INSERT INTO captures (filename, class_name, timestamp, width, height, file_size, camera_settings, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.filename,
                metadata.class_name,
                metadata.timestamp,
                metadata.resolution[0],
                metadata.resolution[1],
                metadata.file_size,
                settings_json,
                metadata.session_id
            ))
            self._connection.commit()
            logger.info(f"Added '{metadata.filename}' to database.")
        except sqlite3.IntegrityError:
            logger.warning(f"'{metadata.filename}' already exists in the database. Skipping.")
        except Exception as e:
            logger.error(f"Database Error: Could not add capture {metadata.filename}. Reason: {e}")
            self._connection.rollback()

    def get_class_counts(self) -> Dict[str, int]:
        """Gets the count of images for each class."""
        self._cursor.execute("SELECT class_name, COUNT(*) FROM captures GROUP BY class_name")
        return dict(self._cursor.fetchall())

    def get_total_captures(self) -> int:
        """Gets the total number of captures in the database."""
        self._cursor.execute("SELECT COUNT(id) FROM captures")
        result = self._cursor.fetchone()
        return result[0] if result else 0

    def close(self):
        """Closes the database connection."""
        if self._connection:
            self._connection.close()

class ConfigManager:
    """Manages loading and saving of application settings to a JSON file."""
    def __init__(self, config_file: str):
        self.config_path = Path(config_file)
        self.defaults = {
            "last_camera_index": 0,
            "window_geometry": None,
            "save_options": {
                "create_preview": False,
                "quality": 95
            },
            "camera_controls": {
                "brightness": 0,
                "contrast": 0,
                "saturation": 0,
                "exposure_comp": 0
            }
        }
        self.config = self._load()

    def _load(self) -> Dict[str, Any]:
        """Loads config from JSON file, creating it with defaults if it doesn't exist."""
        if not self.config_path.exists():
            logger.info(f"'{self.config_path}' not found, creating with default settings.")
            self.save(self.defaults)
            return self.defaults
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                # Ensure all keys from defaults are present
                for key, value in self.defaults.items():
                    config.setdefault(key, value)
                return config
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading '{self.config_path}': {e}. Using default settings.")
            return self.defaults

    def get(self, key: str, default: Any = None) -> Any:
        """Gets a value from the config."""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Sets a value in the config."""
        self.config[key] = value

    def save(self, data: Optional[Dict[str, Any]] = None):
        """Saves the current config to the JSON file."""
        to_save = data if data is not None else self.config
        try:
            with open(self.config_path, 'w') as f:
                json.dump(to_save, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save config to '{self.config_path}': {e}")

class SaveWorker(QThread):
    """Worker thread for saving images without blocking the UI"""
    finished = Signal(bool, str, object) # success, message, metadata_tuple

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
            # --- Pre-emptive Disk Space Check ---
            free_space_bytes = shutil.disk_usage(self.class_path.anchor).free
            free_space_mb = free_space_bytes / (1024 * 1024)
            
            if free_space_mb < MIN_DISK_SPACE_MB:
                raise IOError(f"Low disk space: {free_space_mb:.2f} MB remaining. "
                              f"Need at least {MIN_DISK_SPACE_MB} MB.")

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
                # No longer saving JSON file here, will be handled by main thread

            self.finished.emit(True, str(filepath), metadata)

        except Exception as e:
            self.finished.emit(False, str(e), None)


class CameraControlsWidget(QWidget):
    """Advanced camera controls for image quality adjustment"""
    
    settingsChanged = Signal(dict)
    
    def __init__(self, camera_thread):
        super().__init__()
        self.camera_thread = camera_thread
        self.init_ui()
        
    def init_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(8)
        
        # Title
        title = QLabel("<b>Camera Controls</b>")
        layout.addWidget(title, 0, 0, 1, 3)
        
        # Brightness
        layout.addWidget(QLabel("Brightness:"), 1, 0)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.update_controls)
        self.brightness_value = QLabel("0")
        layout.addWidget(self.brightness_slider, 1, 1)
        layout.addWidget(self.brightness_value, 1, 2)
        
        # Contrast
        layout.addWidget(QLabel("Contrast:"), 2, 0)
        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(-100, 100)
        self.contrast_slider.setValue(0)
        self.contrast_slider.valueChanged.connect(self.update_controls)
        self.contrast_value = QLabel("0")
        layout.addWidget(self.contrast_slider, 2, 1)
        layout.addWidget(self.contrast_value, 2, 2)
        
        # Saturation
        layout.addWidget(QLabel("Saturation:"), 3, 0)
        self.saturation_slider = QSlider(Qt.Orientation.Horizontal)
        self.saturation_slider.setRange(-100, 100)
        self.saturation_slider.setValue(0)
        self.saturation_slider.valueChanged.connect(self.update_controls)
        self.saturation_value = QLabel("0")
        layout.addWidget(self.saturation_slider, 3, 1)
        layout.addWidget(self.saturation_value, 3, 2)

        # --- Camera Mode ---
        layout.addWidget(QLabel("<b>Camera Mode</b>"), 4, 0, 1, 3)
        self.native_mode_cb = QCheckBox("Native Mode (Recommended)")
        self.native_mode_cb.setChecked(True)
        self.native_mode_cb.stateChanged.connect(self.on_native_mode_changed)
        layout.addWidget(self.native_mode_cb, 5, 0, 1, 3)
        
        # --- White Balance (Hardware) ---
        layout.addWidget(QLabel("<b>White Balance</b>"), 6, 0, 1, 3)
        self.wb_auto_cb = QCheckBox("Auto")
        self.wb_auto_cb.setChecked(True)
        self.wb_auto_cb.stateChanged.connect(self.update_controls)
        layout.addWidget(self.wb_auto_cb, 7, 0)

        self.wb_temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.wb_temp_slider.setRange(2000, 7500) # Kelvin scale
        self.wb_temp_slider.setValue(4500)
        self.wb_temp_slider.valueChanged.connect(self.update_controls)
        self.wb_temp_value = QLabel("4500 K")
        layout.addWidget(self.wb_temp_slider, 7, 1)
        layout.addWidget(self.wb_temp_value, 7, 2)
        
        # Add Tint control
        layout.addWidget(QLabel("WB Tint:"), 8, 0)
        self.wb_tint_slider = QSlider(Qt.Orientation.Horizontal)
        self.wb_tint_slider.setRange(-50, 50)
        self.wb_tint_slider.setValue(0)
        self.wb_tint_slider.valueChanged.connect(self.update_controls)
        self.wb_tint_value = QLabel("0")
        layout.addWidget(self.wb_tint_slider, 8, 1)
        layout.addWidget(self.wb_tint_value, 8, 2)
        
        # Exposure (repurposed as software brightness boost)
        layout.addWidget(QLabel("Exposure Comp:"), 9, 0)
        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self.exposure_slider.setRange(-10, 10)
        self.exposure_slider.setValue(0)
        self.exposure_slider.valueChanged.connect(self.update_controls)
        self.exposure_value = QLabel("0")
        layout.addWidget(self.exposure_slider, 9, 1)
        layout.addWidget(self.exposure_value, 9, 2)
        
        # Dehaze control (new)
        layout.addWidget(QLabel("<b>Haze Reduction</b>"), 10, 0, 1, 3)
        layout.addWidget(QLabel("Dehaze:"), 11, 0)
        self.dehaze_slider = QSlider(Qt.Orientation.Horizontal)
        self.dehaze_slider.setRange(0, 100)
        self.dehaze_slider.setValue(0)
        self.dehaze_slider.valueChanged.connect(self.update_controls)
        self.dehaze_value = QLabel("0")
        layout.addWidget(self.dehaze_slider, 11, 1)
        layout.addWidget(self.dehaze_value, 11, 2)
        
        # Quick presets for common scenarios
        layout.addWidget(QLabel("<b>Quick Presets</b>"), 12, 0, 1, 3)
        presets_layout = QHBoxLayout()
        
        indoor_btn = QPushButton("Indoor")
        indoor_btn.clicked.connect(lambda: self.apply_preset("indoor"))
        presets_layout.addWidget(indoor_btn)
        
        outdoor_btn = QPushButton("Outdoor")
        outdoor_btn.clicked.connect(lambda: self.apply_preset("outdoor"))
        presets_layout.addWidget(outdoor_btn)
        
        hazy_btn = QPushButton("Hazy")
        hazy_btn.clicked.connect(lambda: self.apply_preset("hazy"))
        presets_layout.addWidget(hazy_btn)
        
        layout.addLayout(presets_layout, 13, 0, 1, 3)
        
        # Reset button
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self.reset_all)
        layout.addWidget(reset_btn, 14, 0, 1, 3)
        
        # Apply custom styling
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #E5E5EA;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #007AFF;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox:disabled {
                color: #8E8E93;
            }
        """)
        
    def update_controls(self):
        """Unified method to update all software controls."""
        if not self.camera_thread:
            return
            
        brightness = self.brightness_slider.value()
        contrast = self.contrast_slider.value()
        saturation = self.saturation_slider.value()
        exposure = self.exposure_slider.value()
        dehaze = self.dehaze_slider.value()
        auto_wb = self.wb_auto_cb.isChecked()
        wb_temp = self.wb_temp_slider.value()
        wb_tint = self.wb_tint_slider.value()

        # Enable/disable controls based on modes
        native_mode = self.native_mode_cb.isChecked()
        self.wb_auto_cb.setEnabled(not native_mode)
        self.wb_temp_slider.setEnabled(not native_mode and not auto_wb)
        self.wb_tint_slider.setEnabled(not native_mode and not auto_wb)
        
        # In native mode, disable most manual controls
        if native_mode:
            auto_wb = True  # Force auto WB in native mode
        
        self.brightness_value.setText(str(brightness))
        self.contrast_value.setText(str(contrast))
        self.saturation_value.setText(str(saturation))
        self.exposure_value.setText(str(exposure))
        self.dehaze_value.setText(str(dehaze))
        self.wb_temp_value.setText(f"{wb_temp} K")
        self.wb_tint_value.setText(str(wb_tint))
        
        # Log the settings being applied
        logger.debug(f"Applying settings - Brightness: {brightness}, Contrast: {contrast}, Saturation: {saturation}, WB: {wb_temp}K, Auto: {auto_wb}")
        
        # Set hardware properties (now software-based)
        self.camera_thread.set_hardware_controls(
            auto_wb=auto_wb,
            wb_temp=wb_temp,
            wb_tint=wb_tint
        )
        
        # Set software properties
        self.camera_thread.set_software_controls(
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            exposure=exposure,
            dehaze=dehaze
        )
        
    def reset_all(self):
        self.native_mode_cb.setChecked(True)
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.saturation_slider.setValue(0)
        self.exposure_slider.setValue(0)
        self.dehaze_slider.setValue(0)
        self.wb_auto_cb.setChecked(True)
        self.wb_temp_slider.setValue(5500)  # Reset to neutral
        self.wb_tint_slider.setValue(0)
        
    def on_native_mode_changed(self):
        """Handle native mode checkbox changes with delay after stop."""
        native_mode = self.native_mode_cb.isChecked()
        
        # Get current camera index from the thread itself
        current_index = self.camera_thread.current_index
        if current_index == -1:  # Fallback if not initialized yet
            logger.warning("Camera index not found in thread, using config fallback.")
            if hasattr(self, 'config_manager'):
                current_index = self.config_manager.get("last_camera_index", 0)
            else:
                current_index = 0

        # Restart camera with new mode
        logger.info(f"Re-initializing camera at index {current_index} for mode change.")
        self.camera_thread.stop()
        time.sleep(0.5)  # Add delay to ensure camera is released
        if self.camera_thread.initialize_camera(current_index, native_mode):
            self.camera_thread.start()
            mode_str = "native" if native_mode else "custom"
            # Safely access status bar if available
            try:
                parent = self.parent()
                if parent and hasattr(parent, 'status_bar'):
                    parent.status_bar.showMessage(f"Switched to {mode_str} mode", 3000)
            except AttributeError:
                # Status bar not available, just log the change
                logger.info(f"Switched to {mode_str} mode")
    
    def apply_preset(self, preset_name):
        """Apply predefined settings for common scenarios."""
        presets = {
            "indoor": {
                "brightness": 10,
                "contrast": 10,
                "saturation": 5,
                "exposure": 0,
                "dehaze": 0,
                "wb_auto": False,
                "wb_temp": 3200,  # Warmer for indoor lighting
                "wb_tint": 0
            },
            "outdoor": {
                "brightness": 0,
                "contrast": 5,
                "saturation": 10,
                "exposure": 0,
                "dehaze": 20,
                "wb_auto": False,
                "wb_temp": 5600,  # Daylight
                "wb_tint": 0
            },
            "hazy": {
                "brightness": 5,
                "contrast": 20,
                "saturation": 15,
                "exposure": 0,
                "dehaze": 60,  # Strong dehaze
                "wb_auto": False,
                "wb_temp": 5500,
                "wb_tint": -10  # Slight green to counteract haze
            }
        }
        
        if preset_name in presets:
            preset = presets[preset_name]
            logger.info(f"Applying {preset_name} preset: {preset}")
            
            # Temporarily disconnect valueChanged signals to prevent multiple updates
            self.brightness_slider.valueChanged.disconnect()
            self.contrast_slider.valueChanged.disconnect()
            self.saturation_slider.valueChanged.disconnect()
            self.exposure_slider.valueChanged.disconnect()
            self.dehaze_slider.valueChanged.disconnect()
            self.wb_temp_slider.valueChanged.disconnect()
            self.wb_tint_slider.valueChanged.disconnect()
            
            # Set the values
            self.brightness_slider.setValue(preset["brightness"])
            self.contrast_slider.setValue(preset["contrast"])
            self.saturation_slider.setValue(preset["saturation"])
            self.exposure_slider.setValue(preset["exposure"])
            self.dehaze_slider.setValue(preset["dehaze"])
            self.wb_auto_cb.setChecked(preset["wb_auto"])
            self.wb_temp_slider.setValue(preset["wb_temp"])
            self.wb_tint_slider.setValue(preset["wb_tint"])
            
            # Reconnect the signals
            self.brightness_slider.valueChanged.connect(self.update_controls)
            self.contrast_slider.valueChanged.connect(self.update_controls)
            self.saturation_slider.valueChanged.connect(self.update_controls)
            self.exposure_slider.valueChanged.connect(self.update_controls)
            self.dehaze_slider.valueChanged.connect(self.update_controls)
            self.wb_temp_slider.valueChanged.connect(self.update_controls)
            self.wb_tint_slider.valueChanged.connect(self.update_controls)
            
            # Disable native mode when using presets
            self.native_mode_cb.setChecked(False)
            
            # Apply the settings to the camera thread
            self.update_controls()
            logger.info(f"Applied {preset_name} preset to camera thread")
            
            # Show feedback
            try:
                parent = self.parent()
                if parent and hasattr(parent, 'status_bar'):
                    parent.status_bar.showMessage(f"Applied {preset_name} preset", 3000)
            except AttributeError:
                logger.info(f"Applied {preset_name} preset")

class HistogramWidget(QWidget):
    """Live histogram display for exposure monitoring"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(150)
        self.setMaximumHeight(200)
        self.histogram_data = None
        
    def update_histogram(self, frame):
        """Update histogram from frame"""
        if frame is None:
            return
            
        # Calculate histograms
        hist_b = cv2.calcHist([frame], [0], None, [256], [0, 256])
        hist_g = cv2.calcHist([frame], [1], None, [256], [0, 256])
        hist_r = cv2.calcHist([frame], [2], None, [256], [0, 256])
        
        # Normalize
        hist_b = hist_b.flatten() / hist_b.max() if hist_b.max() > 0 else hist_b.flatten()
        hist_g = hist_g.flatten() / hist_g.max() if hist_g.max() > 0 else hist_g.flatten()
        hist_r = hist_r.flatten() / hist_r.max() if hist_r.max() > 0 else hist_r.flatten()
        
        self.histogram_data = (hist_b, hist_g, hist_r)
        self.update()
        
    def paintEvent(self, event):
        """Draw the histogram"""
        if not self.histogram_data:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        # Draw grid
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        for i in range(0, 11):
            x = int(self.width() * i / 10)
            painter.drawLine(x, 0, x, self.height())
            
        # Draw histograms
        hist_b, hist_g, hist_r = self.histogram_data
        
        for i in range(256):
            x = int(self.width() * i / 256)
            
            # Blue channel
            painter.setPen(QPen(QColor(0, 0, 255, 128), 1))
            h_b = int(self.height() * hist_b[i])
            painter.drawLine(x, self.height(), x, self.height() - h_b)
            
            # Green channel
            painter.setPen(QPen(QColor(0, 255, 0, 128), 1))
            h_g = int(self.height() * hist_g[i])
            painter.drawLine(x, self.height(), x, self.height() - h_g)
            
            # Red channel
            painter.setPen(QPen(QColor(255, 0, 0, 128), 1))
            h_r = int(self.height() * hist_r[i])
            painter.drawLine(x, self.height(), x, self.height() - h_r)

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
    frameReady = Signal(np.ndarray)
    statusUpdate = Signal(str, str)  # message, severity
    
    def __init__(self):
        super().__init__()
        self.camera = None
        self.running = False
        self.current_frame = None
        self.frame_times = deque(maxlen=30)
        self.fps = 0.0
        self.current_index = -1  # Track the current camera index
        
        # Software image processing values
        self.sw_brightness = 0
        self.sw_contrast = 0
        self.sw_saturation = 0
        self.sw_exposure_comp = 0
        
        # White balance values (defaults that preserve camera behavior)
        self.auto_wb = True  # Use camera's native auto WB by default
        self.manual_wb_temp = 5500  # Neutral temperature
        self.wb_tint = 0  # No tint adjustment
        self.native_mode = True  # New: preserve camera's natural settings
        
        # White balance estimation state
        self.wb_gains = np.array([1.0, 1.0, 1.0])  # BGR gains
        self.wb_history = deque(maxlen=10)  # Temporal smoothing
        self.scene_stable_count = 0  # Track scene stability
        self.last_histogram = None  # For scene change detection
        
        # Debug mode for white balance
        self.wb_debug_mode = False  # Can be toggled to show diagnostic info
        
        # Haze reduction
        self.dehaze_amount = 0  # 0-100 scale
        
    def set_software_controls(self, brightness=None, contrast=None, saturation=None, exposure=None, dehaze=None):
        """Update software control values with logging and error handling."""
        try:
            if brightness is not None:
                self.sw_brightness = brightness
                logger.debug(f"Set software brightness: {brightness}")
            if contrast is not None:
                self.sw_contrast = contrast
                logger.debug(f"Set software contrast: {contrast}")
            if saturation is not None:
                self.sw_saturation = saturation
                logger.debug(f"Set software saturation: {saturation}")
            if exposure is not None:
                self.sw_exposure_comp = exposure * 5
                logger.debug(f"Set software exposure compensation: {exposure * 5}")
            if dehaze is not None:
                self.dehaze_amount = dehaze
                logger.debug(f"Set software dehaze: {dehaze}")
        except Exception as e:
            logger.error(f"Error setting software controls: {e}")

    def set_hardware_controls(self, auto_wb=None, wb_temp=None, wb_tint=None):
        """Set white balance controls (software implementation) with logging and error handling."""
        try:
            if auto_wb is not None:
                self.auto_wb = auto_wb
                logger.debug(f"Set hardware auto white balance: {auto_wb}")
            if wb_temp is not None:
                self.manual_wb_temp = wb_temp
                logger.debug(f"Set hardware white balance temp: {wb_temp}")
            if wb_tint is not None:
                self.wb_tint = wb_tint
                logger.debug(f"Set hardware white balance tint: {wb_tint}")
        except Exception as e:
            logger.error(f"Error setting hardware controls: {e}")

    def _estimate_white_balance(self, frame: np.ndarray) -> np.ndarray:
        """
        Advanced automatic white balance using multiple algorithms.
        Specifically tuned for IMX219 sensor with blue tint correction.
        """
        try:
            # Convert to float for precise calculations
            frame_float = frame.astype(np.float32)
            h, w, c = frame_float.shape
            
            # 1. Robust Gray World with outlier exclusion
            # Exclude very dark (shadows) and very bright (highlights/overexposed) regions
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mask = (gray > 30) & (gray < 220)  # Exclude extreme values
            
            if np.sum(mask) < (h * w * 0.1):  # If too few pixels, use all
                mask = np.ones_like(gray, dtype=bool)
            
            # Calculate means only from valid regions
            b_mean = np.mean(frame_float[mask, 0])
            g_mean = np.mean(frame_float[mask, 1])
            r_mean = np.mean(frame_float[mask, 2])
            
            # Prevent division by zero
            if min(b_mean, g_mean, r_mean) < 1.0:
                return np.array([1.0, 1.0, 1.0])
            
            # Gray world assumption: RGB means should be equal
            avg_mean = (b_mean + g_mean + r_mean) / 3.0
            gray_world_gains = np.array([avg_mean/b_mean, avg_mean/g_mean, avg_mean/r_mean])
            
            # 2. White Point Detection (find bright neutral areas)
            # Look for pixels that could be white references
            bright_mask = gray > 180
            white_gains = np.array([1.0, 1.0, 1.0])
            
            if np.sum(bright_mask) > 100:  # Enough bright pixels
                b_white = np.mean(frame_float[bright_mask, 0])
                g_white = np.mean(frame_float[bright_mask, 1])
                r_white = np.mean(frame_float[bright_mask, 2])
                
                if min(b_white, g_white, r_white) > 50:  # Valid white point
                    max_white = max(b_white, g_white, r_white)
                    white_gains = np.array([max_white/b_white, max_white/g_white, max_white/r_white])
            
            # 3. IMX219 sensor-specific correction for blue bias
            # This sensor has stronger blue response in daylight conditions
            sensor_gains = np.array([0.90, 1.0, 1.05])  # Reduce blue, boost red slightly
            
            # 4. Combine algorithms with weights
            # Gray World: 60%, White Point: 25%, Sensor Correction: 15%
            combined_gains = (
                0.60 * gray_world_gains + 
                0.25 * white_gains + 
                0.15 * sensor_gains
            )
            
            # 5. Apply bounds and smoothing
            # Clamp gains to reasonable range to avoid over-correction
            combined_gains = np.clip(combined_gains, 0.5, 2.0)
            
            # Temporal smoothing for stability
            self.wb_history.append(combined_gains)
            if len(self.wb_history) > 1:
                # Weighted average with more weight on recent frames
                weights = np.linspace(0.5, 1.0, len(self.wb_history))
                weights /= np.sum(weights)
                
                smoothed_gains = np.zeros(3)
                for i, gains in enumerate(self.wb_history):
                    smoothed_gains += weights[i] * gains
                
                combined_gains = smoothed_gains
            
            # Normalize to preserve overall brightness
            combined_gains = combined_gains / np.mean(combined_gains)
            
            # Debug logging
            if self.wb_debug_mode:
                logger.info(f"WB Debug - Gray World: B={gray_world_gains[0]:.3f}, G={gray_world_gains[1]:.3f}, R={gray_world_gains[2]:.3f}")
                logger.info(f"WB Debug - Final Gains: B={combined_gains[0]:.3f}, G={combined_gains[1]:.3f}, R={combined_gains[2]:.3f}")
                logger.info(f"WB Debug - Mean RGB: {b_mean:.1f}, {g_mean:.1f}, {r_mean:.1f}")
            
            return combined_gains
            
        except Exception as e:
            logger.error(f"White balance estimation failed: {e}")
            # Return slight blue reduction as fallback for IMX219
            return np.array([0.90, 1.0, 1.05])

    def _kelvin_to_rgb_gains(self, kelvin: float) -> np.ndarray:
        """
        Convert color temperature to RGB gains using accurate color science.
        Calibrated specifically for IMX219 sensor characteristics.
        """
        # Clamp to reasonable range
        kelvin = np.clip(kelvin, 2000, 10000)
        
        # More accurate color temperature to RGB conversion
        # Based on CIE daylight illuminants and blackbody radiation
        if kelvin <= 4000:
            # Warm temperatures (candlelight to tungsten)
            r_gain = 1.0
            g_gain = 0.65 + 0.35 * (kelvin - 2000) / 2000
            b_gain = 0.25 + 0.45 * (kelvin - 2000) / 2000
        elif kelvin <= 5500:
            # Neutral warm (tungsten to daylight)
            t = (kelvin - 4000) / 1500
            r_gain = 1.0
            g_gain = 0.85 + 0.15 * t
            b_gain = 0.7 + 0.3 * t
        elif kelvin <= 6500:
            # Daylight range
            t = (kelvin - 5500) / 1000
            r_gain = 1.0 - 0.1 * t
            g_gain = 1.0
            b_gain = 1.0 + 0.1 * t
        else:
            # Cool temperatures (shade to overcast)
            t = (kelvin - 6500) / 3500
            r_gain = 0.9 - 0.2 * t
            g_gain = 1.0 - 0.05 * t
            b_gain = 1.1 + 0.15 * t
        
        # IMX219 sensor correction factors
        # This sensor tends to have stronger blue response - reduce blue bias
        sensor_correction = np.array([1.05, 1.0, 0.95])  # BGR - reduce blue, boost red
        
        # Apply sensor correction and convert to BGR order
        gains = np.array([b_gain, g_gain, r_gain]) * sensor_correction
        
        # Normalize to preserve brightness
        return gains / np.mean(gains)

    def _apply_tint_adjustment(self, gains: np.ndarray, tint: float) -> np.ndarray:
        """Apply green-magenta tint adjustment to gains."""
        # Tint adjustment primarily affects green channel
        # Positive tint = more magenta (less green)
        # Negative tint = more green
        tint_factor = 1.0 - (tint / 200.0)  # Scale tint to reasonable range
        adjusted_gains = gains.copy()
        adjusted_gains[1] *= tint_factor  # Adjust green channel
        return adjusted_gains / np.mean(adjusted_gains)  # Renormalize
    
    def _apply_dehaze(self, frame: np.ndarray, strength: float) -> np.ndarray:
        """
        Apply dehazing using simplified dark channel prior.
        Effective for removing atmospheric haze and improving clarity.
        """
        if strength <= 0:
            return frame
            
        try:
            # Normalize strength to 0-1 range
            strength = strength / 100.0
            
            # 1. Calculate dark channel
            # Find minimum value across color channels in local patches
            kernel_size = 15
            dark_channel = cv2.erode(frame.min(axis=2), np.ones((kernel_size, kernel_size)))
            
            # 2. Estimate atmospheric light
            # Use top 0.1% brightest pixels in dark channel
            flat_dark = dark_channel.flatten()
            num_pixels = len(flat_dark)
            top_pixels = int(max(1, num_pixels * 0.001))
            indices = np.argpartition(flat_dark, -top_pixels)[-top_pixels:]
            
            # Get corresponding pixels from original image
            h, w = dark_channel.shape
            y_coords = indices // w
            x_coords = indices % w
            atmospheric_light = frame[y_coords, x_coords].max(axis=0)
            
            # 3. Estimate transmission
            # t(x) = 1 - ω * min_c(min_y∈Ω(x)(I^c(y)/A^c))
            omega = 0.95 * strength  # Haze removal strength
            normalized = frame.astype(np.float32) / (atmospheric_light.astype(np.float32) + 1)
            dark_normalized = cv2.erode(normalized.min(axis=2), np.ones((kernel_size, kernel_size)))
            transmission = 1 - omega * dark_normalized
            transmission = np.maximum(transmission, 0.1)  # Avoid division by very small numbers
            
            # 4. Refine transmission using bilateral filter
            transmission = cv2.bilateralFilter(transmission.astype(np.float32), 9, 75, 75)
            
            # 5. Recover scene radiance
            # J(x) = (I(x) - A) / max(t(x), t0) + A
            transmission_3d = np.stack([transmission] * 3, axis=2)
            dehazed = (frame.astype(np.float32) - atmospheric_light) / transmission_3d + atmospheric_light
            
            # 6. Enhance contrast slightly after dehazing
            dehazed = np.clip(dehazed, 0, 255).astype(np.uint8)
            
            # Apply subtle contrast enhancement for stronger dehazing
            if strength > 0.5:
                # CLAHE for local contrast enhancement
                lab = cv2.cvtColor(dehazed, cv2.COLOR_BGR2LAB)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                lab[:, :, 0] = clahe.apply(lab[:, :, 0])
                dehazed = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            return dehazed
            
        except Exception as e:
            logger.error(f"Dehaze failed: {e}")
            return frame

    def initialize_camera(self, index=0, native_mode=True) -> bool:
        """Initialize camera with minimal interference to preserve native quality."""
        self.current_index = index  # Store the current index
        logger.info(f"Attempting to initialize camera at index {index} (native_mode={native_mode})...")
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

            if native_mode:
                # NATIVE MODE: Minimal interference - let camera use its defaults
                logger.info("Using native mode - preserving camera defaults")
                
                # Only set essential properties
                preview_config = IMX219_CONFIGS["preview"]
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, preview_config["width"])
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, preview_config["height"])
                self.camera.set(cv2.CAP_PROP_FPS, preview_config["fps"])
                
                # DON'T force specific FOURCC, auto-exposure, or white balance
                # Let the camera use its optimal settings
                
            else:
                # CUSTOM MODE: Full control
                logger.info("Using custom mode - applying specific settings")
                
                preview_config = IMX219_CONFIGS["preview"]
                target_width = preview_config["width"]
                target_height = preview_config["height"]
                target_fps = preview_config["fps"]
                
                self.camera.set(cv2.CAP_PROP_FOURCC, CAMERA_FOURCC)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
                self.camera.set(cv2.CAP_PROP_FPS, target_fps)
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
                self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                self.camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                self.camera.set(cv2.CAP_PROP_AUTO_WB, 1.0)
            
            # Allow time for the camera to stabilize
            time.sleep(0.5 if native_mode else 1.0)

            width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if width == 0 or height == 0:
                logger.error("Camera returned 0x0 resolution. It might be in use or drivers are faulty.")
                self.camera.release()
                self.statusUpdate.emit("Camera resolution is 0x0. Is it in use?", "error")
                return False

            mode_str = "native" if native_mode else "custom"
            self.statusUpdate.emit(f"Camera initialized ({mode_str}): {width}x{height}", "success")
            logger.info(f"Camera successfully initialized in {mode_str} mode: {width}x{height}.")
            return True
            
        except Exception as e:
            error_msg = f"Exception during camera init: {str(e)}"
            self.statusUpdate.emit(error_msg, "error")
            logger.exception(error_msg)
            return False
        
    def run(self):
        """Enhanced camera capture loop with software image processing"""
        self.running = True
        no_frame_count = 0
        
        while self.running:
            if self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                
                if ret and frame is not None:
                    no_frame_count = 0

                    # Apply software processing
                    processed_frame = self._process_frame(frame)
                    
                    self.current_frame = processed_frame
                    
                    # Correct FPS calculation over a rolling window
                    self.frame_times.append(time.perf_counter())
                    if len(self.frame_times) > 1:
                        time_span = self.frame_times[-1] - self.frame_times[0]
                        if time_span > 0:
                            self.fps = (len(self.frame_times) - 1) / time_span
                    
                    self.frameReady.emit(processed_frame)
                    
                else:
                    no_frame_count += 1
                    if no_frame_count > 100: # After ~1.6s of no frames
                        self.statusUpdate.emit("No frames received from camera.", "warning")
                        no_frame_count = 0 # Reset to avoid spamming
                        
            time.sleep(0.016)  # Target ~60Hz update rate

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Apply processing with automatic white balance correction by default."""
        if frame is None:
            return None
        
        # Always apply automatic white balance correction unless explicitly disabled
        # This fixes the persistent blue tint issue
        needs_processing = (
            self.auto_wb or  # Apply auto WB by default
            (not self.auto_wb and (self.manual_wb_temp != 5500 or self.wb_tint != 0)) or
            self.sw_brightness != 0 or
            self.sw_contrast != 0 or
            self.sw_saturation != 0 or
            self.sw_exposure_comp != 0 or
            (hasattr(self, 'dehaze_amount') and self.dehaze_amount > 0)
        )
        
        if not needs_processing:
            # This should rarely happen now since auto_wb is usually True
            return frame
        
        try:
            processed_frame = frame.copy()
            
            # 1. White Balance Correction (Auto or Manual)
            if self.auto_wb:
                # Automatic white balance - estimate from scene
                self.wb_gains = self._estimate_white_balance(processed_frame)
            elif self.manual_wb_temp != 5500 or self.wb_tint != 0:
                # Manual white balance based on temperature/tint
                self.wb_gains = self._kelvin_to_rgb_gains(self.manual_wb_temp)
                self.wb_gains = self._apply_tint_adjustment(self.wb_gains, self.wb_tint)
            else:
                # Fallback: apply minimal correction for IMX219 blue bias
                self.wb_gains = np.array([0.90, 1.0, 1.05])  # BGR
            
            # Apply white balance gains using LUT for performance
            for i in range(3):
                lut = np.arange(256, dtype=np.float32) * self.wb_gains[i]
                lut = np.clip(lut, 0, 255).astype(np.uint8)
                processed_frame[:, :, i] = cv2.LUT(processed_frame[:, :, i], lut)
            
            # 2. Brightness / Contrast adjustments (only when non-zero)
            brightness = self.sw_brightness + self.sw_exposure_comp
            contrast = self.sw_contrast
            
            if brightness != 0 or contrast != 0:
                contrast_alpha = 1.0 + (contrast / 100.0)
                processed_frame = cv2.convertScaleAbs(processed_frame, alpha=contrast_alpha, beta=brightness)
            
            # 3. Saturation adjustment (only when non-zero)
            if self.sw_saturation != 0:
                hls = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2HLS).astype(np.float32)
                saturation_factor = 1.0 + (self.sw_saturation / 100.0)
                hls[:, :, 2] = np.clip(hls[:, :, 2] * saturation_factor, 0, 255)
                processed_frame = cv2.cvtColor(hls.astype(np.uint8), cv2.COLOR_HLS2BGR)
            
            # 4. Haze Reduction (only when enabled)
            if hasattr(self, 'dehaze_amount') and self.dehaze_amount > 0:
                processed_frame = self._apply_dehaze(processed_frame, self.dehaze_amount)
            
            return processed_frame
            
        except Exception as e:
            logger.error(f"Frame processing failed: {e}")
            return frame

    def capture_image(self, quality="high") -> Optional[np.ndarray]:
        """
        Captures a high-resolution image. In native mode, uses current frame.
        In custom mode, temporarily switches to high resolution.
        """
        if not self.camera or not self.camera.isOpened():
            return None
            
        try:
            # In native mode, use current frame to avoid disrupting camera
            if getattr(self, 'native_mode', True):
                if self.current_frame is not None:
                    return self.current_frame.copy()
                # Fallback: single frame capture without resolution change
                ret, frame = self.camera.read()
                if ret and frame is not None:
                    return self._process_frame(frame)
                return None
            
            # Custom mode: temporarily switch to high resolution
            current_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            current_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Switch to high resolution for capture
            high_res_config = IMX219_CONFIGS["capture_high"]
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, high_res_config["width"])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, high_res_config["height"])
            
            # Flush buffer and capture fresh frame
            for _ in range(3):
                self.camera.read()
            
            ret, frame = self.camera.read()
            
            # Restore preview resolution
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, current_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, current_height)
            
            if ret and frame is not None:
                return self._process_frame(frame)
            
            return None
            
        except Exception as e:
            logger.error(f"Capture failed: {e}")
            return self.current_frame.copy() if self.current_frame is not None else None
            
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
        """Clean camera shutdown with logging."""
        self.running = False
        self.wait()
        if self.camera:
            try:
                self.camera.release()
                logger.info("Camera released successfully.")
            except Exception as e:
                logger.error(f"Error releasing camera: {e}")
            self.camera = None

class AIScaleDataCollector(QMainWindow):
    """Enhanced main application with better error handling and features"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager(CONFIG_FILE)
        self.db_manager = DatabaseManager(DATABASE_FILE)
        self.camera_thread = CameraThread()
        self.camera_thread.frameReady.connect(self.update_frame)
        self.camera_thread.statusUpdate.connect(self.handle_camera_status)
        self.current_class = ""
        self.dataset_path = Path("data/raw")
        self.session_manager = SessionManager(self.dataset_path)
        
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
        
    def toggle_wb_debug(self):
        """Toggle white balance debug mode"""
        if hasattr(self.camera_thread, 'wb_debug_mode'):
            self.camera_thread.wb_debug_mode = not self.camera_thread.wb_debug_mode
            state = "ON" if self.camera_thread.wb_debug_mode else "OFF"
            self.status_bar.showMessage(f"White Balance Debug: {state}", 3000)
            logger.info(f"White Balance Debug Mode: {state}")
    
    def show_wb_info(self):
        """Show current white balance information"""
        if hasattr(self.camera_thread, 'wb_gains'):
            gains = self.camera_thread.wb_gains
            auto_wb = self.camera_thread.auto_wb
            temp = self.camera_thread.manual_wb_temp
            tint = self.camera_thread.wb_tint
            
            info_text = f"""White Balance Status:
            
Mode: {'Automatic' if auto_wb else 'Manual'}
Temperature: {temp}K
Tint: {tint}

Current Gains (BGR):
Blue: {gains[0]:.3f}
Green: {gains[1]:.3f}
Red: {gains[2]:.3f}

Correction Active: {'Yes' if not np.allclose(gains, [1.0, 1.0, 1.0]) else 'No'}"""
            
            QMessageBox.information(self, "White Balance Info", info_text)
        else:
            QMessageBox.warning(self, "White Balance Info", "White balance information not available.")
        
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
        
        # Add debug menu
        debug_menu = menu_bar.addMenu("&Debug")
        wb_debug_action = QAction("Toggle &White Balance Debug", self)
        wb_debug_action.setShortcut("Ctrl+D")
        wb_debug_action.triggered.connect(self.toggle_wb_debug)
        debug_menu.addAction(wb_debug_action)
        
        # Add white balance info action
        wb_info_action = QAction("Show White Balance &Info", self)
        wb_info_action.setShortcut("Ctrl+I")
        wb_info_action.triggered.connect(self.show_wb_info)
        debug_menu.addAction(wb_info_action)
        
        # Add view menu for UI options
        view_menu = menu_bar.addMenu("&View")
        
        # Toggle histogram display
        histogram_action = QAction("Show &Histogram", self)
        histogram_action.setCheckable(True)
        histogram_action.setChecked(True)
        histogram_action.triggered.connect(self.toggle_histogram)
        view_menu.addAction(histogram_action)
        
        # Performance mode
        performance_action = QAction("&Performance Mode", self)
        performance_action.setCheckable(True)
        performance_action.triggered.connect(self.toggle_performance_mode)
        view_menu.addAction(performance_action)
        
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
            report = quick_validate_dataset(self.dataset_path, self.db_manager.db_path)
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
            
        # Try to restore the last used camera index from config
        last_cam_index = self.config_manager.get("last_camera_index", 0)
        
        # Find the corresponding item in the combobox
        for i in range(combo_box.count()):
            if combo_box.itemData(i) == last_cam_index:
                combo_box.setCurrentIndex(i)
                break

    def switch_camera(self, ui_index):
        """Switches camera with smooth UX feedback"""
        if not self.available_cameras or ui_index < 0:
            return

        camera_index = self.camera_combo.itemData(ui_index)
        if camera_index is None:
            return
            
        # Show switching feedback
        self.status_bar.showMessage("🔄 Switching camera...", 2000)
        self.camera_view.setText("Switching Camera...")
        QApplication.processEvents()  # Update UI immediately
        
        logger.info(f"Switching to camera index: {camera_index}")
        
        self.camera_thread.stop()
        
        # Use current native mode setting
        native_mode = True
        if hasattr(self, 'camera_controls') and hasattr(self.camera_controls, 'native_mode_cb'):
            native_mode = self.camera_controls.native_mode_cb.isChecked()
            
        if self.camera_thread.initialize_camera(camera_index, native_mode):
            self.start_camera_feed()
            self.config_manager.set("last_camera_index", camera_index)
            
            # Update camera controls with new camera
            if hasattr(self, 'camera_controls'):
                self.camera_controls.camera_thread = self.camera_thread
                self.camera_controls.reset_all()
                
            self.status_bar.showMessage(f"✅ Switched to Camera {camera_index}", 2000)
        else:
            self.handle_camera_status(f"Failed to switch to Camera {camera_index}", "error")
            # Revert combo box selection
            for i in range(self.camera_combo.count()):
                if self.camera_combo.itemData(i) == self.config_manager.get("last_camera_index", 0):
                    self.camera_combo.setCurrentIndex(i)
                    break

    def create_camera_section(self, parent_layout):
        """Enhanced camera view with a scrollable controls panel."""
        camera_container = QWidget()
        camera_layout = QVBoxLayout(camera_container)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.setSpacing(12)
        
        # Main camera area with side panel
        camera_area = QHBoxLayout()
        
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
        camera_area.addWidget(self.camera_view, 3)
        
        # --- Side Panel with Scroll Area ---
        side_panel_container = QWidget()
        side_panel_container.setMaximumWidth(320)
        side_panel_layout = QVBoxLayout(side_panel_container)
        side_panel_layout.setContentsMargins(0, 0, 0, 0)
        side_panel_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }") # Seamless look

        scroll_content_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_content_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10) # Padding for content
        scroll_layout.setSpacing(15)

        # Add camera controls widget to the scrollable layout
        self.camera_controls = CameraControlsWidget(self.camera_thread)
        scroll_layout.addWidget(self.camera_controls)
        
        # Add histogram display to the scrollable layout
        self.histogram_widget = HistogramWidget()
        scroll_layout.addWidget(self.histogram_widget)
        
        scroll_layout.addStretch(1) # Pushes content to the top
        
        scroll_area.setWidget(scroll_content_widget)
        side_panel_layout.addWidget(scroll_area)
        
        camera_area.addWidget(side_panel_container, 1)
        
        camera_layout.addLayout(camera_area, 1)
        
        # Enhanced status bar
        status_layout = QHBoxLayout()
        self.fps_label = QLabel("FPS: --")
        self.resolution_label = QLabel("Resolution: --")
        self.capture_indicator = QLabel("●")
        self.capture_indicator.setStyleSheet("color: #30D158; font-size: 16px;")
        self.capture_indicator.hide()
        
        status_layout.addWidget(self.fps_label)
        status_layout.addWidget(self.capture_indicator)
        status_layout.addStretch()
        status_layout.addWidget(self.resolution_label)
        camera_layout.addLayout(status_layout)
        
        parent_layout.addWidget(camera_container, 5)
        
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
        """Enhanced capture with visual feedback and better error handling"""
        if not self.current_class:
            self.shake_widget(self.capture_button)
            QMessageBox.warning(self, "No Selection", "📁 Please select a produce type first.")
            return
            
        # Disable capture button during process
        self.capture_button.setEnabled(False)
        self.capture_button.setText("Capturing...")
        
        # Visual capture indication
        self.capture_indicator.show()
        QTimer.singleShot(200, self.capture_indicator.hide)
        
        # Capture frame with timeout protection
        try:
            frame = self.camera_thread.capture_image()
            if frame is None:
                raise RuntimeError("Camera returned empty frame")
                
            # Check frame quality
            if frame.size == 0:
                raise RuntimeError("Frame has zero size")
                
            # Quality check for very dark/bright images
            mean_brightness = np.mean(frame)
            if mean_brightness < 10:
                logger.warning(f"Very dark image captured (brightness: {mean_brightness:.1f})")
            elif mean_brightness > 245:
                logger.warning(f"Very bright image captured (brightness: {mean_brightness:.1f})")
                
            # The frame is already processed by the camera thread
            frame_to_save = frame
            
            # Debug logging if enabled
            if hasattr(self.camera_thread, 'wb_debug_mode') and self.camera_thread.wb_debug_mode:
                gains = self.camera_thread.wb_gains
                logger.info(f"WB Debug - Gains: B={gains[0]:.3f}, G={gains[1]:.3f}, R={gains[2]:.3f}")
                
            # Save image
            self.save_image_async(frame_to_save)
            
            # Success feedback
            self.capture_button.setText("✓ Captured")
            self.capture_button.setStyleSheet("""
                QPushButton {
                    background-color: #30D158;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: 500;
                    font-size: 15px;
                }
            """)
            QTimer.singleShot(800, self.reset_capture_button)
            
        except Exception as e:
            self.shake_widget(self.capture_button)
            error_msg = str(e)
            logger.error(f"Capture failed: {error_msg}")
            
            if "empty frame" in error_msg:
                suggestion = "Check camera connection and lighting."
            elif "timeout" in error_msg.lower():
                suggestion = "Camera may be busy. Wait a moment and try again."
            else:
                suggestion = "Restart the application if this persists."
                
            QMessageBox.critical(
                self, 
                "Capture Failed", 
                f"📷 Could not capture image:\n\n{error_msg}\n\n💡 {suggestion}"
            )
            self.reset_capture_button()

    def shake_widget(self, widget):
        """Shake animation for error feedback"""
        original_pos = widget.pos()
        
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(100)
        animation.setLoopCount(3)
        
        animation.setKeyValueAt(0, original_pos)
        animation.setKeyValueAt(0.25, original_pos + QPoint(5, 0))
        animation.setKeyValueAt(0.75, original_pos + QPoint(-5, 0))
        animation.setKeyValueAt(1, original_pos)
        
        animation.start()

    def reset_capture_button(self):
        """Reset capture button after capture"""
        self.capture_button.setText("Capture Image")
        self.capture_button.setEnabled(True)
        # Reset button style
        self.capture_button.setStyleSheet("")
        
    def flash_success_indicator(self):
        """Flash green border on camera view for successful capture"""
        original_style = self.camera_view.styleSheet()
        success_style = original_style + "border: 3px solid #30D158;"
        
        self.camera_view.setStyleSheet(success_style)
        QTimer.singleShot(150, lambda: self.camera_view.setStyleSheet(original_style))
        
    def toggle_histogram(self, checked):
        """Toggle histogram widget visibility for performance."""
        if hasattr(self, 'histogram_widget'):
            self.histogram_widget.setVisible(checked)
            self.status_bar.showMessage(f"Histogram {'shown' if checked else 'hidden'}", 2000)
            
    def toggle_performance_mode(self, checked):
        """Toggle performance optimizations."""
        if checked:
            # Reduce update frequency further
            self.update_timer.setInterval(1000)  # 1 second
            # Hide histogram by default
            if hasattr(self, 'histogram_widget'):
                self.histogram_widget.setVisible(False)
            self.status_bar.showMessage("Performance mode enabled", 3000)
        else:
            # Restore normal frequency
            self.update_timer.setInterval(500)
            # Show histogram
            if hasattr(self, 'histogram_widget'):
                self.histogram_widget.setVisible(True)
            self.status_bar.showMessage("Performance mode disabled", 3000)
        
    def on_save_finished(self, success, result, metadata):
        """Handle save completion with enhanced feedback"""
        if success:
            filename = Path(result).name
            self.session_count += 1
            self.session_counter.setText(f"Captures: {self.session_count}")
            self.session_label.setText(f"<b>Session:</b> {self.session_count} captures")
            
            if metadata:
                self.session_manager.add_capture(metadata)
                self.db_manager.add_capture(metadata)
                
            # Show success with file size and quality info
            file_size_mb = Path(result).stat().st_size / (1024 * 1024)
            resolution = f"{metadata.resolution[0]}x{metadata.resolution[1]}" if metadata else "unknown"
            self.status_bar.showMessage(f"✅ Saved: {filename} ({file_size_mb:.1f} MB, {resolution})", 4000)
            
            # Flash green border on camera view
            self.flash_success_indicator()
        else:
            # Show detailed error with suggestions
            error_msg = str(result)
            if "disk space" in error_msg.lower():
                suggestion = "Free up disk space and try again."
            elif "permission" in error_msg.lower():
                suggestion = "Check folder permissions."
            else:
                suggestion = "Check camera connection and try again."
                
            QMessageBox.critical(
                self, 
                "Save Failed", 
                f"Could not save image:\n\n{error_msg}\n\n💡 {suggestion}"
            )
            self.status_bar.showMessage(f"❌ Save failed: {error_msg[:50]}...", 5000)
            
    def update_fps(self):
        """Update FPS display"""
        fps = self.camera_thread.fps
        self.fps_label.setText(f"FPS: {fps:.1f}")
        
    def update_frame(self, frame):
        """Update camera display with histogram"""
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        
        # Update histogram
        if hasattr(self, 'histogram_widget'):
            self.histogram_widget.update_histogram(frame)
        
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
        
        # Automatically start with the default (or last used) camera in native mode
        # Enable auto white balance by default to fix blue tint
        if self.available_cameras:
            initial_cam_index = self.camera_combo.itemData(self.camera_combo.currentIndex())
            # Ensure auto white balance is enabled by default
            self.camera_thread.auto_wb = True
            if self.camera_thread.initialize_camera(initial_cam_index, native_mode=True):
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
            self.update_timer.start(500)  # Update FPS less frequently for performance
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
                'create_preview': self.config_manager.get("save_options")["create_preview"],
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
        """Restore saved settings from config file"""
        # Window geometry
        geometry_hex = self.config_manager.get("window_geometry")
        if geometry_hex:
            self.restoreGeometry(bytes.fromhex(geometry_hex))
        
        # Restore camera control settings
        if hasattr(self, 'camera_controls'):
            controls_settings = self.config_manager.get("camera_controls")
            self.camera_controls.brightness_slider.setValue(controls_settings.get("brightness", 0))
            self.camera_controls.contrast_slider.setValue(controls_settings.get("contrast", 0))
            self.camera_controls.saturation_slider.setValue(controls_settings.get("saturation", 0))
            self.camera_controls.exposure_slider.setValue(controls_settings.get("exposure_comp", 0))


    def closeEvent(self, event):
        """Clean shutdown and save settings"""
        # Save camera control settings
        if hasattr(self, 'camera_controls'):
            controls_settings = {
                "brightness": self.camera_controls.brightness_slider.value(),
                "contrast": self.camera_controls.contrast_slider.value(),
                "saturation": self.camera_controls.saturation_slider.value(),
                "exposure_comp": self.camera_controls.exposure_slider.value()
            }
            self.config_manager.set("camera_controls", controls_settings)
            
        # Save window geometry
        self.config_manager.set("window_geometry", self.saveGeometry().toHex().data().decode())
        
        self.config_manager.save()
        self.db_manager.close()
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