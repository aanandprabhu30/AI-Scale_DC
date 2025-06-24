# AI-Scale Data Collector v2.4.0

Clean, production-ready produce image capture and weighing system optimized for RK3568 embedded boards.

## Key Features

- **🎯 Visual Enhancement**: Fixes bluish haze, brightness/contrast imbalance, and color accuracy issues
- **📱 Optimized UI**: Clean interface designed for 1366×768 displays with 6-bit color optimization
- **🎛️ Real-time Controls**: Live adjustments for brightness, contrast, white balance, gamma, saturation, vibrance
- **📸 Professional Capture**: Full-resolution images with timestamped filenames and metadata
- **⚡ Hardware Optimized**: Efficient performance on RK3568 (4GB RAM, 32GB eMMC)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python run_ai_scale.py
```

## Hardware Requirements

- **Board**: Rockchip RK3568 (SV3c-MPOS35687B or compatible)
- **Display**: 15.6" BOE eDP (1366×768, 6-bit color, 45% gamut)
- **Camera**: Arducam USB with Sony IMX219 sensor (8MP, MJPEG/YUY2)
- **Scale**: USB/RS232 compatible scales (auto-detected)

## Real-time Image Processing

The application addresses common visual issues through advanced image processing:

- **White Balance Correction**: Reduces bluish haze using LAB color space adjustments
- **Gamma Correction**: Fixes brightness/contrast imbalance for better visibility
- **Color Enhancement**: Improves accuracy of reds, greens, and yellows
- **CLAHE**: Local contrast enhancement for better detail preservation
- **Vibrance Control**: Selective saturation boost for natural-looking colors

## File Structure

```bash
AI-Scale/
├── ai_scale_ui.py             # Main application UI
├── run_ai_scale.py           # Application launcher
├── camera_backend.py         # Camera abstraction layer
├── scale_interface.py        # Scale communication interface
├── requirements.txt         # Python dependencies
├── config.json             # Persistent settings
└── data/
    └── captures/           # Captured images and metadata
```

## Usage

1. **Connect Hardware**: Plug in your Arducam USB camera and scale
2. **Launch Application**: Run `python run_ai_scale.py`
3. **Select Camera**: Choose your camera from the dropdown
4. **Adjust Settings**: Use real-time controls to fix visual issues:
   - **Brightness**: Adjust overall brightness (-50 to +50)
   - **Contrast**: Modify contrast ratio (0.5 to 2.0)
   - **Gamma**: Improve brightness balance (0.5 to 2.0)
   - **White Balance**: Reduce bluish cast (-10 to +10)
   - **Saturation**: Enhance color accuracy (0.5 to 2.0)
   - **Vibrance**: Boost muted colors naturally (0.0 to 1.0)
   - **CLAHE**: Enable local contrast enhancement
5. **Capture Images**: Click "Capture Image" to save at full resolution

## Captured Data

Each capture creates:

- **Image**: `capture_YYYYMMDD_HHMMSS.jpg` (full resolution, 95% quality)
- **Metadata**: `capture_YYYYMMDD_HHMMSS.json` with settings and scale reading

The application uses JSON files for metadata storage instead of a database for simplicity and portability.

## Display Optimization

The UI is specifically optimized for your hardware:

- **Layout**: 1366×768 with efficient space usage
- **Colors**: Carefully chosen for 6-bit displays and 45% gamut
- **Performance**: 30 FPS real-time preview with minimal CPU usage
- **Theme**: Dark theme optimized for embedded display characteristics

## Configuration

Settings are automatically saved to `config.json`:

```json
{
  "_version": "2.4.0",
  "_status": "Production ready for RK3568 deployment",
  "_last_updated": "24 June 2025",
  "last_camera_index": 1,
  "window_geometry": "...",
  "save_options": {
    "create_preview": false,
    "quality": 95
  },
  "camera_controls": {
    "brightness": 0,
    "contrast": 1.0,
    "gamma": 1.0,
    "white_balance": 0.0,
    "saturation": 1.0,
    "vibrance": 0.0,
    "clahe_enabled": false
  }
}
```

## Dependencies

Core dependencies (see `requirements.txt` for full list):

- **PySide6>=6.5.0**: Modern Qt-based GUI framework
- **opencv-python>=4.8.0**: Computer vision and image processing
- **numpy>=1.24.0**: Numerical computing
- **pyserial>=3.5**: Serial communication for scale integration
- **psutil>=5.9.0**: System monitoring and performance

## Troubleshooting

**Camera Issues:**

```bash
# List available cameras
v4l2-ctl --list-devices

# Check camera permissions
ls -l /dev/video*
```

**Scale Connection:**

```bash
# Test scale interface
python3 -c "from scale_interface import ScaleInterface; print(ScaleInterface().list_serial_ports())"
```

**Display Issues:**

- Ensure display is set to 1366×768 native resolution
- Check HDMI/eDP connection is secure
- Verify graphics drivers are installed

## Development

Test the components:

```bash
# Test camera backend
python3 -c "from camera_backend import CameraBackend; cb = CameraBackend(); print(cb.enumerate_cameras())"

# Test scale interface
python3 -c "from scale_interface import ScaleInterface; si = ScaleInterface(); print(si.list_serial_ports())"
```

## Legacy Support

The original `AIScaleDataCollector.py` is preserved for compatibility but the new `ai_scale_ui.py` is recommended for production use.
