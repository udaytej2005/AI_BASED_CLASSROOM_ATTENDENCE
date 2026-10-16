"""Face-model adapters.

``FaceDetector`` and ``FaceEmbedder`` are small protocols. ``OpenCVFaceBackend`` implements them with OpenCV's
YuNet detector and SFace recogniser (ONNX files, see docs/face-recognition.md). Tests use a fake backend.

Licences: the *code* in OpenCV is Apache-2.0. The model files are declared by OpenCV Zoo as Apache-2.0
(SFace) and MIT
(YuNet); the training-data terms behind SFace are NOT verified in this project. Model files are never
committed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from app.core.config import Settings, get_settings
from app.vision.types import Box, Detection

REPO_ROOT = Path(__file__).resolve().parents[3]


class BackendUnavailable(RuntimeError):
    """Raised when a model file is missing or OpenCV cannot load it. The message names the missing file."""


class FaceDetector(Protocol):
    name: str
    version: str

    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class FaceEmbedder(Protocol):
    name: str
    version: str
    dimension: int

    def embed(self, frame: np.ndarray, detection: Detection) -> np.ndarray:
        """Return an L2-normalised embedding of the aligned face."""
        ...


@dataclass(frozen=True)
class FaceBackend:
    detector: FaceDetector
    embedder: FaceEmbedder

    @property
    def model_name(self) -> str:
        return self.embedder.name

    @property
    def model_version(self) -> str:
        return self.embedder.version


def resolve_model_path(configured: str) -> Path:
    path = Path(configured)
    return path if path.is_absolute() else REPO_ROOT / path


class OpenCVYuNetDetector:
    name = "opencv-yunet"
    version = "2023mar"

    def __init__(self, model_path: Path, score_threshold: float = 0.6) -> None:
        import cv2

        self._cv2 = cv2
        self._detector = cv2.FaceDetectorYN.create(
            str(model_path), "", (320, 320), score_threshold, 0.3, 5000
        )

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(frame)
        if faces is None:
            return []
        detections: list[Detection] = []
        for row in faces:
            values = tuple(float(v) for v in row)
            landmarks = tuple((values[i], values[i + 1]) for i in range(4, 14, 2))
            detections.append(
                Detection(
                    box=Box(values[0], values[1], values[2], values[3]),
                    score=values[14],
                    landmarks=landmarks,
                    row=values,
                )
            )
        return detections


class OpenCVSFaceEmbedder:
    name = "opencv-sface"
    version = "2021dec"
    dimension = 128

    def __init__(self, model_path: Path) -> None:
        import cv2

        self._cv2 = cv2
        self._recognizer = cv2.FaceRecognizerSF.create(str(model_path), "")

    def embed(self, frame: np.ndarray, detection: Detection) -> np.ndarray:
        row = np.array(detection.row, dtype=np.float32)
        aligned = self._recognizer.alignCrop(frame, row)
        feature = self._recognizer.feature(aligned).astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(feature))
        return feature / norm if norm > 0 else feature


def load_opencv_backend(settings: Settings | None = None) -> FaceBackend:
    """Load the configured ONNX models. Raises BackendUnavailable with the missing path if they are not
    installed."""
    settings = settings or get_settings()
    detector_path = resolve_model_path(settings.face_detector_model_path)
    recognizer_path = resolve_model_path(settings.face_recognizer_model_path)
    for path in (detector_path, recognizer_path):
        if not path.is_file():
            raise BackendUnavailable(
                f"Face model file not found: {path.name}. "
                "Download it as described in docs/face-recognition.md."
            )
    try:
        return FaceBackend(
            detector=OpenCVYuNetDetector(detector_path),
            embedder=OpenCVSFaceEmbedder(recognizer_path),
        )
    except Exception as exc:  # OpenCV raises cv2.error for corrupt or incompatible files
        raise BackendUnavailable(f"Face model could not be loaded: {type(exc).__name__}") from exc


_cached: FaceBackend | None = None


def get_backend() -> FaceBackend:
    """Process-wide backend, loaded on first use. Tests replace this function."""
    global _cached
    if _cached is None:
        _cached = load_opencv_backend()
    return _cached


def backend_status() -> dict[str, str]:
    """Non-sensitive status for the server dashboard: whether the model files are present."""
    settings = get_settings()
    detector_path = resolve_model_path(settings.face_detector_model_path)
    recognizer_path = resolve_model_path(settings.face_recognizer_model_path)
    if detector_path.is_file() and recognizer_path.is_file():
        return {"status": "ready", "detector": detector_path.name, "recognizer": recognizer_path.name}
    missing = [p.name for p in (detector_path, recognizer_path) if not p.is_file()]
    return {"status": "not_configured", "missing": ", ".join(missing)}
