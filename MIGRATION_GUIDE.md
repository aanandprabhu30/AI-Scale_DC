# AI-Scale Migration Guide v2.2.0 → v2.3.0

## 🚀 **Major Changes Overview**

This guide helps you understand the significant changes from v2.2.0 (macOS-focused) to v2.3.0 (cross-platform with RK3568 optimization).

## 📋 **Breaking Changes**

### **1. Architecture Changes**

- **Old**: macOS-specific with AVFoundation camera backend
- **New**: Cross-platform with hardware abstraction layer

### **2. Camera System**

- **Old**: `cv2.CAP_AVFOUNDATION` hardcoded backend
- **New**: `CameraBackend` class with platform detection
- **Migration**: Camera initialization now automatic based on platform

### **3. Configuration System**

- **Old**: Static configuration in constants
- **New**: Dynamic platform-specific configuration
- **Migration**: Use `platform_config.get()` instead of hardcoded values

### **4. Dependencies**

- **Added**: `pyserial`, `psutil` for scale and monitoring
- **Changed**: Platform-specific OpenCV packages
- **Migration**: Run `./setup_dev.sh` or install from updated `requirements.txt`

## 🔧 **API Changes**

### **Camera Initialization**

```python
# OLD (v2.2.0)
camera = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)

# NEW (v2.3.0)
from camera_backend import camera_backend
camera = camera_backend.create_capture(index)
```

### **Configuration Access**

```python
# OLD (v2.2.0)
width = IMX219_CONFIGS["preview"]["width"]

# NEW (v2.3.0)
from platform_config import platform_config
width = platform_config.get('camera.default_resolution', (1920, 1080))[0]
```

### **Platform Detection**

```python
# NEW (v2.3.0)
if platform_config.is_rk3568:
    # RK3568 specific code
    enable_hardware_acceleration()
elif platform_config.platform == 'darwin':
    # macOS specific code
    setup_retina_display()
```

## 🆕 **New Features**

### **1. Scale Integration**

```python
from scale_interface import ScaleInterface, ScaleProtocol

# Auto-detect and connect to scale
scale = ScaleInterface()
if scale.connect():
    weight = scale.get_weight(stable_only=True)
    print(f"Weight: {weight.weight} {weight.unit}")
```

### **2. Hardware Acceleration**

```python
from hardware_acceleration import hardware_accelerator

# Enable all optimizations
hardware_accelerator.enable_optimizations()

# Get acceleration info
info = hardware_accelerator.get_acceleration_info()
print(f"GPU available: {info['gpu_available']}")
```

### **3. System Monitoring**

```python
from system_monitor import system_monitor

# Start monitoring
system_monitor.start_monitoring()

# Get current metrics
metrics = system_monitor.get_current_metrics()
print(f"CPU: {metrics.cpu_percent}%, Memory: {metrics.memory_percent}%")
```

### **4. Display Optimization**

```python
from display_manager import display_manager

# Get optimal window size
size = display_manager.get_optimal_window_size(1000, 700)

# Setup platform-specific window
display_manager.setup_window_for_platform(window)
```

## 📦 **Deployment Changes**

### **Development Setup**

```bash
# OLD (v2.2.0)
pip install -r requirements.txt
python AIScaleDataCollector.py

# NEW (v2.3.0)
./setup_dev.sh  # Automated setup
./run.sh        # Start application
```

### **Production Deployment (RK3568)**

```bash
# Copy files to device
scp -r * user@rk3568-device:/tmp/aiscale/

# Deploy on device
ssh user@rk3568-device
cd /tmp/aiscale
sudo ./deploy_rk3568.sh
```

### **Service Management**

```bash
# Check status
sudo systemctl status aiscale

# View logs
sudo journalctl -u aiscale -f

# Start/stop
sudo systemctl start aiscale
sudo systemctl stop aiscale
```

## 🗂️ **File Structure Changes**

### **New Files**

``` bash
├── camera_backend.py          # Hardware abstraction for cameras
├── scale_interface.py         # Serial scale communication
├── platform_config.py        # Platform-specific configuration
├── hardware_acceleration.py   # GPU/NPU acceleration
├── system_monitor.py         # Performance monitoring
├── display_manager.py        # Display optimization
├── deploy_rk3568.sh          # Production deployment script
├── setup_dev.sh              # Development setup script
└── run.sh                    # Application launcher
```

### **Updated Files**

``` bash
├── AIScaleDataCollector.py   # Main app with scale integration
├── requirements.txt          # Cross-platform dependencies
├── README.md                 # Updated documentation
└── .gitignore               # Extended for new platforms
```

### **Removed Files**

``` bash
├── CAMERA_IMPROVEMENTS_SUMMARY.md  # Obsolete documentation
└── setup.sh                        # Replaced by setup_dev.sh
```

## 🔄 **Migration Steps**

### **1. Update Dependencies**

```bash
# Remove old virtual environment
rm -rf venv/

# Run new setup
./setup_dev.sh
```

### **2. Update Configuration**

If you have custom configuration files:

```bash
# Backup old config
cp config.json config.json.backup

# Update to new format (automatic detection)
# Your settings will be migrated automatically
```

### **3. Test Platform Detection**

```python
from platform_config import platform_config
print(f"Platform: {platform_config.platform}")
print(f"Is RK3568: {platform_config.is_rk3568}")
print(f"Camera backend: {platform_config.get('camera.backend')}")
```

### **4. Verify Hardware Support**

```python
from camera_backend import CameraBackend
from scale_interface import ScaleInterface

# Test camera
backend = CameraBackend()
cameras = backend.enumerate_cameras()
print(f"Found {len(cameras)} cameras")

# Test scale (if available)
scale = ScaleInterface()
if scale.connect():
    print("Scale connected successfully")
```

## 🧪 **Testing Your Migration**

### **1. Basic Functionality**

```bash
# Start application
./run.sh

# Verify camera detection
# Verify UI scaling
# Test image capture
```

### **2. Platform-Specific Features**

```bash
# On RK3568
# Verify hardware acceleration
# Test serial scale connection
# Check thermal monitoring

# On macOS
# Verify Retina display support
# Test AVFoundation camera
# Check permission handling
```

### **3. Performance Monitoring**

```python
from system_monitor import system_monitor

system_monitor.start_monitoring()
# Run application for 5 minutes
metrics = system_monitor.get_average_metrics(5)
print(f"Average CPU: {metrics['cpu_avg']:.1f}%")
```

## ⚠️ **Common Issues & Solutions**

### **1. Camera Not Detected**

```bash
# Check platform detection
python3 -c "from platform_config import platform_config; print(platform_config.platform)"

# List available cameras
python3 -c "from camera_backend import CameraBackend; print(CameraBackend().enumerate_cameras())"
```

### **2. Scale Connection Failed**

```bash
# List serial ports
python3 -c "from scale_interface import ScaleInterface; print(ScaleInterface().list_serial_ports())"

# Check permissions
sudo usermod -a -G dialout $USER
# Logout and login again
```

### **3. Performance Issues**

```bash
# Check system resources
python3 -c "from system_monitor import system_monitor; system_monitor.start_monitoring(); import time; time.sleep(2); print(system_monitor.get_current_metrics())"

# Enable hardware acceleration
python3 -c "from hardware_acceleration import hardware_accelerator; hardware_accelerator.enable_optimizations(); print(hardware_accelerator.get_acceleration_info())"
```

### **4. Display Issues**

```bash
# Check display configuration
python3 -c "from display_manager import display_manager; print(display_manager.get_display_info())"

# For RK3568, ensure proper X11 setup
export DISPLAY=:0
xrandr --output HDMI-1 --mode 1366x768
```

## 📈 **Performance Improvements**

### **Memory Usage**

- **v2.2.0**: ~200MB (macOS)
- **v2.3.0**: ~150MB (RK3568), ~200MB (other platforms)

### **Startup Time**

- **v2.2.0**: ~3 seconds
- **v2.3.0**: ~2 seconds (with optimizations)

### **Camera Performance**

- **v2.2.0**: Platform-dependent
- **v2.3.0**: Optimized per platform (MJPEG, buffer management)

## 🤝 **Getting Help**

### **Documentation**

- Read the updated [README.md](README.md)
- Check platform-specific configuration in `platform_config.py`
- Review hardware acceleration options in `hardware_acceleration.py`

### **Debugging**

```bash
# Enable debug logging
export AISCALE_DEBUG=1
./run.sh

# Check logs
tail -f logs/aiscale.log
```

### **Community Support**

- Open issues on GitHub for bugs
- Share performance results for different platforms
- Contribute platform-specific optimizations

---

**Migration Complete!** 🎉

Your AI-Scale Data Collector is now ready for cross-platform deployment with full RK3568 optimization.
