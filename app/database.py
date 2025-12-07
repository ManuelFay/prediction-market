from __future__ import annotations

from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = "sqlite:///./prediction.db"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
