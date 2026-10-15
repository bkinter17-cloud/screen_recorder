"""
نقطة الدخول الرئيسية لتطبيق Screen Recorder.

تشغيل التطبيق:
    python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.settings.config_manager import ConfigManager, ConfigError
from app.ui.main_window import MainWindow
from app.utils.logger import setup_logging, get_logger


def main() -> int:
    # 1) تهيئة الـ Logging أولاً حتى يُسجَّل أي خطأ لاحق
    setup_logging(level="INFO")
    logger = get_logger(__name__)
    logger.info("=== بدء تشغيل التطبيق ===")

    # 2) تحميل الإعدادات
    try:
        config = ConfigManager()
    except ConfigError as exc:
        logger.critical("تعذر تحميل الإعدادات، سيتم إنهاء التطبيق: %s", exc)
        return 1

    # 3) تشغيل تطبيق Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Screen Recorder")

    # الواجهة بالكامل عربية RTL افتراضياً — هذا يعكس اتجاه كل شيء تلقائياً
    # (الشريط الجانبي، محاذاة النصوص، ترتيب عناصر النماذج) دون الحاجة
    # لضبط كل widget يدوياً. عند إضافة لغة إنجليزية مستقبلاً، تُقرأ من
    # general.language وتتحول لـ Qt.LeftToRight هنا فقط.
    is_rtl = config.get("general", "language", "ar") == "ar"
    app.setLayoutDirection(Qt.RightToLeft if is_rtl else Qt.LeftToRight)

    window = MainWindow(config)
    window.show()

    logger.info("تم عرض الواجهة الرئيسية بنجاح")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
