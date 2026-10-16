"""Per-face quality gates used at enrollment and during live recognition.

The thresholds come from settings and are conservative defaults, not validated values. They reject faces that
are too small, too blurry, too dark or too bright, or whose eyes are strongly tilted (large roll).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.vision.types import Detection


@dataclass(frozen=True)
class QualityPolicy:
    min_face_px: int = 80
    min_detector_score: float = 0.85
    min_sharpness: float = 60.0
    brightness_min: int = 50
    brightness_max: int = 215
    max_roll_ratio: float = 0.35


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    reasons: tuple[str, ...] = field(default=())
    face_px: int = 0
    sharpness: float = 0.0
    brightness: float = 0.0


def _crop(frame: np.ndarray, detection: Detection) -> np.ndarray:
    height, width = frame.shape[:2]
    x0 = max(0, int(detection.box.x))
    y0 = max(0, int(detection.box.y))
    x1 = min(width, int(detection.box.x + detection.box.w))
    y1 = min(height, int(detection.box.y + detection.box.h))
    return frame[y0:y1, x0:x1]


def _gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.float32)
    return (0.114 * image[..., 0] + 0.587 * image[..., 1] + 0.299 * image[..., 2]).astype(np.float32)


def _laplacian_variance(gray: np.ndarray) -> float:
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    lap = -4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
    return float(lap.var())


def assess(frame: np.ndarray, detection: Detection, policy: QualityPolicy) -> QualityReport:
    crop = _crop(frame, detection)
    reasons: list[str] = []
    face_px = int(min(detection.box.w, detection.box.h))
    if face_px < policy.min_face_px:
        reasons.append(f"face too small ({face_px}px, need {policy.min_face_px}px)")
    if detection.score < policy.min_detector_score:
        reasons.append("detector confidence too low")
    if crop.size == 0:
        return QualityReport(False, tuple(reasons + ["face outside the frame"]), face_px, 0.0, 0.0)

    gray = _gray(crop)
    sharpness = _laplacian_variance(gray)
    brightness = float(gray.mean())
    if sharpness < policy.min_sharpness:
        reasons.append("image is blurred")
    if brightness < policy.brightness_min:
        reasons.append("too dark")
    if brightness > policy.brightness_max:
        reasons.append("too bright")
    if len(detection.landmarks) >= 2:
        (rx, ry), (lx, ly) = detection.landmarks[0], detection.landmarks[1]
        eye_span = max(1e-6, abs(lx - rx))
        if abs(ly - ry) / eye_span > policy.max_roll_ratio:
            reasons.append("head is tilted too far")
    return QualityReport(not reasons, tuple(reasons), face_px, round(sharpness, 2), round(brightness, 2))
