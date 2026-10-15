"""
أدوات تشغيل العمليات الفرعية بأمان دون إظهار نوافذ Console سوداء.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any


def subprocess_no_window_kwargs() -> dict[str, Any]:
    """
    إرجاع إعدادات منع ظهور نوافذ الـ Console (الشاشات السوداء) في نظام Windows.
    في نظام Windows، يمنع CREATE_NO_WINDOW ظهور أي نافذة موجه أوامر للعمليات الفرعية
    (مثل FFmpeg أو FFprobe)، بما في ذلك عند تشغيل التطبيق كـ GUI Windowed.
    """
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return kwargs
