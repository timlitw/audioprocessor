"""Records a live stream to MP3, watching for when audio starts and stops.

Runs one ffmpeg process with two outputs: the MP3 file, and a null output
carrying the silencedetect filter. Silence events arrive on stderr and drive
the start/stop logic.
"""

import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass

from PyQt6.QtCore import QThread, pyqtSignal

from core.ffmpeg_manager import get_ffmpeg_path
from core.probe import probe_stream

_SILENCE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")
_PROGRESS = re.compile(r"time=\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")

# Audio must hold for this long before we call it the real start, so a door
# slam or a cough during the pre-service dead air doesn't count.
_SUSTAIN_SECONDS = 20.0

# Silence shorter than this is just a pause between speakers.
_MIN_SILENCE_SECONDS = 2.0

# How long to wait between attempts when the stream isn't up yet.
_RETRY_INTERVAL = 20.0
_RETRY_PROBE_TIMEOUT = 15


@dataclass
class RecordingJob:
    url: str
    output_path: str
    max_seconds: int
    silence_limit_seconds: int      # 0 disables the silence rule
    silence_threshold_db: float
    retry_seconds: int = 0          # keep trying this long if the stream is down


class Recorder(QThread):
    """Runs a RecordingJob. All signals are emitted from the worker thread."""

    log = pyqtSignal(str)
    status = pyqtSignal(str)
    audio_detected = pyqtSignal(float)          # stream seconds
    progress = pyqtSignal(float)                # stream seconds recorded
    done = pyqtSignal(str, str)                 # reason, output path

    def __init__(self, job: RecordingJob, parent=None):
        super().__init__(parent)
        self.job = job

        self._proc: subprocess.Popen | None = None
        self._stop_requested = False
        self._stop_reason = ""
        self._wake = threading.Event()      # interrupts the retry wait

        # Detection state, all measured in stream time.
        self._stream_time = 0.0
        self._audio_started = False
        self._seen_any_silence = False
        self._pending_start: float | None = None
        self._silence_began: float | None = None

    # ------------------------------------------------------------------ run

    def run(self) -> None:
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            self.done.emit("error: ffmpeg not found", "")
            return

        self.status.emit("Connecting...")
        probe = self._connect_with_retry()
        if probe is None:
            return

        self.log.emit(f"Stream: {probe.detail}")

        # The source is already MP3 in the normal case, so copy it through
        # untouched. Anything else has to be encoded.
        if probe.codec == "mp3":
            codec_args = ["-c:a", "copy"]
            self.log.emit("Recording without re-encoding (no quality loss)")
        else:
            codec_args = ["-c:a", "libmp3lame", "-b:a", "192k"]
            self.log.emit(f"Source is {probe.codec or 'unknown'} - encoding to MP3 192k")

        silence_filter = (
            f"silencedetect=noise={self.job.silence_threshold_db}dB:d={_MIN_SILENCE_SECONDS}"
        )

        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "info", "-stats_period", "1",
            # Church streams drop. Reconnect and keep writing the same file.
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_delay_max", "30",
            "-t", str(self.job.max_seconds),
            "-i", self.job.url,
            "-map", "0:a:0", *codec_args, "-y", self.job.output_path,
            "-map", "0:a:0", "-af", silence_filter, "-f", "null", "-",
        ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=_no_window(),
            )
        except OSError as exc:
            self.done.emit(f"error: could not start ffmpeg ({exc})", "")
            return

        self.status.emit("Recording - waiting for audio to start")

        lines: queue.Queue = queue.Queue()
        reader = threading.Thread(
            target=_pump_stderr, args=(self._proc, lines), daemon=True
        )
        reader.start()

        while True:
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                line = None

            if line is None and self._proc.poll() is not None and lines.empty():
                break

            if line is not None:
                self._handle_line(line)

            self._check_limits()

        reader.join(timeout=2)

        if self._stop_reason:
            reason = self._stop_reason
        else:
            reason = "max duration reached"
        self.done.emit(reason, self.job.output_path)

    def _connect_with_retry(self):
        """Wait for the stream to come up, within the job's retry window.

        A sound tech running a few minutes late shouldn't cost the whole
        recording, which is what an immediate failure would do.
        """
        deadline = time.monotonic() + self.job.retry_seconds
        attempt = 0

        while True:
            if self._stop_requested:
                self.done.emit("cancelled", "")
                return None

            timeout = _RETRY_PROBE_TIMEOUT if self.job.retry_seconds else 25
            probe = probe_stream(self.job.url, timeout=timeout)
            if probe.ok:
                if attempt:
                    self.log.emit(f"Stream came up after {attempt} retries.")
                return probe

            attempt += 1
            if time.monotonic() >= deadline:
                if attempt > 1:
                    self.log.emit(f"Gave up after {attempt} attempts.")
                self.done.emit(f"error: {probe.detail}", "")
                return None

            if attempt == 1:
                self.log.emit(f"Stream not up yet - {probe.detail}")
                self.log.emit("Retrying until the window closes.")

            left = int(deadline - time.monotonic())
            self.status.emit(f"Waiting for stream - {format_span(max(left, 0))} left")
            self._wake.wait(_RETRY_INTERVAL)

    # ------------------------------------------------------------- stopping

    def request_stop(self, reason: str = "stopped by user") -> None:
        """Ask ffmpeg to finalize the file and exit."""
        self._stop_requested = True
        self._stop_reason = reason
        self._wake.set()                # break out of a retry wait

        proc = self._proc
        if proc is None or proc.poll() is not None:
            return

        # Sending q is ffmpeg's clean shutdown - it flushes and closes the file.
        try:
            proc.stdin.write(b"q")
            proc.stdin.flush()
        except (OSError, ValueError, AttributeError):
            proc.terminate()

    # ------------------------------------------------------------- parsing

    def _handle_line(self, line: str) -> None:
        progress = _PROGRESS.search(line)
        if progress:
            hours, minutes, seconds = progress.groups()
            self._stream_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            self.progress.emit(self._stream_time)

        start = _SILENCE_START.search(line)
        if start:
            self._on_silence_start(max(0.0, float(start.group(1))))

        end = _SILENCE_END.search(line)
        if end:
            self._on_silence_end(max(0.0, float(end.group(1))))

    def _on_silence_start(self, timestamp: float) -> None:
        self._seen_any_silence = True

        if self._audio_started:
            self._silence_began = timestamp
            return

        # Audio came up but fell away again before it held - not the real start.
        self._pending_start = None

    def _on_silence_end(self, timestamp: float) -> None:
        if self._audio_started:
            self._silence_began = None
        else:
            self._pending_start = timestamp

    def _check_limits(self) -> None:
        if not self._audio_started:
            # Stream was already carrying audio when we connected.
            if not self._seen_any_silence and self._stream_time > 5.0:
                self._confirm_audio_start(0.0)
            elif (
                self._pending_start is not None
                and self._stream_time - self._pending_start >= _SUSTAIN_SECONDS
            ):
                self._confirm_audio_start(self._pending_start)
            return

        if self.job.silence_limit_seconds <= 0 or self._silence_began is None:
            return

        silent_for = self._stream_time - self._silence_began
        if silent_for >= self.job.silence_limit_seconds:
            span = format_span(self.job.silence_limit_seconds)
            self.log.emit(f"Silent for {span} - stopping.")
            self.request_stop(f"stopped after {span} of silence")

    def _confirm_audio_start(self, timestamp: float) -> None:
        self._audio_started = True
        self._pending_start = None
        self._silence_began = None
        self.audio_detected.emit(timestamp)
        self.log.emit(f"Audio started at {clock(timestamp)} into the recording.")
        self.status.emit("Recording - audio detected")


def _pump_stderr(proc: subprocess.Popen, out: queue.Queue) -> None:
    """ffmpeg mixes CR progress updates with LF messages, so split on both."""
    buffer = ""
    while True:
        chunk = proc.stderr.read(512)
        if not chunk:
            break
        buffer += chunk.decode("utf-8", errors="replace")
        buffer = buffer.replace("\r", "\n")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if line.strip():
                out.put(line)
    if buffer.strip():
        out.put(buffer)


def clock(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def format_span(seconds: int) -> str:
    """'5 minutes', '1 minute', '90 seconds' - whichever reads better."""
    if seconds >= 60 and seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{seconds} seconds"


def _no_window() -> int:
    try:
        return subprocess.CREATE_NO_WINDOW
    except AttributeError:
        return 0
