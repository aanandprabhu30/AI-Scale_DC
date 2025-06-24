import cv2
import numpy as np
import logging
import subprocess
import os
from typing import Optional, Tuple, List
from platform_config import platform_config

logger = logging.getLogger(__name__)

class HardwareAccelerator:
    """Hardware acceleration interface for RK3568 and other platforms"""
    
    def __init__(self):
        self.platform = platform_config.platform
        self.is_rk3568 = platform_config.is_rk3568
        self.gpu_available = False
        self.npu_available = False
        self.vaapi_available = False
        
        self._detect_capabilities()
        
    def _detect_capabilities(self):
        """Detect available hardware acceleration capabilities"""
        if self.is_rk3568:
            self._detect_rk3568_capabilities()
        else:
            self._detect_generic_capabilities()
    
    def _detect_rk3568_capabilities(self):
        """Detect RK3568 specific capabilities"""
        logger.info("Detecting RK3568 hardware acceleration capabilities...")
        
        # Check for Mali GPU (OpenGL ES)
        try:
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=5)
            if 'Mali' in result.stdout:
                self.gpu_available = True
                logger.info("Mali GPU detected")
        except:
            pass
        
        # Check for NPU (Neural Processing Unit)
        if os.path.exists('/dev/rknpu'):
            self.npu_available = True
            logger.info("RK3568 NPU detected")
        
        # Check for hardware video acceleration
        if os.path.exists('/dev/video-dec0') or os.path.exists('/dev/mpp_service'):
            self.vaapi_available = True
            logger.info("Hardware video acceleration available")
            
        # Set environment variables for hardware acceleration
        if self.gpu_available:
            os.environ['GST_GL_PLATFORM'] = 'egl'
            os.environ['GST_GL_API'] = 'gles2'
            
        if self.vaapi_available:
            os.environ['GST_VAAPI_ALL_DRIVERS'] = '1'
            os.environ['LIBVA_DRIVER_NAME'] = 'rockchip'
    
    def _detect_generic_capabilities(self):
        """Detect generic hardware acceleration capabilities"""
        # Check for CUDA
        try:
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self.gpu_available = True
                logger.info("CUDA GPU detected")
        except:
            pass
        
        # Check for OpenCL
        try:
            if cv2.ocl.haveOpenCL():
                self.gpu_available = True
                logger.info("OpenCL available")
        except:
            pass
    
    def create_optimized_capture(self, camera_index: int) -> cv2.VideoCapture:
        """Create hardware-accelerated video capture if available"""
        cap = cv2.VideoCapture(camera_index)
        
        if self.is_rk3568:
            # RK3568 specific optimizations
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            # Try to enable hardware acceleration
            if self.vaapi_available:
                try:
                    cap.set(cv2.CAP_PROP_BACKEND, cv2.CAP_GSTREAMER)
                    logger.info("Using GStreamer backend with hardware acceleration")
                except:
                    logger.warning("Failed to set GStreamer backend")
        
        return cap
    
    def resize_image_accelerated(self, image: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
        """Hardware-accelerated image resizing"""
        if self.gpu_available and self.is_rk3568:
            try:
                # Use OpenCL acceleration if available
                if cv2.ocl.haveOpenCL():
                    gpu_image = cv2.UMat(image)
                    gpu_resized = cv2.resize(gpu_image, size, interpolation=cv2.INTER_LINEAR)
                    return gpu_resized.get()
            except Exception as e:
                logger.debug(f"GPU resize failed, falling back to CPU: {e}")
        
        # Fallback to CPU
        return cv2.resize(image, size, interpolation=cv2.INTER_LINEAR)
    
    def apply_filters_accelerated(self, image: np.ndarray, filters: dict) -> np.ndarray:
        """Apply image filters with hardware acceleration when possible"""
        result = image.copy()
        
        try:
            if self.gpu_available and cv2.ocl.haveOpenCL():
                # Use GPU acceleration
                gpu_image = cv2.UMat(result)
                
                # Apply brightness/contrast
                if 'brightness' in filters or 'contrast' in filters:
                    alpha = 1.0 + filters.get('contrast', 0) / 100.0
                    beta = filters.get('brightness', 0)
                    gpu_image = cv2.convertScaleAbs(gpu_image, alpha=alpha, beta=beta)
                
                # Apply blur if requested
                if 'blur' in filters and filters['blur'] > 0:
                    kernel_size = int(filters['blur']) * 2 + 1
                    gpu_image = cv2.GaussianBlur(gpu_image, (kernel_size, kernel_size), 0)
                
                result = gpu_image.get()
                
            else:
                # CPU fallback
                if 'brightness' in filters or 'contrast' in filters:
                    alpha = 1.0 + filters.get('contrast', 0) / 100.0
                    beta = filters.get('brightness', 0)
                    result = cv2.convertScaleAbs(result, alpha=alpha, beta=beta)
                
                if 'blur' in filters and filters['blur'] > 0:
                    kernel_size = int(filters['blur']) * 2 + 1
                    result = cv2.GaussianBlur(result, (kernel_size, kernel_size), 0)
                    
        except Exception as e:
            logger.error(f"Filter acceleration failed: {e}")
            
        return result
    
    def encode_image_accelerated(self, image: np.ndarray, quality: int = 95) -> bytes:
        """Hardware-accelerated image encoding"""
        if self.vaapi_available and self.is_rk3568:
            try:
                # Try hardware JPEG encoding
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                success, encoded = cv2.imencode('.jpg', image, encode_params)
                if success:
                    return encoded.tobytes()
            except Exception as e:
                logger.debug(f"Hardware encoding failed: {e}")
        
        # Fallback to software encoding
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        success, encoded = cv2.imencode('.jpg', image, encode_params)
        return encoded.tobytes() if success else b''
    
    def optimize_memory_usage(self):
        """Optimize memory usage for embedded systems"""
        if self.is_rk3568:
            # Set conservative memory limits
            import gc
            gc.collect()
            
            # Reduce OpenCV thread count for memory efficiency
            cv2.setNumThreads(2)
            
            # Set buffer pool size limits
            try:
                cv2.setUseOptimized(True)
            except:
                pass
    
    def create_video_writer_accelerated(self, 
                                       filename: str, 
                                       fourcc: str, 
                                       fps: float, 
                                       frame_size: Tuple[int, int]) -> cv2.VideoWriter:
        """Create hardware-accelerated video writer"""
        fourcc_code = cv2.VideoWriter_fourcc(*fourcc)
        
        if self.vaapi_available and self.is_rk3568:
            try:
                # Try hardware encoding
                writer = cv2.VideoWriter(filename, cv2.CAP_GSTREAMER, fourcc_code, fps, frame_size)
                if writer.isOpened():
                    logger.info("Using hardware-accelerated video encoding")
                    return writer
            except Exception as e:
                logger.debug(f"Hardware video encoding failed: {e}")
        
        # Fallback to software encoding
        return cv2.VideoWriter(filename, fourcc_code, fps, frame_size)
    
    def get_optimal_thread_count(self) -> int:
        """Get optimal thread count for the platform"""
        if self.is_rk3568:
            # RK3568 has 4 CPU cores, leave 1 for system
            return min(3, os.cpu_count() or 2)
        else:
            # Generic case
            return max(1, (os.cpu_count() or 4) - 1)
    
    def enable_optimizations(self):
        """Enable all available optimizations"""
        try:
            # Enable OpenCV optimizations
            cv2.setUseOptimized(True)
            
            # Set optimal thread count
            cv2.setNumThreads(self.get_optimal_thread_count())
            
            # Enable OpenCL if available
            if cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(True)
                logger.info("OpenCL acceleration enabled")
            
            # Platform-specific optimizations
            if self.is_rk3568:
                self.optimize_memory_usage()
                logger.info("RK3568 optimizations enabled")
                
        except Exception as e:
            logger.error(f"Failed to enable optimizations: {e}")
    
    def get_acceleration_info(self) -> dict:
        """Get information about available acceleration"""
        return {
            'platform': self.platform,
            'is_rk3568': self.is_rk3568,
            'gpu_available': self.gpu_available,
            'npu_available': self.npu_available,
            'vaapi_available': self.vaapi_available,
            'opencl_available': cv2.ocl.haveOpenCL() if hasattr(cv2, 'ocl') else False,
            'cuda_devices': cv2.cuda.getCudaEnabledDeviceCount() if hasattr(cv2, 'cuda') else 0,
            'opencv_version': cv2.__version__,
            'optimal_threads': self.get_optimal_thread_count()
        }

# Global instance
hardware_accelerator = HardwareAccelerator()