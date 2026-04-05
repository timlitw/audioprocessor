"""Central audio data holder — the single source of truth for the current audio."""

import numpy as np
from pathlib import Path
from audio.file_io import load_audio


class AudioEngine:
    """Holds the current audio data and metadata."""

    def __init__(self):
        self.data: np.ndarray | None = None  # float32, shape (samples, channels)
        self.sample_rate: int = 44100
        self.file_path: str | None = None
        self._modified: bool = False

    @property
    def num_samples(self) -> int:
        return len(self.data) if self.data is not None else 0

    @property
    def channels(self) -> int:
        if self.data is None:
            return 0
        return self.data.shape[1] if self.data.ndim > 1 else 1

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.num_samples / self.sample_rate if self.data is not None else 0.0

    @property
    def is_loaded(self) -> bool:
        return self.data is not None

    @property
    def is_modified(self) -> bool:
        return self._modified

    @is_modified.setter
    def is_modified(self, value: bool):
        self._modified = value

    @property
    def file_name(self) -> str:
        if self.file_path:
            return Path(self.file_path).name
        return ""

    def load(self, file_path: str) -> None:
        """Load an audio file. Raises on failure."""
        data, sr = load_audio(file_path)
        self.data = data
        self.sample_rate = sr
        self.file_path = file_path
        self._modified = False

    def clear(self) -> None:
        """Unload current audio."""
        self.data = None
        self.sample_rate = 44100
        self.file_path = None
        self._modified = False

    def format_time(self, sample_index: int) -> str:
        """Convert a sample index to HH:MM:SS.ms string."""
        if self.sample_rate == 0:
            return "00:00:00.000"
        seconds = sample_index / self.sample_rate
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:05.2f}"
        return f"{minutes:02d}:{secs:05.2f}"

    def format_duration(self) -> str:
        """Format total duration."""
        return self.format_time(self.num_samples)

    def get_mono(self) -> np.ndarray:
        """Return mono mix of the audio data."""
        if self.data is None:
            return np.array([], dtype=np.float32)
        if self.channels == 1:
            return self.data.flatten()
        return self.data.mean(axis=1)
