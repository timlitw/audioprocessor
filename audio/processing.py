"""Audio editing operations — trim, delete, keep, normalize, fade."""

import numpy as np


def delete_region(data: np.ndarray, start: int, end: int) -> tuple[np.ndarray, np.ndarray]:
    """Delete samples from start to end.

    Returns:
        (new_data, deleted_data) — deleted_data is saved for undo.
    """
    start = max(0, start)
    end = min(len(data), end)
    deleted = data[start:end].copy()
    new_data = np.concatenate([data[:start], data[end:]], axis=0)
    return new_data, deleted


def keep_region(data: np.ndarray, start: int, end: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Keep only the selected region, delete everything else.

    Returns:
        (new_data, deleted_before, deleted_after) for undo.
    """
    start = max(0, start)
    end = min(len(data), end)
    deleted_before = data[:start].copy()
    deleted_after = data[end:].copy()
    new_data = data[start:end].copy()
    return new_data, deleted_before, deleted_after


def normalize_peak(data: np.ndarray, target_db: float = -1.0) -> np.ndarray:
    """Normalize audio so the peak reaches target_db."""
    peak = np.max(np.abs(data))
    if peak == 0:
        return data.copy()
    target = 10.0 ** (target_db / 20.0)
    gain = target / peak
    return data * gain


def normalize_rms(data: np.ndarray, target_db: float = -18.0) -> np.ndarray:
    """Normalize audio so the RMS reaches target_db."""
    rms = np.sqrt(np.mean(data ** 2))
    if rms == 0:
        return data.copy()
    target = 10.0 ** (target_db / 20.0)
    gain = target / rms
    result = data * gain
    # Clip to prevent overflow
    return np.clip(result, -1.0, 1.0)


def fade_in(data: np.ndarray, num_samples: int) -> np.ndarray:
    """Apply a fade-in to the first num_samples."""
    result = data.copy()
    num_samples = min(num_samples, len(data))
    if num_samples <= 0:
        return result

    fade = np.linspace(0.0, 1.0, num_samples, dtype=np.float32)
    if result.ndim > 1:
        for ch in range(result.shape[1]):
            result[:num_samples, ch] *= fade
    else:
        result[:num_samples] *= fade
    return result


def fade_out(data: np.ndarray, num_samples: int) -> np.ndarray:
    """Apply a fade-out to the last num_samples."""
    result = data.copy()
    num_samples = min(num_samples, len(data))
    if num_samples <= 0:
        return result

    fade = np.linspace(1.0, 0.0, num_samples, dtype=np.float32)
    if result.ndim > 1:
        for ch in range(result.shape[1]):
            result[-num_samples:, ch] *= fade
    else:
        result[-num_samples:] *= fade
    return result
