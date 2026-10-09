"""Database engine and session helpers (SQLite via SQLModel)."""
from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread=False: FastAPI may use a session from a different thread than the one that created it.
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    # Import models so their tables are registered on SQLModel.metadata before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
