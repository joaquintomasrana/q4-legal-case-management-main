"""Entry point of the legal case management application."""

import sys
import os
import platform

# DPI awareness for Windows - avoids blurry rendering on high-resolution displays
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Make sure the script directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from ui.app import App


def main():
    db.init_db()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
