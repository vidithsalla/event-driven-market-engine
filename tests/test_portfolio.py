"""Tests for PortfolioState: buy/sell accounting, PnL, and duplicate events."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from event_trading_engine.engine.events import (
    EventType,
    MarketEvent,
    OrderSide,
    Trade,
)
from event_trading_engine.engine.portfolio import PortfolioState

RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TS = datetime(2026, 5, 3, 9, 30, tzinfo=timezone.utc)


def _state(cash: float = 100_000.0) -> PortfolioState:
    return PortfolioState(run_id=RUN_ID, initial_cash=cash)


def _buy(qty: int, price: float, fee: float = 0.0) -> Trade:
    return Trade(
        trade_id=uuid.uuid4(),
        run_id=RUN_ID,
        order_id=uuid.uuid4(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=qty,
        fill_price=price,
        fee=fee,
        timestamp=TS,
    )


def _sell(qty: int, price: float, fee: float = 0.0) -> Trade:
    return Trade(
        trade_id=uuid.uuid4(),
        run_id=RUN_ID,
        order_id=uuid.uuid4(),
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=qty,
        fill_price=price,
        fee=fee,
        timestamp=TS,
    )


def _tick(price: float, symbol: str = "AAPL") -> MarketEvent:
    return MarketEvent(
        event_id=uuid.uuid4(),
        timestamp=TS,
        symbol=symbol,
        event_type=EventType.PRICE_TICK,
        price=price,
        volume=100,
    )


# ---------------------------------------------------------------------------
# Buy accounting
# ---------------------------------------------------------------------------


def test_buy_updates_position_quantity():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    assert state.positions["AAPL"].quantity == 10


def test_buy_sets_average_cost():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    assert state.positions["AAPL"].average_cost == 100.0


def test_buy_reduces_cash():
    state = _state(100_000.0)
    state.apply_trade(_buy(10, 100.0, fee=1.0))
    assert state.cash == 100_000.0 - 10 * 100.0 - 1.0


def test_second_buy_updates_average_cost_correctly():
    """Weighted average cost: (qty1*p1 + qty2*p2) / (qty1 + qty2)."""
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_buy(10, 120.0))
    pos = state.positions["AAPL"]
    assert pos.quantity == 20
    assert pos.average_cost == pytest.approx(110.0)


def test_buy_with_different_lots_correct_avg_cost():
    state = _state()
    state.apply_trade(_buy(5, 100.0))
    state.apply_trade(_buy(15, 200.0))
    pos = state.positions["AAPL"]
    expected_avg = (5 * 100.0 + 15 * 200.0) / 20
    assert pos.average_cost == pytest.approx(expected_avg)


# ---------------------------------------------------------------------------
# Sell accounting
# ---------------------------------------------------------------------------


def test_sell_reduces_quantity():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(5, 110.0))
    assert state.positions["AAPL"].quantity == 5


def test_sell_realizes_profit():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(10, 110.0))
    realized = state.positions["AAPL"].realized_pnl
    assert realized == pytest.approx(100.0)  # 10 * (110 - 100)


def test_sell_realizes_loss():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(10, 90.0))
    realized = state.positions["AAPL"].realized_pnl
    assert realized == pytest.approx(-100.0)


def test_sell_fee_reduces_realized_pnl():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(10, 110.0, fee=5.0))
    realized = state.positions["AAPL"].realized_pnl
    assert realized == pytest.approx(95.0)  # 10*(110-100) - 5


def test_sell_to_flat_position_zeroes_average_cost():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(10, 105.0))
    pos = state.positions["AAPL"]
    assert pos.quantity == 0
    assert pos.average_cost == 0.0


def test_sell_increases_cash():
    state = _state(50_000.0)
    state.apply_trade(_buy(10, 100.0))
    cash_before = state.cash
    state.apply_trade(_sell(10, 110.0, fee=1.0))
    assert state.cash == pytest.approx(cash_before + 10 * 110.0 - 1.0)


# ---------------------------------------------------------------------------
# Unrealized PnL
# ---------------------------------------------------------------------------


def test_unrealized_pnl_updates_on_price_event():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.on_market_event(_tick(110.0))
    assert state.positions["AAPL"].unrealized_pnl == pytest.approx(100.0)


def test_unrealized_pnl_negative_when_price_falls():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.on_market_event(_tick(90.0))
    assert state.positions["AAPL"].unrealized_pnl == pytest.approx(-100.0)


def test_unrealized_zero_after_flat_sell():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(10, 100.0))
    assert state.positions["AAPL"].unrealized_pnl == pytest.approx(0.0)


def test_total_pnl_is_realized_plus_unrealized():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(5, 110.0))  # realized += 5*(110-100) = 50
    state.on_market_event(_tick(115.0))  # unrealized = 5*(115-100) = 75
    total = state.get_total_realized_pnl() + state.get_total_unrealized_pnl()
    assert total == pytest.approx(125.0)


# ---------------------------------------------------------------------------
# Duplicate event guard
# ---------------------------------------------------------------------------


def test_duplicate_event_detected():
    state = _state()
    eid = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    state.mark_event_seen(eid)
    assert state.is_duplicate_event(eid) is True


def test_new_event_not_duplicate():
    state = _state()
    assert state.is_duplicate_event(uuid.uuid4()) is False


# ---------------------------------------------------------------------------
# Market open/close
# ---------------------------------------------------------------------------


def test_market_open_event_sets_flag():
    state = _state()
    e = MarketEvent(
        event_id=uuid.uuid4(),
        timestamp=TS,
        symbol="AAPL",
        event_type=EventType.MARKET_OPEN,
    )
    state.on_market_event(e)
    assert state.market_open is True


def test_market_close_event_clears_flag():
    state = _state()
    state.market_open = True
    e = MarketEvent(
        event_id=uuid.uuid4(),
        timestamp=TS,
        symbol="AAPL",
        event_type=EventType.MARKET_CLOSE,
    )
    state.on_market_event(e)
    assert state.market_open is False


# ---------------------------------------------------------------------------
# Win rate
# ---------------------------------------------------------------------------


def test_win_rate_zero_when_no_sells():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    assert state.get_win_rate() == 0.0


def test_win_rate_one_when_all_wins():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(10, 110.0))
    assert state.get_win_rate() == pytest.approx(1.0)


def test_win_rate_zero_when_all_losses():
    state = _state()
    state.apply_trade(_buy(10, 100.0))
    state.apply_trade(_sell(10, 90.0))
    assert state.get_win_rate() == pytest.approx(0.0)
