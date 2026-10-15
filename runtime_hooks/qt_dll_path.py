"""Make the bundled Qt DLLs win over unrelated Qt installations on Windows.

This module is executed by PyInstaller before ``main.py``.  QtCore.pyd loads
Qt6Core.dll during import, so the directory must be registered before importing
anything from PySide6.  ``add_dll_directory`` is more reliable than relying on
the system PATH on current Windows versions.
"""

from __future__ import annotations

import os
import sys


if sys.platform.startswith("win") and getattr(sys, "frozen", False):
    qt_dll_dir = os.path.join(sys._MEIPASS, "PySide6")
    if os.path.isdir(qt_dll_dir):
        # Keep the handle alive for the lifetime of the application.
        _qt_dll_directory_handle = os.add_dll_directory(qt_dll_dir)
        os.environ["PATH"] = qt_dll_dir + os.pathsep + os.environ.get("PATH", "")
