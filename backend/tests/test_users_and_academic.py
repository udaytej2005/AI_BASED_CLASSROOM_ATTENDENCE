"""User management and academic-record (department, student, faculty) behaviour."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.student import Student
from app.models.user import User
from tests.conftest import PASSWORD, login, make_user

NEW_PASSWORD = "Initial-Password-123"


# ---------- user accounts ----------


def test_admin_creates_user_who_must_change_password_on_first_sign_in(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")

    response = admin.post(
        "/api/v1/users",
        json={
            "email": "  Faculty.New@Example.TEST ",
            "full_name": "  Priya   Sharma ",
            "role": "faculty",
            "initial_password": NEW_PASSWORD,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "faculty.new@example.test"
    assert body["full_name"] == "Priya Sharma"
    assert body["must_change_password"] is True

    newcomer = TestClient(app)
    sign_in = newcomer.post("/api/v1/auth/login", json={"email": body["email"], "password": NEW_PASSWORD})
    assert sign_in.status_code == 200
    assert sign_in.json()["must_change_password"] is True


def test_duplicate_email_is_a_conflict_not_a_server_error(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    make_user(db, email="taken@example.test", role="faculty")
    admin = login(app, "admin@example.test")

    response = admin.post(
        "/api/v1/users",
        json={
            "email": "taken@example.test",
            "full_name": "Dup Person",
            "role": "student",
            "initial_password": NEW_PASSWORD,
        },
    )
    assert response.status_code == 409


def test_user_creation_validates_input(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    base = {
        "email": "ok@example.test",
        "full_name": "Valid Name",
        "role": "student",
        "initial_password": NEW_PASSWORD,
    }

    assert admin.post("/api/v1/users", json={**base, "role": "superuser"}).status_code == 422
    assert admin.post("/api/v1/users", json={**base, "email": "not-an-email"}).status_code == 422
    assert admin.post("/api/v1/users", json={**base, "initial_password": "short"}).status_code == 422
    assert (
        admin.post("/api/v1/users", json={**base, "initial_password": "alllowercaseletters"}).status_code
        == 422
    )


def test_admin_cannot_remove_own_admin_rights_or_deactivate_self(app: FastAPI, db: Session):
    me = make_user(db, email="solo.admin@example.test", role="admin")
    admin = login(app, me.email)

    assert admin.patch(f"/api/v1/users/{me.id}", json={"role": "faculty"}).status_code == 422
    assert admin.patch(f"/api/v1/users/{me.id}", json={"is_active": False}).status_code == 422


def test_deactivating_a_user_revokes_their_sessions(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    target = make_user(db, email="target@example.test", role="faculty")
    admin = login(app, "admin@example.test")
    target_client = login(app, "target@example.test")
    assert target_client.get("/api/v1/auth/me").status_code == 200

    response = admin.patch(f"/api/v1/users/{target.id}", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert target_client.get("/api/v1/auth/me").status_code == 401


def test_password_reset_forces_change_and_revokes_sessions(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    target = make_user(db, email="reset.me@example.test", role="student")
    admin = login(app, "admin@example.test")
    target_client = login(app, "reset.me@example.test")

    response = admin.post(
        f"/api/v1/users/{target.id}/reset-password", json={"new_password": "Temporary-Pass-456"}
    )

    assert response.status_code == 200
    assert response.json()["must_change_password"] is True
    assert target_client.get("/api/v1/auth/me").status_code == 401
    assert (
        TestClient(app)
        .post("/api/v1/auth/login", json={"email": "reset.me@example.test", "password": PASSWORD})
        .status_code
        == 401
    )


def test_user_list_supports_search_filters_and_pagination(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin", full_name="Admin Person")
    for index in range(5):
        make_user(db, email=f"fac{index}@example.test", role="faculty", full_name=f"Faculty {index}")
    admin = login(app, "admin@example.test")

    page = admin.get("/api/v1/users", params={"role": "faculty", "page_size": 2, "page": 2}).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["total_pages"] == 3

    search = admin.get("/api/v1/users", params={"q": "fac3"}).json()
    assert [item["email"] for item in search["items"]] == ["fac3@example.test"]

    assert admin.get("/api/v1/users", params={"page_size": 500}).status_code == 422


# ---------- departments ----------


def test_department_codes_are_normalised_and_unique(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")

    created = admin.post("/api/v1/departments", json={"code": "ece", "name": "Electronics"})
    assert created.status_code == 201
    assert created.json()["code"] == "ECE"

    assert admin.post("/api/v1/departments", json={"code": "ECE", "name": "Other"}).status_code == 409
    assert admin.post("/api/v1/departments", json={"code": "bad code!", "name": "Bad"}).status_code == 422


# ---------- students ----------


def _student_payload(department_id: int, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "student_code": "cse001",
        "full_name": "  Asha   Verma ",
        "department_id": department_id,
        "year": 2,
        "section": "a",
        "email": "Asha.Verma@Example.TEST",
    }
    payload.update(overrides)
    return payload


def test_admin_creates_student_with_normalised_fields(app: FastAPI, db: Session, department_id: int):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")

    response = admin.post("/api/v1/students", json=_student_payload(department_id))

    assert response.status_code == 201
    body = response.json()
    assert body["student_code"] == "CSE001"
    assert body["full_name"] == "Asha Verma"
    assert body["section"] == "A"
    assert body["email"] == "asha.verma@example.test"
    assert body["department_code"] == "CSE"
    assert body["has_login"] is False
    assert body["is_synthetic"] is False


def test_student_validation_and_duplicates(app: FastAPI, db: Session, department_id: int):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    assert admin.post("/api/v1/students", json=_student_payload(department_id)).status_code == 201

    assert admin.post("/api/v1/students", json=_student_payload(department_id)).status_code == 409
    assert admin.post("/api/v1/students", json=_student_payload(department_id, year=9)).status_code == 422
    assert admin.post("/api/v1/students", json=_student_payload(department_id, year=0)).status_code == 422
    assert (
        admin.post("/api/v1/students", json=_student_payload(department_id, section="A-1!")).status_code
        == 422
    )
    assert (
        admin.post("/api/v1/students", json=_student_payload(department_id, status="deleted")).status_code
        == 422
    )
    assert (
        admin.post("/api/v1/students", json=_student_payload(999_999, student_code="CSE777")).status_code
        == 422
    )


def test_student_with_login_is_created_atomically(app: FastAPI, db: Session, department_id: int):
    make_user(db, email="admin@example.test", role="admin")
    make_user(db, email="already.used@example.test", role="faculty")
    admin = login(app, "admin@example.test")

    # The login email is already taken, so the whole request must fail and no profile may be left behind.
    clash = admin.post(
        "/api/v1/students",
        json=_student_payload(
            department_id,
            student_code="CSE050",
            account={"email": "already.used@example.test", "initial_password": NEW_PASSWORD},
        ),
    )
    assert clash.status_code == 409
    assert db.scalar(select(Student).where(Student.student_code == "CSE050")) is None

    ok = admin.post(
        "/api/v1/students",
        json=_student_payload(
            department_id,
            student_code="CSE051",
            account={"email": "cse051@example.test", "initial_password": NEW_PASSWORD},
        ),
    )
    assert ok.status_code == 201
    assert ok.json()["has_login"] is True
    account = db.scalar(select(User).where(User.email == "cse051@example.test"))
    assert account.role == "student"
    assert account.must_change_password is True


def test_student_profile_update_is_partial_and_audited(app: FastAPI, db: Session, department_id: int):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    student_id = admin.post("/api/v1/students", json=_student_payload(department_id)).json()["id"]

    response = admin.patch(f"/api/v1/students/{student_id}", json={"year": 3, "status": "inactive"})

    assert response.status_code == 200
    assert response.json()["year"] == 3
    assert response.json()["status"] == "inactive"
    assert response.json()["full_name"] == "Asha Verma"  # unchanged
    assert admin.patch(f"/api/v1/students/{student_id}", json={"status": None}).status_code == 422


def test_explicit_nulls_for_required_fields_are_rejected_not_ignored(
    app: FastAPI, db: Session, department_id: int
):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    student_id = admin.post("/api/v1/students", json=_student_payload(department_id)).json()["id"]
    faculty_id = admin.post(
        "/api/v1/faculty",
        json={"employee_code": "EMP-200", "full_name": "Dr Null Test", "department_id": department_id},
    ).json()["id"]

    for field in ("full_name", "department_id", "year", "section"):
        response = admin.patch(f"/api/v1/students/{student_id}", json={field: None})
        assert response.status_code == 422, field
    response = admin.patch(f"/api/v1/faculty/{faculty_id}", json={"full_name": None})
    assert response.status_code == 422
    response = admin.patch(f"/api/v1/faculty/{faculty_id}", json={"department_id": None})
    assert response.status_code == 422

    # The record is unchanged after the rejected requests.
    assert admin.get(f"/api/v1/students/{student_id}").json()["full_name"] == "Asha Verma"
    assert admin.get(f"/api/v1/faculty/{faculty_id}").json()["full_name"] == "Dr Null Test"


def test_student_search_filters_and_pagination(app: FastAPI, db: Session, department_id: int):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    for index in range(1, 26):
        admin.post(
            "/api/v1/students",
            json=_student_payload(
                department_id,
                student_code=f"CSE{index:03d}",
                full_name=f"Student Number {index}",
                email=None,
                section="B" if index % 2 else "A",
            ),
        )

    first = admin.get("/api/v1/students", params={"page_size": 10}).json()
    assert first["total"] == 25 and first["total_pages"] == 3 and len(first["items"]) == 10
    assert first["items"][0]["student_code"] == "CSE001"

    search = admin.get("/api/v1/students", params={"q": "cse02"}).json()
    assert search["total"] == 6  # CSE020 through CSE025 contain "cse02"

    by_status = admin.get("/api/v1/students", params={"status": "inactive"}).json()
    assert by_status["total"] == 0

    assert admin.get("/api/v1/students", params={"page_size": 101}).status_code == 422


def test_student_record_is_never_hard_deleted_by_the_api(app: FastAPI, db: Session, department_id: int):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    student_id = admin.post("/api/v1/students", json=_student_payload(department_id)).json()["id"]
    assert admin.delete(f"/api/v1/students/{student_id}").status_code == 405


def test_unknown_student_returns_404(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    assert admin.get("/api/v1/students/424242").status_code == 404


# ---------- faculty ----------


def test_faculty_create_update_and_directory(app: FastAPI, db: Session, department_id: int):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")

    created = admin.post(
        "/api/v1/faculty",
        json={"employee_code": "emp-100", "full_name": "Dr Test Faculty", "department_id": department_id},
    )
    assert created.status_code == 201
    faculty_id = created.json()["id"]
    assert created.json()["employee_code"] == "EMP-100"

    updated = admin.patch(f"/api/v1/faculty/{faculty_id}", json={"status": "inactive"})
    assert updated.status_code == 200 and updated.json()["status"] == "inactive"

    listing = admin.get("/api/v1/faculty", params={"status": "inactive"}).json()
    assert listing["total"] == 1


def test_faculty_account_creation_links_login_and_rejects_non_faculty_role(
    app: FastAPI, db: Session, department_id: int
):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    response = admin.post(
        "/api/v1/faculty",
        json={
            "employee_code": "EMP-200",
            "full_name": "Dr Login Faculty",
            "department_id": department_id,
            "account": {"email": "emp200@example.test", "initial_password": NEW_PASSWORD},
        },
    )
    assert response.status_code == 201
    assert response.json()["has_login"] is True
    account = db.scalar(select(User).where(User.email == "emp200@example.test"))
    assert account.role == "faculty"


def test_department_is_required_for_students(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    admin = login(app, "admin@example.test")
    department = Department(code="ECE", name="Electronics", is_active=False)
    db.add(department)
    db.commit()
    response = admin.post("/api/v1/students", json=_student_payload(department.id))
    assert response.status_code == 422
