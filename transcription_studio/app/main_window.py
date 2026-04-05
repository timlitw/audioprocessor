"""Main window for Transcription Studio — two tabs: Transcribe + Video."""

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

from app.theme import DARK_THEME
from app.transcribe_tab import TranscribeTab
from app.video_tab import VideoTab
from audio.playback import PlaybackEngine
from core.project import TranscriptProject


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcription Studio")
        self.resize(1100, 700)

        # Shared state
        self.project = TranscriptProject()
        self.playback = PlaybackEngine(self)

        # Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.transcribe_tab = TranscribeTab(self.project, self.playback)
        self.video_tab = VideoTab(self.project)

        self.tabs.addTab(self.transcribe_tab, "Transcribe")
        self.tabs.addTab(self.video_tab, "Video")

        # Wire signals
        self.transcribe_tab.project_changed.connect(self._on_project_changed)

        self._build_menus()
        self._build_shortcuts()
        self.setStyleSheet(DARK_THEME)

    def _build_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        open_audio = QAction("Open &Audio...", self)
        open_audio.setShortcut(QKeySequence.StandardKey.Open)
        open_audio.triggered.connect(self.transcribe_tab._open_audio)
        file_menu.addAction(open_audio)

        open_project = QAction("Open &Project...", self)
        open_project.triggered.connect(self.transcribe_tab._open_project)
        file_menu.addAction(open_project)

        file_menu.addSeparator()

        save_action = QAction("&Save Project", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.transcribe_tab._save_project)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_shortcuts(self):
        space = QShortcut(Qt.Key.Key_Space, self)
        space.activated.connect(self.transcribe_tab._toggle_play)

    def _on_project_changed(self):
        self.video_tab.refresh_project()
        title = "Transcription Studio"
        if self.project.audio_file:
            title += f" \u2014 {self.project.audio_file}"
        self.setWindowTitle(title)

    def _show_about(self):
        QMessageBox.about(
            self,
            "About Transcription Studio",
            "<h3>Transcription Studio</h3>"
            "<p>Transcribe audio, identify speakers, and generate shareable videos.</p>"
            "<hr>"
            "<p><b>Open-source libraries:</b></p>"
            "<ul>"
            "<li>PyQt6 \u2014 GUI (GPL v3)</li>"
            "<li>faster-whisper \u2014 Speech recognition (MIT)</li>"
            "<li>NumPy / SciPy \u2014 Audio processing (BSD)</li>"
            "<li>soundfile / sounddevice \u2014 Audio I/O (BSD / MIT)</li>"
            "<li>imageio-ffmpeg / FFmpeg \u2014 Video encoding (BSD / LGPL)</li>"
            "</ul>"
        )

    def closeEvent(self, event):
        self.playback.stop()
        if self.project.is_dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save project before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self.transcribe_tab._save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        super().closeEvent(event)
