"""اختبارات وحدة لمكتبة التسجيلات."""

from __future__ import annotations

import time

import pytest

from app.core.recordings_library import (
    RecordingsLibraryError,
    delete_recording,
    list_recordings,
    rename_recording,
)


def _make_file(folder, name: str, size: int = 1000) -> None:
    (folder / name).write_bytes(b"0" * size)


def test_list_recordings_filters_non_video_files(tmp_path):
    _make_file(tmp_path, "a.mp4")
    _make_file(tmp_path, "notes.txt")
    _make_file(tmp_path, "b.mkv")

    names = {r.name for r in list_recordings(tmp_path)}
    assert names == {"a.mp4", "b.mkv"}


def test_list_recordings_sorted_newest_first(tmp_path):
    _make_file(tmp_path, "old.mp4")
    time.sleep(0.05)
    _make_file(tmp_path, "new.mp4")

    result = list_recordings(tmp_path)
    assert [r.name for r in result] == ["new.mp4", "old.mp4"]


def test_list_recordings_empty_folder_returns_empty_list(tmp_path):
    assert list_recordings(tmp_path / "does_not_exist") == []


def test_rename_recording_success(tmp_path):
    _make_file(tmp_path, "old_name.mp4")
    path = tmp_path / "old_name.mp4"

    new_path = rename_recording(path, "new_name")
    assert new_path.name == "new_name.mp4"
    assert new_path.exists()
    assert not path.exists()


def test_rename_recording_rejects_invalid_characters(tmp_path):
    _make_file(tmp_path, "a.mp4")
    with pytest.raises(RecordingsLibraryError):
        rename_recording(tmp_path / "a.mp4", "bad:name")


def test_rename_recording_rejects_existing_name(tmp_path):
    _make_file(tmp_path, "a.mp4")
    _make_file(tmp_path, "b.mp4")
    with pytest.raises(RecordingsLibraryError):
        rename_recording(tmp_path / "a.mp4", "b")


def test_delete_recording_removes_file(tmp_path):
    _make_file(tmp_path, "a.mp4")
    path = tmp_path / "a.mp4"
    delete_recording(path)
    assert not path.exists()


def test_delete_recording_missing_file_raises(tmp_path):
    with pytest.raises(RecordingsLibraryError):
        delete_recording(tmp_path / "nonexistent.mp4")
