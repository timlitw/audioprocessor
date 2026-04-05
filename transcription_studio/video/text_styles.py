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
        raise NotImplementedError

    def _fit_font_size(self, painter: QPainter, text: str, max_width: int,
                        max_height: int, font_name: str, max_size: int, min_size: int = 16) -> QFont:
        """Find the largest font size that fits the text in the given area."""
        for size in range(max_size, min_size - 1, -2):
            font = QFont(font_name, size)
            font.setWeight(QFont.Weight.Medium)
            painter.setFont(font)
            fm = QFontMetrics(font)
            bounding = fm.boundingRect(
                QRectF(0, 0, max_width, max_height).toRect(),
                Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter,
                text,
            )
            if bounding.height() <= max_height and bounding.width() <= max_width + 10:
                return font
        font = QFont(font_name, min_size)
        font.setWeight(QFont.Weight.Medium)
        return font

    def _draw_text_centered(self, painter: QPainter, rect: QRectF, text: str,
                             font: QFont, color: QColor, shadow_offset: int = 2):
        painter.setFont(font)
        flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap

        # Draw shadow/outline for readability (multiple offsets for thickness)
        shadow_color = QColor(0, 0, 0, min(color.alpha(), 200))
        painter.setPen(shadow_color)
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 2), (2, 0), (0, -2), (-2, 0)]:
            offset_rect = QRectF(rect.x() + dx, rect.y() + dy, rect.width(), rect.height())
            painter.drawText(offset_rect, flags, text)

        # Main text
        painter.setPen(color)
        painter.drawText(rect, flags, text)


class SentenceAtATime(TextStyle):
    """One sentence centered on screen, fades between segments."""

    name = "Sentence at a Time"

    def render(self, painter, width, height, text, words,
               segment_start, segment_end, current_time, is_singing):

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

        margin = width * 0.08
        text_width = int(width - 2 * margin)
        text_height = int(height * 0.5)
        max_font = max(24, height // 22)

        font = self._fit_font_size(painter, text, text_width, text_height, "Segoe UI", max_font)

        rect = QRectF(margin, height * 0.2, text_width, text_height)
        self._draw_text_centered(painter, rect, text, font, color)


class SubtitleStyle(TextStyle):
    """1-2 lines at the bottom, classic subtitle look."""

    name = "Subtitle (Bottom)"

    def render(self, painter, width, height, text, words,
               segment_start, segment_end, current_time, is_singing):

        if is_singing:
            color = QColor(100, 200, 220)
            text = f"\u266b {text} \u266b"
        else:
            color = QColor(255, 255, 255)

        margin = width * 0.06
        text_width = int(width - 2 * margin)
        max_text_height = int(height * 0.2)
        max_font = max(20, height // 28)

        font = self._fit_font_size(painter, text, text_width, max_text_height, "Segoe UI", max_font)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Measure actual text height to size the background box
        bounding = fm.boundingRect(
            QRectF(0, 0, text_width, max_text_height).toRect(),
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter,
            text,
        )
        actual_height = bounding.height() + 20  # padding

        y_top = height - actual_height - height * 0.05
        rect = QRectF(margin, y_top, text_width, actual_height)

        # Semi-transparent background box
        bg_rect = QRectF(rect.x() - 12, rect.y() - 6, rect.width() + 24, rect.height() + 12)
        painter.fillRect(bg_rect, QColor(0, 0, 0, 160))

        self._draw_text_centered(painter, rect, text, font, color, shadow_offset=1)


class WordByWordHighlight(TextStyle):
    """All words visible, current word highlighted bright."""

    name = "Word-by-Word Highlight"

    def render(self, painter, width, height, text, words,
               segment_start, segment_end, current_time, is_singing):

        if is_singing or not words:
            # Fall back to sentence style
            color = QColor(100, 200, 220) if is_singing else QColor(255, 255, 255)
            if is_singing:
                text = f"\u266b {text} \u266b"
            margin = width * 0.08
            text_width = int(width - 2 * margin)
            max_font = max(24, height // 22)
            font = self._fit_font_size(painter, text, text_width, int(height * 0.5), "Segoe UI", max_font)
            rect = QRectF(margin, height * 0.2, text_width, height * 0.5)
            self._draw_text_centered(painter, rect, text, font, color)
            return

        # Find current word
        current_word_idx = 0
        for i, w in enumerate(words):
            if w["start"] <= current_time:
                current_word_idx = i

        # Auto-size font
        margin = width * 0.08
        text_width = int(width - 2 * margin)
        max_font = max(24, height // 22)
        font = self._fit_font_size(painter, text, text_width, int(height * 0.4), "Segoe UI", max_font)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Lay out words with word wrap
        word_texts = [w["word"] for w in words]
        space_width = fm.horizontalAdvance(" ")

        # Build lines
        lines = []
        current_line = []
        current_line_width = 0
        for wt in word_texts:
            w_width = fm.horizontalAdvance(wt)
            if current_line and current_line_width + space_width + w_width > text_width:
                lines.append(current_line)
                current_line = [wt]
                current_line_width = w_width
            else:
                if current_line:
                    current_line_width += space_width
                current_line.append(wt)
                current_line_width += w_width
        if current_line:
            lines.append(current_line)

        line_height = fm.height() * 1.3
        total_height = line_height * len(lines)
        y_start = (height - total_height) / 2

        word_idx = 0
        for line_num, line_words in enumerate(lines):
            line_text = " ".join(line_words)
            line_width = fm.horizontalAdvance(line_text)
            x = (width - line_width) / 2
            y = y_start + line_num * line_height + fm.ascent()

            for wt in line_words:
                # Shadow
                painter.setPen(QColor(0, 0, 0, 200))
                for dx, dy in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
                    painter.drawText(int(x) + dx, int(y) + dy, wt)

                # Color based on position
                if word_idx == current_word_idx:
                    painter.setPen(QColor(255, 230, 50))  # bright yellow
                elif word_idx < current_word_idx:
                    painter.setPen(QColor(220, 220, 220))  # spoken
                else:
                    painter.setPen(QColor(140, 140, 140, 150))  # upcoming
                painter.drawText(int(x), int(y), wt)

                x += fm.horizontalAdvance(wt) + space_width
                word_idx += 1


class ScrollUp(TextStyle):
    """Teleprompter style — text scrolls upward."""

    name = "Scroll Up"

    def render(self, painter, width, height, text, words,
               segment_start, segment_end, current_time, is_singing):

        if is_singing:
            color = QColor(100, 200, 220)
            text = f"\u266b {text} \u266b"
        else:
            color = QColor(255, 255, 255)

        # Position based on time within segment
        progress = 0.0
        if segment_end > segment_start:
            progress = (current_time - segment_start) / (segment_end - segment_start)

        # Text starts below center, scrolls above center
        y_start = height * 0.6
        y_end = height * 0.2
        y_center = y_start + (y_end - y_start) * progress

        margin = width * 0.08
        text_width = int(width - 2 * margin)
        max_font = max(22, height // 26)
        font = self._fit_font_size(painter, text, text_width, int(height * 0.3), "Segoe UI", max_font)

        rect = QRectF(margin, y_center, text_width, height * 0.3)

        # Fade based on vertical position
        alpha = 255
        if y_center < height * 0.25:
            alpha = int(255 * max(0, (y_center - height * 0.1)) / (height * 0.15))
        elif y_center > height * 0.55:
            alpha = int(255 * max(0, (height * 0.7 - y_center)) / (height * 0.15))
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
