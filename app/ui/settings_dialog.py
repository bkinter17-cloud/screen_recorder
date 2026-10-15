"""
نافذة الإعدادات الكاملة (Phase 9) — منظمة إلى أقسام حسب المواصفات (البند 15):
General / Recording / Audio / Output / Hotkeys / Advanced.

كل الحقول مربوطة مباشرة بـ ConfigManager الحقيقي — لا قيم وهمية.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.settings.config_manager import ConfigManager, get_default_save_folder, resolve_save_folder
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SettingsDialog(QDialog):
    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("الإعدادات")
        self.resize(520, 480)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_general_tab()
        self._build_recording_tab()
        self._build_audio_tab()
        self._build_output_tab()
        self._build_hotkeys_tab()
        self._build_advanced_tab()

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ #
    def _build_general_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.config.get("general", "theme", "dark"))
        form.addRow("المظهر (Theme):", self.theme_combo)

        self.start_minimized_check = QCheckBox()
        self.start_minimized_check.setChecked(self.config.get("general", "start_minimized", False))
        form.addRow("البدء مصغّراً:", self.start_minimized_check)

        self.start_with_windows_check = QCheckBox()
        self.start_with_windows_check.setChecked(self.config.get("general", "start_with_windows", False))
        form.addRow("التشغيل مع بدء Windows:", self.start_with_windows_check)

        self.minimize_to_tray_check = QCheckBox()
        self.minimize_to_tray_check.setChecked(self.config.get("general", "minimize_to_tray", True))
        form.addRow("التصغير لشريط النظام:", self.minimize_to_tray_check)

        self.tabs.addTab(tab, "عام")

    def _build_recording_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)

        self.default_fps_spin = QSpinBox()
        self.default_fps_spin.setRange(10, 120)
        self.default_fps_spin.setValue(self.config.get("recording", "default_fps", 30))
        form.addRow("FPS الافتراضي:", self.default_fps_spin)

        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(500, 50000)
        self.bitrate_spin.setSingleStep(500)
        self.bitrate_spin.setValue(self.config.get("recording", "bitrate_kbps", 8000))
        form.addRow("Bitrate (kbps):", self.bitrate_spin)

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["auto", "software", "nvidia", "intel", "amd"])
        self.encoder_combo.setCurrentText(self.config.get("recording", "encoder", "auto"))
        form.addRow("المُرمِّز (Encoder):", self.encoder_combo)

        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["mp4", "mkv", "webm"])
        self.output_format_combo.setCurrentText(self.config.get("recording", "output_format", "mp4"))
        form.addRow("صيغة الإخراج:", self.output_format_combo)

        self.tabs.addTab(tab, "التسجيل")

    def _build_audio_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)

        self.capture_mic_check = QCheckBox()
        self.capture_mic_check.setChecked(self.config.get("audio", "capture_microphone", True))
        form.addRow("تسجيل الميكروفون:", self.capture_mic_check)

        self.capture_system_check = QCheckBox()
        self.capture_system_check.setChecked(self.config.get("audio", "capture_system_audio", True))
        form.addRow("تسجيل صوت النظام:", self.capture_system_check)

        self.mic_volume_spin = QSpinBox()
        self.mic_volume_spin.setRange(0, 200)
        self.mic_volume_spin.setSuffix("%")
        self.mic_volume_spin.setValue(self.config.get("audio", "microphone_volume", 100))
        form.addRow("مستوى الميكروفون:", self.mic_volume_spin)

        self.system_volume_spin = QSpinBox()
        self.system_volume_spin.setRange(0, 200)
        self.system_volume_spin.setSuffix("%")
        self.system_volume_spin.setValue(self.config.get("audio", "system_audio_volume", 100))
        form.addRow("مستوى صوت النظام:", self.system_volume_spin)

        self.tabs.addTab(tab, "الصوت")

    def _build_output_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)

        folder_layout = QHBoxLayout()
        current_save_folder = str(self.config.get_save_folder())
        self.save_folder_edit = QLineEdit(current_save_folder)
        self.browse_btn = QPushButton("تصفح...")
        self.browse_btn.clicked.connect(self._on_browse_save_folder)
        folder_layout.addWidget(self.save_folder_edit)
        folder_layout.addWidget(self.browse_btn)
        form.addRow("مجلد الحفظ:", folder_layout)

        self.filename_template_edit = QLineEdit(
            self.config.get("output", "filename_template", "ScreenRecord_%Y-%m-%d_%H-%M-%S")
        )
        form.addRow("قالب اسم الملف:", self.filename_template_edit)

        self.tabs.addTab(tab, "الإخراج")

    def _on_browse_save_folder(self) -> None:
        initial = self.save_folder_edit.text().strip() or str(get_default_save_folder())
        chosen = QFileDialog.getExistingDirectory(self, "اختر مجلد الحفظ", initial)
        if chosen:
            self.save_folder_edit.setText(chosen)

    def _build_hotkeys_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)

        self.hotkey_start_edit = QLineEdit(self.config.get("hotkeys", "start_stop_recording", "Ctrl+Alt+R"))
        form.addRow("بدء/إيقاف التسجيل:", self.hotkey_start_edit)

        self.hotkey_pause_edit = QLineEdit(self.config.get("hotkeys", "pause_resume", "Ctrl+Alt+P"))
        form.addRow("إيقاف مؤقت/استئناف:", self.hotkey_pause_edit)

        self.hotkey_screenshot_edit = QLineEdit(self.config.get("hotkeys", "screenshot", "Ctrl+Alt+S"))
        form.addRow("لقطة شاشة:", self.hotkey_screenshot_edit)

        self.tabs.addTab(tab, "الاختصارات")

    def _build_advanced_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)

        self.ffmpeg_path_edit = QLineEdit(self.config.get("advanced", "ffmpeg_path", "") or "")
        self.ffmpeg_path_edit.setPlaceholderText("فارغ = البحث التلقائي في PATH")
        form.addRow("مسار FFmpeg:", self.ffmpeg_path_edit)

        self.logging_level_combo = QComboBox()
        self.logging_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.logging_level_combo.setCurrentText(self.config.get("advanced", "logging_level", "INFO"))
        form.addRow("مستوى الـ Logging:", self.logging_level_combo)

        self.tabs.addTab(tab, "متقدم")

    # ------------------------------------------------------------------ #
    def _on_save(self) -> None:
        self.config.set("general", "theme", self.theme_combo.currentText())
        self.config.set("general", "start_minimized", self.start_minimized_check.isChecked())
        self.config.set("general", "start_with_windows", self.start_with_windows_check.isChecked())
        self.config.set("general", "minimize_to_tray", self.minimize_to_tray_check.isChecked())

        self.config.set("recording", "default_fps", self.default_fps_spin.value())
        self.config.set("recording", "bitrate_kbps", self.bitrate_spin.value())
        self.config.set("recording", "encoder", self.encoder_combo.currentText())
        self.config.set("recording", "output_format", self.output_format_combo.currentText())

        self.config.set("audio", "capture_microphone", self.capture_mic_check.isChecked())
        self.config.set("audio", "capture_system_audio", self.capture_system_check.isChecked())
        self.config.set("audio", "microphone_volume", self.mic_volume_spin.value())
        self.config.set("audio", "system_audio_volume", self.system_volume_spin.value())

        self.config.set("output", "save_folder", self.save_folder_edit.text().strip() or str(get_default_save_folder()))
        self.config.set("output", "filename_template", self.filename_template_edit.text().strip())

        self.config.set("hotkeys", "start_stop_recording", self.hotkey_start_edit.text().strip())
        self.config.set("hotkeys", "pause_resume", self.hotkey_pause_edit.text().strip())
        self.config.set("hotkeys", "screenshot", self.hotkey_screenshot_edit.text().strip())

        self.config.set("advanced", "ffmpeg_path", self.ffmpeg_path_edit.text().strip() or None)
        self.config.set("advanced", "logging_level", self.logging_level_combo.currentText())

        try:
            self.config.save()
        except Exception:  # noqa: BLE001
            logger.exception("فشل حفظ الإعدادات من نافذة الإعدادات")

        logger.info("تم حفظ الإعدادات من نافذة الإعدادات")
        self.accept()
