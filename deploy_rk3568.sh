#!/bin/bash

# AI-Scale Data Collector Deployment Script for RK3568
# This script sets up the application on Rockchip RK3568 hardware

set -e  # Exit on any error

echo "🚀 AI-Scale Data Collector RK3568 Deployment"
echo "============================================="

# Configuration
APP_NAME="aiscale"
APP_DIR="/opt/aiscale"
SERVICE_NAME="aiscale"
USER_NAME="aiscale"
DATA_DIR="/home/aiscale/data"
LOG_DIR="/var/log/aiscale"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

# Detect RK3568 hardware
detect_hardware() {
    log "Detecting hardware..."
    
    if grep -q "rk3568" /proc/cpuinfo || grep -q "rockchip" /proc/cpuinfo; then
        log "✅ RK3568 hardware detected"
    else
        warn "RK3568 hardware not detected. Continuing anyway..."
    fi
    
    # Check available memory
    TOTAL_MEM=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_MEM_GB=$((TOTAL_MEM / 1024 / 1024))
    
    log "Total memory: ${TOTAL_MEM_GB}GB"
    
    if [[ $TOTAL_MEM_GB -lt 2 ]]; then
        warn "Low memory detected (${TOTAL_MEM_GB}GB). Performance may be limited."
    fi
}

# Install system dependencies
install_dependencies() {
    log "Installing system dependencies..."
    
    # Update package lists
    apt-get update
    
    # Install Python and development tools
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        cmake \
        pkg-config \
        git
    
    # Install multimedia libraries
    apt-get install -y \
        libopencv-dev \
        python3-opencv \
        libv4l-dev \
        v4l-utils \
        uvcdynctrl
    
    # Install Qt dependencies
    apt-get install -y \
        python3-pyqt6 \
        python3-pyqt6.qtmultimedia \
        qt6-base-dev \
        libqt6multimedia6-dev
    
    # Install hardware acceleration libraries
    apt-get install -y \
        libmali-g52-x11 \
        rockchip-multimedia-config \
        gstreamer1.0-rockchip1 \
        libdrm-rockchip1
    
    # Install serial communication tools
    apt-get install -y \
        python3-serial \
        setserial \
        minicom
    
    log "✅ System dependencies installed"
}

# Create application user
create_user() {
    log "Creating application user..."
    
    if id "$USER_NAME" &>/dev/null; then
        log "User $USER_NAME already exists"
    else
        useradd -m -s /bin/bash "$USER_NAME"
        log "✅ User $USER_NAME created"
    fi
    
    # Add user to necessary groups
    usermod -a -G video,audio,dialout,plugdev "$USER_NAME"
    
    # Create data directory
    sudo -u "$USER_NAME" mkdir -p "$DATA_DIR"
    chown -R "$USER_NAME:$USER_NAME" "$DATA_DIR"
}

# Setup application directory
setup_application() {
    log "Setting up application..."
    
    # Create application directory
    mkdir -p "$APP_DIR"
    
    # Copy application files
    if [[ -f "AIScaleDataCollector.py" ]]; then
        cp *.py "$APP_DIR/"
        
        # Copy additional modules
        if [[ -d "tools" ]]; then
            cp -r tools "$APP_DIR/"
        fi
        
        log "✅ Application files copied"
    else
        error "AIScaleDataCollector.py not found in current directory"
    fi
    
    # Set permissions
    chown -R "$USER_NAME:$USER_NAME" "$APP_DIR"
    chmod +x "$APP_DIR/AIScaleDataCollector.py"
}

# Setup Python virtual environment
setup_python_env() {
    log "Setting up Python virtual environment..."
    
    # Create virtual environment as the app user
    sudo -u "$USER_NAME" python3 -m venv "$APP_DIR/venv"
    
    # Install Python dependencies
    sudo -u "$USER_NAME" "$APP_DIR/venv/bin/pip" install --upgrade pip
    
    if [[ -f "requirements.txt" ]]; then
        # Install ARM-optimized packages for RK3568
        sudo -u "$USER_NAME" "$APP_DIR/venv/bin/pip" install \
            opencv-python-headless \
            numpy \
            pillow \
            pyserial \
            psutil \
            PySide6
        
        log "✅ Python environment setup complete"
    else
        warn "requirements.txt not found, installing minimal dependencies"
    fi
}

# Setup hardware optimizations
setup_hardware_optimizations() {
    log "Applying hardware optimizations..."
    
    # CPU governor settings
    cat > /etc/systemd/system/cpu-performance.service << 'EOF'
[Unit]
Description=Set CPU Governor to Performance
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'
ExecStart=/bin/bash -c 'echo performance > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor'
ExecStart=/bin/bash -c 'echo performance > /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor'
ExecStart=/bin/bash -c 'echo performance > /sys/devices/system/cpu/cpu3/cpufreq/scaling_governor'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl enable cpu-performance.service
    
    # GPU frequency settings
    if [[ -f "/sys/class/devfreq/ff400000.gpu/governor" ]]; then
        echo performance > /sys/class/devfreq/ff400000.gpu/governor
    fi
    
    # Video memory settings
    cat >> /etc/sysctl.conf << 'EOF'

# RK3568 optimizations for AI-Scale
vm.swappiness=10
vm.vfs_cache_pressure=50
kernel.sched_latency_ns=1000000
kernel.sched_min_granularity_ns=100000
EOF
    
    log "✅ Hardware optimizations applied"
}

# Setup camera permissions
setup_camera_permissions() {
    log "Setting up camera permissions..."
    
    # Create udev rules for camera access
    cat > /etc/udev/rules.d/99-aiscale-camera.rules << 'EOF'
# AI-Scale camera permissions
SUBSYSTEM=="video4linux", GROUP="video", MODE="0664"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0c45", GROUP="video", MODE="0664"
KERNEL=="video[0-9]*", GROUP="video", MODE="0664"
EOF
    
    # Reload udev rules
    udevadm control --reload-rules
    udevadm trigger
    
    log "✅ Camera permissions configured"
}

# Setup serial port permissions
setup_serial_permissions() {
    log "Setting up serial port permissions..."
    
    # Create udev rules for serial devices
    cat > /etc/udev/rules.d/99-aiscale-serial.rules << 'EOF'
# AI-Scale serial port permissions
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", GROUP="dialout", MODE="0664"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", GROUP="dialout", MODE="0664"
KERNEL=="ttyUSB[0-9]*", GROUP="dialout", MODE="0664"
KERNEL=="ttyACM[0-9]*", GROUP="dialout", MODE="0664"
EOF
    
    udevadm control --reload-rules
    udevadm trigger
    
    log "✅ Serial permissions configured"
}

# Create systemd service
create_service() {
    log "Creating systemd service..."
    
    cat > /etc/systemd/system/"$SERVICE_NAME".service << EOF
[Unit]
Description=AI-Scale Data Collector
After=multi-user.target network.target
Wants=network.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$APP_DIR
Environment=DISPLAY=:0
Environment=QT_QPA_PLATFORM=xcb
Environment=QT_AUTO_SCREEN_SCALE_FACTOR=1
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/AIScaleDataCollector.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryMax=1G
CPUQuota=300%

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    
    log "✅ Systemd service created and enabled"
}

# Setup logging
setup_logging() {
    log "Setting up logging..."
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    chown "$USER_NAME:$USER_NAME" "$LOG_DIR"
    
    # Setup log rotation
    cat > /etc/logrotate.d/aiscale << 'EOF'
/var/log/aiscale/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 aiscale aiscale
}
EOF
    
    log "✅ Logging configured"
}

# Create startup script
create_startup_script() {
    log "Creating startup script..."
    
    cat > "$APP_DIR/start.sh" << 'EOF'
#!/bin/bash

# AI-Scale startup script
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Check if X server is running
if ! pgrep -x "Xorg" > /dev/null; then
    echo "Starting X server..."
    startx &
    sleep 5
fi

# Start the application
cd /opt/aiscale
./venv/bin/python AIScaleDataCollector.py
EOF
    
    chmod +x "$APP_DIR/start.sh"
    chown "$USER_NAME:$USER_NAME" "$APP_DIR/start.sh"
    
    log "✅ Startup script created"
}

# Configure autostart
configure_autostart() {
    log "Configuring autostart..."
    
    # Create desktop entry for autostart
    sudo -u "$USER_NAME" mkdir -p "/home/$USER_NAME/.config/autostart"
    
    cat > "/home/$USER_NAME/.config/autostart/aiscale.desktop" << 'EOF'
[Desktop Entry]
Name=AI-Scale Data Collector
Comment=Produce image capture and weighing system
Exec=/opt/aiscale/start.sh
Icon=/opt/aiscale/icon.png
Terminal=false
Type=Application
X-GNOME-Autostart-enabled=true
EOF
    
    chown "$USER_NAME:$USER_NAME" "/home/$USER_NAME/.config/autostart/aiscale.desktop"
    
    log "✅ Autostart configured"
}

# Main deployment function
main() {
    log "Starting AI-Scale deployment for RK3568..."
    
    check_root
    detect_hardware
    install_dependencies
    create_user
    setup_application
    setup_python_env
    setup_hardware_optimizations
    setup_camera_permissions
    setup_serial_permissions
    create_service
    setup_logging
    create_startup_script
    configure_autostart
    
    log ""
    log "🎉 Deployment completed successfully!"
    log ""
    log "Next steps:"
    log "1. Reboot the system: sudo reboot"
    log "2. Check service status: sudo systemctl status $SERVICE_NAME"
    log "3. View logs: sudo journalctl -u $SERVICE_NAME -f"
    log "4. Manual start: sudo systemctl start $SERVICE_NAME"
    log ""
    log "Application will start automatically after reboot."
    log "Data will be stored in: $DATA_DIR"
    log "Logs will be in: $LOG_DIR"
}

# Run main function
main "$@"