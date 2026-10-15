"""
لوحة التحكم العائمة أثناء التسجيل (Floating Recording Controller).

تظهر بدل النافذة الرئيسية بعد بدء التسجيل (البند 3: "إمكانية إخفاء
النافذة الرئيسية أثناء التسجيل" + "إمكانية إظهار Floating Recording
Controller صغير"). نافذة صغيرة بلا إطار، تبقى فوق كل النوافذ الأخرى،
قابلة للسحب، وتعرض المؤقت الحي مع أزرار Pause/Resume/Stop وزر لإعادة
إظهار النافذة الرئيسية.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

STYLESHEET = """
QWidget#floatingRoot {
    background-color: #1a1b22;
    border: 1px solid #3a3c48;
    border-radius: 12px;
}
QLabel#recDot { color: #ff4d4d; font-size: 16px; }
QLabel#timer { color: #f0f0f2; font-size: 14px; font-weight: 600; font-family: "Consolas", monospace; }
QPushButton {
    background-color: transparent; border: none; color: #e6e6e6;
    padding: 6px; border-radius: 8px; font-size: 14px;
}
QPushButton:hover { background-color: #2c2e3a; }
QPushButton#stopBtn { color: #ff5c56; font-weight: bold; }
"""


class FloatingController(QWidget):
    pause_resume_requested = Signal()
    stop_requested = Signal()
    restore_requested = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setObjectName("floatingRoot")
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(STYLESHEET)

        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.dot_label = QLabel("●")
        self.dot_label.setObjectName("recDot")
        layout.addWidget(self.dot_label)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timer")
        layout.addWidget(self.timer_label)

        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setToolTip("إيقاف مؤقت / استئناف")
        self.pause_btn.clicked.connect(self.pause_resume_requested.emit)
        layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setToolTip("إنهاء التسجيل")
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        layout.addWidget(self.stop_btn)

        self.restore_btn = QPushButton("⤢")
        self.restore_btn.setToolTip("إظهار النافذة الرئيسية")
        self.restore_btn.clicked.connect(self.restore_requested.emit)
        layout.addWidget(self.restore_btn)

        self.adjustSize()

    def set_paused_icon(self, is_paused: bool) -> None:
        self.pause_btn.setText("▶" if is_paused else "⏸")
        self.dot_label.setStyleSheet("color: #f5c542;" if is_paused else "color: #ff4d4d;")

    def set_timer_text(self, text: str) -> None:
        self.timer_label.setText(text)

    def position_top_right(self, margin: int = 24) -> None:
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.adjustSize()
        x = geo.right() - self.width() - margin
        y = geo.top() + margin
        self.move(x, y)

    # --- سحب النافذة بالماوس (لا يوجد شريط عنوان بسبب FramelessWindowHint) ---
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
