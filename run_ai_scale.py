#!/usr/bin/env python3
"""
AI-Scale Data Collector Launcher
Simple launcher script for the new clean UI
"""

import sys
import os
from pathlib import Path

# Add the current directory to the path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ai_scale_ui import main
    if __name__ == "__main__":
        sys.exit(main())
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all dependencies are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Error starting AI-Scale: {e}")
    sys.exit(1)