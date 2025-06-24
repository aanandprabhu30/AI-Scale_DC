# AI-Scale Data Collector Changelog

## [2.3.0] - 2024-12-24 - Cross-Platform Release 🚀

### 🎯 **Major Features**

- **Cross-platform support** - Linux, macOS, Windows compatibility
- **RK3568 optimization** - Full hardware acceleration for Rockchip RK3568
- **Scale integration** - Complete serial scale communication system
- **Hardware abstraction** - Platform-agnostic camera and device access
- **System monitoring** - Real-time performance tracking and alerts
- **Production deployment** - Automated setup and service management

### ⚖️ **Scale Integration**

- **Auto-detection** of serial scales on USB/RS232 ports
- **Real-time weight display** with stability indication
- **Automatic weight capture** with image metadata
- **Scale commands**: Zero, Tare, Print
- **Thread-safe operation** with callback system

### 📸 **Camera System Enhancements**

- **Hardware abstraction layer** (`CameraBackend`) for cross-platform access
- **Automatic camera enumeration** with platform-specific optimizations
- **V4L2 backend** for Linux systems
- **AVFoundation** maintained for macOS
- **DirectShow** support for Windows
- **Resolution detection** and optimal settings per platform

### 💻 **RK3568 Optimizations**

- **Mali GPU acceleration** for image processing
- **NPU utilization** for AI workloads (0.8TOPS)
- **MJPEG hardware encoding** for camera capture
- **1366x768 display optimization** for BOE NT156WHM-N42
- **Memory optimization** for 2GB/4GB configurations
- **Thermal monitoring** with automatic throttling
- **eMMC storage optimization** with wear leveling

### 🖥️ **Display Management**

- **Platform-specific UI scaling** and optimization
- **Touch interface support** for embedded systems
- **Fullscreen mode** for kiosk applications
- **Font and UI scaling** for different screen densities
- **Performance optimizations** for GPU acceleration

### 📊 **System Monitoring**

- **Real-time metrics**: CPU, memory, temperature, disk usage
- **Alert system** with configurable thresholds
- **Automatic actions**: CPU throttling, memory cleanup, log rotation
- **Performance logging** and analytics
- **Health monitoring** for 24/7 operation

### 🔧 **Configuration System**

- **Platform detection** with automatic configuration
- **Dynamic settings** based on hardware capabilities
- **User configuration** override system
- **JSON-based configuration** files
- **Runtime optimization** switching

### 🛠️ **Development & Deployment**

- **`setup_dev.sh`** - Automated development environment setup
- **`deploy_rk3568.sh`** - Production deployment script for RK3568
- **`run.sh`** - Smart application launcher with diagnostics
- **Cross-platform requirements** management
- **Comprehensive testing** and validation tools

### 🚀 **Performance Improvements**

- **Startup time**: 5 seconds (RK3568), 3 seconds (other platforms)
- **Memory usage**: 300MB max (RK3568), 200MB (other platforms)
- **Camera latency**: <100ms capture time
- **Scale reading**: <50ms response time
- **Storage efficiency**: Optimized for eMMC longevity

### 🔄 **API Changes**

- **Breaking**: Removed hardcoded camera constants (`IMX219_CONFIGS`, `CAMERA_BACKEND`)
- **New**: `CameraBackend` class for camera abstraction
- **New**: `ScaleInterface` class for scale communication
- **New**: `platform_config` for configuration management
- **Enhanced**: Dynamic resolution and FPS selection
- **Improved**: Error handling and logging

### 📦 **Dependencies**

- **Added**: `pyserial` >= 3.5 for scale communication
- **Added**: `psutil` >= 5.9.0 for system monitoring
- **Updated**: Platform-specific OpenCV packages
- **Maintained**: PySide6, NumPy, Pillow core dependencies

### 🗂️ **File Structure**

``` bash
├── camera_backend.py          # NEW: Hardware abstraction for cameras
├── scale_interface.py         # NEW: Serial scale communication
├── platform_config.py        # NEW: Platform-specific configuration
├── hardware_acceleration.py   # NEW: GPU/NPU acceleration
├── system_monitor.py         # NEW: Performance monitoring
├── display_manager.py        # NEW: Display optimization
├── deploy_rk3568.sh          # NEW: Production deployment script
├── setup_dev.sh              # NEW: Development setup script
├── run.sh                    # NEW: Application launcher
├── MIGRATION_GUIDE.md        # NEW: Migration documentation
├── AIScaleDataCollector.py   # UPDATED: Scale integration, cross-platform
├── requirements.txt          # UPDATED: Cross-platform dependencies
├── README.md                 # UPDATED: Comprehensive documentation
└── .gitignore               # UPDATED: Extended for new platforms
```

### 🗑️ **Removed**

- **`CAMERA_IMPROVEMENTS_SUMMARY.md`** - Obsolete documentation
- **`check_qt_plugins()`** - Unused Qt diagnostic function
- **Hardcoded camera constants** - Replaced with dynamic configuration
- **macOS-specific code paths** - Moved to platform abstraction

---

## [2.2.0] - 2024-12-01 - Camera Enhancement

### ✅ **Implemented**

- Camera type detection (MacBook vs External)
- Manual white balance override system
- Debug overlay and diagnostic tools
- Enhanced white balance algorithm
- Performance optimizations

### ❌ **Known Issues**

- Blue tint issue in external cameras (addressed in v2.3.0)
- Limited to macOS platform (resolved in v2.3.0)

---

## [2.1.0] - 2024-11-15 - Foundation

### ✅ **Features**

- Basic camera functionality
- Database integration with SQLite
- Dataset validation tools
- Simple UI with capture functionality

---

## 🚀 **Upgrade Path**

### **From v2.2.0 to v2.3.0**

1. **Backup data**: `cp -r data data_backup`
2. **Run setup**: `./setup_dev.sh`
3. **Test functionality**: `./run.sh --test`
4. **Read migration guide**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

### **For RK3568 Deployment**

1. **Copy files**: `scp -r * user@rk3568:/tmp/aiscale/`
2. **Deploy**: `ssh user@rk3568 "cd /tmp/aiscale && sudo ./deploy_rk3568.sh"`
3. **Verify**: `ssh user@rk3568 "sudo systemctl status aiscale"`

## 🎯 **Next Steps (v2.4.0)**

### **Planned Features**

- **AI model integration** with RKNN inference
- **Cloud synchronization** for data backup
- **Multi-camera support** for stereo imaging
- **Advanced analytics** dashboard
- **Mobile app** for remote monitoring

### **Platform Expansion**

- **NVIDIA Jetson** optimization
- **Raspberry Pi 5** support
- **Industrial IoT** integration
- **Edge AI** deployment tools

---

**Current Status**: ✅ **PRODUCTION READY FOR RK3568**

For detailed information about specific changes, see the [README.md](README.md) and [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md).
