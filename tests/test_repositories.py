"""Tests for BacktestRepository: CRUD operations against SQLite in-memory DB."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from event_trading_engine.app.repositories.backtest_repository import BacktestRepository
from event_trading_engine.engine.events import (
    EventType,
    MarketEvent,
    OrderSide,
    OrderStatus,
    PortfolioSnapshot,
    Position,
    Signal,
    SignalAction,
    SimulatedOrder,
    Trade,
)

RUN_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
TS = datetime(2026, 5, 3, 9, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo(db_session):
    return BacktestRepository(db_session)


def _create_run(repo, run_id: str = RUN_ID):
    return repo.create_run(
        run_id=run_id,
        strategy_name="test_strategy",
        initial_cash=100_000.0,
    )


def _make_trade(run_id_str: str) -> Trade:
    return Trade(
        trade_id=uuid4(),
        run_id=uuid.UUID(run_id_str),
        order_id=uuid4(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        fill_price=115.0,
        fee=1.15,
        timestamp=TS,
    )


def _make_signal(run_id_str: str) -> Signal:
    return Signal(
        signal_id=uuid4(),
        run_id=uuid.UUID(run_id_str),
        timestamp=TS,
        symbol="AAPL",
        action=SignalAction.BUY,
        quantity=10,
        reason="test signal",
    )


def _make_order(run_id_str: str, signal_id: uuid.UUID) -> SimulatedOrder:
    return SimulatedOrder(
        order_id=uuid4(),
        run_id=uuid.UUID(run_id_str),
        signal_id=signal_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        requested_price=115.0,
        status=OrderStatus.FILLED,
    )


def _make_position(run_id_str: str) -> Position:
    return Position(
        run_id=uuid.UUID(run_id_str),
        symbol="AAPL",
        quantity=10,
        average_cost=115.0,
        market_price=115.0,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
    )


def _make_snapshot(run_id_str: str) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        run_id=uuid.UUID(run_id_str),
        timestamp=TS,
        cash=98_850.0,
        equity=100_000.0,
        gross_exposure=1_150.0,
        net_exposure=1_150.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        total_pnl=0.0,
    )


def _make_event(run_id_str: str) -> MarketEvent:
    return MarketEvent(
        event_id=uuid4(),
        timestamp=TS,
        symbol="AAPL",
        event_type=EventType.PRICE_TICK,
        price=115.0,
        volume=1000,
    )


# ---------------------------------------------------------------------------
# Run CRUD
# ---------------------------------------------------------------------------


def test_create_run_stores_and_returns_model(db_session):
    repo = _repo(db_session)
    run = _create_run(repo)
    assert run.id == RUN_ID
    assert run.strategy_name == "test_strategy"
    assert run.status == "RUNNING"
    assert run.initial_cash == 100_000.0


def test_get_run_returns_created_run(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    db_session.commit()
    fetched = repo.get_run(RUN_ID)
    assert fetched is not None
    assert fetched.id == RUN_ID


def test_get_run_returns_none_for_missing(db_session):
    repo = _repo(db_session)
    assert repo.get_run("nonexistent") is None


def test_list_runs_returns_all(db_session):
    repo = _repo(db_session)
    _create_run(repo, run_id=str(uuid4()))
    _create_run(repo, run_id=str(uuid4()))
    db_session.commit()
    runs = repo.list_runs()
    assert len(runs) == 2


def test_list_runs_empty(db_session):
    repo = _repo(db_session)
    assert repo.list_runs() == []


def test_update_run_status(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    db_session.commit()
    repo.update_run_status(RUN_ID, "COMPLETED", ended_at=datetime.now(timezone.utc))
    db_session.commit()
    run = repo.get_run(RUN_ID)
    assert run.status == "COMPLETED"
    assert run.ended_at is not None


def test_update_run_status_raises_for_missing(db_session):
    repo = _repo(db_session)
    with pytest.raises(ValueError):
        repo.update_run_status("missing-id", "COMPLETED")


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


def test_save_and_get_trades(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    trades = [_make_trade(RUN_ID), _make_trade(RUN_ID)]
    repo.save_trades(RUN_ID, trades)
    db_session.commit()
    stored = repo.get_trades(RUN_ID)
    assert len(stored) == 2


def test_get_trades_empty_for_unknown_run(db_session):
    repo = _repo(db_session)
    assert repo.get_trades("unknown") == []


def test_trade_fields_persisted_correctly(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    trade = _make_trade(RUN_ID)
    repo.save_trades(RUN_ID, [trade])
    db_session.commit()
    stored = repo.get_trades(RUN_ID)[0]
    assert stored.symbol == "AAPL"
    assert stored.side == "BUY"
    assert stored.quantity == 10
    assert stored.fill_price == pytest.approx(115.0)


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def test_save_and_get_signals(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    repo.save_signals(RUN_ID, [_make_signal(RUN_ID)])
    db_session.commit()
    stored = repo.get_signals(RUN_ID)
    assert len(stored) == 1
    assert stored[0].action == "BUY"


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


def test_save_and_get_orders(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    signal = _make_signal(RUN_ID)
    order = _make_order(RUN_ID, signal.signal_id)
    repo.save_orders(RUN_ID, [order])
    db_session.commit()
    stored = repo.get_orders(RUN_ID)
    assert len(stored) == 1
    assert stored[0].status == "FILLED"


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


def test_save_and_get_positions(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    repo.save_positions(RUN_ID, [_make_position(RUN_ID)])
    db_session.commit()
    stored = repo.get_positions(RUN_ID)
    assert len(stored) == 1
    assert stored[0].symbol == "AAPL"
    assert stored[0].quantity == 10
    assert stored[0].average_cost == pytest.approx(115.0)


# ---------------------------------------------------------------------------
# Portfolio snapshots
# ---------------------------------------------------------------------------


def test_save_and_get_snapshots(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    snapshots = [_make_snapshot(RUN_ID) for _ in range(5)]
    repo.save_snapshots(RUN_ID, snapshots)
    db_session.commit()
    stored = repo.get_snapshots(RUN_ID)
    assert len(stored) == 5


# ---------------------------------------------------------------------------
# Market events
# ---------------------------------------------------------------------------


def test_save_and_get_events(db_session):
    repo = _repo(db_session)
    _create_run(repo)
    events = [_make_event(RUN_ID) for _ in range(3)]
    repo.save_events(RUN_ID, events)
    db_session.commit()
    # No get_events method yet; verify via direct model count
    from event_trading_engine.app.db.models import MarketEventModel
    count = db_session.query(MarketEventModel).filter(MarketEventModel.run_id == RUN_ID).count()
    assert count == 3
