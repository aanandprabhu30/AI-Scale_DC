# AI-Scale Data Collector

A clean, focused tool for capturing high-quality produce images for AI training. Optimized for modern macOS with a simple, intuitive interface.

## 🎯 Purpose

This tool is designed for the data collection phase of the AI-Scale project—a smart retail scale that uses computer vision to automatically identify fruits and vegetables. Its purpose is to make capturing a clean, organized dataset as simple as possible.

## 🚀 Quick Start

### 1. Setup Environment

The setup script creates a virtual environment and installs all necessary dependencies.

```bash
# Make setup script executable and run it
chmod +x setup.sh
./setup.sh
```

### 2. Grant Camera Permissions (macOS)

The first time you run the app, macOS will ask for camera permission.

1. A dialog will appear. Click **OK**.
2. If you miss the dialog, go to **System Settings** → **Privacy & Security** → **Camera**.
3. Enable camera access for your terminal application (e.g., **Terminal** or **iTerm**).
4. Restart your terminal application for the changes to take effect.

### 3. Start Collecting Data

```bash
# Use the start script (recommended)
./start_collector.sh

# Or, if you prefer to run it manually:
source venv/bin/activate
python AIScaleDataCollector.py
```

## 📸 How to Use

The interface is designed for simplicity and focus.

1. **Select Produce Type**: Use the dropdown menu to choose the produce you are capturing.
2. **Add a New Type**: If your produce isn't listed, click **+ Add New** and enter a name.
3. **Position Item**: Place the produce under the camera.
4. **Capture**: Click the **Capture Image** button or press the **Spacebar**.
5. **Repeat**: Capture multiple angles and variations of each item to build a robust dataset.

### Camera Selection

If the camera view is black or showing the wrong camera:

* Go to **File** → **Camera Settings...** in the menu bar.
* Select the correct camera (e.g., your Arducam) from the list and click **OK**.

### Keyboard Shortcuts

* **Spacebar** - Capture the current image.
* **Ctrl+Q** - Quit the application.

## 📁 Data Organization

Images are automatically saved into a clean, organized folder structure. All data is stored in the `data/raw/` directory, with a separate folder for each produce type.

``` bash
data/raw/
├── apple/
│   ├── apple_0001_20240120_143022.jpg
│   └── apple_0001_20240120_143022.json
├── banana/
│   ├── banana_0001_20240120_143501.jpg
│   └── banana_0001_20240120_143501.json
└── gala_apple/
```

* A `.json` file containing metadata is saved alongside each image.
* The old `data/sessions` directory is no longer used.

## ⚙️ Key Features

* **Simple, Clean UI**: An Apple-inspired interface that's easy to use.
* **Live Camera Preview**: See exactly what you're capturing in real-time.
* **Reliable Capture**: A stable capture process that works with a wide range of USB cameras.
* **Camera Selection**: Easily switch between connected cameras via the File menu.
* **Automatic Organization**: Images are automatically named, timestamped, and saved in the correct class folder.
* **Metadata Generation**: A JSON file with key details is saved with every image.

## 🔧 Troubleshooting

### Camera Not Detected or Black Screen

This is the most common issue and is usually easy to fix.

1. **Check Physical Connection**: Ensure your USB camera is securely plugged in.
2. **Select the Right Camera**: Go to **File → Camera Settings...** and select your camera from the list. The application may have defaulted to your built-in FaceTime camera.
3. **Check macOS Permissions**: Make sure your terminal has camera access in **System Settings**.
4. **Close Other Apps**: Ensure no other application (e.g., Zoom, Photo Booth) is using the camera.

### `PySide6` Not Found

If you see an error about `PySide6` not being found, your environment is not set up correctly. Run the setup script again:
`./setup.sh`

This application uses **PySide6**, which provides the best compatibility and performance on modern macOS.
