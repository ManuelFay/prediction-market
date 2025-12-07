from __future__ import annotations

import logging
import os

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///./prediction.db"
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def _reset_database() -> None:
    """Drop all existing tables to avoid schema incompatibilities."""

    # Remove the SQLite file entirely to ensure a clean schema on initialization.
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "", 1)
        if os.path.exists(db_path):
            logger.info("Resetting database by deleting existing file at %s", db_path)
            os.remove(db_path)


def init_db() -> None:
    """Reset and recreate the database.

    This is invoked by the FastAPI startup event in ``app.main.on_startup`` so the
    schema is recreated each time the app boots.
    """

    _reset_database()
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    with Session(engine) as session:
        yield session
