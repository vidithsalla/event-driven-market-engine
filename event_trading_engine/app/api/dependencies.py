"""FastAPI dependency injection helpers."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy.orm import Session

from event_trading_engine.app.db.session import build_engine, build_session_factory

_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://trader:trader@localhost:5432/trading_sim"
)
_engine = build_engine(_DB_URL)
_session_factory = build_session_factory(_engine)


def get_db() -> Generator[Session, None, None]:
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
