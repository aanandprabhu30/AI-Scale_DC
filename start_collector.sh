#!/bin/bash

echo "🍎 Starting AI-Scale Data Collector"
echo "=================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

# Check if main application exists
if [ ! -f "AIScaleDataCollector.py" ]; then
    echo "❌ AIScaleDataCollector.py not found. Please ensure you're in the correct directory."
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if required packages are installed
echo "📦 Checking dependencies..."
python3 -c "import cv2, numpy, PyQt6" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Run ./setup.sh to install them."
    exit 1
fi

# Check if camera is accessible
echo "📷 Checking camera access..."
python3 -c "
import cv2
try:
    camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    if camera.isOpened():
        print('✅ Camera ready')
        camera.release()
    else:
        print('❌ Camera not accessible')
        print('Please check:')
        print('  1. Arducam IMX219 is connected')
        print('  2. Camera permissions granted in System Settings')
        print('  3. No other app using camera')
        exit(1)
except Exception as e:
    print(f'❌ Camera access error: {e}')
    print('Please check camera permissions in System Settings')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "1. Open System Settings → Privacy & Security → Camera"
    echo "2. Enable camera access for Terminal/Cursor"
    echo "3. Restart Terminal/Cursor and try again"
    echo ""
    exit 1
fi

# Check dataset directory
if [ ! -d "data/raw" ]; then
    echo "📁 Creating dataset directory..."
    mkdir -p data/raw
fi

echo ""
echo "🚀 Launching Data Collector..."
echo ""
echo "⌨️  Keyboard shortcuts:"
echo "  Space - Capture image"
echo "  Ctrl+N - Focus on new class input"
echo "  Ctrl+O - Change dataset path"
echo "  Ctrl+S - Update statistics"
echo "  Ctrl+G - Toggle grid overlay"
echo "  Ctrl+C - Toggle center guide"
echo "  Ctrl+Q - Quit application"
echo ""
echo "💡 Tips:"
echo "  • Use consistent lighting for best results"
echo "  • Capture multiple angles of each item"
echo "  • Enable grid overlay for composition"
echo "  • Use burst mode for quick captures"
echo ""

# Run the data collector
python AIScaleDataCollector.py 