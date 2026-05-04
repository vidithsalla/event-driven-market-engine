"""Tests for RiskEngine: all five rejection conditions plus acceptance."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from event_trading_engine.engine.events import OrderSide, OrderStatus, SimulatedOrder, Trade
from event_trading_engine.engine.portfolio import PortfolioState
from event_trading_engine.engine.risk import RiskConfig, RiskEngine

RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TS = datetime(2026, 5, 3, 9, 30, tzinfo=timezone.utc)


def _state(open: bool = True, cash: float = 100_000.0) -> PortfolioState:
    s = PortfolioState(run_id=RUN_ID, initial_cash=cash)
    s.market_open = open
    return s


def _order(
    qty: int = 10,
    price: float = 100.0,
    side: OrderSide = OrderSide.BUY,
    symbol: str = "AAPL",
) -> SimulatedOrder:
    return SimulatedOrder(
        order_id=uuid.uuid4(),
        run_id=RUN_ID,
        signal_id=uuid.uuid4(),
        symbol=symbol,
        side=side,
        quantity=qty,
        requested_price=price,
    )


def _buy_trade(qty: int, price: float) -> Trade:
    return Trade(
        trade_id=uuid.uuid4(),
        run_id=RUN_ID,
        order_id=uuid.uuid4(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=qty,
        fill_price=price,
        fee=0.0,
        timestamp=TS,
    )


# ---------------------------------------------------------------------------
# Acceptance
# ---------------------------------------------------------------------------


def test_valid_order_is_accepted():
    engine = RiskEngine(RiskConfig())
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    ok, reason = engine.check(_order(), state)
    assert ok is True
    assert reason == ""


# ---------------------------------------------------------------------------
# Market closed
# ---------------------------------------------------------------------------


def test_rejects_when_market_closed():
    engine = RiskEngine(RiskConfig())
    state = _state(open=False)
    ok, reason = engine.check(_order(), state)
    assert ok is False
    assert "market is closed" in reason


# ---------------------------------------------------------------------------
# Max position quantity
# ---------------------------------------------------------------------------


def test_rejects_above_max_position_quantity():
    config = RiskConfig(max_position_quantity=15)
    engine = RiskEngine(config)
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    state.apply_trade(_buy_trade(10, 100.0))
    # Trying to buy 10 more → total 20 > 15
    ok, reason = engine.check(_order(qty=10), state)
    assert ok is False
    assert "max_position_quantity" in reason


def test_accepts_at_max_position_quantity_boundary():
    config = RiskConfig(max_position_quantity=20)
    engine = RiskEngine(config)
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    state.apply_trade(_buy_trade(10, 100.0))
    # 10 existing + 10 new = 20 = limit → should pass
    ok, _ = engine.check(_order(qty=10), state)
    assert ok is True


# ---------------------------------------------------------------------------
# Max symbol notional
# ---------------------------------------------------------------------------


def test_rejects_above_max_symbol_notional():
    config = RiskConfig(max_symbol_notional=500.0)
    engine = RiskEngine(config)
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    # 10 * 100 = 1000 > 500
    ok, reason = engine.check(_order(qty=10, price=100.0), state)
    assert ok is False
    assert "max_symbol_notional" in reason


# ---------------------------------------------------------------------------
# Max total notional
# ---------------------------------------------------------------------------


def test_rejects_above_max_total_notional():
    config = RiskConfig(max_total_notional=1_500.0)
    engine = RiskEngine(config)
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    state.latest_prices["MSFT"] = 100.0
    # Already hold 10 AAPL @ 100 = 1000 notional
    state.apply_trade(
        Trade(
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
    )
    # Buying 10 MSFT @ 100 would add 1000 → total 2000 > 1500
    ok, reason = engine.check(_order(qty=10, price=100.0, symbol="MSFT"), state)
    assert ok is False
    assert "max_total_notional" in reason


# ---------------------------------------------------------------------------
# Max loss
# ---------------------------------------------------------------------------


def test_rejects_when_max_loss_exceeded():
    config = RiskConfig(max_loss=100.0)
    engine = RiskEngine(config)
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    # Simulate a big unrealized loss
    state.apply_trade(_buy_trade(10, 200.0))
    state.latest_prices["AAPL"] = 100.0  # position is now worth 1000, cost 2000 → unrealized -1000
    state.positions["AAPL"].unrealized_pnl = -1000.0

    ok, reason = engine.check(_order(), state)
    assert ok is False
    assert "max_loss" in reason


# ---------------------------------------------------------------------------
# Sell insufficient position
# ---------------------------------------------------------------------------


def test_rejects_sell_with_no_position():
    engine = RiskEngine(RiskConfig())
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    ok, reason = engine.check(_order(qty=5, side=OrderSide.SELL), state)
    assert ok is False
    assert "insufficient position" in reason


def test_rejects_sell_exceeding_position():
    engine = RiskEngine(RiskConfig())
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    state.apply_trade(_buy_trade(5, 100.0))
    ok, reason = engine.check(_order(qty=10, side=OrderSide.SELL), state)
    assert ok is False
    assert "insufficient position" in reason


def test_accepts_sell_within_position():
    engine = RiskEngine(RiskConfig())
    state = _state()
    state.latest_prices["AAPL"] = 100.0
    state.apply_trade(_buy_trade(10, 100.0))
    ok, _ = engine.check(_order(qty=10, side=OrderSide.SELL), state)
    assert ok is True


# ---------------------------------------------------------------------------
# apply_rejection helper
# ---------------------------------------------------------------------------


def test_apply_rejection_sets_order_status():
    engine = RiskEngine(RiskConfig())
    order = _order()
    engine.apply_rejection(order, "test reason")
    assert order.status == OrderStatus.REJECTED_RISK
    assert order.rejection_reason == "test reason"
