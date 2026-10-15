"""اختبارات وحدة لطبقة FFmpeg — لا تحتاج شاشة حقيقية (تختبر بناء الأوامر والاكتشاف فقط)."""

from __future__ import annotations

from pathlib import Path

from app.video.ffmpeg_manager import (
    CaptureRequest,
    build_ffmpeg_command,
    find_ffmpeg,
    get_ffmpeg_version,
)


def test_find_ffmpeg_locates_system_binary():
    path = find_ffmpeg()
    assert path is not None
    assert Path(path).is_file()


def test_find_ffmpeg_returns_none_for_bad_explicit_path():
    # مسار خاطئ في الإعدادات يجب أن يتجاهله ويبحث في PATH بدلاً من الانهيار
    path = find_ffmpeg(explicit_path="/nonexistent/ffmpeg_binary_xyz")
    assert path is not None  # يعود للبحث في PATH


def test_get_ffmpeg_version_returns_a_version_string():
    path = find_ffmpeg()
    version = get_ffmpeg_version(path)
    assert version is not None
    assert len(version) > 0


def test_build_command_contains_output_path_and_codec():
    req = CaptureRequest(
        output_path=Path("/tmp/whatever/output"),
        fps=30, left=0, top=0, width=1920, height=1080,
        video_codec="libx264", bitrate_kbps=8000, container="mp4",
    )
    temp_output = Path("/tmp/whatever/output.recording.mkv")
    cmd = build_ffmpeg_command("/usr/bin/ffmpeg", req, temp_output)

    assert cmd[0] == "/usr/bin/ffmpeg"
    assert "-c:v" in cmd and "libx264" in cmd
    assert str(temp_output) == cmd[-1]
    assert "-b:v" in cmd and "8000k" in cmd


def test_build_command_includes_audio_codec_only_when_audio_inputs_present():
    base_req = dict(
        output_path=Path("/tmp/x/output"), fps=30, left=0, top=0,
        width=1280, height=720, video_codec="libx264",
        bitrate_kbps=5000, container="mp4",
    )
    no_audio = CaptureRequest(**base_req, audio_inputs=[])
    with_audio = CaptureRequest(**base_req, audio_inputs=["-f", "pulse", "-i", "default"])

    cmd_no_audio = build_ffmpeg_command("ffmpeg", no_audio, Path("/tmp/x/o.mkv"))
    cmd_with_audio = build_ffmpeg_command("ffmpeg", with_audio, Path("/tmp/x/o.mkv"))

    assert "-c:a" not in cmd_no_audio
    assert "-c:a" in cmd_with_audio and "aac" in cmd_with_audio
