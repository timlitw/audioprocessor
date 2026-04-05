"""Multi-resolution peak cache for efficient waveform rendering.

Builds a pyramid of min/max values at increasing block sizes so the
waveform widget can render any zoom level without scanning raw samples.
"""

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

# Block sizes for each pyramid level
BLOCK_SIZES = [256, 1024, 4096, 16384, 65536]


class PeakData:
    """Holds the peak pyramid for one channel."""

    def __init__(self):
        self.levels: list[tuple[np.ndarray, np.ndarray]] = []  # (mins, maxs) per level

    def get_peaks(self, start_sample: int, end_sample: int, num_pixels: int) -> tuple[np.ndarray, np.ndarray]:
        """Get min/max peaks for a sample range, optimized for the given pixel width.

        Returns (mins, maxs) arrays of length num_pixels.
        """
        if not self.levels or num_pixels <= 0:
            return np.zeros(num_pixels), np.zeros(num_pixels)

        samples_per_pixel = (end_sample - start_sample) / max(num_pixels, 1)

        # Find the best cache level: largest block_size <= samples_per_pixel
        best_level = -1
        for i, block_size in enumerate(BLOCK_SIZES):
            if i < len(self.levels) and block_size <= samples_per_pixel:
                best_level = i

        mins_out = np.zeros(num_pixels, dtype=np.float32)
        maxs_out = np.zeros(num_pixels, dtype=np.float32)

        if best_level >= 0:
            block_size = BLOCK_SIZES[best_level]
            level_mins, level_maxs = self.levels[best_level]
            self._resample_peaks(level_mins, level_maxs, block_size,
                                 start_sample, end_sample, mins_out, maxs_out)
        else:
            # Zoomed in very far — use raw data handled by caller
            pass

        return mins_out, maxs_out

    def _resample_peaks(self, level_mins, level_maxs, block_size,
                        start_sample, end_sample, mins_out, maxs_out):
        num_pixels = len(mins_out)
        samples_per_pixel = (end_sample - start_sample) / num_pixels

        for px in range(num_pixels):
            s0 = start_sample + px * samples_per_pixel
            s1 = start_sample + (px + 1) * samples_per_pixel

            b0 = max(0, int(s0 / block_size))
            b1 = min(len(level_mins), int(np.ceil(s1 / block_size)))

            if b0 >= b1 or b0 >= len(level_mins):
                mins_out[px] = 0.0
                maxs_out[px] = 0.0
            else:
                mins_out[px] = level_mins[b0:b1].min()
                maxs_out[px] = level_maxs[b0:b1].max()


class PeakCacheBuilder(QThread):
    """Builds peak cache in background thread."""

    progress = pyqtSignal(int)  # 0-100
    finished_building = pyqtSignal(list)  # list of PeakData, one per channel

    def __init__(self, audio_data: np.ndarray, parent=None):
        super().__init__(parent)
        self.audio_data = audio_data

    def run(self):
        data = self.audio_data
        channels = data.shape[1] if data.ndim > 1 else 1
        num_samples = len(data)

        result = []
        total_work = channels * len(BLOCK_SIZES)
        done = 0

        for ch in range(channels):
            peak_data = PeakData()
            if channels > 1:
                channel = data[:, ch]
            else:
                channel = data.flatten()

            for level_idx, block_size in enumerate(BLOCK_SIZES):
                num_blocks = num_samples // block_size
                if num_blocks == 0:
                    peak_data.levels.append((np.array([channel.min()]), np.array([channel.max()])))
                else:
                    trimmed = channel[:num_blocks * block_size]
                    blocks = trimmed.reshape(num_blocks, block_size)
                    mins = blocks.min(axis=1).astype(np.float32)
                    maxs = blocks.max(axis=1).astype(np.float32)
                    peak_data.levels.append((mins, maxs))

                done += 1
                self.progress.emit(int(done / total_work * 100))

            result.append(peak_data)

        self.finished_building.emit(result)
