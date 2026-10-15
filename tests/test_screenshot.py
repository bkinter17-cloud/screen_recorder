"""اختبارات وحدة لمنطق تسمية ملفات لقطة الشاشة (بدون الحاجة لشاشة حقيقية)."""

from __future__ import annotations

from app.screenshot.screenshot import _default_filename


def test_default_filename_has_expected_prefix_and_extension(tmp_path):
    name = _default_filename("png", tmp_path)
    assert name.startswith("Screenshot_")
    assert name.endswith(".png")


def test_default_filename_avoids_collision(tmp_path):
    first = _default_filename("png", tmp_path)
    (tmp_path / first).touch()  # يحاكي وجود لقطة سابقة بنفس الاسم

    second = _default_filename("png", tmp_path)
    assert second != first
    assert not (tmp_path / second).exists()
