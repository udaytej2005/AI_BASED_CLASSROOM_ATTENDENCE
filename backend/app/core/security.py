"""Password hashing, password policy and session-token helpers.

- Passwords are hashed with Argon2id (argon2-cffi), the current OWASP-recommended password hash.
- Session tokens are random 256-bit values. The database stores only their SHA-256 digest, so a database
  leak does not reveal usable session cookies.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128  # Prevents very large inputs from being hashed (denial of service).

_hasher = PasswordHasher()  # argon2-cffi defaults (Argon2id) are used.

# A valid hash of a random value, used to keep login timing similar when the email is unknown.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


def validate_password_policy(password: str) -> None:
    """Raise ValueError with a user-facing message when a password does not meet the policy."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters long.")
    if password.strip() != password or not password.strip():
        raise ValueError("Password must not start or end with spaces and must not be blank.")
    classes = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if classes < 3:
        raise ValueError("Password must contain at least three of: lower case, upper case, digit, symbol.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Return True if the password matches. Never raises for malformed or missing hashes."""
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def spend_dummy_verification(password: str) -> None:
    """Run a hash verification so unknown-email logins take as long as known-email logins."""
    verify_password(_DUMMY_HASH, password)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
