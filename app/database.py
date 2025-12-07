from __future__ import annotations

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = "sqlite:///./prediction.db"
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    with Session(engine) as session:
        yield session
