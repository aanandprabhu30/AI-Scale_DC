#!/bin/bash
# AI-Scale Data Collector v2.4.0 - RK3568 Deployment Script
# Optimized for Rockchip RK3568 ARM64 systems

set -e  # Exit on any error

echo "🚀 AI-Scale Data Collector v2.4.0 - RK3568 Deployment"
echo "=================================================="

# Check if running on ARM64
if [ "$(uname -m)" != "aarch64" ]; then
    echo "⚠️  Warning: This script is optimized for ARM64 (RK3568) systems"
    echo "   Current architecture: $(uname -m)"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update package list
echo "📦 Updating package list..."
sudo apt-get update

# Install system dependencies for RK3568
echo "🔧 Installing system dependencies..."
sudo apt-get install -y \
    python3-opencv \
    python3-numpy \
    python3-serial \
    python3-pil \
    python3-pyqt5 \
    v4l-utils \
    python3-pip \
    python3-venv

# Install Python packages
echo "🐍 Installing Python packages..."
pip3 install psutil pytest pytest-qt

# Check camera hardware
echo "📷 Checking camera hardware..."
if command -v v4l2-ctl &> /dev/null; then
    echo "Available video devices:"
    v4l2-ctl --list-devices || echo "No video devices found"
else
    echo "⚠️  v4l2-utils not installed, cannot check cameras"
fi

# Create data directory
echo "📁 Creating data directories..."
mkdir -p data/captures
touch data/captures/.gitkeep

# Set permissions
echo "🔐 Setting permissions..."
chmod +x run_ai_scale.py
chmod +x ai_scale_ui.py

# Test OpenCV installation
echo "🧪 Testing OpenCV installation..."
python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" || {
    echo "❌ OpenCV installation failed"
    echo "Try: sudo apt-get install python3-opencv"
    exit 1
}

# Test PyQt5 installation
echo "🧪 Testing PyQt5 installation..."
python3 -c "from PyQt5.QtWidgets import QApplication; print('PyQt5 working')" || {
    echo "❌ PyQt5 installation failed"
    echo "Try: sudo apt-get install python3-pyqt5"
    exit 1
}

# Test camera backend
echo "🧪 Testing camera backend..."
python3 -c "
import sys
sys.path.insert(0, '.')
from camera_backend import CameraBackend
backend = CameraBackend()
cameras = backend.enumerate_cameras()
print(f'Found {len(cameras)} cameras')
" || echo "⚠️  Camera backend test failed (may be normal if no camera connected)"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Connect your Arducam USB camera"
echo "2. Run: python3 run_ai_scale.py"
echo "3. Test camera detection and image capture"
echo ""
echo "📋 Hardware checklist:"
echo "   ✅ RK3568 board (ARM64)"
echo "   ✅ 1366×768 display"
echo "   ✅ Arducam USB camera (IMX219)"
echo "   ✅ USB scale (optional)"
echo ""
echo "🔧 Troubleshooting:"
echo "   - Camera issues: v4l2-ctl --list-devices"
echo "   - Performance: Check /proc/cpuinfo for RK3568"
echo "   - Display: Ensure 1366×768 resolution"
echo ""
echo "🚀 Ready for production use on RK3568!" 