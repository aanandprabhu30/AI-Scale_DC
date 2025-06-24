import platform
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import psutil
import logging

logger = logging.getLogger(__name__)

class PlatformConfig:
    """Platform-specific configuration management"""
    
    # RK3568 specific optimizations
    RK3568_CONFIG = {
        "camera": {
            "backend": "v4l2",
            "buffer_size": 1,
            "preferred_format": "MJPG",
            "max_resolution": (1920, 1080),
            "default_resolution": (1366, 768),  # Match display
            "fps": 30,
            "hardware_acceleration": True
        },
        "display": {
            "width": 1366,
            "height": 768,
            "fullscreen_default": True,
            "dpi_scale": 1.0,
            "vsync": True,
            "opengl": "es2"  # OpenGL ES 2.0 for embedded
        },
        "performance": {
            "max_threads": 4,  # Quad-core Cortex-A55
            "image_cache_size": 100,  # MB
            "db_cache_size": 50,  # MB
            "low_memory_mode": True,
            "gpu_acceleration": True,
            "npu_acceleration": True  # RK3568 has NPU
        },
        "serial": {
            "default_ports": ["/dev/ttyS0", "/dev/ttyS1", "/dev/ttyUSB0"],
            "baudrate": 9600,
            "scale_protocol": "generic"
        },
        "storage": {
            "data_path": "/home/aiscale/data",
            "temp_path": "/tmp/aiscale",
            "log_path": "/var/log/aiscale",
            "max_storage_gb": 20  # Leave space on 32GB eMMC
        },
        "network": {
            "enable_remote_api": True,
            "api_port": 8080,
            "enable_mqtt": True,
            "mqtt_broker": "localhost"
        }
    }
    
    # Generic ARM Linux config
    ARM_LINUX_CONFIG = {
        "camera": {
            "backend": "v4l2",
            "buffer_size": 1,
            "preferred_format": "MJPG",
            "max_resolution": (1920, 1080),
            "fps": 30
        },
        "display": {
            "fullscreen_default": False,
            "dpi_scale": 1.0
        },
        "performance": {
            "max_threads": os.cpu_count() or 4,
            "low_memory_mode": True
        },
        "serial": {
            "default_ports": ["/dev/ttyUSB0", "/dev/ttyS0"],
            "baudrate": 9600
        },
        "storage": {
            "data_path": os.path.expanduser("~/aiscale_data"),
            "temp_path": "/tmp/aiscale",
            "log_path": os.path.expanduser("~/.aiscale/logs")
        }
    }
    
    # macOS config (existing platform)
    MACOS_CONFIG = {
        "camera": {
            "backend": "avfoundation",
            "buffer_size": 3,
            "preferred_format": "MJPG",
            "max_resolution": (3840, 2160),
            "fps": 60
        },
        "display": {
            "fullscreen_default": False,
            "dpi_scale": 2.0  # Retina display
        },
        "performance": {
            "max_threads": os.cpu_count() or 8,
            "low_memory_mode": False
        },
        "serial": {
            "default_ports": ["/dev/tty.usbserial*", "/dev/tty.usbmodem*"],
            "baudrate": 9600
        },
        "storage": {
            "data_path": os.path.expanduser("~/Desktop/AIScaleData"),
            "temp_path": "/tmp/aiscale",
            "log_path": os.path.expanduser("~/Library/Logs/AIScale")
        }
    }
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.machine = platform.machine().lower()
        self.is_arm = self.machine in ['aarch64', 'arm64', 'armv7l', 'armv8']
        self.is_rk3568 = self._detect_rk3568()
        
        # Load configuration
        self.config = self._load_platform_config()
        
        # Create necessary directories
        self._create_directories()
        
    def _detect_rk3568(self) -> bool:
        """Detect if running on RK3568 hardware"""
        try:
            # Check CPU info for RK3568
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read().lower()
                    if 'rk3568' in cpuinfo or 'rockchip' in cpuinfo:
                        return True
                        
            # Check device tree
            if os.path.exists('/proc/device-tree/model'):
                with open('/proc/device-tree/model', 'r') as f:
                    model = f.read().lower()
                    if 'rk3568' in model:
                        return True
                        
        except Exception as e:
            logger.debug(f"Failed to detect RK3568: {e}")
            
        return False
    
    def _load_platform_config(self) -> Dict[str, Any]:
        """Load platform-specific configuration"""
        # Start with base config
        config = {}
        
        # Select platform-specific config
        if self.is_rk3568:
            logger.info("Detected RK3568 hardware - loading optimized configuration")
            config = self.RK3568_CONFIG.copy()
        elif self.platform == 'darwin':
            logger.info("Detected macOS - loading macOS configuration")
            config = self.MACOS_CONFIG.copy()
        elif self.platform == 'linux' and self.is_arm:
            logger.info("Detected ARM Linux - loading ARM configuration")
            config = self.ARM_LINUX_CONFIG.copy()
        else:
            logger.info(f"Loading generic configuration for {self.platform}")
            config = self.ARM_LINUX_CONFIG.copy()
        
        # Load user overrides if they exist
        user_config_path = self._get_user_config_path()
        if user_config_path.exists():
            try:
                with open(user_config_path, 'r') as f:
                    user_config = json.load(f)
                    config = self._merge_configs(config, user_config)
                    logger.info(f"Loaded user configuration from {user_config_path}")
            except Exception as e:
                logger.error(f"Failed to load user config: {e}")
        
        return config
    
    def _get_user_config_path(self) -> Path:
        """Get path for user configuration file"""
        if self.platform == 'linux':
            return Path.home() / '.config' / 'aiscale' / 'config.json'
        elif self.platform == 'darwin':
            return Path.home() / 'Library' / 'Preferences' / 'aiscale' / 'config.json'
        else:
            return Path.home() / '.aiscale' / 'config.json'
    
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge configuration dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def _create_directories(self):
        """Create necessary directories"""
        dirs = [
            self.get('storage.data_path'),
            self.get('storage.temp_path'),
            self.get('storage.log_path'),
            self._get_user_config_path().parent
        ]
        
        for dir_path in dirs:
            if dir_path:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
            
        config[keys[-1]] = value
    
    def save_user_config(self):
        """Save current configuration as user override"""
        config_path = self._get_user_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        logger.info(f"Saved configuration to {config_path}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get current system information"""
        info = {
            "platform": self.platform,
            "machine": self.machine,
            "is_arm": self.is_arm,
            "is_rk3568": self.is_rk3568,
            "cpu_count": psutil.cpu_count(),
            "memory_total_mb": psutil.virtual_memory().total // (1024 * 1024),
            "memory_available_mb": psutil.virtual_memory().available // (1024 * 1024),
            "disk_usage_percent": psutil.disk_usage('/').percent
        }
        
        # Add GPU info if available
        if self.is_rk3568:
            info["gpu"] = "Mali-G52 2EE"
            info["npu"] = "0.8TOPS NPU"
            
        return info
    
    def optimize_for_hardware(self):
        """Apply hardware-specific optimizations"""
        if self.is_rk3568:
            logger.info("Applying RK3568 optimizations...")
            
            # Set CPU governor to performance
            try:
                for cpu in range(4):
                    governor_path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"
                    if os.path.exists(governor_path):
                        with open(governor_path, 'w') as f:
                            f.write("performance")
            except Exception as e:
                logger.warning(f"Failed to set CPU governor: {e}")
            
            # Enable hardware video decoding
            os.environ['GST_VAAPI_ALL_DRIVERS'] = '1'
            os.environ['LIBVA_DRIVER_NAME'] = 'rockchip'
            
            # Set memory limits
            if psutil.virtual_memory().total < 4 * 1024 * 1024 * 1024:  # Less than 4GB
                self.set('performance.low_memory_mode', True)
                self.set('performance.image_cache_size', 50)
                
    def get_optimal_thread_count(self, task_type: str = "general") -> int:
        """Get optimal thread count for specific task"""
        cpu_count = psutil.cpu_count()
        
        if self.is_rk3568:
            # RK3568 has 4 cores
            if task_type == "camera":
                return 1  # Single thread for camera capture
            elif task_type == "image_processing":
                return 2  # Leave cores for UI and system
            else:
                return 3  # General tasks
        else:
            # General case
            if task_type == "camera":
                return 1
            elif task_type == "image_processing":
                return max(1, cpu_count - 2)
            else:
                return max(1, cpu_count - 1)

# Global instance
platform_config = PlatformConfig()