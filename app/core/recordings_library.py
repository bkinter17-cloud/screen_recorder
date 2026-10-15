"""
مكتبة التسجيلات السابقة (Recordings Library).

يكمل هذا الملف الجزء الذي أُجِّل سابقاً من صفحة "التسجيلات": عرض قائمة
التسجيلات، حذف، إعادة تسمية، وعرض الحجم/المدة، مرتبة حسب التاريخ.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.utils.logger import get_logger
from app.utils.process import subprocess_no_window_kwargs
from app.video.ffmpeg_manager import find_ffmpeg

logger = get_logger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm"}


class RecordingsLibraryError(Exception):
    pass


@dataclass(frozen=True)
class RecordingInfo:
    path: Path
    name: str
    size_bytes: int
    modified_at: datetime
    duration_seconds: float | None  # None إذا تعذر قراءتها (ffprobe غير متاح مثلاً)

    @property
    def size_label(self) -> str:
        mb = self.size_bytes / (1024 * 1024)
        return f"{mb:.1f} MB" if mb < 1024 else f"{mb / 1024:.2f} GB"

    @property
    def duration_label(self) -> str:
        if self.duration_seconds is None:
            return "—"
        total = int(self.duration_seconds)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    @property
    def date_label(self) -> str:
        return self.modified_at.strftime("%Y-%m-%d %H:%M")


def _probe_duration(video_path: Path) -> float | None:
    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        return None
    ffprobe_path = ffmpeg_path.replace("ffmpeg", "ffprobe")
    if not Path(ffprobe_path).is_file():
        import shutil
        ffprobe_path = shutil.which("ffprobe") or ""
    if not ffprobe_path:
        return None

    try:
        result = subprocess.run(
            [ffprobe_path, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            **subprocess_no_window_kwargs(),
        )
        return float(result.stdout.strip()) if result.stdout.strip() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        logger.warning("تعذر قراءة مدة الفيديو: %s", video_path)
        return None


def list_recordings(folder: Path) -> list[RecordingInfo]:
    """يعيد كل التسجيلات في المجلد مرتبة من الأحدث إلى الأقدم (البند 9)."""
    try:
        if not folder.exists():
            return []
        entries = list(folder.iterdir())
    except OSError as exc:
        logger.warning("تعذر قراءة محتويات مجلد التسجيلات %s: %s", folder, exc)
        return []

    recordings: list[RecordingInfo] = []
    for path in entries:
        try:
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            stat = path.stat()
            recordings.append(RecordingInfo(
                path=path,
                name=path.name,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                duration_seconds=_probe_duration(path),
            ))
        except OSError as exc:
            logger.warning("تعذر قراءة بيانات الملف %s: %s", path, exc)
            continue

    recordings.sort(key=lambda r: r.modified_at, reverse=True)
    logger.info("تم العثور على %d تسجيل في %s", len(recordings), folder)
    return recordings


def delete_recording(path: Path) -> None:
    try:
        path.unlink()
        logger.info("تم حذف التسجيل: %s", path)
    except OSError as exc:
        logger.exception("فشل حذف التسجيل: %s", path)
        raise RecordingsLibraryError(f"تعذر حذف الملف: {exc}") from exc


def rename_recording(path: Path, new_stem: str) -> Path:
    if not new_stem.strip():
        raise RecordingsLibraryError("الاسم الجديد لا يمكن أن يكون فارغاً")

    invalid_chars = '<>:"/\\|?*'
    if any(ch in new_stem for ch in invalid_chars):
        raise RecordingsLibraryError(f"الاسم يحتوي على رموز غير مسموحة: {invalid_chars}")

    new_path = path.with_name(new_stem.strip() + path.suffix)
    if new_path.exists():
        raise RecordingsLibraryError(f"يوجد ملف آخر بهذا الاسم بالفعل: {new_path.name}")

    try:
        path.rename(new_path)
        logger.info("تم تغيير اسم التسجيل: %s -> %s", path.name, new_path.name)
        return new_path
    except OSError as exc:
        logger.exception("فشل إعادة تسمية التسجيل")
        raise RecordingsLibraryError(f"تعذرت إعادة التسمية: {exc}") from exc
