"""Main application window — menus, toolbar, layout, and coordination."""

from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QApplication, QVBoxLayout, QWidget,
    QToolBar, QMenu,
)
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

from audio.engine import AudioEngine
from audio.playback import PlaybackEngine
from audio.file_io import FILE_FILTER
from audio.processing import delete_region, keep_region
from app.waveform_widget import WaveformWidget
from app.transport_bar import TransportBar
from app.status_bar import AudioStatusBar
from core.undo_manager import UndoManager
from core.ffmpeg_manager import get_ffmpeg_path
from core.settings import (
    get_recent_files, add_recent_file, get_last_directory, set_last_directory,
    get_last_bitrate, set_last_bitrate,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Processor")
        self.resize(1200, 600)
        self.setAcceptDrops(True)

        self._has_ffmpeg = get_ffmpeg_path() is not None

        # Core engines
        self.engine = AudioEngine()
        self.playback = PlaybackEngine(self)
        self.undo_mgr = UndoManager()

        # Build UI
        self._build_toolbar()
        self._build_ui()
        self._build_menus()
        self._build_shortcuts()
        self._apply_dark_theme()

        # Wire playback signals
        self.playback.position_changed.connect(self._on_playback_position)
        self.playback.playback_finished.connect(self._on_playback_finished)

        # Context menu on waveform
        self.waveform.display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.waveform.display.customContextMenuRequested.connect(self._show_context_menu)

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(tb.iconSize())
        self.addToolBar(tb)

        btn_style = """
            QToolButton {
                background: #3a3a3a; color: #d0d0d0; border: 1px solid #555;
                border-radius: 3px; padding: 3px 10px; margin: 1px; font-size: 12px;
            }
            QToolButton:hover { background: #4a4a4a; }
            QToolButton:pressed { background: #2a2a2a; }
            QToolButton:disabled { color: #666; background: #333; }
        """
        tb.setStyleSheet(btn_style)

        self._act_open = tb.addAction("Open")
        self._act_open.setToolTip("Open audio file (Ctrl+O)")
        self._act_open.triggered.connect(self._open_file)

        self._act_save_mp3 = tb.addAction("Save MP3")
        self._act_save_mp3.setToolTip("Export as MP3 (Ctrl+S)")
        self._act_save_mp3.triggered.connect(self._save_mp3)

        tb.addSeparator()

        self._act_undo = tb.addAction("Undo")
        self._act_undo.setToolTip("Undo (Ctrl+Z)")
        self._act_undo.triggered.connect(self._undo)

        self._act_redo = tb.addAction("Redo")
        self._act_redo.setToolTip("Redo (Ctrl+Shift+Z)")
        self._act_redo.triggered.connect(self._redo)

        tb.addSeparator()

        self._act_delete = tb.addAction("Delete")
        self._act_delete.setToolTip("Delete selection (Del)")
        self._act_delete.triggered.connect(self._delete_selection)

        self._act_keep = tb.addAction("Keep")
        self._act_keep.setToolTip("Keep only selection")
        self._act_keep.triggered.connect(self._keep_selection)

        tb.addSeparator()

        self._act_find_start = tb.addAction("Find Start")
        self._act_find_start.setToolTip("Find where the performance starts")
        self._act_find_start.triggered.connect(self._find_performance_start)

        tb.addSeparator()

        self._act_normalize = tb.addAction("Normalize")
        self._act_normalize.setToolTip("Normalize volume")
        self._act_normalize.triggered.connect(self._normalize)

        self._act_fade_in = tb.addAction("Fade In")
        self._act_fade_in.setToolTip("Apply fade in")
        self._act_fade_in.triggered.connect(self._fade_in)

        self._act_fade_out = tb.addAction("Fade Out")
        self._act_fade_out.setToolTip("Apply fade out")
        self._act_fade_out.triggered.connect(self._fade_out)

        self._act_noise = tb.addAction("Noise Reduce")
        self._act_noise.setToolTip("Noise reduction")
        self._act_noise.triggered.connect(self._noise_reduction)

        tb.addSeparator()

        self._act_zoom_in = tb.addAction("Zoom +")
        self._act_zoom_in.setToolTip("Zoom in (Ctrl+=)")

        self._act_zoom_out = tb.addAction("Zoom -")
        self._act_zoom_out.setToolTip("Zoom out (Ctrl+-)")

        self._act_zoom_fit = tb.addAction("Fit")
        self._act_zoom_fit.setToolTip("Zoom to fit (Ctrl+0)")

        self.toolbar = tb

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Waveform widget
        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform, 1)

        # Transport bar
        self.transport = TransportBar()
        layout.addWidget(self.transport)

        # Status bar
        self.audio_status = AudioStatusBar()
        self.setStatusBar(self.audio_status)

        # Wire waveform signals
        self.waveform.selection_changed.connect(self._on_selection_changed)
        self.waveform.cursor_moved.connect(self._on_cursor_moved)

        # Wire transport signals
        self.transport.play_clicked.connect(self._play)
        self.transport.pause_clicked.connect(self._pause)
        self.transport.stop_clicked.connect(self._stop)
        self.transport.skip_start_clicked.connect(self._skip_to_start)
        self.transport.zoom_in_clicked.connect(lambda: self.waveform.display.zoom_in())
        self.transport.zoom_out_clicked.connect(lambda: self.waveform.display.zoom_out())
        self.transport.zoom_fit_clicked.connect(lambda: self.waveform.display.zoom_to_fit())

        # Wire toolbar zoom (connected after waveform exists)
        self._act_zoom_in.triggered.connect(lambda: self.waveform.display.zoom_in())
        self._act_zoom_out.triggered.connect(lambda: self.waveform.display.zoom_out())
        self._act_zoom_fit.triggered.connect(lambda: self.waveform.display.zoom_to_fit())

    def _build_menus(self):
        menubar = self.menuBar()

        # --- File menu ---
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        # Recent files submenu
        self._recent_menu = file_menu.addMenu("Recent &Files")
        self._update_recent_menu()

        file_menu.addSeparator()

        save_mp3_action = QAction("&Save as MP3...", self)
        save_mp3_action.setShortcut(QKeySequence("Ctrl+S"))
        save_mp3_action.triggered.connect(self._save_mp3)
        file_menu.addAction(save_mp3_action)

        save_wav_action = QAction("Save as &WAV...", self)
        save_wav_action.triggered.connect(self._save_wav)
        file_menu.addAction(save_wav_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- Edit menu ---
        edit_menu = menubar.addMenu("&Edit")

        undo_action = QAction("&Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("&Redo", self)
        redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        redo_action.triggered.connect(self._redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        delete_action = QAction("&Delete Selection", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self._delete_selection)
        edit_menu.addAction(delete_action)

        keep_action = QAction("&Keep Selection", self)
        keep_action.triggered.connect(self._keep_selection)
        edit_menu.addAction(keep_action)

        edit_menu.addSeparator()

        select_all_action = QAction("Select &All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(lambda: self.waveform.display.select_all())
        edit_menu.addAction(select_all_action)

        # --- View menu ---
        view_menu = menubar.addMenu("&View")

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        zoom_in_action.triggered.connect(lambda: self.waveform.display.zoom_in())
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(lambda: self.waveform.display.zoom_out())
        view_menu.addAction(zoom_out_action)

        zoom_fit_action = QAction("Zoom to &Fit", self)
        zoom_fit_action.setShortcut(QKeySequence("Ctrl+0"))
        zoom_fit_action.triggered.connect(lambda: self.waveform.display.zoom_to_fit())
        view_menu.addAction(zoom_fit_action)

        zoom_sel_action = QAction("Zoom to &Selection", self)
        zoom_sel_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        zoom_sel_action.triggered.connect(lambda: self.waveform.display.zoom_to_selection())
        view_menu.addAction(zoom_sel_action)

        # --- Effects menu ---
        effects_menu = menubar.addMenu("E&ffects")

        normalize_action = QAction("&Normalize...", self)
        normalize_action.triggered.connect(self._normalize)
        effects_menu.addAction(normalize_action)

        fade_in_action = QAction("Fade &In...", self)
        fade_in_action.triggered.connect(self._fade_in)
        effects_menu.addAction(fade_in_action)

        fade_out_action = QAction("Fade &Out...", self)
        fade_out_action.triggered.connect(self._fade_out)
        effects_menu.addAction(fade_out_action)

        effects_menu.addSeparator()

        noise_action = QAction("Noise &Reduction...", self)
        noise_action.triggered.connect(self._noise_reduction)
        effects_menu.addAction(noise_action)

        effects_menu.addSeparator()

        find_start_action = QAction("Find Performance &Start", self)
        find_start_action.triggered.connect(self._find_performance_start)
        effects_menu.addAction(find_start_action)

        # --- Help menu ---
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_shortcuts(self):
        # Space — play/pause toggle
        space = QShortcut(Qt.Key.Key_Space, self)
        space.activated.connect(self._toggle_play_pause)

        # Home — skip to start
        home = QShortcut(Qt.Key.Key_Home, self)
        home.activated.connect(self._skip_to_start)

        # End — skip to end
        end = QShortcut(Qt.Key.Key_End, self)
        end.activated.connect(self._skip_to_end)

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #2b2b2b; color: #d0d0d0; }
            QMenuBar { background-color: #2b2b2b; color: #d0d0d0; }
            QMenuBar::item:selected { background-color: #3d3d3d; }
            QMenu { background-color: #2b2b2b; color: #d0d0d0; border: 1px solid #555; }
            QMenu::item:selected { background-color: #3d3d3d; }
            QMenu::item:disabled { color: #666; }
            QScrollBar:horizontal {
                background: #1e1e1e; height: 14px; margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #555; min-width: 30px; border-radius: 3px;
            }
            QScrollBar::handle:horizontal:hover { background: #666; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0; background: none;
            }
            QToolBar { background: #2b2b2b; border-bottom: 1px solid #444; spacing: 2px; padding: 2px; }
        """)

    # --- Context menu ---

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #d0d0d0; border: 1px solid #555; }
            QMenu::item:selected { background-color: #3d3d3d; }
            QMenu::item:disabled { color: #666; }
        """)

        has_sel = self.waveform.display.has_selection

        act_delete = menu.addAction("Delete Selection")
        act_delete.setEnabled(has_sel)
        act_delete.triggered.connect(self._delete_selection)

        act_keep = menu.addAction("Keep Selection")
        act_keep.setEnabled(has_sel)
        act_keep.triggered.connect(self._keep_selection)

        menu.addSeparator()

        act_sel_all = menu.addAction("Select All")
        act_sel_all.triggered.connect(lambda: self.waveform.display.select_all())

        menu.addSeparator()

        act_zoom_sel = menu.addAction("Zoom to Selection")
        act_zoom_sel.setEnabled(has_sel)
        act_zoom_sel.triggered.connect(lambda: self.waveform.display.zoom_to_selection())

        act_zoom_fit = menu.addAction("Zoom to Fit")
        act_zoom_fit.triggered.connect(lambda: self.waveform.display.zoom_to_fit())

        menu.exec(self.waveform.display.mapToGlobal(pos))

    # --- Editing with undo ---

    def _delete_selection(self):
        if not self.engine.is_loaded or not self.waveform.display.has_selection:
            return
        self._stop()

        sel_start, sel_end = self.waveform.display.selection

        # Push undo before modifying
        deleted = self.engine.data[sel_start:sel_end].copy()
        self.undo_mgr.push_delete("Delete Selection", sel_start, deleted, self.engine.sample_rate)

        new_data, _ = delete_region(self.engine.data, sel_start, sel_end)
        self.engine.data = new_data
        self.engine.is_modified = True

        self.waveform.display.clear_selection()
        self._refresh_after_edit()

    def _keep_selection(self):
        if not self.engine.is_loaded or not self.waveform.display.has_selection:
            return
        self._stop()

        sel_start, sel_end = self.waveform.display.selection

        # Push full snapshot for undo (keep is complex — two deletions)
        self.undo_mgr.push_full("Keep Selection", self.engine.data, self.engine.sample_rate)

        new_data, _, _ = keep_region(self.engine.data, sel_start, sel_end)
        self.engine.data = new_data
        self.engine.is_modified = True

        self.waveform.display.clear_selection()
        self._refresh_after_edit()

    def _undo(self):
        if not self.undo_mgr.can_undo or self.engine.data is None:
            return
        self._stop()

        result = self.undo_mgr.undo(self.engine.data)
        if result is not None:
            self.engine.data = result
            self.engine.is_modified = True
            self.waveform.display.clear_selection()
            self._refresh_after_edit()

    def _redo(self):
        if not self.undo_mgr.can_redo or self.engine.data is None:
            return
        self._stop()

        result = self.undo_mgr.redo(self.engine.data)
        if result is not None:
            self.engine.data = result
            self.engine.is_modified = True
            self.waveform.display.clear_selection()
            self._refresh_after_edit()

    def _refresh_after_edit(self):
        """Refresh the waveform and status after an edit operation."""
        self.waveform.set_audio(self.engine.data, self.engine.sample_rate)
        self.playback.set_audio(self.engine.data, self.engine.sample_rate)
        self.audio_status.set_format_info(
            self.engine.sample_rate,
            self.engine.channels,
            self.engine.format_duration(),
            self.engine.file_name,
        )
        self._update_time_display(0)
        modified = " *" if self.engine.is_modified else ""
        self.setWindowTitle(f"Audio Processor \u2014 {self.engine.file_name}{modified}")

    # --- Audio Effects ---

    _noise_profile = None  # stored noise profile for spectral subtraction

    def _normalize(self):
        if not self.engine.is_loaded:
            return
        self._stop()

        from app.dialogs.normalize_dialog import NormalizeDialog
        dlg = NormalizeDialog(self)
        if not dlg.exec():
            return

        from audio.processing import normalize_peak, normalize_rms

        self.undo_mgr.push_full("Normalize", self.engine.data, self.engine.sample_rate)

        if dlg.mode == "peak":
            self.engine.data = normalize_peak(self.engine.data, dlg.target_db)
        else:
            self.engine.data = normalize_rms(self.engine.data, dlg.target_db)

        self.engine.is_modified = True
        self._refresh_after_edit()

    def _fade_in(self):
        if not self.engine.is_loaded:
            return
        self._stop()

        from app.dialogs.fade_dialog import FadeDialog
        dlg = FadeDialog("in", self)
        if not dlg.exec():
            return

        from audio.processing import fade_in
        num_samples = int(dlg.duration_seconds * self.engine.sample_rate)

        # Save region for undo
        self.undo_mgr.push_region(
            "Fade In", 0, self.engine.data[:num_samples].copy(), self.engine.sample_rate
        )

        self.engine.data = fade_in(self.engine.data, num_samples)
        self.engine.is_modified = True
        self._refresh_after_edit()

    def _fade_out(self):
        if not self.engine.is_loaded:
            return
        self._stop()

        from app.dialogs.fade_dialog import FadeDialog
        dlg = FadeDialog("out", self)
        if not dlg.exec():
            return

        from audio.processing import fade_out
        num_samples = int(dlg.duration_seconds * self.engine.sample_rate)

        # Save region for undo
        start = max(0, len(self.engine.data) - num_samples)
        self.undo_mgr.push_region(
            "Fade Out", start, self.engine.data[start:].copy(), self.engine.sample_rate
        )

        self.engine.data = fade_out(self.engine.data, num_samples)
        self.engine.is_modified = True
        self._refresh_after_edit()

    def _noise_reduction(self):
        if not self.engine.is_loaded:
            return
        self._stop()

        from app.dialogs.noise_profile import NoiseReductionDialog
        has_sel = self.waveform.display.has_selection
        has_profile = self._noise_profile is not None

        dlg = NoiseReductionDialog(has_profile=has_profile, has_selection=has_sel, parent=self)
        if not dlg.exec():
            return

        from audio.noise_reduction import capture_noise_profile, apply_noise_reduction, remove_hum

        if dlg.capture_profile:
            if not has_sel:
                QMessageBox.warning(self, "Noise Reduction",
                                    "Select a noise-only region first (e.g., the pre-show silence).")
                return
            sel_start, sel_end = self.waveform.display.selection
            self._noise_profile = capture_noise_profile(
                self.engine.data, self.engine.sample_rate, sel_start, sel_end
            )
            QMessageBox.information(self, "Noise Reduction", "Noise profile captured. Open this dialog again to apply.")
            return

        if dlg.apply_reduction:
            if self._noise_profile is None:
                QMessageBox.warning(self, "Noise Reduction", "Capture a noise profile first.")
                return

            self.undo_mgr.push_full("Noise Reduction", self.engine.data, self.engine.sample_rate)

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.engine.data = apply_noise_reduction(
                    self.engine.data, self.engine.sample_rate,
                    self._noise_profile, dlg.strength, dlg.floor
                )

                if dlg.remove_hum:
                    self.engine.data = remove_hum(
                        self.engine.data, self.engine.sample_rate,
                        fundamental=dlg.hum_freq
                    )

                self.engine.is_modified = True
                self._refresh_after_edit()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Noise reduction failed:\n{e}")
            finally:
                QApplication.restoreOverrideCursor()

    # --- Find Performance Start ---

    def _find_performance_start(self):
        if not self.engine.is_loaded:
            return
        self._stop()

        from audio.silence_detector import find_performance_start

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        result = find_performance_start(
            self.engine.data, self.engine.sample_rate, sensitivity=0.5
        )
        QApplication.restoreOverrideCursor()

        time_str = self.engine.format_time(result.performance_start)
        pre_duration = result.performance_start / self.engine.sample_rate

        msg = (
            f"Performance appears to start at {time_str}\n"
            f"({pre_duration:.0f} seconds of pre-show audio)\n\n"
            f"Noise floor: {result.noise_floor_db:.1f} dB\n"
            f"Detection confidence: {result.confidence}\n\n"
            "Would you like to select the pre-show section for deletion?"
        )

        reply = QMessageBox.question(
            self, "Find Performance Start", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Select everything before the performance start
            self.waveform.display.set_selection(0, result.performance_start)
            # Scroll to show the transition point
            margin = int(10 * self.engine.sample_rate)  # 10 seconds
            self.waveform.display.set_view(
                max(0, result.performance_start - margin),
                result.performance_start + margin
            )
            self.waveform._update_scrollbar()
        elif reply == QMessageBox.StandardButton.No:
            # Just scroll to the detected position
            margin = int(10 * self.engine.sample_rate)
            self.waveform.display.set_view(
                max(0, result.performance_start - margin),
                result.performance_start + margin
            )
            self.waveform._update_scrollbar()

    # --- Playback ---

    def _play(self):
        if not self.engine.is_loaded:
            return
        self.playback.set_audio(self.engine.data, self.engine.sample_rate)
        sel = self.waveform.display.selection
        if self.waveform.display.has_selection:
            self.playback.play(sel[0], sel[1])
        else:
            pos = self.waveform.display._playhead
            if pos < 0:
                pos = 0
            self.playback.play(pos)

    def _pause(self):
        self.playback.pause()

    def _stop(self):
        self.playback.stop()
        self.waveform.display.set_playhead(-1)
        self._update_time_display(0)

    def _toggle_play_pause(self):
        if self.playback.is_playing:
            self._pause()
        elif self.playback.is_paused:
            self._play()
        else:
            self._play()

    def _skip_to_start(self):
        self._stop()
        self.waveform.display.set_view(0, self.waveform.display.visible_samples)

    def _skip_to_end(self):
        if not self.engine.is_loaded:
            return
        end = self.engine.num_samples
        length = self.waveform.display.visible_samples
        self.waveform.display.set_view(max(0, end - length), end)

    def _on_playback_position(self, sample: int):
        self.waveform.display.set_playhead(sample)
        self._update_time_display(sample)

        # Auto-scroll: if playhead is near the right edge, scroll forward
        display = self.waveform.display
        if sample > display.view_end - display.visible_samples // 10:
            margin = display.visible_samples // 5
            display.set_view(
                sample - margin,
                sample - margin + display.visible_samples
            )
            self.waveform._update_scrollbar()

    def _on_playback_finished(self):
        pass

    def _update_time_display(self, sample: int):
        current = self.engine.format_time(sample)
        total = self.engine.format_duration()
        self.transport.set_time(current, total)

    # --- File operations ---

    def _update_recent_menu(self):
        self._recent_menu.clear()
        recent = get_recent_files()
        if not recent:
            action = self._recent_menu.addAction("(no recent files)")
            action.setEnabled(False)
            return
        for path in recent:
            action = self._recent_menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self._load_file(p))

    def _open_file(self):
        last_dir = get_last_directory()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Audio File", last_dir, FILE_FILTER
        )
        if not file_path:
            return
        self._load_file(file_path)

    def _load_file(self, file_path: str):
        self._stop()
        self.undo_mgr.clear()
        self._noise_profile = None
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.engine.load(file_path)
            self.playback.set_audio(self.engine.data, self.engine.sample_rate)
            self.waveform.set_audio(self.engine.data, self.engine.sample_rate)
            self.audio_status.set_format_info(
                self.engine.sample_rate,
                self.engine.channels,
                self.engine.format_duration(),
                self.engine.file_name,
            )
            self._update_time_display(0)
            self.setWindowTitle(f"Audio Processor \u2014 {self.engine.file_name}")

            # Update settings
            add_recent_file(file_path)
            set_last_directory(str(Path(file_path).parent))
            self._update_recent_menu()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _save_mp3(self):
        if not self.engine.is_loaded:
            return
        if not self._has_ffmpeg:
            QMessageBox.warning(self, "Error", "ffmpeg not found. Cannot export MP3.")
            return

        from app.dialogs.export_dialog import ExportDialog
        dlg = ExportDialog(self)
        if dlg.exec():
            last_dir = get_last_directory()
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save as MP3", last_dir, "MP3 Files (*.mp3)"
            )
            if file_path:
                try:
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    from audio.file_io import save_mp3
                    save_mp3(self.engine.data, self.engine.sample_rate, file_path, dlg.bitrate)
                    self.engine.is_modified = False
                    self.audio_status.showMessage(f"Saved: {file_path}", 5000)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
                finally:
                    QApplication.restoreOverrideCursor()

    def _save_wav(self):
        if not self.engine.is_loaded:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save as WAV", "", "WAV Files (*.wav)"
        )
        if file_path:
            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                from audio.file_io import save_wav
                save_wav(self.engine.data, self.engine.sample_rate, file_path)
                self.engine.is_modified = False
                self.audio_status.showMessage(f"Saved: {file_path}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
            finally:
                QApplication.restoreOverrideCursor()

    # --- Selection callbacks ---

    def _on_selection_changed(self, start: int, end: int):
        if start < 0:
            self.transport.set_selection_text("")
            self.audio_status.set_selection_info("")
            return
        t_start = self.engine.format_time(start)
        t_end = self.engine.format_time(end)
        duration = (end - start) / self.engine.sample_rate
        text = f"Sel: {t_start} \u2014 {t_end} ({duration:.1f}s)"
        self.transport.set_selection_text(text)
        self.audio_status.set_selection_info(text)

    def _on_cursor_moved(self, sample: int):
        t = self.engine.format_time(sample)
        self.audio_status.set_cursor_info(f"  {t}  ")

    # --- About ---

    def _show_about(self):
        QMessageBox.about(
            self,
            "About Audio Processor",
            "<h3>Audio Processor</h3>"
            "<p>A simple audio editor for cleaning performance recordings.</p>"
            "<hr>"
            "<p><b>Open-source libraries used:</b></p>"
            "<ul>"
            "<li>PyQt6 \u2014 GUI framework (GPL v3)</li>"
            "<li>NumPy \u2014 Numerical computing (BSD)</li>"
            "<li>SciPy \u2014 Signal processing (BSD)</li>"
            "<li>soundfile / libsndfile \u2014 Audio I/O (BSD / LGPL)</li>"
            "<li>sounddevice / PortAudio \u2014 Audio playback (MIT / MIT)</li>"
            "<li>imageio-ffmpeg / FFmpeg \u2014 Media encoding (BSD / LGPL)</li>"
            "</ul>"
        )

    # --- Drag and drop ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self._load_file(urls[0].toLocalFile())

    def closeEvent(self, event):
        self._stop()
        self.undo_mgr.clear()
        super().closeEvent(event)
