"""
منسّق التسجيل الرئيسي (Core Orchestrator).

هذا هو الكائن الوحيد الذي يتعامل معه الـ UI: يخفي عنه تفاصيل FFmpeg
والصوت، ويوفر واجهة بسيطة: start / pause / resume / stop، بالإضافة إلى
معلومات حية (المدة، الحجم، مستوى الصوت) لعرضها في الواجهة والـ Overlay.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.audio.audio_capture import AudioCaptureSession
from app.settings.config_manager import ConfigManager
from app.utils.logger import get_logger
from app.video.ffmpeg_manager import (
    CaptureRequest,
    FFmpegError,
    FFmpegRecorder,
    RecorderState,
    find_ffmpeg,
)
from app.video.hardware_encoders import EncoderBackend, select_best_encoder

logger = get_logger(__name__)


@dataclass
class RecordingOptions:
    """الخيارات التي يجمعها الـ UI من المستخدم قبل بدء التسجيل."""

    output_folder: Path
    filename_stem: str  # بدون امتداد — يُبنى حسب filename_template
    left: int
    top: int
    width: int
    height: int
    fps: int = 30
    video_codec: str = "libx264"
    bitrate_kbps: int = 8000
    container: str = "mp4"
    microphone_device_id: str | None = None
    system_audio_device_id: str | None = None
    microphone_volume: float = 1.0
    system_audio_volume: float = 1.0


class RecordingController:
    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        ffmpeg_path = find_ffmpeg(config.get("advanced", "ffmpeg_path"))
        if not ffmpeg_path:
            raise FFmpegError(
                "لم يتم العثور على FFmpeg. الرجاء تثبيته أو تحديد مساره من الإعدادات."
            )
        self._ffmpeg_path = ffmpeg_path
        self._video = FFmpegRecorder(ffmpeg_path)
        self._audio: AudioCaptureSession | None = None
        self._audio_wav_path: Path | None = None

    @property
    def state(self) -> RecorderState:
        return self._video.state

    def start(self, opts: RecordingOptions) -> None:
        try:
            opts.output_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("تعذر إنشاء مجلد حفظ التسجيلات %s: %s", opts.output_folder, exc)
            raise FFmpegError(
                f"تعذر إنشاء مجلد حفظ التسجيلات:\n{opts.output_folder}\n\nالسبب: {exc}\n"
                "يرجى التحقق من صلاحيات المجلد أو تغييره من الإعدادات."
            ) from exc
        base_path = self._unique_base_path(opts.output_folder / opts.filename_stem, opts.container)

        # اختيار مُرمِّز يعمل فعلياً على هذا الجهاز حسب تفضيل المستخدم في الإعدادات
        # (Auto/Software/NVIDIA/Intel/AMD)، مع رجوع تلقائي آمن للبرمجي عند الفشل (Phase 10).
        try:
            preferred = EncoderBackend(self.config.get("recording", "encoder", "auto"))
        except ValueError:
            logger.warning("قيمة المُرمِّز المحفوظة غير صالحة؛ سيتم استخدام الاختيار التلقائي")
            preferred = EncoderBackend.AUTO
        try:
            encoder_result = select_best_encoder(self._ffmpeg_path, preferred, "h264")
            resolved_codec = encoder_result.codec_name
        except RuntimeError as exc:
            raise FFmpegError(f"تعذر إيجاد أي مُرمِّز فيديو يعمل على هذا الجهاز: {exc}") from exc

        container = opts.container.lower().lstrip(".")
        if container not in {"mp4", "mkv", "webm"}:
            logger.warning("صيغة إخراج غير صالحة '%s'؛ سيتم استخدام MP4", opts.container)
            container = "mp4"

        req = CaptureRequest(
            output_path=base_path,
            fps=opts.fps,
            left=opts.left,
            top=opts.top,
            width=opts.width,
            height=opts.height,
            video_codec=resolved_codec,
            bitrate_kbps=opts.bitrate_kbps,
            container=container,
        )

        wants_audio = bool(opts.microphone_device_id or opts.system_audio_device_id)
        if wants_audio:
            self._audio_wav_path = base_path.with_suffix(".audio.wav")
            self._audio = AudioCaptureSession(
                output_wav_path=self._audio_wav_path,
                microphone_device_id=opts.microphone_device_id,
                system_audio_device_id=opts.system_audio_device_id,
                microphone_volume=opts.microphone_volume,
                system_audio_volume=opts.system_audio_volume,
            )
        else:
            self._audio = None
            self._audio_wav_path = None

        # الفيديو أولاً حتى لا نفقد لقطات بداية التسجيل، ثم الصوت مباشرة بعده
        self._video.start(req)
        if self._audio:
            try:
                self._audio.start()
            except Exception as exc:  # noqa: BLE001
                # Do not leave a hidden video recording running when an audio
                # device cannot be opened.
                try:
                    self._video.stop()
                except FFmpegError:
                    logger.exception("تعذر إيقاف الفيديو بعد فشل بدء الصوت")
                self._audio = None
                self._audio_wav_path = None
                raise FFmpegError(f"تعذر بدء تسجيل الصوت: {exc}") from exc

        logger.info("بدأ التسجيل الكامل (صوت=%s)", wants_audio)

    def pause(self) -> None:
        self._video.pause()
        if self._audio:
            self._audio.pause()

    def resume(self) -> None:
        self._video.resume()
        if self._audio:
            self._audio.resume()

    def stop(self) -> Path:
        audio_wav = None
        if self._audio:
            audio_wav = self._audio.stop()
            self._audio = None

        final_path = self._video.stop(audio_wav_path=audio_wav)
        logger.info("انتهى التسجيل: %s", final_path)
        return final_path

    def set_microphone_muted(self, muted: bool) -> None:
        if self._audio:
            self._audio.set_muted(muted)

    # ------------------------------------------------------------------ #
    # معلومات حية للواجهة
    # ------------------------------------------------------------------ #
    def elapsed_seconds(self) -> float:
        return self._video.elapsed_seconds()

    def current_size_bytes(self) -> int:
        return self._video.current_output_size_bytes()

    def audio_levels(self) -> dict[str, float]:
        return self._audio.get_levels() if self._audio else {}

    @staticmethod
    def _unique_base_path(base_path: Path, container: str) -> Path:
        """Avoid replacing a recording when two sessions begin in one second."""
        candidate = base_path
        suffix = 2
        while any(
            path.exists()
            for path in (
                candidate.with_suffix(f".{container}"),
                candidate.with_suffix(".recording.mkv"),
                candidate.with_suffix(".audio.wav"),
            )
        ):
            candidate = base_path.with_name(f"{base_path.name}_{suffix}")
            suffix += 1
        return candidate
