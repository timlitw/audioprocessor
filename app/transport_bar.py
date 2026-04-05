"""Transport bar — playback controls, time display, zoom slider."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QSlider, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal


class TransportBar(QWidget):
    """Playback controls and time/zoom display."""

    play_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    skip_start_clicked = pyqtSignal()
    zoom_in_clicked = pyqtSignal()
    zoom_out_clicked = pyqtSignal()
    zoom_fit_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        btn_style = """
            QPushButton {
                background: #3a3a3a; color: #d0d0d0; border: 1px solid #555;
                border-radius: 3px; padding: 2px 8px; min-width: 28px; font-size: 14px;
            }
            QPushButton:hover { background: #4a4a4a; }
            QPushButton:pressed { background: #2a2a2a; }
        """

        # Skip to start
        self.btn_skip_start = QPushButton("\u23ee")
        self.btn_skip_start.setToolTip("Go to start (Home)")
        self.btn_skip_start.setStyleSheet(btn_style)
        self.btn_skip_start.clicked.connect(self.skip_start_clicked)

        # Play
        self.btn_play = QPushButton("\u25b6")
        self.btn_play.setToolTip("Play (Space)")
        self.btn_play.setStyleSheet(btn_style)
        self.btn_play.clicked.connect(self.play_clicked)

        # Pause
        self.btn_pause = QPushButton("\u23f8")
        self.btn_pause.setToolTip("Pause (Space)")
        self.btn_pause.setStyleSheet(btn_style)
        self.btn_pause.clicked.connect(self.pause_clicked)

        # Stop
        self.btn_stop = QPushButton("\u23f9")
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.setStyleSheet(btn_style)
        self.btn_stop.clicked.connect(self.stop_clicked)

        layout.addWidget(self.btn_skip_start)
        layout.addWidget(self.btn_play)
        layout.addWidget(self.btn_pause)
        layout.addWidget(self.btn_stop)

        # Separator
        sep = QLabel("|")
        sep.setStyleSheet("color: #555; padding: 0 4px;")
        layout.addWidget(sep)

        # Time display
        self.time_label = QLabel("00:00.00 / 00:00.00")
        self.time_label.setStyleSheet("color: #00cc44; font-family: monospace; font-size: 13px; padding: 0 8px;")
        layout.addWidget(self.time_label)

        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #555; padding: 0 4px;")
        layout.addWidget(sep2)

        # Selection info
        self.selection_label = QLabel("")
        self.selection_label.setStyleSheet("color: #7799dd; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.selection_label)

        layout.addStretch()

        # Zoom controls
        sep3 = QLabel("|")
        sep3.setStyleSheet("color: #555; padding: 0 4px;")
        layout.addWidget(sep3)

        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(zoom_label)

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setToolTip("Zoom out (Ctrl+-)")
        self.btn_zoom_out.setStyleSheet(btn_style)
        self.btn_zoom_out.setFixedWidth(28)
        self.btn_zoom_out.clicked.connect(self.zoom_out_clicked)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setToolTip("Zoom in (Ctrl+=)")
        self.btn_zoom_in.setStyleSheet(btn_style)
        self.btn_zoom_in.setFixedWidth(28)
        self.btn_zoom_in.clicked.connect(self.zoom_in_clicked)

        self.btn_zoom_fit = QPushButton("Fit")
        self.btn_zoom_fit.setToolTip("Zoom to fit (Ctrl+0)")
        self.btn_zoom_fit.setStyleSheet(btn_style)
        self.btn_zoom_fit.clicked.connect(self.zoom_fit_clicked)

        layout.addWidget(self.btn_zoom_out)
        layout.addWidget(self.btn_zoom_in)
        layout.addWidget(self.btn_zoom_fit)

    def set_time(self, current: str, total: str):
        self.time_label.setText(f"{current} / {total}")

    def set_selection_text(self, text: str):
        self.selection_label.setText(text)
