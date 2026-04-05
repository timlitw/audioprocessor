"""Whisper transcription worker — runs in a background QThread."""

from PyQt6.QtCore import QThread, pyqtSignal


class WhisperWorker(QThread):
    """Transcribe audio using faster-whisper in a background thread."""

    progress = pyqtSignal(int, str)       # (percent, message)
    segment_ready = pyqtSignal(dict)       # emitted per segment as they're transcribed
    finished_transcription = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, audio_path: str, model_size: str = "base", parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.model_size = model_size

    def run(self):
        try:
            self.progress.emit(5, f"Loading {self.model_size} model (first run downloads ~{self._model_size_mb()}MB)...")

            from faster_whisper import WhisperModel

            model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
            )

            self.progress.emit(15, "Model loaded. Transcribing...")

            segments_iter, info = model.transcribe(
                self.audio_path,
                word_timestamps=True,
                language=None,  # auto-detect
            )

            duration = info.duration if hasattr(info, 'duration') else 0
            self.progress.emit(20, f"Language: {info.language} (p={info.language_probability:.0%}). Processing segments...")

            for seg in segments_iter:
                words = []
                if seg.words:
                    for w in seg.words:
                        words.append({
                            "word": w.word.strip(),
                            "start": round(w.start, 3),
                            "end": round(w.end, 3),
                        })

                seg_dict = {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                    "words": words,
                    "confidence": round(seg.avg_log_prob, 3) if hasattr(seg, 'avg_log_prob') else 0.0,
                }
                self.segment_ready.emit(seg_dict)

                # Update progress based on position in audio
                if duration > 0:
                    pct = min(95, int(20 + (seg.end / duration) * 75))
                    self.progress.emit(pct, f"Transcribing... {seg.end:.0f}s / {duration:.0f}s")

            self.progress.emit(100, "Done!")
            self.finished_transcription.emit()

        except ImportError:
            self.error.emit(
                "faster-whisper is not installed.\n\n"
                "Install it with: pip install faster-whisper\n\n"
                "This will download ~30MB. The model itself downloads on first use."
            )
        except Exception as e:
            self.error.emit(str(e))

    def _model_size_mb(self) -> str:
        sizes = {"tiny": "75", "base": "150", "small": "500", "medium": "1500"}
        return sizes.get(self.model_size, "?")
