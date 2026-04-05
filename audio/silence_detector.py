"""Silence and noise detection — finds where the actual performance starts."""

import numpy as np
from dataclasses import dataclass


@dataclass
class DetectionResult:
    """Result of performance start detection."""
    performance_start: int          # sample index
    noise_floor_db: float           # estimated noise floor in dB
    threshold_db: float             # detection threshold in dB
    confidence: str                 # "high", "medium", "low"


def find_performance_start(
    audio_data: np.ndarray,
    sample_rate: int,
    sensitivity: float = 0.5,
) -> DetectionResult:
    """Find where the actual performance starts in a recording.

    Algorithm:
    1. Compute RMS energy in 0.5s sliding windows
    2. Estimate noise floor from first 60 seconds (median RMS)
    3. Set threshold based on sensitivity (3-12 dB above noise floor)
    4. Scan for first sustained activity above threshold
    5. Backtrack to catch gradual onsets

    Args:
        audio_data: float32 array, shape (samples,) or (samples, channels)
        sample_rate: samples per second
        sensitivity: 0.0 (needs loud start) to 1.0 (very sensitive)

    Returns:
        DetectionResult with the detected start position
    """
    # Mix to mono
    if audio_data.ndim > 1 and audio_data.shape[1] > 1:
        mono = audio_data.mean(axis=1)
    else:
        mono = audio_data.flatten()

    # Window parameters
    window_samples = int(0.5 * sample_rate)  # 0.5 second windows
    hop_samples = int(0.1 * sample_rate)     # 0.1 second hops
    num_windows = (len(mono) - window_samples) // hop_samples

    if num_windows < 20:
        return DetectionResult(
            performance_start=0,
            noise_floor_db=-60.0,
            threshold_db=-40.0,
            confidence="low",
        )

    # Compute RMS for each window
    rms = np.zeros(num_windows, dtype=np.float64)
    for i in range(num_windows):
        start = i * hop_samples
        window = mono[start : start + window_samples]
        rms[i] = np.sqrt(np.mean(window.astype(np.float64) ** 2))

    # Step 1: Estimate noise floor from first 60 seconds
    noise_windows = min(int(60.0 / 0.1), num_windows // 4)  # up to 600 windows or 25% of file
    noise_windows = max(noise_windows, 10)
    noise_floor = np.median(rms[:noise_windows])

    # Convert to dB
    noise_floor_db = 20.0 * np.log10(max(noise_floor, 1e-10))

    # Step 2: Set detection threshold based on sensitivity
    db_above_noise = 12.0 - (sensitivity * 9.0)  # 3dB to 12dB above noise
    threshold = noise_floor * (10.0 ** (db_above_noise / 20.0))
    threshold_db = 20.0 * np.log10(max(threshold, 1e-10))

    # Step 3: Find first sustained activity above threshold
    # "Sustained" = at least 70% of windows in a 10-second span are above threshold
    sustain_windows = max(5, int(10.0 / 0.1))  # 10 seconds worth of windows
    required_above = int(sustain_windows * 0.7)

    perf_start_window = 0
    confidence = "low"

    for i in range(num_windows - sustain_windows):
        span = rms[i : i + sustain_windows]
        above_count = np.sum(span > threshold)
        if above_count >= required_above:
            perf_start_window = i
            # Confidence based on how far above the threshold
            mean_above = np.mean(span[span > threshold])
            ratio = mean_above / max(noise_floor, 1e-10)
            if ratio > 10:
                confidence = "high"
            elif ratio > 4:
                confidence = "medium"
            else:
                confidence = "low"
            break

    # Step 4: Backtrack to find the softer onset before the sustained section
    # Walk backwards looking for where RMS first exceeds 1.5x noise floor
    soft_threshold = noise_floor * 1.5
    onset_window = perf_start_window
    for i in range(perf_start_window - 1, -1, -1):
        if rms[i] < soft_threshold:
            onset_window = i + 1
            break
    else:
        onset_window = 0

    # Step 5: Add safety margin (5 seconds back from detected onset)
    safety_windows = int(5.0 / 0.1)
    final_window = max(0, onset_window - safety_windows)

    # Convert window index to sample index
    perf_start_sample = final_window * hop_samples

    return DetectionResult(
        performance_start=perf_start_sample,
        noise_floor_db=float(noise_floor_db),
        threshold_db=float(threshold_db),
        confidence=confidence,
    )


def detect_silence_regions(
    audio_data: np.ndarray,
    sample_rate: int,
    min_silence_seconds: float = 2.0,
    threshold_db: float = -40.0,
) -> list[tuple[int, int]]:
    """Find all silence regions in the audio.

    Returns list of (start_sample, end_sample) tuples.
    """
    if audio_data.ndim > 1 and audio_data.shape[1] > 1:
        mono = audio_data.mean(axis=1)
    else:
        mono = audio_data.flatten()

    block_size = 4096
    threshold_linear = 10.0 ** (threshold_db / 20.0)
    min_blocks = max(1, int(min_silence_seconds * sample_rate / block_size))

    num_blocks = len(mono) // block_size
    if num_blocks == 0:
        return []

    trimmed = mono[:num_blocks * block_size]
    blocks = trimmed.reshape(num_blocks, block_size)
    rms = np.sqrt(np.mean(blocks.astype(np.float64) ** 2, axis=1))

    is_silent = rms < threshold_linear

    regions = []
    in_silence = False
    start_block = 0

    for i, silent in enumerate(is_silent):
        if silent and not in_silence:
            start_block = i
            in_silence = True
        elif not silent and in_silence:
            if i - start_block >= min_blocks:
                regions.append((start_block * block_size, i * block_size))
            in_silence = False

    if in_silence and num_blocks - start_block >= min_blocks:
        regions.append((start_block * block_size, num_blocks * block_size))

    return regions
