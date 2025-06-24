import psutil
import time
import threading
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from collections import deque
import json
from pathlib import Path
from platform_config import platform_config

logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_available_mb: int
    disk_usage_percent: float
    disk_free_gb: float
    temperature: Optional[float] = None
    gpu_usage: Optional[float] = None
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0

class SystemMonitor:
    """System monitoring for embedded environments"""
    
    def __init__(self, 
                 update_interval: float = 5.0,
                 history_size: int = 720):  # 1 hour at 5s intervals
        self.update_interval = update_interval
        self.history_size = history_size
        self.metrics_history = deque(maxlen=history_size)
        self.callbacks = []
        self.running = False
        self.monitor_thread = None
        
        # Performance thresholds
        self.thresholds = {
            'cpu_warning': platform_config.get('monitoring.cpu_warning', 80),
            'cpu_critical': platform_config.get('monitoring.cpu_critical', 95),
            'memory_warning': platform_config.get('monitoring.memory_warning', 85),
            'memory_critical': platform_config.get('monitoring.memory_critical', 95),
            'disk_warning': platform_config.get('monitoring.disk_warning', 90),
            'disk_critical': platform_config.get('monitoring.disk_critical', 95),
            'temperature_warning': platform_config.get('monitoring.temp_warning', 70),
            'temperature_critical': platform_config.get('monitoring.temp_critical', 85)
        }
        
        # Alert state tracking
        self.alert_states = {}
        self.last_alert_time = {}
        self.alert_cooldown = 60  # seconds
        
    def add_callback(self, callback: Callable[[SystemMetrics], None]):
        """Add callback for metric updates"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[SystemMetrics], None]):
        """Remove callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def start_monitoring(self):
        """Start system monitoring thread"""
        if self.running:
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"System monitoring started (interval: {self.update_interval}s)")
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        logger.info("System monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Check for alerts
                self._check_alerts(metrics)
                
                # Notify callbacks
                for callback in self.callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(self.update_interval)
    
    def _collect_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available // (1024 * 1024)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage_percent = disk.percent
        disk_free_gb = disk.free // (1024 * 1024 * 1024)
        
        # Network usage
        network = psutil.net_io_counters()
        network_bytes_sent = network.bytes_sent
        network_bytes_recv = network.bytes_recv
        
        # Temperature (platform-specific)
        temperature = self._get_temperature()
        
        # GPU usage (if available)
        gpu_usage = self._get_gpu_usage()
        
        return SystemMetrics(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            disk_usage_percent=disk_usage_percent,
            disk_free_gb=disk_free_gb,
            temperature=temperature,
            gpu_usage=gpu_usage,
            network_bytes_sent=network_bytes_sent,
            network_bytes_recv=network_bytes_recv
        )
    
    def _get_temperature(self) -> Optional[float]:
        """Get system temperature"""
        try:
            if platform_config.is_rk3568:
                # RK3568 specific temperature reading
                temp_files = [
                    '/sys/class/thermal/thermal_zone0/temp',
                    '/sys/class/thermal/thermal_zone1/temp'
                ]
                
                for temp_file in temp_files:
                    try:
                        with open(temp_file, 'r') as f:
                            temp_millic = int(f.read().strip())
                            return temp_millic / 1000.0  # Convert to Celsius
                    except:
                        continue
            
            # Generic temperature reading
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        return entries[0].current
                        
        except Exception as e:
            logger.debug(f"Temperature reading failed: {e}")
            
        return None
    
    def _get_gpu_usage(self) -> Optional[float]:
        """Get GPU usage if available"""
        try:
            if platform_config.is_rk3568:
                # RK3568 Mali GPU usage (if available)
                gpu_files = [
                    '/sys/class/devfreq/ff400000.gpu/load',
                    '/sys/devices/platform/ff400000.gpu/devfreq/ff400000.gpu/load'
                ]
                
                for gpu_file in gpu_files:
                    try:
                        with open(gpu_file, 'r') as f:
                            load_str = f.read().strip()
                            # Format might be "usage@frequency"
                            if '@' in load_str:
                                usage = int(load_str.split('@')[0])
                                return float(usage)
                    except:
                        continue
        except Exception as e:
            logger.debug(f"GPU usage reading failed: {e}")
            
        return None
    
    def _check_alerts(self, metrics: SystemMetrics):
        """Check for alert conditions"""
        current_time = time.time()
        
        # CPU alerts
        self._check_threshold_alert(
            'cpu', metrics.cpu_percent, 
            self.thresholds['cpu_warning'], 
            self.thresholds['cpu_critical'],
            current_time
        )
        
        # Memory alerts
        self._check_threshold_alert(
            'memory', metrics.memory_percent,
            self.thresholds['memory_warning'],
            self.thresholds['memory_critical'],
            current_time
        )
        
        # Disk alerts
        self._check_threshold_alert(
            'disk', metrics.disk_usage_percent,
            self.thresholds['disk_warning'],
            self.thresholds['disk_critical'],
            current_time
        )
        
        # Temperature alerts
        if metrics.temperature is not None:
            self._check_threshold_alert(
                'temperature', metrics.temperature,
                self.thresholds['temperature_warning'],
                self.thresholds['temperature_critical'],
                current_time
            )
    
    def _check_threshold_alert(self, 
                             metric_name: str, 
                             value: float, 
                             warning_threshold: float, 
                             critical_threshold: float,
                             current_time: float):
        """Check individual threshold and trigger alerts"""
        alert_key = f"{metric_name}_critical"
        warning_key = f"{metric_name}_warning"
        
        # Check for critical alert
        if value >= critical_threshold:
            if not self.alert_states.get(alert_key, False):
                self._trigger_alert(alert_key, f"{metric_name.title()} critical: {value:.1f}%", current_time)
                self.alert_states[alert_key] = True
                self.alert_states[warning_key] = True  # Also set warning
        
        # Check for warning alert (if not already critical)
        elif value >= warning_threshold:
            if not self.alert_states.get(warning_key, False):
                self._trigger_alert(warning_key, f"{metric_name.title()} warning: {value:.1f}%", current_time)
                self.alert_states[warning_key] = True
        
        # Clear alerts if below warning threshold
        else:
            if self.alert_states.get(alert_key, False) or self.alert_states.get(warning_key, False):
                logger.info(f"{metric_name.title()} returned to normal: {value:.1f}%")
                self.alert_states[alert_key] = False
                self.alert_states[warning_key] = False
    
    def _trigger_alert(self, alert_type: str, message: str, current_time: float):
        """Trigger an alert with cooldown"""
        last_alert = self.last_alert_time.get(alert_type, 0)
        
        if current_time - last_alert > self.alert_cooldown:
            logger.warning(f"SYSTEM ALERT: {message}")
            self.last_alert_time[alert_type] = current_time
            
            # Additional actions for critical alerts
            if 'critical' in alert_type:
                self._handle_critical_alert(alert_type, message)
    
    def _handle_critical_alert(self, alert_type: str, message: str):
        """Handle critical system alerts"""
        if 'memory' in alert_type:
            # Force garbage collection
            import gc
            gc.collect()
            logger.info("Forced garbage collection due to high memory usage")
        
        elif 'disk' in alert_type:
            # Clean up temporary files
            self._cleanup_temp_files()
        
        elif 'temperature' in alert_type and platform_config.is_rk3568:
            # Reduce CPU frequency if possible
            self._throttle_cpu()
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            temp_path = Path(platform_config.get('storage.temp_path', '/tmp'))
            if temp_path.exists():
                for file in temp_path.glob('*'):
                    if file.is_file() and file.stat().st_mtime < time.time() - 3600:  # Older than 1 hour
                        file.unlink()
                        logger.debug(f"Cleaned up temp file: {file}")
        except Exception as e:
            logger.error(f"Temp cleanup failed: {e}")
    
    def _throttle_cpu(self):
        """Throttle CPU frequency to reduce temperature"""
        try:
            if platform_config.is_rk3568:
                # Set conservative CPU governor
                governor_files = [
                    '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor',
                    '/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor',
                    '/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor',
                    '/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor'
                ]
                
                for governor_file in governor_files:
                    try:
                        with open(governor_file, 'w') as f:
                            f.write('conservative')
                    except:
                        pass
                        
                logger.info("CPU throttling enabled due to high temperature")
        except Exception as e:
            logger.error(f"CPU throttling failed: {e}")
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent metrics"""
        return self.metrics_history[-1] if self.metrics_history else None
    
    def get_average_metrics(self, minutes: int = 5) -> Optional[Dict]:
        """Get average metrics over specified time period"""
        if not self.metrics_history:
            return None
            
        cutoff_time = time.time() - (minutes * 60)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return None
        
        return {
            'cpu_avg': sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
            'memory_avg': sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
            'disk_usage': recent_metrics[-1].disk_usage_percent,  # Latest value
            'temperature_avg': sum(m.temperature for m in recent_metrics if m.temperature) / 
                              len([m for m in recent_metrics if m.temperature]) if any(m.temperature for m in recent_metrics) else None
        }
    
    def save_metrics_history(self, filename: str):
        """Save metrics history to file"""
        try:
            data = [
                {
                    'timestamp': m.timestamp,
                    'cpu_percent': m.cpu_percent,
                    'memory_percent': m.memory_percent,
                    'memory_available_mb': m.memory_available_mb,
                    'disk_usage_percent': m.disk_usage_percent,
                    'disk_free_gb': m.disk_free_gb,
                    'temperature': m.temperature,
                    'gpu_usage': m.gpu_usage
                }
                for m in self.metrics_history
            ]
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Metrics history saved to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def get_system_info(self) -> Dict:
        """Get comprehensive system information"""
        return {
            'platform': platform_config.platform,
            'is_rk3568': platform_config.is_rk3568,
            'cpu_count': psutil.cpu_count(),
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'disk_total_gb': psutil.disk_usage('/').total / (1024**3),
            'boot_time': psutil.boot_time(),
            'uptime_hours': (time.time() - psutil.boot_time()) / 3600,
            'current_metrics': self.get_current_metrics(),
            'thresholds': self.thresholds,
            'monitoring_active': self.running
        }

# Global instance
system_monitor = SystemMonitor()