"""Video tab — background picker, text style, preview, render."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QPushButton, QComboBox, QProgressBar,
)
from PyQt6.QtCore import Qt

from core.project import TranscriptProject


class VideoTab(QWidget):
    """Video generation workspace — placeholder, built out in M6-M7."""

    def __init__(self, project: TranscriptProject, parent=None):
        super().__init__(parent)
        self.project = project
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Preview area (placeholder)
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("Video preview will appear here.\nTranscribe audio first.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("color: #666; font-size: 14px; background: #1a1a2e; border-radius: 4px;")
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_group, 1)

        # Settings row
        settings_row = QHBoxLayout()

        # Background picker
        bg_group = QGroupBox("Background")
        bg_layout = QVBoxLayout(bg_group)
        self.bg_combo = QComboBox()
        self.bg_combo.addItems(["Warm Bokeh", "Starfield", "Gradient Sweep", "Waves", "Solid Dark", "Custom Image...", "Custom Video..."])
        bg_layout.addWidget(self.bg_combo)
        settings_row.addWidget(bg_group)

        # Text style picker
        style_group = QGroupBox("Text Style")
        style_layout = QVBoxLayout(style_group)
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Sentence at a Time", "Subtitle (Bottom)", "Word-by-Word Highlight", "Scroll Up"])
        style_layout.addWidget(self.style_combo)
        settings_row.addWidget(style_group)

        # Resolution picker
        res_group = QGroupBox("Resolution")
        res_layout = QVBoxLayout(res_group)
        self.res_combo = QComboBox()
        self.res_combo.addItems(["1280x720 (720p)", "1920x1080 (1080p)", "3840x2160 (4K)"])
        self.res_combo.setCurrentIndex(1)
        res_layout.addWidget(self.res_combo)
        settings_row.addWidget(res_group)

        layout.addLayout(settings_row)

        # Progress + render button
        bottom_row = QHBoxLayout()

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        bottom_row.addWidget(self.progress, 1)

        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setEnabled(False)
        bottom_row.addWidget(self.btn_preview)

        self.btn_render = QPushButton("Render MP4")
        self.btn_render.setEnabled(False)
        self.btn_render.setStyleSheet(
            "QPushButton:enabled { background: #1a6b3a; color: white; font-weight: bold; }"
        )
        bottom_row.addWidget(self.btn_render)

        layout.addLayout(bottom_row)

    def refresh_project(self):
        """Called when project data changes (e.g., after transcription)."""
        has_segments = len(self.project.segments) > 0
        self.btn_preview.setEnabled(has_segments)
        self.btn_render.setEnabled(has_segments)
        if has_segments:
            n = len(self.project.segments)
            self.preview_label.setText(
                f"Ready to generate video.\n{n} segments loaded.\n\nClick Preview or Render MP4."
            )
