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

        # --- White Balance (Hardware) ---
        layout.addWidget(QLabel("<b>White Balance</b>"), 4, 0, 1, 3)
        self.wb_auto_cb = QCheckBox("Auto")
        self.wb_auto_cb.setChecked(True)
        self.wb_auto_cb.stateChanged.connect(self.update_controls)
        layout.addWidget(self.wb_auto_cb, 5, 0)

        self.wb_temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.wb_temp_slider.setRange(2000, 7500) # Kelvin scale
        self.wb_temp_slider.setValue(4500)
        self.wb_temp_slider.valueChanged.connect(self.update_controls)
        self.wb_temp_value = QLabel("4500 K")
        layout.addWidget(self.wb_temp_slider, 5, 1)
        layout.addWidget(self.wb_temp_value, 5, 2)
        
        # Add Tint control
        layout.addWidget(QLabel("WB Tint:"), 6, 0)
        self.wb_tint_slider = QSlider(Qt.Orientation.Horizontal)
        self.wb_tint_slider.setRange(-50, 50)
        self.wb_tint_slider.setValue(0)
        self.wb_tint_slider.valueChanged.connect(self.update_controls)
        self.wb_tint_value = QLabel("0")
        layout.addWidget(self.wb_tint_slider, 6, 1)
        layout.addWidget(self.wb_tint_value, 6, 2)
        
        # Exposure (repurposed as software brightness boost)
        layout.addWidget(QLabel("Exposure Comp:"), 7, 0)
        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self.exposure_slider.setRange(-10, 10)
        self.exposure_slider.setValue(0)
        self.exposure_slider.valueChanged.connect(self.update_controls)
        self.exposure_value = QLabel("0")
        layout.addWidget(self.exposure_slider, 7, 1)
        layout.addWidget(self.exposure_value, 7, 2)
        
        # Auto modes
        self.auto_exposure_cb = QCheckBox("Auto Exposure (N/A)")
        self.auto_exposure_cb.setEnabled(False)
        layout.addWidget(self.auto_exposure_cb, 8, 0, 1, 2)
        
        # Reset button
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self.reset_all)
        layout.addWidget(reset_btn, 9, 0, 1, 3)
        
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
        auto_wb = self.wb_auto_cb.isChecked()
        wb_temp = self.wb_temp_slider.value()
        wb_tint = self.wb_tint_slider.value()

        self.wb_temp_slider.setEnabled(not auto_wb)
        self.wb_tint_slider.setEnabled(not auto_wb)
        
        self.brightness_value.setText(str(brightness))
        self.contrast_value.setText(str(contrast))
        self.saturation_value.setText(str(saturation))
        self.exposure_value.setText(str(exposure))
        self.wb_temp_value.setText(f"{wb_temp} K")
        self.wb_tint_value.setText(str(wb_tint))
        
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
            exposure=exposure
        )
        
    def reset_all(self):
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.saturation_slider.setValue(0)
        self.exposure_slider.setValue(0)
        self.wb_auto_cb.setChecked(True)
        self.wb_temp_slider.setValue(4500)
        self.wb_tint_slider.setValue(0)

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
        
        # Software image processing values
        self.sw_brightness = 0
        self.sw_contrast = 0
        self.sw_saturation = 0
        self.sw_exposure_comp = 0
        
        # White balance values
        self.auto_wb = True
        self.manual_wb_temp = 5500  # Kelvin
        self.wb_tint = 0  # Green-Magenta adjustment
        
        # White balance estimation state
        self.wb_gains = np.array([1.0, 1.0, 1.0])  # BGR gains
        self.wb_history = deque(maxlen=10)  # Temporal smoothing
        
    def set_software_controls(self, brightness=None, contrast=None, saturation=None, exposure=None):
        """Update software control values."""
        if brightness is not None:
            self.sw_brightness = brightness
        if contrast is not None:
            self.sw_contrast = contrast
        if saturation is not None:
            self.sw_saturation = saturation
        if exposure is not None:
            # Map exposure slider (-10 to 10) to a brightness compensation
            self.sw_exposure_comp = exposure * 5

    def set_hardware_controls(self, auto_wb=None, wb_temp=None, wb_tint=None):
        """Set white balance controls (software implementation)."""
        if auto_wb is not None:
            self.auto_wb = auto_wb
        if wb_temp is not None:
            self.manual_wb_temp = wb_temp
        if wb_tint is not None:
            self.wb_tint = wb_tint

    def _estimate_white_balance(self, frame: np.ndarray) -> np.ndarray:
        """
        Robust white balance estimation that handles backlighting.
        Returns BGR gain values to neutralize color cast.
        """
        if frame is None or frame.size == 0:
            return np.array([1.0, 1.0, 1.0])
        
        try:
            # Convert to float for precise calculations
            img_float = frame.astype(np.float32) / 255.0
            
            # 1. Create mask to exclude overexposed and underexposed regions
            gray = cv2.cvtColor(img_float, cv2.COLOR_BGR2GRAY)
            
            # Exclude very bright pixels (>0.95) and very dark pixels (<0.05)
            valid_mask = (gray > 0.05) & (gray < 0.95)
            
            # Also exclude pixels with any channel saturated
            channel_mask = np.all((img_float > 0.02) & (img_float < 0.98), axis=2)
            valid_mask = valid_mask & channel_mask
            
            # Ensure we have enough valid pixels
            valid_pixel_ratio = np.sum(valid_mask) / valid_mask.size
            if valid_pixel_ratio < 0.1:  # Less than 10% valid pixels
                logger.warning("Too few valid pixels for white balance estimation")
                return np.array([1.0, 1.0, 1.0])
            
            # 2. Method 1: Modified Grey World on valid pixels only
            valid_pixels = img_float[valid_mask]
            if valid_pixels.size > 0:
                avg_bgr = np.mean(valid_pixels, axis=0)
                # Avoid division by zero
                avg_bgr = np.maximum(avg_bgr, 0.001)
                gray_world_gains = 0.5 / avg_bgr  # Target middle gray
            else:
                gray_world_gains = np.array([1.0, 1.0, 1.0])
            
            # 3. Method 2: Detect near-white pixels in valid regions
            brightness = np.sum(valid_pixels, axis=1) / 3.0
            bright_mask = brightness > 0.6  # Reasonably bright pixels
            
            if np.sum(bright_mask) > 100:  # Need sufficient samples
                bright_pixels = valid_pixels[bright_mask]
                
                # Find pixels with low color variance (likely white/gray)
                pixel_std = np.std(bright_pixels, axis=1)
                neutral_mask = pixel_std < 0.1
                
                if np.sum(neutral_mask) > 50:
                    neutral_pixels = bright_pixels[neutral_mask]
                    avg_neutral = np.mean(neutral_pixels, axis=0)
                    avg_neutral = np.maximum(avg_neutral, 0.001)
                    
                    # White patch gains
                    target_white = 0.9  # Not full white to avoid clipping
                    white_patch_gains = target_white / avg_neutral
                else:
                    white_patch_gains = gray_world_gains
            else:
                white_patch_gains = gray_world_gains
            
            # 4. Combine methods with weighted average
            # Give more weight to white patch if we found good neutral pixels
            if 'neutral_pixels' in locals() and len(neutral_pixels) > 100:
                combined_gains = 0.7 * white_patch_gains + 0.3 * gray_world_gains
            else:
                combined_gains = 0.3 * white_patch_gains + 0.7 * gray_world_gains
            
            # 5. Limit the gains to reasonable ranges
            combined_gains = np.clip(combined_gains, 0.5, 2.0)
            
            # 6. Normalize gains to preserve overall brightness
            gain_avg = np.mean(combined_gains)
            if gain_avg > 0:
                combined_gains = combined_gains / gain_avg
            
            return combined_gains
            
        except Exception as e:
            logger.error(f"White balance estimation failed: {e}")
            return np.array([1.0, 1.0, 1.0])

    def _kelvin_to_rgb_gains(self, kelvin: float) -> np.ndarray:
        """
        Convert color temperature in Kelvin to RGB gains.
        Based on Planckian locus approximation.
        """
        # Normalize temperature to 0-1 range (2000K to 10000K)
        temp_norm = (kelvin - 2000) / 8000
        temp_norm = np.clip(temp_norm, 0, 1)
        
        # Approximate RGB gains for different temperatures
        # These values are empirically derived for typical cameras
        if kelvin < 5000:  # Warm (reddish)
            r_gain = 1.0
            g_gain = 0.8 + 0.2 * (kelvin - 2000) / 3000
            b_gain = 0.5 + 0.5 * (kelvin - 2000) / 3000
        elif kelvin > 6500:  # Cool (bluish)
            r_gain = 1.0 - 0.3 * (kelvin - 6500) / 3500
            g_gain = 1.0 - 0.1 * (kelvin - 6500) / 3500
            b_gain = 1.0
        else:  # Neutral range
            r_gain = 1.0
            g_gain = 1.0
            b_gain = 1.0
        
        # Convert to BGR order and normalize
        gains = np.array([b_gain, g_gain, r_gain])
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
            self.camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75) # Default to auto exposure on
            self.camera.set(cv2.CAP_PROP_AUTO_WB, 1.0) # Default to auto white balance on
            
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
        """Apply all software image processing steps with robust white balance."""
        if frame is None:
            return None
        
        try:
            # 1. White Balance Correction (do this first!)
            if self.auto_wb:
                # Estimate white balance from frame
                new_gains = self._estimate_white_balance(frame)
                
                # Temporal smoothing
                self.wb_history.append(new_gains)
                if len(self.wb_history) > 3:
                    # Use median for robustness against outliers
                    smoothed_gains = np.median(list(self.wb_history), axis=0)
                else:
                    smoothed_gains = new_gains
                
                self.wb_gains = smoothed_gains
            else:
                # Manual white balance
                self.wb_gains = self._kelvin_to_rgb_gains(self.manual_wb_temp)
                self.wb_gains = self._apply_tint_adjustment(self.wb_gains, self.wb_tint)
            
            # Apply white balance gains
            balanced_frame = frame.astype(np.float32)
            for i in range(3):  # BGR channels
                balanced_frame[:, :, i] *= self.wb_gains[i]
            
            # Clip to valid range
            balanced_frame = np.clip(balanced_frame, 0, 255).astype(np.uint8)
            
            # 2. Brightness / Contrast adjustments
            brightness = self.sw_brightness + self.sw_exposure_comp
            contrast_alpha = 1.0 + (self.sw_contrast / 100.0)
            
            adjusted_frame = cv2.convertScaleAbs(balanced_frame, alpha=contrast_alpha, beta=brightness)
            
            # 3. Saturation adjustment
            if self.sw_saturation != 0:
                hsv = cv2.cvtColor(adjusted_frame, cv2.COLOR_BGR2HSV).astype(np.float32)
                
                # Adjust saturation
                saturation_factor = 1.0 + (self.sw_saturation / 100.0)
                hsv[:, :, 1] *= saturation_factor
                hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
                
                adjusted_frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
            
            return adjusted_frame
            
        except Exception as e:
            logger.error(f"Frame processing failed: {e}")
            return frame  # Return original frame on error

    def capture_image(self, quality="high") -> Optional[np.ndarray]:
        """
        Captures the most recent PROCESSED frame from the preview stream.
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
        """Switches camera with proper control updates"""
        if not self.available_cameras or ui_index < 0:
            return

        camera_index = self.camera_combo.itemData(ui_index)
        if camera_index is None:
            return
            
        logger.info(f"Switching to camera index: {camera_index}")
        
        self.camera_thread.stop()
        
        if self.camera_thread.initialize_camera(camera_index):
            self.start_camera_feed()
            self.config_manager.set("last_camera_index", camera_index)
            
            # Update camera controls with new camera
            if hasattr(self, 'camera_controls'):
                self.camera_controls.camera_thread = self.camera_thread
                self.camera_controls.reset_all()
        else:
            self.handle_camera_status(f"Failed to switch to Camera {camera_index}", "error")

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
        """Enhanced capture with visual feedback and color correction"""
        if not self.current_class:
            # Shake animation on the button
            self.shake_widget(self.capture_button)
            QMessageBox.warning(self, "No Selection", "Please select a produce type first.")
            return
            
        # Visual capture indication
        self.capture_indicator.show()
        QTimer.singleShot(200, self.capture_indicator.hide)
        
        # Capture frame
        frame = self.camera_thread.capture_image()
        if frame is None:
            self.shake_widget(self.capture_button)
            QMessageBox.critical(self, "Capture Error", "Failed to capture image.")
            return
            
        # The frame is already processed by the camera thread, no extra processing needed here.
        frame_to_save = frame
            
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
        QTimer.singleShot(300, self.reset_capture_button)

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
        
    def on_save_finished(self, success, result, metadata):
        """Handle save completion with simple feedback"""
        if success:
            filename = Path(result).name
            self.session_count += 1
            self.session_counter.setText(f"Captures: {self.session_count}")
            self.session_label.setText(f"<b>Session:</b> {self.session_count} captures")
            
            if metadata:
                self.session_manager.add_capture(metadata)
                self.db_manager.add_capture(metadata) # Add to database
                
            self.status_bar.showMessage(f"Saved: {filename}", 3000)
        else:
            QMessageBox.critical(self, "Save Error", f"Failed to save: {result}")
            
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