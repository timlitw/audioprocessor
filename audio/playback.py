"""Audio playback via sounddevice with position tracking."""

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class PlaybackEngine(QObject):
    """Manages audio playback with position callbacks."""

    position_changed = pyqtSignal(int)  # current sample position
    playback_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stream: sd.OutputStream | None = None
        self._data: np.ndarray | None = None
        self._sample_rate: int = 44100
        self._pos: int = 0
        self._start: int = 0
        self._end: int = 0
        self._is_playing: bool = False
        self._is_paused: bool = False

        self._timer = QTimer(self)
        self._timer.setInterval(30)  # ~33 fps
        self._timer.timeout.connect(self._emit_position)

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def position(self) -> int:
        return self._pos

    def set_audio(self, data: np.ndarray, sample_rate: int):
        self.stop()
        self._data = data
        self._sample_rate = sample_rate

    def play(self, start: int = 0, end: int | None = None):
        """Play from start to end sample. If paused, resume instead."""
        if self._data is None:
            return

        if self._is_paused:
            self._resume()
            return

        self.stop()

        self._start = max(0, start)
        self._end = min(len(self._data), end) if end is not None else len(self._data)
        self._pos = self._start

        channels = self._data.shape[1] if self._data.ndim > 1 else 1

        def callback(outdata, frames, time_info, status):
            remaining = self._end - self._pos
            if remaining <= 0:
                outdata[:] = 0
                raise sd.CallbackStop()

            chunk_len = min(frames, remaining)
            chunk = self._data[self._pos : self._pos + chunk_len]

            out_ch = outdata.shape[1]
            in_ch = chunk.shape[1] if chunk.ndim > 1 else 1

            if in_ch == 1 and out_ch > 1:
                mono = chunk.flatten()[:chunk_len]
                for c in range(out_ch):
                    outdata[:chunk_len, c] = mono
            elif in_ch >= out_ch:
                outdata[:chunk_len] = chunk[:chunk_len, :out_ch]
            else:
                outdata[:chunk_len, :in_ch] = chunk[:chunk_len]
                outdata[:chunk_len, in_ch:] = 0

            if chunk_len < frames:
                outdata[chunk_len:] = 0

            self._pos += chunk_len

        def finished():
            self._is_playing = False
            self._is_paused = False
            self._timer.stop()
            self.playback_finished.emit()

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=max(channels, 2),
                dtype="float32",
                callback=callback,
                finished_callback=finished,
                blocksize=2048,
            )
            self._stream.start()
            self._is_playing = True
            self._is_paused = False
            self._timer.start()
        except Exception as e:
            self._is_playing = False
            raise RuntimeError(f"Playback failed: {e}")

    def pause(self):
        """Pause playback (can be resumed)."""
        if self._stream and self._is_playing and not self._is_paused:
            self._stream.stop()
            self._is_playing = False
            self._is_paused = True
            self._timer.stop()

    def _resume(self):
        """Resume from paused state."""
        if self._stream and self._is_paused:
            self._stream.start()
            self._is_playing = True
            self._is_paused = False
            self._timer.start()

    def stop(self):
        """Stop and reset."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._is_playing = False
        self._is_paused = False
        self._timer.stop()

    def _emit_position(self):
        self.position_changed.emit(self._pos)
