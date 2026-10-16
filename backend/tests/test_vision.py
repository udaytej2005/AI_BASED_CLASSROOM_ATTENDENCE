"""Vision logic tests. They use synthetic frames and the fake backend in tests/fakes.py.

These tests check the decision logic (gates, matching, tracking, verification, scheduling). They do NOT
measure
face-recognition accuracy. Accuracy needs a separate, consented test set and is not claimed anywhere in this
repo.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.vision import backend as backend_module
from app.vision.backend import BackendUnavailable, backend_status, load_opencv_backend
from app.vision.matcher import Gallery, match
from app.vision.pipeline import FramePipeline
from app.vision.quality import QualityPolicy, assess
from app.vision.tracker import IoUTracker
from app.vision.types import Box, Detection
from app.vision.verification import TemporalVerifier
from tests.fakes import FakeBackend, FakeDetector, identity_vector, make_photo

POLICY = QualityPolicy(
    min_face_px=80, min_detector_score=0.85, min_sharpness=60.0, brightness_min=50, brightness_max=215
)


def _det(x: float = 20, y: float = 20, size: float = 100, score: float = 0.97) -> Detection:
    return Detection(box=Box(x, y, size, size), score=score, landmarks=((x + 30, y + 40), (x + 70, y + 40)))


# --- quality gates ------------------------------------------------------------


def test_good_face_passes_all_gates():
    frame = make_photo([{"identity": 1}])
    report = assess(frame, FakeDetector().detect(frame)[0], POLICY)
    assert report.passed, report.reasons


@pytest.mark.parametrize(
    ("face", "expected_reason"),
    [
        ({"identity": 1, "blur": True}, "blurred"),
        ({"identity": 1, "dark": True}, "too dark"),
        ({"identity": 1, "tilt": True}, "tilted"),
        ({"identity": 1, "low_score": True}, "confidence"),
    ],
)
def test_each_quality_gate_rejects_with_a_reason(face, expected_reason):
    frame = make_photo([face])
    report = assess(frame, FakeDetector().detect(frame)[0], POLICY)
    assert not report.passed
    assert any(expected_reason in reason for reason in report.reasons), report.reasons


def test_small_face_is_rejected():
    frame = make_photo([{"identity": 1}])
    small = Detection(box=Box(20, 20, 60, 60), score=0.97, landmarks=())
    report = assess(frame, small, POLICY)
    assert not report.passed
    assert any("too small" in reason for reason in report.reasons)


def test_too_bright_is_rejected():
    frame = np.full((240, 640, 3), 245, dtype=np.uint8)
    frame[20:120, 20:120] = np.random.default_rng(3).integers(230, 255, (100, 100, 3)).astype(np.uint8)
    report = assess(frame, _det(), POLICY)
    assert any("too bright" in reason for reason in report.reasons)


# --- matcher ------------------------------------------------------------------


def _gallery(*pairs: tuple[int, int, int]) -> Gallery:
    """(student_id, identity, variant) triples -> gallery rows."""
    return Gallery.from_rows([(sid, identity_vector(ident, var)) for sid, ident, var in pairs])


def test_empty_gallery_reports_no_gallery():
    result = match(Gallery.empty(), identity_vector(1), threshold=0.363, margin=0.05)
    assert result.status == "no_gallery"
    assert result.student_id is None


def test_known_face_is_recognised_candidate():
    gallery = _gallery((10, 1, 0), (11, 2, 0))
    result = match(gallery, identity_vector(1, variant=2), threshold=0.363, margin=0.05)
    assert result.status == "recognized_candidate"
    assert result.student_id == 10
    assert result.score > 0.9


def test_stranger_is_unknown_not_matched():
    gallery = _gallery((10, 1, 0), (11, 2, 0))
    result = match(gallery, identity_vector(99), threshold=0.363, margin=0.05)
    assert result.status == "unknown"
    assert result.student_id is None


def test_look_alike_within_margin_is_uncertain():
    # Student 21's enrolment vector is a near-duplicate of student 20's, so both score almost the same.
    twin = identity_vector(20) + 0.01 * np.random.default_rng(5).standard_normal(128).astype(np.float32)
    twin = (twin / np.linalg.norm(twin)).astype(np.float32)
    gallery = Gallery.from_rows([(20, identity_vector(20)), (21, twin)])
    probe = identity_vector(20)
    result = match(gallery, probe, threshold=0.363, margin=0.05)
    assert result.status == "uncertain"
    assert result.student_id == 20
    assert result.runner_up_student_id == 21


def test_best_score_per_student_is_used_for_multiple_enrolment_images():
    gallery = _gallery((10, 1, 0), (10, 1, 3), (11, 2, 0))
    result = match(gallery, identity_vector(1, variant=3), threshold=0.363, margin=0.05)
    assert result.student_id == 10
    assert result.runner_up_student_id == 11


# --- tracker ------------------------------------------------------------------


def test_tracker_keeps_id_for_a_moving_face_and_issues_new_id_for_new_face():
    tracker = IoUTracker(iou_threshold=0.3, max_missing_frames=3)
    first = tracker.update([_det(20, 20)], frame_index=0)
    moved = tracker.update([_det(26, 22)], frame_index=1)
    assert first[0][0].track_id == moved[0][0].track_id
    other = tracker.update([_det(20, 20), _det(300, 20)], frame_index=2)
    ids = {track.track_id for track, _ in other}
    assert len(ids) == 2


def test_track_is_dropped_after_max_missing_frames_and_returns_as_new_track():
    tracker = IoUTracker(iou_threshold=0.3, max_missing_frames=2)
    original = tracker.update([_det()], frame_index=0)[0][0].track_id
    for index in range(1, 5):
        tracker.update([], frame_index=index)
    returned = tracker.update([_det()], frame_index=5)[0][0].track_id
    assert returned != original


# --- temporal verification ----------------------------------------------------


def _verifier() -> TemporalVerifier:
    return TemporalVerifier(min_observations=5, min_span_seconds=2.0, min_gap_seconds=0.4)


def test_one_observation_never_confirms():
    verifier = _verifier()
    assert verifier.add(1, 0.0, 0.9) is False
    assert verifier.confirmed_ids() == set()


def test_repeated_observations_in_the_same_instant_do_not_confirm():
    verifier = _verifier()
    for _ in range(10):
        verifier.add(1, 5.0, 0.9)  # several tracks showing one person at one moment
    assert verifier.confirmed_ids() == set()


def test_spread_out_observations_confirm_once():
    verifier = _verifier()
    confirmations = [verifier.add(7, t * 0.5, 0.8) for t in range(8)]
    assert confirmations.count(True) == 1
    assert verifier.confirmed_ids() == {7}


def test_observations_spanning_too_short_a_time_do_not_confirm():
    verifier = _verifier()
    for index in range(6):
        verifier.add(3, index * 0.45, 0.8)  # the 6th observation (span 2.25 s) is the one that confirms
    assert verifier.confirmed_ids() == {3}
    short = _verifier()
    for index in range(5):
        short.add(4, index * 0.41, 0.8)  # span of 1.64 s, under 2.0 s
    assert short.confirmed_ids() == set()


# --- pipeline -----------------------------------------------------------------


def _pipeline(backend: FakeBackend, gallery: Gallery, recognize_every: int = 10) -> FramePipeline:
    return FramePipeline(
        backend,  # type: ignore[arg-type]
        gallery,
        threshold=0.363,
        margin=0.05,
        quality=POLICY,
        recognize_every=recognize_every,
    )


def test_pipeline_recognises_enrolled_student_and_marks_stranger_unknown():
    backend = FakeBackend()
    gallery = _gallery((10, 1, 0))
    report = _pipeline(backend, gallery).process(
        make_photo([{"identity": 1, "variant": 4}, {"identity": 9}]), 0, 0.0
    )
    statuses = {reading.box.x: reading.status for reading in report.readings}
    assert statuses == {20.0: "recognized_candidate", 140.0: "unknown"}


def test_pipeline_flags_low_quality_face_without_recognising_it():
    backend = FakeBackend()
    pipe = _pipeline(backend, _gallery((10, 1, 0)))
    report = pipe.process(make_photo([{"identity": 1, "blur": True}]), 0, 0.0)
    assert report.readings[0].status == "low_quality"
    assert pipe.recognitions_run == 0


def test_pipeline_does_not_recognise_the_same_track_every_frame():
    backend = FakeBackend()
    pipe = _pipeline(backend, _gallery((10, 1, 0)), recognize_every=10)
    photo = make_photo([{"identity": 1}])
    for index in range(6):
        pipe.process(photo, index, index * 0.2)
    assert pipe.recognitions_run == 1  # new track once, then cached until 10 frames have passed
    for index in range(6, 12):
        pipe.process(photo, index, index * 0.2)
    assert pipe.recognitions_run == 2


def test_pipeline_reports_uncertain_for_look_alike_and_never_recognised():
    twins = {2: 1}  # identity 2 is a near-copy of identity 1
    backend = FakeBackend(twins=twins)
    gallery = Gallery.from_rows([(10, identity_vector(1)), (11, identity_vector(2, base_of=twins))])
    report = _pipeline(backend, gallery).process(make_photo([{"identity": 1}]), 0, 0.0)
    assert report.readings[0].status == "uncertain"
    assert report.readings[0].student_id is None


# --- backend loading ----------------------------------------------------------


def test_missing_model_files_are_reported_by_name_only(monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.setenv("FACE_DETECTOR_MODEL_PATH", str(tmp_path / "missing_detector.onnx"))
    monkeypatch.setenv("FACE_RECOGNIZER_MODEL_PATH", str(tmp_path / "missing_recognizer.onnx"))
    get_settings.cache_clear()
    try:
        with pytest.raises(BackendUnavailable) as info:
            load_opencv_backend()
        assert "missing_detector.onnx" in str(info.value)
        assert str(tmp_path) not in str(info.value)  # no absolute server paths in messages
        status = backend_status()
        assert status["status"] == "not_configured"
        assert "missing_detector.onnx" in status["missing"]
    finally:
        get_settings.cache_clear()


def test_backend_status_has_no_absolute_paths():
    status = backend_module.backend_status()
    assert all("/" not in value for value in status.values())


def test_fake_backend_is_detected_as_not_a_real_model():
    assert FakeBackend().model_name == "fake-embedder"
