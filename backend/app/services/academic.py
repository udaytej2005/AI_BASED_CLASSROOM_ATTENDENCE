"""Departments, students and faculty: creation, search, update and visibility rules.

Visibility rules (enforced here, not in the frontend):
- Administrators and principals see everything, including email addresses.
- Faculty see the student and faculty directories, but not email addresses.
- Students see only their own student record (other records return 404, so existence is not revealed).
"""

from __future__ import annotations

from typing import cast

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.core.security import hash_password, validate_password_policy
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, ROLE_PRINCIPAL, ROLE_STUDENT, User
from app.schemas.academic import (
    AccountSetup,
    DepartmentCreate,
    DepartmentOut,
    FacultyCreate,
    FacultyOut,
    FacultyUpdate,
    Status,
    StudentCreate,
    StudentOut,
    StudentUpdate,
)
from app.schemas.common import Page, PageParams
from app.services import audit

SEES_CONTACT_DETAILS = {ROLE_ADMIN, ROLE_PRINCIPAL}


# ---------- helpers ----------


def _active_department(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None or not department.is_active:
        raise AppError(422, "Select an active department.")
    return department


def _check_account(db: Session, account: AccountSetup, role: str) -> None:
    try:
        validate_password_policy(account.initial_password)
    except ValueError as exc:
        raise AppError(422, str(exc)) from exc
    if db.scalar(select(User.id).where(User.email == account.email)) is not None:
        raise Conflict("An account with this login email already exists.")
    if role not in (ROLE_STUDENT, ROLE_FACULTY):
        raise AppError(422, "Invalid account role.")


def _create_account(db: Session, account: AccountSetup, role: str, full_name: str) -> User:
    user = User(
        email=account.email,
        full_name=full_name,
        role=role,
        password_hash=hash_password(account.initial_password),
        must_change_password=True,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(message) from exc


REQUIRED_FACULTY_FIELDS = {
    "full_name": "Full name",
    "department_id": "Department",
    "status": "Status",
}

REQUIRED_STUDENT_FIELDS = {
    "full_name": "Full name",
    "department_id": "Department",
    "year": "Year",
    "section": "Section",
    "status": "Status",
}


def _student_out(student: Student, department_code: str, viewer_role: str) -> StudentOut:
    return StudentOut(
        id=student.id,
        student_code=student.student_code,
        full_name=student.full_name,
        department_id=student.department_id,
        department_code=department_code,
        year=student.year,
        section=student.section,
        email=student.email if viewer_role in SEES_CONTACT_DETAILS else None,
        status=cast(Status, student.status),
        has_login=student.user_id is not None,
        is_synthetic=student.is_synthetic,
    )


def _faculty_out(member: Faculty, department_code: str, viewer_role: str) -> FacultyOut:
    return FacultyOut(
        id=member.id,
        employee_code=member.employee_code,
        full_name=member.full_name,
        department_id=member.department_id,
        department_code=department_code,
        email=member.email if viewer_role in SEES_CONTACT_DETAILS else None,
        status=cast(Status, member.status),
        has_login=member.user_id is not None,
        is_synthetic=member.is_synthetic,
    )


# ---------- departments ----------


def list_departments(db: Session) -> list[DepartmentOut]:
    rows = db.scalars(select(Department).order_by(Department.code)).all()
    return [DepartmentOut(id=d.id, code=d.code, name=d.name, is_active=d.is_active) for d in rows]


def create_department(db: Session, actor: User, data: DepartmentCreate) -> DepartmentOut:
    department = Department(code=data.code, name=data.name, is_active=True)
    db.add(department)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("A department with this code or name already exists.") from exc
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="department.created",
        entity="department",
        entity_id=department.id,
        details={"code": department.code},
    )
    db.commit()
    return DepartmentOut(id=department.id, code=department.code, name=department.name, is_active=True)


# ---------- students ----------


def list_students(
    db: Session,
    viewer: User,
    *,
    params: PageParams,
    q: str | None = None,
    department_id: int | None = None,
    year: int | None = None,
    status: str | None = None,
) -> Page[StudentOut]:
    statement = select(Student, Department.code).join(Department, Student.department_id == Department.id)
    if q:
        pattern = f"%{q.strip().lower()}%"
        statement = statement.where(
            func.lower(Student.student_code).like(pattern) | func.lower(Student.full_name).like(pattern)
        )
    if department_id is not None:
        statement = statement.where(Student.department_id == department_id)
    if year is not None:
        statement = statement.where(Student.year == year)
    if status is not None:
        statement = statement.where(Student.status == status)
    statement = statement.order_by(Student.student_code)

    # paginate() expects single-entity rows, so build the page from tuples here.
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = db.execute(statement.limit(params.page_size).offset(params.offset)).all()
    items = [_student_out(student, code, viewer.role) for student, code in rows]
    return Page.build(items, total=total, page=params.page, page_size=params.page_size)


def _student_with_department(db: Session, where_clause: ColumnElement[bool]) -> tuple[Student, str] | None:
    row = db.execute(
        select(Student, Department.code)
        .join(Department, Student.department_id == Department.id)
        .where(where_clause)
    ).first()
    return (row[0], row[1]) if row else None


def get_student_for_viewer(db: Session, viewer: User, student_id: int) -> StudentOut:
    found = _student_with_department(db, Student.id == student_id)
    if found is None:
        raise NotFound("Student")
    student, code = found
    if viewer.role == ROLE_STUDENT and student.user_id != viewer.id:
        # Pretend the record does not exist for anyone other than the owner.
        raise NotFound("Student")
    return _student_out(student, code, viewer.role)


def get_own_student(db: Session, user: User) -> StudentOut:
    found = _student_with_department(db, Student.user_id == user.id)
    if found is None:
        raise NotFound("Student profile")
    student, code = found
    return _student_out(student, code, user.role)


def create_student(db: Session, actor: User, data: StudentCreate) -> StudentOut:
    department = _active_department(db, data.department_id)
    if db.scalar(select(Student.id).where(Student.student_code == data.student_code)) is not None:
        raise Conflict("A student with this student ID already exists.")
    if data.account is not None:
        _check_account(db, data.account, ROLE_STUDENT)

    user_id = None
    if data.account is not None:
        user_id = _create_account(db, data.account, ROLE_STUDENT, data.full_name).id

    student = Student(
        student_code=data.student_code,
        full_name=data.full_name,
        department_id=department.id,
        year=data.year,
        section=data.section,
        email=data.email,
        status=data.status,
        user_id=user_id,
        is_synthetic=False,
    )
    db.add(student)
    db.flush()
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="student.created",
        entity="student",
        entity_id=student.id,
        details={"student_code": student.student_code, "has_login": user_id is not None},
    )
    _commit_or_conflict(db, "A student or login with these details already exists.")
    return get_student_for_viewer(db, actor, student.id)


def update_student(db: Session, actor: User, student_id: int, data: StudentUpdate) -> StudentOut:
    found = _student_with_department(db, Student.id == student_id)
    if found is None:
        raise NotFound("Student")
    student, _ = found
    changes = data.model_dump(exclude_unset=True)
    if "department_id" in changes and changes["department_id"] is not None:
        _active_department(db, changes["department_id"])
    for field, value in changes.items():
        if value is None and field in REQUIRED_STUDENT_FIELDS:
            raise AppError(422, f"{REQUIRED_STUDENT_FIELDS[field]} cannot be empty.")
        setattr(student, field, value)
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="student.updated",
        entity="student",
        entity_id=student.id,
        details={"changed_fields": sorted(changes.keys())},
    )
    _commit_or_conflict(db, "The update conflicts with an existing record.")
    return get_student_for_viewer(db, actor, student.id)


# ---------- faculty ----------


def list_faculty(
    db: Session,
    viewer: User,
    *,
    params: PageParams,
    q: str | None = None,
    department_id: int | None = None,
    status: str | None = None,
) -> Page[FacultyOut]:
    statement = select(Faculty, Department.code).join(Department, Faculty.department_id == Department.id)
    if q:
        pattern = f"%{q.strip().lower()}%"
        statement = statement.where(
            func.lower(Faculty.employee_code).like(pattern) | func.lower(Faculty.full_name).like(pattern)
        )
    if department_id is not None:
        statement = statement.where(Faculty.department_id == department_id)
    if status is not None:
        statement = statement.where(Faculty.status == status)
    statement = statement.order_by(Faculty.employee_code)

    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = db.execute(statement.limit(params.page_size).offset(params.offset)).all()
    items = [_faculty_out(member, code, viewer.role) for member, code in rows]
    return Page.build(items, total=total, page=params.page, page_size=params.page_size)


def _faculty_with_department(db: Session, faculty_id: int) -> tuple[Faculty, str]:
    row = db.execute(
        select(Faculty, Department.code)
        .join(Department, Faculty.department_id == Department.id)
        .where(Faculty.id == faculty_id)
    ).first()
    if row is None:
        raise NotFound("Faculty member")
    return row[0], row[1]


def get_faculty_for_viewer(db: Session, viewer: User, faculty_id: int) -> FacultyOut:
    member, code = _faculty_with_department(db, faculty_id)
    return _faculty_out(member, code, viewer.role)


def create_faculty(db: Session, actor: User, data: FacultyCreate) -> FacultyOut:
    department = _active_department(db, data.department_id)
    if db.scalar(select(Faculty.id).where(Faculty.employee_code == data.employee_code)) is not None:
        raise Conflict("A faculty member with this employee code already exists.")
    if data.account is not None:
        _check_account(db, data.account, ROLE_FACULTY)

    user_id = None
    if data.account is not None:
        user_id = _create_account(db, data.account, ROLE_FACULTY, data.full_name).id

    member = Faculty(
        employee_code=data.employee_code,
        full_name=data.full_name,
        department_id=department.id,
        email=data.email,
        status=data.status,
        user_id=user_id,
        is_synthetic=False,
    )
    db.add(member)
    db.flush()
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="faculty.created",
        entity="faculty",
        entity_id=member.id,
        details={"employee_code": member.employee_code, "has_login": user_id is not None},
    )
    _commit_or_conflict(db, "A faculty member or login with these details already exists.")
    return get_faculty_for_viewer(db, actor, member.id)


def update_faculty(db: Session, actor: User, faculty_id: int, data: FacultyUpdate) -> FacultyOut:
    member, _ = _faculty_with_department(db, faculty_id)
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if value is None and field in REQUIRED_FACULTY_FIELDS:
            raise AppError(422, f"{REQUIRED_FACULTY_FIELDS[field]} cannot be empty.")
    if changes.get("department_id") is not None:
        _active_department(db, changes["department_id"])
    for field, value in changes.items():
        setattr(member, field, value)
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="faculty.updated",
        entity="faculty",
        entity_id=member.id,
        details={"changed_fields": sorted(changes.keys())},
    )
    _commit_or_conflict(db, "The update conflicts with an existing record.")
    return get_faculty_for_viewer(db, actor, member.id)
