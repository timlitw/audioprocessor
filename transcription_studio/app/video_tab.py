"""Video tab — background picker, text style, preview with audio, render to MP4."""

import numpy as np
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QPushButton, QComboBox, QProgressBar, QFileDialog, QMessageBox,
    QApplication,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

from audio.playback import PlaybackEngine
from core.project import TranscriptProject
from video.frame_renderer import FrameRenderer
from video.render_worker import RenderWorker, RESOLUTIONS
from video.backgrounds import ALL_BACKGROUNDS, CustomImage
from video.text_styles import ALL_TEXT_STYLES


class VideoTab(QWidget):
    """Video generation workspace — preview with audio and render."""

    def __init__(self, project: TranscriptProject, playback: PlaybackEngine, parent=None):
        super().__init__(parent)
        self.project = project
        self.playback = playback
        self._renderer: FrameRenderer | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(33)  # ~30 fps
        self._preview_timer.timeout.connect(self._update_preview)
        self._previewing: bool = False
        self._render_worker: RenderWorker | None = None
        self._audio_data: np.ndarray | None = None
        self._custom_bg: CustomImage | None = None
        self._custom_image_paths: list[str] = []
        self._slide_duration: float = 30.0

        self._build_ui()

        # Listen to playback position for synced preview
        self.playback.position_changed.connect(self._on_playback_position)
        self.playback.playback_finished.connect(self._on_playback_finished)

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

        bg_group = QGroupBox("Background")
        bg_layout = QVBoxLayout(bg_group)
        self.bg_combo = QComboBox()
        for cls in ALL_BACKGROUNDS:
            self.bg_combo.addItem(cls.name)
        self.bg_combo.addItem("Custom Image(s)...")
        self.bg_combo.currentIndexChanged.connect(self._on_bg_changed)
        bg_layout.addWidget(self.bg_combo)

        self.bg_images_label = QLabel("")
        self.bg_images_label.setStyleSheet("color: #888; font-size: 11px;")
        self.bg_images_label.setVisible(False)
        bg_layout.addWidget(self.bg_images_label)

        settings_row.addWidget(bg_group)

        style_group = QGroupBox("Text Style")
        style_layout = QVBoxLayout(style_group)
        self.style_combo = QComboBox()
        for cls in ALL_TEXT_STYLES:
            self.style_combo.addItem(cls.name)
        self.style_combo.currentIndexChanged.connect(self._on_settings_changed)
        style_layout.addWidget(self.style_combo)
        settings_row.addWidget(style_group)

        res_group = QGroupBox("Resolution")
        res_layout = QVBoxLayout(res_group)
        self.res_combo = QComboBox()
        for key in RESOLUTIONS:
            self.res_combo.addItem(key)
        self.res_combo.setCurrentIndex(1)  # 1080p
        res_layout.addWidget(self.res_combo)
        settings_row.addWidget(res_group)

        layout.addLayout(settings_row)

        # Buttons row
        bottom_row = QHBoxLayout()

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        bottom_row.addWidget(self.progress, 1)

        self.btn_preview = QPushButton("\u25b6 Preview with Audio")
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self._toggle_preview)
        bottom_row.addWidget(self.btn_preview)

        self.btn_snapshot = QPushButton("Snapshot")
        self.btn_snapshot.setEnabled(False)
        self.btn_snapshot.setToolTip("Show a single frame from the first speech segment")
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

    def set_audio(self, data: np.ndarray, sample_rate: int):
        """Called when audio is loaded in the Transcribe tab."""
        self._audio_data = data
        self.playback.set_audio(data, sample_rate)

    def refresh_project(self):
        """Called when project data changes."""
        has_segments = len(self.project.segments) > 0
        self.btn_preview.setEnabled(has_segments and self._audio_data is not None)
        self.btn_snapshot.setEnabled(has_segments)
        self.btn_render.setEnabled(has_segments)
        if has_segments:
            n = len(self.project.segments)
            self.preview_label.setText(f"{n} segments ready.\nClick Preview to see and hear it, or Render MP4.")
        self._renderer = None  # force recreate on next use

    def _on_settings_changed(self):
        """Recreate renderer when background or text style changes."""
        self._renderer = None

    def _on_bg_changed(self, index: int):
        """Handle background combo change — open file picker for custom."""
        self._renderer = None
        is_custom = self.bg_combo.currentText() == "Custom Image(s)..."
        if is_custom:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Select Background Image(s)",
                "",
                "Images (*.jpg *.jpeg *.png *.bmp *.webp);;All Files (*)"
            )
            if paths:
                self._custom_image_paths = paths
                self._custom_bg = CustomImage(paths, self._slide_duration)
                count = len(paths)
                if count == 1:
                    name = Path(paths[0]).name
                    self.bg_images_label.setText(f"  {name}")
                else:
                    self.bg_images_label.setText(f"  {count} images (slideshow, {self._slide_duration:.0f}s each)")
                self.bg_images_label.setVisible(True)
            else:
                # User cancelled — revert to first option
                self.bg_combo.setCurrentIndex(0)
                self.bg_images_label.setVisible(False)
        else:
            self.bg_images_label.setVisible(False)
            self._custom_bg = None

    def _create_renderer(self, width: int = 640, height: int = 360) -> FrameRenderer:
        renderer = FrameRenderer(
            self.project, width, height,
            self.bg_combo.currentText(),
            self.style_combo.currentText(),
        )
        # Use custom image background if selected
        if self._custom_bg and self.bg_combo.currentText() == "Custom Image(s)...":
            custom = CustomImage(self._custom_image_paths, self._slide_duration)
            renderer.background = custom
        return renderer

    # --- Snapshot ---

    def _show_snapshot(self):
        if not self.project.segments:
            return

        t = 60.0
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

    # --- Preview with audio ---

    def _toggle_preview(self):
        if self._previewing:
            self._stop_preview()
        else:
            self._start_preview()

    def _start_preview(self):
        if not self.project.segments or self._audio_data is None:
            return

        self._renderer = self._create_renderer(640, 360)

        # Find first speech segment to start from
        start_time = 0.0
        for seg in self.project.segments:
            if seg.type == "speech":
                start_time = seg.start
                break

        # Start audio playback
        self.playback.play(start_time)

        self._previewing = True
        self.btn_preview.setText("\u23f9 Stop Preview")
        self._preview_timer.start()

    def _stop_preview(self):
        self._preview_timer.stop()
        self.playback.stop()
        self._previewing = False
        self.btn_preview.setText("\u25b6 Preview with Audio")

    def _on_playback_position(self, seconds: float):
        """Sync preview frame to audio playback position."""
        # Only render if we're in preview mode and on the Video tab
        pass  # actual rendering happens in _update_preview via timer

    def _update_preview(self):
        """Render a frame at the current audio playback position."""
        if self._renderer is None or not self._previewing:
            return

        current_time = self.playback.position_seconds
        image = self._renderer.render_frame(current_time)
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def _on_playback_finished(self):
        if self._previewing:
            self._stop_preview()

    # --- Render ---

    def _start_render(self):
        if not self.project.segments:
            return

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

        custom_paths = self._custom_image_paths if self._custom_bg else None
        self._render_worker = RenderWorker(
            project=self.project,
            output_path=output_path,
            background_name=self.bg_combo.currentText(),
            text_style_name=self.style_combo.currentText(),
            resolution_key=self.res_combo.currentText(),
            custom_image_paths=custom_paths,
            slide_duration=self._slide_duration,
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
