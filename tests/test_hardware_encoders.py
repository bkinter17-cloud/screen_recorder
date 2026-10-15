"""اختبارات وحدة لاكتشاف المُرمِّزات — تُجري فحصاً حقيقياً عبر FFmpeg (libx264 يجب أن يعمل دائماً)."""

from __future__ import annotations

import pytest

from app.video.ffmpeg_manager import find_ffmpeg
from app.video.hardware_encoders import EncoderBackend, probe_all_encoders, select_best_encoder


@pytest.fixture(scope="module")
def ffmpeg_path():
    path = find_ffmpeg()
    assert path is not None
    return path


def test_software_encoder_always_works(ffmpeg_path):
    results = probe_all_encoders(ffmpeg_path, codec="h264")
    software = next(r for r in results if r.backend == EncoderBackend.SOFTWARE)
    assert software.working is True
    assert software.codec_name == "libx264"


def test_auto_selection_never_raises_and_returns_working_encoder(ffmpeg_path):
    result = select_best_encoder(ffmpeg_path, EncoderBackend.AUTO, "h264")
    assert result.working is True


def test_requesting_unavailable_backend_falls_back_to_software(ffmpeg_path):
    # في بيئة الاختبار هذه لا توجد بطاقة NVIDIA حقيقية، لذا يجب أن يرجع للبرمجي بدل الفشل
    result = select_best_encoder(ffmpeg_path, EncoderBackend.NVIDIA, "h264")
    assert result.working is True
    assert result.backend == EncoderBackend.SOFTWARE
