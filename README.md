# AI-Scale Data Collector v2.2

A professional, production-ready tool for capturing high-quality produce images for computer vision model training. This application is optimized for macOS and features a robust, intuitive interface designed to maximize data collection efficiency and quality.

![App Screenshot](https://i.imgur.com/g91xJ0s.png)

## 🌟 Key Features

* **High-Quality Image Processing**: On-the-fly, software-based image processing corrects for common camera issues.
  * **Auto White Balance**: Eliminates color casts (e.g., blue tint) for true-to-life colors.
  * **Live Adjustments**: Real-time sliders for brightness, contrast, and saturation.
  * **Live Histogram**: A side-panel histogram to monitor exposure and color balance.
* **Robust Data Management**:
  * **SQLite Database**: All image metadata is stored in a scalable and efficient `metadata.db` file, replacing thousands of individual `.json` files.
  * **Configuration File**: A simple `config.json` stores your settings, like last-used camera and window size.
  * **Disk Space Guard**: The app pre-emptively checks for sufficient disk space before saving to prevent errors.
* **Intuitive User Experience**:
  * **Modern UI**: A clean, Apple-inspired interface that is simple and responsive.
  * **Asynchronous Operations**: The UI never freezes, as image saving and processing happen in background threads.
  * **Clear Feedback**: Visual cues for successful captures, save errors, and selection requirements.
* **Stable & Reliable**:
  * **Hardware Compatibility**: Works reliably with a wide range of UVC-compliant USB cameras on macOS.
  * **Error Recovery**: Gracefully handles camera connection and switching issues.

## 🚀 Quick Start

### 1. Setup

The setup script creates a Python virtual environment, installs all dependencies, and prepares the necessary files and directories.

```bash
# Make the setup script executable and run it
chmod +x setup.sh
./setup.sh
```

### 2. Grant Camera Permissions (macOS)

The very first time you run the app, you may need to grant camera permissions.

1. Run the application using the start script: `./start_collector.sh`.
2. A dialog will appear asking for camera access. Click **OK**.
3. If you don't see a dialog, you may need to go to **System Settings → Privacy & Security → Camera** and manually enable access for your terminal application (e.g., **Terminal**, **iTerm**, or **Cursor**).
4. You must **restart your terminal application** for the permission change to take effect.

### 3. Start Collecting Data

Use the provided start script to launch the application.

```bash
./start_collector.sh
```

## 📸 How to Use the Application

1. **Select Camera**: If you have multiple cameras, choose the correct one from the **Camera** dropdown.
2. **Select Produce Type**: Use the **Produce Type** dropdown to choose the item you are capturing.
3. **Add a New Type**: If your produce isn't listed, click the **+ Add New** button and enter its name.
4. **Adjust Image Quality**: Use the sliders in the **Camera Controls** panel on the right to fine-tune the image. The white balance is corrected automatically.
5. **Position Item**: Place the produce under the camera.
6. **Capture**: Click the **Capture Image** button or press the **Spacebar**.

### Keyboard Shortcuts

* **Spacebar**: Capture the current image.
* **Ctrl+Q**: Quit the application.

## 📁 Project Structure

The project is organized for clarity and scalability.

``` bash
AI-Scale/
│
├── AIScaleDataCollector.py   # Main application source code
├── README.md                 # This documentation file
├── requirements.txt          # Python dependencies
├── config.json               # User-specific settings (auto-generated)
│
├── data/
│   ├── raw/                  # Where image files are stored
│   │   ├── apple/
│   │   └── banana/
│   └── metadata.db           # SQLite database for all image metadata
│
├── tools/
│   └── data_processing/
│       └── quick_validate.py # Script to validate the dataset
│
├── setup.sh                  # Run this first to set up the environment
├── start_collector.sh        # Run this to start the application
└── test_collector.py         # A simple smoke test for the application
```

## 🔧 Validation & Troubleshooting

### Validating Your Dataset

A script is provided to quickly validate the integrity of your dataset by checking the database against the files on disk.

```bash
# Activate virtual environment
source venv/bin/activate

# Run the validation script
python tools/data_processing/quick_validate.py data/raw
```

### Camera Not Detected or Black Screen

This is the most common issue and is usually easy to resolve.

1. **Check Physical Connection**: Ensure your USB camera is securely plugged in.
2. **Select the Right Camera**: Use the "Camera" dropdown in the UI. The app might have defaulted to your Mac's built-in FaceTime camera.
3. **Check macOS Permissions**: Verify that your terminal has camera access in **System Settings**.
4. **Close Other Apps**: Make sure no other application (e.g., Zoom, Photo Booth) is currently using the camera.

---
*This tool has been significantly refactored and improved for robustness and professional use.*
