"""Frame renderer — composites background + text + speaker name into a QImage."""

from PyQt6.QtGui import QPainter, QImage, QColor, QFont
from PyQt6.QtCore import Qt, QRectF

from core.project import TranscriptProject, Segment
from video.backgrounds import Background, CustomImage, get_background
from video.text_styles import TextStyle, get_text_style


class FrameRenderer:
    """Renders individual video frames given a timestamp."""

    def __init__(self, project: TranscriptProject, width: int, height: int,
                 background_name: str = "Warm Bokeh",
                 text_style_name: str = "Sentence at a Time"):
        self.project = project
        self.width = width
        self.height = height
        self.default_background = get_background(background_name)
        self.background = self.default_background
        self.text_style = get_text_style(text_style_name)

        # Background trigger cache: maps background_change string -> Background instance
        self._bg_cache: dict[str, Background] = {}
        self._current_bg_key: str = ""

        self._last_speaker_id: str = ""
        self._speaker_fade_time: float = 0.0

    def render_frame(self, time_seconds: float) -> QImage:
        """Render one frame at the given timestamp. Returns a QImage."""
        image = QImage(self.width, self.height, QImage.Format.Format_RGB888)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 1. Resolve background (check for segment triggers)
        active_bg = self._resolve_background(time_seconds)
        active_bg.render(painter, self.width, self.height, time_seconds)

        # 2. Find active segment
        seg = self.project.get_segment_at_time(time_seconds)

        if seg is not None:
            # 3. Speaker name (top center, uses sticky speaker)
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

    def _resolve_background(self, time_seconds: float) -> Background:
        """Find the effective background at this time using segment triggers."""
        # Walk segments to find the most recent background_change
        effective_bg = ""
        for seg in self.project.segments:
            if seg.start > time_seconds:
                break
            if seg.background_change:
                effective_bg = seg.background_change

        if not effective_bg:
            return self.background  # use the default/manually set background

        # Cache background instances
        if effective_bg not in self._bg_cache:
            if effective_bg.startswith("image:"):
                path = effective_bg[6:]
                self._bg_cache[effective_bg] = CustomImage([path])
            else:
                self._bg_cache[effective_bg] = get_background(effective_bg)

        return self._bg_cache[effective_bg]

    def _render_speaker_name(self, painter: QPainter, seg: Segment, time_seconds: float):
        """Show speaker name at top center when speaker changes. Uses sticky lookup."""
        # Find the effective speaker (sticky from last assignment)
        seg_idx = self.project.segments.index(seg) if seg in self.project.segments else -1
        speaker_id = self.project.get_effective_speaker(seg_idx) if seg_idx >= 0 else seg.speaker_id

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
            alpha = int(255 * (4.0 - elapsed))

        label = self.project.get_speaker_label(speaker_id)
        if not label:
            return

        speaker_color = QColor(255, 255, 255, alpha)
        for s in self.project.speakers:
            if s.id == speaker_id:
                c = QColor(s.color)
                speaker_color = QColor(c.red(), c.green(), c.blue(), alpha)
                break

        font = QFont("Segoe UI", max(20, self.height // 35))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)

        rect = QRectF(0, self.height * 0.04, self.width, self.height * 0.06)

        # Outline
        painter.setPen(QColor(0, 0, 0, min(alpha, 200)))
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 2), (2, 0)]:
            offset_rect = QRectF(rect.x() + dx, rect.y() + dy, rect.width(), rect.height())
            painter.drawText(offset_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)

        painter.setPen(speaker_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
