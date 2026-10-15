"""
جلسة التقاط الصوت الحية (Phase 4).

تدعم:
- تسجيل الميكروفون فقط، صوت النظام فقط، أو كليهما معاً (بالمزج الحي).
- عرض مستوى الصوت اللحظي (VU Meter) لكل مصدر.
- كتم الميكروفون أثناء التسجيل (Mute) دون إيقاف صوت النظام.
- التحكم بمستوى الصوت (Volume) لكل مصدر بشكل مستقل.
- إيقاف مؤقت/استئناف (لا يُكتب أي صوت أثناء الإيقاف المؤقت، لتبقى مدة
  ملف الصوت متوافقة تقريباً مع مدة الفيديو الموقوف مؤقتاً).

الناتج: ملف WAV خام (PCM 16-bit) يُدمج مع الفيديو في خطوة الدمج النهائية
(app/core/recording_controller.py)، بدون أي ترميز يعاد اختراعه هنا —
الترميز النهائي (AAC) يقوم به FFmpeg فقط عند الدمج.
"""

from __future__ import annotations

import sys
import threading
import wave
from pathlib import Path

import numpy as np

from app.utils.logger import get_logger

logger = get_logger(__name__)

if len(sys.argv) < 2:
    sys.argv = sys.argv + ["screen_recorder"]

SAMPLE_RATE = 48000
CHANNELS = 2
BLOCK_SIZE = 1024  # عدد العينات لكل قراءة — قيمة صغيرة لاستجابة VU meter سريعة


class AudioCaptureError(Exception):
    pass


class _DeviceReader(threading.Thread):
    """Thread يقرأ باستمرار من جهاز صوت واحد (ميكروفون أو loopback) ويحدّث آخر قطعة مسجلة."""

    def __init__(self, device_id: str, name: str) -> None:
        super().__init__(daemon=True, name=f"AudioReader-{name}")
        self.device_id = device_id
        self.name_label = name
        self._stop_event = threading.Event()
        self.latest_chunk: np.ndarray = np.zeros((BLOCK_SIZE, CHANNELS), dtype=np.float32)
        self.level: float = 0.0  # RMS 0..1 لعرض VU meter
        self._lock = threading.Lock()
        self._error: Exception | None = None

    def run(self) -> None:
        import soundcard as sc

        try:
            device = sc.get_microphone(id=self.device_id, include_loopback=True)
        except Exception as exc:  # noqa: BLE001
            self._error = exc
            logger.exception("فشل فتح جهاز الصوت: %s", self.name_label)
            return

        try:
            with device.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=BLOCK_SIZE) as rec:
                while not self._stop_event.is_set():
                    chunk = rec.record(numframes=BLOCK_SIZE)  # shape: (frames, channels), float32 [-1,1]
                    rms = float(np.sqrt(np.mean(np.square(chunk)))) if chunk.size else 0.0
                    with self._lock:
                        self.latest_chunk = chunk
                        self.level = min(1.0, rms * 4.0)  # تكبير بسيط لعرض أوضح في الـ VU meter
        except Exception as exc:  # noqa: BLE001
            self._error = exc
            logger.exception("خطأ أثناء القراءة من جهاز الصوت: %s", self.name_label)

    def get_chunk(self) -> np.ndarray:
        with self._lock:
            return self.latest_chunk.copy()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def error(self) -> Exception | None:
        return self._error


class AudioCaptureSession:
    """
    ينسّق قراءة مصدر واحد أو اثنين (ميكروفون + صوت النظام)، يمزجهما حسب
    الإعدادات، ويكتب الناتج إلى ملف WAV خام مستمر.
    """

    def __init__(
        self,
        output_wav_path: Path,
        microphone_device_id: str | None = None,
        system_audio_device_id: str | None = None,
        microphone_volume: float = 1.0,
        system_audio_volume: float = 1.0,
    ) -> None:
        if not microphone_device_id and not system_audio_device_id:
            raise AudioCaptureError("يجب تحديد ميكروفون أو مصدر صوت نظام واحد على الأقل")

        self.output_wav_path = output_wav_path
        self.microphone_volume = microphone_volume
        self.system_audio_volume = system_audio_volume
        self.muted = False

        self._mic_reader = _DeviceReader(microphone_device_id, "microphone") if microphone_device_id else None
        self._sys_reader = _DeviceReader(system_audio_device_id, "system_audio") if system_audio_device_id else None

        self._writer_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._wav_file: wave.Wave_write | None = None
        self._frames_written = 0

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self.output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        self._wav_file = wave.open(str(self.output_wav_path), "wb")
        self._wav_file.setnchannels(CHANNELS)
        self._wav_file.setsampwidth(2)  # 16-bit
        self._wav_file.setframerate(SAMPLE_RATE)

        if self._mic_reader:
            self._mic_reader.start()
        if self._sys_reader:
            self._sys_reader.start()

        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True, name="AudioWriter")
        self._writer_thread.start()
        logger.info(
            "بدأ التقاط الصوت (ميكروفون=%s، صوت النظام=%s)",
            bool(self._mic_reader), bool(self._sys_reader),
        )

    def _writer_loop(self) -> None:
        import time

        block_duration = BLOCK_SIZE / SAMPLE_RATE
        while not self._stop_event.is_set():
            time.sleep(block_duration)
            if self._paused.is_set():
                continue

            mic_chunk = None
            sys_chunk = None

            if self._mic_reader and not self.muted:
                mic_chunk = self._mic_reader.get_chunk() * self.microphone_volume
            if self._sys_reader:
                sys_chunk = self._sys_reader.get_chunk() * self.system_audio_volume

            if mic_chunk is not None and sys_chunk is not None:
                mixed = np.clip(mic_chunk + sys_chunk, -1.0, 1.0)
            elif mic_chunk is not None:
                mixed = mic_chunk
            elif sys_chunk is not None:
                mixed = sys_chunk
            else:
                mixed = np.zeros((BLOCK_SIZE, CHANNELS), dtype=np.float32)

            pcm16 = (np.clip(mixed, -1.0, 1.0) * 32767.0).astype(np.int16)
            if self._wav_file:
                self._wav_file.writeframes(pcm16.tobytes())
                self._frames_written += len(pcm16)

    # ------------------------------------------------------------------ #
    def pause(self) -> None:
        self._paused.set()
        logger.info("تم إيقاف تسجيل الصوت مؤقتاً")

    def resume(self) -> None:
        self._paused.clear()
        logger.info("تم استئناف تسجيل الصوت")

    def set_muted(self, muted: bool) -> None:
        self.muted = muted

    def get_levels(self) -> dict[str, float]:
        levels = {}
        if self._mic_reader:
            levels["microphone"] = 0.0 if self.muted else self._mic_reader.level
        if self._sys_reader:
            levels["system_audio"] = self._sys_reader.level
        return levels

    def stop(self) -> Path:
        self._stop_event.set()
        if self._writer_thread:
            self._writer_thread.join(timeout=3)
        if self._mic_reader:
            self._mic_reader.stop()
        if self._sys_reader:
            self._sys_reader.stop()
        if self._wav_file:
            self._wav_file.close()

        duration = self._frames_written / SAMPLE_RATE if SAMPLE_RATE else 0
        logger.info("تم إيقاف تسجيل الصوت — المدة المسجلة: %.2f ثانية", duration)

        for reader in (self._mic_reader, self._sys_reader):
            if reader is not None and reader.error is not None:
                logger.error("حدث خطأ في أحد مصادر الصوت أثناء التسجيل: %s", reader.error)

        return self.output_wav_path
