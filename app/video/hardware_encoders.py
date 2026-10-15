"""
اكتشاف واختيار مُرمِّز الفيديو (Hardware Encoding) — Phase 10.

مجرد ظهور اسم مُرمِّز في مخرجات `ffmpeg -encoders` لا يعني أنه سيعمل فعلياً
(قد يكون FFmpeg مبنياً بدعم NVENC لكن لا توجد بطاقة NVIDIA فعلية على هذا
الجهاز). لذلك، لا نكتفي بالقائمة النصية، بل "نُجرّب" كل مُرمِّز عملياً
بترميز بضعة إطارات فعلياً عبر FFmpeg (lavfi testsrc)، ونعتبره متاحاً فقط
إذا نجحت العملية فعلاً (returncode == 0).

هذا يحقق البند 32 من المواصفات: "لا تخترع أسماء functions أو APIs" —
هنا نتحقق عملياً بدل الافتراض.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum

from app.utils.logger import get_logger
from app.utils.process import subprocess_no_window_kwargs
from app.video.ffmpeg_manager import list_available_encoders

logger = get_logger(__name__)


class EncoderBackend(str, Enum):
    AUTO = "auto"
    SOFTWARE = "software"
    NVIDIA = "nvidia"
    INTEL = "intel"
    AMD = "amd"


ENCODER_NAMES: dict[EncoderBackend, dict[str, str]] = {
    EncoderBackend.SOFTWARE: {"h264": "libx264", "h265": "libx265"},
    EncoderBackend.NVIDIA: {"h264": "h264_nvenc", "h265": "hevc_nvenc"},
    EncoderBackend.INTEL: {"h264": "h264_qsv", "h265": "hevc_qsv"},
    EncoderBackend.AMD: {"h264": "h264_amf", "h265": "hevc_amf"},
}

AUTO_PRIORITY = [EncoderBackend.NVIDIA, EncoderBackend.INTEL, EncoderBackend.AMD, EncoderBackend.SOFTWARE]


@dataclass(frozen=True)
class EncoderProbeResult:
    backend: EncoderBackend
    codec_name: str
    working: bool
    detail: str = ""


def _probe_single_encoder(ffmpeg_path: str, encoder_name: str, timeout: float = 8.0) -> bool:
    cmd = [
        ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=0.5",
        "-c:v", encoder_name, "-frames:v", "5",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=False,
            **subprocess_no_window_kwargs(),
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def probe_all_encoders(ffmpeg_path: str, codec: str = "h264") -> list[EncoderProbeResult]:
    available_names = list_available_encoders(ffmpeg_path)
    results: list[EncoderProbeResult] = []

    for backend, codec_map in ENCODER_NAMES.items():
        encoder_name = codec_map.get(codec)
        if not encoder_name:
            continue

        if encoder_name not in available_names:
            results.append(EncoderProbeResult(backend, encoder_name, False, "غير مدرج في بناء FFmpeg هذا"))
            continue

        working = _probe_single_encoder(ffmpeg_path, encoder_name)
        detail = "يعمل فعلياً" if working else "مدرج لكن فشل التشغيل الفعلي (على الأرجح لا يوجد عتاد مناسب)"
        results.append(EncoderProbeResult(backend, encoder_name, working, detail))
        logger.info("فحص المُرمِّز %s (%s): %s", encoder_name, backend.value, detail)

    return results


def select_best_encoder(
    ffmpeg_path: str, preferred_backend: EncoderBackend = EncoderBackend.AUTO, codec: str = "h264",
) -> EncoderProbeResult:
    """
    يختار أفضل مُرمِّز متاح فعلياً حسب تفضيل المستخدم في الإعدادات.
    - backend محدد وغير متاح فعلياً: رجوع تلقائي لـ Software مع تحذير، بدل فشل التسجيل بالكامل.
    - Auto: يجرّب حسب ترتيب الأفضلية وينتقل لأول واحد يعمل فعلياً.
    """
    results = {r.backend: r for r in probe_all_encoders(ffmpeg_path, codec)}
    software = results.get(EncoderBackend.SOFTWARE)

    if preferred_backend != EncoderBackend.AUTO:
        chosen = results.get(preferred_backend)
        if chosen and chosen.working:
            return chosen
        logger.warning(
            "المُرمِّز المفضّل '%s' غير متاح فعلياً على هذا الجهاز، "
            "سيتم الرجوع تلقائياً إلى الترميز البرمجي (Software).",
            preferred_backend.value,
        )
        if software and software.working:
            return software
        raise RuntimeError("لا يوجد أي مُرمِّز فيديو يعمل فعلياً — حتى الترميز البرمجي (libx264) فشل")

    for backend in AUTO_PRIORITY:
        candidate = results.get(backend)
        if candidate and candidate.working:
            return candidate

    raise RuntimeError("لا يوجد أي مُرمِّز فيديو يعمل فعلياً — حتى الترميز البرمجي (libx264) فشل")
