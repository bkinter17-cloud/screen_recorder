"""
إدارة إعدادات التطبيق (Configuration Management).

- يقرأ إعدادات افتراضية من config/default_config.json
- يقرأ/يكتب إعدادات المستخدم من config/user_config.json
- أي مفتاح غير موجود عند المستخدم يُستكمل تلقائياً من الافتراضي (merge)
  حتى لا ينهار التطبيق عند تحديث الإعدادات مستقبلاً.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _bundled_root() -> Path:
    """Return the directory holding files shipped with PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return PROJECT_ROOT


def _user_data_dir() -> Path:
    """Keep writable files outside the read-only application bundle."""
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ScreenRecorder"
    return PROJECT_ROOT / "config"


def get_default_save_folder() -> Path:
    """إرجاع المجلد الافتراضي لحفظ التسجيلات داخل مجلد المستخدم (فيديوهات المستخدم)."""
    videos = Path.home() / "Videos"
    if videos.exists() or sys.platform == "win32":
        return videos / "ScreenRecorder"
    return Path.home() / "ScreenRecorder"


def resolve_save_folder(configured_folder: str | Path | None) -> Path:
    """
    تحويل مسار مجلد الحفظ إلى مسار مطلق آمن داخل مجلد المستخدم.
    إذا كان المسار فارغاً أو 'recordings' (القيمة الافتراضية القديمة التي كانت تسبب الحفظ في Program Files)
    أو مساراً نسبياً، يتم تحويله لمجلد آمن للمستخدم بدلاً من Path.cwd().
    """
    if not configured_folder:
        return get_default_save_folder()

    path = Path(configured_folder)
    if not path.is_absolute():
        posix = path.as_posix().strip()
        if posix in (".", "recordings", "ScreenRecorder", ""):
            return get_default_save_folder()
        # مسار نسبي مخصص: نحفظه داخل مجلد الفيديوهات/المستخدم وليس مجلد البرنامج
        videos = Path.home() / "Videos"
        base = videos if (videos.exists() or sys.platform == "win32") else Path.home()
        return base / path

    return path


DEFAULT_CONFIG_PATH = _bundled_root() / "config" / "default_config.json"
USER_CONFIG_PATH = _user_data_dir() / "user_config.json"


class ConfigError(Exception):
    """يُرفع عند فشل قراءة أو كتابة ملف الإعدادات."""


class ConfigManager:
    """
    واجهة موحّدة للتعامل مع الإعدادات في كل أنحاء التطبيق.
    الاستخدام المعتاد:
        config = ConfigManager()
        theme = config.get("general", "theme")
        config.set("general", "theme", "light")
        config.save()
    """

    def __init__(
        self,
        default_path: Path = DEFAULT_CONFIG_PATH,
        user_path: Path = USER_CONFIG_PATH,
    ) -> None:
        self._default_path = default_path
        self._user_path = user_path
        self._data: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------ #
    # تحميل / حفظ
    # ------------------------------------------------------------------ #
    def load(self) -> None:
        defaults = self._read_json(self._default_path, required=True)

        if self._user_path.exists():
            user_overrides = self._read_json(self._user_path, required=False)
            self._data = self._deep_merge(defaults, user_overrides)
            logger.info("تم تحميل إعدادات المستخدم من %s", self._user_path)
        else:
            self._data = defaults
            logger.info("لا يوجد ملف إعدادات مستخدم، تم استخدام الإعدادات الافتراضية")

    def save(self) -> None:
        try:
            self._user_path.parent.mkdir(parents=True, exist_ok=True)
            with self._user_path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            logger.info("تم حفظ الإعدادات في %s", self._user_path)
        except OSError as exc:
            logger.error("فشل حفظ الإعدادات: %s", exc)
            raise ConfigError(f"تعذر حفظ ملف الإعدادات: {exc}") from exc

    def reset_to_defaults(self) -> None:
        self._data = self._read_json(self._default_path, required=True)
        logger.info("تمت إعادة الإعدادات للوضع الافتراضي")

    # ------------------------------------------------------------------ #
    # قراءة / تعديل
    # ------------------------------------------------------------------ #
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        return self._data.get(section, {}).get(key, fallback)

    def get_section(self, section: str) -> dict[str, Any]:
        return dict(self._data.get(section, {}))

    def set(self, section: str, key: str, value: Any) -> None:
        self._data.setdefault(section, {})[key] = value

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def get_save_folder(self) -> Path:
        """إرجاع المسار المحلول لمجلد حفظ التسجيلات آمناً في مجلد المستخدم."""
        raw = self.get("output", "save_folder")
        return resolve_save_folder(raw)

    # ------------------------------------------------------------------ #
    # أدوات داخلية
    # ------------------------------------------------------------------ #
    @staticmethod
    def _read_json(path: Path, required: bool) -> dict[str, Any]:
        if not path.exists():
            if required:
                raise ConfigError(f"ملف الإعدادات الأساسي غير موجود: {path}")
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("خطأ في قراءة ملف الإعدادات %s: %s", path, exc)
            if required:
                raise ConfigError(f"ملف الإعدادات تالف: {path}") from exc
            return {}

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """يدمج override فوق base بشكل متداخل (nested) بدون حذف مفاتيح ناقصة."""
        result = dict(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
