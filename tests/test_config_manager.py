"""اختبارات وحدة لـ ConfigManager."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.settings.config_manager import ConfigManager, ConfigError


@pytest.fixture()
def temp_config_paths(tmp_path: Path):
    default_data = {
        "general": {"theme": "dark", "language": "ar"},
        "recording": {"default_fps": 30},
    }
    default_path = tmp_path / "default_config.json"
    default_path.write_text(json.dumps(default_data), encoding="utf-8")

    user_path = tmp_path / "user_config.json"
    return default_path, user_path


def test_loads_defaults_when_no_user_config(temp_config_paths):
    default_path, user_path = temp_config_paths
    config = ConfigManager(default_path=default_path, user_path=user_path)

    assert config.get("general", "theme") == "dark"
    assert config.get("recording", "default_fps") == 30


def test_set_and_save_persists_to_user_config(temp_config_paths):
    default_path, user_path = temp_config_paths
    config = ConfigManager(default_path=default_path, user_path=user_path)

    config.set("general", "theme", "light")
    config.save()

    assert user_path.exists()
    saved = json.loads(user_path.read_text(encoding="utf-8"))
    assert saved["general"]["theme"] == "light"


def test_user_overrides_merge_with_defaults(temp_config_paths):
    default_path, user_path = temp_config_paths
    user_path.write_text(json.dumps({"general": {"theme": "light"}}), encoding="utf-8")

    config = ConfigManager(default_path=default_path, user_path=user_path)

    # القيمة المعدّلة من المستخدم
    assert config.get("general", "theme") == "light"
    # القيمة الافتراضية التي لم يعدّلها المستخدم يجب أن تبقى موجودة
    assert config.get("general", "language") == "ar"
    assert config.get("recording", "default_fps") == 30


def test_missing_default_file_raises_config_error(tmp_path):
    missing_default = tmp_path / "does_not_exist.json"
    user_path = tmp_path / "user_config.json"

    with pytest.raises(ConfigError):
        ConfigManager(default_path=missing_default, user_path=user_path)


def test_get_with_fallback_returns_fallback_for_missing_key(temp_config_paths):
    default_path, user_path = temp_config_paths
    config = ConfigManager(default_path=default_path, user_path=user_path)

    assert config.get("general", "nonexistent_key", fallback="x") == "x"
