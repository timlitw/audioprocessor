"""Lyrics matching — fuzzy match segments against the lyrics library."""

import difflib
import string
from dataclasses import dataclass
from lyrics.library import LyricsLibrary, Song, _normalize


@dataclass
class MatchResult:
    """Result of matching a segment against the lyrics library."""
    song: Song
    line_start: int    # index of first matched line in song.lines
    line_end: int      # index past last matched line (exclusive)
    score: float       # 0.0 to 1.0 confidence
    matched_text: str  # the correct lyrics text for the segment


class LyricsMatcher:
    """Match transcribed text against the lyrics library."""

    def __init__(self, library: LyricsLibrary):
        self.library = library

    def match_segment(self, text: str, candidates: list[Song] | None = None,
                      threshold: float = 0.55) -> MatchResult | None:
        """Match a segment's text against the library (open search).

        Returns the best match above threshold, or None.
        """
        if not text or not text.strip():
            return None

        if candidates is None:
            candidates = self.library.get_candidates(text)

        if not candidates:
            return None

        normalized = _normalize(text)
        best: MatchResult | None = None

        for song in candidates:
            result = self._best_window_match(normalized, song)
            if result and result.score >= threshold:
                if best is None or result.score > best.score:
                    best = result

        return best

    def match_in_song(self, text: str, song: Song,
                      expected_line: int = 0,
                      window: int = 8) -> MatchResult | None:
        """Match text against a specific song near expected_line.

        Used for sequential tracking within a known song.
        Also searches repeatable sections (Chorus, Bridge) regardless of position.
        """
        if not text or not text.strip():
            return None

        normalized = _normalize(text)
        search_start = max(0, expected_line - window)
        search_end = min(len(song.lines), expected_line + window)

        # Search near expected position
        best = self._best_window_match(normalized, song, search_start, search_end)

        # Also search repeatable sections (chorus, bridge) anywhere in the song
        repeatable = {"chorus", "bridge", "refrain"}
        for section_start, section_end in self._get_section_ranges(song):
            section_name = song.lines[section_start].section.lower()
            if any(r in section_name for r in repeatable):
                # Skip if already within the search window
                if section_start >= search_start and section_end <= search_end:
                    continue
                result = self._best_window_match(normalized, song, section_start, section_end)
                if result and (best is None or result.score > best.score):
                    best = result

        return best

    @staticmethod
    def _get_section_ranges(song: Song) -> list[tuple[int, int]]:
        """Get (start, end) line index ranges for each section in the song."""
        if not song.lines:
            return []
        ranges = []
        current_section = song.lines[0].section
        section_start = 0
        for i, line in enumerate(song.lines):
            if line.section != current_section:
                ranges.append((section_start, i))
                current_section = line.section
                section_start = i
        ranges.append((section_start, len(song.lines)))
        return ranges

    def _best_window_match(self, normalized_text: str, song: Song,
                           search_start: int = 0,
                           search_end: int | None = None) -> MatchResult | None:
        """Find the best matching window of 1-4 consecutive lines in a song."""
        if search_end is None:
            search_end = len(song.lines)

        input_word_count = len(normalized_text.split())
        best: MatchResult | None = None

        for window_size in range(1, 5):  # 1 to 4 lines
            for start in range(search_start, search_end):
                end = min(start + window_size, len(song.lines))
                if end > search_end:
                    break

                window_text = " ".join(
                    song.lines[i].normalized for i in range(start, end)
                )

                # Reject if lyrics have way more words than the segment
                # (prevents cramming a whole verse into a short segment)
                lyrics_word_count = len(window_text.split())
                if input_word_count > 0 and lyrics_word_count > input_word_count * 2:
                    continue

                score = difflib.SequenceMatcher(
                    None, normalized_text, window_text
                ).ratio()

                if best is None or score > best.score:
                    matched_original = " ".join(
                        song.lines[i].text for i in range(start, end)
                    )
                    best = MatchResult(
                        song=song,
                        line_start=start,
                        line_end=end,
                        score=score,
                        matched_text=matched_original,
                    )

        return best


class SongTracker:
    """Track sequential position within a detected song during transcription."""

    MAX_MISSES = 3

    def __init__(self, matcher: LyricsMatcher):
        self.matcher = matcher
        self.active_song: Song | None = None
        self.next_expected_line: int = 0
        self.consecutive_misses: int = 0

    def process_segment(self, text: str) -> MatchResult | None:
        """Process a new segment. Returns a match result if lyrics were found."""

        # If tracking a song, try sequential match first
        if self.active_song is not None:
            result = self.matcher.match_in_song(
                text, self.active_song,
                expected_line=self.next_expected_line,
            )

            if result and result.score >= 0.45:
                self.next_expected_line = result.line_end
                self.consecutive_misses = 0
                return result

            # Miss — maybe song ended or a spoken interlude
            self.consecutive_misses += 1
            if self.consecutive_misses >= self.MAX_MISSES:
                self.reset()
            else:
                return None  # give it a chance to resume

        # Open match — try to detect a new song
        result = self.matcher.match_segment(text, threshold=0.55)
        if result:
            self.active_song = result.song
            self.next_expected_line = result.line_end
            self.consecutive_misses = 0
            return result

        return None

    def reset(self):
        """Clear tracking state."""
        self.active_song = None
        self.next_expected_line = 0
        self.consecutive_misses = 0
