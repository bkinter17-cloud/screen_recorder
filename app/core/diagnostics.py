"""
تشخيص النظام (Diagnostics) — Phase 11.

يجمع معلومات حقيقية عن الجهاز والبيئة لعرضها في صفحة Diagnostics:
إصدار Python، نظام التشغيل، المعالج، الذاكرة، الشاشات، أجهزة الصوت،
الكاميرات، FFmpeg وإصداره، والمُرمِّزات المتاحة فعلياً.

لا توجد أي بيانات تُرسل لأي مكان — كل شيء يُعرض محلياً فقط للمستخدم
(البند 23: "لا ترسل أي بيانات إلى الإنترنت").
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DiagnosticsReport:
    python_version: str = ""
    os_name: str = ""
    cpu_name: str = ""
    cpu_cores: int = 0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    monitors: list[str] = field(default_factory=list)
    microphones: list[str] = field(default_factory=list)
    system_audio_devices: list[str] = field(default_factory=list)
    cameras: list[str] = field(default_factory=list)
    ffmpeg_found: bool = False
    ffmpeg_version: str = "غير موجود"
    ffmpeg_path: str = "—"
    working_encoders: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        """نص قابل للنسخ (زر Copy Diagnostics في المواصفات)."""
        lines = [
            "=== Screen Recorder — Diagnostics ===",
            f"Python: {self.python_version}",
            f"OS: {self.os_name}",
            f"CPU: {self.cpu_name} ({self.cpu_cores} cores)",
            f"RAM: {self.ram_available_gb:.1f} / {self.ram_total_gb:.1f} GB متاحة",
            "",
            f"FFmpeg: {'موجود' if self.ffmpeg_found else 'غير موجود'} — {self.ffmpeg_version}",
            f"مسار FFmpeg: {self.ffmpeg_path}",
            f"المُرمِّزات العاملة فعلياً: {', '.join(self.working_encoders) or 'لا شيء'}",
            "",
            f"الشاشات ({len(self.monitors)}): " + (", ".join(self.monitors) or "لا شيء"),
            f"الميكروفونات ({len(self.microphones)}): " + (", ".join(self.microphones) or "لا شيء"),
            f"مصادر صوت النظام ({len(self.system_audio_devices)}): " + (", ".join(self.system_audio_devices) or "لا شيء"),
            f"الكاميرات ({len(self.cameras)}): " + (", ".join(self.cameras) or "لا شيء"),
        ]
        return "\n".join(lines)


def run_diagnostics() -> DiagnosticsReport:
    report = DiagnosticsReport()

    # --- Python / OS / CPU / RAM ---
    report.python_version = platform.python_version()
    report.os_name = platform.platform()

    try:
        import psutil
        report.cpu_cores = psutil.cpu_count(logical=True) or 0
        mem = psutil.virtual_memory()
        report.ram_total_gb = mem.total / (1024**3)
        report.ram_available_gb = mem.available / (1024**3)
    except Exception:  # noqa: BLE001
        logger.exception("فشل جمع معلومات CPU/RAM")

    report.cpu_name = platform.processor() or "غير معروف"

    # --- الشاشات ---
    try:
        from app.recording.sources import get_monitors
        report.monitors = [m.label for m in get_monitors()]
    except Exception:  # noqa: BLE001
        logger.exception("فشل جمع معلومات الشاشات")

    # --- الصوت ---
    try:
        from app.audio.audio_devices import list_microphones, list_system_audio_devices
        report.microphones = [d.name for d in list_microphones()]
        report.system_audio_devices = [d.name for d in list_system_audio_devices()]
    except Exception:  # noqa: BLE001
        logger.exception("فشل جمع معلومات الصوت")

    # --- الكاميرات ---
    try:
        from app.webcam.webcam_capture import list_cameras
        report.cameras = [c.name for c in list_cameras()]
    except Exception:  # noqa: BLE001
        logger.exception("فشل جمع معلومات الكاميرات")

    # --- FFmpeg والمُرمِّزات ---
    try:
        from app.video.ffmpeg_manager import find_ffmpeg, get_ffmpeg_version
        from app.video.hardware_encoders import probe_all_encoders

        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            report.ffmpeg_found = True
            report.ffmpeg_path = ffmpeg_path
            report.ffmpeg_version = get_ffmpeg_version(ffmpeg_path) or "غير معروف"
            results = probe_all_encoders(ffmpeg_path, "h264")
            report.working_encoders = [r.codec_name for r in results if r.working]
    except Exception:  # noqa: BLE001
        logger.exception("فشل جمع معلومات FFmpeg")

    logger.info("تم تشغيل Diagnostics بنجاح")
    return report
