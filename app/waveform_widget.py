"""Custom waveform display widget with zoom, scroll, and selection."""

import numpy as np
from PyQt6.QtWidgets import QWidget, QScrollBar, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap, QMouseEvent, QWheelEvent

from app.peak_cache import PeakData, PeakCacheBuilder, BLOCK_SIZES

# Colors — Audition-style dark theme
COLOR_BG = QColor(43, 43, 43)
COLOR_WAVEFORM = QColor(0, 204, 68)
COLOR_WAVEFORM_RMS = QColor(0, 153, 51)
COLOR_CENTER_LINE = QColor(80, 80, 80)
COLOR_SELECTION = QColor(50, 100, 200, 80)
COLOR_SELECTION_BORDER = QColor(80, 140, 255, 150)
COLOR_PLAYHEAD = QColor(255, 80, 40)
COLOR_RULER_BG = QColor(35, 35, 35)
COLOR_RULER_TEXT = QColor(180, 180, 180)
COLOR_RULER_TICK = QColor(100, 100, 100)

RULER_HEIGHT = 24


class WaveformDisplay(QWidget):
    """The actual waveform painting surface."""

    selection_changed = pyqtSignal(int, int)  # start_sample, end_sample
    cursor_moved = pyqtSignal(int)  # sample position
    zoom_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.setMouseTracking(True)

        # Audio data reference
        self._audio_data: np.ndarray | None = None
        self._sample_rate: int = 44100
        self._channels: int = 1

        # Peak caches (one per channel)
        self._peak_data: list[PeakData] = []
        self._cache_builder: PeakCacheBuilder | None = None

        # View state
        self._view_start: int = 0  # first visible sample
        self._view_end: int = 0  # last visible sample
        self._num_samples: int = 0

        # Selection
        self._sel_start: int = -1
        self._sel_end: int = -1
        self._selecting: bool = False
        self._select_anchor: int = -1

        # Playhead
        self._playhead: int = -1

        # Rendering cache
        self._pixmap: QPixmap | None = None
        self._dirty: bool = True

    def set_audio(self, data: np.ndarray, sample_rate: int):
        """Set new audio data and rebuild peak cache."""
        self._audio_data = data
        self._sample_rate = sample_rate
        self._channels = data.shape[1] if data.ndim > 1 else 1
        self._num_samples = len(data)
        self._view_start = 0
        self._view_end = self._num_samples
        self._sel_start = -1
        self._sel_end = -1
        self._playhead = -1
        self._peak_data = []

        # Build peak cache in background
        if self._cache_builder is not None:
            self._cache_builder.quit()
            self._cache_builder.wait()

        self._cache_builder = PeakCacheBuilder(data)
        self._cache_builder.finished_building.connect(self._on_peaks_built)
        self._cache_builder.start()

        self._mark_dirty()

    def _on_peaks_built(self, peak_data: list[PeakData]):
        self._peak_data = peak_data
        self._mark_dirty()

    def clear_audio(self):
        self._audio_data = None
        self._peak_data = []
        self._num_samples = 0
        self._view_start = 0
        self._view_end = 0
        self._sel_start = -1
        self._sel_end = -1
        self._playhead = -1
        self._mark_dirty()

    # --- View manipulation ---

    @property
    def view_start(self) -> int:
        return self._view_start

    @property
    def view_end(self) -> int:
        return self._view_end

    @property
    def visible_samples(self) -> int:
        return self._view_end - self._view_start

    def set_view(self, start: int, end: int):
        start = max(0, start)
        end = min(self._num_samples, end)
        if end - start < 100:
            return
        self._view_start = start
        self._view_end = end
        self._mark_dirty()
        self.zoom_changed.emit()

    def zoom_in(self, center: int | None = None):
        """Zoom in 2x centered on the given sample (or view center)."""
        if center is None:
            center = (self._view_start + self._view_end) // 2
        half = self.visible_samples // 4
        self.set_view(center - half, center + half)

    def zoom_out(self, center: int | None = None):
        if center is None:
            center = (self._view_start + self._view_end) // 2
        half = self.visible_samples
        self.set_view(center - half, center + half)

    def zoom_to_fit(self):
        self.set_view(0, self._num_samples)

    def zoom_to_selection(self):
        if self._sel_start >= 0 and self._sel_end > self._sel_start:
            margin = max(100, (self._sel_end - self._sel_start) // 20)
            self.set_view(self._sel_start - margin, self._sel_end + margin)

    def scroll_by(self, samples: int):
        length = self.visible_samples
        new_start = self._view_start + samples
        new_start = max(0, min(new_start, self._num_samples - length))
        self.set_view(new_start, new_start + length)

    # --- Selection ---

    @property
    def selection(self) -> tuple[int, int]:
        return (self._sel_start, self._sel_end)

    @property
    def has_selection(self) -> bool:
        return self._sel_start >= 0 and self._sel_end > self._sel_start

    def set_selection(self, start: int, end: int):
        self._sel_start = max(0, min(start, end))
        self._sel_end = min(self._num_samples, max(start, end))
        self._mark_dirty()
        self.selection_changed.emit(self._sel_start, self._sel_end)

    def clear_selection(self):
        self._sel_start = -1
        self._sel_end = -1
        self._mark_dirty()
        self.selection_changed.emit(-1, -1)

    def select_all(self):
        if self._num_samples > 0:
            self.set_selection(0, self._num_samples)

    # --- Playhead ---

    def set_playhead(self, sample: int):
        old = self._playhead
        self._playhead = sample
        # Only do a lightweight repaint for playhead movement
        if old != sample:
            self.update()

    # --- Coordinate conversion ---

    def _sample_to_x(self, sample: int) -> float:
        if self.visible_samples == 0:
            return 0.0
        return (sample - self._view_start) / self.visible_samples * self.width()

    def _x_to_sample(self, x: float) -> int:
        if self.width() == 0:
            return self._view_start
        sample = self._view_start + (x / self.width()) * self.visible_samples
        return int(max(0, min(sample, self._num_samples)))

    # --- Mouse interaction ---

    # Minimum pixel drag distance before it counts as a selection vs a click
    _DRAG_THRESHOLD = 4

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._audio_data is not None:
            self._mouse_press_x = event.position().x()
            sample = self._x_to_sample(event.position().x())
            self._selecting = False  # don't start selecting until drag exceeds threshold
            self._select_anchor = sample
            self._click_sample = sample

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton and self._audio_data is not None:
            dx = abs(event.position().x() - self._mouse_press_x)
            if not self._selecting and dx >= self._DRAG_THRESHOLD:
                # Start a selection drag
                self._selecting = True

            if self._selecting:
                sample = self._x_to_sample(event.position().x())
                self._sel_start = min(self._select_anchor, sample)
                self._sel_end = max(self._select_anchor, sample)
                self._mark_dirty()
                self.selection_changed.emit(self._sel_start, self._sel_end)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._audio_data is not None:
            if not self._selecting:
                # Single click — place cursor, clear selection
                sample = self._click_sample
                self._playhead = sample
                self.clear_selection()
                self._mark_dirty()
                self.cursor_moved.emit(sample)
            else:
                # Finished drag selection
                self._selecting = False
                if self._sel_end - self._sel_start < 100:
                    # Too small, treat as click
                    self._playhead = self._click_sample
                    self.clear_selection()
                    self.cursor_moved.emit(self._click_sample)

    def wheelEvent(self, event: QWheelEvent):
        if self._audio_data is None:
            return

        delta = event.angleDelta().y()
        mods = event.modifiers()

        if mods & Qt.KeyboardModifier.ControlModifier:
            # Zoom centered on mouse
            center = self._x_to_sample(event.position().x())
            if delta > 0:
                self.zoom_in(center)
            else:
                self.zoom_out(center)
        else:
            # Scroll horizontally
            scroll_amount = self.visible_samples // 10
            if delta > 0:
                self.scroll_by(-scroll_amount)
            else:
                self.scroll_by(scroll_amount)

    # --- Painting ---

    def _mark_dirty(self):
        self._dirty = True
        self.update()

    def resizeEvent(self, event):
        self._mark_dirty()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w = self.width()
        h = self.height()

        if self._dirty:
            self._pixmap = QPixmap(self.size())
            cache_painter = QPainter(self._pixmap)
            cache_painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            self._paint_background(cache_painter, w, h)
            self._paint_ruler(cache_painter, w)
            self._paint_waveform(cache_painter, w, h)
            self._paint_selection(cache_painter, w, h)
            cache_painter.end()
            self._dirty = False

        if self._pixmap:
            painter.drawPixmap(0, 0, self._pixmap)

        # Playhead always drawn live (not cached)
        self._paint_playhead(painter, h)
        painter.end()

    def _paint_background(self, p: QPainter, w: int, h: int):
        p.fillRect(0, 0, w, h, COLOR_BG)

    def _paint_ruler(self, p: QPainter, w: int):
        p.fillRect(0, 0, w, RULER_HEIGHT, COLOR_RULER_BG)

        if self._num_samples == 0 or self._sample_rate == 0:
            return

        duration_visible = self.visible_samples / self._sample_rate

        # Pick tick interval based on zoom level
        tick_intervals = [0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600]
        target_px_per_tick = 80
        secs_per_pixel = duration_visible / max(w, 1)
        tick_interval = tick_intervals[-1]
        for ti in tick_intervals:
            if ti / secs_per_pixel >= target_px_per_tick:
                tick_interval = ti
                break

        start_time = self._view_start / self._sample_rate
        first_tick = int(start_time / tick_interval) * tick_interval

        p.setPen(QPen(COLOR_RULER_TICK, 1))
        font = p.font()
        font.setPixelSize(10)
        p.setFont(font)

        t = first_tick
        end_time = self._view_end / self._sample_rate
        while t <= end_time:
            x = self._sample_to_x(int(t * self._sample_rate))
            if 0 <= x <= w:
                p.setPen(QPen(COLOR_RULER_TICK, 1))
                p.drawLine(int(x), RULER_HEIGHT - 6, int(x), RULER_HEIGHT)

                p.setPen(QPen(COLOR_RULER_TEXT, 1))
                minutes = int(t // 60)
                secs = t % 60
                if t >= 3600:
                    hours = int(t // 3600)
                    minutes = int((t % 3600) // 60)
                    label = f"{hours}:{minutes:02d}:{secs:04.1f}"
                elif t >= 60:
                    label = f"{minutes}:{secs:04.1f}"
                else:
                    label = f"{secs:.2f}s"
                p.drawText(int(x) + 3, RULER_HEIGHT - 8, label)

            t += tick_interval

    def _paint_waveform(self, p: QPainter, w: int, h: int):
        if self._audio_data is None or self._num_samples == 0:
            return

        waveform_top = RULER_HEIGHT
        waveform_height = h - RULER_HEIGHT
        channels = self._channels

        if channels == 0:
            return

        channel_height = waveform_height / channels

        for ch in range(channels):
            y_center = waveform_top + ch * channel_height + channel_height / 2

            # Center line
            p.setPen(QPen(COLOR_CENTER_LINE, 1))
            p.drawLine(0, int(y_center), w, int(y_center))

            # Get peak data
            mins, maxs = self._get_peaks_for_channel(ch, w)
            if len(mins) == 0:
                continue

            half_h = channel_height / 2 * 0.9  # 90% of available height

            p.setPen(QPen(COLOR_WAVEFORM, 1))
            for px in range(min(w, len(mins))):
                y_min = int(y_center - maxs[px] * half_h)
                y_max = int(y_center - mins[px] * half_h)
                if y_min == y_max:
                    y_max = y_min + 1
                p.drawLine(px, y_min, px, y_max)

    def _get_peaks_for_channel(self, channel: int, width: int) -> tuple[np.ndarray, np.ndarray]:
        """Get min/max peaks for a channel at current zoom."""
        if not self._peak_data or channel >= len(self._peak_data):
            # No cache yet — fall back to raw downsampling
            return self._raw_peaks(channel, width)

        peak_data = self._peak_data[channel]
        samples_per_pixel = self.visible_samples / max(width, 1)

        # Check if we need raw data (very zoomed in)
        if samples_per_pixel < BLOCK_SIZES[0]:
            return self._raw_peaks(channel, width)

        return peak_data.get_peaks(self._view_start, self._view_end, width)

    def _raw_peaks(self, channel: int, width: int) -> tuple[np.ndarray, np.ndarray]:
        """Compute peaks directly from raw audio data for very zoomed-in views."""
        if self._audio_data is None or width <= 0:
            return np.zeros(width), np.zeros(width)

        mins = np.zeros(width, dtype=np.float32)
        maxs = np.zeros(width, dtype=np.float32)

        samples_per_pixel = self.visible_samples / width
        for px in range(width):
            s0 = int(self._view_start + px * samples_per_pixel)
            s1 = int(self._view_start + (px + 1) * samples_per_pixel)
            s0 = max(0, s0)
            s1 = min(self._num_samples, max(s1, s0 + 1))

            if self._channels > 1:
                chunk = self._audio_data[s0:s1, channel]
            else:
                chunk = self._audio_data[s0:s1].flatten()

            if len(chunk) > 0:
                mins[px] = chunk.min()
                maxs[px] = chunk.max()

        return mins, maxs

    def _paint_selection(self, p: QPainter, w: int, h: int):
        if not self.has_selection:
            return

        x0 = max(0, int(self._sample_to_x(self._sel_start)))
        x1 = min(w, int(self._sample_to_x(self._sel_end)))

        if x1 <= x0:
            return

        p.fillRect(x0, RULER_HEIGHT, x1 - x0, h - RULER_HEIGHT, COLOR_SELECTION)
        p.setPen(QPen(COLOR_SELECTION_BORDER, 1))
        p.drawLine(x0, RULER_HEIGHT, x0, h)
        p.drawLine(x1, RULER_HEIGHT, x1, h)

    def _paint_playhead(self, p: QPainter, h: int):
        if self._playhead < 0:
            return

        x = self._sample_to_x(self._playhead)
        if 0 <= x <= self.width():
            p.setPen(QPen(COLOR_PLAYHEAD, 2))
            p.drawLine(int(x), RULER_HEIGHT, int(x), h)


class WaveformWidget(QWidget):
    """Waveform display + horizontal scrollbar."""

    selection_changed = pyqtSignal(int, int)
    cursor_moved = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.display = WaveformDisplay(self)
        self.scrollbar = QScrollBar(Qt.Orientation.Horizontal, self)
        self.scrollbar.setMaximum(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.display, 1)
        layout.addWidget(self.scrollbar)

        # Connect signals
        self.display.selection_changed.connect(self.selection_changed)
        self.display.cursor_moved.connect(self.cursor_moved)
        self.display.zoom_changed.connect(self._update_scrollbar)
        self.scrollbar.valueChanged.connect(self._on_scroll)

    def set_audio(self, data: np.ndarray, sample_rate: int):
        self.display.set_audio(data, sample_rate)
        self._update_scrollbar()

    def clear_audio(self):
        self.display.clear_audio()
        self.scrollbar.setMaximum(0)

    def _update_scrollbar(self):
        d = self.display
        if d._num_samples == 0:
            self.scrollbar.setMaximum(0)
            return

        page = d.visible_samples
        self.scrollbar.blockSignals(True)
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(max(0, d._num_samples - page))
        self.scrollbar.setPageStep(page)
        self.scrollbar.setSingleStep(max(1, page // 20))
        self.scrollbar.setValue(d.view_start)
        self.scrollbar.blockSignals(False)

    def _on_scroll(self, value: int):
        d = self.display
        length = d.visible_samples
        d.set_view(value, value + length)
