"""Application error type. Services raise AppError; the app converts it into a consistent JSON response."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class NotFound(AppError):
    def __init__(self, what: str = "Record") -> None:
        super().__init__(404, f"{what} not found.")


class Conflict(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(409, detail)


class Forbidden(AppError):
    def __init__(self, detail: str = "You do not have permission to perform this action.") -> None:
        super().__init__(403, detail)
