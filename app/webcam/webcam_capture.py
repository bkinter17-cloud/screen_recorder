"""
كاميرا الويب فوق التسجيل (Webcam Overlay) — Phase 8.

ميزة اختيارية بالكامل (mouse/config: webcam.enabled). عند تعطيلها، لا يتم
استيراد OpenCV أصلاً ولا تُفتح أي كاميرا — صفر تأثير على التسجيل العادي،
تماشياً مع المواصفات: "يجب أن تكون هذه الميزة اختيارية ولا تؤثر على
التسجيل العادي عند تعطيلها".

يستخدم OpenCV لالتقاط الكاميرا فقط (بدون إعادة اختراع أي ترميز فيديو —
الدمج مع الشاشة يتم بصرياً فقط عبر نافذة عائمة شفافة الخلفية تُلتقط هي
نفسها ضمن منطقة التسجيل، وليس عبر دمج بيانات الفيديو داخل بايثون).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum

from app.utils.logger import get_logger

logger = get_logger(__name__)


class WebcamError(Exception):
    pass


class WebcamPosition(str, Enum):
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CUSTOM = "custom"  # بعد تحريك المستخدم لها يدوياً


@dataclass(frozen=True)
class CameraInfo:
    index: int
    name: str


def list_cameras(max_probe: int = 5) -> list[CameraInfo]:
    """
    يفحص أول `max_probe` فهارس كاميرا ويعيد فقط الفهارس التي تفتح فعلياً.
    OpenCV لا يوفر أسماء أجهزة حقيقية على كل الأنظمة، لذلك نستخدم تسمية
    عامة (كاميرا 0، كاميرا 1 ...) عند عدم توفر اسم حقيقي.
    """
    try:
        import cv2
        try:
            cv2.setLogLevel(0)  # إسكات تحذيرات "camera not found" — غير متاح في كل نسخ OpenCV
        except AttributeError:
            pass
    except ImportError:
        logger.error("مكتبة OpenCV غير مثبتة — لا يمكن اكتشاف الكاميرات")
        return []

    cameras: list[CameraInfo] = []
    for idx in range(max_probe):
        cap = cv2.VideoCapture(idx)
        try:
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    cameras.append(CameraInfo(idx, f"كاميرا {idx}"))
        finally:
            cap.release()

    logger.info("تم اكتشاف %d كاميرا", len(cameras))
    return cameras


class WebcamCaptureThread(threading.Thread):
    """
    Thread خلفي يقرأ إطارات الكاميرا باستمرار ويحتفظ بآخر إطار فقط
    (لا حاجة لقائمة انتظار — العرض الحي يهتم فقط بأحدث صورة).
    """

    def __init__(self, camera_index: int) -> None:
        super().__init__(daemon=True, name=f"WebcamCapture-{camera_index}")
        self.camera_index = camera_index
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_frame = None  # numpy array (BGR) أو None
        self.error: Exception | None = None

    def run(self) -> None:
        try:
            import cv2
        except ImportError as exc:
            self.error = exc
            logger.error("تعذر استيراد OpenCV لبدء التقاط الكاميرا")
            return

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error = WebcamError(f"تعذر فتح الكاميرا رقم {self.camera_index}")
            logger.error(str(self.error))
            return

        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    continue
                with self._lock:
                    self._latest_frame = frame
        finally:
            cap.release()

    def get_latest_frame(self):
        with self._lock:
            return None if self._latest_frame is None else self._latest_frame.copy()

    def stop(self) -> None:
        self._stop_event.set()


def compute_overlay_geometry(
    position: WebcamPosition,
    screen_width: int, screen_height: int,
    overlay_width: int, overlay_height: int,
    margin: int = 24,
) -> tuple[int, int]:
    """يحسب إحداثيات (x, y) لنافذة الـ overlay حسب الموضع المختار من المستخدم."""
    if position == WebcamPosition.TOP_LEFT:
        return margin, margin
    if position == WebcamPosition.TOP_RIGHT:
        return screen_width - overlay_width - margin, margin
    if position == WebcamPosition.BOTTOM_LEFT:
        return margin, screen_height - overlay_height - margin
    if position == WebcamPosition.BOTTOM_RIGHT:
        return screen_width - overlay_width - margin, screen_height - overlay_height - margin
    raise WebcamError("لا يمكن حساب موضع تلقائي لوضع CUSTOM — يُترك للمستخدم تحريكه يدوياً")
