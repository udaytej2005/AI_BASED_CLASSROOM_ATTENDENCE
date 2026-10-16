"""One frame through detection, tracking, quality gating and recognition.

Recognition is scheduled per track: a face is embedded when it is new, or when its last recognition is older
than
``recognize_every`` processed frames. This avoids re-running the recogniser on an unchanged, already-known
face.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.vision.backend import FaceBackend
from app.vision.matcher import Gallery, match
from app.vision.quality import QualityPolicy, assess
from app.vision.tracker import IoUTracker
from app.vision.types import Box

STATUSES = ("recognized_candidate", "unknown", "uncertain", "low_quality", "error", "not_checked")


@dataclass(frozen=True)
class TrackReading:
    track_id: int
    box: Box
    detector_score: float
    status: str
    student_id: int | None
    score: float
    recognized_now: bool


@dataclass(frozen=True)
class FrameReport:
    frame_index: int
    timestamp: float
    readings: tuple[TrackReading, ...]

    @property
    def face_count(self) -> int:
        return len(self.readings)


class FramePipeline:
    def __init__(
        self,
        backend: FaceBackend,
        gallery: Gallery,
        *,
        threshold: float,
        margin: float,
        quality: QualityPolicy,
        recognize_every: int = 10,
        tracker: IoUTracker | None = None,
    ) -> None:
        self.backend = backend
        self.gallery = gallery
        self.threshold = threshold
        self.margin = margin
        self.quality = quality
        self.recognize_every = recognize_every
        self.tracker = tracker or IoUTracker()
        self.recognitions_run = 0

    def process(self, frame: np.ndarray, frame_index: int, timestamp: float) -> FrameReport:
        detections = self.backend.detector.detect(frame)
        readings: list[TrackReading] = []
        for track, detection in self.tracker.update(detections, frame_index):
            quality = assess(frame, detection, self.quality)
            if not quality.passed:
                readings.append(
                    TrackReading(
                        track.track_id, detection.box, detection.score, "low_quality", None, 0.0, False
                    )
                )
                continue

            due = track.last_recognized_frame is None or (
                frame_index - track.last_recognized_frame >= self.recognize_every
            )
            if not due:
                readings.append(
                    TrackReading(
                        track.track_id,
                        detection.box,
                        detection.score,
                        track.last_status or "not_checked",
                        track.student_id,
                        track.last_score,
                        False,
                    )
                )
                continue

            try:
                vector = self.backend.embedder.embed(frame, detection)
            except Exception:  # a single bad crop must not stop the whole frame
                readings.append(
                    TrackReading(track.track_id, detection.box, detection.score, "error", None, 0.0, False)
                )
                continue

            self.recognitions_run += 1
            result = match(self.gallery, vector, self.threshold, self.margin)
            track.last_recognized_frame = frame_index
            track.last_status = result.status
            track.last_score = result.score
            track.student_id = result.student_id if result.status == "recognized_candidate" else None
            # Only a clear match is attributed to a student. Uncertain or unknown faces carry no identity.
            attributed = result.student_id if result.status == "recognized_candidate" else None
            readings.append(
                TrackReading(
                    track.track_id,
                    detection.box,
                    detection.score,
                    result.status,
                    attributed,
                    result.score,
                    True,
                )
            )
        return FrameReport(frame_index=frame_index, timestamp=timestamp, readings=tuple(readings))
