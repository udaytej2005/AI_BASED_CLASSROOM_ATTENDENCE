"""Role-based access control matrix. Each endpoint is checked against every role.

These tests are the executable form of the permission table in docs/privacy-security-and-limitations.md.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.user import User
from tests.conftest import login, make_user

ROLES = ["admin", "principal", "faculty", "student", "technical"]


@pytest.fixture
def world(app: FastAPI, db: Session) -> dict[str, object]:
    """One signed-in client per role, plus one student record owned by the student user."""
    department = Department(code="CSE", name="Computer Science and Engineering", is_active=True)
    db.add(department)
    db.flush()

    users: dict[str, User] = {}
    for role in ROLES:
        users[role] = make_user(db, email=f"{role}@example.test", role=role)
    other_student = make_user(db, email="other.student@example.test", role="student")

    own_student = Student(
        student_code="CSE001",
        full_name="Owner Student",
        department_id=department.id,
        year=2,
        section="A",
        email="owner@example.test",
        status="active",
        user_id=users["student"].id,
    )
    stranger = Student(
        student_code="CSE002",
        full_name="Other Student",
        department_id=department.id,
        year=2,
        section="A",
        email="stranger@example.test",
        status="active",
        user_id=other_student.id,
    )
    faculty_member = Faculty(
        employee_code="F001",
        full_name="Dr Staff",
        department_id=department.id,
        email="staff@example.test",
        status="active",
    )
    db.add_all([own_student, stranger, faculty_member])
    db.commit()

    clients: dict[str, TestClient] = {role: login(app, f"{role}@example.test") for role in ROLES}
    return {
        "clients": clients,
        "own_student_id": own_student.id,
        "stranger_id": stranger.id,
        "faculty_id": faculty_member.id,
        "department_id": department.id,
    }


@pytest.mark.parametrize(
    ("method", "path", "allowed_roles"),
    [
        ("GET", "/api/v1/users", {"admin"}),
        ("GET", "/api/v1/audit-logs", {"admin"}),
        ("GET", "/api/v1/students", {"admin", "principal", "faculty"}),
        ("GET", "/api/v1/faculty", {"admin", "principal", "faculty"}),
        ("GET", "/api/v1/departments", set(ROLES)),
        ("GET", "/api/v1/students/me", {"student"}),
    ],
)
def test_read_endpoints_follow_the_permission_table(
    world: dict[str, object], app: FastAPI, method: str, path: str, allowed_roles: set[str]
):
    clients: dict[str, TestClient] = world["clients"]  # type: ignore[assignment]
    for role, client in clients.items():
        response = client.request(method, path)
        if role in allowed_roles:
            assert response.status_code == 200, f"{role} should reach {path}: {response.text}"
        else:
            assert response.status_code in (403, 404), f"{role} must not reach {path}: {response.status_code}"

    assert TestClient(app).request(method, path).status_code == 401


def test_only_admin_can_create_records(world: dict[str, object]):
    clients: dict[str, TestClient] = world["clients"]  # type: ignore[assignment]
    department_id = world["department_id"]

    def payloads(tag: str) -> dict[str, dict[str, object]]:
        return {
            "/api/v1/students": {
                "student_code": f"S{tag}01",
                "full_name": "New Student",
                "department_id": department_id,
                "year": 1,
                "section": "A",
            },
            "/api/v1/faculty": {
                "employee_code": f"FAC{tag}",
                "full_name": "New Faculty",
                "department_id": department_id,
            },
            "/api/v1/departments": {"code": f"D{tag}", "name": f"Dept {tag}"},
            "/api/v1/users": {
                "email": f"new{tag.lower()}@example.test",
                "full_name": "New Person",
                "role": "student",
                "initial_password": "Long-Enough-Pass-1",
            },
        }

    # Non-administrators are refused even with otherwise valid payloads.
    for index, role in enumerate(r for r in ROLES if r != "admin"):
        for path, payload in payloads(f"R{index}").items():
            response = clients[role].post(path, json=payload)
            assert response.status_code == 403, f"{role} must not POST {path}: {response.status_code}"

    # The administrator succeeds with the same kinds of payloads.
    for path, payload in payloads("ADM").items():
        response = clients["admin"].post(path, json=payload)
        assert response.status_code == 201, f"admin POST {path} failed: {response.text}"


def test_student_can_only_read_own_record(world: dict[str, object]):
    clients: dict[str, TestClient] = world["clients"]  # type: ignore[assignment]
    student_client = clients["student"]
    own_id = world["own_student_id"]
    stranger_id = world["stranger_id"]

    assert student_client.get(f"/api/v1/students/{own_id}").status_code == 200
    # Another student's record is reported as not found, so existence is not revealed.
    hidden = student_client.get(f"/api/v1/students/{stranger_id}")
    assert hidden.status_code == 404
    assert "Other Student" not in hidden.text


def test_technical_operator_cannot_read_student_or_faculty_records(world: dict[str, object]):
    clients: dict[str, TestClient] = world["clients"]  # type: ignore[assignment]
    technical = clients["technical"]
    assert technical.get(f"/api/v1/students/{world['own_student_id']}").status_code == 403
    assert technical.get(f"/api/v1/faculty/{world['faculty_id']}").status_code == 403


def test_contact_email_is_visible_only_to_admin_and_principal(world: dict[str, object]):
    clients: dict[str, TestClient] = world["clients"]  # type: ignore[assignment]
    student_id = world["own_student_id"]

    assert clients["admin"].get(f"/api/v1/students/{student_id}").json()["email"] == "owner@example.test"
    assert clients["principal"].get(f"/api/v1/students/{student_id}").json()["email"] == "owner@example.test"
    faculty_view = clients["faculty"].get("/api/v1/students").json()["items"]
    assert faculty_view and all(item["email"] is None for item in faculty_view)
    assert "owner@example.test" not in clients["faculty"].get("/api/v1/faculty").text


def test_faculty_directory_search_works_and_hides_contact_details(world: dict[str, object]):
    clients: dict[str, TestClient] = world["clients"]  # type: ignore[assignment]
    response = clients["faculty"].get("/api/v1/students", params={"q": "owner"})
    assert response.status_code == 200
    assert [item["student_code"] for item in response.json()["items"]] == ["CSE001"]
    assert response.json()["items"][0]["email"] is None
