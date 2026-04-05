"""Video tab — background picker, text style, preview, render to MP4."""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QPushButton, QComboBox, QProgressBar, QFileDialog, QMessageBox,
    QApplication,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

from core.project import TranscriptProject
from video.frame_renderer import FrameRenderer
from video.render_worker import RenderWorker, RESOLUTIONS
from video.backgrounds import ALL_BACKGROUNDS
from video.text_styles import ALL_TEXT_STYLES


class VideoTab(QWidget):
    """Video generation workspace — preview and render."""

    def __init__(self, project: TranscriptProject, parent=None):
        super().__init__(parent)
        self.project = project
        self._renderer: FrameRenderer | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(33)  # ~30 fps
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_time: float = 0.0
        self._previewing: bool = False
        self._render_worker: RenderWorker | None = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Preview area
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("Transcribe audio first, then preview or render video.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("background: #1a1a2e; border-radius: 4px;")
        self.preview_label.setScaledContents(False)
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_group, 1)

        # Settings row
        settings_row = QHBoxLayout()

        # Background picker
        bg_group = QGroupBox("Background")
        bg_layout = QVBoxLayout(bg_group)
        self.bg_combo = QComboBox()
        for cls in ALL_BACKGROUNDS:
            self.bg_combo.addItem(cls.name)
        bg_layout.addWidget(self.bg_combo)
        settings_row.addWidget(bg_group)

        # Text style picker
        style_group = QGroupBox("Text Style")
        style_layout = QVBoxLayout(style_group)
        self.style_combo = QComboBox()
        for cls in ALL_TEXT_STYLES:
            self.style_combo.addItem(cls.name)
        style_layout.addWidget(self.style_combo)
        settings_row.addWidget(style_group)

        # Resolution picker
        res_group = QGroupBox("Resolution")
        res_layout = QVBoxLayout(res_group)
        self.res_combo = QComboBox()
        for key in RESOLUTIONS:
            self.res_combo.addItem(key)
        self.res_combo.setCurrentIndex(1)  # default 1080p
        res_layout.addWidget(self.res_combo)
        settings_row.addWidget(res_group)

        layout.addLayout(settings_row)

        # Buttons row
        bottom_row = QHBoxLayout()

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        bottom_row.addWidget(self.progress, 1)

        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self._toggle_preview)
        bottom_row.addWidget(self.btn_preview)

        self.btn_snapshot = QPushButton("Snapshot")
        self.btn_snapshot.setEnabled(False)
        self.btn_snapshot.setToolTip("Show a single frame at the 1-minute mark")
        self.btn_snapshot.clicked.connect(self._show_snapshot)
        bottom_row.addWidget(self.btn_snapshot)

        self.btn_render = QPushButton("Render MP4")
        self.btn_render.setEnabled(False)
        self.btn_render.setStyleSheet(
            "QPushButton:enabled { background: #1a6b3a; color: white; font-weight: bold; }"
        )
        self.btn_render.clicked.connect(self._start_render)
        bottom_row.addWidget(self.btn_render)

        layout.addLayout(bottom_row)

    def refresh_project(self):
        """Called when project data changes."""
        has_segments = len(self.project.segments) > 0
        self.btn_preview.setEnabled(has_segments)
        self.btn_snapshot.setEnabled(has_segments)
        self.btn_render.setEnabled(has_segments)
        if has_segments:
            n = len(self.project.segments)
            self.preview_label.setText(f"{n} segments ready.\nClick Snapshot to preview a frame, or Render MP4.")

    def _create_renderer(self, width: int = 640, height: int = 360) -> FrameRenderer:
        """Create a renderer at preview resolution."""
        return FrameRenderer(
            self.project, width, height,
            self.bg_combo.currentText(),
            self.style_combo.currentText(),
        )

    # --- Preview ---

    def _show_snapshot(self):
        """Render a single frame at a representative timestamp."""
        if not self.project.segments:
            return

        # Show a frame from the first speech segment
        t = 60.0  # default to 1 minute
        for seg in self.project.segments:
            if seg.type == "speech" and seg.text.strip():
                t = (seg.start + seg.end) / 2
                break

        renderer = self._create_renderer(960, 540)
        image = renderer.render_frame(t)
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def _toggle_preview(self):
        if self._previewing:
            self._stop_preview()
        else:
            self._start_preview()

    def _start_preview(self):
        if not self.project.segments:
            return
        self._renderer = self._create_renderer(640, 360)
        # Start from the first speech segment
        self._preview_time = 0.0
        for seg in self.project.segments:
            if seg.type == "speech":
                self._preview_time = seg.start
                break
        self._previewing = True
        self.btn_preview.setText("Stop Preview")
        self._preview_timer.start()

    def _stop_preview(self):
        self._preview_timer.stop()
        self._previewing = False
        self.btn_preview.setText("Preview")

    def _update_preview(self):
        if self._renderer is None:
            return

        image = self._renderer.render_frame(self._preview_time)
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

        self._preview_time += 1.0 / 30.0  # advance ~1 frame
        if self._preview_time >= self.project.audio_duration:
            self._stop_preview()

    # --- Render ---

    def _start_render(self):
        if not self.project.segments:
            return

        # Choose output path
        default_name = Path(self.project.audio_file).stem + ".mp4"
        default_dir = self.project.project_dir
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save Video", str(Path(default_dir) / default_name),
            "MP4 Video (*.mp4)"
        )
        if not output_path:
            return

        self.btn_render.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        self._render_worker = RenderWorker(
            project=self.project,
            output_path=output_path,
            background_name=self.bg_combo.currentText(),
            text_style_name=self.style_combo.currentText(),
            resolution_key=self.res_combo.currentText(),
        )
        self._render_worker.progress.connect(self._on_render_progress)
        self._render_worker.finished_render.connect(self._on_render_finished)
        self._render_worker.error.connect(self._on_render_error)
        self._render_worker.start()

    def _on_render_progress(self, pct: int, msg: str):
        self.progress.setValue(pct)
        self.progress.setFormat(msg)

    def _on_render_finished(self, output_path: str):
        self.progress.setVisible(False)
        self.btn_render.setEnabled(True)
        self.btn_preview.setEnabled(True)
        QMessageBox.information(
            self, "Render Complete",
            f"Video saved to:\n{output_path}\n\n"
            "You can play it in Windows Media Player or upload to YouTube."
        )

    def _on_render_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_render.setEnabled(True)
        self.btn_preview.setEnabled(True)
        QMessageBox.critical(self, "Render Error", msg)
