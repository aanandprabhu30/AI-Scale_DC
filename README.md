# AI-Scale Data Collector

Cross-platform produce image capture and weighing system for RK3568 and other platforms.

## Quick Start

```bash
# Setup
./scripts/setup_dev.sh

# Run
./scripts/run.sh

# Deploy to RK3568
sudo ./scripts/deploy_rk3568.sh
```

## Features

- **Camera**: Cross-platform support (Linux V4L2, macOS AVFoundation, Windows DirectShow)
- **Scale**: Auto-detection of USB/RS232 scales with multi-protocol support
- **Hardware**: RK3568 optimization with Mali GPU and NPU acceleration
- **UI**: Touch-optimized interface for embedded use

## Hardware Support

- **Primary**: Rockchip RK3568 (1366x768 display, 2GB/4GB RAM)
- **Alternative**: Linux ARM/x86, macOS, Windows

## Usage

1. Connect scale (auto-detected)
2. Select camera (auto-detected)
3. Choose produce type
4. Capture images (weight automatically recorded)

**Shortcuts:**

- Space: Capture image
- Ctrl+Q: Quit
- F11: Fullscreen
- Ctrl+D: Debug info

## File Structure

``` bash
AI-Scale/
├── AIScaleDataCollector.py    # Main application
├── camera_backend.py          # Camera abstraction
├── scale_interface.py         # Scale communication
├── platform_config.py        # Platform detection
├── hardware_acceleration.py  # GPU/NPU acceleration
├── system_monitor.py         # Performance monitoring
├── display_manager.py        # Display optimization
├── scripts/                  # Shell scripts
│   ├── setup_dev.sh         # Development setup
│   ├── run.sh               # Application launcher
│   └── deploy_rk3568.sh     # Production deployment
├── requirements.txt          # Dependencies
├── config.json              # User settings
└── data/                    # Captured images & metadata
```

## Configuration

```json
{
  "camera": {
    "backend": "v4l2",
    "default_resolution": [1366, 768],
    "fps": 30
  },
  "scale": {
    "auto_connect": true,
    "default_ports": ["/dev/ttyUSB0", "/dev/ttyS0"]
  }
}
```

## Troubleshooting

**Camera not detected:**

```bash
v4l2-ctl --list-devices
```

**Scale not connecting:**

```bash
python3 -c "from scale_interface import ScaleInterface; print(ScaleInterface().list_serial_ports())"
```

**Performance issues:**

```bash
./scripts/run.sh --info
```

## Development

```bash
# Test mode
./scripts/run.sh --test

# Debug mode
./scripts/run.sh --debug

# System info
./scripts/run.sh --info
```

## Service Management (RK3568)

```bash
sudo systemctl start aiscale
sudo systemctl stop aiscale
sudo systemctl status aiscale
sudo journalctl -u aiscale -f
```
