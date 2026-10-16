from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import UserOut, normalize_email

RoleName = Literal["admin", "principal", "faculty", "student", "technical"]


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(min_length=2, max_length=120)
    role: RoleName
    initial_password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return " ".join(value.split())


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: RoleName | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


__all__ = ["PasswordResetRequest", "RoleName", "UserCreate", "UserOut", "UserUpdate"]
