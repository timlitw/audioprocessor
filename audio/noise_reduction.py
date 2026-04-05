"""Noise reduction via spectral subtraction + optional hum removal."""

import numpy as np
from scipy.signal import stft, istft, iirnotch, sosfilt


def capture_noise_profile(
    audio_data: np.ndarray,
    sample_rate: int,
    start_sample: int,
    end_sample: int,
    n_fft: int = 2048,
) -> np.ndarray:
    """Capture a noise profile from a selected "noise only" region.

    Returns the mean magnitude spectrum (shape: n_fft//2 + 1).
    """
    if audio_data.ndim > 1 and audio_data.shape[1] > 1:
        mono = audio_data[start_sample:end_sample].mean(axis=1)
    else:
        mono = audio_data[start_sample:end_sample].flatten()

    f, t, Zxx = stft(mono, fs=sample_rate, nperseg=n_fft, noverlap=n_fft * 3 // 4)
    mag = np.abs(Zxx)
    noise_profile = mag.mean(axis=1)

    return noise_profile


def apply_noise_reduction(
    audio_data: np.ndarray,
    sample_rate: int,
    noise_profile: np.ndarray,
    strength: float = 2.0,
    floor: float = 0.02,
    n_fft: int = 2048,
) -> np.ndarray:
    """Apply spectral subtraction noise reduction.

    Args:
        audio_data: input audio (samples, channels)
        sample_rate: sample rate
        noise_profile: from capture_noise_profile()
        strength: how aggressively to subtract (alpha). Range ~0.5 to 5.0.
        floor: spectral floor to prevent "musical noise" artifacts (beta). Range ~0.01 to 0.1.
        n_fft: FFT size

    Returns:
        Cleaned audio, same shape as input.
    """
    result = np.zeros_like(audio_data)
    channels = audio_data.shape[1] if audio_data.ndim > 1 else 1

    for ch in range(channels):
        if channels > 1:
            channel = audio_data[:, ch].astype(np.float64)
        else:
            channel = audio_data.flatten().astype(np.float64)

        f, t, Zxx = stft(channel, fs=sample_rate, nperseg=n_fft, noverlap=n_fft * 3 // 4)

        mag = np.abs(Zxx)
        phase = np.angle(Zxx)

        # Spectral subtraction
        noise = noise_profile[:, np.newaxis] * strength
        clean_mag = np.maximum(mag - noise, floor * mag)

        # Reconstruct
        clean_Zxx = clean_mag * np.exp(1j * phase)
        _, cleaned = istft(clean_Zxx, fs=sample_rate, nperseg=n_fft, noverlap=n_fft * 3 // 4)

        # Match original length
        if len(cleaned) > len(channel):
            cleaned = cleaned[:len(channel)]
        elif len(cleaned) < len(channel):
            cleaned = np.pad(cleaned, (0, len(channel) - len(cleaned)))

        if channels > 1:
            result[:, ch] = cleaned.astype(np.float32)
        else:
            result[:, 0] = cleaned.astype(np.float32)

    return result


def remove_hum(
    audio_data: np.ndarray,
    sample_rate: int,
    fundamental: float = 60.0,
    num_harmonics: int = 5,
    q_factor: float = 30.0,
) -> np.ndarray:
    """Remove hum (50/60 Hz and harmonics) using notch filters.

    Args:
        audio_data: input audio
        sample_rate: sample rate
        fundamental: hum frequency (50 Hz in EU, 60 Hz in US)
        num_harmonics: number of harmonics to remove (including fundamental)
        q_factor: quality factor of notch filters (higher = narrower notch)
    """
    result = audio_data.copy()
    channels = result.shape[1] if result.ndim > 1 else 1

    for harmonic in range(1, num_harmonics + 1):
        freq = fundamental * harmonic
        if freq >= sample_rate / 2:
            break
        b, a = iirnotch(freq, q_factor, sample_rate)
        # Convert to SOS for numerical stability
        from scipy.signal import tf2sos
        sos = tf2sos(b, a)
        for ch in range(channels):
            if channels > 1:
                result[:, ch] = sosfilt(sos, result[:, ch]).astype(np.float32)
            else:
                result[:, 0] = sosfilt(sos, result[:, 0]).astype(np.float32)

    return result
