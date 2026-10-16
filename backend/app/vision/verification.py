"""Temporal verification: turn repeated, spread-out recognitions into a confirmed (Present) student.

A student is confirmed only when:
- at least ``min_observations`` recognitions were accepted, and
- they span at least ``min_span_seconds``, and
- consecutive accepted observations are at least ``min_gap_seconds`` apart.

The gap rule means that one frame, or several tracks showing the same person in the same moment, cannot
confirm a
student on their own. Once confirmed, a student stays confirmed for the session (no duplicate attendance).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Evidence:
    student_id: int
    observations: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    best_score: float = 0.0
    confirmed_at: float | None = None

    @property
    def span(self) -> float:
        return self.last_seen - self.first_seen


class TemporalVerifier:
    def __init__(self, *, min_observations: int, min_span_seconds: float, min_gap_seconds: float) -> None:
        self.min_observations = min_observations
        self.min_span_seconds = min_span_seconds
        self.min_gap_seconds = min_gap_seconds
        self._evidence: dict[int, Evidence] = {}

    def add(self, student_id: int, timestamp: float, score: float) -> bool:
        """Record one accepted recognition. Returns True when this observation confirms the student."""
        evidence = self._evidence.get(student_id)
        if evidence is None:
            evidence = Evidence(student_id=student_id, first_seen=timestamp, last_seen=timestamp)
            self._evidence[student_id] = evidence
            evidence.observations = 1
        elif timestamp - evidence.last_seen >= self.min_gap_seconds:
            evidence.observations += 1
            evidence.last_seen = timestamp
        else:
            # Too close to the previous observation: keep the best score but do not count it again.
            evidence.best_score = max(evidence.best_score, score)
            return False
        evidence.best_score = max(evidence.best_score, score)
        if (
            evidence.confirmed_at is None
            and evidence.observations >= self.min_observations
            and evidence.span >= self.min_span_seconds
        ):
            evidence.confirmed_at = timestamp
            return True
        return False

    def evidence(self) -> list[Evidence]:
        return sorted(self._evidence.values(), key=lambda e: e.student_id)

    def confirmed_ids(self) -> set[int]:
        return {e.student_id for e in self._evidence.values() if e.confirmed_at is not None}
