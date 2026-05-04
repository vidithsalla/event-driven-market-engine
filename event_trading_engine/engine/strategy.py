"""Strategy interface and concrete strategy implementations.

Strategies receive market events and current portfolio state. They return
signals. They must not execute orders, write to any store, or mutate state.
"""
from __future__ import annotations

import statistics
from collections import deque
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID, uuid4

from .events import EventType, MarketEvent, Signal, SignalAction

if TYPE_CHECKING:
    from .portfolio import PortfolioState


@runtime_checkable
class Strategy(Protocol):
    name: str

    def on_event(self, event: MarketEvent, state: PortfolioState) -> Signal | None:
        ...


class MovingAverageCrossoverStrategy:
    """Buy when short MA crosses above long MA; sell when it crosses below.

    A signal is emitted only on the crossing tick, not on every tick where
    short_ma > long_ma. This prevents duplicate orders on every subsequent tick.
    """

    name = "moving_average_crossover"

    def __init__(
        self,
        run_id: UUID,
        symbol: str,
        short_window: int = 5,
        long_window: int = 20,
        quantity: int = 10,
    ) -> None:
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
        if short_window < 1 or long_window < 2:
            raise ValueError("window sizes must be positive")
        self.run_id = run_id
        self.symbol = symbol.upper()
        self.short_window = short_window
        self.long_window = long_window
        self.quantity = quantity
        self._prices: deque[float] = deque(maxlen=long_window)
        self._prev_short_above: bool | None = None

    def on_event(self, event: MarketEvent, state: PortfolioState) -> Signal | None:
        if event.symbol != self.symbol:
            return None
        if event.event_type not in (EventType.PRICE_TICK, EventType.TRADE_PRINT):
            return None

        self._prices.append(event.price)

        if len(self._prices) < self.long_window:
            return None

        prices = list(self._prices)
        short_ma = sum(prices[-self.short_window :]) / self.short_window
        long_ma = sum(prices) / len(prices)
        short_above = short_ma > long_ma

        signal: Signal | None = None
        if self._prev_short_above is not None and short_above != self._prev_short_above:
            action = SignalAction.BUY if short_above else SignalAction.SELL
            direction = "up" if short_above else "down"
            signal = Signal(
                signal_id=uuid4(),
                run_id=self.run_id,
                timestamp=event.timestamp,
                symbol=self.symbol,
                action=action,
                quantity=self.quantity,
                reason=f"ma_cross_{direction} short={short_ma:.4f} long={long_ma:.4f}",
            )

        self._prev_short_above = short_above
        return signal


class MeanReversionStrategy:
    """Buy when price is significantly below the rolling mean; sell when above.

    Uses z-score = (price - rolling_mean) / rolling_std to measure deviation.
    Emits at most one signal per threshold crossing to avoid repeated orders.
    Checks current position so it does not buy when already long or sell when flat.
    """

    name = "mean_reversion"

    def __init__(
        self,
        run_id: UUID,
        symbol: str,
        window: int = 20,
        z_threshold: float = 1.5,
        quantity: int = 10,
    ) -> None:
        if window < 2:
            raise ValueError("window must be at least 2")
        if z_threshold <= 0:
            raise ValueError("z_threshold must be positive")
        self.run_id = run_id
        self.symbol = symbol.upper()
        self.window = window
        self.z_threshold = z_threshold
        self.quantity = quantity
        self._prices: deque[float] = deque(maxlen=window)
        self._prev_signal: SignalAction | None = None

    def on_event(self, event: MarketEvent, state: PortfolioState) -> Signal | None:
        if event.symbol != self.symbol:
            return None
        if event.event_type not in (EventType.PRICE_TICK, EventType.TRADE_PRINT):
            return None

        self._prices.append(event.price)

        if len(self._prices) < self.window:
            return None

        prices = list(self._prices)
        mean = statistics.mean(prices)
        stdev = statistics.stdev(prices)

        if stdev == 0:
            return None

        z_score = (event.price - mean) / stdev
        pos = state.get_position(self.symbol)
        current_qty = pos.quantity if pos else 0

        signal: Signal | None = None

        if z_score < -self.z_threshold and current_qty == 0:
            if self._prev_signal != SignalAction.BUY:
                signal = Signal(
                    signal_id=uuid4(),
                    run_id=self.run_id,
                    timestamp=event.timestamp,
                    symbol=self.symbol,
                    action=SignalAction.BUY,
                    quantity=self.quantity,
                    reason=f"mean_reversion_buy z={z_score:.4f} mean={mean:.4f}",
                )
                self._prev_signal = SignalAction.BUY

        elif z_score > self.z_threshold and current_qty > 0:
            if self._prev_signal != SignalAction.SELL:
                signal = Signal(
                    signal_id=uuid4(),
                    run_id=self.run_id,
                    timestamp=event.timestamp,
                    symbol=self.symbol,
                    action=SignalAction.SELL,
                    quantity=min(self.quantity, current_qty),
                    reason=f"mean_reversion_sell z={z_score:.4f} mean={mean:.4f}",
                )
                self._prev_signal = SignalAction.SELL

        else:
            self._prev_signal = None

        return signal
