#!/bin/bash

echo "🚀 Setting up AI-Scale Data Collector for M2 MacBook Air"
echo "=================================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create dataset directory
echo "📁 Creating dataset directory..."
mkdir -p data/raw

# Test camera access
echo "📷 Testing camera access..."
python3 -c "
import cv2
camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
if camera.isOpened():
    print('✅ Camera detected and accessible')
    camera.release()
else:
    print('⚠️  Camera not detected. Please check:')
    print('   1. Arducam IMX219 is connected')
    print('   2. Camera permissions are granted in System Settings')
    print('   3. No other app is using the camera')
"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Grant camera permissions in System Settings → Privacy & Security → Camera"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python AIScaleDataCollector.py"
echo ""
echo "Keyboard shortcuts:"
echo "  Space - Capture image"
echo "  Ctrl+N - Focus on new class input"
echo "  Ctrl+O - Change dataset path"
echo "  Ctrl+Q - Quit application"
echo ""
echo "Happy data collecting! 🍎📸" 