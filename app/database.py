"""SQLAlchemy engine and session handling.

Each app instance owns its own engine so tests can point at an isolated
temporary SQLite file without sharing connections with other tests.
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str) -> Engine:
    connect_args = {}
    if database_url.startswith("sqlite"):
        # FastAPI serves sync routes from a thread pool, so the same SQLite
        # connection may be used from different threads over its lifetime.
        connect_args["check_same_thread"] = False
        db_path = database_url.split("///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(database_url, connect_args=connect_args, future=True)


def build_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
