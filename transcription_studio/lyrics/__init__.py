"""Lyrics matching system — auto-detect songs and correct transcriptions."""

from lyrics.library import LyricsLibrary, Song, SongLine
from lyrics.matcher import LyricsMatcher, SongTracker, MatchResult
from lyrics.alignment import align_words
