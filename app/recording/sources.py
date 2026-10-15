"""
اكتشاف مصادر التسجيل: الشاشات (Monitors)، النوافذ (Windows)، والمناطق المخصصة.

- اكتشاف الشاشات: عبر مكتبة mss (تعمل على Windows/Linux/macOS).
- اكتشاف النوافذ: خاص بنظام التشغيل. على Windows نستخدم pywin32 (win32gui).
  على أنظمة أخرى (Linux/macOS) نُرجع قائمة فارغة مع تسجيل السبب في الـ log،
  لأن هذه الميزة مخصصة لـ Windows حسب متطلبات المشروع.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class MonitorInfo:
    index: int  # 0 = "كل الشاشات مجتمعة" في mss، لذلك مصادرنا تبدأ من 1
    left: int
    top: int
    width: int
    height: int
    is_primary: bool = False

    @property
    def label(self) -> str:
        tag = " (رئيسية)" if self.is_primary else ""
        return f"شاشة {self.index}{tag} — {self.width}x{self.height}"


@dataclass(frozen=True)
class WindowInfo:
    handle: int
    title: str
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class RegionInfo:
    left: int
    top: int
    width: int
    height: int

    @property
    def label(self) -> str:
        return f"منطقة مخصصة ({self.width}x{self.height} عند {self.left},{self.top})"


def get_monitors() -> list[MonitorInfo]:
    """
    يعيد قائمة الشاشات المتصلة. الفهرسة تبدأ من 1 (mss تحجز index=0 لـ "كل الشاشات").
    """
    try:
        import mss
    except ImportError:
        logger.error("مكتبة mss غير مثبتة — لا يمكن اكتشاف الشاشات")
        return []

    monitors: list[MonitorInfo] = []
    try:
        with mss.mss() as sct:
            raw_monitors = sct.monitors  # index 0 = union of all monitors
            for idx, mon in enumerate(raw_monitors[1:], start=1):
                monitors.append(
                    MonitorInfo(
                        index=idx,
                        left=mon["left"],
                        top=mon["top"],
                        width=mon["width"],
                        height=mon["height"],
                        is_primary=(idx == 1),
                    )
                )
        logger.info("تم اكتشاف %d شاشة/شاشات", len(monitors))
    except Exception:
        logger.exception("فشل اكتشاف الشاشات")
    return monitors


def get_windows() -> list[WindowInfo]:
    """
    يعيد قائمة النوافذ المفتوحة القابلة للتسجيل (لها عنوان ظاهر وحجم غير صفري).
    مدعومة على Windows فقط عبر pywin32.
    """
    if not sys.platform.startswith("win"):
        logger.warning(
            "اكتشاف النوافذ (Window enumeration) غير مدعوم على هذا النظام (%s)، "
            "هذه الميزة مخصصة لـ Windows حسب متطلبات المشروع.",
            sys.platform,
        )
        return []

    try:
        import win32gui  # type: ignore
    except ImportError:
        logger.error("مكتبة pywin32 غير مثبتة — لا يمكن اكتشاف النوافذ على Windows")
        return []

    windows: list[WindowInfo] = []

    def _enum_handler(hwnd: int, _) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return
        windows.append(WindowInfo(hwnd, title, left, top, width, height))

    try:
        win32gui.EnumWindows(_enum_handler, None)
        logger.info("تم اكتشاف %d نافذة قابلة للتسجيل", len(windows))
    except Exception:
        logger.exception("فشل اكتشاف النوافذ")

    return windows
