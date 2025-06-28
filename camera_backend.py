import cv2
import numpy as np
import platform
import subprocess
import re
import json
import os
from typing import List, Dict, Optional, Tuple, Any
import logging
from pathlib import Path

# Suppress OpenCV warnings during camera enumeration
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'

logger = logging.getLogger(__name__)

class CameraProfile:
    """Camera profile with optimal settings and specifications"""
    
    def __init__(self, profile_data: Dict[str, Any]):
        self.name = profile_data.get('name', 'Unknown Camera')
        self.model = profile_data.get('model', 'Unknown')
        self.vendor_id = profile_data.get('vendor_id')
        self.product_id = profile_data.get('product_id')
        self.sensor = profile_data.get('sensor', {})
        self.supported_resolutions = profile_data.get('supported_resolutions', [])
        self.optimal_settings = profile_data.get('optimal_settings', {})
        self.image_processing = profile_data.get('image_processing', {})
        self.features = profile_data.get('features', [])
    
    def get_optimal_resolution(self, target_width: int = 1920) -> Tuple[int, int]:
        """Get optimal resolution based on target width"""
        if not self.supported_resolutions:
            return (1280, 720)
        
        # Find closest resolution to target width
        best_res = min(self.supported_resolutions,
                      key=lambda r: abs(r['width'] - target_width))
        return (best_res['width'], best_res['height'])
    
    def get_max_resolution(self) -> Tuple[int, int]:
        """Get maximum supported resolution"""
        max_res = self.sensor.get('max_resolution', {})
        return (max_res.get('width', 1920), max_res.get('height', 1080))

class CameraBackend:
    """Hardware abstraction layer for camera access across different platforms"""
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.is_arm = platform.machine().lower() in ['aarch64', 'arm64', 'armv7l', 'armv8']
        self.backend = self._get_backend()
        self.profiles = self._load_camera_profiles()
        self.detected_cameras = {}
        
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
    
    def _load_camera_profiles(self) -> Dict[str, CameraProfile]:
        """Load camera profiles from JSON file"""
        profiles = {}
        profile_path = Path(__file__).parent / 'camera_profiles.json'
        
        try:
            if profile_path.exists():
                with open(profile_path, 'r') as f:
                    data = json.load(f)
                    for key, profile_data in data.get('profiles', {}).items():
                        profiles[key] = CameraProfile(profile_data)
            else:
                logger.warning(f"Camera profiles file not found: {profile_path}")
        except Exception as e:
            logger.error(f"Error loading camera profiles: {e}")
        
        return profiles
    
    def _detect_usb_camera(self, device_path: str = None) -> Optional[str]:
        """Detect USB camera model by VID/PID"""
        profile_key = None
        
        try:
            if self.platform == 'linux':
                # Use lsusb to get USB device info
                result = subprocess.run(['lsusb', '-v'], capture_output=True, text=True)
                if result.returncode == 0:
                    # Parse for known VID/PID combinations using patterns from profiles
                    usb_output = result.stdout.lower()
                    
                    # Check for Arducam B0196 patterns
                    if any(pattern in usb_output for pattern in ['0bda:5830', 'idvendor.*0x0bda.*idproduct.*0x5830']):
                        profile_key = 'arducam_b0196'
                        logger.info("Detected Arducam B0196 camera via USB VID/PID")
                    # Check for JSK-S8130-V3.0 patterns
                    elif any(pattern in usb_output for pattern in ['1bcf:2c99', 'idvendor.*0x1bcf.*idproduct.*0x2c99']):
                        profile_key = 'jsk_s8130_v3'
                        logger.info("Detected JSK-S8130-V3.0 camera via USB VID/PID")
            
            elif self.platform == 'darwin':
                # Use system_profiler on macOS
                result = subprocess.run(['system_profiler', 'SPUSBDataType'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    # Parse for known VID/PID patterns
                    profiler_output = result.stdout.lower()
                    if '0x0bda' in profiler_output and '0x5830' in profiler_output:
                        profile_key = 'arducam_b0196'
                        logger.info("Detected Arducam B0196 camera via system_profiler")
                    elif '0x1bcf' in profiler_output and '0x2c99' in profiler_output:
                        profile_key = 'jsk_s8130_v3'
                        logger.info("Detected JSK-S8130-V3.0 camera via system_profiler")
            
            elif self.platform == 'windows':
                # Use wmic on Windows
                result = subprocess.run(['wmic', 'path', 'Win32_USBHub', 'get', 
                                       'DeviceID,PNPDeviceID'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    # Parse for known VID/PID patterns
                    wmic_output = result.stdout.upper()
                    if 'VID_0BDA&PID_5830' in wmic_output:
                        profile_key = 'arducam_b0196'
                        logger.info("Detected Arducam B0196 camera via WMIC")
                    elif 'VID_1BCF&PID_2C99' in wmic_output:
                        profile_key = 'jsk_s8130_v3'
                        logger.info("Detected JSK-S8130-V3.0 camera via WMIC")
        
        except Exception as e:
            logger.debug(f"Error detecting USB camera: {e}")
        
        if profile_key:
            logger.info(f"Camera detection successful: {profile_key}")
        else:
            logger.debug("No specific camera model detected, using generic profile")
        
        return profile_key
    
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
                        
                        # Try to detect camera model
                        profile_key = self._detect_usb_camera(device)
                        camera_profile = self.profiles.get(profile_key, self.profiles.get('generic'))
                        
                        camera_info = {
                            'index': device_num,
                            'name': name,
                            'device': device,
                            'resolutions': resolutions,
                            'backend': 'V4L2',
                            'profile_key': profile_key or 'generic',
                            'profile': camera_profile
                        }
                        
                        if camera_profile and profile_key:
                            camera_info['name'] = camera_profile.name
                            camera_info['model'] = camera_profile.model
                            self.detected_cameras[device_num] = camera_profile
                        
                        cameras.append(camera_info)
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
                    
                    # Try to detect camera model for non-Linux platforms
                    profile_key = self._detect_usb_camera()
                    camera_profile = self.profiles.get(profile_key, self.profiles.get('generic'))
                    
                    camera_info = {
                        'index': i,
                        'name': f"Camera {i}",
                        'device': f"index:{i}",
                        'resolutions': resolutions,
                        'current_resolution': (width, height),
                        'fps': fps,
                        'backend': self._backend_name(),
                        'profile_key': profile_key or 'generic',
                        'profile': camera_profile
                    }
                    
                    if camera_profile and profile_key:
                        camera_info['name'] = camera_profile.name
                        camera_info['model'] = camera_profile.model
                        self.detected_cameras[i] = camera_profile
                    
                    cameras.append(camera_info)
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
        
        # Apply camera profile settings if available
        camera_profile = self.detected_cameras.get(camera_index)
        if camera_profile:
            # Apply optimal settings from profile
            optimal = camera_profile.optimal_settings
            
            # Set format if specified
            if 'format' in optimal:
                if optimal['format'] == 'MJPG':
                    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
                elif optimal['format'] == 'YUYV':
                    fourcc = cv2.VideoWriter_fourcc(*'YUYV')
                    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            
            # Apply camera control settings
            if 'brightness' in optimal and optimal['brightness'] != 'auto':
                cap.set(cv2.CAP_PROP_BRIGHTNESS, optimal['brightness'])
            if 'contrast' in optimal and optimal['contrast'] != 'auto':
                cap.set(cv2.CAP_PROP_CONTRAST, optimal['contrast'])
            if 'saturation' in optimal and optimal['saturation'] != 'auto':
                cap.set(cv2.CAP_PROP_SATURATION, optimal['saturation'])
            if 'gain' in optimal and optimal['gain'] != 'auto':
                cap.set(cv2.CAP_PROP_GAIN, optimal['gain'])
            if 'exposure' in optimal and optimal['exposure'] != 'auto':
                cap.set(cv2.CAP_PROP_EXPOSURE, optimal['exposure'])
        
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
    
    def get_camera_profile(self, camera_index: int) -> Optional[CameraProfile]:
        """Get camera profile for a specific camera index"""
        return self.detected_cameras.get(camera_index)
    
    def apply_profile_image_processing(self, image: np.ndarray, camera_index: int) -> np.ndarray:
        """Apply camera-specific image processing based on profile"""
        profile = self.detected_cameras.get(camera_index)
        if not profile or not profile.image_processing:
            return image
        
        processing = profile.image_processing
        
        # Apply gamma correction if needed
        if processing.get('gamma_correction', 1.0) != 1.0:
            gamma = processing['gamma_correction']
            inv_gamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255 
                            for i in np.arange(0, 256)]).astype("uint8")
            image = cv2.LUT(image, table)
        
        # Apply denoise if needed
        if processing.get('denoise_strength', 0) > 0:
            strength = processing['denoise_strength']
            image = cv2.fastNlMeansDenoisingColored(image, None, 
                                                   h=10 * strength,
                                                   hColor=10 * strength,
                                                   templateWindowSize=7,
                                                   searchWindowSize=21)
        
        return image