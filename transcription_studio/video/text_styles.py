"""Transcription display styles for video rendering."""

import math
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen
from PyQt6.QtCore import Qt, QRectF


class TextStyle:
    """Base class for text display styles."""

    name: str = "Base"

    def render(self, painter: QPainter, width: int, height: int,
               text: str, words: list[dict] | None,
               segment_start: float, segment_end: float,
               current_time: float, is_singing: bool):
        """Render transcript text onto the frame.

        Args:
            painter: QPainter for the frame
            width, height: frame dimensions
            text: full segment text
            words: list of {"word", "start", "end"} or None
            segment_start, segment_end: segment time bounds
            current_time: current playback time
            is_singing: True if this is a singing segment
        """
        raise NotImplementedError

    def _draw_text_with_shadow(self, painter: QPainter, x: int, y: int, text: str,
                                font: QFont, color: QColor, shadow_offset: int = 2):
        """Draw text with a dark shadow for readability."""
        painter.setFont(font)
        # Shadow
        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(x + shadow_offset, y + shadow_offset, text)
        # Main text
        painter.setPen(color)
        painter.drawText(x, y, text)

    def _draw_text_centered(self, painter: QPainter, rect: QRectF, text: str,
                             font: QFont, color: QColor, shadow_offset: int = 2):
        painter.setFont(font)
        # Shadow
        shadow_rect = QRectF(rect.x() + shadow_offset, rect.y() + shadow_offset,
                              rect.width(), rect.height())
        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(shadow_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
        # Main text
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)


class SentenceAtATime(TextStyle):
    """One sentence centered on screen, fades between segments."""

    name = "Sentence at a Time"

    def render(self, painter, width, height, text, words,
               segment_start, segment_end, current_time, is_singing):
        font = QFont("Segoe UI", max(28, height // 25))
        font.setWeight(QFont.Weight.Medium)

        # Fade in/out at segment boundaries
        fade_duration = 0.4
        alpha = 255
        elapsed = current_time - segment_start
        remaining = segment_end - current_time

        if elapsed < fade_duration:
            alpha = int(255 * elapsed / fade_duration)
        elif remaining < fade_duration:
            alpha = int(255 * remaining / fade_duration)

        if is_singing:
            color = QColor(100, 200, 220, alpha)
            text = f"\u266b {text} \u266b"
        else:
            color = QColor(255, 255, 255, alpha)

        margin = width * 0.1
        rect = QRectF(margin, height * 0.35, width - 2 * margin, height * 0.3)
        self._draw_text_centered(painter, rect, text, font, color)


class SubtitleStyle(TextStyle):
    """1-2 lines at the bottom, classic subtitle look."""

    name = "Subtitle (Bottom)"

    def render(self, painter, width, height, text, words,
               segment_start, segment_end, current_time, is_singing):
        font = QFont("Segoe UI", max(24, height // 30))

        if is_singing:
            color = QColor(100, 200, 220)
            text = f"\u266b {text} \u266b"
        else:
            color = QColor(255, 255, 255)

        margin = width * 0.08
        box_height = height * 0.12
        rect = QRectF(margin, height - box_height - height * 0.06,
                       width - 2 * margin, box_height)

        # Semi-transparent background box
        bg_rect = QRectF(rect.x() - 10, rect.y() - 5,
                          rect.width() + 20, rect.height() + 10)
        painter.fillRect(bg_rect, QColor(0, 0, 0, 140))

        self._draw_text_centered(painter, rect, text, font, color, shadow_offset=1)


class WordByWordHighlight(TextStyle):
    """All words visible, current word highlighted bright."""

    name = "Word-by-Word Highlight"

    def render(self, painter, width, height, text, words,
               segment_start, segment_end, current_time, is_singing):
        font = QFont("Segoe UI", max(28, height // 25))
        font.setWeight(QFont.Weight.Medium)
        fm = QFontMetrics(font)
        painter.setFont(font)

        if is_singing or not words:
            # Fall back to sentence style for singing or missing word data
            color = QColor(100, 200, 220) if is_singing else QColor(255, 255, 255)
            if is_singing:
                text = f"\u266b {text} \u266b"
            margin = width * 0.1
            rect = QRectF(margin, height * 0.35, width - 2 * margin, height * 0.3)
            self._draw_text_centered(painter, rect, text, font, color)
            return

        # Find current word
        current_word_idx = 0
        for i, w in enumerate(words):
            if w["start"] <= current_time:
                current_word_idx = i

        # Draw all words, highlight the current one
        word_texts = [w["word"] for w in words]
        full_text = " ".join(word_texts)
        total_width = fm.horizontalAdvance(full_text)
        start_x = (width - total_width) / 2
        y = int(height * 0.5)

        # Shadow pass
        x = start_x
        for i, wt in enumerate(word_texts):
            painter.setPen(QColor(0, 0, 0, 180))
            painter.drawText(int(x) + 2, y + 2, wt)
            x += fm.horizontalAdvance(wt + " ")

        # Color pass
        x = start_x
        for i, wt in enumerate(word_texts):
            if i == current_word_idx:
                painter.setPen(QColor(255, 230, 50))  # bright yellow
            elif i < current_word_idx:
                painter.setPen(QColor(200, 200, 200, 200))  # already spoken
            else:
                painter.setPen(QColor(150, 150, 150, 120))  # upcoming
            painter.drawText(int(x), y, wt)
            x += fm.horizontalAdvance(wt + " ")


class ScrollUp(TextStyle):
    """Teleprompter style — text scrolls upward."""

    name = "Scroll Up"

    def render(self, painter, width, height, text, words,
               segment_start, segment_end, current_time, is_singing):
        font = QFont("Segoe UI", max(24, height // 30))
        painter.setFont(font)

        if is_singing:
            color = QColor(100, 200, 220)
            text = f"\u266b {text} \u266b"
        else:
            color = QColor(255, 255, 255)

        # Position based on time within segment
        progress = 0.0
        if segment_end > segment_start:
            progress = (current_time - segment_start) / (segment_end - segment_start)

        # Text starts at bottom, scrolls to center, then up
        y_start = height * 0.75
        y_end = height * 0.25
        y = y_start + (y_end - y_start) * progress

        margin = width * 0.1
        rect = QRectF(margin, y - height * 0.05, width - 2 * margin, height * 0.15)

        # Fade based on position
        alpha = 255
        if y < height * 0.3:
            alpha = int(255 * (y - height * 0.1) / (height * 0.2))
        elif y > height * 0.7:
            alpha = int(255 * (height * 0.9 - y) / (height * 0.2))
        alpha = max(0, min(255, alpha))

        color = QColor(color.red(), color.green(), color.blue(), alpha)
        self._draw_text_centered(painter, rect, text, font, color)


# Registry
ALL_TEXT_STYLES = [SentenceAtATime, SubtitleStyle, WordByWordHighlight, ScrollUp]

def get_text_style(name: str) -> TextStyle:
    for cls in ALL_TEXT_STYLES:
        if cls.name == name:
            return cls()
    return SentenceAtATime()
