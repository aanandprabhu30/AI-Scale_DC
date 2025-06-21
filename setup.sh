#!/bin/bash

echo "🚀 Setting up AI-Scale Data Collector v2.2"
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
echo "📦 Creating virtual environment in './venv'..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Create initial directory structure
echo "📁 Creating data directories ('data/raw') and database file..."
mkdir -p "data/raw"
# The application will create the database and config file automatically
# but we can touch the files to make them visible.
touch data/metadata.db
touch config.json

# Make helper scripts executable
echo "⚙️  Making helper scripts executable..."
chmod +x start_collector.sh
chmod +x tools/data_processing/quick_validate.py

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. If this is the first time, grant Camera Permissions for your Terminal app in:"
echo "   System Settings → Privacy & Security → Camera"
echo "2. To run the application, use the start script:"
echo "   ./start_collector.sh"
echo ""
echo "Happy data collecting! 🍎📸" 