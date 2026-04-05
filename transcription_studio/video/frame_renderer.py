"""Frame renderer — composites background + text + speaker name into a QImage."""

from PyQt6.QtGui import QPainter, QImage, QColor, QFont
from PyQt6.QtCore import Qt, QRectF

from core.project import TranscriptProject, Segment
from video.backgrounds import Background, get_background
from video.text_styles import TextStyle, get_text_style


class FrameRenderer:
    """Renders individual video frames given a timestamp."""

    def __init__(self, project: TranscriptProject, width: int, height: int,
                 background_name: str = "Warm Bokeh",
                 text_style_name: str = "Sentence at a Time"):
        self.project = project
        self.width = width
        self.height = height
        self.background = get_background(background_name)
        self.text_style = get_text_style(text_style_name)

        self._last_speaker_id: str = ""
        self._speaker_fade_time: float = 0.0  # when the speaker name started showing

    def render_frame(self, time_seconds: float) -> QImage:
        """Render one frame at the given timestamp. Returns a QImage."""
        image = QImage(self.width, self.height, QImage.Format.Format_RGB888)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 1. Background
        self.background.render(painter, self.width, self.height, time_seconds)

        # 2. Find active segment
        seg = self.project.get_segment_at_time(time_seconds)

        if seg is not None:
            # 3. Speaker name (top center, on change)
            self._render_speaker_name(painter, seg, time_seconds)

            # 4. Transcript text
            words = [{"word": w.word, "start": w.start, "end": w.end} for w in seg.words] if seg.words else None
            is_singing = seg.type == "singing"

            self.text_style.render(
                painter, self.width, self.height,
                seg.text, words,
                seg.start, seg.end,
                time_seconds, is_singing,
            )

        painter.end()
        return image

    def _render_speaker_name(self, painter: QPainter, seg: Segment, time_seconds: float):
        """Show speaker name at top center when speaker changes."""
        speaker_id = seg.speaker_id
        if not speaker_id:
            return

        # Detect speaker change
        if speaker_id != self._last_speaker_id:
            self._last_speaker_id = speaker_id
            self._speaker_fade_time = time_seconds

        # Show for 3 seconds after change, then fade
        elapsed = time_seconds - self._speaker_fade_time
        if elapsed > 4.0:
            return

        alpha = 255
        if elapsed > 3.0:
            alpha = int(255 * (4.0 - elapsed))  # fade out over 1 second

        label = self.project.get_speaker_label(speaker_id)
        if not label:
            return

        # Find speaker color
        speaker_color = QColor(255, 255, 255, alpha)
        for s in self.project.speakers:
            if s.id == speaker_id:
                c = QColor(s.color)
                speaker_color = QColor(c.red(), c.green(), c.blue(), alpha)
                break

        font = QFont("Segoe UI", max(20, self.height // 35))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)

        # Shadow
        rect = QRectF(0, self.height * 0.04, self.width, self.height * 0.06)
        shadow_rect = QRectF(rect.x() + 2, rect.y() + 2, rect.width(), rect.height())
        painter.setPen(QColor(0, 0, 0, min(alpha, 180)))
        painter.drawText(shadow_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)

        # Name
        painter.setPen(speaker_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
