"""Plain data types shared by the vision stages."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Box:
    """Axis-aligned rectangle in pixels: top-left corner plus width and height."""

    x: float
    y: float
    w: float
    h: float

    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)

    def iou(self, other: Box) -> float:
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.x + self.w, other.x + other.w)
        bottom = min(self.y + self.h, other.y + other.h)
        inter = max(0.0, right - left) * max(0.0, bottom - top)
        union = self.area() + other.area() - inter
        return inter / union if union > 0 else 0.0


@dataclass(frozen=True)
class Detection:
    """One face found in a frame.

    ``row`` keeps the detector's raw output (box, five landmarks, score) so that the recogniser can align the
    face.
    Landmarks are (right eye, left eye, nose, right mouth corner, left mouth corner) in pixels.
    """

    box: Box
    score: float
    landmarks: tuple[tuple[float, float], ...] = ()
    row: tuple[float, ...] = field(default=(), compare=False)
