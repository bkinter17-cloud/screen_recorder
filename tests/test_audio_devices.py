"""اختبارات وحدة لاكتشاف أجهزة الصوت — لا تفشل إن لم توجد أجهزة صوت فعلية في البيئة."""

from __future__ import annotations

from app.audio.audio_devices import list_microphones, list_system_audio_devices


def test_list_microphones_returns_a_list_without_raising():
    result = list_microphones()
    assert isinstance(result, list)


def test_list_system_audio_devices_returns_a_list_without_raising():
    result = list_system_audio_devices()
    assert isinstance(result, list)
