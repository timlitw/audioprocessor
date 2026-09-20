"""Check that a stream URL is reachable and find out what codec it serves."""

import re
import subprocess
from dataclasses import dataclass

from core.ffmpeg_manager import get_ffmpeg_path

_AUDIO_LINE = re.compile(r"Audio:\s*([A-Za-z0-9_]+)")


@dataclass
class ProbeResult:
    ok: bool
    codec: str          # "mp3", "aac", ... or "" when unknown
    detail: str         # human-readable line for the log


def probe_stream(url: str, timeout: int = 25) -> ProbeResult:
    """Connect to the stream briefly and report what it is.

    Used by the Test button, and by the recorder to decide whether it can
    copy the audio straight through or has to re-encode.
    """
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return ProbeResult(False, "", "ffmpeg not found")

    cmd = [
        ffmpeg, "-hide_banner", "-nostdin",
        "-i", url,
        "-t", "1", "-f", "null", "-",
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=_no_window(),
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(False, "", "Timed out connecting to the stream")
    except OSError as exc:
        return ProbeResult(False, "", f"Could not run ffmpeg: {exc}")

    stderr = proc.stderr or ""

    for line in stderr.splitlines():
        if "Stream #" in line and "Audio:" in line:
            match = _AUDIO_LINE.search(line)
            codec = match.group(1).lower() if match else ""
            return ProbeResult(True, codec, line.strip())

    # No audio stream found — surface whatever ffmpeg complained about.
    tail = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    return ProbeResult(False, "", tail[-1] if tail else "No audio stream found")


def _no_window() -> int:
    """CREATE_NO_WINDOW on Windows so probing doesn't flash a console."""
    try:
        return subprocess.CREATE_NO_WINDOW
    except AttributeError:
        return 0
