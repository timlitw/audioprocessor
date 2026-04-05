"""Pre-compute per-frame state for efficient rendering."""

from core.project import TranscriptProject


def compute_frame_times(duration_seconds: float, fps: int = 30) -> list[float]:
    """Generate the timestamp for each frame."""
    total_frames = int(duration_seconds * fps)
    return [i / fps for i in range(total_frames)]
