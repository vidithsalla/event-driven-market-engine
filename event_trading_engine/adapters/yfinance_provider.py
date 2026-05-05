"""yfinance-based historical market data adapter.

This module is the ONLY place in the project that imports yfinance or pandas.
The engine never sees these imports. The adapter's sole job is to convert
OHLCV rows into normalized MarketEvent objects that the engine already understands.

Requires the [historical] extra:
    pip install -e ".[historical]"
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from event_trading_engine.engine.events import EventType, MarketEvent


def _require_yfinance():
    try:
        import pandas  # noqa: F401
        import yfinance  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "yfinance and pandas are required for historical data fetching.\n"
            "Install them with: pip install -e '.[historical]'"
        ) from exc


def _ohlcv_row_to_events(
    symbol: str,
    timestamp: datetime,
    open_price: float,
    close_price: float,
    volume: int,
    source: str,
) -> list[MarketEvent]:
    """Convert one OHLCV bar to a list of MarketEvents.

    Each bar becomes two PRICE_TICK events: one for the open price and one
    for the close price. This gives the strategy two price observations per
    bar, which is sufficient for moving average and mean reversion logic.
    """
    events: list[MarketEvent] = []

    events.append(
        MarketEvent(
            event_id=uuid4(),
            timestamp=timestamp,
            symbol=symbol,
            event_type=EventType.PRICE_TICK,
            price=round(open_price, 4),
            volume=0,
            source=source,
        )
    )
    events.append(
        MarketEvent(
            event_id=uuid4(),
            timestamp=timestamp,
            symbol=symbol,
            event_type=EventType.PRICE_TICK,
            price=round(close_price, 4),
            volume=volume,
            source=source,
        )
    )
    return events


class YFinanceProvider:
    """Fetches historical OHLCV data from Yahoo Finance and converts to MarketEvents.

    This class satisfies the MarketDataProvider protocol.

    Note: Yahoo Finance data is subject to their terms of service. This adapter
    is for educational and research purposes only. Data accuracy and availability
    are not guaranteed. Do not use for real trading.
    """

    def __init__(self, source_label: str = "YFINANCE_HISTORICAL") -> None:
        self._source = source_label

    def fetch(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1h",
    ) -> list[MarketEvent]:
        """Fetch OHLCV bars and return normalized MarketEvents.

        A MARKET_OPEN event is injected at the start of each trading day,
        and a MARKET_CLOSE event is injected at the end. This mirrors the
        structure of the sample CSV and ensures the risk engine's market-hours
        check passes.

        Args:
            symbol:   Ticker, e.g. "AAPL".
            start:    ISO date, e.g. "2024-01-01".
            end:      ISO date, e.g. "2024-02-01".
            interval: Bar size. Supported: "1m","2m","5m","15m","30m","60m",
                      "90m","1h","1d","5d","1wk","1mo","3mo".

        Returns:
            list[MarketEvent] in chronological order.
        """
        _require_yfinance()
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, interval=interval)

        if df.empty:
            raise ValueError(
                f"No data returned for {symbol} ({start} to {end}, interval={interval}). "
                "Check symbol, date range, and network access."
            )

        symbol = symbol.upper()
        events: list[MarketEvent] = []
        current_day: str | None = None

        for ts, row in df.iterrows():
            if hasattr(ts, "to_pydatetime"):
                dt: datetime = ts.to_pydatetime()
            else:
                dt = datetime.fromisoformat(str(ts))

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)

            day_str = dt.strftime("%Y-%m-%d")

            if day_str != current_day:
                if current_day is not None:
                    # Close the previous day
                    events.append(
                        MarketEvent(
                            event_id=uuid4(),
                            timestamp=dt,
                            symbol=symbol,
                            event_type=EventType.MARKET_CLOSE,
                            price=0.0,
                            volume=0,
                            source=self._source,
                        )
                    )
                # Open the new day
                events.append(
                    MarketEvent(
                        event_id=uuid4(),
                        timestamp=dt,
                        symbol=symbol,
                        event_type=EventType.MARKET_OPEN,
                        price=0.0,
                        volume=0,
                        source=self._source,
                    )
                )
                current_day = day_str

            bar_events = _ohlcv_row_to_events(
                symbol=symbol,
                timestamp=dt,
                open_price=float(row["Open"]),
                close_price=float(row["Close"]),
                volume=int(row["Volume"]),
                source=self._source,
            )
            events.extend(bar_events)

        # Close the final day
        if events:
            last_dt = events[-1].timestamp
            events.append(
                MarketEvent(
                    event_id=uuid4(),
                    timestamp=last_dt,
                    symbol=symbol,
                    event_type=EventType.MARKET_CLOSE,
                    price=0.0,
                    volume=0,
                    source=self._source,
                )
            )

        return events


def events_to_csv(events: list[MarketEvent], path: Path) -> int:
    """Write a list of MarketEvents to a CSV file compatible with BacktestRunner.

    Returns the number of rows written (excluding header).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["event_id", "timestamp", "symbol", "event_type", "price", "volume", "source"]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for e in events:
            writer.writerow(
                {
                    "event_id": str(e.event_id),
                    "timestamp": e.timestamp.isoformat(),
                    "symbol": e.symbol,
                    "event_type": e.event_type.value,
                    "price": e.price,
                    "volume": e.volume,
                    "source": e.source,
                }
            )
    return len(events)
