"""Audit trail, demo seed, command-line setup and password primitives."""

import io
import json
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cli
from app.core import config
from app.core.security import (
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.user import User
from app.seed.demo import DEMO_DEFAULT_PASSWORD, seed_demo
from app.services.audit import record_audit
from tests.conftest import login, make_user

# ---------- audit trail ----------


def test_administrative_changes_are_audited_without_secrets(app: FastAPI, db: Session, department_id: int):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    admin.post(
        "/api/v1/students",
        json={
            "student_code": "CSE300",
            "full_name": "Audited Student",
            "department_id": department_id,
            "year": 1,
            "section": "A",
            "account": {"email": "cse300@example.test", "initial_password": "Audit-Password-99"},
        },
    )

    response = admin.get("/api/v1/audit-logs", params={"entity": "student"})
    assert response.status_code == 200
    actions = [item["action"] for item in response.json()["items"]]
    assert "student.created" in actions

    everything = response.text + json.dumps([row.details for row in db.scalars(select(AuditLog)).all()])
    assert "Audit-Password-99" not in everything
    assert "password_hash" not in everything


def test_login_and_logout_are_recorded(app: FastAPI, db: Session):
    make_user(db, email="auditor@example.test", role="admin")
    client = login(app, "auditor@example.test")
    client.post("/api/v1/auth/logout")

    actions = {row.action for row in db.scalars(select(AuditLog)).all()}
    assert {"auth.login", "auth.logout"} <= actions


def test_audit_details_reject_sensitive_field_names(db: Session):
    with pytest.raises(ValueError):
        record_audit(
            db,
            actor_user_id=None,
            action="test.bad",
            entity="user",
            entity_id=1,
            details={"new_password": "x"},
        )
    with pytest.raises(ValueError):
        record_audit(
            db, actor_user_id=None, action="t", entity="face", entity_id=1, details={"embedding_hash": "x"}
        )


# ---------- demo seed ----------


def test_seed_creates_expected_synthetic_records_and_is_idempotent(db: Session):
    first = seed_demo(db)
    assert first.created["students"] == 20
    assert first.created["faculty"] == 3
    assert first.created["departments"] == 3

    counts_before = {
        model.__tablename__: db.scalar(select(func.count()).select_from(model))
        for model in (User, Student, Faculty, Department)
    }

    second = seed_demo(db)
    assert second.created == {}

    counts_after = {
        model.__tablename__: db.scalar(select(func.count()).select_from(model))
        for model in (User, Student, Faculty, Department)
    }
    assert counts_before == counts_after
    assert counts_after["students"] == 20

    students = db.scalars(select(Student)).all()
    assert all(s.is_synthetic for s in students)
    assert all(s.email and s.email.endswith("@demo.invalid") for s in students)
    assert sorted(s.student_code for s in students) == [f"CSE{i:03d}" for i in range(1, 21)]


def test_seeded_demo_accounts_can_sign_in_and_are_marked_synthetic(app: FastAPI, db: Session):
    seed_demo(db)

    student_client = TestClient(app)
    response = student_client.post(
        "/api/v1/auth/login", json={"email": "cse001@demo.invalid", "password": DEMO_DEFAULT_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["is_synthetic"] is True
    profile = student_client.get("/api/v1/students/me")
    assert profile.status_code == 200
    assert profile.json()["student_code"] == "CSE001"

    admin = TestClient(app)
    assert (
        admin.post(
            "/api/v1/auth/login", json={"email": "admin@demo.invalid", "password": DEMO_DEFAULT_PASSWORD}
        ).status_code
        == 200
    )


def test_seed_refuses_to_run_in_production(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:realpw@db/x")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            seed_demo(db)
    finally:
        config.get_settings.cache_clear()


def test_seed_password_override_must_meet_policy(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEMO_PASSWORD", "weak")
    with pytest.raises(ValueError):
        seed_demo(db)


# ---------- command-line setup ----------


def test_create_admin_from_stdin_creates_one_active_admin(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("Setup-Passphrase-42\n"))
    code = cli.main(
        ["create-admin", "--email", "Head.Admin@College.Example", "--name", "Head Admin", "--password-stdin"]
    )
    assert code == 0

    admin = db.scalar(select(User).where(User.email == "head.admin@college.example"))
    assert admin is not None
    assert admin.role == "admin" and admin.is_active
    assert verify_password(admin.password_hash, "Setup-Passphrase-42")
    assert admin.password_hash != "Setup-Passphrase-42"


def test_create_admin_refuses_duplicates_and_weak_passwords(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("Setup-Passphrase-42\n"))
    assert (
        cli.main(["create-admin", "--email", "dup@college.example", "--name", "Dup", "--password-stdin"]) == 0
    )

    monkeypatch.setattr(sys, "stdin", io.StringIO("Setup-Passphrase-42\n"))
    with pytest.raises(SystemExit):
        cli.main(["create-admin", "--email", "dup@college.example", "--name", "Dup", "--password-stdin"])

    monkeypatch.setattr(sys, "stdin", io.StringIO("short\n"))
    assert (
        cli.main(["create-admin", "--email", "weak@college.example", "--name", "Weak", "--password-stdin"])
        == 1
    )
    assert db.scalar(select(User).where(User.email == "weak@college.example")) is None


# ---------- password primitives ----------


def test_password_hashing_is_salted_argon2_and_verifies_correctly():
    first = hash_password("Correct-Horse-1")
    second = hash_password("Correct-Horse-1")
    assert first.startswith("$argon2id$")
    assert first != second  # random salt
    assert verify_password(first, "Correct-Horse-1")
    assert not verify_password(first, "Wrong-Horse-1")


def test_malformed_or_missing_hashes_never_raise():
    assert verify_password(None, "anything") is False
    assert verify_password("", "anything") is False
    assert verify_password("not-a-hash", "anything") is False


@pytest.mark.parametrize(
    ("password", "message_fragment"),
    [
        ("short1A!", "at least 12"),
        ("alllowercaseonly", "three of"),
        ("  Spaced-Password-1  ", "start or end with spaces"),
        ("x" * 129, "at most 128"),
    ],
)
def test_password_policy_rejects_weak_values(password: str, message_fragment: str):
    with pytest.raises(ValueError, match=message_fragment):
        validate_password_policy(password)


def test_password_policy_accepts_reasonable_passphrase():
    validate_password_policy("Correct-Horse-Battery-1")
