"""Audio file loading and saving.

Uses soundfile for WAV/FLAC/OGG/AIFF (fast, native).
Uses ffmpeg subprocess for MP3/M4A/WMA/AAC (via imageio-ffmpeg bundled binary).
"""

import io
import json
import struct
import subprocess
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
from core.ffmpeg_manager import get_ffmpeg_path

SOUNDFILE_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif"}
FFMPEG_EXTENSIONS = {".mp3", ".wma", ".m4a", ".aac", ".opus", ".webm"}
ALL_EXTENSIONS = SOUNDFILE_EXTENSIONS | FFMPEG_EXTENSIONS

FILE_FILTER = (
    "Audio Files (*.wav *.mp3 *.flac *.ogg *.aiff *.aif *.m4a *.aac *.wma *.opus *.webm);;"
    "WAV (*.wav);;MP3 (*.mp3);;FLAC (*.flac);;OGG (*.ogg);;AIFF (*.aiff *.aif);;"
    "M4A (*.m4a);;AAC (*.aac);;WMA (*.wma);;All Files (*)"
)


def load_audio(file_path: str) -> tuple[np.ndarray, int]:
    """Load an audio file into a float32 numpy array.

    Returns:
        (data, sample_rate) where data has shape (samples, channels), dtype float32.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in SOUNDFILE_EXTENSIONS:
        return _load_soundfile(file_path)
    elif ext in FFMPEG_EXTENSIONS:
        return _load_ffmpeg(file_path)
    else:
        try:
            return _load_soundfile(file_path)
        except Exception:
            return _load_ffmpeg(file_path)


def _load_soundfile(file_path: str) -> tuple[np.ndarray, int]:
    data, sr = sf.read(file_path, dtype="float32", always_2d=True)
    return data, sr


def _get_audio_info(ffmpeg_path: str, file_path: str) -> tuple[int, int]:
    """Use ffmpeg to probe audio file for sample rate and channel count."""
    cmd = [
        ffmpeg_path, "-i", file_path,
        "-hide_banner", "-f", "null", "-"
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )
    # ffmpeg prints info to stderr
    info = result.stderr

    # Parse sample rate and channels from ffmpeg output
    sample_rate = 44100
    channels = 2

    for line in info.split("\n"):
        if "Audio:" in line:
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                if "Hz" in part:
                    try:
                        sample_rate = int(part.replace("Hz", "").strip())
                    except ValueError:
                        pass
                if "stereo" in part.lower():
                    channels = 2
                elif "mono" in part.lower():
                    channels = 1
                elif "5.1" in part:
                    channels = 6
            break

    return sample_rate, channels


def _load_ffmpeg(file_path: str) -> tuple[np.ndarray, int]:
    """Load audio using ffmpeg subprocess — decode to raw PCM float32."""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError(
            "ffmpeg not found. Install imageio-ffmpeg (pip install imageio-ffmpeg) "
            "or add ffmpeg to your system PATH."
        )

    # Probe file for sample rate and channels
    sample_rate, channels = _get_audio_info(ffmpeg_path, file_path)

    # Decode to raw float32 PCM via pipe
    cmd = [
        ffmpeg_path,
        "-i", file_path,
        "-f", "f32le",        # raw float32 little-endian
        "-acodec", "pcm_f32le",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-v", "quiet",
        "pipe:1",             # output to stdout
    ]

    result = subprocess.run(
        cmd, capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to decode: {result.stderr.decode(errors='replace')}")

    raw = result.stdout
    samples = np.frombuffer(raw, dtype=np.float32)

    if channels > 1:
        samples = samples.reshape(-1, channels)
    else:
        samples = samples.reshape(-1, 1)

    return samples, sample_rate


def save_mp3(data: np.ndarray, sample_rate: int, file_path: str, bitrate: str = "192k") -> None:
    """Export audio data as MP3 using ffmpeg."""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("ffmpeg not found. Cannot export MP3.")

    channels = data.shape[1] if data.ndim > 1 else 1

    cmd = [
        ffmpeg_path,
        "-f", "f32le",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-i", "pipe:0",
        "-b:a", bitrate,
        "-y",  # overwrite
        "-v", "quiet",
        file_path,
    ]

    proc = subprocess.run(
        cmd, input=data.astype(np.float32).tobytes(),
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg MP3 export failed: {proc.stderr.decode(errors='replace')}")


def save_wav(data: np.ndarray, sample_rate: int, file_path: str) -> None:
    """Export audio data as WAV."""
    sf.write(file_path, data, sample_rate)
