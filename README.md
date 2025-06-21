# AI-Scale Data Collector

A clean, focused tool for capturing high-quality produce images for AI training. Optimized for M2 MacBook Air with Arducam IMX219 USB camera.

## 🎯 Purpose

This tool is designed for the early data collection phase of the AI-Scale project - a next-generation smart retail weighing scale that uses edge-based computer vision to automatically identify fruits and vegetables at checkout.

## 🖥️ Hardware Requirements

- **Development Machine**: M2 MacBook Air (2022, 8GB RAM)
- **Camera**: Arducam USB Camera (SKU: B0196) with Sony IMX219 sensor
- **Target Deployment**: Rockchip RK3568 (Linux, 1 TOPS NPU)

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Make setup script executable and run it
chmod +x setup.sh
./setup.sh
```

### 2. Grant Camera Permissions

1. Open **System Settings** → **Privacy & Security** → **Camera**
2. Enable camera access for **Terminal** (or Cursor)
3. Restart your terminal/Cursor if needed

### 3. Start Collecting Data

```bash
# Activate virtual environment
source venv/bin/activate

# Run the data collector
python AIScaleDataCollector.py
```

## 📸 How to Use

### Basic Workflow

1. **Select Produce Type**: Click emoji buttons or use dropdown
2. **Position Item**: Place produce under camera
3. **Capture**: Press **Space** or click the big red CAPTURE button
4. **Repeat**: Move/rotate item and capture 20-50 variations

### Keyboard Shortcuts

- **Space** - Capture image
- **Ctrl+N** - Focus on new class input
- **Ctrl+O** - Change dataset path
- **Ctrl+Q** - Quit application

### Adding Custom Classes

For fine-grained classification (e.g., Gala vs Fuji apples):

1. Type class name in "New Class" field
2. Press Enter or click "Add Class"
3. Names are automatically sanitized (spaces → underscores)

## 📁 Data Organization

Images are automatically organized into folders:

```bash
data/raw/
├── apple/
│   ├── apple_0001_20240120_143022_123.jpg
│   └── apple_0002_20240120_143025_456.jpg
├── banana/
├── carrot/
└── [other produce types]/
```

## ⚙️ Camera Optimizations

### IMX219 Sensor Settings

- **Preview**: 1920x1080 @ 30fps (smooth operation)
- **Capture**: 3280x2464 (full 8MP when high-res enabled)
- **Format**: MJPEG for best compatibility
- **Autofocus**: Enabled
- **Auto-exposure**: Enabled

### M2 Mac Optimizations

- Uses AVFoundation backend (best for macOS)
- Reduced buffer size for lower latency
- Proper permission handling

## 🎯 Data Collection Guidelines

### Image Quality

- **Lighting**: Natural or consistent lighting
- **Background**: Clean, uncluttered surface
- **Angles**: Capture from multiple angles (top, side, rotated)
- **Variations**: Different sizes, ripeness, damage levels

### Recommended Quantities

- **Per Class**: 100-200 images minimum
- **Variations**: 5-10 different items per class
- **Angles**: 3-5 different viewing angles per item

### Fine-Grained Classification

For distinguishing varieties (e.g., apple types):

- **gala_apple**: 150+ images
- **fuji_apple**: 150+ images
- **granny_smith_apple**: 150+ images

## 🔧 Troubleshooting

### Camera Not Detected

```bash
# Test camera access
python3 -c "import cv2; print('Camera found:', cv2.VideoCapture(0).isOpened())"
```

**Common Solutions:**

1. Check USB connection
2. Grant camera permissions in System Settings
3. Close other camera-using applications
4. Restart terminal/Cursor

### Permission Errors

- Quit and restart Cursor/Terminal after granting permissions
- Check System Settings → Privacy & Security → Camera

### High-Resolution Capture Issues

- The tool automatically falls back to preview resolution
- Check available camera resolutions with your specific IMX219 model

## 📊 Features

### Core Functionality

- ✅ Real-time camera preview
- ✅ High-resolution capture (8MP)
- ✅ Automatic file organization
- ✅ Session statistics
- ✅ Recent captures list
- ✅ Keyboard shortcuts

### UI/UX

- ✅ Clean, modern interface
- ✅ Quick-select produce buttons
- ✅ Visual capture feedback
- ✅ Resizable panels
- ✅ Status bar with information

### Data Management

- ✅ Auto-incrementing filenames
- ✅ Timestamp-based naming
- ✅ Sanitized class names
- ✅ Session tracking
- ✅ Dataset path management

## 🔮 Future Development

This tool is designed for the data collection phase. Future phases include:

1. **Model Training**: EfficientNet-B0/MobileNet training
2. **Model Conversion**: PyTorch → RKNN conversion
3. **Edge Deployment**: RK3568 deployment with INT8 quantization
4. **Production Integration**: Full retail checkout system

## 📝 Notes

- **Local Storage Only**: No cloud integration or backend required
- **Offline Operation**: Works completely offline
- **Production Ready**: Clean codebase ready for team collaboration
- **Scalable**: Easy to add new features as project grows

---

### Happy data collecting! 🍎📸
