"""Adapter interface for market data providers.

Any class that satisfies MarketDataProvider can feed the engine.
The engine itself only consumes list[MarketEvent] — it has no knowledge
of where the data came from.
"""

from __future__ import annotations

from typing import Protocol

from event_trading_engine.engine.events import MarketEvent


class MarketDataProvider(Protocol):
    """Minimal protocol that all data adapters must satisfy."""

    def fetch(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1h",
    ) -> list[MarketEvent]:
        """Return normalized MarketEvents for the given symbol and date range.

        Args:
            symbol: Ticker symbol (e.g. "AAPL").
            start:  ISO date string, inclusive (e.g. "2024-01-01").
            end:    ISO date string, exclusive (e.g. "2024-02-01").
            interval: Bar interval — provider-dependent (e.g. "1h", "1d").

        Returns:
            A list of MarketEvent objects in chronological order.
            The list is bracketed by MARKET_OPEN and MARKET_CLOSE events
            for each trading day present in the data.
        """
        ...
