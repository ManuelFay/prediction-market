from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/prediction.db")
RESET_DB_ON_STARTUP = os.getenv("RESET_DB_ON_STARTUP", "false").lower() == "true"

if DATABASE_URL.startswith("sqlite:///"):
    db_path = Path(DATABASE_URL.replace("sqlite:///", "", 1))
    db_path.parent.mkdir(parents=True, exist_ok=True)

engine_kwargs: dict = {
    "echo": False,
    "connect_args": {"check_same_thread": False},
}

# In-memory SQLite benefits from StaticPool to reuse the same connection during tests.
if DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_kwargs)


def _reset_database() -> None:
    """Drop all existing tables to avoid schema incompatibilities."""

    # Remove the SQLite file entirely to ensure a clean schema on initialization.
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "", 1)
        if os.path.exists(db_path):
            logger.info("Resetting database by deleting existing file at %s", db_path)
            os.remove(db_path)


def ensure_market_deleted_flag(engine_obj=engine) -> None:
    """Backfill the ``is_deleted`` column for legacy SQLite databases."""

    url = str(engine_obj.url)
    if not url.startswith("sqlite"):
        return

    with engine_obj.connect() as conn:
        table_exists = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='market'"
        ).first()
        if not table_exists:
            return

        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(market);")}
        if "is_deleted" not in columns:
            logger.info("Adding missing is_deleted column to market table")
            conn.exec_driver_sql("ALTER TABLE market ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0")


def init_db() -> None:
    """Reset and recreate the database.

    This is invoked by the FastAPI startup event in ``app.main.on_startup`` so the
    schema is recreated each time the app boots.
    """

    if RESET_DB_ON_STARTUP:
        _reset_database()
    SQLModel.metadata.create_all(engine)
    ensure_market_deleted_flag()


def get_session() -> Session:
    with Session(engine) as session:
        yield session
