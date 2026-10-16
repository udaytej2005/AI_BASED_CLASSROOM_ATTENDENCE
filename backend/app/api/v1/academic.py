"""Departments, students and faculty endpoints.

Role summary:
- departments: any signed-in user can read; administrators create.
- students:   administrators and principals manage; faculty read; students read only their own record.
- faculty:    administrators manage; principals and faculty read.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.errors import Forbidden
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, ROLE_PRINCIPAL, ROLE_STUDENT, User
from app.schemas.academic import (
    DepartmentCreate,
    DepartmentOut,
    FacultyCreate,
    FacultyOut,
    FacultyUpdate,
    StudentCreate,
    StudentOut,
    StudentUpdate,
)
from app.schemas.common import Page, PageParams
from app.services import academic

router = APIRouter(tags=["academic"])

AdminUser = Annotated[User, Depends(require_roles(ROLE_ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_FACULTY))]
DirectoryUser = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_FACULTY))]

# ---------- departments ----------


@router.get("/departments", response_model=list[DepartmentOut], summary="List departments")
def list_departments(db: DbSession, user: CurrentUser) -> list[DepartmentOut]:
    return academic.list_departments(db)


@router.post("/departments", response_model=DepartmentOut, status_code=201, summary="Create a department")
def create_department(payload: DepartmentCreate, db: DbSession, admin: AdminUser) -> DepartmentOut:
    return academic.create_department(db, admin, payload)


# ---------- students ----------


@router.get("/students", response_model=Page[StudentOut], summary="Search the student directory")
def list_students(
    db: DbSession,
    viewer: DirectoryUser,
    params: Annotated[PageParams, Depends()],
    q: Annotated[str | None, Query(max_length=120)] = None,
    department_id: Annotated[int | None, Query(ge=1)] = None,
    year: Annotated[int | None, Query(ge=1, le=6)] = None,
    status: Annotated[str | None, Query(pattern="^(active|inactive)$")] = None,
) -> Page[StudentOut]:
    return academic.list_students(
        db, viewer, params=params, q=q, department_id=department_id, year=year, status=status
    )


@router.get("/students/me", response_model=StudentOut, summary="The signed-in student's own profile")
def my_student_profile(db: DbSession, user: CurrentUser) -> StudentOut:
    if user.role != ROLE_STUDENT:
        raise Forbidden("Only student accounts have a student profile.")
    return academic.get_own_student(db, user)


@router.get("/students/{student_id}", response_model=StudentOut, summary="Get one student profile")
def get_student(student_id: int, db: DbSession, user: CurrentUser) -> StudentOut:
    # Students may read only their own record; other roles use the directory rules.
    if user.role not in {ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_FACULTY, ROLE_STUDENT}:
        raise Forbidden()
    return academic.get_student_for_viewer(db, user, student_id)


@router.post("/students", response_model=StudentOut, status_code=201, summary="Create a student profile")
def create_student(payload: StudentCreate, db: DbSession, admin: AdminUser) -> StudentOut:
    return academic.create_student(db, admin, payload)


@router.patch("/students/{student_id}", response_model=StudentOut, summary="Update a student profile")
def update_student(student_id: int, payload: StudentUpdate, db: DbSession, admin: AdminUser) -> StudentOut:
    return academic.update_student(db, admin, student_id, payload)


# ---------- faculty ----------


@router.get("/faculty", response_model=Page[FacultyOut], summary="Search the faculty directory")
def list_faculty(
    db: DbSession,
    viewer: DirectoryUser,
    params: Annotated[PageParams, Depends()],
    q: Annotated[str | None, Query(max_length=120)] = None,
    department_id: Annotated[int | None, Query(ge=1)] = None,
    status: Annotated[str | None, Query(pattern="^(active|inactive)$")] = None,
) -> Page[FacultyOut]:
    return academic.list_faculty(db, viewer, params=params, q=q, department_id=department_id, status=status)


@router.get("/faculty/{faculty_id}", response_model=FacultyOut, summary="Get one faculty member")
def get_faculty(faculty_id: int, db: DbSession, viewer: StaffUser) -> FacultyOut:
    return academic.get_faculty_for_viewer(db, viewer, faculty_id)


@router.post("/faculty", response_model=FacultyOut, status_code=201, summary="Create a faculty member")
def create_faculty(payload: FacultyCreate, db: DbSession, admin: AdminUser) -> FacultyOut:
    return academic.create_faculty(db, admin, payload)


@router.patch("/faculty/{faculty_id}", response_model=FacultyOut, summary="Update a faculty member")
def update_faculty(faculty_id: int, payload: FacultyUpdate, db: DbSession, admin: AdminUser) -> FacultyOut:
    return academic.update_faculty(db, admin, faculty_id, payload)
