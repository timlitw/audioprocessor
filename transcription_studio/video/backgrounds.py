"""Procedural background generators — soothing, cinematic animations."""

import math
import random
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QLinearGradient, QPainterPath, QImage
from PyQt6.QtCore import QPointF, QRectF, Qt


class Background:
    """Base class for procedural backgrounds."""

    name: str = "Base"

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        raise NotImplementedError


class WarmBokeh(Background):
    """Soft, out-of-focus light orbs drifting very slowly with gentle color breathing."""

    name = "Warm Bokeh"

    def __init__(self, num_orbs: int = 40, seed: int = 42):
        rng = random.Random(seed)
        self._orbs = []
        colors = [
            (255, 180, 60),   # amber
            (255, 140, 40),   # deep amber
            (255, 200, 100),  # gold
            (220, 100, 80),   # soft red
            (200, 160, 220),  # soft lavender
            (255, 160, 140),  # soft pink
            (180, 140, 255),  # soft purple
            (255, 220, 180),  # warm cream
        ]
        for _ in range(num_orbs):
            r, g, b = rng.choice(colors)
            self._orbs.append({
                "x": rng.uniform(-0.1, 1.1),
                "y": rng.uniform(-0.1, 1.1),
                "radius": rng.uniform(0.04, 0.15),
                # Slow but visible drift
                "speed_x": rng.uniform(-0.006, 0.006),
                "speed_y": rng.uniform(-0.004, 0.004),
                # Visible breathing pulse
                "pulse_speed": rng.uniform(0.3, 0.7),
                "pulse_phase": rng.uniform(0, math.tau),
                # Visible alpha breathing
                "alpha_base": rng.randint(60, 120),
                "alpha_pulse": rng.randint(15, 40),
                "alpha_speed": rng.uniform(0.2, 0.5),
                "alpha_phase": rng.uniform(0, math.tau),
                "color": (r, g, b),
            })

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        # Slowly shifting background color
        bg_shift = math.sin(time_seconds * 0.02) * 5
        painter.fillRect(0, 0, width, height, QColor(
            int(15 + bg_shift), int(10 + bg_shift * 0.5), int(22 + bg_shift)
        ))

        painter.setPen(Qt.PenStyle.NoPen)

        for orb in self._orbs:
            # Gentle sine wobble adds organic feel to the drift
            wobble_x = math.sin(time_seconds * 0.15 + orb["pulse_phase"]) * 0.02
            wobble_y = math.cos(time_seconds * 0.12 + orb["alpha_phase"]) * 0.015
            x = (orb["x"] + orb["speed_x"] * time_seconds + wobble_x) % 1.3 - 0.15
            y = (orb["y"] + orb["speed_y"] * time_seconds + wobble_y) % 1.3 - 0.15

            # Gentle size breathing
            pulse = 1.0 + 0.15 * math.sin(orb["pulse_speed"] * time_seconds + orb["pulse_phase"])
            radius = orb["radius"] * pulse * min(width, height)

            # Gentle alpha breathing
            alpha = orb["alpha_base"] + int(orb["alpha_pulse"] *
                    math.sin(orb["alpha_speed"] * time_seconds + orb["alpha_phase"]))

            cx = x * width
            cy = y * height
            r, g, b = orb["color"]

            gradient = QRadialGradient(QPointF(cx, cy), radius)
            gradient.setColorAt(0.0, QColor(r, g, b, alpha))
            gradient.setColorAt(0.3, QColor(r, g, b, int(alpha * 0.6)))
            gradient.setColorAt(0.7, QColor(r, g, b, int(alpha * 0.2)))
            gradient.setColorAt(1.0, QColor(r, g, b, 0))

            painter.setBrush(gradient)
            painter.drawEllipse(QPointF(cx, cy), radius, radius)


class Starfield(Background):
    """Gently twinkling stars drifting slowly on deep blue."""

    name = "Starfield"

    def __init__(self, num_stars: int = 180, seed: int = 42):
        rng = random.Random(seed)
        self._stars = []
        for _ in range(num_stars):
            self._stars.append({
                "x": rng.uniform(0, 1),
                "y": rng.uniform(0, 1),
                "size": rng.uniform(0.8, 2.5),
                "speed": rng.uniform(0.0005, 0.003),  # very slow drift
                "brightness": rng.randint(140, 255),
                "twinkle_speed": rng.uniform(0.2, 0.8),
                "twinkle_phase": rng.uniform(0, math.tau),
            })

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        # Slowly shifting deep blue background
        blue_shift = math.sin(time_seconds * 0.015) * 3
        painter.fillRect(0, 0, width, height, QColor(
            int(5 + blue_shift), int(5 + blue_shift), int(18 + blue_shift * 2)
        ))

        painter.setPen(Qt.PenStyle.NoPen)

        for star in self._stars:
            x = (star["x"] + star["speed"] * time_seconds) % 1.0
            y = star["y"]
            b = star["brightness"]

            # Gentle twinkling
            twinkle = 0.6 + 0.4 * math.sin(star["twinkle_speed"] * time_seconds + star["twinkle_phase"])
            alpha = int(b * twinkle)

            # Slight warm tint variation
            tint = math.sin(time_seconds * 0.03 + star["twinkle_phase"]) * 0.1
            r_val = int(min(255, alpha * (1.0 + tint)))
            g_val = int(min(255, alpha * (1.0 + tint * 0.5)))

            color = QColor(r_val, g_val, alpha, alpha)
            size = star["size"] * (0.8 + 0.2 * twinkle)

            # Soft glow around brighter stars
            if b > 200:
                glow_radius = size * 3
                glow = QRadialGradient(QPointF(x * width, y * height), glow_radius)
                glow.setColorAt(0.0, QColor(r_val, g_val, alpha, int(alpha * 0.3)))
                glow.setColorAt(1.0, QColor(r_val, g_val, alpha, 0))
                painter.setBrush(glow)
                painter.drawEllipse(QPointF(x * width, y * height), glow_radius, glow_radius)

            painter.setBrush(color)
            painter.drawEllipse(QPointF(x * width, y * height), size, size)


class GradientSweep(Background):
    """Slowly morphing color gradient — soothing color transitions."""

    name = "Gradient Sweep"

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        # Very slow rotation
        angle = time_seconds * 0.015

        cx, cy = width / 2, height / 2
        r = max(width, height) * 0.8

        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx - r * math.cos(angle)
        y2 = cy - r * math.sin(angle)

        # Colors slowly shift over time
        t = time_seconds * 0.02
        r1 = int(10 + 15 * math.sin(t))
        g1 = int(15 + 10 * math.sin(t + 1.0))
        b1 = int(50 + 20 * math.sin(t + 2.0))

        r2 = int(30 + 20 * math.sin(t + 3.0))
        g2 = int(15 + 15 * math.sin(t + 4.0))
        b2 = int(60 + 25 * math.sin(t + 5.0))

        r3 = int(10 + 10 * math.sin(t + 1.5))
        g3 = int(10 + 8 * math.sin(t + 2.5))
        b3 = int(35 + 15 * math.sin(t + 3.5))

        gradient = QLinearGradient(QPointF(x1, y1), QPointF(x2, y2))
        gradient.setColorAt(0.0, QColor(r1, g1, b1))
        gradient.setColorAt(0.5, QColor(r2, g2, b2))
        gradient.setColorAt(1.0, QColor(r3, g3, b3))

        painter.fillRect(0, 0, width, height, gradient)

        # Add a subtle radial glow in the center
        glow_alpha = int(20 + 10 * math.sin(time_seconds * 0.03))
        center_glow = QRadialGradient(QPointF(cx, cy), max(width, height) * 0.4)
        center_glow.setColorAt(0.0, QColor(60, 40, 80, glow_alpha))
        center_glow.setColorAt(1.0, QColor(60, 40, 80, 0))
        painter.fillRect(0, 0, width, height, center_glow)


class Waves(Background):
    """Gentle ocean waves with slowly shifting colors."""

    name = "Waves"

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        # Slowly shifting dark ocean background
        bg_shift = math.sin(time_seconds * 0.02) * 3
        painter.fillRect(0, 0, width, height, QColor(
            int(8 + bg_shift), int(15 + bg_shift), int(30 + bg_shift * 2)
        ))

        for layer in range(5):
            y_base = height * (0.50 + layer * 0.08)
            amplitude = 15 + layer * 8
            freq = 0.004 - layer * 0.0005
            # Very slow wave motion
            speed = 0.15 + layer * 0.08
            alpha = 35 - layer * 5

            # Color shifts slowly per layer
            color_shift = math.sin(time_seconds * 0.025 + layer * 0.5) * 15

            path = QPainterPath()
            for x in range(0, width + 3, 3):
                y = y_base + amplitude * math.sin(freq * x + speed * time_seconds + layer * 0.7)
                # Add a second harmonic for more organic feel
                y += (amplitude * 0.3) * math.sin(freq * 2.3 * x + speed * 0.7 * time_seconds + layer)
                if x == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            path.lineTo(width, height)
            path.lineTo(0, height)
            path.closeSubpath()

            color = QColor(
                int(25 + layer * 12 + color_shift),
                int(55 + layer * 18 + color_shift * 0.5),
                int(110 + layer * 18 + color_shift),
                alpha,
            )
            painter.fillPath(path, color)


class SolidDark(Background):
    """Plain dark background with very subtle color breathing."""

    name = "Solid Dark"

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        # Very subtle color shift so it doesn't feel dead
        shift = math.sin(time_seconds * 0.015) * 3
        painter.fillRect(0, 0, width, height, QColor(
            int(20 + shift), int(20 + shift * 0.5), int(35 + shift)
        ))


class CustomImage(Background):
    """Static image or slideshow with crossfade transitions."""

    name = "Custom Image"

    def __init__(self, image_paths: list[str] | None = None, slide_duration: float = 30.0):
        self._images: list[QImage] = []
        self._scaled_cache: dict[tuple, QImage] = {}
        self._slide_duration = slide_duration

        if image_paths:
            for path in image_paths:
                img = QImage(path)
                if not img.isNull():
                    self._images.append(img)

    def set_images(self, image_paths: list[str], slide_duration: float = 30.0):
        self._images.clear()
        self._scaled_cache.clear()
        self._slide_duration = slide_duration
        for path in image_paths:
            img = QImage(path)
            if not img.isNull():
                self._images.append(img)

    def _get_scaled(self, idx: int, width: int, height: int) -> QImage:
        cache_key = (idx, width, height)
        if cache_key not in self._scaled_cache:
            img = self._images[idx]
            scaled = img.scaled(width, height,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation)
            x_offset = (scaled.width() - width) // 2
            y_offset = (scaled.height() - height) // 2
            self._scaled_cache[cache_key] = scaled.copy(x_offset, y_offset, width, height)
        return self._scaled_cache[cache_key]

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        if not self._images:
            painter.fillRect(0, 0, width, height, QColor(20, 20, 35))
            return

        if len(self._images) == 1:
            painter.drawImage(0, 0, self._get_scaled(0, width, height))
            painter.fillRect(0, 0, width, height, QColor(0, 0, 0, 50))
            return

        # Slideshow with smooth crossfade
        idx = int(time_seconds / self._slide_duration) % len(self._images)
        next_idx = (idx + 1) % len(self._images)

        position_in_slide = time_seconds % self._slide_duration
        fade_duration = 2.0  # 2 second crossfade

        # Draw current image
        painter.drawImage(0, 0, self._get_scaled(idx, width, height))

        # Crossfade near transition
        if position_in_slide > self._slide_duration - fade_duration:
            fade_progress = (position_in_slide - (self._slide_duration - fade_duration)) / fade_duration
            painter.setOpacity(fade_progress)
            painter.drawImage(0, 0, self._get_scaled(next_idx, width, height))
            painter.setOpacity(1.0)

        # Slight dark overlay for text readability
        painter.fillRect(0, 0, width, height, QColor(0, 0, 0, 50))


class Aurora(Background):
    """Slow-moving curtains of soft color, like northern lights."""

    name = "Aurora"

    def __init__(self, seed: int = 42):
        rng = random.Random(seed)
        self._bands = []
        colors = [
            (40, 180, 120),   # green
            (60, 200, 160),   # teal-green
            (80, 140, 200),   # blue
            (120, 80, 200),   # purple
            (60, 160, 180),   # cyan
            (100, 200, 140),  # mint
        ]
        for i in range(8):
            r, g, b = rng.choice(colors)
            self._bands.append({
                "color": (r, g, b),
                "y_center": rng.uniform(0.15, 0.55),
                "amplitude": rng.uniform(0.03, 0.08),
                "freq": rng.uniform(0.3, 0.8),
                "speed": rng.uniform(0.02, 0.06),
                "phase": rng.uniform(0, math.tau),
                "width": rng.uniform(0.08, 0.18),
                "alpha": rng.randint(30, 70),
            })

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        # Dark background with subtle blue
        bg_b = 18 + int(3 * math.sin(time_seconds * 0.01))
        painter.fillRect(0, 0, width, height, QColor(5, 5, bg_b))

        painter.setPen(Qt.PenStyle.NoPen)

        for band in self._bands:
            r, g, b = band["color"]
            alpha = band["alpha"] + int(15 * math.sin(time_seconds * 0.08 + band["phase"]))

            # Draw the aurora as vertical strips with varying height
            strip_width = max(4, width // 80)
            for sx in range(0, width, strip_width):
                x_frac = sx / width
                # Undulating curtain shape
                wave = math.sin(x_frac * band["freq"] * math.tau + time_seconds * band["speed"] + band["phase"])
                wave2 = math.sin(x_frac * band["freq"] * 1.7 * math.tau + time_seconds * band["speed"] * 0.7 + band["phase"] * 2)

                y_center = band["y_center"] + band["amplitude"] * (wave * 0.7 + wave2 * 0.3)
                band_height = band["width"] * (0.8 + 0.2 * wave)

                y_top = int((y_center - band_height * 0.5) * height)
                y_bot = int((y_center + band_height * 0.5) * height)

                # Vertical gradient — bright at top, fading down
                grad = QLinearGradient(QPointF(sx, y_top), QPointF(sx, y_bot))
                grad.setColorAt(0.0, QColor(r, g, b, int(alpha * 0.3)))
                grad.setColorAt(0.3, QColor(r, g, b, alpha))
                grad.setColorAt(0.6, QColor(r, g, b, int(alpha * 0.7)))
                grad.setColorAt(1.0, QColor(r, g, b, 0))

                painter.setBrush(grad)
                painter.drawRect(sx, y_top, strip_width, y_bot - y_top)

        # Add a few "stars" peeking through
        rng = random.Random(42)
        for _ in range(40):
            sx = rng.uniform(0, 1) * width
            sy = rng.uniform(0, 1) * height
            twinkle = 0.5 + 0.5 * math.sin(time_seconds * rng.uniform(0.3, 0.8) + rng.uniform(0, math.tau))
            sa = int(180 * twinkle)
            painter.setBrush(QColor(255, 255, 240, sa))
            painter.drawEllipse(QPointF(sx, sy), 1.2, 1.2)


class Candlelight(Background):
    """Warm flickering glow that slowly pulses, like a room lit by candles."""

    name = "Candlelight"

    def __init__(self, num_candles: int = 12, seed: int = 42):
        rng = random.Random(seed)
        self._candles = []
        for _ in range(num_candles):
            self._candles.append({
                "x": rng.uniform(0.05, 0.95),
                "y": rng.uniform(0.3, 0.95),
                "radius": rng.uniform(0.15, 0.35),
                "flicker_speed": rng.uniform(1.5, 4.0),
                "flicker_phase": rng.uniform(0, math.tau),
                "flicker2_speed": rng.uniform(3.0, 7.0),
                "flicker2_phase": rng.uniform(0, math.tau),
                "warmth": rng.uniform(0, 1),  # 0=amber, 1=warm white
                "intensity": rng.uniform(0.6, 1.0),
            })

    def render(self, painter: QPainter, width: int, height: int, time_seconds: float):
        # Dark warm background
        bg_r = 18 + int(4 * math.sin(time_seconds * 0.03))
        bg_g = 12 + int(2 * math.sin(time_seconds * 0.025))
        painter.fillRect(0, 0, width, height, QColor(bg_r, bg_g, 8))

        painter.setPen(Qt.PenStyle.NoPen)

        for candle in self._candles:
            # Flickering intensity — combines slow pulse with fast flicker
            slow = math.sin(candle["flicker_speed"] * time_seconds + candle["flicker_phase"])
            fast = math.sin(candle["flicker2_speed"] * time_seconds + candle["flicker2_phase"])
            flicker = 0.7 + 0.2 * slow + 0.1 * fast
            flicker *= candle["intensity"]

            # Color based on warmth — amber to warm white
            w = candle["warmth"]
            r = int(255 * flicker)
            g = int((140 + 80 * w) * flicker)
            b = int((30 + 50 * w) * flicker)
            alpha = int(90 * flicker)

            cx = candle["x"] * width
            cy = candle["y"] * height
            radius = candle["radius"] * min(width, height) * (0.95 + 0.05 * slow)

            # Soft radial glow
            grad = QRadialGradient(QPointF(cx, cy), radius)
            grad.setColorAt(0.0, QColor(r, g, b, alpha))
            grad.setColorAt(0.2, QColor(r, g, b, int(alpha * 0.7)))
            grad.setColorAt(0.5, QColor(r, g, int(b * 0.5), int(alpha * 0.3)))
            grad.setColorAt(1.0, QColor(r // 3, g // 4, 0, 0))

            painter.setBrush(grad)
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Subtle overall warm wash at the top (like light rising)
        top_wash = QLinearGradient(QPointF(width / 2, 0), QPointF(width / 2, height * 0.5))
        warm_alpha = int(20 + 8 * math.sin(time_seconds * 0.05))
        top_wash.setColorAt(0.0, QColor(255, 180, 60, warm_alpha))
        top_wash.setColorAt(1.0, QColor(255, 140, 30, 0))
        painter.setBrush(top_wash)
        painter.drawRect(0, 0, width, int(height * 0.5))


# Registry of procedural backgrounds
ALL_BACKGROUNDS = [Aurora, Candlelight, Starfield, GradientSweep, Waves, SolidDark]

def get_background(name: str) -> Background:
    for cls in ALL_BACKGROUNDS:
        if cls.name == name:
            return cls()
    return SolidDark()
