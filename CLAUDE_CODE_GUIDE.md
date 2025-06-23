# Claude Code Guide for AI-Scale Project

## 🎉 Installation Complete

Claude Code is now installed globally and ready to use with your AI-Scale project.

## 🚀 How to Use Claude Code with Your Virtual Environment

### 1. Start a Session

```bash
# Activate your virtual environment first
source venv/bin/activate

# Start Claude Code in interactive mode
claude
```

### 2. Useful Commands for Your Project

```bash
# Ask about your codebase
claude "Explain how the camera initialization works in AIScaleDataCollector.py"

# Get help with debugging
claude "Why might the camera view be black? Check the camera handling code"

# Request code improvements
claude "Review the image saving function for potential improvements"

# Add new features
claude "Add a feature to export images in different formats (PNG, JPEG, TIFF)"

# Debug database issues
claude "Help me debug why the metadata.db might be corrupted"
```

### 3. Interactive Development Workflow

```bash
# Start interactive session
claude

# Then you can ask questions like:
# "How does the PySide6 camera widget work?"
# "Show me how to add a new image filter"
# "Explain the white balance correction algorithm"
# "Help me optimize the image processing pipeline"
```

### 4. Project-Specific Prompts

Here are some tailored prompts for your AI-Scale project:

#### Camera and Hardware

```bash
claude "How does the application detect and handle multiple USB cameras?"
claude "Explain the camera resolution and frame rate settings"
claude "How can I add support for different camera types?"
```

#### Image Processing

```bash
claude "Explain the white balance correction in the image processing pipeline"
claude "How does the brightness/contrast adjustment work?"
claude "Show me how to add new image filters or effects"
```

#### Data Management

```bash
claude "How does the SQLite database store image metadata?"
claude "Explain the session tracking and export functionality"
claude "How can I add data validation for the captured images?"
```

#### UI and UX

```bash
claude "How does the PySide6 UI handle asynchronous operations?"
claude "Explain the produce type selection and management"
claude "How can I improve the user interface for better usability?"
```

### 5. Advanced Usage

#### Using with Specific Files

```bash
# Ask about specific files
claude "Analyze the AIScaleDataCollector.py file and suggest improvements"

# Get help with specific functions
claude "Explain the capture_image function in detail"
```

#### Debugging Sessions

```bash
# Continue previous conversation
claude -c

# Resume specific session
claude -r [session-id]
```

#### Code Generation

```bash
# Generate new features
claude "Create a new function to validate image quality before saving"

# Add documentation
claude "Generate docstrings for all functions in the main class"
```

## 🔧 Integration with Cursor

Since you're using Cursor, you can also:

1. **Use Cursor's built-in AI** (`Cmd+L` or `Cmd+K`)
2. **Highlight code** and ask questions
3. **Get real-time suggestions** as you code
4. **Use the terminal integration** for Claude Code

## 📋 Quick Reference

### Common Commands

```bash
claude                    # Start interactive session
claude -p "prompt"       # Print response and exit
claude -c                # Continue last conversation
claude --help            # Show all options
claude config            # Manage configuration
```

### Environment Setup

```bash
# Always activate virtual environment first
source venv/bin/activate

# Then use Claude Code
claude
```

## 🎯 Best Practices

1. **Always activate your virtual environment** before using Claude Code
2. **Be specific** in your prompts about your AI-Scale project
3. **Use the project context** - Claude Code can see your entire codebase
4. **Ask for explanations** of complex camera or image processing code
5. **Request improvements** for performance, UI, or features

## 🚨 Troubleshooting

### If Claude Code isn't found

```bash
# Check if it's in your PATH
echo $PATH | grep npm-global

# If not, reload your shell
source ~/.zshrc
```

### If you get permission errors

```bash
# The global installation should have fixed this
# If issues persist, use npx instead:
npx @anthropic-ai/claude-code
```

---

Happy coding with Claude Code! 🤖
