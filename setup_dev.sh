#!/bin/bash

# AI-Scale Development Environment Setup
# Cross-platform setup script for development

set -e

echo "🛠️  AI-Scale Development Environment Setup"
echo "=========================================="

# Detect platform
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    PLATFORM="windows"
else
    PLATFORM="unknown"
fi

echo "Detected platform: $PLATFORM"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check Python version
check_python() {
    log "Checking Python installation..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log "Python $PYTHON_VERSION found"
        
        # Check if version is 3.8 or higher
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
            log "✅ Python version is compatible"
        else
            error "Python 3.8 or higher is required"
        fi
    else
        error "Python 3 is not installed"
    fi
}

# Install platform-specific system dependencies
install_system_deps() {
    log "Installing system dependencies for $PLATFORM..."
    
    case $PLATFORM in
        linux)
            if command -v apt-get &> /dev/null; then
                # Debian/Ubuntu
                sudo apt-get update
                sudo apt-get install -y \
                    python3-dev \
                    python3-pip \
                    python3-venv \
                    libopencv-dev \
                    python3-opencv \
                    libv4l-dev \
                    v4l-utils \
                    python3-serial \
                    build-essential \
                    cmake \
                    pkg-config
                    
                # Check if we're on ARM
                if [[ $(uname -m) =~ ^(aarch64|armv7l|armv8)$ ]]; then
                    log "ARM platform detected, installing additional packages..."
                    sudo apt-get install -y \
                        python3-pyqt6 \
                        python3-pyqt6.qtmultimedia
                fi
                
            elif command -v yum &> /dev/null; then
                # RHEL/CentOS
                sudo yum install -y \
                    python3-devel \
                    python3-pip \
                    opencv-devel \
                    python3-opencv \
                    v4l-utils-devel \
                    python3-pyserial \
                    gcc \
                    gcc-c++ \
                    cmake
            fi
            ;;
            
        macos)
            if command -v brew &> /dev/null; then
                brew install opencv python@3.11
            else
                warn "Homebrew not found. Please install manually or install Homebrew first."
            fi
            ;;
            
        windows)
            warn "Windows detected. Please install dependencies manually:"
            warn "1. Install Python 3.8+ from python.org"
            warn "2. Install Visual Studio Build Tools"
            warn "3. Run: pip install opencv-python"
            ;;
    esac
    
    log "✅ System dependencies installed"
}

# Setup Python virtual environment
setup_venv() {
    log "Setting up Python virtual environment..."
    
    if [[ -d "venv" ]]; then
        warn "Virtual environment already exists. Removing..."
        rm -rf venv
    fi
    
    python3 -m venv venv
    
    # Activate virtual environment
    source venv/bin/activate || source venv/Scripts/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    log "✅ Virtual environment created"
}

# Install Python dependencies
install_python_deps() {
    log "Installing Python dependencies..."
    
    # Activate virtual environment
    source venv/bin/activate || source venv/Scripts/activate
    
    # Install based on platform
    if [[ $PLATFORM == "linux" ]] && [[ $(uname -m) =~ ^(aarch64|armv7l|armv8)$ ]]; then
        # ARM Linux - use lighter packages
        pip install \
            opencv-python-headless>=4.8.0 \
            numpy>=1.24.0 \
            Pillow>=9.5.0 \
            pyserial>=3.5 \
            psutil>=5.9.0 \
            PySide6>=6.5.0
    else
        # Install from requirements.txt
        if [[ -f "requirements.txt" ]]; then
            pip install -r requirements.txt
        else
            # Fallback installation
            pip install \
                PySide6>=6.5.0 \
                opencv-python>=4.8.0 \
                numpy>=1.24.0 \
                Pillow>=9.5.0 \
                pyserial>=3.5 \
                psutil>=5.9.0 \
                pytest>=7.0.0 \
                pytest-qt>=4.2.0
        fi
    fi
    
    log "✅ Python dependencies installed"
}

# Create development configuration
create_dev_config() {
    log "Creating development configuration..."
    
    # Create data directory
    mkdir -p data/raw
    mkdir -p data/temp
    mkdir -p logs
    
    # Create basic config if it doesn't exist
    if [[ ! -f "config.json" ]]; then
        cat > config.json << 'EOF'
{
    "last_camera_index": 0,
    "auto_white_balance": true,
    "default_resolution": "1920x1080",
    "save_format": "jpg",
    "quality": 95,
    "create_preview": true,
    "create_metadata": true,
    "debug_mode": false
}
EOF
        log "✅ Default configuration created"
    fi
    
    # Create .gitignore if it doesn't exist
    if [[ ! -f ".gitignore" ]]; then
        cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# Data and logs
data/
logs/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Configuration
config.json
*.db
EOF
        log "✅ .gitignore created"
    fi
}

# Setup development tools
setup_dev_tools() {
    log "Setting up development tools..."
    
    # Activate virtual environment
    source venv/bin/activate || source venv/Scripts/activate
    
    # Install development tools
    pip install \
        black \
        pylint \
        mypy \
        pre-commit
    
    # Setup pre-commit hooks
    if [[ -f ".pre-commit-config.yaml" ]]; then
        pre-commit install
        log "✅ Pre-commit hooks installed"
    fi
}

# Test installation
test_installation() {
    log "Testing installation..."
    
    # Activate virtual environment
    source venv/bin/activate || source venv/Scripts/activate
    
    # Test imports
    python3 -c "
import cv2
import numpy as np
import serial
import psutil
from PySide6.QtWidgets import QApplication
from platform_config import platform_config
from camera_backend import CameraBackend
from scale_interface import ScaleInterface
print('✅ All imports successful')
print(f'OpenCV version: {cv2.__version__}')
print(f'Platform: {platform_config.platform}')
print(f'Hardware: RK3568' if platform_config.is_rk3568 else 'Generic')
"
    
    log "✅ Installation test passed"
}

# Create run script
create_run_script() {
    log "Creating run script..."
    
    cat > run.sh << 'EOF'
#!/bin/bash

# Activate virtual environment
source venv/bin/activate || source venv/Scripts/activate

# Set environment variables
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_QPA_PLATFORM_PLUGIN_PATH=""

# Run the application
python3 AIScaleDataCollector.py "$@"
EOF
    
    chmod +x run.sh
    
    log "✅ Run script created (use ./run.sh to start the application)"
}

# Print final instructions
print_instructions() {
    log ""
    log "🎉 Development environment setup complete!"
    log ""
    log "To start development:"
    log "1. Activate virtual environment: source venv/bin/activate"
    log "2. Run the application: ./run.sh"
    log "3. Or run directly: python3 AIScaleDataCollector.py"
    log ""
    log "For RK3568 deployment:"
    log "1. Copy all files to the target device"
    log "2. Run: sudo ./deploy_rk3568.sh"
    log ""
    log "Configuration file: config.json"
    log "Data directory: data/"
    log "Logs directory: logs/"
}

# Main function
main() {
    check_python
    install_system_deps
    setup_venv
    install_python_deps
    create_dev_config
    setup_dev_tools
    test_installation
    create_run_script
    print_instructions
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi