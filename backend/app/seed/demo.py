"""Synthetic demonstration data.

Everything created here is FICTIONAL and flagged `is_synthetic=True`. The seed:
- uses the reserved `.invalid` domain for every email address, so no message can reach a real person;
- creates 20 students (CSE001-CSE020), 3 faculty, a principal, a technical operator and an administrator;
- never creates face embeddings, photographs or attendance records (those belong to later phases);
- is idempotent: running it again creates nothing new and never duplicates a record;
- refuses to run when APP_ENV=production.

The demo password is a documented, well-known value for local demonstration ONLY. Set DEMO_PASSWORD in the
environment to use your own value. Change or delete demo accounts before any real deployment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, validate_password_policy
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, ROLE_PRINCIPAL, ROLE_STUDENT, ROLE_TECHNICAL, User

DEMO_DOMAIN = "demo.invalid"
DEMO_DEFAULT_PASSWORD = "Demo-Local-2026!"  # Local demonstration only. See module docstring.

DEPARTMENTS = [
    ("CSE", "Computer Science and Engineering"),
    ("ECE", "Electronics and Communication Engineering"),
    ("MECH", "Mechanical Engineering"),
]

# Fictional names only.
STUDENT_NAMES = [
    "Aarav Mehta", "Diya Krishnan", "Rohan Iyer", "Meera Nair", "Kabir Sethi",
    "Ishita Rao", "Vihaan Reddy", "Anika Joshi", "Arjun Pillai", "Saanvi Gupta",
    "Dhruv Chawla", "Tara Menon", "Ishaan Kulkarni", "Riya Bhatt", "Advait Shah",
    "Nisha Varma", "Krish Patel", "Pooja Hegde", "Yash Malhotra", "Kavya Subramanian",
]  # fmt: skip

FACULTY = [
    ("DEMO-F001", "Dr. Lakshmi Narayan", "CSE", "faculty1"),
    ("DEMO-F002", "Prof. Sameer Ahuja", "ECE", "faculty2"),
    ("DEMO-F003", "Dr. Helen Thomas", "MECH", "faculty3"),
]


@dataclass
class SeedReport:
    created: dict[str, int]

    def add(self, key: str, count: int = 1) -> None:
        self.created[key] = self.created.get(key, 0) + count


def _demo_password() -> str:
    password = os.environ.get("DEMO_PASSWORD", DEMO_DEFAULT_PASSWORD)
    validate_password_policy(password)
    return password


def _ensure_department(db: Session, code: str, name: str, report: SeedReport) -> Department:
    department = db.scalar(select(Department).where(Department.code == code))
    if department is None:
        department = Department(code=code, name=name, is_active=True)
        db.add(department)
        db.flush()
        report.add("departments")
    return department


def _ensure_user(
    db: Session, *, email: str, full_name: str, role: str, password_hash: str, report: SeedReport
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            role=role,
            password_hash=password_hash,
            must_change_password=False,
            is_synthetic=True,
            is_active=True,
        )
        db.add(user)
        db.flush()
        report.add("users")
    return user


def seed_demo(db: Session) -> SeedReport:
    if get_settings().app_env == "production":
        raise RuntimeError("Demo seed data must not be created when APP_ENV=production.")

    report = SeedReport(created={})
    password_hash = hash_password(_demo_password())

    departments = {code: _ensure_department(db, code, name, report) for code, name in DEPARTMENTS}

    _ensure_user(
        db,
        email=f"admin@{DEMO_DOMAIN}",
        full_name="Demo Administrator",
        role=ROLE_ADMIN,
        password_hash=password_hash,
        report=report,
    )
    _ensure_user(
        db,
        email=f"principal@{DEMO_DOMAIN}",
        full_name="Demo Principal",
        role=ROLE_PRINCIPAL,
        password_hash=password_hash,
        report=report,
    )
    _ensure_user(
        db,
        email=f"technical@{DEMO_DOMAIN}",
        full_name="Demo Technical Operator",
        role=ROLE_TECHNICAL,
        password_hash=password_hash,
        report=report,
    )

    for employee_code, name, dept_code, login in FACULTY:
        user = _ensure_user(
            db,
            email=f"{login}@{DEMO_DOMAIN}",
            full_name=name,
            role=ROLE_FACULTY,
            password_hash=password_hash,
            report=report,
        )
        if db.scalar(select(Faculty.id).where(Faculty.employee_code == employee_code)) is None:
            db.add(
                Faculty(
                    employee_code=employee_code,
                    full_name=name,
                    department_id=departments[dept_code].id,
                    email=user.email,
                    status="active",
                    user_id=user.id,
                    is_synthetic=True,
                )
            )
            report.add("faculty")

    for index, name in enumerate(STUDENT_NAMES, start=1):
        code = f"CSE{index:03d}"
        email = f"{code.lower()}@{DEMO_DOMAIN}"
        if db.scalar(select(Student.id).where(Student.student_code == code)) is not None:
            continue
        user = _ensure_user(
            db,
            email=email,
            full_name=name,
            role=ROLE_STUDENT,
            password_hash=password_hash,
            report=report,
        )
        db.add(
            Student(
                student_code=code,
                full_name=name,
                department_id=departments["CSE"].id,
                year=2,
                section="A" if index <= 10 else "B",
                email=email,
                status="active",
                user_id=user.id,
                is_synthetic=True,
            )
        )
        report.add("students")

    db.commit()
    return report
