"""Database session factory.

Usage:
    engine = build_engine(DATABASE_URL)
    factory = build_session_factory(engine)
    with transactional_session(factory) as session:
        session.add(...)
"""
from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://trader:trader@localhost:5432/trading_sim",
)


def build_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def build_session_factory(engine: Engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def transactional_session(session_factory) -> Generator[Session, None, None]:
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
