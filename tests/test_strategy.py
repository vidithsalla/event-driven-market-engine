"""Tests for MovingAverageCrossoverStrategy and MeanReversionStrategy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from event_trading_engine.engine.events import EventType, MarketEvent, SignalAction
from event_trading_engine.engine.portfolio import PortfolioState
from event_trading_engine.engine.strategy import (
    MeanReversionStrategy,
    MovingAverageCrossoverStrategy,
)

RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TS = datetime(2026, 5, 3, 9, 30, tzinfo=timezone.utc)


def _tick(price: float, symbol: str = "AAPL") -> MarketEvent:
    return MarketEvent(
        event_id=uuid.uuid4(),
        timestamp=TS,
        symbol=symbol,
        event_type=EventType.PRICE_TICK,
        price=price,
        volume=100,
    )


def _state() -> PortfolioState:
    return PortfolioState(run_id=RUN_ID, initial_cash=100_000.0)


# ---------------------------------------------------------------------------
# MovingAverageCrossoverStrategy
# ---------------------------------------------------------------------------


def test_ma_no_signal_before_enough_data():
    strategy = MovingAverageCrossoverStrategy(
        run_id=RUN_ID, symbol="AAPL", short_window=3, long_window=5, quantity=10
    )
    state = _state()
    for _ in range(4):
        signal = strategy.on_event(_tick(100.0), state)
    assert signal is None


def test_ma_no_signal_at_exact_long_window_flat_prices():
    """At exactly long_window ticks of flat prices, prev is None so no signal."""
    strategy = MovingAverageCrossoverStrategy(
        run_id=RUN_ID, symbol="AAPL", short_window=3, long_window=5, quantity=10
    )
    state = _state()
    for _ in range(5):
        signal = strategy.on_event(_tick(100.0), state)
    assert signal is None


def test_ma_emits_buy_on_upward_cross():
    """Short MA crosses above long MA when price spikes after flat period."""
    strategy = MovingAverageCrossoverStrategy(
        run_id=RUN_ID, symbol="AAPL", short_window=3, long_window=5, quantity=10
    )
    state = _state()
    # Fill deque with 5 flat prices (establishes baseline, sets _prev_short_above=False)
    for _ in range(5):
        strategy.on_event(_tick(100.0), state)
    # Spike upward: short MA will exceed long MA
    signal = strategy.on_event(_tick(130.0), state)
    assert signal is not None
    assert signal.action == SignalAction.BUY
    assert signal.quantity == 10
    assert signal.symbol == "AAPL"


def test_ma_emits_sell_on_downward_cross():
    """After an upward cross, a downward cross emits SELL."""
    strategy = MovingAverageCrossoverStrategy(
        run_id=RUN_ID, symbol="AAPL", short_window=3, long_window=5, quantity=10
    )
    state = _state()
    # Flat baseline
    for _ in range(5):
        strategy.on_event(_tick(100.0), state)
    # Spike up → BUY signal (short crosses above long)
    for _ in range(3):
        strategy.on_event(_tick(130.0), state)
    # Now crash → short MA drops below long MA → SELL
    signal = None
    for _ in range(3):
        s = strategy.on_event(_tick(60.0), state)
        if s is not None:
            signal = s
            break
    assert signal is not None
    assert signal.action == SignalAction.SELL


def test_ma_no_repeat_signal_same_direction():
    """Signal fires only on the crossing tick, not on every subsequent tick."""
    strategy = MovingAverageCrossoverStrategy(
        run_id=RUN_ID, symbol="AAPL", short_window=3, long_window=5, quantity=10
    )
    state = _state()
    for _ in range(5):
        strategy.on_event(_tick(100.0), state)
    # First spike → BUY
    strategy.on_event(_tick(130.0), state)
    # Continued high prices → no more signals
    signals = [strategy.on_event(_tick(130.0), state) for _ in range(5)]
    buy_signals = [s for s in signals if s is not None and s.action == SignalAction.BUY]
    assert len(buy_signals) == 0


def test_ma_ignores_different_symbol():
    strategy = MovingAverageCrossoverStrategy(
        run_id=RUN_ID, symbol="AAPL", short_window=3, long_window=5, quantity=10
    )
    state = _state()
    for _ in range(6):
        signal = strategy.on_event(_tick(130.0, symbol="MSFT"), state)
    assert signal is None


def test_ma_invalid_windows_raise():
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(
            run_id=RUN_ID, symbol="AAPL", short_window=10, long_window=5
        )


# ---------------------------------------------------------------------------
# MeanReversionStrategy
# ---------------------------------------------------------------------------


def test_mr_no_signal_before_window_full():
    strategy = MeanReversionStrategy(
        run_id=RUN_ID, symbol="AAPL", window=5, z_threshold=1.5, quantity=10
    )
    state = _state()
    for _ in range(4):
        signal = strategy.on_event(_tick(100.0), state)
    assert signal is None


def test_mr_emits_buy_when_z_below_negative_threshold():
    """Price well below rolling mean triggers BUY (expect reversion up)."""
    strategy = MeanReversionStrategy(
        run_id=RUN_ID, symbol="AAPL", window=5, z_threshold=1.0, quantity=10
    )
    state = _state()
    # Establish mean ≈ 100 with low variance
    for p in [100.0, 100.0, 100.0, 100.0]:
        strategy.on_event(_tick(p), state)
    # Price crashes well below mean → z-score very negative
    signal = strategy.on_event(_tick(50.0), state)
    assert signal is not None
    assert signal.action == SignalAction.BUY


def test_mr_emits_sell_when_z_above_positive_threshold():
    """Price well above rolling mean triggers SELL when already long."""
    strategy = MeanReversionStrategy(
        run_id=RUN_ID, symbol="AAPL", window=5, z_threshold=1.0, quantity=10
    )
    state = _state()
    state.market_open = True

    # Establish mean at ~100
    for p in [100.0, 100.0, 100.0, 100.0]:
        strategy.on_event(_tick(p), state)
    # Price crashes → BUY signal (flat position, so buy fires)
    strategy.on_event(_tick(50.0), state)
    # Manually inject a position so SELL can fire
    from event_trading_engine.engine.events import OrderSide, Trade
    trade = Trade(
        trade_id=uuid.uuid4(),
        run_id=RUN_ID,
        order_id=uuid.uuid4(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        fill_price=50.0,
        fee=0.0,
        timestamp=TS,
    )
    state.apply_trade(trade)
    state.latest_prices["AAPL"] = 50.0

    # Now feed prices that establish a new rolling mean around 100 with a spike
    for p in [98.0, 99.0, 100.0, 101.0]:
        strategy.on_event(_tick(p), state)
    # Spike far above mean → SELL signal
    signal = strategy.on_event(_tick(200.0), state)
    assert signal is not None
    assert signal.action == SignalAction.SELL


def test_mr_no_buy_when_already_long():
    """Mean reversion strategy does not double-buy when already holding a position."""
    strategy = MeanReversionStrategy(
        run_id=RUN_ID, symbol="AAPL", window=5, z_threshold=1.0, quantity=10
    )
    state = _state()
    # Inject a long position
    from event_trading_engine.engine.events import OrderSide, Trade
    state.market_open = True
    trade = Trade(
        trade_id=uuid.uuid4(),
        run_id=RUN_ID,
        order_id=uuid.uuid4(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        fill_price=100.0,
        fee=0.0,
        timestamp=TS,
    )
    state.apply_trade(trade)
    state.latest_prices["AAPL"] = 100.0

    for p in [100.0, 100.0, 100.0, 100.0]:
        strategy.on_event(_tick(p), state)
    # Price crashes — but we're already long, so no BUY
    signal = strategy.on_event(_tick(50.0), state)
    assert signal is None or signal.action != SignalAction.BUY
