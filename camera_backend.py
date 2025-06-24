import cv2
import platform
import subprocess
import re
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class CameraBackend:
    """Hardware abstraction layer for camera access across different platforms"""
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.is_arm = platform.machine().lower() in ['aarch64', 'arm64', 'armv7l', 'armv8']
        self.backend = self._get_backend()
        
    def _get_backend(self) -> int:
        """Determine the appropriate camera backend based on platform"""
        if self.platform == 'darwin':
            return cv2.CAP_AVFOUNDATION
        elif self.platform == 'linux':
            # Check if we're on Android
            try:
                with open('/proc/version', 'r') as f:
                    if 'android' in f.read().lower():
                        return cv2.CAP_ANDROID
            except:
                pass
            # Default to V4L2 for Linux
            return cv2.CAP_V4L2
        elif self.platform == 'windows':
            return cv2.CAP_DSHOW
        else:
            # Default fallback
            return cv2.CAP_ANY
    
    def enumerate_cameras(self) -> List[Dict[str, any]]:
        """Enumerate available cameras with platform-specific methods"""
        cameras = []
        
        if self.platform == 'linux':
            cameras = self._enumerate_linux_cameras()
        else:
            # Fallback to index-based enumeration
            cameras = self._enumerate_by_index()
            
        return cameras
    
    def _enumerate_linux_cameras(self) -> List[Dict[str, any]]:
        """Linux-specific camera enumeration using V4L2"""
        cameras = []
        
        try:
            # List all video devices
            import glob
            import os
            
            video_devices = glob.glob('/dev/video*')
            
            for device in sorted(video_devices):
                try:
                    # Get device info using v4l2-ctl if available
                    device_num = int(re.search(r'/dev/video(\d+)', device).group(1))
                    
                    # Try to get device name
                    name = f"Camera {device_num}"
                    try:
                        result = subprocess.run(
                            ['v4l2-ctl', '-d', device, '--info'],
                            capture_output=True, text=True, timeout=1
                        )
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if 'Card type' in line:
                                    name = line.split(':', 1)[1].strip()
                                    break
                    except:
                        pass
                    
                    # Test if camera is usable
                    cap = cv2.VideoCapture(device_num, self.backend)
                    if cap.isOpened():
                        # Get supported resolutions
                        resolutions = self._get_supported_resolutions(cap)
                        cap.release()
                        
                        cameras.append({
                            'index': device_num,
                            'name': name,
                            'device': device,
                            'resolutions': resolutions,
                            'backend': 'V4L2'
                        })
                except Exception as e:
                    logger.debug(f"Error checking device {device}: {e}")
                    
        except Exception as e:
            logger.error(f"Error enumerating Linux cameras: {e}")
            
        # If no cameras found, try index-based enumeration
        if not cameras:
            cameras = self._enumerate_by_index()
            
        return cameras
    
    def _enumerate_by_index(self) -> List[Dict[str, any]]:
        """Fallback camera enumeration by testing indices"""
        cameras = []
        
        for i in range(10):  # Check first 10 indices
            try:
                cap = cv2.VideoCapture(i, self.backend)
                if cap.isOpened():
                    # Get camera properties
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = int(cap.get(cv2.CAP_PROP_FPS))
                    
                    # Get supported resolutions
                    resolutions = self._get_supported_resolutions(cap)
                    
                    cap.release()
                    
                    cameras.append({
                        'index': i,
                        'name': f"Camera {i}",
                        'device': f"index:{i}",
                        'resolutions': resolutions,
                        'current_resolution': (width, height),
                        'fps': fps,
                        'backend': self._backend_name()
                    })
            except:
                pass
                
        return cameras
    
    def _get_supported_resolutions(self, cap) -> List[Tuple[int, int]]:
        """Get list of supported resolutions for a camera"""
        common_resolutions = [
            (3840, 2160),  # 4K
            (2560, 1440),  # 1440p
            (1920, 1080),  # 1080p
            (1366, 768),   # Match display resolution
            (1280, 720),   # 720p
            (1024, 768),   # XGA
            (800, 600),    # SVGA
            (640, 480),    # VGA
        ]
        
        supported = []
        original_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        original_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        for width, height in common_resolutions:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if actual_width == width and actual_height == height:
                supported.append((width, height))
        
        # Restore original resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, original_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, original_height)
        
        return supported
    
    def _backend_name(self) -> str:
        """Get human-readable backend name"""
        backend_names = {
            cv2.CAP_AVFOUNDATION: "AVFoundation",
            cv2.CAP_V4L2: "V4L2",
            cv2.CAP_DSHOW: "DirectShow",
            cv2.CAP_ANDROID: "Android",
            cv2.CAP_ANY: "Auto"
        }
        return backend_names.get(self.backend, "Unknown")
    
    def create_capture(self, camera_index: int, **kwargs) -> cv2.VideoCapture:
        """Create a VideoCapture object with platform-specific optimizations"""
        cap = cv2.VideoCapture(camera_index, self.backend)
        
        if self.platform == 'linux' and self.is_arm:
            # Optimizations for ARM Linux (RK3568)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer to minimize latency
            
            # Try to set MJPEG format for better performance
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            
            # Set reasonable FPS for embedded system
            cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Apply any additional settings
        for prop, value in kwargs.items():
            if hasattr(cv2, f'CAP_PROP_{prop.upper()}'):
                cap.set(getattr(cv2, f'CAP_PROP_{prop.upper()}'), value)
        
        return cap
    
    def get_optimal_resolution(self, cap, target_width: int = 1920) -> Tuple[int, int]:
        """Get optimal resolution based on camera capabilities and system resources"""
        resolutions = self._get_supported_resolutions(cap)
        
        if not resolutions:
            return (1280, 720)  # Default fallback
        
        # For embedded systems, prefer lower resolutions
        if self.is_arm:
            # Find resolution closest to 1366x768 (display size)
            target_pixels = 1366 * 768
            best_resolution = min(resolutions, 
                                 key=lambda r: abs(r[0] * r[1] - target_pixels))
        else:
            # Find resolution closest to target width
            best_resolution = min(resolutions, 
                                 key=lambda r: abs(r[0] - target_width))
        
        return best_resolution