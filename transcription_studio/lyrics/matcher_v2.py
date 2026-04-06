"""Lyrics matching v2 — word-level approach.

Instead of matching Whisper segments to lyrics lines, this works at the
word level: flatten all Whisper words into one stream, align against the
full song lyrics word-by-word, then split into segments at lyrics line
boundaries. Whisper provides timing, lyrics provide the correct words.
"""

import difflib
import string
from dataclasses import dataclass
from core.project import Word, Segment
from lyrics.library import Song, SongLine


_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _norm(w: str) -> str:
    return w.lower().translate(_PUNCT_TABLE)


@dataclass
class SongMatchResult:
    """Result of matching a word stream against a full song."""
    song: Song
    segments: list[Segment]
    anchor_count: int      # how many words matched exactly
    total_lyrics_words: int
    match_ratio: float     # anchor_count / total_lyrics_words


def match_song_words(whisper_words: list[Word], song: Song,
                     section_order: list[str] | None = None) -> SongMatchResult | None:
    """Match a stream of Whisper words against a song's lyrics, word by word.

    Args:
        whisper_words: All Whisper words from the song region, in time order.
        song: The Song object with lyrics lines.
        section_order: Optional ordered list of section names as performed
                       (e.g., ["Verse 1", "Chorus", "Verse 2", "Chorus"]).
                       If None, builds order by detecting repeats.

    Returns:
        SongMatchResult with one Segment per lyrics line, or None if match is too poor.
    """
    if not whisper_words or not song.lines:
        return None

    # Build the full lyrics word list in performance order
    # If no section_order given, try standard patterns then detect
    if section_order is None:
        lyrics_lines = _build_standard_order(whisper_words, song)
    else:
        lyrics_lines = _build_from_section_order(song, section_order)

    if not lyrics_lines:
        return None

    # Flatten lyrics into word list, tracking which line each word belongs to
    lyrics_words: list[str] = []
    lyrics_norm: list[str] = []
    word_to_line: list[int] = []  # index into lyrics_lines

    for line_idx, line in enumerate(lyrics_lines):
        line_words = line.text.split()
        for w in line_words:
            lyrics_words.append(w)
            lyrics_norm.append(_norm(w))
            word_to_line.append(line_idx)

    # Normalize Whisper words
    whisper_norm = [_norm(w.word) for w in whisper_words]

    # Find matching blocks between Whisper and lyrics
    matcher = difflib.SequenceMatcher(None, whisper_norm, lyrics_norm)
    matching_blocks = matcher.get_matching_blocks()

    # Build anchors: for each lyrics word that matched a Whisper word,
    # record the Whisper word's timestamp
    anchors: dict[int, tuple[float, float]] = {}  # lyrics_idx -> (start, end)

    for w_pos, l_pos, size in matching_blocks:
        if size == 0:
            continue
        for i in range(size):
            anchors[l_pos + i] = (whisper_words[w_pos + i].start, whisper_words[w_pos + i].end)

    total_lyrics = len(lyrics_words)
    anchor_count = len(anchors)
    match_ratio = anchor_count / total_lyrics if total_lyrics > 0 else 0

    # Need at least 20% anchors for a usable match
    if match_ratio < 0.2:
        return None

    # Build timestamps for every lyrics word using anchors + interpolation
    word_timestamps = _interpolate_timestamps(
        lyrics_words, anchors,
        whisper_words[0].start, whisper_words[-1].end
    )

    # Split into segments at lyrics line boundaries
    segments = _build_segments(lyrics_lines, lyrics_words, word_to_line,
                               word_timestamps, song)

    return SongMatchResult(
        song=song,
        segments=segments,
        anchor_count=anchor_count,
        total_lyrics_words=total_lyrics,
        match_ratio=match_ratio,
    )


def _build_standard_order(whisper_words: list[Word], song: Song) -> list[SongLine]:
    """Try standard worship song patterns and pick the best match.

    Common patterns:
    - V1 C V2 C V3 C (chorus after every verse)
    - V1 C V2 C V3 C C (double chorus at end)
    - V1 V2 C V3 C (no chorus after V1)
    - Just all sections in order (hymn style, no repeats)
    """
    # Get unique sections in order
    sections: dict[str, list[SongLine]] = {}
    section_order_in_file: list[str] = []
    for line in song.lines:
        if line.section not in sections:
            sections[line.section] = []
            section_order_in_file.append(line.section)
        sections[line.section].append(line)

    # Find the chorus section (if any)
    chorus_name = None
    verse_names = []
    for name in section_order_in_file:
        if name.lower() in ("chorus", "refrain", "bridge"):
            chorus_name = name
        else:
            verse_names.append(name)

    # Build candidate orderings
    candidates: list[list[SongLine]] = []

    # Pattern 1: all sections in file order (no repeats)
    candidates.append(list(song.lines))

    if chorus_name:
        # Pattern 2: V1 C V2 C V3 C ...
        order2 = []
        for vn in verse_names:
            order2.extend(sections[vn])
            order2.extend(sections[chorus_name])
        candidates.append(order2)

        # Pattern 3: V1 C V2 C V3 C C (double chorus at end)
        order3 = list(order2) + list(sections[chorus_name])
        candidates.append(order3)

        # Pattern 4: V1 C V2 C V3 C V4 (verse 4 after last chorus, for songs with coda)
        if len(verse_names) > 1:
            order4 = []
            for vn in verse_names[:-1]:
                order4.extend(sections[vn])
                order4.extend(sections[chorus_name])
            order4.extend(sections[verse_names[-1]])
            candidates.append(order4)

    # Test each candidate against Whisper words
    whisper_norm = [_norm(w.word) for w in whisper_words]
    best_lines = candidates[0]
    best_ratio = 0.0

    for candidate in candidates:
        lyrics_norm = []
        for line in candidate:
            for w in line.text.split():
                lyrics_norm.append(_norm(w))

        sm = difflib.SequenceMatcher(None, whisper_norm, lyrics_norm)
        blocks = sm.get_matching_blocks()
        matched = sum(b.size for b in blocks)
        ratio = matched / len(lyrics_norm) if lyrics_norm else 0

        if ratio > best_ratio:
            best_ratio = ratio
            best_lines = candidate

    return best_lines


def _detect_performance_order(whisper_words: list[Word], song: Song) -> list[SongLine]:
    """Detect which sections were performed and in what order.

    Walks through Whisper words, matching chunks against song sections
    to build the performance order (e.g., V1, Chorus, V2, Chorus, V3, Chorus).
    """
    # Get section ranges
    sections: list[tuple[str, list[SongLine]]] = []
    current_section = song.lines[0].section if song.lines else ""
    current_lines: list[SongLine] = []

    for line in song.lines:
        if line.section != current_section:
            if current_lines:
                sections.append((current_section, current_lines))
            current_section = line.section
            current_lines = []
        current_lines.append(line)
    if current_lines:
        sections.append((current_section, current_lines))

    # Flatten Whisper text into chunks for matching
    whisper_text = " ".join(_norm(w.word) for w in whisper_words)

    # Try to find each section in the whisper text, in order
    # Walk through whisper text position by position
    result_lines: list[SongLine] = []
    whisper_pos = 0
    whisper_words_norm = [_norm(w.word) for w in whisper_words]

    while whisper_pos < len(whisper_words_norm):
        best_section = None
        best_score = 0
        best_section_lines: list[SongLine] = []
        best_advance = 0

        for sec_name, sec_lines in sections:
            # Build section text
            sec_words = []
            for line in sec_lines:
                sec_words.extend(_norm(w) for w in line.text.split())

            if not sec_words:
                continue

            # Try matching this section at current position
            # Take a window of whisper words roughly the same length
            win_size = min(len(sec_words) * 2, len(whisper_words_norm) - whisper_pos)
            if win_size < len(sec_words) // 2:
                continue

            window = whisper_words_norm[whisper_pos:whisper_pos + win_size]

            # Use SequenceMatcher on the word lists
            sm = difflib.SequenceMatcher(None, window, sec_words)
            score = sm.ratio()

            if score > best_score and score > 0.35:
                best_section = sec_name
                best_score = score
                best_section_lines = sec_lines
                # Advance by roughly the section length
                # Use matching blocks to find how far we actually got
                blocks = sm.get_matching_blocks()
                if blocks:
                    last_block = blocks[-2] if len(blocks) > 1 else blocks[0]
                    best_advance = max(last_block.a + last_block.size, len(sec_words) // 2)
                else:
                    best_advance = len(sec_words)

        if best_section and best_score > 0.35:
            result_lines.extend(best_section_lines)
            whisper_pos += best_advance
        else:
            # Skip this word — might be spoken interlude
            whisper_pos += 1

    return result_lines if result_lines else list(song.lines)


def _build_from_section_order(song: Song, section_order: list[str]) -> list[SongLine]:
    """Build lyrics lines from an explicit section order."""
    # Map section names to their lines
    section_map: dict[str, list[SongLine]] = {}
    for line in song.lines:
        if line.section not in section_map:
            section_map[line.section] = []
        section_map[line.section].append(line)

    result = []
    for sec_name in section_order:
        if sec_name in section_map:
            result.extend(section_map[sec_name])
    return result


def _interpolate_timestamps(lyrics_words: list[str],
                            anchors: dict[int, tuple[float, float]],
                            stream_start: float,
                            stream_end: float) -> list[Word]:
    """Build Word objects for every lyrics word using anchor timestamps + interpolation."""

    n = len(lyrics_words)
    word_starts = [0.0] * n

    # Set anchor timestamps
    for idx, (start, end) in anchors.items():
        word_starts[idx] = start

    # Build sorted anchor list for interpolation
    sorted_anchors = sorted(anchors.items())

    # Add virtual anchors at boundaries if needed
    if not sorted_anchors or sorted_anchors[0][0] != 0:
        first_real = sorted_anchors[0][1][0] if sorted_anchors else stream_start
        sorted_anchors.insert(0, (0, (stream_start, stream_start)))
    if sorted_anchors[-1][0] != n - 1:
        last_real = sorted_anchors[-1][1][1] if sorted_anchors else stream_end
        sorted_anchors.append((n - 1, (stream_end, stream_end)))

    # Interpolate between anchors
    for a in range(len(sorted_anchors) - 1):
        idx1 = sorted_anchors[a][0]
        start1 = sorted_anchors[a][1][0]
        idx2 = sorted_anchors[a + 1][0]
        start2 = sorted_anchors[a + 1][1][0]

        for i in range(idx1 + 1, idx2):
            if i not in anchors:
                frac = (i - idx1) / (idx2 - idx1)
                word_starts[i] = start1 + frac * (start2 - start1)

    # Build Word objects — use anchor end times where available
    result = []
    for i, word_text in enumerate(lyrics_words):
        start = round(word_starts[i], 3)

        if i in anchors:
            # Anchor word — use Whisper's actual end time
            end = round(anchors[i][1], 3)
        elif i + 1 < n:
            end = round(word_starts[i + 1], 3)
        else:
            end = round(stream_end, 3)

        if end <= start:
            end = round(start + 0.05, 3)

        result.append(Word(word=word_text, start=start, end=end))

    return result


def _build_segments(lyrics_lines: list[SongLine],
                    lyrics_words: list[str],
                    word_to_line: list[int],
                    word_timestamps: list[Word],
                    song: Song) -> list[Segment]:
    """Split the aligned word stream into Segments at lyrics line boundaries."""

    segments = []
    current_line_idx = -1
    current_words: list[Word] = []

    for i, word in enumerate(word_timestamps):
        line_idx = word_to_line[i]

        if line_idx != current_line_idx:
            # Emit previous segment
            if current_words:
                line = lyrics_lines[current_line_idx]
                seg = Segment(
                    id=len(segments) + 1,
                    type="speech",
                    start=current_words[0].start,
                    end=current_words[-1].end,
                    text=line.text,
                    words=current_words,
                    note=f"Matched: {song.title} (v2)",
                )
                segments.append(seg)

            current_line_idx = line_idx
            current_words = [word]
        else:
            current_words.append(word)

    # Emit final segment
    if current_words and current_line_idx >= 0:
        line = lyrics_lines[current_line_idx]
        seg = Segment(
            id=len(segments) + 1,
            type="speech",
            start=current_words[0].start,
            end=current_words[-1].end,
            text=line.text,
            words=current_words,
            note=f"Matched: {song.title} (v2)",
        )
        segments.append(seg)

    return segments
