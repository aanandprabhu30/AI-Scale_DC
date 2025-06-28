# AI-Scale Data Collector v2.4.0

Production-ready produce image capture and weighing system optimized for RK3568 embedded boards.

## 🚀 Quick Start

### For Development (x86_64)

```bash
pip install -r requirements.txt
python run_ai_scale.py
```

### For RK3568 Deployment

```bash
./deploy_rk3568.sh
```

## 🎯 Key Features

- **Real-time Image Processing**: Fixes bluish haze, brightness/contrast issues
- **Smart Camera Detection**: Auto-detects camera models via USB VID/PID
- **Camera Profiles**: Optimized settings for Arducam B0196 and JSK-S8130-V3.0
- **Adaptive Image Processing**: Camera-specific color correction and enhancement
- **Scale Integration**: USB/RS232 scale communication with auto-detection
- **Hardware Optimized**: RK3568-specific optimizations for 1366×768 displays
- **Settings Persistence**: Automatic save/load of user preferences

## 📋 Hardware Requirements

- **Board**: Rockchip RK3568 (SV3c-MPOS35687B or compatible)
- **Display**: 15.6" BOE eDP (1366×768, 6-bit color)
- **Scale**: USB/RS232 compatible scales (auto-detected)

### Supported Cameras

1. **Arducam 8MP 1080P USB Camera Module (B0196)**
   - Sensor: 1/4" CMOS IMX219
   - Max Resolution: 3280×2464 (8MP)
   - USB VID/PID: 0x0bda:0x5830
   - Features: Fixed focus, no IR filter, wide dynamic range

2. **JSK-S8130-V3.0 Camera Module**
   - Sensor: 1/2.5" CMOS OV5648
   - Max Resolution: 2592×1944 (5MP)
   - USB VID/PID: 0x1bcf:0x2c99
   - Features: Auto focus, built-in IR filter, optimized for daylight

3. **Generic USB Cameras**
   - Automatic fallback for any USB camera
   - Standard resolution support up to 1080p

## 🛠️ Installation

### x86_64 Systems

```bash
pip install -r requirements.txt
```

### ARM64 (RK3568) Systems

```bash
# System packages
sudo apt-get install python3-opencv python3-pyqt5 python3-numpy python3-serial python3-pil v4l-utils

# Python packages
pip3 install psutil pytest pytest-qt
```

## 📁 Project Structure

``` bash
AI-Scale/
├── ai_scale_ui.py             # Main application UI
├── run_ai_scale.py           # Application launcher
├── camera_backend.py         # Camera abstraction layer
├── scale_interface.py        # Scale communication interface
├── deploy_rk3568.sh         # RK3568 deployment script
├── requirements.txt         # Python dependencies
├── config.json             # Persistent settings
└── data/
    └── captures/           # Captured images and metadata
```

## 🎮 Usage

1. **Connect Hardware**: Plug in camera and scale
2. **Launch**: Run `python run_ai_scale.py`
3. **Select Camera**: Choose from dropdown or click "Refresh"
4. **Adjust Settings**: Use real-time controls:
   - **Brightness**: -50 to +50
   - **Contrast**: 0.5 to 2.0
   - **Gamma**: 0.5 to 2.0
   - **White Balance**: -10 to +10
   - **Saturation**: 0.5 to 2.0
   - **Vibrance**: 0.0 to 1.0
   - **CLAHE**: Enable local contrast enhancement
5. **Capture**: Click "Capture Image" for full-resolution photos

## 📸 Captured Data

Each capture creates:

- **Image**: `capture_YYYYMMDD_HHMMSS.jpg` (95% quality)
- **Metadata**: `capture_YYYYMMDD_HHMMSS.json` with settings and scale reading

## 🔧 RK3568 Optimizations

- **6-bit Color Display**: Automatic color depth reduction
- **ARM64 Compatibility**: PyQt5 fallback for better support
- **MJPEG Format**: Optimized camera format for performance
- **Memory Efficient**: Designed for 4GB RAM systems
- **Display Optimized**: UI designed for 1366×768 resolution

## 🐛 Troubleshooting

### Camera Issues

```bash
v4l2-ctl --list-devices
ls -l /dev/video*
```

### Scale Issues

```bash
python3 -c "from scale_interface import ScaleInterface; print(ScaleInterface().list_serial_ports())"
```

### RK3568 Specific

```bash
# OpenCV issues
sudo apt-get install python3-opencv

# PySide6 compatibility
sudo apt-get install python3-pyqt5

# Performance check
cat /proc/cpuinfo | grep -i rockchip
free -h
```

## 🧪 Development

Test components:

```bash
# Camera backend
python3 -c "from camera_backend import CameraBackend; print(CameraBackend().enumerate_cameras())"

# Scale interface
python3 -c "from scale_interface import ScaleInterface; print(ScaleInterface().list_serial_ports())"
```

## 📄 Configuration

Settings are saved to `config.json`:

```json
{
  "_version": "2.4.0",
  "camera_controls": {
    "brightness": 0.0,
    "contrast": 1.0,
    "gamma": 1.0,
    "white_balance": 0.0,
    "saturation": 1.0,
    "vibrance": 0.0,
    "clahe_enabled": false
  }
}
```

---

**Ready for production deployment on RK3568 hardware!** 🚀
