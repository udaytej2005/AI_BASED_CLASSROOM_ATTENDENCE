"""Verifies that Alembic can initialise a clean database from scratch."""

from sqlalchemy import inspect

from alembic import command
from alembic.config import Config
from app.db.session import build_engine


def test_migrations_apply_to_clean_database(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrate.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    from app.core import config

    config.get_settings.cache_clear()
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    engine = build_engine(url)
    try:
        assert "alembic_version" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
    config.get_settings.cache_clear()
