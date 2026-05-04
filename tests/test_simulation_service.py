"""Integration tests: SimulationService runs a full backtest and persists to SQLite."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from event_trading_engine.app.services.simulation_service import SimulationService
from event_trading_engine.engine.execution import ExecutionConfig
from event_trading_engine.engine.risk import RiskConfig
from event_trading_engine.engine.strategy import (
    MeanReversionStrategy,
    MovingAverageCrossoverStrategy,
)

SAMPLE_CSV = Path(__file__).parent.parent / "data" / "sample_events.csv"


def _ma_strategy(run_id):
    return MovingAverageCrossoverStrategy(
        run_id=run_id,
        symbol="AAPL",
        short_window=5,
        long_window=20,
        quantity=10,
    )


def _run(db_session, run_id=None, save_events=False, save_snapshots=False):
    rid = run_id or uuid4()
    svc = SimulationService(db_session)
    result = svc.run_backtest_from_csv(
        run_id=rid,
        csv_path=SAMPLE_CSV,
        strategy=_ma_strategy(rid),
        risk_config=RiskConfig(),
        execution_config=ExecutionConfig(slippage_bps=5.0, fee_rate=0.001),
        save_events=save_events,
        save_snapshots=save_snapshots,
    )
    db_session.commit()
    return rid, result


# ---------------------------------------------------------------------------
# Run record lifecycle
# ---------------------------------------------------------------------------


def test_service_creates_run_record(db_session):
    rid, _ = _run(db_session)
    svc = SimulationService(db_session)
    run = svc.get_run(str(rid))
    assert run is not None
    assert run.id == str(rid)


def test_run_status_is_completed(db_session):
    rid, _ = _run(db_session)
    svc = SimulationService(db_session)
    run = svc.get_run(str(rid))
    assert run.status == "COMPLETED"


def test_run_ended_at_is_set(db_session):
    rid, _ = _run(db_session)
    svc = SimulationService(db_session)
    run = svc.get_run(str(rid))
    assert run.ended_at is not None


def test_list_runs_after_two_runs(db_session):
    _run(db_session)
    _run(db_session)
    svc = SimulationService(db_session)
    runs = svc.list_runs()
    assert len(runs) == 2


# ---------------------------------------------------------------------------
# Trades persisted
# ---------------------------------------------------------------------------


def test_trades_are_persisted(db_session):
    rid, result = _run(db_session)
    svc = SimulationService(db_session)
    stored = svc.get_trades(str(rid))
    assert len(stored) == len(result.trades)


def test_trade_count_matches_engine_result(db_session):
    rid, result = _run(db_session)
    svc = SimulationService(db_session)
    stored = svc.get_trades(str(rid))
    assert len(stored) == 2


def test_first_stored_trade_is_buy(db_session):
    rid, _ = _run(db_session)
    svc = SimulationService(db_session)
    stored = svc.get_trades(str(rid))
    assert stored[0].side == "BUY"


def test_fill_prices_match_engine_output(db_session):
    rid, result = _run(db_session)
    svc = SimulationService(db_session)
    stored = svc.get_trades(str(rid))
    for t_db, t_engine in zip(stored, result.trades):
        assert t_db.fill_price == pytest.approx(t_engine.fill_price, rel=1e-5)


# ---------------------------------------------------------------------------
# Positions persisted
# ---------------------------------------------------------------------------


def test_positions_are_persisted(db_session):
    rid, result = _run(db_session)
    svc = SimulationService(db_session)
    stored = svc.get_positions(str(rid))
    # One AAPL position (flat at 0 quantity after sell)
    assert len(stored) == len(result.positions)


def test_position_quantity_matches_engine(db_session):
    rid, result = _run(db_session)
    svc = SimulationService(db_session)
    stored = svc.get_positions(str(rid))
    stored_by_symbol = {p.symbol: p for p in stored}
    for eng_pos in result.positions:
        assert stored_by_symbol[eng_pos.symbol].quantity == eng_pos.quantity


# ---------------------------------------------------------------------------
# Signals and orders persisted
# ---------------------------------------------------------------------------


def test_signals_are_persisted(db_session):
    rid, result = _run(db_session)
    svc = SimulationService(db_session)
    stored = svc.get_signals(str(rid))
    assert len(stored) == len(result.signals)


def test_orders_are_persisted(db_session):
    rid, result = _run(db_session)
    svc = SimulationService(db_session)
    stored = svc.get_orders(str(rid))
    assert len(stored) == len(result.orders)


# ---------------------------------------------------------------------------
# Optional event and snapshot persistence
# ---------------------------------------------------------------------------


def test_events_saved_when_requested(db_session):
    rid, _ = _run(db_session, save_events=True)
    from event_trading_engine.app.db.models import MarketEventModel
    count = db_session.query(MarketEventModel).filter(
        MarketEventModel.run_id == str(rid)
    ).count()
    assert count == 47  # matches sample CSV row count


def test_events_not_saved_by_default(db_session):
    rid, _ = _run(db_session, save_events=False)
    from event_trading_engine.app.db.models import MarketEventModel
    count = db_session.query(MarketEventModel).filter(
        MarketEventModel.run_id == str(rid)
    ).count()
    assert count == 0


def test_snapshots_saved_when_requested(db_session):
    rid, result = _run(db_session, save_snapshots=True)
    svc = SimulationService(db_session)
    stored = svc.get_snapshots(str(rid))
    assert len(stored) == len(result.snapshots)


def test_snapshots_not_saved_by_default(db_session):
    rid, _ = _run(db_session, save_snapshots=False)
    svc = SimulationService(db_session)
    assert svc.get_snapshots(str(rid)) == []


# ---------------------------------------------------------------------------
# Mean reversion strategy also persists correctly
# ---------------------------------------------------------------------------


def test_mean_reversion_run_is_persisted(db_session):
    rid = uuid4()
    svc = SimulationService(db_session)
    strategy = MeanReversionStrategy(
        run_id=rid,
        symbol="AAPL",
        window=15,
        z_threshold=1.5,
        quantity=10,
    )
    svc.run_backtest_from_csv(
        run_id=rid,
        csv_path=SAMPLE_CSV,
        strategy=strategy,
    )
    db_session.commit()
    run = svc.get_run(str(rid))
    assert run is not None
    assert run.strategy_name == "mean_reversion"
    assert run.status == "COMPLETED"


# ---------------------------------------------------------------------------
# Duplicate run_id raises integrity error (each run must be unique)
# ---------------------------------------------------------------------------


def test_duplicate_run_id_raises(db_session):
    from sqlalchemy.exc import IntegrityError

    rid = uuid4()
    _run(db_session, run_id=rid)
    db_session.rollback()  # reset after successful commit
    with pytest.raises(IntegrityError):
        _run(db_session, run_id=rid)
