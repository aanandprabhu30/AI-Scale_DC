#!/bin/bash

# AI-Scale Data Collector Launcher
# Cross-platform startup script with optimization detection

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 AI-Scale Data Collector v2.3.0${NC}"
echo "======================================"

# Check if virtual environment exists
if [[ ! -d "venv" ]]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    echo "Please run setup first: ./setup_dev.sh"
    exit 1
fi

# Activate virtual environment
echo -e "${GREEN}📦 Activating virtual environment...${NC}"
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# Check Python dependencies
echo -e "${GREEN}🔍 Checking dependencies...${NC}"
if ! python3 -c "
import cv2, numpy, serial, psutil
from PySide6.QtWidgets import QApplication
print('✅ Core dependencies available')
" 2>/dev/null; then
    echo -e "${RED}❌ Missing dependencies${NC}"
    echo "Please run: pip install -r requirements.txt"
    exit 1
fi

# Platform detection
echo -e "${GREEN}🖥️  Detecting platform...${NC}"
python3 -c "
from platform_config import platform_config
print(f'Platform: {platform_config.platform}')
print(f'Architecture: {platform_config.machine}')
if platform_config.is_rk3568:
    print('🎯 RK3568 optimizations enabled')
elif platform_config.is_arm:
    print('💪 ARM optimizations enabled')
else:
    print('🖥️  Generic platform configuration')
"

# Hardware check
echo -e "${GREEN}🔧 Checking hardware...${NC}"
python3 -c "
from camera_backend import CameraBackend
from hardware_acceleration import hardware_accelerator

# Check cameras
backend = CameraBackend()
cameras = backend.enumerate_cameras()
print(f'📷 Found {len(cameras)} camera(s)')

# Check acceleration
info = hardware_accelerator.get_acceleration_info()
if info['gpu_available']:
    print('🚀 GPU acceleration available')
if info['opencl_available']:
    print('⚡ OpenCL acceleration available')
if info['is_rk3568'] and info['npu_available']:
    print('🧠 NPU acceleration available')
"

# Scale detection
echo -e "${GREEN}⚖️  Checking for scales...${NC}"
python3 -c "
from scale_interface import ScaleInterface
scale = ScaleInterface()
ports = scale.list_serial_ports()
if ports:
    print(f'📊 Found {len(ports)} potential scale port(s)')
    for port in ports[:3]:  # Show first 3
        print(f'   - {port[\"device\"]}: {port[\"description\"]}')
else:
    print('📊 No scale ports detected')
" 2>/dev/null || echo "📊 Scale detection unavailable"

# Environment setup
echo -e "${GREEN}🌍 Setting up environment...${NC}"

# Set Qt platform variables
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_SCALE_FACTOR_ROUNDING_POLICY=RoundPreferFloor

# Platform-specific environment
case "$(uname -s)" in
    Linux*)
        export QT_QPA_PLATFORM=xcb
        # Check if we're on RK3568
        if grep -q "rk3568\|rockchip" /proc/cpuinfo 2>/dev/null; then
            export DISPLAY=${DISPLAY:-:0}
            export QT_QPA_PLATFORM_PLUGIN_PATH=""
            # Enable hardware acceleration
            export GST_VAAPI_ALL_DRIVERS=1
            export LIBVA_DRIVER_NAME=rockchip
            echo "🎯 RK3568 environment configured"
        fi
        ;;
    Darwin*)
        export QT_QPA_PLATFORM=cocoa
        echo "🍎 macOS environment configured"
        ;;
    CYGWIN*|MINGW*|MSYS*)
        export QT_QPA_PLATFORM=windows
        echo "🪟 Windows environment configured"
        ;;
esac

# Check display availability
if [[ -n "$DISPLAY" ]] || [[ "$(uname -s)" == "Darwin" ]] || [[ "$(uname -s)" =~ ^(CYGWIN|MINGW|MSYS) ]]; then
    echo -e "${GREEN}🖼️  Display available${NC}"
else
    echo -e "${YELLOW}⚠️  No display detected - running in headless mode${NC}"
fi

# Performance optimization
echo -e "${GREEN}⚡ Applying optimizations...${NC}"
python3 -c "
from hardware_acceleration import hardware_accelerator
hardware_accelerator.enable_optimizations()
print('✅ Hardware optimizations enabled')
" 2>/dev/null || echo "⚠️  Hardware optimizations unavailable"

# Start monitoring if enabled
python3 -c "
from platform_config import platform_config
from system_monitor import system_monitor
if platform_config.get('monitoring.enabled', True):
    system_monitor.start_monitoring()
    print('📊 System monitoring started')
" 2>/dev/null || echo "📊 System monitoring unavailable"

# Launch application
echo -e "${GREEN}🚀 Starting AI-Scale Data Collector...${NC}"
echo ""

# Handle different startup scenarios
if [[ "$1" == "--debug" ]]; then
    echo -e "${YELLOW}🐛 Debug mode enabled${NC}"
    export AISCALE_DEBUG=1
    python3 -u AIScaleDataCollector.py "$@"
elif [[ "$1" == "--test" ]]; then
    echo -e "${YELLOW}🧪 Test mode - basic functionality check${NC}"
    python3 -c "
import sys
from AIScaleDataCollector import AIScaleDataCollector
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
window = AIScaleDataCollector()
print('✅ Application initialized successfully')
app.quit()
"
elif [[ "$1" == "--info" ]]; then
    echo -e "${BLUE}ℹ️  System Information${NC}"
    python3 -c "
from platform_config import platform_config
from hardware_acceleration import hardware_accelerator
from display_manager import display_manager
import json

info = {
    'platform': platform_config.get_system_info(),
    'hardware': hardware_accelerator.get_acceleration_info(),
    'display': display_manager.get_display_info()
}

print(json.dumps(info, indent=2, default=str))
"
else
    # Normal startup
    exec python3 AIScaleDataCollector.py "$@"
fi