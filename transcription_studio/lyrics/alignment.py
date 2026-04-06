"""Word alignment — map Whisper timestamps onto correct lyrics words."""

import difflib
import string
from core.project import Word


_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _normalize_word(w: str) -> str:
    return w.lower().translate(_PUNCT_TABLE)


def align_words(whisper_words: list[Word], lyrics_text: str) -> list[Word]:
    """Map Whisper's word timestamps onto the correct lyrics words.

    Strategy:
    1. Find matching words between Whisper and lyrics using SequenceMatcher
    2. Use matched words as timing anchors (their timestamps are reliable)
    3. Distribute unmatched lyrics words evenly between anchors
    4. If too few anchors exist (< 30% match), fall back to even distribution

    Returns new Word objects with correct lyrics text and estimated timestamps.
    """
    if not whisper_words or not lyrics_text.strip():
        return whisper_words

    lyrics_word_list = lyrics_text.split()
    if not lyrics_word_list:
        return whisper_words

    seg_start = whisper_words[0].start
    seg_end = whisper_words[-1].end

    # Normalize both sequences for alignment
    w_norm = [_normalize_word(w.word) for w in whisper_words]
    l_norm = [_normalize_word(w) for w in lyrics_word_list]

    # Find matching blocks between the two word sequences
    matcher = difflib.SequenceMatcher(None, w_norm, l_norm)
    matching_blocks = matcher.get_matching_blocks()

    # Build anchors: lyrics word index -> whisper word timestamp
    # An anchor is a lyrics word that matched a Whisper word exactly
    anchors: list[tuple[int, float, float]] = []  # (lyrics_idx, start, end)

    for w_pos, l_pos, size in matching_blocks:
        if size == 0:
            continue
        for i in range(size):
            w_idx = w_pos + i
            l_idx = l_pos + i
            anchors.append((l_idx, whisper_words[w_idx].start, whisper_words[w_idx].end))

    total_lyrics = len(lyrics_word_list)
    match_ratio = len(anchors) / total_lyrics if total_lyrics > 0 else 0

    # If too few anchors, just distribute evenly across the time window
    if match_ratio < 0.3 or len(anchors) < 2:
        return _distribute_evenly(lyrics_word_list, seg_start, seg_end)

    # Build timestamps using anchors + interpolation between them
    # Add virtual anchors at start and end
    all_anchors = [(0, seg_start, seg_start)] if anchors[0][0] != 0 else []
    all_anchors.extend(anchors)
    if anchors[-1][0] != total_lyrics - 1:
        all_anchors.append((total_lyrics - 1, seg_end, seg_end))

    # For each lyrics word, find its timestamp
    word_starts: list[float] = [0.0] * total_lyrics

    # Set anchor timestamps directly
    anchor_set = {}
    for l_idx, start, end in anchors:
        anchor_set[l_idx] = start
        word_starts[l_idx] = start

    # Interpolate between anchors for non-anchor words
    # Walk through all_anchors pairwise and fill in gaps
    for a in range(len(all_anchors) - 1):
        idx1, start1, _ = all_anchors[a]
        idx2, start2, _ = all_anchors[a + 1]

        if idx2 - idx1 <= 1:
            continue  # no gap to fill

        # Distribute words evenly between these two anchors
        for i in range(idx1 + 1, idx2):
            if i not in anchor_set:
                frac = (i - idx1) / (idx2 - idx1)
                word_starts[i] = start1 + frac * (start2 - start1)

    # Handle words before first anchor
    if anchors[0][0] > 0:
        first_anchor_idx, first_anchor_start, _ = anchors[0]
        time_per_word = (first_anchor_start - seg_start) / first_anchor_idx if first_anchor_idx > 0 else 0
        for i in range(first_anchor_idx):
            word_starts[i] = seg_start + i * time_per_word

    # Build Word objects with end times
    result: list[Word] = []
    for i, lyrics_word in enumerate(lyrics_word_list):
        start = round(word_starts[i], 3)
        if i + 1 < total_lyrics:
            end = round(word_starts[i + 1], 3)
        else:
            end = round(seg_end, 3)

        # Ensure positive duration
        if end <= start:
            end = round(start + 0.05, 3)

        result.append(Word(word=lyrics_word, start=start, end=end))

    # Final monotonicity check
    for i in range(1, len(result)):
        if result[i].start < result[i - 1].end:
            result[i] = Word(
                word=result[i].word,
                start=result[i - 1].end,
                end=max(result[i].end, result[i - 1].end + 0.05),
            )

    # Clamp last word to segment end
    if result and result[-1].end > seg_end + 0.1:
        result[-1] = Word(word=result[-1].word, start=result[-1].start, end=round(seg_end, 3))

    return result


def _distribute_evenly(lyrics_words: list[str], start: float, end: float) -> list[Word]:
    """Distribute lyrics words evenly across a time window.

    Used when Whisper's output is too garbled to align word-by-word.
    """
    n = len(lyrics_words)
    if n == 0:
        return []

    duration = end - start
    word_duration = duration / n

    return [
        Word(
            word=lyrics_words[i],
            start=round(start + i * word_duration, 3),
            end=round(start + (i + 1) * word_duration, 3),
        )
        for i in range(n)
    ]
