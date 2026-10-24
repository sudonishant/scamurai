"""Database engine, session factory and declarative base.

PostgreSQL is the production target from the master prompt; SQLite keeps the
smallest runnable milestone working without infrastructure. Switch with
SCAMURAI_DATABASE_URL=postgresql+psycopg://user:pass@db/scamurai.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Dev/test convenience. Production schema changes go through Alembic migrations.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
