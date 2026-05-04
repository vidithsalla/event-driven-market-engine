"""Tests for the FastAPI layer.

All tests use an in-memory SQLite database injected via dependency override.
No live Postgres, Redpanda, or Redis required.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from event_trading_engine.app.api.app import create_app
from event_trading_engine.app.api.dependencies import get_db
from event_trading_engine.app.db.models import Base

# ---------------------------------------------------------------------------
# Test client fixture with SQLite override
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    # StaticPool forces all connections to reuse the same in-memory SQLite
    # connection, so tables created in the fixture are visible to request threads.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

class TestStrategies:
    def test_list_strategies_returns_two(self, client):
        resp = client.get("/api/strategies")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_strategy_has_required_fields(self, client):
        resp = client.get("/api/strategies")
        strategy = resp.json()[0]
        assert "name" in strategy
        assert "description" in strategy
        assert "parameters" in strategy

    def test_ma_crossover_listed(self, client):
        names = [s["name"] for s in client.get("/api/strategies").json()]
        assert "ma_crossover" in names

    def test_mean_reversion_listed(self, client):
        names = [s["name"] for s in client.get("/api/strategies").json()]
        assert "mean_reversion" in names


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class TestRuns:
    def _create_run(self, client, strategy_name: str = "ma_crossover"):
        return client.post("/api/runs", json={"strategy_name": strategy_name})

    def test_create_run_returns_201(self, client):
        resp = self._create_run(client)
        assert resp.status_code == 201

    def test_create_run_has_id(self, client):
        data = self._create_run(client).json()
        assert "id" in data and data["id"]

    def test_create_run_status_completed(self, client):
        data = self._create_run(client).json()
        assert data["status"] == "COMPLETED"

    def test_list_runs_empty_initially(self, client):
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_runs_after_create(self, client):
        self._create_run(client)
        runs = client.get("/api/runs").json()
        assert len(runs) == 1

    def test_get_run_by_id(self, client):
        run_id = self._create_run(client).json()["id"]
        resp = client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == run_id

    def test_get_missing_run_returns_404(self, client):
        resp = client.get("/api/runs/nonexistent-id")
        assert resp.status_code == 404

    def test_mean_reversion_run(self, client):
        resp = self._create_run(client, "mean_reversion")
        assert resp.status_code == 201
        assert resp.json()["strategy_name"] == "mean_reversion"


# ---------------------------------------------------------------------------
# Trades / orders / signals
# ---------------------------------------------------------------------------

class TestTradeEndpoints:
    def _run_id(self, client):
        return client.post("/api/runs", json={"strategy_name": "ma_crossover"}).json()["id"]

    def test_trades_returns_list(self, client):
        run_id = self._run_id(client)
        resp = client.get(f"/api/runs/{run_id}/trades")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_trades_has_two_entries(self, client):
        run_id = self._run_id(client)
        trades = client.get(f"/api/runs/{run_id}/trades").json()
        assert len(trades) == 2

    def test_orders_returns_list(self, client):
        run_id = self._run_id(client)
        resp = client.get(f"/api/runs/{run_id}/orders")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_signals_returns_list(self, client):
        run_id = self._run_id(client)
        resp = client.get(f"/api/runs/{run_id}/signals")
        assert resp.status_code == 200

    def test_trades_missing_run_returns_404(self, client):
        assert client.get("/api/runs/bad-id/trades").status_code == 404

    def test_orders_missing_run_returns_404(self, client):
        assert client.get("/api/runs/bad-id/orders").status_code == 404

    def test_signals_missing_run_returns_404(self, client):
        assert client.get("/api/runs/bad-id/signals").status_code == 404


# ---------------------------------------------------------------------------
# Portfolio / positions / metrics
# ---------------------------------------------------------------------------

class TestPortfolioEndpoints:
    def _run_id(self, client):
        return client.post("/api/runs", json={"strategy_name": "ma_crossover"}).json()["id"]

    def test_positions_returns_list(self, client):
        run_id = self._run_id(client)
        resp = client.get(f"/api/runs/{run_id}/positions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_portfolio_snapshots_returns_list(self, client):
        run_id = self._run_id(client)
        resp = client.get(f"/api/runs/{run_id}/portfolio")
        assert resp.status_code == 200

    def test_metrics_returns_object(self, client):
        run_id = self._run_id(client)
        resp = client.get(f"/api/runs/{run_id}/metrics")
        assert resp.status_code == 200
        m = resp.json()
        assert "total_pnl" in m
        assert "trade_count" in m

    def test_metrics_trade_count_matches_trades(self, client):
        run_id = self._run_id(client)
        trades = client.get(f"/api/runs/{run_id}/trades").json()
        metrics = client.get(f"/api/runs/{run_id}/metrics").json()
        assert metrics["trade_count"] == len(trades)

    def test_positions_missing_run_returns_404(self, client):
        assert client.get("/api/runs/bad-id/positions").status_code == 404

    def test_metrics_missing_run_returns_404(self, client):
        assert client.get("/api/runs/bad-id/metrics").status_code == 404
