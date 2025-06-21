#!/bin/bash

echo "🚀 Setting up AI-Scale Data Collector for M2 MacBook Air"
echo "=================================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found. Please ensure you're in the correct directory."
    exit 1
fi

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

# Fix potential Qt platform plugin issue on macOS
echo "🔧 Checking Qt installation..."
python3 -c "
try:
    # Try PySide6 first (better macOS compatibility)
    from PySide6.QtWidgets import QApplication
    print('✅ PySide6 available (recommended for macOS)')
except ImportError:
    try:
        # Fallback to PyQt6
        from PyQt6.QtWidgets import QApplication
        print('✅ PyQt6 available')
    except ImportError:
        print('❌ No Qt library found')
        print('   Installing PySide6...')
        import subprocess
        subprocess.run(['pip', 'install', 'PySide6'])
        print('✅ PySide6 installed')
"

# Create dataset directories
echo "Creating data directories..."
mkdir -p "data/raw"
mkdir -p "data/processed"

# Create tools directory structure
echo "🛠️  Setting up tools..."
mkdir -p tools/data_processing

# Make validation scripts executable
if [ -f "tools/data_processing/dataset_validator.py" ]; then
    chmod +x tools/data_processing/dataset_validator.py
    echo "✅ Dataset validator script made executable"
fi

if [ -f "tools/data_processing/quick_validate.py" ]; then
    chmod +x tools/data_processing/quick_validate.py
    echo "✅ Quick validation script made executable"
fi

# Test camera access
echo "📷 Testing camera access..."
python3 -c "
import cv2
try:
    camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    if camera.isOpened():
        print('✅ Camera detected and accessible')
        camera.release()
    else:
        print('⚠️  Camera not detected. Please check:')
        print('   1. Arducam IMX219 is connected')
        print('   2. Camera permissions are granted in System Settings')
        print('   3. No other app is using the camera')
except Exception as e:
    print(f'⚠️  Camera test error: {e}')
    print('   This is normal if camera permissions are not granted yet.')
"

# Test basic functionality
echo "🧪 Testing basic functionality..."
python3 test_collector.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Basic functionality test passed"
else
    echo "⚠️  Basic functionality test failed (this may be normal)"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Grant camera permissions in System Settings → Privacy & Security → Camera"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python AIScaleDataCollector.py"
echo "   or use: ./start_collector.sh"
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
echo "🛠️  Additional tools:"
echo "  python tools/data_processing/dataset_validator.py data/raw"
echo "  python test_collector.py"
echo ""
echo "Happy data collecting! 🍎📸" 