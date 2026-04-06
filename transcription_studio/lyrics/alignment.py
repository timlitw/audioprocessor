"""Word alignment — map Whisper timestamps onto correct lyrics words."""

import difflib
import string
from core.project import Word


_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _normalize_word(w: str) -> str:
    return w.lower().translate(_PUNCT_TABLE)


def align_words(whisper_words: list[Word], lyrics_text: str) -> list[Word]:
    """Map Whisper's word timestamps onto the correct lyrics words.

    Returns new Word objects with correct lyrics text and estimated timestamps.
    """
    if not whisper_words or not lyrics_text.strip():
        return whisper_words

    lyrics_word_list = lyrics_text.split()
    if not lyrics_word_list:
        return whisper_words

    # Normalize both sequences for alignment
    w_norm = [_normalize_word(w.word) for w in whisper_words]
    l_norm = [_normalize_word(w) for w in lyrics_word_list]

    # Build a mapping: for each lyrics word index, find its best Whisper word index
    matcher = difflib.SequenceMatcher(None, w_norm, l_norm)
    opcodes = matcher.get_opcodes()

    # Map each lyrics word to a fractional position in the Whisper word list
    lyrics_to_whisper: dict[int, float] = {}

    for tag, w_start, w_end, l_start, l_end in opcodes:
        w_len = w_end - w_start
        l_len = l_end - l_start

        if tag == "equal" or tag == "replace":
            # Map proportionally
            for i in range(l_len):
                if w_len > 0:
                    w_pos = w_start + (i * w_len / l_len)
                    lyrics_to_whisper[l_start + i] = w_pos
        elif tag == "insert":
            # Lyrics words with no Whisper counterpart — interpolate
            # Use the Whisper position just before this insertion
            anchor = w_start - 0.5 if w_start > 0 else 0.0
            for i in range(l_len):
                if l_len > 1:
                    frac = i / (l_len - 1) if l_len > 1 else 0
                    lyrics_to_whisper[l_start + i] = anchor + frac * 0.5
                else:
                    lyrics_to_whisper[l_start + i] = anchor
        # "delete" — Whisper words with no lyrics counterpart, skip them

    # Now build Word objects for each lyrics word with interpolated timestamps
    seg_start = whisper_words[0].start
    seg_end = whisper_words[-1].end
    total_w = len(whisper_words)

    result: list[Word] = []

    for l_idx, lyrics_word in enumerate(lyrics_word_list):
        w_pos = lyrics_to_whisper.get(l_idx)

        if w_pos is not None:
            # Interpolate timestamp from Whisper word positions
            w_int = int(w_pos)
            w_frac = w_pos - w_int

            if w_int < total_w:
                start = whisper_words[w_int].start
                if w_int + 1 < total_w:
                    start = start + w_frac * (whisper_words[w_int + 1].start - start)
            else:
                start = seg_end

            # End time: use next lyrics word's start, or seg_end
            end = seg_end  # default
        else:
            # Fallback: distribute evenly
            frac = l_idx / max(len(lyrics_word_list) - 1, 1)
            start = seg_start + frac * (seg_end - seg_start)
            end = seg_end

        result.append(Word(word=lyrics_word, start=round(start, 3), end=round(end, 3)))

    # Fix end times: each word ends when the next begins
    for i in range(len(result) - 1):
        result[i] = Word(
            word=result[i].word,
            start=result[i].start,
            end=result[i + 1].start,
        )
    # Last word ends at segment end
    if result:
        result[-1] = Word(
            word=result[-1].word,
            start=result[-1].start,
            end=seg_end,
        )

    # Ensure monotonicity
    for i in range(1, len(result)):
        if result[i].start < result[i - 1].start:
            result[i] = Word(
                word=result[i].word,
                start=result[i - 1].end,
                end=max(result[i].end, result[i - 1].end),
            )

    return result
