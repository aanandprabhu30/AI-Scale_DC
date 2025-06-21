#!/usr/bin/env python3
"""
AI-Scale Data Collector
Optimized for M2 MacBook Air with Arducam IMX219 USB Camera
Clean, focused tool for capturing produce images for AI training
"""

import sys
import os
import cv2
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QGroupBox, QGridLayout,
    QLineEdit, QMessageBox, QFileDialog, QSpinBox, QCheckBox,
    QSlider, QListWidget, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QIcon, QPalette, QKeySequence, QShortcut

# Constants for IMX219 sensor
IMX219_RESOLUTIONS = {
    "3280x2464": (3280, 2464),  # Full 8MP
    "1920x1080": (1920, 1080),  # Full HD
    "1640x1232": (1640, 1232),  # 2MP
    "1280x720": (1280, 720),    # HD
    "640x480": (640, 480)       # VGA for preview
}

class CameraThread(QThread):
    """Dedicated thread for camera operations"""
    frameReady = pyqtSignal(np.ndarray)
    
    def __init__(self):
        super().__init__()
        self.camera = None
        self.running = False
        self.capture_flag = False
        self.current_frame = None
        
    def initialize_camera(self, index=0):
        """Initialize camera with macOS-optimized settings for Arducam IMX219"""
        # Try AVFoundation backend first (best for macOS)
        self.camera = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
        
        if not self.camera.isOpened():
            # Fallback to default
            self.camera = cv2.VideoCapture(index)
            
        if self.camera.isOpened():
            # Configure for IMX219 - optimized for M2 Mac
            self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
            self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)   # Enable autofocus
            self.camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Auto exposure
            return True
        return False
        
    def run(self):
        """Camera capture loop"""
        self.running = True
        while self.running:
            if self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                if ret:
                    self.current_frame = frame
                    self.frameReady.emit(frame)
            time.sleep(0.033)  # ~30 FPS
            
    def capture_high_res(self):
        """Capture a high-resolution image using IMX219 full 8MP capability"""
        if self.camera and self.camera.isOpened():
            try:
                # Switch to high res for capture
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 3280)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 2464)
                
                # Clear buffer to get fresh frame
                for _ in range(3):
                    self.camera.read()
                    
                # Capture with timeout
                start_time = time.time()
                while time.time() - start_time < 2.0:  # 2 second timeout
                    ret, frame = self.camera.read()
                    if ret and frame is not None and frame.size > 0:
                        # Switch back to preview resolution
                        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                        return frame
                    time.sleep(0.1)
                
                # Fallback to current resolution if high-res fails
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                ret, frame = self.camera.read()
                if ret:
                    return frame
                    
            except Exception as e:
                print(f"High-res capture error: {e}")
                # Reset to preview resolution
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                
        return None
        
    def stop(self):
        """Stop camera thread"""
        self.running = False
        self.wait()
        if self.camera:
            self.camera.release()

class ModernButton(QPushButton):
    """Styled button with hover effects"""
    def __init__(self, text, color="#2196F3"):
        super().__init__(text)
        self.default_color = color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(color, 0.3)};
            }}
        """)
        
    def darken_color(self, color, factor=0.1):
        """Darken a hex color"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(int(c * (1 - factor)) for c in rgb)
        return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"

class ProduceSelector(QWidget):
    """Quick selection grid for common produce"""
    itemSelected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(8)
        
        # Common produce items with emojis
        items = [
            ("🍎 Apple", "apple"),
            ("🍌 Banana", "banana"),
            ("🥕 Carrot", "carrot"),
            ("🍊 Orange", "orange"),
            ("🍅 Tomato", "tomato"),
            ("🥔 Potato", "potato"),
            ("🥒 Cucumber", "cucumber"),
            ("🍋 Lemon", "lemon"),
            ("🧅 Onion", "onion")
        ]
        
        for i, (display, value) in enumerate(items):
            btn = QPushButton(display)
            btn.setMinimumHeight(50)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #e3f2fd;
                    border-color: #2196F3;
                }
            """)
            btn.clicked.connect(lambda checked, v=value: self.itemSelected.emit(v))
            layout.addWidget(btn, i // 3, i % 3)

class AIScaleDataCollector(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.camera_thread = CameraThread()
        self.current_class = ""
        self.dataset_path = Path("data/raw")
        self.session_count = 0
        self.class_counts = {}
        
        self.init_ui()
        self.setup_camera()
        self.load_classes()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("AI-Scale Data Collector")
        self.setMinimumSize(1200, 800)
        
        # Set modern style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #fafafa;
            }
        """)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Create panels
        camera_panel = self.create_camera_panel()
        control_panel = self.create_control_panel()
        
        splitter.addWidget(camera_panel)
        splitter.addWidget(control_panel)
        splitter.setSizes([800, 400])  # Initial sizes
        
        # Create status bar
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #f5f5f5;
                border-top: 1px solid #e0e0e0;
            }
        """)
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
    def setup_shortcuts(self):
        """Setup keyboard shortcuts for quick operation"""
        
        # Space bar to capture
        capture_shortcut = QShortcut(QKeySequence("Space"), self)
        capture_shortcut.activated.connect(self.capture_image)
        
        # Ctrl+N for new class
        new_class_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_class_shortcut.activated.connect(lambda: self.new_class_input.setFocus())
        
        # Ctrl+O to change dataset path
        path_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        path_shortcut.activated.connect(self.change_dataset_path)
        
        # Ctrl+Q to quit
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.close)
        
    def create_camera_panel(self):
        """Create camera view panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        
        # Camera display
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(800, 600)
        self.camera_label.setStyleSheet("""
            QLabel {
                background-color: #000;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
            }
        """)
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setScaledContents(True)
        layout.addWidget(self.camera_label)
        
        # Camera info overlay
        self.info_label = QLabel("Initializing camera...")
        self.info_label.setStyleSheet("""
            QLabel {
                background-color: rgba(33, 150, 243, 0.9);
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 12px;
            }
        """)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        
        return panel
        
    def create_control_panel(self):
        """Create control panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("🍎 AI-Scale Collector")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2196F3;
                padding: 8px;
            }
        """)
        layout.addWidget(title)
        
        # Class selection
        class_group = QGroupBox("Select Produce Type")
        class_layout = QVBoxLayout()
        
        # Manual selection
        self.class_combo = QComboBox()
        self.class_combo.setPlaceholderText("Choose produce type...")
        self.class_combo.currentTextChanged.connect(self.on_class_changed)
        class_layout.addWidget(self.class_combo)
        
        # Add new class
        add_layout = QHBoxLayout()
        self.new_class_input = QLineEdit()
        self.new_class_input.setPlaceholderText("Add new type (e.g., 'fuji_apple')")
        add_button = ModernButton("Add", "#4CAF50")
        add_button.clicked.connect(self.add_class)
        add_layout.addWidget(self.new_class_input)
        add_layout.addWidget(add_button)
        class_layout.addLayout(add_layout)
        
        # Quick select grid
        self.produce_selector = ProduceSelector()
        self.produce_selector.itemSelected.connect(self.on_quick_select)
        class_layout.addWidget(self.produce_selector)
        
        class_group.setLayout(class_layout)
        layout.addWidget(class_group)
        
        # Capture controls
        capture_group = QGroupBox("Capture Controls")
        capture_layout = QVBoxLayout()
        
        # Main capture button
        self.capture_button = ModernButton("📸 CAPTURE IMAGE", "#FF5722")
        self.capture_button.setMinimumHeight(60)
        self.capture_button.clicked.connect(self.capture_image)
        capture_layout.addWidget(self.capture_button)
        
        # Options
        self.high_res_check = QCheckBox("High Resolution (8MP)")
        self.high_res_check.setChecked(True)
        capture_layout.addWidget(self.high_res_check)
        
        self.auto_increment_check = QCheckBox("Auto-increment filename")
        self.auto_increment_check.setChecked(True)
        capture_layout.addWidget(self.auto_increment_check)
        
        capture_group.setLayout(capture_layout)
        layout.addWidget(capture_group)
        
        # Statistics
        stats_group = QGroupBox("Session Statistics")
        stats_layout = QVBoxLayout()
        
        self.stats_label = QLabel("No images captured yet")
        self.stats_label.setStyleSheet("padding: 8px;")
        stats_layout.addWidget(self.stats_label)
        
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(120)
        stats_layout.addWidget(self.recent_list)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Dataset path
        path_layout = QHBoxLayout()
        path_label = QLabel("Dataset:")
        self.path_label = QLabel(str(self.dataset_path))
        self.path_label.setStyleSheet("color: #666;")
        change_path_btn = ModernButton("Change", "#9E9E9E")
        change_path_btn.clicked.connect(self.change_dataset_path)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_label, 1)
        path_layout.addWidget(change_path_btn)
        layout.addLayout(path_layout)
        
        layout.addStretch()
        return panel
        
    def setup_camera(self):
        """Initialize camera"""
        if self.camera_thread.initialize_camera():
            self.camera_thread.frameReady.connect(self.update_frame)
            self.camera_thread.start()
            self.info_label.setText("IMX219 Camera Ready - 1920x1080 @ 30fps")
            self.info_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(76, 175, 80, 0.9);
                    color: white;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 12px;
                }
            """)
        else:
            self.info_label.setText("Camera not found - Please check connection")
            self.info_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(244, 67, 54, 0.9);
                    color: white;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 12px;
                }
            """)
            QMessageBox.warning(self, "Camera Error", 
                              "Could not initialize camera.\n"
                              "Please check that your Arducam is connected.")
            
    def update_frame(self, frame):
        """Update camera display"""
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line,
                        QImage.Format.Format_BGR888).rgbSwapped()
        
        # Scale to fit label while maintaining aspect ratio
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(self.camera_label.size(),
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        self.camera_label.setPixmap(scaled)
        
    def load_classes(self):
        """Load produce classes"""
        # Create dataset directory
        self.dataset_path.mkdir(exist_ok=True)
        
        # Load existing classes
        classes = []
        for item in self.dataset_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                classes.append(item.name)
                
        # Update combo box
        self.class_combo.clear()
        self.class_combo.addItems(sorted(classes))
        
        # Update counts
        self.update_statistics()
        
    def on_class_changed(self, class_name):
        """Handle class selection change"""
        self.current_class = class_name
        if class_name:
            count = len(list((self.dataset_path / class_name).glob("*.jpg")))
            self.status_bar.showMessage(f"Selected: {class_name} ({count} images)")
            
    def on_quick_select(self, item_name):
        """Handle quick selection"""
        # Check if class exists
        if item_name not in [self.class_combo.itemText(i) 
                           for i in range(self.class_combo.count())]:
            # Add it
            self.new_class_input.setText(item_name)
            self.add_class()
        else:
            # Select it
            index = self.class_combo.findText(item_name)
            if index >= 0:
                self.class_combo.setCurrentIndex(index)
                
    def add_class(self):
        """Add new produce class"""
        class_name = self.new_class_input.text().strip().lower()
        if not class_name:
            return
            
        # Sanitize name
        class_name = class_name.replace(' ', '_')
        class_name = ''.join(c for c in class_name if c.isalnum() or c == '_')
        
        # Create directory
        class_path = self.dataset_path / class_name
        if not class_path.exists():
            class_path.mkdir()
            self.load_classes()
            
            # Select the new class
            index = self.class_combo.findText(class_name)
            if index >= 0:
                self.class_combo.setCurrentIndex(index)
                
        self.new_class_input.clear()
        
    def capture_image(self):
        """Capture and save image"""
        if not self.current_class:
            QMessageBox.warning(self, "No Class Selected",
                              "Please select a produce type first.")
            return
            
        # Get frame
        if self.high_res_check.isChecked():
            frame = self.camera_thread.capture_high_res()
        else:
            frame = self.camera_thread.current_frame
            
        if frame is None:
            QMessageBox.error(self, "Capture Error",
                            "Failed to capture image. Check camera connection.")
            return
            
        # Generate filename
        class_path = self.dataset_path / self.current_class
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        if self.auto_increment_check.isChecked():
            count = len(list(class_path.glob("*.jpg"))) + 1
            filename = f"{self.current_class}_{count:04d}_{timestamp}.jpg"
        else:
            filename = f"{self.current_class}_{timestamp}.jpg"
            
        filepath = class_path / filename
        
        # Save image with high quality
        success = cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        if not success:
            QMessageBox.error(self, "Save Error",
                            f"Failed to save image to {filepath}")
            return
        
        # Update UI
        self.session_count += 1
        self.class_counts[self.current_class] = self.class_counts.get(self.current_class, 0) + 1
        
        # Add to recent list
        item = QListWidgetItem(f"✓ {filename}")
        self.recent_list.insertItem(0, item)
        if self.recent_list.count() > 5:
            self.recent_list.takeItem(5)
            
        # Update statistics
        self.update_statistics()
        
        # Flash effect
        self.flash_capture()
        
        # Status message
        self.status_bar.showMessage(f"Captured: {filename}", 3000)
        
    def flash_capture(self):
        """Visual feedback for capture"""
        original_style = self.capture_button.styleSheet()
        self.capture_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
                font-weight: 600;
            }
        """)
        QTimer.singleShot(200, lambda: self.capture_button.setStyleSheet(original_style))
        
    def update_statistics(self):
        """Update statistics display"""
        total = 0
        details = []
        
        for class_dir in self.dataset_path.iterdir():
            if class_dir.is_dir() and not class_dir.name.startswith('.'):
                count = len(list(class_dir.glob("*.jpg")))
                total += count
                if count > 0:
                    details.append(f"{class_dir.name}: {count}")
                    
        stats_text = f"Total: {total} images\n"
        stats_text += f"Session: {self.session_count} captured\n"
        stats_text += f"Classes: {len(details)}"
        
        self.stats_label.setText(stats_text)
        
    def change_dataset_path(self):
        """Change dataset save location"""
        folder = QFileDialog.getExistingDirectory(self, "Select Dataset Folder")
        if folder:
            self.dataset_path = Path(folder)
            self.path_label.setText(str(self.dataset_path))
            self.load_classes()
            
    def closeEvent(self, event):
        """Clean up on close"""
        self.camera_thread.stop()
        event.accept()

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("AI-Scale Data Collector")
    
    # Set application style
    app.setStyle("Fusion")
    
    window = AIScaleDataCollector()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
