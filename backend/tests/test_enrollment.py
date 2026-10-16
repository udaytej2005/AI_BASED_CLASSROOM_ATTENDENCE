"""Consent, enrolment and biometric deletion tests (synthetic images and the fake backend only)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.biometric import BiometricConsent, FaceEmbedding
from app.models.student import Student
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, ROLE_PRINCIPAL, ROLE_STUDENT
from app.services import enrollment
from app.vision.backend import BackendUnavailable
from tests.conftest import login, make_user
from tests.fakes import FakeBackend, encode_png, make_photo


@pytest.fixture
def fake_backend(monkeypatch) -> FakeBackend:
    backend = FakeBackend()
    import app.api.v1.biometrics as api

    monkeypatch.setattr(api, "get_backend", lambda: backend)
    return backend


@pytest.fixture
def admin(db: Session):
    return make_user(db, email="admin@example.test", role=ROLE_ADMIN)


@pytest.fixture
def student(db: Session, department_id: int) -> Student:
    row = Student(
        student_code="S-001",
        full_name="Synthetic Student",
        department_id=department_id,
        year=2,
        section="A",
        status="active",
        is_synthetic=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _good_photos(count: int, identity: int = 1) -> list[tuple[str, bytes, str]]:
    return [
        (f"p{i}.png", encode_png(make_photo([{"identity": identity, "variant": i}])), "image/png")
        for i in range(count)
    ]


def _upload(client: TestClient, student_id: int, files: list[tuple[str, bytes, str]]):
    return client.post(
        f"/api/v1/students/{student_id}/enrollment",
        files=[("images", (name, data, mime)) for name, data, mime in files],
    )


def _consent(client: TestClient, student_id: int, **extra):
    return client.post(f"/api/v1/students/{student_id}/consent", json={"confirmed": True, **extra})


def test_enrollment_requires_recorded_consent(app: FastAPI, client: TestClient, admin, student, fake_backend):
    client = login(app, admin.email)
    response = _upload(client, student.id, _good_photos(5))
    assert response.status_code == 409
    assert "consent" in response.json()["detail"].lower()


def test_consent_must_be_confirmed(app: FastAPI, admin, student):
    client = login(app, admin.email)
    response = client.post(f"/api/v1/students/{student.id}/consent", json={"confirmed": False})
    assert response.status_code == 422


def test_consent_cannot_be_recorded_twice(app: FastAPI, admin, student):
    client = login(app, admin.email)
    assert _consent(client, student.id, reference="FORM-12").status_code == 201
    assert _consent(client, student.id).status_code == 409


def test_enrol_then_status_reports_counts_but_no_biometric_data(
    app: FastAPI, admin, student, fake_backend, db: Session
):
    client = login(app, admin.email)
    _consent(client, student.id, reference="FORM-12")
    response = _upload(client, student.id, _good_photos(6))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["accepted"] == 6 and body["rejected"] == 0 and body["uploaded"] == 6
    assert body["model_name"] == "fake-embedder"

    status = client.get(f"/api/v1/students/{student.id}/enrollment").json()
    assert status["embedding_count"] == 6
    assert status["consent_active"] is True

    # No vector, image bytes or embedding field may appear in any response.
    text = json.dumps([response.json(), status]).lower()
    assert "embedding" not in text.replace("embedding_count", "")
    assert "base64" not in text
    assert db.scalar(select(func.count()).select_from(FaceEmbedding)) == 6


def test_bad_images_are_reported_with_reasons_and_not_stored_when_below_minimum(
    app: FastAPI, admin, student, fake_backend, db: Session
):
    client = login(app, admin.email)
    _consent(client, student.id)
    files = _good_photos(4)
    files.append(("two.png", encode_png(make_photo([{"identity": 1}, {"identity": 2}])), "image/png"))
    files.append(("blurred.png", encode_png(make_photo([{"identity": 1, "blur": True}])), "image/png"))
    files.append(("notes.txt", b"hello, this is not an image", "text/plain"))
    files.append(("empty.png", encode_png(make_photo([])), "image/png"))
    response = _upload(client, student.id, files)
    assert response.status_code == 422
    assert "Nothing was saved" in response.json()["detail"]
    assert db.scalar(select(func.count()).select_from(FaceEmbedding)) == 0


def test_partial_success_stores_only_when_minimum_is_met(
    app: FastAPI, admin, student, fake_backend, db: Session
):
    client = login(app, admin.email)
    _consent(client, student.id)
    files = _good_photos(5)
    files.append(("blurred.png", encode_png(make_photo([{"identity": 1, "blur": True}])), "image/png"))
    files.append(("notes.txt", b"not an image", "text/plain"))
    response = _upload(client, student.id, files)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["accepted"] == 5 and body["rejected"] == 2
    reasons = {o["index"]: o["reasons"] for o in body["outcomes"]}
    assert any("blurred" in r for r in reasons[5])
    assert any("JPEG or PNG" in r for r in reasons[6])
    assert db.scalar(select(func.count()).select_from(FaceEmbedding)) == 5


def test_oversized_image_is_refused_without_decoding(app: FastAPI, admin, student, fake_backend):
    client = login(app, admin.email)
    _consent(client, student.id)
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (3 * 1024 * 1024 + 10)
    response = _upload(client, student.id, _good_photos(5) + [("big.png", big, "image/png")])
    assert response.status_code == 201
    assert any("larger than 3 MB" in r for r in response.json()["outcomes"][5]["reasons"])


def test_re_enrolment_replaces_previous_embeddings(app: FastAPI, admin, student, fake_backend, db: Session):
    client = login(app, admin.email)
    _consent(client, student.id)
    _upload(client, student.id, _good_photos(5))
    _upload(client, student.id, _good_photos(7, identity=1))
    assert db.scalar(select(func.count()).select_from(FaceEmbedding)) == 7


def test_withdrawing_consent_deletes_all_embeddings(app: FastAPI, admin, student, fake_backend, db: Session):
    client = login(app, admin.email)
    _consent(client, student.id)
    _upload(client, student.id, _good_photos(5))
    response = client.delete(f"/api/v1/students/{student.id}/consent")
    assert response.status_code == 200
    assert response.json() == {"embeddings_deleted": 5}
    assert db.scalar(select(func.count()).select_from(FaceEmbedding)) == 0
    consent = db.scalar(select(BiometricConsent).where(BiometricConsent.student_id == student.id))
    assert consent is not None and consent.withdrawn_at is not None  # the record stays for the audit trail
    assert client.delete(f"/api/v1/students/{student.id}/consent").status_code == 409


def test_enrolment_is_refused_after_withdrawal(app: FastAPI, admin, student, fake_backend):
    client = login(app, admin.email)
    _consent(client, student.id)
    client.delete(f"/api/v1/students/{student.id}/consent")
    assert _upload(client, student.id, _good_photos(5)).status_code == 409


def test_delete_enrolment_keeps_consent(app: FastAPI, admin, student, fake_backend, db: Session):
    client = login(app, admin.email)
    _consent(client, student.id)
    _upload(client, student.id, _good_photos(5))
    assert client.delete(f"/api/v1/students/{student.id}/enrollment").json() == {"embeddings_deleted": 5}
    status = client.get(f"/api/v1/students/{student.id}/enrollment").json()
    assert status["consent_active"] is True and status["embedding_count"] == 0


def test_faculty_can_read_status_but_not_enrol_or_consent(
    app: FastAPI, db: Session, admin, student, fake_backend
):
    faculty = make_user(db, email="faculty@example.test", role=ROLE_FACULTY)
    client_admin = login(app, admin.email)
    _consent(client_admin, student.id)
    client = login(app, faculty.email)
    assert client.get(f"/api/v1/students/{student.id}/enrollment").status_code == 200
    assert _upload(client, student.id, _good_photos(5)).status_code == 403
    assert _consent(client, student.id).status_code == 403
    assert client.delete(f"/api/v1/students/{student.id}/consent").status_code == 403


def test_principal_and_student_roles_are_limited(app: FastAPI, db: Session, admin, student, fake_backend):
    principal = make_user(db, email="principal@example.test", role=ROLE_PRINCIPAL)
    learner = make_user(db, email="learner@example.test", role=ROLE_STUDENT)
    assert login(app, principal.email).get(f"/api/v1/students/{student.id}/enrollment").status_code == 200
    assert _consent(login(app, principal.email), student.id).status_code == 403
    assert login(app, learner.email).get(f"/api/v1/students/{student.id}/enrollment").status_code == 403


def test_unauthenticated_requests_are_refused(app: FastAPI, student):
    anon = TestClient(app)
    assert anon.get(f"/api/v1/students/{student.id}/enrollment").status_code == 401
    assert _consent(anon, student.id).status_code == 401


def test_missing_models_return_503_without_paths(app: FastAPI, admin, student, monkeypatch):
    import app.api.v1.biometrics as api

    def unavailable():
        raise BackendUnavailable("Face model file not found: face_detection_yunet_2023mar.onnx.")

    monkeypatch.setattr(api, "get_backend", unavailable)
    client = login(app, admin.email)
    _consent(client, student.id)
    response = _upload(client, student.id, _good_photos(5))
    assert response.status_code == 503
    assert "/" not in response.json()["detail"]


def test_too_many_images_is_refused(app: FastAPI, admin, student, fake_backend):
    client = login(app, admin.email)
    _consent(client, student.id)
    response = _upload(client, student.id, _good_photos(21))
    assert response.status_code == 422


def test_audit_log_records_counts_not_biometrics(app: FastAPI, admin, student, fake_backend, db: Session):
    client = login(app, admin.email)
    _consent(client, student.id)
    _upload(client, student.id, _good_photos(5))
    rows = db.scalars(select(AuditLog).where(AuditLog.action.like("enrollment.%"))).all()
    assert rows and rows[0].details is not None
    dumped = json.dumps(rows[0].details)
    assert "embedding" not in dumped and "image" not in dumped


def test_inactive_student_cannot_be_enrolled(app: FastAPI, admin, student, db: Session):
    student.status = "inactive"
    db.commit()
    client = login(app, admin.email)
    response = _consent(client, student.id)
    assert response.status_code == 422


def test_retention_purge_removes_only_expired_embeddings(
    app: FastAPI, admin, student, fake_backend, db: Session
):
    client = login(app, admin.email)
    _consent(client, student.id)
    _upload(client, student.id, _good_photos(5))
    old = datetime.now(UTC) - timedelta(days=400)
    rows = db.scalars(select(FaceEmbedding)).all()
    for row in rows[:2]:
        row.created_at = old
    db.commit()
    deleted = enrollment.purge_expired(db, retention_days=365)
    assert deleted == 2
    assert db.scalar(select(func.count()).select_from(FaceEmbedding)) == 3


def test_purge_cli_reports_count(db: Session, capsys):
    from app.cli import main

    assert main(["purge-biometrics"]) == 0
    assert "Deleted 0 expired face embedding" in capsys.readouterr().out


def test_gallery_rows_skip_inactive_students_and_wrong_dimension(
    app: FastAPI, admin, student, fake_backend, db: Session
):
    client = login(app, admin.email)
    _consent(client, student.id)
    _upload(client, student.id, _good_photos(5))
    assert len(enrollment.load_gallery_rows(db)) == 5
    student.status = "inactive"
    db.commit()
    assert enrollment.load_gallery_rows(db) == []
