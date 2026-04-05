"""Transcript project — load/save transcript.json, data model."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Word:
    word: str
    start: float
    end: float


@dataclass
class Segment:
    id: int
    type: str  # "speech", "singing", "silence"
    start: float
    end: float
    text: str = ""
    speaker_id: str = ""
    words: list[Word] = field(default_factory=list)
    confidence: float = 0.0
    note: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Speaker:
    id: str
    label: str
    color: str = "#4a9eff"


class TranscriptProject:
    """Holds all data for a transcription project."""

    def __init__(self):
        self.version: str = "1.0"
        self.created: str = ""
        self.modified: str = ""
        self.audio_file: str = ""
        self.audio_duration: float = 0.0
        self.audio_sample_rate: int = 44100
        self.language: str = "en"
        self.speakers: list[Speaker] = []
        self.segments: list[Segment] = []
        self.project_dir: str = ""
        self._dirty: bool = False

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        self._dirty = True
        self.modified = datetime.now(timezone.utc).isoformat()

    def new_project(self, audio_path: str, duration: float, sample_rate: int):
        """Create a new project from an audio file."""
        self.created = datetime.now(timezone.utc).isoformat()
        self.modified = self.created
        self.audio_file = Path(audio_path).name
        self.audio_duration = duration
        self.audio_sample_rate = sample_rate
        self.speakers = []
        self.segments = []
        self.project_dir = str(Path(audio_path).parent)
        self._dirty = True

    def get_audio_path(self) -> str:
        """Full path to the audio file."""
        return str(Path(self.project_dir) / self.audio_file)

    def get_transcript_path(self) -> str:
        """Full path to transcript.json."""
        return str(Path(self.project_dir) / "transcript.json")

    def save(self, path: str | None = None):
        """Save project to transcript.json."""
        if path is None:
            path = self.get_transcript_path()

        data = {
            "version": self.version,
            "created": self.created,
            "modified": self.modified,
            "audio_file": self.audio_file,
            "audio_duration_seconds": self.audio_duration,
            "audio_sample_rate": self.audio_sample_rate,
            "language": self.language,
            "speakers": [asdict(s) for s in self.speakers],
            "segments": [self._segment_to_dict(s) for s in self.segments],
        }

        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
        self._dirty = False

    def load(self, path: str):
        """Load project from transcript.json."""
        data = json.loads(Path(path).read_text())

        self.version = data.get("version", "1.0")
        self.created = data.get("created", "")
        self.modified = data.get("modified", "")
        self.audio_file = data.get("audio_file", "")
        self.audio_duration = data.get("audio_duration_seconds", 0.0)
        self.audio_sample_rate = data.get("audio_sample_rate", 44100)
        self.language = data.get("language", "en")
        self.project_dir = str(Path(path).parent)

        self.speakers = [
            Speaker(id=s["id"], label=s["label"], color=s.get("color", "#4a9eff"))
            for s in data.get("speakers", [])
        ]

        self.segments = []
        for seg_data in data.get("segments", []):
            words = [
                Word(word=w["word"], start=w["start"], end=w["end"])
                for w in seg_data.get("words", [])
            ]
            seg = Segment(
                id=seg_data["id"],
                type=seg_data.get("type", "speech"),
                start=seg_data["start"],
                end=seg_data["end"],
                text=seg_data.get("text", ""),
                speaker_id=seg_data.get("speaker_id", ""),
                words=words,
                confidence=seg_data.get("confidence", 0.0),
                note=seg_data.get("note", ""),
            )
            self.segments.append(seg)

        self._dirty = False

    def _segment_to_dict(self, seg: Segment) -> dict:
        d = {
            "id": seg.id,
            "type": seg.type,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
        }
        if seg.speaker_id:
            d["speaker_id"] = seg.speaker_id
        if seg.words:
            d["words"] = [{"word": w.word, "start": w.start, "end": w.end} for w in seg.words]
        if seg.confidence > 0:
            d["confidence"] = seg.confidence
        if seg.note:
            d["note"] = seg.note
        return d

    def get_speaker_label(self, speaker_id: str) -> str:
        """Get display name for a speaker ID."""
        for s in self.speakers:
            if s.id == speaker_id:
                return s.label
        return speaker_id

    def get_segment_at_time(self, time_seconds: float) -> Segment | None:
        """Find the segment active at a given time."""
        for seg in self.segments:
            if seg.start <= time_seconds < seg.end:
                return seg
        return None

    def format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS.ss or H:MM:SS.ss."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:05.2f}"
        return f"{minutes:02d}:{secs:05.2f}"
