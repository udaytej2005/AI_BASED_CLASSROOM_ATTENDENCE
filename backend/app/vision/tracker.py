"""Greedy IoU tracker: keeps a stable track id for a face across consecutive frames.

A track that is re-detected in the next frame keeps its identity, so the same person does not generate new
attendance observations just because the detector fired again. Tracks that stay unseen for too long are
dropped,
so a student who leaves and returns is seen as a new track (and is matched again, not duplicated).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.vision.types import Box, Detection


@dataclass
class Track:
    track_id: int
    box: Box
    first_frame: int
    last_frame: int
    hits: int = 1
    last_recognized_frame: int | None = None
    student_id: int | None = None
    last_status: str | None = None
    last_score: float = 0.0


class IoUTracker:
    def __init__(self, iou_threshold: float = 0.3, max_missing_frames: int = 15) -> None:
        self.iou_threshold = iou_threshold
        self.max_missing_frames = max_missing_frames
        self._tracks: list[Track] = []
        self._next_id = 1

    @property
    def tracks(self) -> list[Track]:
        return list(self._tracks)

    def update(self, detections: list[Detection], frame_index: int) -> list[tuple[Track, Detection]]:
        candidates: list[tuple[float, int, int]] = []
        for t_index, track in enumerate(self._tracks):
            for d_index, detection in enumerate(detections):
                overlap = track.box.iou(detection.box)
                if overlap >= self.iou_threshold:
                    candidates.append((overlap, t_index, d_index))
        candidates.sort(reverse=True)

        used_tracks: set[int] = set()
        used_detections: set[int] = set()
        pairs: list[tuple[Track, Detection]] = []
        for _, t_index, d_index in candidates:
            if t_index in used_tracks or d_index in used_detections:
                continue
            used_tracks.add(t_index)
            used_detections.add(d_index)
            track = self._tracks[t_index]
            track.box = detections[d_index].box
            track.last_frame = frame_index
            track.hits += 1
            pairs.append((track, detections[d_index]))

        for d_index, detection in enumerate(detections):
            if d_index in used_detections:
                continue
            track = Track(
                track_id=self._next_id, box=detection.box, first_frame=frame_index, last_frame=frame_index
            )
            self._next_id += 1
            self._tracks.append(track)
            pairs.append((track, detection))

        self._tracks = [t for t in self._tracks if frame_index - t.last_frame <= self.max_missing_frames]
        return pairs
