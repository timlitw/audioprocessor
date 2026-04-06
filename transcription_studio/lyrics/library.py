"""Lyrics library — scan, parse, index, and save song lyrics files."""

import re
import string
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SongLine:
    """A single line of lyrics within a song."""
    text: str          # original text
    normalized: str    # lowercase, no punctuation, collapsed whitespace
    section: str       # e.g. "Verse 1", "Chorus"
    line_index: int    # position within the song (0-based across all sections)


@dataclass
class Song:
    """A parsed song from the lyrics library."""
    title: str
    file_path: str
    lines: list[SongLine] = field(default_factory=list)
    ngrams: set[str] = field(default_factory=set)


_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return " ".join(text.lower().translate(_PUNCT_TABLE).split())


def _word_trigrams(text: str) -> set[str]:
    """Generate word-level trigrams from normalized text."""
    words = text.split()
    if len(words) < 3:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i+3]) for i in range(len(words) - 2)}


def parse_lyrics_file(file_path: Path) -> Song | None:
    """Parse a .md or .txt lyrics file into a Song object."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    lines_raw = text.split("\n")
    title = file_path.stem  # fallback to filename
    section = ""
    song_lines: list[SongLine] = []
    all_normalized: list[str] = []
    line_index = 0

    for raw in lines_raw:
        stripped = raw.strip()
        if not stripped:
            continue

        # Title: first # heading
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            continue

        # Section heading
        if stripped.startswith("## "):
            section = stripped[3:].strip()
            continue

        # Regular lyrics line
        normalized = _normalize(stripped)
        if not normalized:
            continue

        sl = SongLine(
            text=stripped,
            normalized=normalized,
            section=section,
            line_index=line_index,
        )
        song_lines.append(sl)
        all_normalized.append(normalized)
        line_index += 1

    if not song_lines:
        return None

    # Build trigrams from all lines combined
    full_text = " ".join(all_normalized)
    ngrams = _word_trigrams(full_text)

    return Song(title=title, file_path=str(file_path), lines=song_lines, ngrams=ngrams)


class LyricsLibrary:
    """In-memory index of all songs in the lyrics directory."""

    def __init__(self, lyrics_dir: str):
        self.lyrics_dir = Path(lyrics_dir)
        self.songs: list[Song] = []
        self._trigram_index: dict[str, list[int]] = {}  # trigram -> song indices

    def scan(self):
        """Scan lyrics directory for .md and .txt files, parse and index them."""
        self.songs.clear()
        self._trigram_index.clear()

        if not self.lyrics_dir.exists():
            return

        for ext in ("*.md", "*.txt"):
            for file_path in self.lyrics_dir.glob(ext):
                song = parse_lyrics_file(file_path)
                if song:
                    song_idx = len(self.songs)
                    self.songs.append(song)

                    # Index trigrams
                    for trigram in song.ngrams:
                        if trigram not in self._trigram_index:
                            self._trigram_index[trigram] = []
                        self._trigram_index[trigram].append(song_idx)

    def get_candidates(self, text: str, max_candidates: int = 10) -> list[Song]:
        """Find songs that share the most trigrams with the given text."""
        normalized = _normalize(text)
        query_trigrams = _word_trigrams(normalized)

        if not query_trigrams:
            return []

        # Count trigram hits per song
        scores: dict[int, int] = {}
        for trigram in query_trigrams:
            for song_idx in self._trigram_index.get(trigram, []):
                scores[song_idx] = scores.get(song_idx, 0) + 1

        # Sort by hit count, return top N
        ranked = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
        return [self.songs[i] for i in ranked[:max_candidates]]

    def save_song(self, title: str, sections: list[tuple[str, list[str]]]) -> str:
        """Write a new lyrics .md file. Returns the file path.

        Args:
            title: Song title
            sections: List of (section_name, [line1, line2, ...])
        """
        self.lyrics_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        file_path = self.lyrics_dir / f"{safe_name}.md"

        lines = [f"# {title}"]
        for section_name, section_lines in sections:
            lines.append(f"## {section_name}")
            for line in section_lines:
                lines.append(line)
            lines.append("")  # blank line between sections

        file_path.write_text("\n".join(lines), encoding="utf-8")

        # Re-index to include the new song
        self.scan()

        return str(file_path)

    @property
    def song_count(self) -> int:
        return len(self.songs)
