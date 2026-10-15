"""اختبارات إخفاء نوافذ العمليات الفرعية (Console Windows) في Windows."""

from __future__ import annotations

import subprocess
import sys

from app.utils.process import subprocess_no_window_kwargs


def test_subprocess_no_window_kwargs_on_windows():
    kwargs = subprocess_no_window_kwargs()
    if sys.platform == "win32":
        assert "creationflags" in kwargs
        assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    else:
        assert kwargs == {}
