"""
نظام Logging مركزي للتطبيق.

يوفر logger واحد (app-wide) يكتب إلى logs/app.log مع Rotation،
بالإضافة إلى الطباعة على الـ console أثناء التطوير.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

if getattr(sys, "frozen", False):
    LOG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ScreenRecorder" / "logs"
else:
    LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"

MAX_BYTES = 5 * 1024 * 1024  # 5 MB لكل ملف
BACKUP_COUNT = 5  # يحتفظ بآخر 5 ملفات قبل الحذف

_LOGGER_NAME = "screen_recorder"
_configured = False


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    يهيئ الـ root logger الخاص بالتطبيق مرة واحدة فقط.
    يستدعى من main.py عند بدء التشغيل.
    """
    global _configured

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(_LOGGER_NAME)

    if _configured:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    _configured = True
    logger.info("تم تهيئة نظام الـ Logging (level=%s)", level)
    return logger


def get_logger(module_name: str | None = None) -> logging.Logger:
    """
    يعيد logger فرعي (child) تابع للـ app logger، لاستخدامه داخل أي module.
    مثال: logger = get_logger(__name__)
    """
    if module_name:
        return logging.getLogger(f"{_LOGGER_NAME}.{module_name}")
    return logging.getLogger(_LOGGER_NAME)
