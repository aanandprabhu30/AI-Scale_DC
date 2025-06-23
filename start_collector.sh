#!/bin/bash

echo "🍎 Starting AI-Scale Data Collector v2.2.0"
echo "=========================================="
echo "Status: Camera improvements implemented, blue tint issue pending resolution"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# Check if main application exists
if [ ! -f "AIScaleDataCollector.py" ]; then
    echo "❌ AIScaleDataCollector.py not found. Please ensure you're in the correct directory."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if required packages are installed, specifically PySide6
python3 -c "import PySide6" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Please run ./setup.sh again."
    exit 1
fi

echo ""
echo "🚀 Launching Data Collector..."
echo "Press Ctrl+C in this terminal to close the application."
echo ""
echo "💡 Tips:"
echo "  - Use Cmd+D to toggle debug overlay"
echo "  - Use Ctrl+M for manual white balance override"
echo "  - Use Ctrl+E for extreme blue fix"
echo ""

# Run the data collector
python3 AIScaleDataCollector.py 