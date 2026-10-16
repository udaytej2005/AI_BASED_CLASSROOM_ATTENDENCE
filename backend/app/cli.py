"""Command-line tools for setup.

Examples (run from backend/ with the virtual environment active):

    python -m app.cli create-admin --email you@college.example --name "Your Name"
    python -m app.cli seed-demo

`create-admin` asks for the password interactively (or reads one line from stdin with --password-stdin).
Passwords are never accepted as command-line arguments, so they do not end up in shell history.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password, validate_password_policy
from app.db.session import get_session_factory
from app.models.user import ROLE_ADMIN, User
from app.schemas.auth import normalize_email
from app.services import audit


def create_admin(email: str, full_name: str, password: str) -> None:
    normalized = normalize_email(email)
    validate_password_policy(password)
    with get_session_factory()() as db:
        if db.scalar(select(User.id).where(User.email == normalized)) is not None:
            raise SystemExit(f"An account with {normalized} already exists. No changes made.")
        user = User(
            email=normalized,
            full_name=" ".join(full_name.split()),
            role=ROLE_ADMIN,
            password_hash=hash_password(password),
            must_change_password=False,
            is_active=True,
            is_synthetic=False,
        )
        db.add(user)
        db.flush()
        audit.record_audit(
            db,
            actor_user_id=None,
            action="user.created_via_cli",
            entity="user",
            entity_id=user.id,
            details={"role": ROLE_ADMIN, "email": normalized},
        )
        db.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    admin = sub.add_parser("create-admin", help="Create the first (or an additional) administrator account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    admin.add_argument("--password-stdin", action="store_true", help="Read the password from stdin")

    sub.add_parser("seed-demo", help="Create synthetic demonstration data (idempotent, never in production)")

    purge = sub.add_parser("purge-biometrics", help="Delete face embeddings older than the retention period")
    purge.add_argument(
        "--retention-days", type=int, default=None, help="Override BIOMETRIC_RETENTION_DAYS once"
    )

    args = parser.parse_args(argv)

    if args.command == "create-admin":
        if args.password_stdin:
            password = sys.stdin.readline().rstrip("\n")
        else:
            password = getpass.getpass("Password (min 12 characters): ")
            if getpass.getpass("Repeat password: ") != password:
                print("The passwords do not match.", file=sys.stderr)
                return 1
        try:
            create_admin(args.email, args.name, password)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Administrator account created for {normalize_email(args.email)}.")
        return 0

    if args.command == "purge-biometrics":
        from app.services.enrollment import purge_expired

        with get_session_factory()() as db:
            deleted = purge_expired(db, retention_days=args.retention_days)
        print(f"Deleted {deleted} expired face embedding(s).")
        return 0

    if args.command == "seed-demo":
        from app.seed.demo import seed_demo

        if get_settings().app_env == "production":
            print("Refusing to seed demo data when APP_ENV=production.", file=sys.stderr)
            return 1
        with get_session_factory()() as db:
            report = seed_demo(db)
        if report.created:
            summary = ", ".join(f"{count} {name}" for name, count in sorted(report.created.items()))
            print(f"Demo data created: {summary}.")
        else:
            print("Demo data already present. Nothing to do.")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
