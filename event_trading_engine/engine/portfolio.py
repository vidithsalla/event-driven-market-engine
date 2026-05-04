"""Portfolio state: tracks cash, positions, trades, and duplicate events.

This is a pure in-memory, single-threaded state object. No external calls.
All state transitions are driven by explicit method calls from the backtest runner.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from .events import EventType, MarketEvent, OrderSide, PortfolioSnapshot, Position, Trade


class PortfolioState:
    def __init__(self, run_id: UUID, initial_cash: float = 100_000.0) -> None:
        self.run_id = run_id
        self.initial_cash = initial_cash
        self.cash: float = initial_cash
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.market_open: bool = False
        self.latest_prices: dict[str, float] = {}

        self._seen_event_ids: set[UUID] = set()
        self._peak_equity: float = initial_cash
        self._max_drawdown: float = 0.0
        self._sell_count: int = 0
        self._sell_wins: int = 0

    # ------------------------------------------------------------------
    # Duplicate event guard
    # ------------------------------------------------------------------

    def is_duplicate_event(self, event_id: UUID) -> bool:
        return event_id in self._seen_event_ids

    def mark_event_seen(self, event_id: UUID) -> None:
        self._seen_event_ids.add(event_id)

    # ------------------------------------------------------------------
    # Market event integration
    # ------------------------------------------------------------------

    def on_market_event(self, event: MarketEvent) -> None:
        if event.event_type == EventType.MARKET_OPEN:
            self.market_open = True
        elif event.event_type == EventType.MARKET_CLOSE:
            self.market_open = False
        elif event.event_type in (EventType.PRICE_TICK, EventType.TRADE_PRINT):
            self.latest_prices[event.symbol] = event.price
            self._refresh_unrealized(event.symbol, event.price)
            self._update_drawdown()

    # ------------------------------------------------------------------
    # Trade application (buy / sell accounting)
    # ------------------------------------------------------------------

    def apply_trade(self, trade: Trade) -> None:
        self.trades.append(trade)
        symbol = trade.symbol

        if symbol not in self.positions:
            self.positions[symbol] = Position(run_id=self.run_id, symbol=symbol)

        pos = self.positions[symbol]

        if trade.side == OrderSide.BUY:
            old_qty = pos.quantity
            old_avg = pos.average_cost
            new_qty = old_qty + trade.quantity
            pos.average_cost = (old_qty * old_avg + trade.quantity * trade.fill_price) / new_qty
            pos.quantity = new_qty
            self.cash -= trade.quantity * trade.fill_price + trade.fee

        else:  # SELL
            realized = trade.quantity * (trade.fill_price - pos.average_cost) - trade.fee
            pos.realized_pnl += realized
            self._sell_count += 1
            if realized > 0:
                self._sell_wins += 1
            pos.quantity -= trade.quantity
            if pos.quantity == 0:
                pos.average_cost = 0.0
            self.cash += trade.quantity * trade.fill_price - trade.fee

        # Refresh unrealized after the position changes.
        market_price = self.latest_prices.get(symbol, trade.fill_price)
        pos.market_price = market_price
        pos.unrealized_pnl = pos.quantity * (market_price - pos.average_cost)

        self._update_drawdown()

    # ------------------------------------------------------------------
    # Computed views
    # ------------------------------------------------------------------

    def get_position(self, symbol: str) -> Position | None:
        return self.positions.get(symbol)

    def get_total_realized_pnl(self) -> float:
        return sum(p.realized_pnl for p in self.positions.values())

    def get_total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    def get_total_notional(self) -> float:
        total = 0.0
        for symbol, pos in self.positions.items():
            price = self.latest_prices.get(symbol, pos.average_cost)
            total += pos.quantity * price
        return total

    def get_equity(self) -> float:
        return self.cash + self.get_total_notional()

    def get_win_rate(self) -> float:
        if self._sell_count == 0:
            return 0.0
        return self._sell_wins / self._sell_count

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self, timestamp: datetime) -> PortfolioSnapshot:
        realized = self.get_total_realized_pnl()
        unrealized = self.get_total_unrealized_pnl()
        gross_exposure = self.get_total_notional()
        return PortfolioSnapshot(
            run_id=self.run_id,
            timestamp=timestamp,
            cash=round(self.cash, 6),
            equity=round(self.get_equity(), 6),
            gross_exposure=round(gross_exposure, 6),
            net_exposure=round(gross_exposure, 6),  # long-only in v1
            realized_pnl=round(realized, 6),
            unrealized_pnl=round(unrealized, 6),
            total_pnl=round(realized + unrealized, 6),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refresh_unrealized(self, symbol: str, price: float) -> None:
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.market_price = price
            pos.unrealized_pnl = pos.quantity * (price - pos.average_cost)

    def _update_drawdown(self) -> None:
        equity = self.get_equity()
        if equity > self._peak_equity:
            self._peak_equity = equity
        drawdown = equity - self._peak_equity
        if drawdown < self._max_drawdown:
            self._max_drawdown = drawdown
