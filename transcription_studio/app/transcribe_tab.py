"""Transcribe tab — audio loading, transcription controls, editable transcript."""

import sys
import numpy as np
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem, QSplitter, QFileDialog,
    QProgressBar, QGroupBox, QApplication, QHeaderView, QMenu,
    QAbstractItemView, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QShortcut, QKeySequence

from audio.playback import PlaybackEngine
from core.project import TranscriptProject, Segment, Word, Speaker
from core.settings import get_last_directory, set_last_directory

# Reuse file_io from audio_processor (parent project)
import importlib.util
_file_io_path = str(Path(__file__).resolve().parent.parent.parent / "audio" / "file_io.py")
_spec = importlib.util.spec_from_file_location("audio_processor_file_io", _file_io_path)
_file_io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_file_io)
load_audio = _file_io.load_audio
FILE_FILTER = _file_io.FILE_FILTER

# Table column indices
COL_TIME = 0
COL_SPEAKER = 1
COL_TEXT = 2
COL_TYPE = 3
COL_BG = 4


class TranscribeTab(QWidget):
    """Main transcription workspace with editable transcript table."""

    project_changed = pyqtSignal()

    def __init__(self, project: TranscriptProject, playback: PlaybackEngine, parent=None):
        super().__init__(parent)
        self.project = project
        self.playback = playback
        self._audio_data: np.ndarray | None = None
        self._updating_table: bool = False  # flag to prevent edit loops

        self._build_ui()
        self._connect_signals()
        self._build_shortcuts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- Top bar ---
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

        # --- Main area: transcript table + info panel ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Transcript table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Time", "Speaker", "Text", "Type", "BG"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_TIME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_SPEAKER, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_TEXT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_BG, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setStyleSheet("""
            QTableWidget {
                font-family: 'Segoe UI', sans-serif; font-size: 13px;
                gridline-color: #333;
            }
            QTableWidget::item { padding: 4px 6px; }
            QTableWidget::item:selected { background: #3a5a8a; }
            QHeaderView::section {
                background: #333; color: #aaa; padding: 4px 8px;
                border: none; border-bottom: 1px solid #555;
            }
        """)
        splitter.addWidget(self.table)

        # Info panel
        info_panel = QGroupBox("Segment Info")
        info_layout = QVBoxLayout(info_panel)
        self.info_label = QLabel(
            "Load an audio file and click Transcribe.\n\n"
            "After transcription:\n"
            "- Click a row to play that segment\n"
            "- Double-click the Text column to edit\n"
            "- Right-click for more options\n"
            "- Tab = replay segment\n"
            "- Enter = next segment"
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #999;")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()
        splitter.addWidget(info_panel)

        splitter.setSizes([700, 200])
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
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellChanged.connect(self._on_cell_changed)

    def _build_shortcuts(self):
        # Tab = replay current segment
        tab_key = QShortcut(Qt.Key.Key_Tab, self.table)
        tab_key.activated.connect(self._replay_current_segment)

        # Enter = move to next segment and play it
        enter_key = QShortcut(Qt.Key.Key_Return, self.table)
        enter_key.activated.connect(self._next_segment)

    # --- Context menu ---

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #d0d0d0; border: 1px solid #555; }
            QMenu::item:selected { background-color: #3d3d3d; }
            QMenu::item:disabled { color: #666; }
        """)

        seg = self._get_segment_for_row(row)
        if seg is None:
            return

        act_play = menu.addAction(f"Play segment ({self.project.format_time(seg.start)})")
        act_play.triggered.connect(lambda: self._play_segment(seg))

        menu.addSeparator()

        act_edit = menu.addAction("Edit text")
        act_edit.triggered.connect(lambda: self.table.editItem(self.table.item(row, COL_TEXT)))

        menu.addSeparator()

        # Type submenu
        type_menu = menu.addMenu("Set type")
        for t in ["speech", "singing", "silence"]:
            act = type_menu.addAction(t.title())
            act.triggered.connect(lambda checked, typ=t: self._set_segment_type(row, typ))

        menu.addSeparator()

        act_split = menu.addAction("Split at midpoint")
        act_split.triggered.connect(lambda: self._split_segment(row))

        if row > 0:
            act_merge_up = menu.addAction("Merge with previous")
            act_merge_up.triggered.connect(lambda: self._merge_segments(row - 1, row))

        if row < self.table.rowCount() - 1:
            act_merge_down = menu.addAction("Merge with next")
            act_merge_down.triggered.connect(lambda: self._merge_segments(row, row + 1))

        menu.addSeparator()

        act_delete = menu.addAction("Delete segment")
        act_delete.triggered.connect(lambda: self._delete_segment(row))

        menu.addSeparator()

        # Background change
        bg_menu = menu.addMenu("Set Background Change Here")

        # Procedural options
        from video.backgrounds import ALL_BACKGROUNDS
        for bg_cls in ALL_BACKGROUNDS:
            act = bg_menu.addAction(bg_cls.name)
            act.triggered.connect(lambda checked, name=bg_cls.name: self._set_background_change(row, name))

        bg_menu.addSeparator()
        act_bg_image = bg_menu.addAction("Choose Image...")
        act_bg_image.triggered.connect(lambda: self._set_background_image(row))

        if seg.background_change:
            act_clear_bg = menu.addAction("Clear Background Change")
            act_clear_bg.triggered.connect(lambda: self._clear_background_change(row))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    # --- Segment editing ---

    def _on_cell_changed(self, row: int, col: int):
        """Handle inline edits to text or speaker columns."""
        if self._updating_table:
            return

        seg = self._get_segment_for_row(row)
        if seg is None:
            return

        if col == COL_TEXT:
            item = self.table.item(row, COL_TEXT)
            new_text = item.text().strip()
            if new_text != seg.text:
                seg.text = new_text
                self.project.mark_dirty()
                self.info_label.setText(f"Edited segment {seg.id} at {self.project.format_time(seg.start)}")

        elif col == COL_SPEAKER:
            item = self.table.item(row, COL_SPEAKER)
            new_name = item.text().strip()
            if new_name:
                # Find or create speaker
                speaker_id = None
                for s in self.project.speakers:
                    if s.label == new_name:
                        speaker_id = s.id
                        break
                if speaker_id is None:
                    # Create new speaker
                    colors = ["#4a9eff", "#ff6b6b", "#6bff6b", "#ffaa33", "#cc66ff", "#66ffcc"]
                    color = colors[len(self.project.speakers) % len(colors)]
                    speaker_id = f"speaker_{len(self.project.speakers) + 1:02d}"
                    self.project.speakers.append(Speaker(speaker_id, new_name, color))

                seg.speaker_id = speaker_id
                self.project.mark_dirty()
                # Refresh display to show sticky propagation
                self._refresh_display_speakers()
                self.info_label.setText(f"Speaker set to '{new_name}' from {self.project.format_time(seg.start)} onward")

    def _set_segment_type(self, row: int, seg_type: str):
        seg = self._get_segment_for_row(row)
        if seg is None:
            return
        seg.type = seg_type
        if seg_type == "singing":
            seg.text = seg.text or "[Singing]"
        elif seg_type == "silence":
            seg.text = "[Silence]"
        self.project.mark_dirty()
        self._refresh_row(row)

    def _split_segment(self, row: int):
        seg = self._get_segment_for_row(row)
        if seg is None or seg.duration < 0.5:
            return

        mid_time = (seg.start + seg.end) / 2

        # Split text roughly in half by words
        words = seg.text.split()
        mid_word = len(words) // 2
        text1 = " ".join(words[:mid_word]) if mid_word > 0 else seg.text
        text2 = " ".join(words[mid_word:]) if mid_word < len(words) else ""

        # Create new segment
        new_id = max(s.id for s in self.project.segments) + 1
        new_seg = Segment(
            id=new_id,
            type=seg.type,
            start=mid_time,
            end=seg.end,
            text=text2,
            speaker_id=seg.speaker_id,
        )

        # Shorten original
        seg.end = mid_time
        seg.text = text1

        # Insert into project
        idx = self.project.segments.index(seg)
        self.project.segments.insert(idx + 1, new_seg)
        self.project.mark_dirty()

        self._refresh_table()
        self.table.selectRow(row)

    def _merge_segments(self, row1: int, row2: int):
        seg1 = self._get_segment_for_row(row1)
        seg2 = self._get_segment_for_row(row2)
        if seg1 is None or seg2 is None:
            return

        seg1.end = seg2.end
        seg1.text = (seg1.text + " " + seg2.text).strip()
        self.project.segments.remove(seg2)
        self.project.mark_dirty()

        self._refresh_table()
        self.table.selectRow(row1)

    def _delete_segment(self, row: int):
        seg = self._get_segment_for_row(row)
        if seg is None:
            return
        self.project.segments.remove(seg)
        self.project.mark_dirty()
        self._refresh_table()

    def _set_background_change(self, row: int, bg_name: str):
        seg = self._get_segment_for_row(row)
        if seg is None:
            return
        seg.background_change = bg_name
        self.project.mark_dirty()
        self._refresh_row(row)
        self.info_label.setText(f"Background changes to '{bg_name}' at {self.project.format_time(seg.start)}")

    def _set_background_image(self, row: int):
        seg = self._get_segment_for_row(row)
        if seg is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Background Image", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp);;All Files (*)"
        )
        if path:
            seg.background_change = f"image:{path}"
            self.project.mark_dirty()
            self._refresh_row(row)
            self.info_label.setText(f"Background image set at {self.project.format_time(seg.start)}")

    def _clear_background_change(self, row: int):
        seg = self._get_segment_for_row(row)
        if seg is None:
            return
        seg.background_change = ""
        self.project.mark_dirty()
        self._refresh_row(row)

    def _refresh_display_speakers(self):
        """Update the speaker column display to show sticky names."""
        self._updating_table = True
        current_speaker = ""
        for i in range(self.table.rowCount()):
            seg = self._get_segment_for_row(i)
            if seg is None:
                continue
            if seg.speaker_id:
                current_speaker = self.project.get_speaker_label(seg.speaker_id)
            speaker_item = self.table.item(i, COL_SPEAKER)
            if speaker_item:
                if seg.speaker_id:
                    speaker_item.setText(current_speaker)
                    speaker_item.setForeground(QColor(160, 200, 255))
                elif current_speaker:
                    speaker_item.setText(f"  ({current_speaker})")
                    speaker_item.setForeground(QColor(100, 100, 100))
                else:
                    speaker_item.setText("")
        self._updating_table = False

    def _replay_current_segment(self):
        row = self.table.currentRow()
        if row < 0:
            return
        seg = self._get_segment_for_row(row)
        if seg:
            self._play_segment(seg)

    def _next_segment(self):
        row = self.table.currentRow()
        next_row = row + 1
        if next_row < self.table.rowCount():
            self.table.selectRow(next_row)
            seg = self._get_segment_for_row(next_row)
            if seg:
                self._play_segment(seg)

    def _play_segment(self, seg: Segment):
        self.playback.stop()
        self.playback.play(seg.start, seg.end)
        self.btn_play.setText("\u23f8 Pause")

    # --- Table helpers ---

    def _get_segment_for_row(self, row: int) -> Segment | None:
        if row < 0 or row >= self.table.rowCount():
            return None
        item = self.table.item(row, COL_TIME)
        if item is None:
            return None
        seg_id = item.data(Qt.ItemDataRole.UserRole)
        for seg in self.project.segments:
            if seg.id == seg_id:
                return seg
        return None

    def _refresh_table(self):
        self._updating_table = True
        self.table.setRowCount(0)
        for seg in self.project.segments:
            self._add_segment_row(seg)
        self._updating_table = False

    def _add_segment_row(self, seg: Segment):
        self._updating_table = True
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Time (not editable)
        time_item = QTableWidgetItem(self.project.format_time(seg.start))
        time_item.setData(Qt.ItemDataRole.UserRole, seg.id)
        time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, COL_TIME, time_item)

        # Speaker (EDITABLE — double-click to type name, sticky forward)
        seg_idx = self.project.segments.index(seg) if seg in self.project.segments else row
        if seg.speaker_id:
            speaker_text = self.project.get_speaker_label(seg.speaker_id)
        else:
            # Show inherited speaker in dim
            inherited = self.project.get_effective_speaker_label(seg_idx)
            speaker_text = f"  ({inherited})" if inherited else ""
        speaker_item = QTableWidgetItem(speaker_text)
        if seg.speaker_id:
            speaker_item.setForeground(QColor(160, 200, 255))
        else:
            speaker_item.setForeground(QColor(100, 100, 100))
        self.table.setItem(row, COL_SPEAKER, speaker_item)

        # Text (EDITABLE — double-click to edit)
        text_item = QTableWidgetItem(seg.text)
        self.table.setItem(row, COL_TEXT, text_item)

        # Type badge (not editable — use context menu)
        type_item = QTableWidgetItem(seg.type.title())
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if seg.type == "singing":
            type_item.setForeground(QColor(0, 180, 180))
        elif seg.type == "silence":
            type_item.setForeground(QColor(120, 120, 120))
        self.table.setItem(row, COL_TYPE, type_item)

        # Background change indicator
        bg_text = ""
        if seg.background_change:
            bg = seg.background_change
            if bg.startswith("image:"):
                bg_text = "\U0001f5bc " + Path(bg[6:]).name  # 🖼 + filename
            else:
                bg_text = "\u25cf " + bg  # ● + name
        bg_item = QTableWidgetItem(bg_text)
        bg_item.setFlags(bg_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if bg_text:
            bg_item.setForeground(QColor(200, 180, 100))
        self.table.setItem(row, COL_BG, bg_item)

        self._updating_table = False

    def _refresh_row(self, row: int):
        seg = self._get_segment_for_row(row)
        if seg is None:
            return
        self._updating_table = True
        self.table.item(row, COL_TEXT).setText(seg.text)

        type_item = self.table.item(row, COL_TYPE)
        type_item.setText(seg.type.title())
        if seg.type == "singing":
            type_item.setForeground(QColor(0, 180, 180))
        elif seg.type == "silence":
            type_item.setForeground(QColor(120, 120, 120))
        else:
            type_item.setForeground(QColor(208, 208, 208))

        # Update BG column
        bg_item = self.table.item(row, COL_BG)
        if bg_item:
            if seg.background_change:
                bg = seg.background_change
                if bg.startswith("image:"):
                    bg_item.setText("\U0001f5bc " + Path(bg[6:]).name)
                else:
                    bg_item.setText("\u25cf " + bg)
                bg_item.setForeground(QColor(200, 180, 100))
            else:
                bg_item.setText("")

        self._updating_table = False

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
            self._refresh_table()

            set_last_directory(str(Path(path).parent))
            self.project_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _open_project(self):
        last_dir = get_last_directory()
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", last_dir, "Transcript Files (*.json);;All Files (*)"
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
            self._refresh_table()
            self._update_time(0.0)
            set_last_directory(str(Path(path).parent))
            self.project_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

    def _save_project(self):
        try:
            self.project.save()
            self.info_label.setText(f"Saved to {self.project.get_transcript_path()}")
        except Exception as e:
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

        # Clear existing segments
        self.project.segments.clear()
        self._refresh_table()

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
        self._add_segment_row(seg)
        # Auto-scroll to latest segment
        self.table.scrollToBottom()

    def _on_transcribe_finished(self):
        self.progress.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        self.project.mark_dirty()
        n = len(self.project.segments)
        self.info_label.setText(f"Transcription complete: {n} segments.\nDouble-click text to edit. Right-click for options.")
        self.file_label.setText(
            f"{self.project.audio_file}  |  {self.project.audio_duration / 60:.1f} min  |  {n} segments"
        )
        self.project_changed.emit()

    def _on_transcribe_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        self.info_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Transcription Error", msg)

    # --- Playback ---

    def _on_cell_clicked(self, row: int, col: int):
        seg = self._get_segment_for_row(row)
        if seg:
            self._update_time(seg.start)
            dur = seg.end - seg.start
            speaker = self.project.get_speaker_label(seg.speaker_id) if seg.speaker_id else "Unknown"
            self.info_label.setText(
                f"Segment {seg.id}\n"
                f"Time: {self.project.format_time(seg.start)} — {self.project.format_time(seg.end)}\n"
                f"Duration: {dur:.1f}s\n"
                f"Speaker: {speaker}\n"
                f"Type: {seg.type}\n"
                f"Confidence: {seg.confidence:.2f}\n\n"
                f"Click to select, double-click text to edit.\n"
                f"Tab = replay, Enter = next segment."
            )

    def _toggle_play(self):
        if self.playback.is_playing:
            self.playback.pause()
            self.btn_play.setText("\u25b6 Play")
        elif self.playback.is_paused:
            self.playback.play()
            self.btn_play.setText("\u23f8 Pause")
        else:
            # Play from current segment or beginning
            row = self.table.currentRow()
            seg = self._get_segment_for_row(row) if row >= 0 else None
            if seg:
                self.playback.play(seg.start)
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
        for i in range(self.table.rowCount()):
            seg = self._get_segment_for_row(i)
            if seg and seg.start <= seconds < seg.end:
                if self.table.currentRow() != i:
                    self.table.selectRow(i)
                    self.table.scrollTo(self.table.model().index(i, 0))
                return
