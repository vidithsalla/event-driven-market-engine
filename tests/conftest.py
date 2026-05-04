"""Shared pytest fixtures.

All DB tests use an in-memory SQLite engine so they run without Docker.
Each test gets a fresh schema via the db_session fixture.

Tests marked @pytest.mark.integration require live Docker services (Postgres,
Redpanda, Redis) and are skipped by default. Run with --integration to enable.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from event_trading_engine.app.db.models import Base


def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", default=False, help="Run integration tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires live Docker services")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="pass --integration to run")
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(skip_integration)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
