"""Tests for MarketEvent and other domain model validation."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from event_trading_engine.engine.events import (
    EventType,
    MarketEvent,
    OrderSide,
    OrderStatus,
    Signal,
    SignalAction,
    SimulatedOrder,
)


def _event(**kwargs) -> dict:
    defaults = dict(
        event_id=str(uuid.uuid4()),
        timestamp="2026-05-03T09:30:00Z",
        symbol="AAPL",
        event_type="PRICE_TICK",
        price=100.0,
        volume=500,
        source="SIMULATED",
    )
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Valid event parsing
# ---------------------------------------------------------------------------


def test_valid_price_tick_parses():
    e = MarketEvent(**_event())
    assert e.symbol == "AAPL"
    assert e.event_type == EventType.PRICE_TICK
    assert e.price == 100.0
    assert e.volume == 500


def test_symbol_is_uppercased():
    e = MarketEvent(**_event(symbol="aapl"))
    assert e.symbol == "AAPL"


def test_market_open_allows_zero_price():
    e = MarketEvent(**_event(event_type="MARKET_OPEN", price=0.0, volume=0))
    assert e.event_type == EventType.MARKET_OPEN


def test_market_close_allows_zero_price():
    e = MarketEvent(**_event(event_type="MARKET_CLOSE", price=0.0, volume=0))
    assert e.event_type == EventType.MARKET_CLOSE


# ---------------------------------------------------------------------------
# Validation rejections
# ---------------------------------------------------------------------------


def test_negative_price_rejected():
    with pytest.raises(ValidationError):
        MarketEvent(**_event(price=-1.0))


def test_zero_price_for_price_tick_rejected():
    with pytest.raises(ValidationError):
        MarketEvent(**_event(event_type="PRICE_TICK", price=0.0))


def test_empty_symbol_rejected():
    with pytest.raises(ValidationError):
        MarketEvent(**_event(symbol=""))


def test_whitespace_symbol_rejected():
    with pytest.raises(ValidationError):
        MarketEvent(**_event(symbol="   "))


def test_negative_volume_rejected():
    with pytest.raises(ValidationError):
        MarketEvent(**_event(volume=-1))


def test_invalid_event_type_rejected():
    with pytest.raises(ValidationError):
        MarketEvent(**_event(event_type="NOT_AN_EVENT"))


def test_missing_timestamp_rejected():
    data = _event()
    del data["timestamp"]
    with pytest.raises(ValidationError):
        MarketEvent(**data)


# ---------------------------------------------------------------------------
# Duplicate event detection (handled by PortfolioState, not MarketEvent itself)
# but we verify that identical event_ids parse fine as the same object.
# ---------------------------------------------------------------------------


def test_same_event_id_parses_twice():
    fixed_id = str(uuid.uuid4())
    e1 = MarketEvent(**_event(event_id=fixed_id))
    e2 = MarketEvent(**_event(event_id=fixed_id, price=101.0))
    assert e1.event_id == e2.event_id


# ---------------------------------------------------------------------------
# Signal model
# ---------------------------------------------------------------------------


def test_signal_model_roundtrip():
    run_id = uuid.uuid4()
    s = Signal(
        signal_id=uuid.uuid4(),
        run_id=run_id,
        timestamp=datetime.fromisoformat("2026-05-03T09:31:00+00:00"),
        symbol="AAPL",
        action=SignalAction.BUY,
        quantity=10,
        reason="test",
    )
    assert s.action == SignalAction.BUY
    assert s.quantity == 10


# ---------------------------------------------------------------------------
# SimulatedOrder model
# ---------------------------------------------------------------------------


def test_order_default_status_is_created():
    o = SimulatedOrder(
        order_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        signal_id=uuid.uuid4(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=5,
        requested_price=100.0,
    )
    assert o.status == OrderStatus.CREATED
    assert o.rejection_reason == ""
