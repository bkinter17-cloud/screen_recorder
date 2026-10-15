"""
طبقة التكامل مع FFmpeg (Phase 3).

هذه الطبقة هي المسؤولة الوحيدة عن:
- اكتشاف FFmpeg وإصداره.
- بناء أمر FFmpeg المناسب لالتقاط الشاشة (gdigrab على Windows، x11grab على
  Linux للاختبار في هذه البيئة، avfoundation على macOS).
- إدارة عملية FFmpeg (بدء / إيقاف مؤقت عبر تعليق العملية / استئناف / إنهاء آمن).
- التسجيل أولاً إلى ملف MKV مؤقت (أكثر أماناً عند الانقطاع المفاجئ لأنه
  self-contained حتى لو لم يُغلق بشكل صحيح)، ثم تحويله (remux بدون إعادة
  ترميز) إلى الصيغة النهائية التي اختارها المستخدم بعد انتهاء التسجيل.

لا يعيد هذا الملف اختراع أي محرك ترميز فيديو — كل المعالجة الفعلية تتم داخل
FFmpeg نفسه عبر subprocess.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import psutil

from app.utils.logger import get_logger
from app.utils.process import subprocess_no_window_kwargs

logger = get_logger(__name__)


class RecorderState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class FFmpegError(Exception):
    """يُرفع عند أي فشل متعلق بـ FFmpeg (غير موجود، فشل بدء، فشل إنهاء ...)."""


@dataclass
class CaptureRequest:
    """كل ما يلزم لبناء أمر FFmpeg لجلسة تسجيل واحدة."""

    output_path: Path
    fps: int = 30
    # منطقة الالتقاط (لكامل الشاشة استخدم أبعاد الشاشة نفسها)
    left: int = 0
    top: int = 0
    width: int = 1920
    height: int = 1080
    video_codec: str = "libx264"  # قد تُستبدل تلقائياً بمرمّز Hardware (Phase 10)
    bitrate_kbps: int = 8000
    audio_inputs: list[str] = field(default_factory=list)  # يُستخدم في Phase 4
    container: str = "mp4"  # الصيغة النهائية المطلوبة من المستخدم


def find_ffmpeg(explicit_path: str | None = None) -> str | None:
    """
    يبحث عن ffmpeg: أولاً في المسار الذي حدده المستخدم في الإعدادات (إن وُجد)،
    ثم في PATH النظام.
    """
    if explicit_path:
        candidate = Path(explicit_path)
        if candidate.is_file():
            return str(candidate)
        logger.warning("مسار FFmpeg المحدد في الإعدادات غير صالح: %s", explicit_path)

    # The release build ships FFmpeg alongside the application.  Check that
    # predictable location before falling back to the system PATH.
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        executable_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
        bundled = bundle_root / "bin" / executable_name
        if bundled.is_file():
            return str(bundled)

    found = shutil.which("ffmpeg")
    if found:
        return found

    logger.error("لم يتم العثور على FFmpeg لا في الإعدادات ولا في PATH")
    return None


def get_ffmpeg_version(ffmpeg_path: str) -> str | None:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            **subprocess_no_window_kwargs(),
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        match = re.search(r"ffmpeg version (\S+)", first_line)
        return match.group(1) if match else first_line or None
    except (OSError, subprocess.SubprocessError):
        logger.exception("فشل الحصول على إصدار FFmpeg")
        return None


def list_available_encoders(ffmpeg_path: str) -> set[str]:
    """يعيد أسماء كل الـ encoders المتاحة في هذا الـ build من FFmpeg."""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            **subprocess_no_window_kwargs(),
        )
        encoders = set()
        for line in result.stdout.splitlines():
            match = re.match(r"^\s*[VAS.][F.][S.][X.][B.][D.]\s+(\S+)", line)
            if match:
                encoders.add(match.group(1))
        return encoders
    except (OSError, subprocess.SubprocessError):
        logger.exception("فشل الحصول على قائمة الـ encoders")
        return set()


def _video_input_args(req: CaptureRequest) -> list[str]:
    """
    يبني وسائط input الخاصة بالتقاط الشاشة حسب نظام التشغيل.
    Windows -> gdigrab (المطلوب فعلياً في الإنتاج)
    Linux   -> x11grab (تُستخدم فقط لاختبار طبقة FFmpeg في بيئة التطوير هذه)
    macOS   -> avfoundation
    """
    if sys.platform.startswith("win"):
        return [
            "-f", "gdigrab",
            "-framerate", str(req.fps),
            "-offset_x", str(req.left),
            "-offset_y", str(req.top),
            "-video_size", f"{req.width}x{req.height}",
            "-i", "desktop",
        ]
    if sys.platform.startswith("linux"):
        display = ":0.0"
        return [
            "-f", "x11grab",
            "-framerate", str(req.fps),
            "-video_size", f"{req.width}x{req.height}",
            "-i", f"{display}+{req.left},{req.top}",
        ]
    if sys.platform == "darwin":
        return [
            "-f", "avfoundation",
            "-framerate", str(req.fps),
            "-i", "1:none",
        ]
    raise FFmpegError(f"نظام تشغيل غير مدعوم لالتقاط الشاشة: {sys.platform}")


def build_ffmpeg_command(ffmpeg_path: str, req: CaptureRequest, temp_output: Path) -> list[str]:
    cmd: list[str] = [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "warning"]
    cmd += _video_input_args(req)
    cmd += list(req.audio_inputs)  # Phase 4 سيملأ هذه القائمة بوسائط input الصوت

    cmd += ["-c:v", req.video_codec]
    if req.video_codec in ("libx264", "libx265"):
        cmd += ["-preset", "veryfast", "-pix_fmt", "yuv420p"]
    cmd += ["-b:v", f"{req.bitrate_kbps}k"]

    if req.audio_inputs:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    # التسجيل دائماً إلى MKV مؤقت أولاً (Recovery - البند 20)
    cmd += [str(temp_output)]
    return cmd


class FFmpegRecorder:
    """
    يدير دورة حياة عملية FFmpeg الخاصة بجلسة تسجيل واحدة.

    ملاحظة مهمة حول Pause/Resume: FFmpeg نفسه لا يدعم إيقافاً مؤقتاً حقيقياً
    لالتقاط الشاشة الحي. الحل المعتمد هنا هو تعليق (suspend) عملية FFmpeg نفسها
    عبر psutil (يعمل على Windows وLinux)، مما يوقف كل استهلاك CPU/كتابة الملف
    فعلياً أثناء الإيقاف المؤقت. النتيجة: توقف زمني بسيط في الفيديو عند
    الاستئناف، وهو سلوك مقبول ومستخدم فعلياً في أدوات مشابهة بسيطة.
    """

    def __init__(self, ffmpeg_path: str) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.state: RecorderState = RecorderState.IDLE
        self._process: subprocess.Popen | None = None
        self._psutil_process: psutil.Process | None = None
        self._temp_output: Path | None = None
        self._final_output: Path | None = None
        self._start_time: float | None = None
        self._paused_accum: float = 0.0
        self._pause_started_at: float | None = None
        # FFmpeg writes warnings to stderr throughout a recording.  Leaving that
        # pipe unread eventually blocks the encoder once its OS buffer is full.
        self._stderr_tail = ""
        self._stderr_lock = threading.Lock()
        self._stderr_thread: threading.Thread | None = None

    def _drain_stderr(self) -> None:
        """Continuously consume FFmpeg diagnostics while retaining a useful tail."""
        if not self._process or not self._process.stderr:
            return
        try:
            for line in iter(self._process.stderr.readline, b""):
                text = line.decode(errors="replace")
                with self._stderr_lock:
                    self._stderr_tail = (self._stderr_tail + text)[-8192:]
        except OSError:
            # The pipe can be closed as part of a forced shutdown.
            pass

    def _last_stderr(self) -> str:
        with self._stderr_lock:
            return self._stderr_tail.strip()

    # ------------------------------------------------------------------ #
    def start(self, req: CaptureRequest) -> None:
        if self.state != RecorderState.IDLE:
            raise FFmpegError(f"لا يمكن بدء تسجيل جديد أثناء الحالة: {self.state}")

        req.output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = req.output_path.with_suffix(".recording.mkv")
        cmd = build_ffmpeg_command(self.ffmpeg_path, req, temp_output)

        logger.info("أمر FFmpeg: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                **subprocess_no_window_kwargs(),
            )
        except OSError as exc:
            self.state = RecorderState.ERROR
            logger.exception("فشل بدء عملية FFmpeg")
            raise FFmpegError(f"تعذر بدء FFmpeg: {exc}") from exc

        self._stderr_tail = ""
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, daemon=True, name="FFmpegStderrDrain"
        )
        self._stderr_thread.start()

        # تأكد أن العملية لم تنهر فوراً (خطأ في الوسائط مثلاً)
        time.sleep(0.3)
        if self._process.poll() is not None:
            if self._stderr_thread:
                self._stderr_thread.join(timeout=1)
            stderr = self._last_stderr()
            self._process = None
            self._stderr_thread = None
            # A failed start must not lock the user out of retrying after
            # changing a source or setting.
            self.state = RecorderState.IDLE
            logger.error("توقفت عملية FFmpeg فوراً بعد البدء: %s", stderr)
            raise FFmpegError(f"فشل بدء التسجيل: {stderr.strip()[-500:]}")

        self._psutil_process = psutil.Process(self._process.pid)
        self._temp_output = temp_output
        self._final_output = req.output_path.with_suffix(f".{req.container}")
        self._start_time = time.monotonic()
        self._paused_accum = 0.0
        self.state = RecorderState.RECORDING
        logger.info("بدأ التسجيل بنجاح -> %s", temp_output)

    def pause(self) -> None:
        if self.state != RecorderState.RECORDING:
            raise FFmpegError("لا يمكن الإيقاف المؤقت إلا أثناء التسجيل")
        assert self._psutil_process is not None
        try:
            self._psutil_process.suspend()
        except psutil.Error as exc:
            logger.exception("فشل تعليق عملية FFmpeg")
            raise FFmpegError(f"فشل الإيقاف المؤقت: {exc}") from exc
        self._pause_started_at = time.monotonic()
        self.state = RecorderState.PAUSED
        logger.info("تم إيقاف التسجيل مؤقتاً")

    def resume(self) -> None:
        if self.state != RecorderState.PAUSED:
            raise FFmpegError("لا يمكن الاستئناف إلا من حالة الإيقاف المؤقت")
        assert self._psutil_process is not None
        try:
            self._psutil_process.resume()
        except psutil.Error as exc:
            logger.exception("فشل استئناف عملية FFmpeg")
            raise FFmpegError(f"فشل الاستئناف: {exc}") from exc
        if self._pause_started_at is not None:
            self._paused_accum += time.monotonic() - self._pause_started_at
            self._pause_started_at = None
        self.state = RecorderState.RECORDING
        logger.info("تم استئناف التسجيل")

    def stop(self, timeout: float = 10.0, audio_wav_path: Path | None = None) -> Path:
        """
        يوقف FFmpeg بشكل آمن (يرسل 'q' عبر stdin وهي الطريقة الموصى بها رسمياً
        لإنهاء FFmpeg بأمان بدلاً من kill المفاجئ الذي قد يُتلف الملف)،
        ثم يحوّل الملف المؤقت (MKV) إلى الصيغة النهائية عبر remux بدون إعادة ترميز.
        إذا تم تمرير audio_wav_path (من app.audio)، يتم دمج الصوت مع الفيديو
        في نفس خطوة التحويل النهائية.
        """
        if self.state not in (RecorderState.RECORDING, RecorderState.PAUSED):
            raise FFmpegError(f"لا يوجد تسجيل نشط لإيقافه (الحالة الحالية: {self.state})")

        self.state = RecorderState.STOPPING
        assert self._process is not None and self._psutil_process is not None

        # إن كانت العملية معلّقة (paused) يجب استئنافها أولاً قبل إرسال أمر الإيقاف
        try:
            if self._psutil_process.status() == psutil.STATUS_STOPPED:
                self._psutil_process.resume()
        except psutil.Error:
            pass

        try:
            if self._process.stdin:
                self._process.stdin.write(b"q")
                self._process.stdin.flush()
            self._process.wait(timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            logger.warning("لم يستجب FFmpeg للإيقاف الآمن، سيتم إنهاؤه قسراً")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

        logger.info("توقفت عملية FFmpeg (return code=%s)", self._process.returncode)

        if self._stderr_thread:
            self._stderr_thread.join(timeout=1)

        final_path = self._remux_to_final_format(audio_wav_path)
        self.state = RecorderState.IDLE
        self._process = None
        self._psutil_process = None
        self._stderr_thread = None
        return final_path

    def _remux_to_final_format(self, audio_wav_path: Path | None) -> Path:
        assert self._temp_output is not None and self._final_output is not None
        temp_output, final_output = self._temp_output, self._final_output

        if not temp_output.exists() or temp_output.stat().st_size == 0:
            raise FFmpegError("الملف المؤقت للتسجيل فارغ أو غير موجود — فشل التسجيل")

        cmd = [self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "warning", "-i", str(temp_output)]

        has_audio = bool(audio_wav_path and audio_wav_path.exists() and audio_wav_path.stat().st_size > 44)
        if has_audio:
            cmd += ["-i", str(audio_wav_path)]
        if final_output.suffix.lower() == ".webm":
            # WebM does not accept the H.264/AAC streams produced for the
            # temporary MKV, so a real conversion is required here.
            cmd += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32"]
            if has_audio:
                cmd += ["-c:a", "libopus", "-b:a", "128k", "-shortest"]
            else:
                cmd += ["-an"]
        elif has_audio:
            cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        else:
            cmd += ["-c", "copy"]
        cmd += [str(final_output)]

        logger.info("تحويل/دمج الملف النهائي: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            **subprocess_no_window_kwargs(),
        )

        if result.returncode != 0 or not final_output.exists():
            # حماية: إذا فشل التحويل، أبقِ الملف المؤقت كما هو بدل فقدان التسجيل بالكامل
            logger.error("فشل تحويل/دمج الصيغة، سيبقى الملف بصيغة MKV المؤقتة (بدون صوت): %s", result.stderr)
            return temp_output

        temp_output.unlink(missing_ok=True)
        if has_audio and audio_wav_path:
            audio_wav_path.unlink(missing_ok=True)
        logger.info("تم حفظ التسجيل النهائي: %s", final_output)
        return final_output

    # ------------------------------------------------------------------ #
    def elapsed_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        paused_extra = 0.0
        if self._pause_started_at is not None:
            paused_extra = time.monotonic() - self._pause_started_at
        return time.monotonic() - self._start_time - self._paused_accum - paused_extra

    def current_output_size_bytes(self) -> int:
        if self._temp_output and self._temp_output.exists():
            return self._temp_output.stat().st_size
        return 0
