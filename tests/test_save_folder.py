"""اختبارات حل مجلد الحفظ الافتراضي ومعالجة أخطاء إنشاء المجلدات."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.recording_controller import RecordingController, RecordingOptions
from app.screenshot.screenshot import ScreenshotError, capture_region
from app.settings.config_manager import (
    ConfigManager,
    get_default_save_folder,
    resolve_save_folder,
)
from app.video.ffmpeg_manager import FFmpegError


def test_get_default_save_folder_in_user_space():
    folder = get_default_save_folder()
    assert folder.is_absolute()
    # يجب أن يكون المسار داخل مجلد المستخدم (Home)
    assert Path.home() in folder.parents or folder == Path.home()
    assert "ScreenRecorder" in str(folder) or "Videos" in str(folder)


def test_resolve_save_folder_empty_and_legacy_defaults():
    default_dir = get_default_save_folder()

    assert resolve_save_folder(None) == default_dir
    assert resolve_save_folder("") == default_dir
    assert resolve_save_folder("recordings") == default_dir
    assert resolve_save_folder("./recordings") == default_dir
    assert resolve_save_folder("ScreenRecorder") == default_dir


def test_resolve_save_folder_custom_relative_resolves_in_user_space():
    custom_rel = "MyCustomClips"
    resolved = resolve_save_folder(custom_rel)
    assert resolved.is_absolute()
    # تأكيد أنه لا يُحل بالنسبة لـ Path.cwd() (الذي قد يكون Program Files)
    assert Path.cwd() not in resolved.parents or Path.home() in resolved.parents
    assert custom_rel in str(resolved)


def test_resolve_save_folder_absolute_path_preserved():
    abs_path = Path.home() / "D_Drive_Recordings"
    assert resolve_save_folder(str(abs_path)) == abs_path


def test_config_manager_get_save_folder(tmp_path: Path):
    default_cfg = tmp_path / "default.json"
    default_cfg.write_text('{"output": {"save_folder": "recordings"}}', encoding="utf-8")
    user_cfg = tmp_path / "user.json"

    cfg = ConfigManager(default_path=default_cfg, user_path=user_cfg)
    # القيمة "recordings" الافتراضية يجب أن تتحول تلقائياً لمجلد المستخدم
    assert cfg.get_save_folder() == get_default_save_folder()


def test_recording_controller_mkdir_oserror_raises_ffmpeg_error():
    mock_config = MagicMock()
    mock_config.get.return_value = "dummy"

    with patch("app.core.recording_controller.find_ffmpeg", return_value="ffmpeg.exe"):
        controller = RecordingController(mock_config)

    opts = RecordingOptions(
        output_folder=Path("C:/Restricted/Path"),
        filename_stem="test_rec",
        left=0,
        top=0,
        width=1920,
        height=1080,
    )

    with patch.object(Path, "mkdir", side_effect=PermissionError("Access is denied")):
        with pytest.raises(FFmpegError) as exc_info:
            controller.start(opts)

        assert "تعذر إنشاء مجلد حفظ التسجيلات" in str(exc_info.value)
        assert "Access is denied" in str(exc_info.value)


def test_recording_controller_uses_a_unique_name_when_a_recording_exists(tmp_path: Path):
    base = tmp_path / "ScreenRecord"
    base.with_suffix(".mp4").touch()

    assert RecordingController._unique_base_path(base, "mp4") == tmp_path / "ScreenRecord_2"


def test_invalid_output_format_falls_back_to_mp4(tmp_path: Path):
    mock_config = MagicMock()
    mock_config.get.return_value = "auto"
    with patch("app.core.recording_controller.find_ffmpeg", return_value="ffmpeg.exe"):
        controller = RecordingController(mock_config)

    opts = RecordingOptions(tmp_path, "recording", 0, 0, 640, 480, container="unexpected")
    with patch("app.core.recording_controller.select_best_encoder") as select_encoder, patch.object(controller._video, "start") as start:
        select_encoder.return_value = MagicMock(codec_name="libx264")
        controller.start(opts)

    assert start.call_args.args[0].container == "mp4"


from app.screenshot.screenshot import ScreenshotError, _save_raw_capture


def test_screenshot_mkdir_oserror_raises_screenshot_error(tmp_path: Path):
    mock_shot = MagicMock()
    mock_shot.rgb = b"1234"
    mock_shot.size = (10, 10)
    out_file = tmp_path / "sub" / "screenshot.png"

    with patch.object(Path, "mkdir", side_effect=PermissionError("Access is denied")):
        with pytest.raises(ScreenshotError) as exc_info:
            _save_raw_capture(mock_shot, out_file, "png")

        assert "تعذر إنشاء مجلد لقطات الشاشة" in str(exc_info.value)
        assert "Access is denied" in str(exc_info.value)
