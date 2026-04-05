"""Locate ffmpeg binary — prefers bundled imageio-ffmpeg, falls back to system PATH."""

import shutil


def get_ffmpeg_path() -> str | None:
    """Return path to ffmpeg binary, or None if not found."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, FileNotFoundError):
        pass

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    return None
