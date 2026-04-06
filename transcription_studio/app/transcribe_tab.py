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
from audio.file_io import load_audio, FILE_FILTER
from core.project import TranscriptProject, Segment, Word, Speaker
from core.settings import get_last_directory, set_last_directory, get_lyrics_dir
from lyrics.library import LyricsLibrary
from lyrics.matcher import LyricsMatcher, SongTracker
from lyrics.alignment import align_words
from lyrics.matcher_v2 import match_song_words

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

        # Lyrics matching
        self._lyrics_library = LyricsLibrary(get_lyrics_dir())
        self._lyrics_library.scan()
        self._lyrics_matcher = LyricsMatcher(self._lyrics_library)
        self._lyrics_tracker: SongTracker | None = None

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
        self.model_combo.addItems(["small", "medium", "large-v3"])
        self.model_combo.setCurrentText("medium")
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
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.verticalHeader().setMinimumSectionSize(28)

        # Expand row when editing for better visibility
        self._editing_row = -1
        self._original_row_height = 32
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
            QTableWidget QLineEdit {
                font-family: 'Segoe UI', sans-serif; font-size: 14px;
                padding: 2px 6px;
                margin: 0px;
                background: #1a1a2e; color: #ffffff;
                border: 2px solid #4a9eff;
                min-height: 28px;
            }
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
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.itemDelegate().closeEditor.connect(self._on_editor_closed)

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

        # Lyrics matching
        if self._lyrics_library.song_count > 0:
            act_match = menu.addAction(f"Match Lyrics ({self._lyrics_library.song_count} songs)")
            act_match.triggered.connect(lambda: self._match_lyrics(row))

        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if len(selected_rows) >= 1:
            act_save_song = menu.addAction("Save as Song...")
            act_save_song.triggered.connect(lambda: self._save_as_song(selected_rows))

        act_group = menu.addAction("Group Song Lines")
        act_group.triggered.connect(self._group_lyrics_manual)

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

    def _on_cell_double_clicked(self, row: int, col: int):
        """Expand the row when user starts editing for better visibility."""
        if col in (COL_TEXT, COL_SPEAKER):
            self._editing_row = row
            self._original_row_height = self.table.rowHeight(row)
            self.table.setRowHeight(row, 56)

    def _on_editor_closed(self):
        """Restore row height after editing finishes."""
        if self._editing_row >= 0:
            self.table.setRowHeight(self._editing_row, self._original_row_height)
            self._editing_row = -1

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

                # If playback was paused (review mode), replay edited segment then continue
                if self.playback.is_paused:
                    self.playback.play(seg.start)
                    self.btn_play.setText("\u23f8 Pause")

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

    # --- Lyrics matching ---

    def _match_lyrics(self, row: int):
        """Manual lyrics lookup for a single segment."""
        seg = self._get_segment_for_row(row)
        if seg is None:
            return

        result = self._lyrics_matcher.match_segment(seg.text, threshold=0.40)
        if result is None:
            QMessageBox.information(self, "Match Lyrics", "No matching song found in the lyrics library.")
            return

        reply = QMessageBox.question(
            self, "Match Lyrics",
            f"Best match: {result.song.title} ({result.score:.0%})\n\n"
            f"Replace:\n  {seg.text}\n\nWith:\n  {result.matched_text}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if seg.words:
                seg.words = align_words(seg.words, result.matched_text)
            seg.text = result.matched_text
            seg.note = f"Matched: {result.song.title} ({result.score:.0%})"
            self.project.mark_dirty()
            self._refresh_row(row)
            self.info_label.setText(f"Matched to: {result.song.title}")
            self.project_changed.emit()

            # Continue matching subsequent segments sequentially
            self._continue_matching(row + 1, result.song, result.line_end)

    def _continue_matching(self, start_row: int, song, expected_line: int):
        """Walk subsequent segments, matching sequentially through the song."""
        from PyQt6.QtWidgets import QCheckBox

        approve_all = False
        row = start_row

        while row < self.table.rowCount() and expected_line < len(song.lines):
            seg = self._get_segment_for_row(row)
            if seg is None:
                break

            result = self._lyrics_matcher.match_in_song(
                seg.text, song, expected_line=expected_line,
            )

            if result is None or result.score < 0.35:
                # No match — song may have ended
                break

            if not approve_all:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Match Lyrics")
                msg_box.setText(
                    f"{song.title} — next line ({result.score:.0%})\n\n"
                    f"Replace:\n  {seg.text}\n\nWith:\n  {result.matched_text}"
                )
                cb = QCheckBox("Approve all remaining matches for this song")
                msg_box.setCheckBox(cb)
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
                reply = msg_box.exec()

                if reply == QMessageBox.StandardButton.Cancel:
                    break
                if reply == QMessageBox.StandardButton.No:
                    # Skip this segment, keep going
                    row += 1
                    continue
                if cb.isChecked():
                    approve_all = True

            # Apply the match
            if seg.words:
                seg.words = align_words(seg.words, result.matched_text)
            seg.text = result.matched_text
            seg.note = f"Matched: {song.title} ({result.score:.0%})"
            self.project.mark_dirty()
            self._refresh_row(row)

            expected_line = result.line_end
            row += 1

        self.info_label.setText(
            f"Matched {row - start_row} segments to: {song.title}"
        )
        self.project_changed.emit()

    def _apply_v2_matching(self) -> int:
        """Apply v2 word-level matching to detected song regions.

        Finds regions where v1 matched a song, collects all Whisper words
        from that region, and re-matches using v2 to get one segment per
        lyrics line with accurate timing.
        """
        if self._lyrics_library.song_count == 0:
            return 0

        segments = self.project.segments
        if not segments:
            return 0

        # Find song regions: consecutive segments that v1 matched to the same song,
        # or long unmatched segments surrounded by matched ones
        regions = self._find_song_regions()
        if not regions:
            return 0

        total_new = 0

        # Process regions in reverse order so index shifts don't affect earlier regions
        for song, start_idx, end_idx in reversed(regions):
            # Collect ALL whisper words from this region
            all_words = []
            for i in range(start_idx, end_idx):
                seg = segments[i]
                if seg.words:
                    all_words.extend(seg.words)

            if len(all_words) < 5:
                continue

            # Sort by time (should already be sorted, but be safe)
            all_words.sort(key=lambda w: w.start)

            # Run v2 matching
            result = match_song_words(all_words, song)
            if result and result.match_ratio >= 0.3:
                # Replace the old segments with v2 segments
                segments[start_idx:end_idx] = result.segments
                total_new += len(result.segments)

        if total_new > 0:
            # Re-number segment IDs
            for i, seg in enumerate(segments):
                seg.id = i + 1
            self._refresh_table()

        return total_new

    def _find_song_regions(self) -> list[tuple]:
        """Find contiguous regions of segments that belong to a song.

        Returns list of (Song, start_index, end_index) tuples.
        """
        segments = self.project.segments
        regions = []
        i = 0

        while i < len(segments):
            seg = segments[i]

            # Find a matched segment to identify the song
            if not seg.note or not seg.note.startswith("Matched:"):
                i += 1
                continue

            # Extract song title
            title = seg.note.replace("Matched: ", "").split(" (")[0]
            song = None
            for s in self._lyrics_library.songs:
                if s.title == title:
                    song = s
                    break

            if not song:
                i += 1
                continue

            # Expand the region to include surrounding segments
            # Go back to include unmatched segments before the first match
            start_idx = i
            while start_idx > 0:
                prev = segments[start_idx - 1]
                # Include if close in time (< 5s gap) and unmatched or same song
                if segments[start_idx].start - prev.end > 5.0:
                    break
                if prev.note and prev.note.startswith("Matched:"):
                    prev_title = prev.note.replace("Matched: ", "").split(" (")[0]
                    if prev_title != title:
                        break
                start_idx -= 1

            # Go forward to include the rest of the song
            end_idx = i + 1
            while end_idx < len(segments):
                next_seg = segments[end_idx]
                # Stop if big gap
                if next_seg.start - segments[end_idx - 1].end > 10.0:
                    break
                # Stop if different song
                if next_seg.note and next_seg.note.startswith("Matched:"):
                    next_title = next_seg.note.replace("Matched: ", "").split(" (")[0]
                    if next_title != title:
                        break
                end_idx += 1

            regions.append((song, start_idx, end_idx))
            i = end_idx

        return regions

    def _split_long_segments(self) -> int:
        """Split long unmatched segments by matching sliding word windows against lyrics.

        When Whisper produces a 25-second, 30-word segment, this tries matching
        the first ~8 words, splits at the match boundary, then repeats for the rest.
        Returns the number of splits performed.
        """
        if self._lyrics_library.song_count == 0:
            return 0

        segments = self.project.segments
        splits = 0
        i = 0

        while i < len(segments):
            seg = segments[i]

            # Only process long segments with word timestamps
            if not seg.words or len(seg.words) < 10:
                i += 1
                continue
            # Skip matched segments unless they're suspiciously long
            # (matched text covers less than half the words)
            if seg.note and seg.note.startswith("Matched:"):
                matched_word_count = len(seg.text.split())
                if matched_word_count >= len(seg.words) * 0.6:
                    i += 1
                    continue
                # Clear the bad match so we can re-split
                seg.note = ""
                seg.text = " ".join(w.word for w in seg.words)

            # Try to find lyrics matches within this segment's words
            new_segments = self._try_split_by_lyrics(seg)
            if new_segments and len(new_segments) > 1:
                # Replace the original segment with the split pieces
                segments[i:i+1] = new_segments
                splits += len(new_segments) - 1
                i += len(new_segments)
            else:
                i += 1

        if splits > 0:
            # Re-number segment IDs
            for idx, seg in enumerate(segments):
                seg.id = idx + 1
            self._refresh_table()

        return splits

    def _try_split_by_lyrics(self, seg: Segment) -> list[Segment] | None:
        """Try to split a segment into pieces that match lyrics lines.

        Slides a window across the segment's words, trying to match each
        window against the lyrics library. When a match is found, creates
        a new segment for those words and continues with the remainder.
        """
        words = seg.words
        if not words:
            return None

        result_segments = []
        word_idx = 0
        seg_id_base = seg.id

        while word_idx < len(words):
            remaining_words = words[word_idx:]
            if len(remaining_words) < 3:
                # Too few words left — add as final segment
                if remaining_words:
                    text = " ".join(w.word for w in remaining_words)
                    new_seg = Segment(
                        id=seg_id_base,
                        type=seg.type,
                        start=remaining_words[0].start,
                        end=remaining_words[-1].end,
                        text=text,
                        words=list(remaining_words),
                        confidence=seg.confidence,
                        speaker_id=seg.speaker_id,
                    )
                    result_segments.append(new_seg)
                break

            # Try matching windows of 4-12 words from the current position
            best_match = None
            best_end_idx = 0

            for win_size in range(min(12, len(remaining_words)), 3, -1):
                window_words = remaining_words[:win_size]
                window_text = " ".join(w.word for w in window_words)

                match = self._lyrics_matcher.match_segment(window_text, threshold=0.50)
                if match:
                    # Check that the match isn't way longer than our window
                    match_word_count = len(match.matched_text.split())
                    if match_word_count <= win_size * 2:
                        best_match = match
                        best_end_idx = win_size
                        break

            if best_match:
                # Create a matched segment
                matched_words = remaining_words[:best_end_idx]
                aligned = align_words(list(matched_words), best_match.matched_text)
                new_seg = Segment(
                    id=seg_id_base,
                    type=seg.type,
                    start=matched_words[0].start,
                    end=matched_words[-1].end,
                    text=best_match.matched_text,
                    words=aligned,
                    confidence=seg.confidence,
                    speaker_id=seg.speaker_id,
                    note=f"Matched: {best_match.song.title} ({best_match.score:.0%})",
                )
                result_segments.append(new_seg)
                word_idx += best_end_idx
            else:
                # No match found — try a smaller chunk (just take ~8 words as-is)
                chunk_size = min(8, len(remaining_words))
                chunk_words = remaining_words[:chunk_size]
                text = " ".join(w.word for w in chunk_words)
                new_seg = Segment(
                    id=seg_id_base,
                    type=seg.type,
                    start=chunk_words[0].start,
                    end=chunk_words[-1].end,
                    text=text,
                    words=list(chunk_words),
                    confidence=seg.confidence,
                    speaker_id=seg.speaker_id,
                )
                result_segments.append(new_seg)
                word_idx += chunk_size

        # Only return if we actually split (more than 1 piece)
        if len(result_segments) > 1:
            return result_segments
        return None

    def _rematch_unmatched_segments(self) -> int:
        """Merge adjacent unmatched segments near song sections and re-try matching."""
        segments = self.project.segments
        if not segments or self._lyrics_library.song_count == 0:
            return 0

        rematched = 0
        i = 0
        while i < len(segments):
            seg = segments[i]

            # Skip already-matched segments
            if seg.note and seg.note.startswith("Matched:"):
                i += 1
                continue

            # Look for a run of consecutive unmatched segments
            run = [i]
            j = i + 1
            while j < len(segments) and j - i < 6:
                next_seg = segments[j]
                if next_seg.note and next_seg.note.startswith("Matched:"):
                    break
                # Only merge if gap is small (< 2 seconds)
                if next_seg.start - segments[j - 1].end > 2.0:
                    break
                run.append(j)
                j += 1

            # Only try re-matching if there are 2+ segments to merge
            # and they're near a matched segment (within 30 seconds)
            if len(run) >= 2:
                near_match = False
                if i > 0 and segments[i - 1].note and segments[i - 1].note.startswith("Matched:"):
                    near_match = True
                if j < len(segments) and segments[j].note and segments[j].note.startswith("Matched:"):
                    near_match = True

                if near_match:
                    # Merge text from the run
                    combined_text = " ".join(segments[k].text for k in run)

                    # Try matching
                    result = self._lyrics_matcher.match_segment(combined_text, threshold=0.50)
                    if result:
                        # Apply match to first segment, remove the rest
                        base = segments[run[0]]
                        base.end = segments[run[-1]].end
                        base.text = result.matched_text

                        # Combine words for alignment
                        all_words = []
                        for k in run:
                            if segments[k].words:
                                all_words.extend(segments[k].words)
                        if all_words:
                            base.words = align_words(all_words, result.matched_text)

                        base.note = f"Matched: {result.song.title} ({result.score:.0%})"

                        # Remove merged segments
                        for k in reversed(run[1:]):
                            segments.pop(k)

                        rematched += 1
                        continue  # don't increment i, check this position again

            i += 1

        if rematched > 0:
            self._refresh_table()

        return rematched

    def _group_lyrics_manual(self):
        """Manual trigger for grouping lyrics segments."""
        merged = self._group_lyrics_segments()
        if merged > 0:
            self.project.mark_dirty()
            self.info_label.setText(f"Grouped {merged} lyrics segments.")
            self.project_changed.emit()
        else:
            self.info_label.setText("No lyrics segments to group.")

    def _group_lyrics_segments(self, max_chars: int = 120, max_lines: int = 3) -> int:
        """Merge consecutive lyrics-matched segments into 2-3 line groups.

        Respects section boundaries — won't merge a verse line with a chorus line.
        Returns the number of merges performed.
        """
        segments = self.project.segments
        if not segments:
            return 0

        def _get_section(seg):
            """Find which section a matched segment belongs to in its song."""
            if not seg.note or not seg.note.startswith("Matched:"):
                return None
            # Extract song title from note
            title = seg.note.replace("Matched: ", "").split(" (")[0]
            for song in self._lyrics_library.songs:
                if song.title == title:
                    # Find matching line by text
                    from lyrics.library import _normalize
                    seg_norm = _normalize(seg.text)
                    for line in song.lines:
                        if line.normalized in seg_norm or seg_norm in line.normalized:
                            return line.section
                    # Try first word match as fallback
                    seg_words = seg_norm.split()[:3]
                    for line in song.lines:
                        line_words = line.normalized.split()[:3]
                        if seg_words == line_words:
                            return line.section
            return None

        merges = 0
        i = 0
        while i < len(segments):
            seg = segments[i]
            if not seg.note or not seg.note.startswith("Matched:"):
                i += 1
                continue

            song_tag = seg.note.split("(")[0].strip()
            base_section = _get_section(seg)

            # Merge consecutive segments from the same song AND same section
            lines_in_chunk = 1
            j = i + 1
            while j < len(segments) and lines_in_chunk < max_lines:
                next_seg = segments[j]
                if not next_seg.note or not next_seg.note.startswith("Matched:"):
                    break
                next_tag = next_seg.note.split("(")[0].strip()
                if next_tag != song_tag:
                    break

                # Check section boundary
                next_section = _get_section(next_seg)
                if next_section != base_section:
                    break

                # Check combined length
                combined_len = len(seg.text) + len(next_seg.text) + 1
                if combined_len > max_chars:
                    break

                # Merge — rebuild word timing from the combined time span
                combined_text = seg.text + " " + next_seg.text

                # Collect all original Whisper word timestamps (no duplicates)
                all_words = []
                seen_times = set()
                for w in (seg.words or []) + (next_seg.words or []):
                    key = (round(w.start, 2), round(w.end, 2))
                    if key not in seen_times:
                        seen_times.add(key)
                        all_words.append(w)
                all_words.sort(key=lambda w: w.start)

                seg.end = next_seg.end
                seg.text = combined_text
                if all_words:
                    seg.words = align_words(all_words, combined_text)
                segments.pop(j)
                merges += 1
                lines_in_chunk += 1

            i += 1

        if merges > 0:
            self._refresh_table()

        return merges

    def _fix_segment_timing(self):
        """Clean up word timing issues after lyrics matching and grouping.

        Fixes:
        - Duplicate lyrics text from overlapping matches
        - Words with timestamps outside their segment boundaries
        - Zero-duration words
        - Overlapping segments
        """
        from lyrics.alignment import _distribute_evenly

        segments = self.project.segments
        for i, seg in enumerate(segments):
            # Fix duplicate text (e.g., "Jesus my Lord Jesus my Lord")
            if seg.note and seg.note.startswith("Matched:"):
                words = seg.text.split()
                n = len(words)
                # Check if the text is the same phrase repeated (e.g., "Jesus my Lord Jesus my Lord")
                for half in range(n // 3, n // 2 + 1):
                    if n >= half * 2 and words[:half] == words[half:2*half]:
                        # First half equals second half — deduplicate
                        seg.text = " ".join(words[:half])
                        break

            if not seg.words:
                continue

            # Rebuild word list from text to ensure consistency
            text_words = seg.text.split()

            # Collect unique word timestamps sorted by time
            unique_times = []
            seen = set()
            for w in seg.words:
                key = round(w.start, 2)
                if key not in seen:
                    seen.add(key)
                    unique_times.append((w.start, w.end))
            unique_times.sort()

            # Check if timing is usable
            bad_timing = False

            # Too few timestamps for the text
            if len(unique_times) < len(text_words) * 0.5:
                bad_timing = True

            # Timestamps outside segment
            if not bad_timing and unique_times:
                if unique_times[0][0] < seg.start - 0.3:
                    bad_timing = True
                if unique_times[-1][1] > seg.end + 0.3:
                    bad_timing = True

            # Non-monotonic or zero-duration
            if not bad_timing:
                for j in range(1, len(unique_times)):
                    if unique_times[j][0] < unique_times[j - 1][0]:
                        bad_timing = True
                        break

            if bad_timing or len(seg.words) != len(text_words):
                # Rebuild evenly — safe fallback
                seg.words = _distribute_evenly(text_words, seg.start, seg.end)
            else:
                # Keep existing timing but ensure words match text
                seg.words = [
                    Word(word=text_words[j], start=seg.words[j].start, end=seg.words[j].end)
                    if j < len(seg.words) else Word(word=text_words[j], start=seg.end, end=seg.end)
                    for j in range(len(text_words))
                ]

            # Ensure segment doesn't overlap with next
            if i + 1 < len(segments):
                next_seg = segments[i + 1]
                if seg.end > next_seg.start:
                    seg.end = next_seg.start

    def _save_as_song(self, rows: list[int]):
        """Save selected segments as a new song in the lyrics library."""
        from PyQt6.QtWidgets import QInputDialog

        segments = []
        for r in rows:
            seg = self._get_segment_for_row(r)
            if seg and seg.text.strip():
                segments.append(seg)

        if not segments:
            return

        title, ok = QInputDialog.getText(self, "Save as Song", "Song title:")
        if not ok or not title.strip():
            return

        # Group into sections — new section when gap > 5 seconds
        sections: list[tuple[str, list[str]]] = []
        current_lines: list[str] = []
        section_num = 1
        prev_end = segments[0].start

        for seg in segments:
            if seg.start - prev_end > 5.0 and current_lines:
                sections.append((f"Verse {section_num}", current_lines))
                current_lines = []
                section_num += 1
            # Split long lines into ~6-10 word phrases
            text = seg.text.strip()
            words = text.split()
            if len(words) <= 10:
                current_lines.append(text)
            else:
                # Split at commas, semicolons, or midpoint
                phrases = []
                current_phrase = []
                for w in words:
                    current_phrase.append(w)
                    # Break after punctuation or when phrase gets long enough
                    if (len(current_phrase) >= 6 and
                            (w.endswith(',') or w.endswith(';') or w.endswith('.')
                             or len(current_phrase) >= 10)):
                        phrases.append(" ".join(current_phrase))
                        current_phrase = []
                if current_phrase:
                    phrases.append(" ".join(current_phrase))
                current_lines.extend(phrases)
            prev_end = seg.end

        if current_lines:
            sections.append((f"Verse {section_num}", current_lines))

        file_path = self._lyrics_library.save_song(title.strip(), sections)
        self.info_label.setText(
            f"Saved '{title.strip()}' to lyrics library "
            f"({len(sections)} sections, {sum(len(s[1]) for s in sections)} lines)"
        )
        QMessageBox.information(
            self, "Save as Song",
            f"Saved: {file_path}\n\n"
            f"{len(sections)} sections, {sum(len(s[1]) for s in sections)} lines.\n"
            f"Library now has {self._lyrics_library.song_count} songs."
        )

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

    def _export_transcript(self):
        """Export transcript as plain text with timestamps."""
        if not self.project.segments:
            QMessageBox.information(self, "Export", "No transcript to export.")
            return

        default_name = ""
        if self.project.audio_file:
            default_name = Path(self.project.audio_file).stem + ".txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Transcript", default_name, "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return

        lines = []
        for seg in self.project.segments:
            if not seg.text.strip():
                continue
            timestamp = self.project.format_time(seg.start)
            lines.append(f"[{timestamp}] {seg.text}")

        try:
            Path(file_path).write_text("\n".join(lines), encoding="utf-8")
            self.info_label.setText(f"Exported {len(lines)} lines to {Path(file_path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export:\n{e}")

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

        # Start lyrics tracking for auto-detection
        self._lyrics_tracker = SongTracker(self._lyrics_matcher)

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

        # Auto-detect lyrics from library
        if self._lyrics_tracker and seg.words and len(seg.words) >= 3:
            match = self._lyrics_tracker.process_segment(seg.text)
            if match:
                seg.words = align_words(seg.words, match.matched_text)
                seg.text = match.matched_text
                seg.note = f"Matched: {match.song.title} ({match.score:.0%})"

        self.project.segments.append(seg)
        self._add_segment_row(seg)
        # Auto-scroll to latest segment
        self.table.scrollToBottom()

    def _on_transcribe_finished(self):
        self.progress.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        self._lyrics_tracker = None

        # Post-processing: use v2 word-level matching on detected song regions
        v2_matched = self._apply_v2_matching()

        # For non-song segments, keep v1 pipeline
        rematched = self._rematch_unmatched_segments()
        self._fix_segment_timing()

        self.project.mark_dirty()
        n = len(self.project.segments)
        msg = f"Transcription complete: {n} segments."
        if v2_matched > 0:
            msg += f" Matched {v2_matched} song segments (v2)."
        if rematched > 0:
            msg += f" Re-matched {rematched} segments."
        if grouped > 0:
            msg += f" Grouped {grouped} lyrics segments."
        msg += "\nDouble-click text to edit. Right-click for options."
        self.info_label.setText(msg)
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
