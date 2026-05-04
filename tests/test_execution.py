"""Tests for ExecutionEngine: slippage, fees, and fill price direction."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from event_trading_engine.engine.events import OrderSide, OrderStatus, SimulatedOrder
from event_trading_engine.engine.execution import ExecutionConfig, ExecutionEngine

RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TS = datetime(2026, 5, 3, 9, 30, tzinfo=timezone.utc)


def _order(side: OrderSide = OrderSide.BUY, qty: int = 10, price: float = 100.0) -> SimulatedOrder:
    return SimulatedOrder(
        order_id=uuid.uuid4(),
        run_id=RUN_ID,
        signal_id=uuid.uuid4(),
        symbol="AAPL",
        side=side,
        quantity=qty,
        requested_price=price,
    )


# ---------------------------------------------------------------------------
# Buy slippage
# ---------------------------------------------------------------------------


def test_buy_fill_price_includes_slippage():
    config = ExecutionConfig(slippage_bps=10.0, fee_rate=0.0)
    engine = ExecutionEngine(config)
    trade = engine.execute(_order(OrderSide.BUY), market_price=100.0, timestamp=TS)
    expected = 100.0 * (1 + 10 / 10_000)
    assert trade.fill_price == pytest.approx(expected)


def test_buy_fill_price_higher_than_market():
    engine = ExecutionEngine(ExecutionConfig(slippage_bps=5.0, fee_rate=0.0))
    trade = engine.execute(_order(OrderSide.BUY), market_price=100.0, timestamp=TS)
    assert trade.fill_price > 100.0


# ---------------------------------------------------------------------------
# Sell slippage
# ---------------------------------------------------------------------------


def test_sell_fill_price_includes_slippage():
    config = ExecutionConfig(slippage_bps=10.0, fee_rate=0.0)
    engine = ExecutionEngine(config)
    trade = engine.execute(_order(OrderSide.SELL), market_price=100.0, timestamp=TS)
    expected = 100.0 * (1 - 10 / 10_000)
    assert trade.fill_price == pytest.approx(expected)


def test_sell_fill_price_lower_than_market():
    engine = ExecutionEngine(ExecutionConfig(slippage_bps=5.0, fee_rate=0.0))
    trade = engine.execute(_order(OrderSide.SELL), market_price=100.0, timestamp=TS)
    assert trade.fill_price < 100.0


# ---------------------------------------------------------------------------
# Fee calculation
# ---------------------------------------------------------------------------


def test_fee_calculated_on_fill_price():
    config = ExecutionConfig(slippage_bps=0.0, fee_rate=0.01)
    engine = ExecutionEngine(config)
    trade = engine.execute(_order(qty=10), market_price=100.0, timestamp=TS)
    assert trade.fee == pytest.approx(10 * 100.0 * 0.01)


def test_zero_fee_rate_produces_zero_fee():
    config = ExecutionConfig(slippage_bps=0.0, fee_rate=0.0)
    engine = ExecutionEngine(config)
    trade = engine.execute(_order(), market_price=100.0, timestamp=TS)
    assert trade.fee == pytest.approx(0.0)


def test_fee_proportional_to_quantity():
    config = ExecutionConfig(slippage_bps=0.0, fee_rate=0.001)
    engine = ExecutionEngine(config)
    t5 = engine.execute(_order(qty=5), market_price=100.0, timestamp=TS)
    t10 = engine.execute(_order(qty=10), market_price=100.0, timestamp=TS)
    assert t10.fee == pytest.approx(t5.fee * 2)


# ---------------------------------------------------------------------------
# Order status mutation
# ---------------------------------------------------------------------------


def test_execute_sets_order_status_to_filled():
    engine = ExecutionEngine(ExecutionConfig())
    order = _order()
    engine.execute(order, market_price=100.0, timestamp=TS)
    assert order.status == OrderStatus.FILLED


# ---------------------------------------------------------------------------
# Trade fields
# ---------------------------------------------------------------------------


def test_trade_has_correct_symbol_and_side():
    engine = ExecutionEngine(ExecutionConfig())
    order = _order(side=OrderSide.SELL)
    trade = engine.execute(order, market_price=100.0, timestamp=TS)
    assert trade.symbol == "AAPL"
    assert trade.side == OrderSide.SELL


def test_trade_quantity_matches_order():
    engine = ExecutionEngine(ExecutionConfig())
    order = _order(qty=7)
    trade = engine.execute(order, market_price=100.0, timestamp=TS)
    assert trade.quantity == 7


def test_trade_timestamp_matches_provided():
    engine = ExecutionEngine(ExecutionConfig())
    trade = engine.execute(_order(), market_price=100.0, timestamp=TS)
    assert trade.timestamp == TS
