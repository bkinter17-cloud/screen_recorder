"""
النافذة الرئيسية للتطبيق.

اعتباراً من Phase 5، هذه الواجهة موصولة بمحرك تسجيل حقيقي
(app.core.recording_controller.RecordingController):
- قائمة الشاشات حقيقية (مصدرها app.recording.sources).
- أزرار Start/Pause/Resume/Stop فعّالة وتُنتج ملف فيديو حقيقياً.
- Timer وحجم الملف يُحدَّثان حياً كل 250ms عبر QTimer.
- أي خطأ من المحرك (FFmpeg غير موجود، فشل بدء ...) يُعرض للمستخدم برسالة
  واضحة بدل انهيار التطبيق (تمهيداً لنظام الأخطاء الكامل في Phase 18).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.audio.audio_devices import list_microphones, list_system_audio_devices
from app.core.recording_controller import RecordingController, RecordingOptions
from app.core.recordings_library import RecordingsLibraryError, delete_recording, list_recordings, rename_recording
from app.hotkeys.hotkey_manager import HotkeyError, HotkeyManager
from app.recording.sources import MonitorInfo, get_monitors
from app.screenshot.screenshot import ScreenshotError, capture_fullscreen
from app.settings.config_manager import ConfigManager
from app.ui.floating_controller import FloatingController
from app.utils.logger import get_logger
from app.video.ffmpeg_manager import FFmpegError, RecorderState

logger = get_logger(__name__)

DARK_STYLESHEET = """
QMainWindow, QWidget { background-color: #131419; color: #e8e9ed; font-size: 13px; }
QListWidget { background-color: #0c0d11; border: none; border-left: 1px solid #24262f; padding: 12px 0; }
QListWidget::item { padding: 11px 18px; border-radius: 8px; margin: 2px 10px; color: #9a9ca8; }
QListWidget::item:selected { background-color: #2a2210; color: #e8a33d; font-weight: 600; }
QListWidget::item:hover:!selected { background-color: #181a21; color: #cdcfd8; }
QPushButton {
    background-color: #1d1f27; border: 1px solid #2e313d; border-radius: 8px;
    padding: 9px 18px; color: #e8e9ed; font-weight: 500;
}
QPushButton:hover { background-color: #262933; border-color: #3a3d4a; }
QPushButton:disabled { color: #55575f; background-color: #191a20; border-color: #24262f; }
QPushButton#startBtn { background-color: #1f9d55; border: none; color: #ffffff; font-weight: 600; }
QPushButton#startBtn:hover { background-color: #24b862; }
QPushButton#stopBtn { background-color: #d5453f; border: none; color: #ffffff; font-weight: 600; }
QPushButton#stopBtn:hover { background-color: #e5544d; }
QComboBox {
    background-color: #1a1c23; border: 1px solid #2e313d; border-radius: 7px;
    padding: 7px 10px; color: #e8e9ed; min-height: 20px;
}
QComboBox:disabled { color: #55575f; }
QComboBox QAbstractItemView {
    background-color: #1a1c23; border: 1px solid #2e313d; color: #e8e9ed;
    selection-background-color: #2a2210; selection-color: #e8a33d;
}
QLineEdit, QSpinBox {
    background-color: #1a1c23; border: 1px solid #2e313d; border-radius: 7px;
    padding: 7px 10px; color: #e8e9ed;
}
QCheckBox { spacing: 8px; }
QTabWidget::pane { border: 1px solid #24262f; border-radius: 8px; top: -1px; }
QTabBar::tab {
    background: transparent; color: #9a9ca8; padding: 8px 16px; margin-right: 2px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #e8a33d; border-bottom: 2px solid #e8a33d; }
QStatusBar { background-color: #0c0d11; color: #6f717c; border-top: 1px solid #24262f; }
QLabel#pageTitle { font-size: 21px; font-weight: 700; color: #f4f5f7; padding: 2px 0 14px 0; }
QLabel#sectionLabel { font-size: 12px; font-weight: 600; color: #6f717c; padding-bottom: 2px; }
QLabel#timerLabel { font-size: 26px; font-weight: 700; color: #f4f5f7; font-family: "Consolas", monospace; }
QLabel#stateRecording { color: #e5484d; font-weight: 600; }
QLabel#statePaused { color: #e8a33d; font-weight: 600; }
QLabel#stateReady { color: #6f717c; }
QFrame#card { background-color: #191b22; border: 1px solid #24262f; border-radius: 14px; }
QFrame#recordRow { background-color: #14151b; border: 1px solid #22242d; border-radius: 10px; }
"""

LIGHT_STYLESHEET = """
QMainWindow, QWidget { background-color: #f6f6f8; color: #1c1d21; font-size: 13px; }
QListWidget { background-color: #ffffff; border: none; border-left: 1px solid #e6e7eb; padding: 12px 0; }
QListWidget::item { padding: 11px 18px; border-radius: 8px; margin: 2px 10px; color: #64656d; }
QListWidget::item:selected { background-color: #fdf0da; color: #b8760a; font-weight: 600; }
QListWidget::item:hover:!selected { background-color: #f1f1f4; color: #1c1d21; }
QPushButton {
    background-color: #ffffff; border: 1px solid #d8dae0; border-radius: 8px;
    padding: 9px 18px; color: #1c1d21; font-weight: 500;
}
QPushButton:hover { background-color: #f1f1f4; }
QPushButton:disabled { color: #a8aab2; background-color: #f6f6f8; }
QPushButton#startBtn { background-color: #1f9d55; border: none; color: #ffffff; font-weight: 600; }
QPushButton#startBtn:hover { background-color: #24b862; }
QPushButton#stopBtn { background-color: #d5453f; border: none; color: #ffffff; font-weight: 600; }
QPushButton#stopBtn:hover { background-color: #e5544d; }
QComboBox {
    background-color: #ffffff; border: 1px solid #d8dae0; border-radius: 7px;
    padding: 7px 10px; color: #1c1d21; min-height: 20px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff; border: 1px solid #d8dae0; color: #1c1d21;
    selection-background-color: #fdf0da; selection-color: #b8760a;
}
QLineEdit, QSpinBox {
    background-color: #ffffff; border: 1px solid #d8dae0; border-radius: 7px;
    padding: 7px 10px; color: #1c1d21;
}
QCheckBox { spacing: 8px; }
QTabWidget::pane { border: 1px solid #e6e7eb; border-radius: 8px; top: -1px; }
QTabBar::tab {
    background: transparent; color: #64656d; padding: 8px 16px; margin-right: 2px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #b8760a; border-bottom: 2px solid #b8760a; }
QStatusBar { background-color: #ffffff; color: #86878f; border-top: 1px solid #e6e7eb; }
QLabel#pageTitle { font-size: 21px; font-weight: 700; color: #101114; padding: 2px 0 14px 0; }
QLabel#sectionLabel { font-size: 12px; font-weight: 600; color: #86878f; padding-bottom: 2px; }
QLabel#timerLabel { font-size: 26px; font-weight: 700; color: #101114; font-family: "Consolas", monospace; }
QLabel#stateRecording { color: #d5453f; font-weight: 600; }
QLabel#statePaused { color: #b8760a; font-weight: 600; }
QLabel#stateReady { color: #86878f; }
QFrame#card { background-color: #ffffff; border: 1px solid #e6e7eb; border-radius: 14px; }
QFrame#recordRow { background-color: #fafafb; border: 1px solid #ececf0; border-radius: 10px; }
"""

QUALITY_PRESETS_KBPS = {
    "منخفضة": 2500,
    "متوسطة": 5000,
    "عالية": 8000,
    "عالية جداً": 16000,
}


class HomePage(QWidget):
    """صفحة البداية: عناصر التحكم بالتسجيل، موصولة بمحرك تسجيل حقيقي."""

    # يُستخدم لتمرير أحداث الاختصارات العامة (التي تصل من Thread مختلف عبر
    # مكتبة keyboard) بأمان إلى الـ GUI thread — Qt signals تضمن queued delivery.
    hotkey_triggered = Signal(str)
    # تُطلق عند بدء/إيقاف التسجيل فعلياً؛ MainWindow يستمع لها لإخفاء/إظهار
    # النافذة الرئيسية وتفعيل/إغلاق لوحة التحكم العائمة (Floating Controller).
    recording_started = Signal()
    recording_stopped = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._monitors: list[MonitorInfo] = []
        self._init_error: str | None = None

        try:
            self.controller = RecordingController(config)
        except FFmpegError as exc:
            # لا يجب أن ينهار التطبيق بالكامل بسبب عدم وجود FFmpeg عند بدء التشغيل —
            # نظام الأخطاء الكامل يأتي في Phase 18، لكن هذه حماية أساسية مبكرة.
            logger.error("تعذر تهيئة محرك التسجيل: %s", exc)
            self.controller = None
            self._init_error = str(exc)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("تسجيل الشاشة")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # --- بطاقة إعدادات المصدر ---
        source_card = QFrame()
        source_card.setObjectName("card")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(18, 18, 18, 18)
        source_layout.setSpacing(11)

        self.monitor_combo = QComboBox()
        self._refresh_monitors()
        source_layout.addWidget(self._labeled_widget("الشاشة:", self.monitor_combo))

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(list(QUALITY_PRESETS_KBPS.keys()))
        configured_bitrate = self.config.get("recording", "bitrate_kbps", 8000)
        self.quality_combo.setCurrentText(min(QUALITY_PRESETS_KBPS, key=lambda name: abs(QUALITY_PRESETS_KBPS[name] - configured_bitrate)))
        source_layout.addWidget(self._labeled_widget("الجودة:", self.quality_combo))

        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["24", "30", "60"])
        self.fps_combo.setCurrentText(str(self.config.get("recording", "default_fps", 30)))
        source_layout.addWidget(self._labeled_widget("FPS:", self.fps_combo))

        layout.addWidget(source_card)

        # --- بطاقة الصوت (الإصلاح المهم: توصيل فعلي لمصدر الصوت بالتسجيل) ---
        audio_card = QFrame()
        audio_card.setObjectName("card")
        audio_layout = QVBoxLayout(audio_card)
        audio_layout.setContentsMargins(18, 18, 18, 18)
        audio_layout.setSpacing(11)

        self.audio_source_combo = QComboBox()
        self.audio_source_combo.addItems(["بدون صوت", "الميكروفون فقط", "صوت النظام فقط", "الميكروفون + صوت النظام"])
        capture_mic = self.config.get("audio", "capture_microphone", True)
        capture_system = self.config.get("audio", "capture_system_audio", True)
        initial_audio_source = (
            "الميكروفون + صوت النظام" if capture_mic and capture_system else
            "الميكروفون فقط" if capture_mic else
            "صوت النظام فقط" if capture_system else "بدون صوت"
        )
        self.audio_source_combo.setCurrentText(initial_audio_source)
        audio_layout.addWidget(self._labeled_widget("مصدر الصوت:", self.audio_source_combo))

        self.microphone_combo = QComboBox()
        self.microphone_row = self._labeled_widget("الميكروفون:", self.microphone_combo)
        audio_layout.addWidget(self.microphone_row)

        self.system_audio_combo = QComboBox()
        self.system_audio_row = self._labeled_widget("صوت النظام:", self.system_audio_combo)
        audio_layout.addWidget(self.system_audio_row)

        refresh_audio_btn = QPushButton("🔄 تحديث أجهزة الصوت")
        refresh_audio_btn.clicked.connect(self._refresh_audio_devices)
        audio_layout.addWidget(refresh_audio_btn)

        layout.addWidget(audio_card)

        self._refresh_audio_devices()
        self.audio_source_combo.currentTextChanged.connect(self._update_audio_rows_visibility)
        self._update_audio_rows_visibility()

        # --- بطاقة الحالة ---
        status_card = QFrame()
        status_card.setObjectName("card")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(18, 16, 18, 16)

        self.state_label = QLabel("جاهز للتسجيل")
        self.state_label.setObjectName("stateReady")
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerLabel")
        self.filesize_label = QLabel("الحجم: —")

        status_layout.addWidget(self.state_label)
        status_layout.addStretch()
        status_layout.addWidget(self.timer_label)
        status_layout.addStretch()
        status_layout.addWidget(self.filesize_label)

        layout.addWidget(status_card)

        # --- أزرار التحكم ---
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        self.start_btn = QPushButton("بدء التسجيل")
        self.start_btn.setObjectName("startBtn")
        self.pause_btn = QPushButton("إيقاف مؤقت")
        self.stop_btn = QPushButton("إنهاء التسجيل")
        self.stop_btn.setObjectName("stopBtn")
        self.screenshot_btn = QPushButton("📷 لقطة شاشة")

        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

        for btn in (self.start_btn, self.pause_btn, self.stop_btn, self.screenshot_btn):
            controls_layout.addWidget(btn)

        layout.addLayout(controls_layout)
        layout.addStretch()

        self.start_btn.clicked.connect(self._on_start_clicked)
        self.pause_btn.clicked.connect(self._on_pause_resume_clicked)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.screenshot_btn.clicked.connect(self._on_screenshot_clicked)

        # مؤقت لتحديث الحالة الحية (المدة، الحجم) أثناء التسجيل
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(250)
        self._ui_timer.timeout.connect(self._update_live_status)

        if self._init_error:
            self.start_btn.setEnabled(False)
            self.state_label.setText(f"⚠️ {self._init_error}")

        self.hotkey_triggered.connect(self._on_hotkey_action)
        self.hotkey_manager = HotkeyManager()
        self._register_hotkeys()

    def _register_hotkeys(self) -> None:
        bindings = {
            "start_stop_recording": self.config.get("hotkeys", "start_stop_recording", "Ctrl+Alt+R"),
            "pause_resume": self.config.get("hotkeys", "pause_resume", "Ctrl+Alt+P"),
            "screenshot": self.config.get("hotkeys", "screenshot", "Ctrl+Alt+S"),
        }
        for action, combo in bindings.items():
            normalized = combo.lower().replace("+", "+")  # مكتبة keyboard تقبل هذا الشكل مباشرة
            try:
                # نستخدم lambda مع قيمة افتراضية لتفادي مشكلة late-binding الشهيرة في الحلقات
                self.hotkey_manager.register(
                    action, normalized,
                    lambda a=action: self.hotkey_triggered.emit(a),
                )
            except HotkeyError as exc:
                logger.warning("تعذر تسجيل اختصار %s: %s", action, exc)

    def _on_hotkey_action(self, action: str) -> None:
        """يُستدعى دائماً داخل GUI thread بفضل Qt signal/slot queued connection."""
        if action == "start_stop_recording":
            if self.controller and self.controller.state == RecorderState.IDLE:
                self._on_start_clicked()
            elif self.controller and self.controller.state in (RecorderState.RECORDING, RecorderState.PAUSED):
                self._on_stop_clicked()
        elif action == "pause_resume":
            if self.controller and self.controller.state in (RecorderState.RECORDING, RecorderState.PAUSED):
                self._on_pause_resume_clicked()
        elif action == "screenshot":
            self._on_screenshot_clicked()

    def cleanup(self) -> None:
        """يُستدعى عند إغلاق التطبيق لإلغاء كل الاختصارات العامة المسجّلة."""
        self.hotkey_manager.unregister_all()

    def _labeled_widget(self, label_text: str, widget: QWidget) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setFixedWidth(140)
        row_layout.addWidget(label)
        row_layout.addWidget(widget)
        row_layout.addStretch()
        return row

    def _refresh_monitors(self) -> None:
        self._monitors = get_monitors()
        self.monitor_combo.clear()
        if not self._monitors:
            self.monitor_combo.addItem("لا توجد شاشات مكتشفة")
            return
        for mon in self._monitors:
            self.monitor_combo.addItem(mon.label)

    def _refresh_audio_devices(self) -> None:
        self._microphones = list_microphones()
        self._system_audio_devices = list_system_audio_devices()

        self.microphone_combo.clear()
        if self._microphones:
            for d in self._microphones:
                self.microphone_combo.addItem(d.name, d.device_id)
        else:
            self.microphone_combo.addItem("لم يتم اكتشاف ميكروفون", None)

        self.system_audio_combo.clear()
        if self._system_audio_devices:
            for d in self._system_audio_devices:
                self.system_audio_combo.addItem(d.name, d.device_id)
        else:
            self.system_audio_combo.addItem("لم يتم اكتشاف مصدر صوت نظام", None)

    def _update_audio_rows_visibility(self) -> None:
        choice = self.audio_source_combo.currentText()
        wants_mic = choice in ("الميكروفون فقط", "الميكروفون + صوت النظام")
        wants_system = choice in ("صوت النظام فقط", "الميكروفون + صوت النظام")
        self.microphone_row.setVisible(wants_mic)
        self.system_audio_row.setVisible(wants_system)

    # ------------------------------------------------------------------ #
    def _on_start_clicked(self) -> None:
        if not self._monitors:
            QMessageBox.warning(self, "خطأ", "لم يتم اكتشاف أي شاشة قابلة للتسجيل.")
            return

        monitor = self._monitors[self.monitor_combo.currentIndex()]
        bitrate = QUALITY_PRESETS_KBPS[self.quality_combo.currentText()]
        fps = int(self.fps_combo.currentText())

        save_folder = self.config.get_save_folder()

        template = self.config.get("output", "filename_template", "ScreenRecord_%Y-%m-%d_%H-%M-%S")
        try:
            filename = datetime.now().strftime(template).strip()
        except (TypeError, ValueError):
            filename = ""
        # A filename template is user editable; keep it a filename, not a path.
        filename = Path(filename).name.strip().rstrip(". ")
        if not filename or any(char in filename for char in '<>:"/\\|?*'):
            filename = f"ScreenRecord_{datetime.now():%Y-%m-%d_%H-%M-%S}"

        audio_choice = self.audio_source_combo.currentText()
        mic_id = None
        system_id = None
        if audio_choice in ("الميكروفون فقط", "الميكروفون + صوت النظام"):
            mic_id = self.microphone_combo.currentData()
        if audio_choice in ("صوت النظام فقط", "الميكروفون + صوت النظام"):
            system_id = self.system_audio_combo.currentData()

        opts = RecordingOptions(
            output_folder=save_folder,
            filename_stem=filename,
            left=monitor.left, top=monitor.top,
            width=monitor.width, height=monitor.height,
            fps=fps, bitrate_kbps=bitrate,
            container=self.config.get("recording", "output_format", "mp4"),
            microphone_device_id=mic_id,
            system_audio_device_id=system_id,
            microphone_volume=self.config.get("audio", "microphone_volume", 100) / 100,
            system_audio_volume=self.config.get("audio", "system_audio_volume", 100) / 100,
        )

        try:
            self.controller.start(opts)
        except (FFmpegError, OSError, Exception) as exc:
            logger.exception("فشل بدء التسجيل: %s", exc)
            QMessageBox.critical(self, "تعذر بدء التسجيل", str(exc))
            return

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("إيقاف مؤقت")
        self.stop_btn.setEnabled(True)
        self.monitor_combo.setEnabled(False)
        self.quality_combo.setEnabled(False)
        self.fps_combo.setEnabled(False)
        self.audio_source_combo.setEnabled(False)
        self.microphone_combo.setEnabled(False)
        self.system_audio_combo.setEnabled(False)
        self._set_state_label("🔴 جاري التسجيل...", "stateRecording")
        self._ui_timer.start()
        self.recording_started.emit()

    def _set_state_label(self, text: str, style_name: str) -> None:
        self.state_label.setText(text)
        self.state_label.setObjectName(style_name)
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)

    def _on_pause_resume_clicked(self) -> None:
        try:
            if self.controller.state == RecorderState.RECORDING:
                self.controller.pause()
                self.pause_btn.setText("استئناف")
                self._set_state_label("⏸ متوقف مؤقتاً", "statePaused")
            elif self.controller.state == RecorderState.PAUSED:
                self.controller.resume()
                self.pause_btn.setText("إيقاف مؤقت")
                self._set_state_label("🔴 جاري التسجيل...", "stateRecording")
        except FFmpegError as exc:
            logger.error("فشل تبديل حالة الإيقاف المؤقت: %s", exc)
            QMessageBox.critical(self, "خطأ", str(exc))

    def _on_stop_clicked(self) -> None:
        self._ui_timer.stop()
        try:
            final_path = self.controller.stop()
        except FFmpegError as exc:
            logger.error("فشل إيقاف التسجيل: %s", exc)
            QMessageBox.critical(self, "خطأ", str(exc))
            final_path = None

        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.monitor_combo.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self.fps_combo.setEnabled(True)
        self.audio_source_combo.setEnabled(True)
        self.microphone_combo.setEnabled(True)
        self.system_audio_combo.setEnabled(True)
        self.timer_label.setText("00:00:00")
        self.filesize_label.setText("الحجم: —")

        if final_path:
            self._set_state_label(f"✅ تم الحفظ: {final_path.name}", "stateReady")
        else:
            self._set_state_label("جاهز للتسجيل", "stateReady")

        self.recording_stopped.emit()

    def _on_screenshot_clicked(self) -> None:
        save_folder = self.config.get_save_folder()
        screenshots_folder = save_folder / "screenshots"
        try:
            path = capture_fullscreen(screenshots_folder, "png")
        except (ScreenshotError, OSError, Exception) as exc:
            logger.exception("فشل التقاط أو حفظ لقطة الشاشة: %s", exc)
            QMessageBox.critical(self, "خطأ في لقطة الشاشة", str(exc))
            return
        self.state_label.setText(f"📷 تم حفظ لقطة الشاشة: {path.name}")

    def _update_live_status(self) -> None:
        elapsed = int(self.controller.elapsed_seconds())
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

        size_mb = self.controller.current_size_bytes() / (1024 * 1024)
        self.filesize_label.setText(f"الحجم: {size_mb:.1f} MB")


class DiagnosticsPage(QWidget):
    """صفحة التشخيص — تجمع وتعرض معلومات حقيقية عن الجهاز والبيئة (Phase 11)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("التشخيص (Diagnostics)")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.output_label = QLabel("اضغط 'تشغيل التشخيص' لعرض معلومات الجهاز.")
        self.output_label.setWordWrap(True)
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.addWidget(self.output_label)
        layout.addWidget(card, stretch=1)

        buttons_layout = QHBoxLayout()
        self.run_btn = QPushButton("🩺 تشغيل التشخيص")
        self.copy_btn = QPushButton("📋 نسخ النتائج")
        self.copy_btn.setEnabled(False)
        buttons_layout.addWidget(self.run_btn)
        buttons_layout.addWidget(self.copy_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        self.run_btn.clicked.connect(self._on_run_clicked)
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        self._last_report_text = ""

    def _on_run_clicked(self) -> None:
        from app.core.diagnostics import run_diagnostics

        self.run_btn.setEnabled(False)
        self.output_label.setText("جارِ الفحص...")
        QApplication.processEvents()

        report = run_diagnostics()
        self._last_report_text = report.to_text()
        self.output_label.setText(self._last_report_text.replace("\n", "<br>"))
        self.copy_btn.setEnabled(True)
        self.run_btn.setEnabled(True)

    def _on_copy_clicked(self) -> None:
        QApplication.clipboard().setText(self._last_report_text)


class SettingsPage(QWidget):
    """صفحة الإعدادات — تفتح نافذة الإعدادات الكاملة (Phase 9) وتعرض ملخصاً سريعاً."""

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("الإعدادات")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        open_btn = QPushButton("⚙️ فتح الإعدادات الكاملة")
        open_btn.clicked.connect(self._open_dialog)
        layout.addWidget(open_btn)
        layout.addStretch()

    def _open_dialog(self) -> None:
        from app.ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.config, self)
        dialog.exec()


class RecordingsPage(QWidget):
    """صفحة التسجيلات السابقة (البند 9): عرض/فتح المجلد/حذف/إعادة تسمية، مرتبة حسب التاريخ."""

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        title = QLabel("التسجيلات السابقة")
        title.setObjectName("pageTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        refresh_btn = QPushButton("🔄 تحديث")
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        self.list_container = QVBoxLayout()
        self.list_container.setSpacing(8)

        scroll_host = QWidget()
        scroll_host.setLayout(self.list_container)

        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(scroll_host)
        layout.addWidget(scroll, stretch=1)

        self.empty_label = QLabel("لا توجد تسجيلات بعد.")
        self.empty_label.setObjectName("stateReady")

        self.refresh()

    def _save_folder(self) -> Path:
        return self.config.get_save_folder()

    def refresh(self) -> None:
        while self.list_container.count():
            item = self.list_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            recordings = list_recordings(self._save_folder())
        except Exception as exc:
            logger.exception("تعذر قراءة قائمة التسجيلات: %s", exc)
            recordings = []

        if not recordings:
            self.list_container.addWidget(self.empty_label)
            return

        for rec in recordings:
            self.list_container.addWidget(self._build_row(rec))
        self.list_container.addStretch()

    def _build_row(self, rec) -> QFrame:
        row = QFrame()
        row.setObjectName("recordRow")
        row.setMaximumHeight(64)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 10, 14, 10)
        row_layout.setSpacing(10)

        info_layout = QVBoxLayout()
        name_label = QLabel(rec.name)
        name_label.setStyleSheet("font-weight: 600;")
        meta_label = QLabel(f"{rec.date_label}   •   {rec.duration_label}   •   {rec.size_label}")
        meta_label.setObjectName("sectionLabel")
        info_layout.addWidget(name_label)
        info_layout.addWidget(meta_label)
        row_layout.addLayout(info_layout, stretch=1)

        open_folder_btn = QPushButton("📂")
        open_folder_btn.setToolTip("فتح مكان الملف")
        open_folder_btn.clicked.connect(lambda _, p=rec.path: self._open_folder(p))
        row_layout.addWidget(open_folder_btn)

        play_btn = QPushButton("▶")
        play_btn.setToolTip("تشغيل الفيديو")
        play_btn.clicked.connect(lambda _, p=rec.path: self._play(p))
        row_layout.addWidget(play_btn)

        rename_btn = QPushButton("✏️")
        rename_btn.setToolTip("إعادة تسمية")
        rename_btn.clicked.connect(lambda _, p=rec.path: self._rename(p))
        row_layout.addWidget(rename_btn)

        delete_btn = QPushButton("🗑")
        delete_btn.setToolTip("حذف")
        delete_btn.clicked.connect(lambda _, p=rec.path: self._delete(p))
        row_layout.addWidget(delete_btn)

        return row

    def _open_folder(self, path: Path) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _play(self, path: Path) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _rename(self, path: Path) -> None:
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "إعادة تسمية", "الاسم الجديد:", text=path.stem)
        if not ok or not new_name.strip():
            return
        try:
            rename_recording(path, new_name.strip())
        except RecordingsLibraryError as exc:
            QMessageBox.warning(self, "تعذرت إعادة التسمية", str(exc))
        self.refresh()

    def _delete(self, path: Path) -> None:
        confirm = QMessageBox.question(
            self, "تأكيد الحذف", f"هل تريد حذف \"{path.name}\" نهائياً؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            delete_recording(path)
        except RecordingsLibraryError as exc:
            QMessageBox.warning(self, "تعذر الحذف", str(exc))
        self.refresh()


class PlaceholderPage(QWidget):
    """صفحة مؤقتة للأقسام التي لم تُبنَ بعد."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel(title)
        label.setObjectName("pageTitle")
        note = QLabel("سيتم بناء هذا القسم في مرحلة لاحقة.")
        layout.addWidget(label)
        layout.addWidget(note)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self.config = config

        self.setWindowTitle("Screen Recorder")
        self.resize(1000, 650)

        self._build_ui()
        self._apply_theme(self.config.get("general", "theme", "dark"))

        logger.info("تم إنشاء النافذة الرئيسية")

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setFrameShape(QFrame.NoFrame)

        pages_config = [
            ("🏠  الرئيسية", HomePage(self.config)),
            ("🎬  التسجيلات", RecordingsPage(self.config)),
            ("🩺  التشخيص", DiagnosticsPage()),
            ("⚙️  الإعدادات", SettingsPage(self.config)),
        ]

        self.stack = QStackedWidget()
        for label_text, page in pages_config:
            QListWidgetItem(label_text, self.sidebar)
            self.stack.addWidget(page)

        self.sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        self.sidebar.setCurrentRow(0)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("جاهز")

        theme_btn = QPushButton("تبديل الوضع الليلي/النهاري")
        theme_btn.clicked.connect(self._toggle_theme)
        status_bar.addPermanentWidget(theme_btn)

        # --- لوحة التحكم العائمة أثناء التسجيل ---
        home_page = self.stack.widget(0)
        self.floating_controller = FloatingController()
        self.floating_controller.pause_resume_requested.connect(home_page._on_pause_resume_clicked)
        self.floating_controller.stop_requested.connect(home_page._on_stop_clicked)
        self.floating_controller.restore_requested.connect(self._show_main_window)

        self._floating_timer = QTimer(self)
        self._floating_timer.setInterval(250)
        self._floating_timer.timeout.connect(self._update_floating_controller)

        home_page.recording_started.connect(self._on_recording_started)
        home_page.recording_stopped.connect(self._on_recording_stopped)

    def _on_sidebar_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page = self.stack.widget(index)
        if isinstance(page, RecordingsPage):
            page.refresh()

    def _on_recording_started(self) -> None:
        self.hide()
        self.floating_controller.position_top_right()
        self.floating_controller.show()
        self._floating_timer.start()

    def _on_recording_stopped(self) -> None:
        self._floating_timer.stop()
        self.floating_controller.hide()
        self._show_main_window()

    def _show_main_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _update_floating_controller(self) -> None:
        home_page = self.stack.widget(0)
        elapsed = int(home_page.controller.elapsed_seconds())
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.floating_controller.set_timer_text(f"{h:02d}:{m:02d}:{s:02d}")
        self.floating_controller.set_paused_icon(home_page.controller.state == RecorderState.PAUSED)

    def _toggle_theme(self) -> None:
        current = self.config.get("general", "theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        self.config.set("general", "theme", new_theme)
        self._apply_theme(new_theme)

    def _apply_theme(self, theme: str) -> None:
        self.setStyleSheet(DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET)
        logger.info("تم تطبيق الثيم: %s", theme)

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self.config.save()
        except Exception:  # noqa: BLE001
            logger.exception("فشل حفظ الإعدادات عند الإغلاق")
        self._floating_timer.stop()
        self.floating_controller.close()
        home_page = self.stack.widget(0)
        if isinstance(home_page, HomePage):
            if home_page.controller and home_page.controller.state in (RecorderState.RECORDING, RecorderState.PAUSED):
                # Finalise an active file before Qt tears down the process pipes.
                home_page._on_stop_clicked()
            home_page.cleanup()
        super().closeEvent(event)
