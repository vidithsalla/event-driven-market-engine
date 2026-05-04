"""Integration tests for BacktestRunner end-to-end."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from event_trading_engine.engine.backtest import BacktestRunner
from event_trading_engine.engine.events import EventType, OrderSide, OrderStatus
from event_trading_engine.engine.execution import ExecutionConfig
from event_trading_engine.engine.risk import RiskConfig
from event_trading_engine.engine.strategy import MovingAverageCrossoverStrategy

SAMPLE_CSV = Path(__file__).parent.parent / "data" / "sample_events.csv"
RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
TS = datetime(2026, 5, 3, 9, 30, tzinfo=timezone.utc)


def _ma_strategy(run_id: uuid.UUID) -> MovingAverageCrossoverStrategy:
    return MovingAverageCrossoverStrategy(
        run_id=run_id,
        symbol="AAPL",
        short_window=5,
        long_window=20,
        quantity=10,
    )


def _runner(run_id: uuid.UUID | None = None) -> BacktestRunner:
    rid = run_id or RUN_ID
    return BacktestRunner(
        run_id=rid,
        strategy=_ma_strategy(rid),
        initial_cash=100_000.0,
        risk_config=RiskConfig(),
        execution_config=ExecutionConfig(slippage_bps=5.0, fee_rate=0.001),
    )


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------


def test_load_events_from_csv():
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    assert len(events) == 47  # 1 OPEN + 45 PRICE_TICK + 1 CLOSE


def test_first_event_is_market_open():
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    assert events[0].event_type == EventType.MARKET_OPEN


def test_last_event_is_market_close():
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    assert events[-1].event_type == EventType.MARKET_CLOSE


# ---------------------------------------------------------------------------
# Full backtest from sample CSV
# ---------------------------------------------------------------------------


def test_full_backtest_produces_two_trades():
    """Sample CSV has a BUY and a SELL signal from MA(5,20) crossovers."""
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    runner = _runner()
    result = runner.run(events)
    assert len(result.trades) == 2


def test_full_backtest_first_trade_is_buy():
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    runner = _runner()
    result = runner.run(events)
    assert result.trades[0].side == OrderSide.BUY


def test_full_backtest_second_trade_is_sell():
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    runner = _runner()
    result = runner.run(events)
    assert result.trades[1].side == OrderSide.SELL


def test_full_backtest_position_is_flat_at_end():
    """After BUY + SELL, position quantity should be 0."""
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    runner = _runner()
    result = runner.run(events)
    aapl = next((p for p in result.positions if p.symbol == "AAPL"), None)
    assert aapl is not None
    assert aapl.quantity == 0


def test_full_backtest_metrics_trade_count():
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    runner = _runner()
    result = runner.run(events)
    assert result.metrics.trade_count == 2


# ---------------------------------------------------------------------------
# Determinism: same input → identical output
# ---------------------------------------------------------------------------


def test_backtest_is_deterministic():
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)

    rid = uuid.UUID("00000000-0000-0000-0000-000000000010")
    r1 = BacktestRunner(
        run_id=rid,
        strategy=_ma_strategy(rid),
        risk_config=RiskConfig(),
        execution_config=ExecutionConfig(slippage_bps=5.0, fee_rate=0.001),
    )
    r2 = BacktestRunner(
        run_id=rid,
        strategy=_ma_strategy(rid),
        risk_config=RiskConfig(),
        execution_config=ExecutionConfig(slippage_bps=5.0, fee_rate=0.001),
    )

    result1 = r1.run(events)
    result2 = r2.run(events)

    # Metrics that should be identical
    assert result1.metrics.total_pnl == result2.metrics.total_pnl
    assert result1.metrics.realized_pnl == result2.metrics.realized_pnl
    assert result1.metrics.trade_count == result2.metrics.trade_count

    # Trade fill prices must match
    for t1, t2 in zip(result1.trades, result2.trades):
        assert t1.fill_price == t2.fill_price
        assert t1.fee == t2.fee
        assert t1.side == t2.side


# ---------------------------------------------------------------------------
# Duplicate event handling
# ---------------------------------------------------------------------------


def test_duplicate_events_do_not_create_duplicate_trades():
    """Replaying the same events twice should not generate extra trades."""
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    doubled = events + events  # All event_ids repeated
    runner = _runner()
    result = runner.run(doubled)
    assert len(result.trades) == 2  # Same as single pass


# ---------------------------------------------------------------------------
# Risk rejection appears in orders list
# ---------------------------------------------------------------------------


def test_risk_rejection_recorded_in_orders():
    """When max_loss is 0, every order should be rejected."""
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    strict_risk = RiskConfig(max_loss=0.0)
    runner = BacktestRunner(
        run_id=RUN_ID,
        strategy=_ma_strategy(RUN_ID),
        risk_config=strict_risk,
        execution_config=ExecutionConfig(),
    )
    result = runner.run(events)
    rejected = [o for o in result.orders if o.status == OrderStatus.REJECTED_RISK]
    assert len(rejected) >= 1


def test_market_closed_rejects_orders():
    """Events without a preceding MARKET_OPEN should reject all orders."""
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    # Strip the MARKET_OPEN event
    no_open = [e for e in events if e.event_type != EventType.MARKET_OPEN]
    runner = _runner()
    result = runner.run(no_open)
    rejected = [o for o in result.orders if o.status == OrderStatus.REJECTED_RISK]
    assert len(rejected) >= 1


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def test_snapshots_count_equals_event_count():
    events = BacktestRunner.load_events_from_csv(SAMPLE_CSV)
    runner = _runner()
    result = runner.run(events)
    assert len(result.snapshots) == len(events)
