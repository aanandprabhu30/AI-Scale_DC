from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QScreen
import logging
from typing import Tuple, Optional
from platform_config import platform_config

logger = logging.getLogger(__name__)

class DisplayManager:
    """Optimized display management for different screen sizes and platforms"""
    
    def __init__(self):
        self.app = QApplication.instance()
        self.primary_screen = None
        self.screen_geometry = None
        self.dpi_scale = 1.0
        self.is_high_dpi = False
        
        if self.app:
            self._initialize_display_info()
    
    def _initialize_display_info(self):
        """Initialize display information"""
        try:
            self.primary_screen = self.app.primaryScreen()
            if self.primary_screen:
                self.screen_geometry = self.primary_screen.geometry()
                self.dpi_scale = self.primary_screen.devicePixelRatio()
                self.is_high_dpi = self.dpi_scale > 1.0
                
                logger.info(f"Display initialized: {self.screen_geometry.width()}x{self.screen_geometry.height()}, "
                           f"DPI scale: {self.dpi_scale}")
        except Exception as e:
            logger.error(f"Failed to initialize display info: {e}")
    
    def get_optimal_window_size(self, min_width: int = 800, min_height: int = 600) -> Tuple[int, int]:
        """Get optimal window size for the current display"""
        if not self.screen_geometry:
            return (min_width, min_height)
        
        screen_width = self.screen_geometry.width()
        screen_height = self.screen_geometry.height()
        
        # Platform-specific optimizations
        if platform_config.is_rk3568:
            # For 1366x768 display, use most of the screen
            if screen_width == 1366 and screen_height == 768:
                return (1340, 720)  # Leave small margins
            
        # For other platforms, use 80% of screen size
        optimal_width = min(int(screen_width * 0.8), max(min_width, screen_width - 100))
        optimal_height = min(int(screen_height * 0.8), max(min_height, screen_height - 100))
        
        return (optimal_width, optimal_height)
    
    def get_optimal_camera_view_size(self, available_width: int, available_height: int) -> Tuple[int, int]:
        """Get optimal camera view size within available space"""
        # Calculate based on 16:9 aspect ratio (most common camera ratio)
        aspect_ratio = 16 / 9
        
        # Try width-limited first
        width = available_width
        height = int(width / aspect_ratio)
        
        # If height exceeds available space, use height-limited
        if height > available_height:
            height = available_height
            width = int(height * aspect_ratio)
        
        # Apply platform-specific constraints
        if platform_config.is_rk3568:
            # Limit to reasonable sizes for embedded display
            max_width = 800
            max_height = 450
            
            if width > max_width:
                width = max_width
                height = int(width / aspect_ratio)
            
            if height > max_height:
                height = max_height
                width = int(height * aspect_ratio)
        
        return (max(320, width), max(240, height))  # Minimum reasonable sizes
    
    def setup_window_for_platform(self, window: QWidget) -> bool:
        """Setup window with platform-specific optimizations"""
        try:
            if platform_config.is_rk3568:
                self._setup_rk3568_window(window)
            elif platform_config.platform == 'darwin':
                self._setup_macos_window(window)
            else:
                self._setup_generic_window(window)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup window: {e}")
            return False
    
    def _setup_rk3568_window(self, window: QWidget):
        """Setup window for RK3568 (1366x768 display)"""
        # Enable fullscreen by default on embedded systems
        if platform_config.get('display.fullscreen_default', True):
            window.showFullScreen()
            logger.info("Window set to fullscreen for RK3568")
        else:
            # Maximize window to use full screen space
            window.showMaximized()
        
        # Disable window decorations for embedded use
        if platform_config.get('display.hide_decorations', False):
            window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # Optimize for touch if available
        window.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        
        # Set minimum size to fit 1366x768
        window.setMinimumSize(1000, 600)
        
    def _setup_macos_window(self, window: QWidget):
        """Setup window for macOS"""
        # Native macOS appearance
        window.setAttribute(Qt.WidgetAttribute.WA_MacBrushedMetal, False)
        
        # Handle high DPI displays
        if self.is_high_dpi:
            window.setAttribute(Qt.WidgetAttribute.WA_HighDpiScaling, True)
        
        # Optimal size for macOS
        optimal_size = self.get_optimal_window_size(1200, 800)
        window.resize(*optimal_size)
        
        # Center on screen
        self._center_window(window)
        
    def _setup_generic_window(self, window: QWidget):
        """Setup window for generic platforms"""
        # Standard window setup
        optimal_size = self.get_optimal_window_size(1000, 700)
        window.resize(*optimal_size)
        
        # Center on screen
        self._center_window(window)
        
        # Enable high DPI support
        if self.is_high_dpi:
            window.setAttribute(Qt.WidgetAttribute.WA_HighDpiScaling, True)
    
    def _center_window(self, window: QWidget):
        """Center window on screen"""
        if not self.screen_geometry:
            return
        
        window_geometry = window.geometry()
        center_point = self.screen_geometry.center()
        
        window_geometry.moveCenter(center_point)
        window.move(window_geometry.topLeft())
    
    def get_font_scaling(self) -> float:
        """Get appropriate font scaling for the platform"""
        if platform_config.is_rk3568:
            # Larger fonts for 1366x768 display readability
            return 1.1
        elif self.is_high_dpi:
            # Adjust for high DPI displays
            return 1.0 / self.dpi_scale
        else:
            return 1.0
    
    def get_ui_scaling(self) -> float:
        """Get UI element scaling factor"""
        if platform_config.is_rk3568:
            # Slightly larger UI elements for touch interaction
            return 1.2
        elif self.is_high_dpi:
            return 1.0
        else:
            return 1.0
    
    def apply_platform_stylesheet(self, base_stylesheet: str) -> str:
        """Apply platform-specific stylesheet modifications"""
        stylesheet = base_stylesheet
        
        font_scale = self.get_font_scaling()
        ui_scale = self.get_ui_scaling()
        
        if platform_config.is_rk3568:
            # RK3568 specific styles
            rk3568_additions = f"""
            /* RK3568 Optimizations */
            QWidget {{
                font-size: {int(14 * font_scale)}px;
            }}
            
            QPushButton {{
                min-height: {int(40 * ui_scale)}px;
                padding: {int(12 * ui_scale)}px {int(24 * ui_scale)}px;
                font-size: {int(15 * font_scale)}px;
            }}
            
            QComboBox {{
                min-height: {int(35 * ui_scale)}px;
                padding: {int(8 * ui_scale)}px {int(12 * ui_scale)}px;
                font-size: {int(14 * font_scale)}px;
            }}
            
            QLabel {{
                font-size: {int(14 * font_scale)}px;
            }}
            
            /* Larger touch targets */
            QSlider::handle {{
                width: {int(20 * ui_scale)}px;
                height: {int(20 * ui_scale)}px;
            }}
            """
            stylesheet += rk3568_additions
            
        elif platform_config.platform == 'darwin' and self.is_high_dpi:
            # macOS high DPI adjustments
            macos_additions = f"""
            /* macOS High DPI */
            QWidget {{
                font-size: {int(13 * font_scale)}px;
            }}
            """
            stylesheet += macos_additions
        
        return stylesheet
    
    def optimize_for_performance(self, window: QWidget):
        """Apply performance optimizations for the display"""
        if platform_config.is_rk3568:
            # Disable transparency and effects for better performance
            window.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
            window.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            
            # Reduce update frequency if possible
            window.setAttribute(Qt.WidgetAttribute.WA_UpdatesDisabled, False)
        
        # Enable hardware acceleration if available
        window.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
    
    def get_display_info(self) -> dict:
        """Get comprehensive display information"""
        info = {
            'screen_count': len(self.app.screens()) if self.app else 0,
            'primary_screen_size': (
                self.screen_geometry.width(), 
                self.screen_geometry.height()
            ) if self.screen_geometry else (0, 0),
            'dpi_scale': self.dpi_scale,
            'is_high_dpi': self.is_high_dpi,
            'font_scaling': self.get_font_scaling(),
            'ui_scaling': self.get_ui_scaling(),
            'platform': platform_config.platform,
            'is_rk3568': platform_config.is_rk3568
        }
        
        if self.primary_screen:
            info.update({
                'physical_dpi': self.primary_screen.physicalDotsPerInch(),
                'logical_dpi': self.primary_screen.logicalDotsPerInch(),
                'refresh_rate': self.primary_screen.refreshRate(),
                'orientation': self.primary_screen.orientation().name if hasattr(self.primary_screen.orientation(), 'name') else 'Unknown'
            })
        
        return info
    
    def force_window_on_top(self, window: QWidget):
        """Force window to stay on top (useful for kiosk mode)"""
        if platform_config.get('display.always_on_top', False):
            window.setWindowFlags(window.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    
    def hide_cursor_if_needed(self, window: QWidget):
        """Hide cursor for kiosk/embedded applications"""
        if platform_config.get('display.hide_cursor', False):
            window.setCursor(Qt.CursorShape.BlankCursor)

# Global instance
display_manager = DisplayManager()