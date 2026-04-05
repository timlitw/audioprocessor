"""Status bar showing audio format info, cursor position, and selection range."""

from PyQt6.QtWidgets import QStatusBar, QLabel
from PyQt6.QtCore import Qt


class AudioStatusBar(QStatusBar):
    """Displays format info and selection details."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QStatusBar { background: #1e1e1e; color: #b0b0b0; }")

        self._format_label = QLabel("No file loaded")
        self._selection_label = QLabel("")
        self._cursor_label = QLabel("")

        self.addWidget(self._format_label, 1)
        self.addPermanentWidget(self._cursor_label)
        self.addPermanentWidget(self._selection_label)

    def set_format_info(self, sample_rate: int, channels: int, duration_str: str, file_name: str):
        ch_text = "Mono" if channels == 1 else "Stereo" if channels == 2 else f"{channels}ch"
        self._format_label.setText(
            f"  {file_name}  |  {sample_rate} Hz  |  {ch_text}  |  {duration_str}"
        )

    def set_selection_info(self, text: str):
        self._selection_label.setText(text)

    def set_cursor_info(self, text: str):
        self._cursor_label.setText(text)

    def clear_info(self):
        self._format_label.setText("No file loaded")
        self._selection_label.setText("")
        self._cursor_label.setText("")
