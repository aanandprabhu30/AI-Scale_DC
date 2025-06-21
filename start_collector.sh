#!/bin/bash

echo "🍎 Starting AI-Scale Data Collector"
echo "=================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if camera is accessible
echo "📷 Checking camera access..."
python3 -c "
import cv2
camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
if camera.isOpened():
    print('✅ Camera ready')
    camera.release()
else:
    print('❌ Camera not accessible')
    print('Please check:')
    print('  1. Arducam is connected')
    print('  2. Camera permissions granted')
    print('  3. No other app using camera')
    exit(1)
"

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""
echo "🚀 Launching Data Collector..."
echo "Keyboard shortcuts:"
echo "  Space - Capture image"
echo "  Ctrl+N - New class"
echo "  Ctrl+O - Change path"
echo "  Ctrl+Q - Quit"
echo ""

# Run the data collector
python AIScaleDataCollector.py 