# AI-Scale Data Collector v2.3

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
  * **Session Export**: Export session data to CSV format for external analysis.
* **Intuitive User Experience**:
  * **Modern UI**: A clean, Apple-inspired interface that is simple and responsive.
  * **Asynchronous Operations**: The UI never freezes, as image saving and processing happen in background threads.
  * **Clear Feedback**: Visual cues for successful captures, save errors, and selection requirements.
  * **Camera Selection**: Dropdown to choose between multiple connected cameras.
  * **Decluttered Layout**: Streamlined produce selector with better organization.
* **Stable & Reliable**:
  * **Hardware Compatibility**: Works reliably with a wide range of UVC-compliant USB cameras on macOS.
  * **Error Recovery**: Gracefully handles camera connection and switching issues.
  * **PySide6 Framework**: Uses PySide6 for optimal macOS compatibility and performance.

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

1. **Select Camera**: If you have multiple cameras, choose the correct one from the **Camera** dropdown in the top toolbar.
2. **Select Produce Type**: Use the **Produce Type** dropdown to choose the item you are capturing.
3. **Add a New Type**: If your produce isn't listed, click the **+ Add New** button and enter its name.
4. **Adjust Image Quality**: Use the sliders in the **Camera Controls** panel on the right to fine-tune the image. The white balance is corrected automatically.
5. **Use Presets**: Click the **Indoor**, **Outdoor**, or **Hazy** buttons for quick lighting adjustments.
6. **Position Item**: Place the produce under the camera.
7. **Capture**: Click the **Capture Image** button or press the **Spacebar**.

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
│       ├── quick_validate.py # Script to validate the dataset
│       └── dataset_validator.py # Comprehensive dataset validation
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

### Comprehensive Dataset Analysis

For more detailed analysis of your dataset:

```bash
# Run the comprehensive validator
python tools/data_processing/dataset_validator.py data/raw
```

### Camera Not Detected or Black Screen

This is the most common issue and is usually easy to resolve.

1. **Check Physical Connection**: Ensure your USB camera is securely plugged in.
2. **Select the Right Camera**: Use the "Camera" dropdown in the UI. The app might have defaulted to your Mac's built-in FaceTime camera.
3. **Check macOS Permissions**: Verify that your terminal has camera access in **System Settings**.
4. **Close Other Apps**: Make sure no other application (e.g., Zoom, Photo Booth) is currently using the camera.

### UI Freezing During Image Save

The application now uses background threads for image saving, so the UI should remain responsive. If you experience freezing:

1. **Check Disk Space**: Ensure you have sufficient free space on your drive.
2. **Restart the Application**: Close and reopen the app if issues persist.
3. **Check File Permissions**: Ensure the `data/raw` directory is writable.

### Status Bar Errors

If you see AttributeError messages about `status_bar`, this has been fixed in v2.3. The application now safely handles status bar access across all widgets.

## 🆕 Recent Updates (v2.3)

* **PySide6 Migration**: Switched from PyQt6 to PySide6 for better macOS compatibility
* **Background Processing**: Image saving now happens in background threads to keep UI responsive
* **Camera Selection**: Added dropdown to manually select between multiple cameras
* **UI Improvements**: Decluttered produce selector layout and improved visual feedback
* **Enhanced Error Handling**: Better error messages and recovery mechanisms
* **Session Export**: Added ability to export session data to CSV format
* **Dataset Validation Tools**: Comprehensive tools for validating dataset integrity
* **Status Bar Fix**: Resolved AttributeError when accessing status bar from child widgets
* **Preset Functionality**: Fixed indoor/outdoor/hazy preset buttons to properly apply camera settings
* **Camera Switching**: Resolved bug where the app would switch to the wrong camera after applying a preset, which caused a black screen.

## 🧪 Testing

Run the test suite to verify everything is working correctly:

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
python test_collector.py
```

## 🤖 AI-Assisted Development with Claude Code

This project is optimized for AI-assisted development using Claude Code in Cursor. Here's how to get the most out of it:

### Setting up Claude Code in Cursor

1. **Install Claude Code CLI** (if not already installed):

   ```bash
   # Option 1: Use npx (no global installation needed)
   npx @anthropic-ai/claude-code
   
   # Option 2: Install globally (fix permissions first if needed)
   mkdir ~/.npm-global
   npm config set prefix '~/.npm-global'
   echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.zshrc
   source ~/.zshrc
   npm install -g @anthropic-ai/claude-code
   ```

2. **Configure in Cursor**:
   * Open Command Palette (`Cmd+Shift+P`)
   * Search for "Claude Code" commands
   * Or use Cursor's built-in AI features (`Cmd+L` or `Cmd+K`)

### AI-Powered Development Workflow

With Claude Code, you can:

* **Ask questions about the codebase**: "How does the camera initialization work?"
* **Get debugging help**: "Why is the camera view black?"
* **Request feature additions**: "Add a new image filter"
* **Code review**: "Review this function for potential issues"
* **Documentation generation**: "Generate docstrings for this class"

### Project-Specific AI Prompts

Here are some useful prompts for this AI-Scale project:

```bash
# Ask about camera handling
"How does the application handle multiple cameras?"

# Get help with image processing
"Explain the white balance correction algorithm"

# Debug database issues
"Why might the metadata.db file be corrupted?"

# Request new features
"Add a feature to export images in different formats"
```

### Using Cursor's Built-in AI

Cursor already has excellent AI integration! You can:

1. **Highlight code** and ask questions about it
2. **Use `Cmd+L`** to open AI chat for general questions
3. **Use `Cmd+K`** for quick code suggestions
4. **Ask for explanations** of complex functions
5. **Request refactoring** suggestions

### AI-Assisted Troubleshooting

When you encounter issues, try these AI prompts:

* "The camera view is black, what could be causing this?"
* "How do I fix the PySide6 import error?"
* "The UI is freezing during image save, how can I fix this?"
* "How do I add a new produce type to the database?"

---
*This tool has been significantly refactored and improved for robustness and professional use.*
