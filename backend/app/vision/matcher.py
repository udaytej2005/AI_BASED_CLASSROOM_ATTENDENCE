"""Compare a live embedding with the registered embeddings.

Rules (all parameters come from settings):
- The score for a student is the best cosine similarity over that student's enrolment embeddings.
- If the best score is below ``threshold`` the face is UNKNOWN.
- If the best and second-best *different* students are closer than ``margin`` the result is UNCERTAIN.
  Look-alike students are the typical cause, so an uncertain face is never counted as present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

MatchStatus = Literal["recognized_candidate", "unknown", "uncertain", "no_gallery"]


@dataclass(frozen=True)
class Gallery:
    """Registered embeddings. ``vectors`` are L2-normalised rows; ``owners`` holds the student id of each
    row."""

    vectors: np.ndarray
    owners: np.ndarray

    @classmethod
    def empty(cls, dimension: int = 128) -> Gallery:
        return cls(np.zeros((0, dimension), dtype=np.float32), np.zeros((0,), dtype=np.int64))

    @classmethod
    def from_rows(cls, rows: list[tuple[int, np.ndarray]], dimension: int = 128) -> Gallery:
        if not rows:
            return cls.empty(dimension)
        vectors = np.stack([v.astype(np.float32) for _, v in rows])
        owners = np.array([student_id for student_id, _ in rows], dtype=np.int64)
        return cls(vectors, owners)

    def __len__(self) -> int:
        return int(self.owners.shape[0])


@dataclass(frozen=True)
class MatchResult:
    status: MatchStatus
    student_id: int | None
    score: float
    runner_up_student_id: int | None = None
    runner_up_score: float | None = None


def match(gallery: Gallery, vector: np.ndarray, threshold: float, margin: float) -> MatchResult:
    if len(gallery) == 0:
        return MatchResult("no_gallery", None, 0.0)
    scores = gallery.vectors @ vector.astype(np.float32)
    best_by_student: dict[int, float] = {}
    for owner, score in zip(gallery.owners.tolist(), scores.tolist(), strict=True):
        if owner not in best_by_student or score > best_by_student[owner]:
            best_by_student[owner] = score
    ranked = sorted(best_by_student.items(), key=lambda item: item[1], reverse=True)
    best_id, best = ranked[0]
    if best < threshold:
        return MatchResult("unknown", None, best)
    runner_id, runner = ranked[1] if len(ranked) > 1 else (None, None)
    if runner is not None and best - runner < margin:
        return MatchResult("uncertain", best_id, best, runner_id, runner)
    return MatchResult("recognized_candidate", best_id, best, runner_id, runner)
