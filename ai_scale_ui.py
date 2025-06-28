#!/usr/bin/env python3
"""
AI-Scale Data Collector v2.4.0
Desktop application for Rockchip RK3568 boards with camera/scale integration
"""

import sys
import os
import json
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

# Debug flag - set to False to disable debug output
DEBUG = False

# Suppress OpenCV warnings and errors
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
cv2.setUseOptimized(True)

# Suppress Qt warnings
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'

try:
    import serial
    SCALE_AVAILABLE = True
except ImportError:
    SCALE_AVAILABLE = False

# Try PySide6 first, fallback to PyQt5 for ARM64 compatibility
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSlider, QGroupBox, QGridLayout,
        QSplitter, QStatusBar, QMessageBox, QCheckBox
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSize
    from PySide6.QtGui import QPixmap, QImage, QFont, QPalette, QColor
    QT_FRAMEWORK = "PySide6"
except ImportError:
    try:
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QComboBox, QSlider, QGroupBox, QGridLayout,
            QSplitter, QStatusBar, QMessageBox, QCheckBox
        )
        from PyQt5.QtCore import Qt, QTimer, pyqtSignal as Signal, QThread, QSize
        from PyQt5.QtGui import QPixmap, QImage, QFont, QPalette, QColor
        QT_FRAMEWORK = "PyQt5"
        print("Using PyQt5 fallback for ARM64 compatibility")
    except ImportError:
        print("Error: Neither PySide6 nor PyQt5 is available")
        print("For ARM64 systems, install: sudo apt-get install python3-pyqt5")
        sys.exit(1)

from camera_backend import CameraBackend

try:
    from scale_interface import ScaleInterface
    SCALE_AVAILABLE = True
except ImportError:
    print("Warning: pyserial not installed. Scale functionality will be disabled.")
    SCALE_AVAILABLE = False
    # Create a dummy ScaleInterface class
    class ScaleInterface:
        def __init__(self):
            pass
        def get_reading(self):
            return None

DEBUG = False

class ImageProcessor:
    """Advanced image processing for color correction and enhancement"""
    
    def __init__(self):
        # Natural CLAHE for visually pleasing local contrast
        self.clahe_bgr = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        self.clahe_lab = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    
    def apply_white_balance(self, image: np.ndarray, temp_offset: float = 0.0) -> np.ndarray:
        """Apply white balance correction to reduce bluish haze"""
        if image is None or image.size == 0:
            return image
            
        # Convert to LAB color space for better color manipulation
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Adjust A and B channels to correct color temperature
        # Positive temp_offset reduces blue cast, negative increases warmth
        a_adj = cv2.add(a, int(temp_offset * 10))  # Green-Red axis
        b_adj = cv2.subtract(b, int(temp_offset * 8))  # Blue-Yellow axis
        
        # Merge and convert back
        lab_balanced = cv2.merge([l, a_adj, b_adj])
        balanced = cv2.cvtColor(lab_balanced, cv2.COLOR_LAB2BGR)
        
        return balanced
    
    def enhance_colors(self, image: np.ndarray, saturation: float = 1.0, 
                      vibrance: float = 0.0) -> np.ndarray:
        """Enhance color accuracy, especially reds, greens, yellows"""
        if image is None or image.size == 0:
            return image
            
        # Convert to HSV for saturation adjustment
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        # Apply saturation enhancement
        if saturation != 1.0:
            s = cv2.multiply(s, saturation)
            s = np.clip(s, 0, 255).astype(np.uint8)
        
        # Apply vibrance (selective saturation for less saturated colors)
        if vibrance > 0:
            # Create mask for less saturated pixels
            mask = s < 128
            s = s.astype(np.int16)
            s[mask] = np.clip(s[mask] + int(vibrance * 30), 0, 255)
            s = s.astype(np.uint8)
        
        enhanced = cv2.merge([h, s, v])
        return cv2.cvtColor(enhanced, cv2.COLOR_HSV2BGR)
    
    def apply_gamma_correction(self, image: np.ndarray, gamma: float = 1.0) -> np.ndarray:
        """Apply gamma correction for brightness/contrast balance"""
        if image is None or image.size == 0 or gamma == 1.0:
            return image
        # Clamp gamma to avoid division by zero
        gamma = max(gamma, 0.01)
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 
                         for i in np.arange(0, 256)]).astype("uint8")
        return cv2.LUT(image, table)
    
    def apply_clahe(self, image: np.ndarray, channel: str = 'lab') -> np.ndarray:
        if DEBUG:
            print("apply_clahe called")
        if image is None or image.size == 0:
            return image
        if channel == 'lab':
            # Apply to L channel in LAB space
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l_clahe = self.clahe_lab.apply(l)
            enhanced = cv2.merge([l_clahe, a, b])
            lab2bgr = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
            # Also apply to BGR for extra drama
            b, g, r = cv2.split(lab2bgr)
            b = self.clahe_bgr.apply(b)
            g = self.clahe_bgr.apply(g)
            r = self.clahe_bgr.apply(r)
            return cv2.merge([b, g, r])
        else:
            # Apply to each BGR channel
            b, g, r = cv2.split(image)
            b_clahe = self.clahe_bgr.apply(b)
            g_clahe = self.clahe_bgr.apply(g)
            r_clahe = self.clahe_bgr.apply(r)
            return cv2.merge([b_clahe, g_clahe, r_clahe])
    
    def process_frame(self, image: np.ndarray, settings: Dict[str, float]) -> np.ndarray:
        if DEBUG:
            print(f"[DEBUG] process_frame called with clahe_enabled={settings.get('clahe_enabled', False)}")
            print("process_frame settings:", settings)
        if image is None or image.size == 0:
            return image
        result = image.copy()
        # White balance correction (reduces bluish haze)
        if settings.get('white_balance', 0.0) != 0.0:
            result = self.apply_white_balance(result, settings['white_balance'])
        # Brightness and contrast (midpoint-shift for photo editor effect)
        brightness_norm = settings.get('brightness', 0.0)  # -1.0 to +1.0
        brightness = int(brightness_norm * 100)            # -100 to +100 for OpenCV
        contrast = settings.get('contrast', 1.0)           # 0.1 to 2.0 for OpenCV
        contrast = max(contrast, 0.01)  # Prevent black screen at zero contrast
        mid = 128
        if brightness != 0 or contrast != 1.0:
            result = cv2.addWeighted(result, contrast, np.full(result.shape, mid, result.dtype), 1 - contrast, brightness)
        # Gamma correction (with safety check)
        gamma = settings.get('gamma', 1.0)
        gamma = max(gamma, 0.01)  # Prevent black screen at zero gamma
        if gamma != 1.0:
            result = self.apply_gamma_correction(result, gamma)
        # Color enhancement
        if settings.get('saturation', 1.0) != 1.0 or settings.get('vibrance', 0.0) != 0.0:
            result = self.enhance_colors(result, 
                                       settings.get('saturation', 1.0),
                                       settings.get('vibrance', 0.0))
        # CLAHE for local contrast
        if settings.get('clahe_enabled', False):
            if DEBUG:
                print("CLAHE ENABLED - applying CLAHE")
            result = self.apply_clahe(result, 'lab')
        return result


class CameraControlWidget(QWidget):
    """Real-time camera control panel"""
    
    settings_changed = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.settings = {
            'brightness': 0.0,
            'contrast': 1.0,
            'gamma': 1.0,
            'saturation': 1.0,
            'vibrance': 0.0,
            'white_balance': 0.0,
            'clahe_enabled': False
        }
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(18)
        
        # Image Enhancement Group
        enhance_group = QGroupBox("Image Enhancement")
        enhance_layout = QGridLayout()
        
        # Brightness (-100% to +100%)
        enhance_layout.addWidget(QLabel("Brightness:"), 0, 0)
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.update_brightness)
        self.brightness_label = QLabel("0%")
        enhance_layout.addWidget(self.brightness_slider, 0, 1)
        enhance_layout.addWidget(self.brightness_label, 0, 2)
        
        # Contrast (10% to 200%)
        enhance_layout.addWidget(QLabel("Contrast:"), 1, 0)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(10, 200)  # 10% to 200%
        self.contrast_slider.setValue(100)  # Default to 1.0
        self.contrast_slider.valueChanged.connect(self.update_contrast)
        self.contrast_label = QLabel("100%")
        enhance_layout.addWidget(self.contrast_slider, 1, 1)
        enhance_layout.addWidget(self.contrast_label, 1, 2)
        
        # Gamma (10% to 200%)
        enhance_layout.addWidget(QLabel("Gamma:"), 2, 0)
        self.gamma_slider = QSlider(Qt.Horizontal)
        self.gamma_slider.setRange(10, 200)  # 10% to 200%
        self.gamma_slider.setValue(100)  # Default to 1.0
        self.gamma_slider.valueChanged.connect(self.update_gamma)
        self.gamma_label = QLabel("100%")
        enhance_layout.addWidget(self.gamma_slider, 2, 1)
        enhance_layout.addWidget(self.gamma_label, 2, 2)
        
        enhance_group.setLayout(enhance_layout)
        layout.addWidget(enhance_group)
        
        # Color Correction Group
        color_group = QGroupBox("Color Correction")
        color_layout = QGridLayout()
        
        # White Balance (-100% to +100%)
        color_layout.addWidget(QLabel("White Balance:"), 0, 0)
        self.wb_slider = QSlider(Qt.Horizontal)
        self.wb_slider.setRange(-100, 100)
        self.wb_slider.setValue(0)
        self.wb_slider.valueChanged.connect(self.update_white_balance)
        self.wb_label = QLabel("0%")
        color_layout.addWidget(self.wb_slider, 0, 1)
        color_layout.addWidget(self.wb_label, 0, 2)
        
        # Saturation (0% to 200%)
        color_layout.addWidget(QLabel("Saturation:"), 1, 0)
        self.saturation_slider = QSlider(Qt.Horizontal)
        self.saturation_slider.setRange(0, 200)
        self.saturation_slider.setValue(100)
        self.saturation_slider.valueChanged.connect(self.update_saturation)
        self.saturation_label = QLabel("100%")
        color_layout.addWidget(self.saturation_slider, 1, 1)
        color_layout.addWidget(self.saturation_label, 1, 2)
        
        # Vibrance (0% to 100%)
        color_layout.addWidget(QLabel("Vibrance:"), 2, 0)
        self.vibrance_slider = QSlider(Qt.Horizontal)
        self.vibrance_slider.setRange(0, 100)
        self.vibrance_slider.setValue(0)
        self.vibrance_slider.valueChanged.connect(self.update_vibrance)
        self.vibrance_label = QLabel("0%")
        color_layout.addWidget(self.vibrance_slider, 2, 1)
        color_layout.addWidget(self.vibrance_label, 2, 2)
        
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        
        # Advanced Options
        advanced_group = QGroupBox("Advanced")
        advanced_layout = QVBoxLayout()
        
        self.clahe_checkbox = QCheckBox("Enable CLAHE (Local Contrast)")
        self.clahe_checkbox.setStyleSheet("font-weight: 700; color: #007aff; font-size: 17px; padding: 10px 0;")
        self.clahe_checkbox.setToolTip("Very strong effect for demo purposes!")
        self.clahe_checkbox.stateChanged.connect(self.update_clahe)
        advanced_layout.addWidget(self.clahe_checkbox)
        
        # CLAHE ON label
        self.clahe_on_label = QLabel("CLAHE ON")
        self.clahe_on_label.setStyleSheet("color: #fff; background: #b71c1c; font-weight: bold; padding: 4px 12px; border-radius: 8px;")
        self.clahe_on_label.setAlignment(Qt.AlignCenter)
        self.clahe_on_label.hide()
        advanced_layout.addWidget(self.clahe_on_label)
        
        # Reset button
        reset_btn = QPushButton("Reset All")
        reset_btn.setStyleSheet("background: #f0f0f3; color: #007aff; font-weight: 600; font-size: 16px; border-radius: 8px; margin-top: 10px;")
        reset_btn.clicked.connect(self.reset_settings)
        advanced_layout.addWidget(reset_btn)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def update_brightness(self, value):
        norm = value / 100.0
        self.settings['brightness'] = norm
        self.brightness_label.setText(f"{value}%")
        self.settings_changed.emit(self.get_settings())
    
    def update_contrast(self, value):
        norm = value / 100.0
        self.settings['contrast'] = norm
        self.contrast_label.setText(f"{value}%")
        self.settings_changed.emit(self.get_settings())
    
    def update_gamma(self, value):
        norm = value / 100.0
        self.settings['gamma'] = norm
        self.gamma_label.setText(f"{value}%")
        self.settings_changed.emit(self.get_settings())
    
    def update_white_balance(self, value):
        norm = value / 100.0
        self.settings['white_balance'] = norm
        self.wb_label.setText(f"{value}%")
        self.settings_changed.emit(self.get_settings())
    
    def update_saturation(self, value):
        norm = value / 100.0
        self.settings['saturation'] = norm
        self.saturation_label.setText(f"{value}%")
        self.settings_changed.emit(self.get_settings())
    
    def update_vibrance(self, value):
        norm = value / 100.0
        self.settings['vibrance'] = norm
        self.vibrance_label.setText(f"{value}%")
        self.settings_changed.emit(self.get_settings())
    
    def update_clahe(self, state):
        if DEBUG:
            print(f"[DEBUG] update_clahe called with state={state}")
        self.settings['clahe_enabled'] = state == Qt.Checked
        # Show or hide CLAHE ON label
        if self.settings['clahe_enabled']:
            self.clahe_on_label.show()
        else:
            self.clahe_on_label.hide()
        self.settings_changed.emit(self.get_settings())
    
    def reset_settings(self):
        """Reset all settings to defaults"""
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(100)
        self.gamma_slider.setValue(100)
        self.wb_slider.setValue(0)
        self.saturation_slider.setValue(100)
        self.vibrance_slider.setValue(0)
        self.clahe_checkbox.setChecked(False)
    
    def load_settings(self, settings_dict):
        """Load settings from dictionary"""
        if not settings_dict:
            return
        
        # Update internal settings
        self.settings.update(settings_dict)
        
        # Update UI controls
        if 'brightness' in settings_dict:
            self.brightness_slider.setValue(int(settings_dict['brightness'] * 100))
        if 'contrast' in settings_dict:
            self.contrast_slider.setValue(int(settings_dict['contrast'] * 100))
        if 'gamma' in settings_dict:
            self.gamma_slider.setValue(int(settings_dict['gamma'] * 100))
        if 'white_balance' in settings_dict:
            self.wb_slider.setValue(int(settings_dict['white_balance'] * 100))
        if 'saturation' in settings_dict:
            self.saturation_slider.setValue(int(settings_dict['saturation'] * 100))
        if 'vibrance' in settings_dict:
            self.vibrance_slider.setValue(int(settings_dict['vibrance'] * 100))
        if 'clahe_enabled' in settings_dict:
            self.clahe_checkbox.setChecked(settings_dict['clahe_enabled'])
    
    def get_settings(self):
        """Get current settings dictionary, always reflecting the UI state."""
        settings = self.settings.copy()
        settings['clahe_enabled'] = self.clahe_checkbox.isChecked()
        return settings
    
    def set_white_balance(self, value):
        """Set white balance value programmatically"""
        self.wb_slider.setValue(int(value * 100))
        self.settings['white_balance'] = value
        self.settings_changed.emit(self.get_settings())


class AIScaleMainWindow(QMainWindow):
    """Main application window optimized for 1366x768 display"""
    
    def __init__(self):
        super().__init__()
        self.camera_backend = CameraBackend()
        self.scale_interface = ScaleInterface()
        self.image_processor = ImageProcessor()
        self.current_frame = None
        self.current_settings = {}
        self.current_camera_index = 0
        
        self.init_ui()
        self.init_camera()
        self.init_timer()
        
        # Load saved settings
        self.load_settings()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("AI-Scale Data Collector v2.4.0")
        self.setMinimumSize(1366, 768)
        font = QFont()
        font.setPointSize(15)
        font.setFamily("Arial, Helvetica, sans-serif")
        self.setFont(font)
        
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Camera view
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Camera selection
        camera_layout = QHBoxLayout()
        camera_layout.addWidget(QLabel("Camera:"))
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumHeight(32)
        self.camera_combo.setMaximumWidth(220)
        self.camera_combo.setStyleSheet("font-size: 15px; padding: 4px 10px; border-radius: 8px;")
        self.camera_combo.currentIndexChanged.connect(self.change_camera)
        camera_layout.addWidget(self.camera_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMinimumHeight(32)
        refresh_btn.setMaximumWidth(110)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                color: #fff;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 500;
                padding: 6px 18px;
            }
            QPushButton:hover {
                background-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #005bb5;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_cameras)
        camera_layout.addWidget(refresh_btn)
        camera_layout.addStretch()
        
        left_layout.addLayout(camera_layout)
        
        # Camera info label
        self.camera_info_label = QLabel("Camera: Not connected")
        self.camera_info_label.setStyleSheet("""
            font-size: 14px;
            color: #666;
            padding: 8px 0;
        """)
        left_layout.addWidget(self.camera_info_label)
        
        # Camera display
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(800, 600)
        self.camera_label.setStyleSheet("border: 2px solid #e0e0e0; background-color: #fff; color: #222; border-radius: 18px;")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setText("No camera connected")
        left_layout.addWidget(self.camera_label)
        
        # Capture controls
        controls_layout = QHBoxLayout()
        
        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.setMinimumHeight(40)
        self.capture_btn.setMaximumWidth(220)
        self.capture_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                color: #fff;
                border: none;
                border-radius: 12px;
                font-size: 17px;
                font-weight: 600;
                padding: 10px 0;
            }
            QPushButton:hover {
                background-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #005bb5;
            }
        """)
        self.capture_btn.clicked.connect(self.capture_image)
        controls_layout.addWidget(self.capture_btn)
        
        # Scale reading display
        self.scale_label = QLabel("Scale: Not connected")
        self.scale_label.setStyleSheet("font-weight: bold; color: #666;")
        controls_layout.addWidget(self.scale_label)
        
        controls_layout.addStretch()
        left_layout.addLayout(controls_layout)
        
        splitter.addWidget(left_panel)
        
        # Right panel - Controls
        self.control_panel = CameraControlWidget()
        self.control_panel.settings_changed.connect(self.update_image_settings)
        self.control_panel.setMaximumWidth(400)
        splitter.addWidget(self.control_panel)
        
        # Set splitter sizes (camera view gets more space)
        splitter.setSizes([1000, 400])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Apply Apple-like light theme for clarity and elegance
        self.apply_theme()
    
    def apply_theme(self):
        """Apply Apple-like light theme for clarity and elegance"""
        self.setStyleSheet("""
            * {
                font-family: Arial, Helvetica, sans-serif;
            }
            QMainWindow {
                background: #f8f8fa;
                color: #222;
            }
            QGroupBox {
                font-weight: 600;
                border: 1.5px solid #e0e0e0;
                border-radius: 14px;
                margin-top: 18px;
                padding: 12px 18px 18px 18px;
                background: #fff;
                font-size: 18px;
                letter-spacing: 0.5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 18px;
                padding: 0 8px 0 8px;
                font-size: 19px;
                color: #222;
                font-weight: 700;
            }
            QPushButton {
                background-color: #007aff;
                color: #fff;
                border: none;
                padding: 12px 0;
                border-radius: 10px;
                min-height: 36px;
                font-size: 17px;
                font-weight: 600;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #005ecb;
            }
            QPushButton:pressed {
                background-color: #003e8a;
            }
            QSlider::groove:horizontal {
                border: 1px solid #e0e0e0;
                height: 10px;
                background: #e9e9ef;
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #007aff;
                border: 1.5px solid #e0e0e0;
                width: 26px;
                border-radius: 13px;
                margin: -8px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #005ecb;
            }
            QComboBox {
                background-color: #fff;
                color: #222;
                border: 1.5px solid #e0e0e0;
                padding: 6px;
                border-radius: 8px;
                font-size: 16px;
            }
            QLabel {
                color: #222;
                font-size: 16px;
                font-weight: 500;
            }
            QStatusBar {
                background-color: #f0f0f3;
                color: #222;
                border-top: 1px solid #e0e0e0;
                font-size: 15px;
            }
            QCheckBox {
                font-size: 16px;
                font-weight: 600;
                padding: 8px 0;
            }
        """)
    
    def init_camera(self):
        """Initialize camera system"""
        self.refresh_cameras()
        if self.camera_combo.count() > 0:
            self.change_camera(0)
    
    def init_timer(self):
        """Initialize update timer"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)  # ~30 FPS
    
    def refresh_cameras(self):
        """Refresh available cameras"""
        self.camera_combo.clear()
        cameras = self.camera_backend.enumerate_cameras()
        for i, camera in enumerate(cameras):
            self.camera_combo.addItem(f"Camera {i}: {camera.get('name', 'Unknown')}")
    
    def change_camera(self, index):
        """Change active camera"""
        if hasattr(self, 'camera') and self.camera:
            self.camera.release()
        
        try:
            self.current_camera_index = index
            self.camera = self.camera_backend.create_capture(index)
            if self.camera:
                # Get camera profile if available
                profile = self.camera_backend.get_camera_profile(index)
                if profile:
                    # Set optimal resolution based on profile
                    optimal_res = profile.get_optimal_resolution(1366)  # Target width for RK3568
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, optimal_res[0])
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, optimal_res[1])
                    
                    # Update status with camera model info
                    self.status_bar.showMessage(f"{profile.name} connected")
                    
                    # Update camera info label with detailed specifications
                    sensor_info = profile.sensor
                    max_res = profile.get_max_resolution()
                    optimal_res = profile.get_optimal_resolution(1366)
                    
                    # Build detailed camera info string
                    camera_details = [
                        f"Camera: {profile.model}",
                        f"Sensor: {sensor_info.get('model', 'Unknown')} {sensor_info.get('size', '')}",
                        f"FOV: {sensor_info.get('fov', 'Unknown')}",
                        f"Focus: {sensor_info.get('focus', 'Unknown')}",
                        f"IR Filter: {'Yes' if sensor_info.get('ir_filter', False) else 'No'}",
                        f"Max: {max_res[0]}×{max_res[1]}",
                        f"Current: {optimal_res[0]}×{optimal_res[1]}"
                    ]
                    
                    self.camera_info_label.setText(" | ".join(camera_details))
                    
                    # Apply profile's white balance offset to current settings
                    if hasattr(self, 'control_panel') and profile.image_processing:
                        wb_offset = profile.image_processing.get('white_balance_offset', 0.0)
                        self.control_panel.set_white_balance(wb_offset)
                else:
                    # Default settings for unknown camera
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    self.camera.set(cv2.CAP_PROP_FPS, 30)
                    self.status_bar.showMessage(f"Camera {index} connected")
                    self.camera_info_label.setText(f"Camera: Generic USB Camera | Current: 1280×720")
            else:
                self.status_bar.showMessage("Failed to connect camera")
                self.camera_info_label.setText("Camera: Not connected")
        except Exception as e:
            self.status_bar.showMessage(f"Camera error: {str(e)}")
            self.camera = None
            self.camera_info_label.setText("Camera: Error connecting")
    
    def update_image_settings(self, settings):
        """Update image processing settings"""
        self.current_settings = self.control_panel.get_settings()
        self.update_frame()
    
    def update_frame(self):
        """Update camera frame"""
        if not self.camera:
            return
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return
        # Apply camera profile-specific processing first
        frame = self.camera_backend.apply_profile_image_processing(frame, self.current_camera_index)
        # Always fetch the latest settings from the control panel
        settings = self.control_panel.get_settings()
        if DEBUG:
            print(f"[DEBUG] update_frame using settings: {settings}")
        frame = self.image_processor.process_frame(frame, settings)
        self.current_frame = frame
        # Convert to Qt format and display
        self.display_frame(frame)
        # Update scale reading
        self.update_scale_reading()
    
    def display_frame(self, frame):
        """Display frame with 6-bit color optimization for RK3568 displays"""
        if frame is None:
            return
        
        # Resize frame to fit display while maintaining aspect ratio
        h, w = frame.shape[:2]
        display_w, display_h = 800, 600
        
        # Calculate scaling to fit
        scale = min(display_w / w, display_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        frame_resized = cv2.resize(frame, (new_w, new_h))
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        
        # 6-bit color optimization for RK3568 displays (64 levels per channel)
        # This reduces color depth to match the 6-bit display capabilities
        frame_6bit = (frame_rgb >> 2) << 2  # Simple bit shift for 6-bit quantization
        
        # Convert to QImage
        h, w, ch = frame_6bit.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame_6bit.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Convert to QPixmap and display
        pixmap = QPixmap.fromImage(qt_image)
        self.camera_label.setPixmap(pixmap)
    
    def update_scale_reading(self):
        """Update scale reading display"""
        if not SCALE_AVAILABLE:
            self.scale_label.setText("Scale: Not available (pyserial not installed)")
            self.scale_label.setStyleSheet("font-weight: bold; color: #f44336;")
            return
            
        try:
            reading = self.scale_interface.get_reading()
            if reading:
                self.scale_label.setText(f"Scale: {reading.weight:.2f} {reading.unit}")
                self.scale_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
            else:
                self.scale_label.setText("Scale: No reading")
                self.scale_label.setStyleSheet("font-weight: bold; color: #666;")
        except:
            self.scale_label.setText("Scale: Not connected")
            self.scale_label.setStyleSheet("font-weight: bold; color: #f44336;")
    
    def capture_image(self):
        """Capture and save image at full resolution"""
        if self.current_frame is None:
            QMessageBox.warning(self, "Error", "No image to capture")
            return
        
        # Create data directory if it doesn't exist
        data_dir = Path("data/captures")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = data_dir / f"capture_{timestamp}.jpg"
        
        # Get scale reading
        scale_reading = None
        try:
            scale_reading = self.scale_interface.get_reading()
        except:
            pass
        
        # Process full resolution frame with camera profile processing
        processed_frame = self.camera_backend.apply_profile_image_processing(
            self.current_frame, self.current_camera_index)
        processed_frame = self.image_processor.process_frame(processed_frame, self.current_settings)
        
        # Save image
        cv2.imwrite(str(filename), processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        # Save metadata
        metadata = {
            "timestamp": timestamp,
            "filename": filename.name,
            "settings": self.current_settings,
            "scale_reading": {
                "weight": scale_reading.weight if scale_reading else None,
                "unit": scale_reading.unit if scale_reading else None
            } if scale_reading else None
        }
        
        metadata_file = data_dir / f"capture_{timestamp}.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.status_bar.showMessage(f"Image saved: {filename.name}")
        QMessageBox.information(self, "Success", f"Image captured and saved as {filename.name}")
    
    def load_settings(self):
        """Load settings from config file"""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                # Load camera controls if they exist
                if 'camera_controls' in config:
                    self.control_panel.load_settings(config['camera_controls'])
                    # Initialize current_settings with loaded values
                    self.current_settings = self.control_panel.get_settings()
        except Exception as e:
            print(f"Error loading settings: {e}")
            # Initialize with default settings
            self.current_settings = self.control_panel.get_settings()
    
    def save_settings(self):
        """Save current settings to config file"""
        try:
            config = {}
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
            
            config['camera_controls'] = self.control_panel.get_settings()
            
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
        except:
            pass
    
    def closeEvent(self, event):
        """Handle application close"""
        if hasattr(self, 'camera') and self.camera:
            self.camera.release()
        self.save_settings()
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("AI-Scale Data Collector")
    app.setApplicationVersion("2.4.0")
    
    # Create and show main window
    window = AIScaleMainWindow()
    window.show()
    
    # Center window on screen
    screen = app.primaryScreen().geometry()
    window.move((screen.width() - window.width()) // 2,
                (screen.height() - window.height()) // 2)
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())