"""Transcribe tab — audio loading, transcription controls, transcript display."""

import sys
import numpy as np
import soundfile as sf
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QListWidget, QListWidgetItem, QSplitter, QFileDialog,
    QProgressBar, QGroupBox, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal

from audio.playback import PlaybackEngine
from core.project import TranscriptProject, Segment
from core.settings import get_last_directory, set_last_directory

# Reuse file_io from audio_processor (parent project)
import importlib.util
_file_io_path = str(Path(__file__).resolve().parent.parent.parent / "audio" / "file_io.py")
_spec = importlib.util.spec_from_file_location("audio_processor_file_io", _file_io_path)
_file_io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_file_io)
load_audio = _file_io.load_audio
FILE_FILTER = _file_io.FILE_FILTER


class TranscribeTab(QWidget):
    """Main transcription workspace."""

    project_changed = pyqtSignal()  # emitted when project data changes

    def __init__(self, project: TranscriptProject, playback: PlaybackEngine, parent=None):
        super().__init__(parent)
        self.project = project
        self.playback = playback
        self._audio_data: np.ndarray | None = None

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- Top bar: file info + controls ---
        top_bar = QHBoxLayout()

        self.btn_open = QPushButton("Open Audio")
        self.btn_open.clicked.connect(self._open_audio)
        top_bar.addWidget(self.btn_open)

        self.btn_open_project = QPushButton("Open Project")
        self.btn_open_project.clicked.connect(self._open_project)
        top_bar.addWidget(self.btn_open_project)

        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet("color: #888; padding: 0 12px;")
        top_bar.addWidget(self.file_label, 1)

        # Model selector
        top_bar.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium"])
        self.model_combo.setCurrentText("base")
        self.model_combo.setToolTip("Whisper model size — larger = more accurate but slower")
        top_bar.addWidget(self.model_combo)

        self.btn_transcribe = QPushButton("Transcribe")
        self.btn_transcribe.setEnabled(False)
        self.btn_transcribe.setStyleSheet(
            "QPushButton:enabled { background: #1a6b3a; color: white; font-weight: bold; }"
        )
        self.btn_transcribe.clicked.connect(self._start_transcription)
        top_bar.addWidget(self.btn_transcribe)

        layout.addLayout(top_bar)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        # --- Main area: splitter with transcript list + info panel ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Transcript segment list
        self.segment_list = QListWidget()
        self.segment_list.setAlternatingRowColors(True)
        self.segment_list.setStyleSheet("""
            QListWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background: #3a5a8a; }
        """)
        splitter.addWidget(self.segment_list)

        # Info / speaker panel (placeholder for M4/M5)
        info_panel = QGroupBox("Info")
        info_layout = QVBoxLayout(info_panel)
        self.info_label = QLabel("Load an audio file and click Transcribe to begin.")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #999;")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()
        splitter.addWidget(info_panel)

        splitter.setSizes([600, 200])
        layout.addWidget(splitter, 1)

        # --- Transport bar ---
        transport = QHBoxLayout()

        self.btn_play = QPushButton("\u25b6 Play")
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self._toggle_play)
        transport.addWidget(self.btn_play)

        self.btn_stop = QPushButton("\u23f9 Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        transport.addWidget(self.btn_stop)

        self.time_label = QLabel("00:00.00 / 00:00.00")
        self.time_label.setStyleSheet("color: #00cc44; font-family: monospace; font-size: 13px; padding: 0 12px;")
        transport.addWidget(self.time_label)

        transport.addStretch()

        self.btn_save = QPushButton("Save Project")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_project)
        transport.addWidget(self.btn_save)

        layout.addLayout(transport)

    def _connect_signals(self):
        self.playback.position_changed.connect(self._on_playback_position)
        self.playback.playback_finished.connect(self._on_playback_finished)
        self.segment_list.itemClicked.connect(self._on_segment_clicked)

    # --- File operations ---

    def _open_audio(self):
        last_dir = get_last_directory()
        path, _ = QFileDialog.getOpenFileName(self, "Open Audio File", last_dir, FILE_FILTER)
        if not path:
            return
        self._load_audio(path)

    def _load_audio(self, path: str):
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            data, sr = load_audio(path)
            self._audio_data = data
            self.playback.set_audio(data, sr)

            duration = len(data) / sr
            self.project.new_project(path, duration, sr)

            self.file_label.setText(f"{Path(path).name}  |  {sr} Hz  |  {duration / 60:.1f} min")
            self.btn_transcribe.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.btn_save.setEnabled(True)
            self._update_time(0.0)

            set_last_directory(str(Path(path).parent))
            self.project_changed.emit()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to load:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _open_project(self):
        last_dir = get_last_directory()
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", last_dir, "Transcript Files (transcript.json);;All Files (*)"
        )
        if not path:
            return
        try:
            self.project.load(path)
            audio_path = self.project.get_audio_path()
            if Path(audio_path).exists():
                data, sr = load_audio(audio_path)
                self._audio_data = data
                self.playback.set_audio(data, sr)
                self.btn_play.setEnabled(True)
                self.btn_stop.setEnabled(True)

            self.file_label.setText(
                f"{self.project.audio_file}  |  {self.project.audio_duration / 60:.1f} min  |  "
                f"{len(self.project.segments)} segments"
            )
            self.btn_transcribe.setEnabled(self._audio_data is not None)
            self.btn_save.setEnabled(True)
            self._refresh_segment_list()
            self._update_time(0.0)
            set_last_directory(str(Path(path).parent))
            self.project_changed.emit()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

    def _save_project(self):
        try:
            self.project.save()
            self.info_label.setText(f"Saved to {self.project.get_transcript_path()}")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    # --- Transcription ---

    def _start_transcription(self):
        if self._audio_data is None:
            return

        model_size = self.model_combo.currentText()
        self.btn_transcribe.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress.setFormat(f"Loading {model_size} model...")
        self.info_label.setText(f"Transcribing with Whisper ({model_size})...")

        # Import and run whisper worker
        from transcription.whisper_worker import WhisperWorker

        self._whisper_worker = WhisperWorker(
            self.project.get_audio_path(),
            model_size,
        )
        self._whisper_worker.progress.connect(self._on_transcribe_progress)
        self._whisper_worker.segment_ready.connect(self._on_segment_ready)
        self._whisper_worker.finished_transcription.connect(self._on_transcribe_finished)
        self._whisper_worker.error.connect(self._on_transcribe_error)
        self._whisper_worker.start()

    def _on_transcribe_progress(self, pct: int, msg: str):
        self.progress.setValue(pct)
        self.progress.setFormat(msg)

    def _on_segment_ready(self, seg_dict: dict):
        """Called as each segment is transcribed — update UI live."""
        from core.project import Segment, Word
        words = [Word(w["word"], w["start"], w["end"]) for w in seg_dict.get("words", [])]
        seg = Segment(
            id=len(self.project.segments) + 1,
            type="speech",
            start=seg_dict["start"],
            end=seg_dict["end"],
            text=seg_dict["text"],
            words=words,
            confidence=seg_dict.get("confidence", 0.0),
        )
        self.project.segments.append(seg)
        self._add_segment_to_list(seg)

    def _on_transcribe_finished(self):
        self.progress.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        self.project.mark_dirty()
        n = len(self.project.segments)
        self.info_label.setText(f"Transcription complete: {n} segments found.")
        self.file_label.setText(
            f"{self.project.audio_file}  |  {self.project.audio_duration / 60:.1f} min  |  {n} segments"
        )
        self.project_changed.emit()

    def _on_transcribe_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        self.info_label.setText(f"Error: {msg}")
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Transcription Error", msg)

    # --- Segment list ---

    def _refresh_segment_list(self):
        self.segment_list.clear()
        for seg in self.project.segments:
            self._add_segment_to_list(seg)

    def _add_segment_to_list(self, seg: Segment):
        time_str = self.project.format_time(seg.start)
        speaker = self.project.get_speaker_label(seg.speaker_id) if seg.speaker_id else ""
        prefix = f"[{time_str}]"
        if speaker:
            prefix += f" {speaker}:"
        if seg.type == "singing":
            text = f"{prefix} {seg.note or '[Singing]'}"
        elif seg.type == "silence":
            text = f"{prefix} [Silence]"
        else:
            text = f"{prefix} {seg.text}"

        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, seg.id)

        if seg.type == "singing":
            item.setForeground(Qt.GlobalColor.darkCyan)
        elif seg.type == "silence":
            item.setForeground(Qt.GlobalColor.darkGray)

        self.segment_list.addItem(item)

    def _on_segment_clicked(self, item: QListWidgetItem):
        seg_id = item.data(Qt.ItemDataRole.UserRole)
        for seg in self.project.segments:
            if seg.id == seg_id:
                self.playback.seek(seg.start)
                self._update_time(seg.start)
                # Play this segment
                self.playback.play(seg.start, seg.end)
                break

    # --- Playback ---

    def _toggle_play(self):
        if self.playback.is_playing:
            self.playback.pause()
            self.btn_play.setText("\u25b6 Play")
        elif self.playback.is_paused:
            self.playback.play()
            self.btn_play.setText("\u23f8 Pause")
        else:
            self.playback.play()
            self.btn_play.setText("\u23f8 Pause")

    def _stop(self):
        self.playback.stop()
        self.btn_play.setText("\u25b6 Play")
        self._update_time(0.0)

    def _on_playback_position(self, seconds: float):
        self._update_time(seconds)
        self._highlight_current_segment(seconds)

    def _on_playback_finished(self):
        self.btn_play.setText("\u25b6 Play")

    def _update_time(self, seconds: float):
        current = self.project.format_time(seconds)
        total = self.project.format_time(self.project.audio_duration)
        self.time_label.setText(f"{current} / {total}")

    def _highlight_current_segment(self, seconds: float):
        """Highlight the segment at the current playback position."""
        for i in range(self.segment_list.count()):
            item = self.segment_list.item(i)
            seg_id = item.data(Qt.ItemDataRole.UserRole)
            for seg in self.project.segments:
                if seg.id == seg_id and seg.start <= seconds < seg.end:
                    self.segment_list.setCurrentItem(item)
                    self.segment_list.scrollToItem(item)
                    return
