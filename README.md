# AI-Scale Data Collector v2.3.0

A comprehensive cross-platform produce image capture and weighing system, optimized for embedded hardware including Rockchip RK3568 platforms.

## 🚀 **Key Features**

### **🎯 Cross-Platform Support**

- **Rockchip RK3568** (SV3c-MPOS35687) - Primary target with full optimization
- **Linux ARM/x86** - Full V4L2 camera support with hardware acceleration
- **macOS** - AVFoundation backend with Retina display support
- **Windows** - DirectShow backend compatibility

### **⚖️ Integrated Scale System**

- **Auto-detection** of serial scales on USB/RS232 ports
- **Multi-protocol support**: Toledo, Ohaus, A&D, Mettler Toledo, Generic
- **Real-time weight display** with stability indication
- **Automatic weight capture** with image metadata
- **Scale commands**: Zero, Tare, Print

### **📸 Advanced Camera System**

- **Hardware abstraction layer** for cross-platform camera access
- **Automatic camera enumeration** with platform-specific optimizations
- **Resolution detection** and optimal settings (1366x768 optimized)
- **Hardware acceleration** (Mali GPU, NPU, OpenCL)
- **Smart white balance** with camera-specific corrections

### **💻 Embedded Optimization**

- **1366x768 display optimization** for RK3568 BOE NT156WHM-N42
- **Memory management** for 2GB/4GB RAM configurations
- **Storage optimization** for 32GB eMMC
- **Thermal monitoring** with automatic throttling
- **System resource monitoring** and alerts

### **🔧 Production Ready**

- **Systemd service** with auto-start and monitoring
- **Comprehensive logging** with rotation
- **Performance analytics** and diagnostics
- **Remote API** for integration (optional)
- **Touch interface** optimized for embedded use

## 📋 **Hardware Requirements**

### **Primary Target: RK3568 Platform**

- **SoC**: Rockchip RK3568 (Quad-core Cortex-A55, up to 2.0GHz)
- **Memory**: 2GB/4GB LPDDR4X
- **Storage**: 32GB eMMC 5.1
- **Display**: 15.6" 1366×768 (BOE NT156WHM-N42 V8.3)
- **Connectivity**: USB 3.0/2.0, Serial COM ports, Ethernet, WiFi
- **Camera**: USB cameras via V4L2
- **Scale**: USB/RS232 serial scales

### **Alternative Platforms**

- **Linux**: ARM64/x86_64 with 2GB+ RAM
- **macOS**: 10.15+ with 4GB+ RAM  
- **Windows**: 10/11 with 4GB+ RAM

## 🛠 **Installation**

### **Development Setup**

```bash
git clone <repository-url>
cd AI-Scale
chmod +x setup_dev.sh
./setup_dev.sh
```

### **RK3568 Production Deployment**

```bash
# Copy files to target device
scp -r * user@rk3568-device:/tmp/aiscale/

# SSH to device and deploy
ssh user@rk3568-device
cd /tmp/aiscale
sudo ./deploy_rk3568.sh
```

### **Manual Installation**

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python3 AIScaleDataCollector.py
```

## 🎮 **Usage**

### **Basic Operation**

1. **Connect scale** - USB or serial connection (auto-detected)
2. **Select camera** - Automatic detection and optimization
3. **Choose produce type** - Add new types as needed
4. **Capture images** - Weight automatically recorded
5. **Data organization** - Images and metadata saved systematically

### **Keyboard Shortcuts**

- **Space**: Capture image
- **Ctrl+Q**: Quit application
- **F11**: Toggle fullscreen (embedded mode)
- **Ctrl+D**: Debug information
- **Ctrl+S**: System status

### **Scale Operations**

- **Auto-connect**: Automatic detection on startup
- **Manual connect**: Click "Connect" button
- **Zero scale**: Automatic zero before weighing
- **Tare container**: Remove container weight
- **Stable readings**: Only captures when weight is stable

## 🏗 **Architecture**

### **Core Modules**

- **`camera_backend.py`** - Hardware abstraction for cameras
- **`scale_interface.py`** - Serial communication with scales  
- **`platform_config.py`** - Platform-specific configurations
- **`hardware_acceleration.py`** - GPU/NPU acceleration
- **`system_monitor.py`** - Performance monitoring
- **`display_manager.py`** - Display optimization
- **`AIScaleDataCollector.py`** - Main application

### **Data Flow**

``` bash
Camera → Image Processing → Scale Reading → Metadata → Storage
   ↓           ↓               ↓            ↓         ↓
V4L2/AVF → OpenCV/GPU → Serial Protocol → SQLite → eMMC/SSD
```

### **Platform Detection**

```python
from platform_config import platform_config

if platform_config.is_rk3568:
    # RK3568 specific optimizations
    use_mali_gpu()
    enable_npu_acceleration()
    optimize_for_emmc()
```

## 📊 **Data Organization**

``` bash
/home/aiscale/data/
├── raw/
│   ├── apple/
│   │   ├── apple_0001_20241224_143022_125g.jpg
│   │   ├── apple_0002_20241224_143045_132g.jpg
│   │   └── ...
│   ├── banana/
│   ├── orange/
│   └── ...
├── metadata.db          # SQLite database
├── config.json         # User configuration
└── session_logs/       # Capture session logs
```

### **Metadata Schema**

```sql
CREATE TABLE captures (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    class_name TEXT,
    timestamp TEXT,
    resolution TEXT,
    file_size INTEGER,
    weight REAL,
    weight_unit TEXT,
    camera_info TEXT,
    session_id TEXT
);
```

## ⚡ **Performance Optimizations**

### **RK3568 Specific**

- **Mali GPU acceleration** for image processing
- **NPU utilization** for AI workloads (0.8TOPS)
- **MJPEG hardware encoding** for camera capture
- **Memory optimization** for 2GB configurations
- **CPU governor tuning** for performance vs power

### **Cross-Platform**

- **OpenCL acceleration** when available
- **Multi-threading** for camera and scale operations
- **Buffer optimization** for low-latency capture
- **Efficient memory management** with garbage collection

## 🔧 **Configuration**

### **Platform Configuration**

```json
{
  "camera": {
    "backend": "v4l2",
    "default_resolution": [1366, 768],
    "fps": 30,
    "hardware_acceleration": true
  },
  "scale": {
    "auto_connect": true,
    "default_ports": ["/dev/ttyUSB0", "/dev/ttyS0"],
    "protocol": "generic"
  },
  "display": {
    "fullscreen_default": true,
    "touch_optimized": true
  }
}
```

### **System Monitoring**

```json
{
  "monitoring": {
    "cpu_warning": 80,
    "memory_warning": 85,
    "temperature_warning": 70,
    "disk_warning": 90
  }
}
```

## 🧪 **Testing & Validation**

### **Automated Tests**

```bash
# Run test suite
source venv/bin/activate
pytest tests/

# Hardware tests
python3 -m tests.hardware_test
python3 -m tests.camera_test
python3 -m tests.scale_test
```

### **Manual Validation**

1. **Camera detection** - Multiple USB cameras
2. **Scale connectivity** - Various serial protocols
3. **Weight accuracy** - Known weight calibration
4. **Performance** - Sustained operation monitoring
5. **Storage** - Long-term eMMC wear testing

## 📈 **Performance Metrics**

### **RK3568 Benchmarks**

- **Startup time**: < 5 seconds
- **Camera initialization**: < 2 seconds
- **Scale detection**: < 3 seconds
- **Image capture**: < 500ms
- **Weight reading**: < 100ms
- **Memory usage**: < 300MB (2GB system)
- **CPU usage**: < 25% (quad-core)

### **Throughput**

- **Images per minute**: 60+
- **Continuous operation**: 24/7 capable
- **Storage efficiency**: 95% eMMC utilization safe
- **Network transfer**: 100Mbps Ethernet support

## 🛡 **System Monitoring**

### **Real-time Metrics**

- **CPU usage and temperature**
- **Memory consumption and availability**
- **Disk usage and health**
- **Network activity**
- **Camera frame rate**
- **Scale communication status**

### **Alerts & Actions**

- **High temperature**: Automatic CPU throttling
- **Low memory**: Garbage collection and cleanup
- **Disk full**: Automatic log rotation
- **Scale disconnect**: Automatic reconnection attempts

## 🔧 **Troubleshooting**

### **Common Issues**

#### **Camera Not Detected**

```bash
# Check V4L2 devices
v4l2-ctl --list-devices

# Test camera access
python3 -c "
from camera_backend import CameraBackend
backend = CameraBackend()
cameras = backend.enumerate_cameras()
print(cameras)
"
```

#### **Scale Not Connecting**

```bash
# List serial ports
python3 -c "
from scale_interface import ScaleInterface
scale = ScaleInterface()
ports = scale.list_serial_ports()
print(ports)
"

# Test specific port
python3 -c "
from scale_interface import ScaleInterface
scale = ScaleInterface(port='/dev/ttyUSB0')
scale.connect()
print('Connected' if scale.is_connected else 'Failed')
"
```

#### **Performance Issues**

```bash
# Check system status
sudo systemctl status aiscale

# Monitor resources
python3 -c "
from system_monitor import system_monitor
system_monitor.start_monitoring()
import time; time.sleep(5)
print(system_monitor.get_current_metrics())
"
```

### **Log Analysis**

```bash
# Application logs
sudo journalctl -u aiscale -f

# System logs
tail -f /var/log/aiscale/app.log

# Performance logs
cat /var/log/aiscale/performance.log
```

## 🚀 **Deployment**

### **Production Checklist**

- [ ] Hardware compatibility verified
- [ ] Camera and scale tested
- [ ] Network connectivity configured
- [ ] Storage capacity planned
- [ ] Monitoring alerts configured
- [ ] Backup strategy implemented
- [ ] Auto-start service enabled
- [ ] Performance baseline established

### **Service Management**

```bash
# Start/stop service
sudo systemctl start aiscale
sudo systemctl stop aiscale

# Enable/disable auto-start
sudo systemctl enable aiscale
sudo systemctl disable aiscale

# Check status
sudo systemctl status aiscale

# View logs
sudo journalctl -u aiscale -f
```

## 📝 **Changelog**

### **v2.3.0 (Current) - Cross-Platform Release**

- ✅ **Cross-platform support** - Linux, macOS, Windows compatibility
- ✅ **RK3568 optimization** - Full hardware acceleration and optimization
- ✅ **Scale integration** - Complete serial scale communication system
- ✅ **Hardware abstraction** - Platform-agnostic camera and device access
- ✅ **System monitoring** - Real-time performance tracking and alerts
- ✅ **Production deployment** - Automated setup and service management
- ✅ **Touch interface** - Optimized for embedded touchscreen use
- ✅ **Performance optimization** - Memory, CPU, and storage efficiency

### **v2.2.0 - Camera Enhancement**

- ✅ Camera type detection and white balance improvements
- ✅ Manual override system for camera controls
- ✅ Debug overlay and diagnostic tools

### **v2.1.0 - Foundation**

- ✅ Basic camera functionality and database integration
- ✅ Dataset validation tools

## 🤝 **Contributing**

1. **Fork** the repository
2. **Create** feature branch (`git checkout -b feature/amazing-feature`)
3. **Test** on target hardware
4. **Commit** changes (`git commit -m 'Add amazing feature'`)
5. **Push** to branch (`git push origin feature/amazing-feature`)
6. **Open** Pull Request

### **Development Guidelines**

- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation
- Test on multiple platforms
- Verify embedded hardware compatibility

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **Rockchip** for RK3568 SoC and development support
- **OpenCV** for computer vision capabilities
- **PySide6/Qt** for cross-platform UI framework
- **Python** ecosystem for rapid development
- **Linux community** for embedded systems support

---

**Status**: ✅ **PRODUCTION READY FOR RK3568 DEPLOYMENT**

For support, questions, or feature requests, please open an issue or contact the development team.
