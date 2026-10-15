"""اختبارات وحدة لوحدة Webcam — حساب المواضع (قابل للاختبار الكامل) والتعامل الآمن مع غياب كاميرا فعلية."""

from __future__ import annotations

import pytest

from app.webcam.webcam_capture import WebcamError, WebcamPosition, compute_overlay_geometry, list_cameras


def test_top_left_position():
    assert compute_overlay_geometry(WebcamPosition.TOP_LEFT, 1920, 1080, 320, 240, margin=20) == (20, 20)


def test_bottom_right_position():
    x, y = compute_overlay_geometry(WebcamPosition.BOTTOM_RIGHT, 1920, 1080, 320, 240, margin=20)
    assert x == 1920 - 320 - 20
    assert y == 1080 - 240 - 20


def test_custom_position_raises():
    with pytest.raises(WebcamError):
        compute_overlay_geometry(WebcamPosition.CUSTOM, 1920, 1080, 320, 240)


def test_list_cameras_returns_list_without_raising_when_no_hardware():
    # في بيئة بدون كاميرا فعلية يجب أن تعود قائمة فارغة، بدون استثناء غير متوقع
    result = list_cameras(max_probe=2)
    assert isinstance(result, list)
