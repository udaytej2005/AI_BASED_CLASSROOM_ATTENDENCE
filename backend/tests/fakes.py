"""Synthetic stand-ins for the face models, used by tests.

They are NOT face recognisers. A "photo" is a generated image in which each face is a textured square whose
identity, sharpness, brightness and tilt are written into a few marker pixels. The fake detector reads those
markers
and the fake embedder maps an identity to a fixed unit vector. This lets the real quality, matching, tracking
and
verification code run deterministically without any real person's image. It says nothing about real accuracy.
"""

from __future__ import annotations

import numpy as np

from app.vision.types import Box, Detection

FACE = 100
SLOT_X = 20
SLOT_STRIDE = 120
DIM = 128


def face_origin(slot: int) -> tuple[int, int]:
    return SLOT_X + slot * SLOT_STRIDE, 20


def make_photo(faces: list[dict[str, object]], height: int = 240, width: int = 640) -> np.ndarray:
    """Build a photo. Each face dict: identity (int), variant (int), optional blur, dark, tilt, low_score
    (bool)."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    for slot, face in enumerate(faces):
        x, y = face_origin(slot)
        identity = int(face["identity"])  # type: ignore[arg-type]
        variant = int(face.get("variant", 0))  # type: ignore[arg-type]
        rng = np.random.default_rng(identity * 1000 + variant + 7)
        if face.get("blur"):
            region = np.full((FACE, FACE, 3), 120, dtype=np.int16) + rng.integers(0, 2, (FACE, FACE, 3))
        elif face.get("dark"):
            region = rng.integers(5, 30, (FACE, FACE, 3))
        else:
            region = rng.integers(60, 190, (FACE, FACE, 3))
        frame[y : y + FACE, x : x + FACE] = np.clip(region, 0, 255).astype(np.uint8)
        # Marker row 0: present flag, identity, variant. Row 1: flags for blur, low score, tilt, dark.
        base = slot * 3
        frame[0, base, 0] = 1
        frame[0, base + 1, 0] = identity
        frame[0, base + 2, 0] = variant
        frame[1, base, 0] = 1 if face.get("blur") else 0
        frame[1, base + 1, 0] = 1 if face.get("low_score") else 0
        frame[1, base + 2, 0] = 1 if face.get("tilt") else 0
        frame[2, base, 0] = 1 if face.get("dark") else 0
    return frame


class FakeDetector:
    name = "fake-detector"
    version = "test"

    def detect(self, frame: np.ndarray) -> list[Detection]:
        detections: list[Detection] = []
        for slot in range(5):
            base = slot * 3
            if frame[0, base, 0] != 1:
                continue
            x, y = face_origin(slot)
            low_score = frame[1, base + 1, 0] == 1
            tilt = frame[1, base + 2, 0] == 1
            right_eye = (x + 30.0, y + 40.0)
            left_eye = (x + 70.0, y + 40.0 + (40.0 if tilt else 0.0))
            detections.append(
                Detection(
                    box=Box(float(x), float(y), float(FACE), float(FACE)),
                    score=0.6 if low_score else 0.97,
                    landmarks=(
                        right_eye,
                        left_eye,
                        (x + 50.0, y + 60.0),
                        (x + 35.0, y + 80.0),
                        (x + 65.0, y + 80.0),
                    ),
                )
            )
        return detections


def identity_vector(identity: int, variant: int = 0, base_of: dict[int, int] | None = None) -> np.ndarray:
    """Unit vector for an identity. ``base_of`` makes one identity a near-twin of another (for look-alike
    tests)."""
    source = identity if not base_of or identity not in base_of else base_of[identity]
    base = np.random.default_rng(source + 90_000).standard_normal(DIM)
    if source != identity:
        base = base + 0.02 * np.random.default_rng(identity + 91_000).standard_normal(DIM)
    if variant:
        base = base + 0.05 * np.random.default_rng(identity * 37 + variant).standard_normal(DIM)
    return (base / np.linalg.norm(base)).astype(np.float32)


class FakeEmbedder:
    name = "fake-embedder"
    version = "test"
    dimension = DIM

    def __init__(self, twins: dict[int, int] | None = None) -> None:
        self.twins = twins or {}

    def embed(self, frame: np.ndarray, detection: Detection) -> np.ndarray:
        slot = self._slot_of(detection)
        base = slot * 3
        identity = int(frame[0, base + 1, 0])
        variant = int(frame[0, base + 2, 0])
        return identity_vector(identity, variant, self.twins)

    @staticmethod
    def _slot_of(detection: Detection) -> int:
        return int(round((detection.box.x - SLOT_X) / SLOT_STRIDE))


class FakeBackend:
    name = "fake-embedder"
    version = "test"

    def __init__(self, twins: dict[int, int] | None = None) -> None:
        self.detector = FakeDetector()
        self.embedder = FakeEmbedder(twins)

    @property
    def model_name(self) -> str:
        return self.embedder.name

    @property
    def model_version(self) -> str:
        return self.embedder.version


def encode_png(frame: np.ndarray) -> bytes:
    import cv2

    ok, buffer = cv2.imencode(".png", frame)
    assert ok
    return bytes(buffer)
