"""Procedural background generators — render directly via QPainter."""

import math
import random
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QLinearGradient, QPainterPath
from PyQt6.QtCore import QPointF, QRectF


class Background:
    """Base class for procedural backgrounds."""

    name: str = "Base"

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        raise NotImplementedError


class WarmBokeh(Background):
    """Soft, out-of-focus light orbs drifting on a dark background."""

    name = "Warm Bokeh"

    def __init__(self, num_orbs: int = 35, seed: int = 42):
        rng = random.Random(seed)
        self._orbs = []
        colors = [
            (255, 180, 60),   # amber
            (255, 140, 40),   # deep amber
            (255, 200, 100),  # gold
            (220, 100, 80),   # soft red
            (200, 160, 220),  # soft lavender
            (255, 160, 140),  # soft pink
        ]
        for _ in range(num_orbs):
            r, g, b = rng.choice(colors)
            self._orbs.append({
                "x": rng.uniform(0, 1),
                "y": rng.uniform(0, 1),
                "radius": rng.uniform(0.03, 0.12),
                "speed_x": rng.uniform(-0.005, 0.005),
                "speed_y": rng.uniform(-0.003, 0.003),
                "pulse_speed": rng.uniform(0.3, 0.8),
                "pulse_phase": rng.uniform(0, math.tau),
                "alpha": rng.randint(15, 50),
                "color": (r, g, b),
            })

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        painter.fillRect(0, 0, width, height, QColor(15, 10, 20))

        for orb in self._orbs:
            # Drift position (wrapping)
            x = (orb["x"] + orb["speed_x"] * time_seconds) % 1.2 - 0.1
            y = (orb["y"] + orb["speed_y"] * time_seconds) % 1.2 - 0.1

            # Pulse size
            pulse = 1.0 + 0.3 * math.sin(orb["pulse_speed"] * time_seconds + orb["pulse_phase"])
            radius = orb["radius"] * pulse * min(width, height)

            cx = x * width
            cy = y * height
            r, g, b = orb["color"]
            alpha = orb["alpha"]

            gradient = QRadialGradient(QPointF(cx, cy), radius)
            gradient.setColorAt(0.0, QColor(r, g, b, alpha))
            gradient.setColorAt(0.5, QColor(r, g, b, alpha // 2))
            gradient.setColorAt(1.0, QColor(r, g, b, 0))

            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), radius, radius)


class Starfield(Background):
    """Drifting white particles on deep blue/black."""

    name = "Starfield"

    def __init__(self, num_stars: int = 200, seed: int = 42):
        rng = random.Random(seed)
        self._stars = []
        for _ in range(num_stars):
            self._stars.append({
                "x": rng.uniform(0, 1),
                "y": rng.uniform(0, 1),
                "size": rng.uniform(1, 3),
                "speed": rng.uniform(0.002, 0.01),
                "brightness": rng.randint(120, 255),
            })

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        painter.fillRect(0, 0, width, height, QColor(5, 5, 15))

        for star in self._stars:
            x = (star["x"] + star["speed"] * time_seconds) % 1.0
            y = star["y"]
            b = star["brightness"]

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(b, b, int(b * 0.9), b))
            painter.drawEllipse(QPointF(x * width, y * height), star["size"], star["size"])


class GradientSweep(Background):
    """Slowly rotating color gradient."""

    name = "Gradient Sweep"

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        angle = time_seconds * 0.05  # slow rotation
        cx, cy = width / 2, height / 2
        r = max(width, height) * 0.8

        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx - r * math.cos(angle)
        y2 = cy - r * math.sin(angle)

        gradient = QLinearGradient(QPointF(x1, y1), QPointF(x2, y2))
        gradient.setColorAt(0.0, QColor(10, 15, 50))
        gradient.setColorAt(0.5, QColor(30, 15, 60))
        gradient.setColorAt(1.0, QColor(10, 10, 35))

        painter.fillRect(0, 0, width, height, gradient)


class Waves(Background):
    """Sine wave animation, ocean palette."""

    name = "Waves"

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        painter.fillRect(0, 0, width, height, QColor(8, 15, 30))

        for layer in range(4):
            y_base = height * (0.55 + layer * 0.1)
            amplitude = 20 + layer * 10
            freq = 0.005 - layer * 0.001
            speed = 0.5 + layer * 0.2
            alpha = 40 - layer * 8

            path = QPainterPath()
            path.moveTo(0, height)

            for x in range(0, width + 2, 3):
                y = y_base + amplitude * math.sin(freq * x + speed * time_seconds + layer)
                if x == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            path.lineTo(width, height)
            path.lineTo(0, height)
            path.closeSubpath()

            color = QColor(30 + layer * 15, 60 + layer * 20, 120 + layer * 20, alpha)
            painter.fillPath(path, color)


class SolidDark(Background):
    """Plain dark background."""

    name = "Solid Dark"

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        painter.fillRect(0, 0, width, height, QColor(20, 20, 35))


class CustomImage(Background):
    """Single static image scaled to fill the frame."""

    name = "Custom Image"

    def __init__(self, image_paths: list[str] | None = None, slide_duration: float = 30.0):
        self._images: list[QImage] = []
        self._scaled_cache: dict[tuple, QImage] = {}
        self._slide_duration = slide_duration  # seconds per image in slideshow mode

        if image_paths:
            for path in image_paths:
                img = QImage(path)
                if not img.isNull():
                    self._images.append(img)

    def set_images(self, image_paths: list[str], slide_duration: float = 30.0):
        """Load images from file paths."""
        self._images.clear()
        self._scaled_cache.clear()
        self._slide_duration = slide_duration
        for path in image_paths:
            img = QImage(path)
            if not img.isNull():
                self._images.append(img)

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        if not self._images:
            painter.fillRect(0, 0, width, height, QColor(20, 20, 35))
            return

        # Pick which image to show (slideshow rotation)
        if len(self._images) == 1:
            idx = 0
        else:
            idx = int(time_seconds / self._slide_duration) % len(self._images)

        img = self._images[idx]

        # Cache scaled version per resolution
        cache_key = (idx, width, height)
        if cache_key not in self._scaled_cache:
            scaled = img.scaled(width, height,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation)
            # Center crop to exact size
            x_offset = (scaled.width() - width) // 2
            y_offset = (scaled.height() - height) // 2
            cropped = scaled.copy(x_offset, y_offset, width, height)
            self._scaled_cache[cache_key] = cropped

        painter.drawImage(0, 0, self._scaled_cache[cache_key])

        # Slight dark overlay so text is readable
        painter.fillRect(0, 0, width, height, QColor(0, 0, 0, 60))

        # If slideshow, add crossfade near transitions
        if len(self._images) > 1:
            position_in_slide = time_seconds % self._slide_duration
            fade_duration = 1.0

            if position_in_slide > self._slide_duration - fade_duration:
                # Fade to next image
                next_idx = (idx + 1) % len(self._images)
                next_key = (next_idx, width, height)
                if next_key not in self._scaled_cache:
                    next_img = self._images[next_idx]
                    scaled = next_img.scaled(width, height,
                                             Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation)
                    x_off = (scaled.width() - width) // 2
                    y_off = (scaled.height() - height) // 2
                    self._scaled_cache[next_key] = scaled.copy(x_off, y_off, width, height)

                fade_progress = (position_in_slide - (self._slide_duration - fade_duration)) / fade_duration
                painter.setOpacity(fade_progress)
                painter.drawImage(0, 0, self._scaled_cache[next_key])
                painter.setOpacity(1.0)
                painter.fillRect(0, 0, width, height, QColor(0, 0, 0, 60))


# Need this import for NoPen
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

# Registry of procedural backgrounds
ALL_BACKGROUNDS = [WarmBokeh, Starfield, GradientSweep, Waves, SolidDark]

def get_background(name: str) -> Background:
    for cls in ALL_BACKGROUNDS:
        if cls.name == name:
            return cls()
    return SolidDark()
