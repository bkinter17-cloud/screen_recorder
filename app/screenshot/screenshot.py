"""
التقاط لقطة شاشة (Screenshot) — Phase 7.

يدعم:
- الشاشة الكاملة (كل الشاشات مجتمعة)
- شاشة محددة
- منطقة مستطيلة مخصصة
- نافذة محددة (Windows فقط، عبر إحداثيات النافذة من app.recording.sources)

يستخدم mss للالتقاط (سريعة، وتدعم PNG أصلياً)، وPillow لتحويل PNG إلى JPG
عند الحاجة (mss لا تدعم JPG مباشرة).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScreenshotError(Exception):
    pass


def _default_filename(extension: str, output_folder: Path) -> str:
    """
    يبني اسم ملف فريد. الصيغة الأساسية بدقة الثانية كما في المواصفات
    (Screenshot_YYYY-MM-DD_HH-MM-SS)، ومع إضافة رقم تسلسلي تلقائياً إذا
    كانت هناك لقطة أخرى بنفس الاسم خلال نفس الثانية (لمنع الكتابة فوقها).
    """
    base = f"Screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    candidate = f"{base}.{extension}"
    counter = 2
    while (output_folder / candidate).exists():
        candidate = f"{base}_{counter}.{extension}"
        counter += 1
    return candidate


def _save_raw_capture(shot, output_path: Path, image_format: str) -> Path:
    """
    يحفظ نتيجة mss.grab() كملف صورة.
    PNG: عبر mss.tools.to_png مباشرة إلى الملف (لا حاجة لـ Pillow).
    JPG: يحتاج Pillow لأن mss لا يدعم ضغط JPEG أصلياً.
    """
    import mss.tools

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("تعذر إنشاء مجلد لقطات الشاشة %s: %s", output_path.parent, exc)
        raise ScreenshotError(
            f"تعذر إنشاء مجلد لقطات الشاشة:\n{output_path.parent}\n\nالسبب: {exc}\n"
            "يرجى التحقق من صلاحيات المجلد أو تغييره من الإعدادات."
        ) from exc

    if image_format.lower() == "png":
        mss.tools.to_png(shot.rgb, shot.size, output=str(output_path))
        return output_path

    if image_format.lower() in ("jpg", "jpeg"):
        try:
            from PIL import Image
        except ImportError as exc:
            raise ScreenshotError(
                "حفظ لقطة الشاشة بصيغة JPG يتطلب مكتبة Pillow المثبتة"
            ) from exc
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        img.save(output_path, "JPEG", quality=92)
        return output_path

    raise ScreenshotError(f"صيغة صورة غير مدعومة: {image_format}")


def capture_region(
    left: int, top: int, width: int, height: int,
    output_folder: Path, image_format: str = "png",
) -> Path:
    """يلتقط منطقة مستطيلة مخصصة من الشاشة (يُستخدم أيضاً لالتقاط شاشة/نافذة محددة)."""
    try:
        import mss
    except ImportError as exc:
        raise ScreenshotError("مكتبة mss غير مثبتة") from exc

    output_path = output_folder / _default_filename(image_format, output_folder)

    try:
        with mss.mss() as sct:
            region = {"left": left, "top": top, "width": width, "height": height}
            shot = sct.grab(region)
        saved = _save_raw_capture(shot, output_path, image_format)
    except ScreenshotError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("فشل التقاط أو حفظ لقطة الشاشة")
        raise ScreenshotError(f"فشل التقاط أو حفظ لقطة الشاشة: {exc}") from exc

    logger.info("تم حفظ لقطة الشاشة: %s", saved)
    return saved


def capture_fullscreen(output_folder: Path, image_format: str = "png") -> Path:
    """يلتقط كل الشاشات مجتمعة (union) — أول عنصر في sct.monitors (index 0)."""
    try:
        import mss
    except ImportError as exc:
        raise ScreenshotError("مكتبة mss غير مثبتة") from exc

    with mss.mss() as sct:
        full = sct.monitors[0]
    return capture_region(full["left"], full["top"], full["width"], full["height"], output_folder, image_format)


def capture_monitor(monitor_index: int, output_folder: Path, image_format: str = "png") -> Path:
    """monitor_index مطابق للفهرسة المستخدمة في app.recording.sources.get_monitors (تبدأ من 1)."""
    from app.recording.sources import get_monitors

    monitors = get_monitors()
    matching = [m for m in monitors if m.index == monitor_index]
    if not matching:
        raise ScreenshotError(f"لا توجد شاشة بالفهرس: {monitor_index}")
    mon = matching[0]
    return capture_region(mon.left, mon.top, mon.width, mon.height, output_folder, image_format)


def capture_window(window_handle: int, output_folder: Path, image_format: str = "png") -> Path:
    """التقاط نافذة محددة (Windows فقط) عبر إحداثياتها الحالية."""
    from app.recording.sources import get_windows

    windows = get_windows()
    matching = [w for w in windows if w.handle == window_handle]
    if not matching:
        raise ScreenshotError("النافذة المحددة لم تعد موجودة")
    win = matching[0]
    return capture_region(win.left, win.top, win.width, win.height, output_folder, image_format)
