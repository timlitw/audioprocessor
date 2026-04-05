"""Video render worker — pipes frames to ffmpeg in a background thread."""

import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

from core.project import TranscriptProject
from core.ffmpeg_manager import get_ffmpeg_path
from video.frame_renderer import FrameRenderer
from video.render_plan import compute_frame_times


# Resolution presets
RESOLUTIONS = {
    "1280x720 (720p)": (1280, 720),
    "1920x1080 (1080p)": (1920, 1080),
    "3840x2160 (4K)": (3840, 2160),
}


class RenderWorker(QThread):
    """Render video frames and pipe to ffmpeg."""

    progress = pyqtSignal(int, str)  # (percent, message)
    finished_render = pyqtSignal(str)  # output file path
    error = pyqtSignal(str)

    def __init__(self, project: TranscriptProject, output_path: str,
                 background_name: str, text_style_name: str,
                 resolution_key: str, fps: int = 30, parent=None):
        super().__init__(parent)
        self.project = project
        self.output_path = output_path
        self.background_name = background_name
        self.text_style_name = text_style_name
        self.resolution_key = resolution_key
        self.fps = fps
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            ffmpeg_path = get_ffmpeg_path()
            if ffmpeg_path is None:
                self.error.emit("ffmpeg not found. Cannot render video.")
                return

            width, height = RESOLUTIONS.get(self.resolution_key, (1920, 1080))
            audio_path = self.project.get_audio_path()

            self.progress.emit(2, "Initializing renderer...")

            renderer = FrameRenderer(
                self.project, width, height,
                self.background_name, self.text_style_name,
            )

            frame_times = compute_frame_times(self.project.audio_duration, self.fps)
            total_frames = len(frame_times)

            if total_frames == 0:
                self.error.emit("No frames to render (audio duration is 0).")
                return

            self.progress.emit(5, f"Rendering {total_frames} frames at {width}x{height}...")

            # Start ffmpeg process
            cmd = [
                ffmpeg_path,
                "-y",
                "-f", "rawvideo",
                "-pix_fmt", "rgb24",
                "-s", f"{width}x{height}",
                "-r", str(self.fps),
                "-i", "pipe:0",
                "-i", audio_path,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-v", "quiet",
                self.output_path,
            ]

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )

            # Render frames and pipe to ffmpeg
            for i, t in enumerate(frame_times):
                if self._cancelled:
                    proc.stdin.close()
                    proc.kill()
                    self.error.emit("Rendering cancelled.")
                    return

                image = renderer.render_frame(t)
                # Convert QImage to raw RGB bytes
                image = image.convertToFormat(image.Format.Format_RGB888)
                ptr = image.bits()
                ptr.setsize(image.sizeInBytes())
                raw_bytes = bytes(ptr)
                proc.stdin.write(raw_bytes)

                # Progress update every 30 frames (~1 second)
                if i % 30 == 0:
                    pct = int(5 + (i / total_frames) * 90)
                    elapsed_min = t / 60
                    total_min = self.project.audio_duration / 60
                    self.progress.emit(pct, f"Rendering... {elapsed_min:.1f} / {total_min:.1f} min")

            proc.stdin.close()
            proc.wait()

            if proc.returncode != 0:
                stderr = proc.stderr.read().decode(errors="replace")
                self.error.emit(f"ffmpeg error:\n{stderr}")
                return

            self.progress.emit(100, "Done!")
            self.finished_render.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))
