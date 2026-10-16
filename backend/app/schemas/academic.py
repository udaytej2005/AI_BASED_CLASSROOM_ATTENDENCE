"""Request and response schemas for departments, students and faculty."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import normalize_email

Status = Literal["active", "inactive"]
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,31}$")
SECTION_PATTERN = re.compile(r"^[A-Za-z0-9]{1,10}$")


def _upper_code(value: str) -> str:
    value = value.strip().upper()
    if not CODE_PATTERN.match(value):
        raise ValueError("Use 2-32 letters, digits or hyphens, starting with a letter or digit.")
    return value


# ---------- Departments ----------


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=120)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        return _upper_code(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return " ".join(value.split())


class DepartmentOut(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool


# ---------- Login account attached to a profile (optional) ----------


class AccountSetup(BaseModel):
    """Optionally create a login for a student or faculty member in the same request."""

    email: str = Field(min_length=3, max_length=254)
    initial_password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)


# ---------- Students ----------


class StudentCreate(BaseModel):
    student_code: str = Field(min_length=2, max_length=32)
    full_name: str = Field(min_length=2, max_length=120)
    department_id: int = Field(ge=1)
    year: int = Field(ge=1, le=6)
    section: str = Field(min_length=1, max_length=10)
    email: str | None = Field(default=None, max_length=254)
    status: Status = "active"
    account: AccountSetup | None = None

    @field_validator("student_code")
    @classmethod
    def _code(cls, value: str) -> str:
        return _upper_code(value)

    @field_validator("full_name")
    @classmethod
    def _name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("section")
    @classmethod
    def _section(cls, value: str) -> str:
        value = value.strip().upper()
        if not SECTION_PATTERN.match(value):
            raise ValueError("Section must be 1-10 letters or digits.")
        return value

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value else None


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    department_id: int | None = Field(default=None, ge=1)
    year: int | None = Field(default=None, ge=1, le=6)
    section: str | None = Field(default=None, min_length=1, max_length=10)
    email: str | None = Field(default=None, max_length=254)
    status: Status | None = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None

    @field_validator("section")
    @classmethod
    def _section(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not SECTION_PATTERN.match(value):
            raise ValueError("Section must be 1-10 letters or digits.")
        return value

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value else None


class StudentOut(BaseModel):
    id: int
    student_code: str
    full_name: str
    department_id: int
    department_code: str
    year: int
    section: str
    email: str | None  # hidden (None) for viewers who are not administrators or principals
    status: Status
    has_login: bool
    is_synthetic: bool


# ---------- Faculty ----------


class FacultyCreate(BaseModel):
    employee_code: str = Field(min_length=2, max_length=32)
    full_name: str = Field(min_length=2, max_length=120)
    department_id: int = Field(ge=1)
    email: str | None = Field(default=None, max_length=254)
    status: Status = "active"
    account: AccountSetup | None = None

    @field_validator("employee_code")
    @classmethod
    def _code(cls, value: str) -> str:
        return _upper_code(value)

    @field_validator("full_name")
    @classmethod
    def _name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value else None


class FacultyUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    department_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=254)
    status: Status | None = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value else None


class FacultyOut(BaseModel):
    id: int
    employee_code: str
    full_name: str
    department_id: int
    department_code: str
    email: str | None
    status: Status
    has_login: bool
    is_synthetic: bool


__all__ = [
    "AccountSetup",
    "DepartmentCreate",
    "DepartmentOut",
    "FacultyCreate",
    "FacultyOut",
    "FacultyUpdate",
    "StudentCreate",
    "StudentOut",
    "StudentUpdate",
]
