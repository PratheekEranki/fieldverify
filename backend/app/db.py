"""Database engine and session helpers (SQLite via SQLModel)."""
import logging
from collections.abc import Iterator

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread=False: FastAPI may use a session from a different thread than the one that created it.
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    # Import models so their tables are registered on SQLModel.metadata before create_all.
    from app import models  # noqa: F401

    if _schema_is_stale():
        # Demo database only: rebuild it rather than migrate. Real deployments would use migrations (Alembic).
        logging.getLogger("fieldverify").warning("Database schema changed; rebuilding the demo database.")
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def _schema_is_stale() -> bool:
    inspector = inspect(engine)
    for table in SQLModel.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        if existing != {c.name for c in table.columns}:
            return True
    return False


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
