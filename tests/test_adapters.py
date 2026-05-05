"""Tests for the historical market data adapter.

All tests use either:
  - the static fixture CSV at data/fixtures/aapl_1d_jan2024.csv, or
  - a mock yfinance.Ticker so no network calls are made.

The core engine is never imported from these tests directly — we verify
the adapter's output is compatible with BacktestRunner independently.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from event_trading_engine.adapters.yfinance_provider import (
    YFinanceProvider,
    _ohlcv_row_to_events,
    events_to_csv,
)
from event_trading_engine.engine.backtest import BacktestRunner
from event_trading_engine.engine.events import EventType, MarketEvent

FIXTURE_CSV = Path(__file__).parent.parent / "data" / "fixtures" / "aapl_1d_jan2024.csv"


# ---------------------------------------------------------------------------
# Helper: build a minimal fake DataFrame row
# ---------------------------------------------------------------------------

def _make_fake_df(rows: list[dict]):
    """Return a fake pandas DataFrame-like object for mocking yfinance."""
    import pandas as pd

    index = []
    data = {"Open": [], "Close": [], "Volume": []}
    for row in rows:
        index.append(pd.Timestamp(row["ts"], tz="UTC"))
        data["Open"].append(row["open"])
        data["Close"].append(row["close"])
        data["Volume"].append(row["volume"])

    df = pd.DataFrame(data, index=index)
    df.index.name = "Datetime"
    return df


# ---------------------------------------------------------------------------
# Unit: _ohlcv_row_to_events
# ---------------------------------------------------------------------------

class TestOhlcvRowToEvents:
    def test_returns_two_events(self):
        ts = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        events = _ohlcv_row_to_events("AAPL", ts, 185.0, 183.5, 1000, "TEST")
        assert len(events) == 2

    def test_first_event_is_open_price(self):
        ts = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        events = _ohlcv_row_to_events("AAPL", ts, 185.0, 183.5, 1000, "TEST")
        assert events[0].price == 185.0
        assert events[0].event_type == EventType.PRICE_TICK

    def test_second_event_is_close_price(self):
        ts = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        events = _ohlcv_row_to_events("AAPL", ts, 185.0, 183.5, 1000, "TEST")
        assert events[1].price == 183.5

    def test_close_event_has_volume(self):
        ts = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        events = _ohlcv_row_to_events("AAPL", ts, 185.0, 183.5, 5000, "TEST")
        assert events[1].volume == 5000

    def test_event_ids_are_unique(self):
        ts = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        events = _ohlcv_row_to_events("AAPL", ts, 185.0, 183.5, 1000, "TEST")
        assert events[0].event_id != events[1].event_id

    def test_symbol_preserved(self):
        ts = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        events = _ohlcv_row_to_events("MSFT", ts, 380.0, 378.0, 200, "TEST")
        assert all(e.symbol == "MSFT" for e in events)

    def test_source_label_preserved(self):
        ts = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
        events = _ohlcv_row_to_events("AAPL", ts, 185.0, 183.5, 1000, "YFINANCE_HISTORICAL")
        assert all(e.source == "YFINANCE_HISTORICAL" for e in events)


# ---------------------------------------------------------------------------
# Unit: YFinanceProvider.fetch with mocked yfinance
# ---------------------------------------------------------------------------

class TestYFinanceProviderMocked:
    def _mock_provider(self, rows: list[dict]) -> list[MarketEvent]:
        df = _make_fake_df(rows)
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = df
            mock_ticker_cls.return_value = mock_ticker
            provider = YFinanceProvider()
            return provider.fetch("AAPL", "2024-01-02", "2024-01-05", interval="1d")

    def test_single_bar_produces_open_close_events(self):
        events = self._mock_provider([
            {"ts": "2024-01-02 14:30:00", "open": 185.0, "close": 183.5, "volume": 1000},
        ])
        types = [e.event_type for e in events]
        assert EventType.MARKET_OPEN in types
        assert EventType.PRICE_TICK in types
        assert EventType.MARKET_CLOSE in types

    def test_single_bar_total_event_count(self):
        events = self._mock_provider([
            {"ts": "2024-01-02 14:30:00", "open": 185.0, "close": 183.5, "volume": 1000},
        ])
        # 1 MARKET_OPEN + 2 PRICE_TICK + 1 MARKET_CLOSE
        assert len(events) == 4

    def test_two_days_get_two_market_opens(self):
        events = self._mock_provider([
            {"ts": "2024-01-02 14:30:00", "open": 185.0, "close": 183.5, "volume": 1000},
            {"ts": "2024-01-03 14:30:00", "open": 182.0, "close": 184.0, "volume": 900},
        ])
        opens = [e for e in events if e.event_type == EventType.MARKET_OPEN]
        assert len(opens) == 2

    def test_two_days_get_two_market_closes(self):
        events = self._mock_provider([
            {"ts": "2024-01-02 14:30:00", "open": 185.0, "close": 183.5, "volume": 1000},
            {"ts": "2024-01-03 14:30:00", "open": 182.0, "close": 184.0, "volume": 900},
        ])
        closes = [e for e in events if e.event_type == EventType.MARKET_CLOSE]
        assert len(closes) == 2

    def test_all_event_ids_are_unique(self):
        events = self._mock_provider([
            {"ts": "2024-01-02 14:30:00", "open": 185.0, "close": 183.5, "volume": 1000},
            {"ts": "2024-01-02 15:30:00", "open": 183.5, "close": 184.0, "volume": 800},
        ])
        ids = [e.event_id for e in events]
        assert len(ids) == len(set(ids))

    def test_symbol_uppercased(self):
        df = _make_fake_df([{"ts": "2024-01-02 14:30:00", "open": 185.0, "close": 183.5, "volume": 100}])
        with patch("yfinance.Ticker") as mock_cls:
            mock_cls.return_value.history.return_value = df
            events = YFinanceProvider().fetch("aapl", "2024-01-02", "2024-01-05")
        assert all(e.symbol == "AAPL" for e in events)

    def test_empty_response_raises(self):
        import pandas as pd
        empty_df = pd.DataFrame(columns=["Open", "Close", "Volume"])
        with patch("yfinance.Ticker") as mock_cls:
            mock_cls.return_value.history.return_value = empty_df
            with pytest.raises(ValueError, match="No data returned"):
                YFinanceProvider().fetch("FAKE", "2024-01-01", "2024-01-02")

    def test_events_are_valid_market_events(self):
        events = self._mock_provider([
            {"ts": "2024-01-02 14:30:00", "open": 185.0, "close": 183.5, "volume": 1000},
        ])
        for e in events:
            assert isinstance(e, MarketEvent)
            assert isinstance(e.event_id, UUID)


# ---------------------------------------------------------------------------
# Unit: events_to_csv
# ---------------------------------------------------------------------------

class TestEventsToCsv:
    def _make_event(self, price: float = 100.0) -> MarketEvent:
        return MarketEvent(
            event_id=__import__("uuid").uuid4(),
            timestamp=datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc),
            symbol="AAPL",
            event_type=EventType.PRICE_TICK,
            price=price,
            volume=500,
            source="TEST",
        )

    def test_writes_correct_row_count(self, tmp_path):
        events = [self._make_event(100.0), self._make_event(101.0)]
        out = tmp_path / "out.csv"
        n = events_to_csv(events, out)
        assert n == 2

    def test_csv_has_header(self, tmp_path):
        out = tmp_path / "out.csv"
        events_to_csv([self._make_event()], out)
        with open(out) as f:
            header = f.readline().strip()
        assert "event_id" in header
        assert "timestamp" in header
        assert "symbol" in header

    def test_csv_price_roundtrip(self, tmp_path):
        out = tmp_path / "out.csv"
        events_to_csv([self._make_event(185.2258)], out)
        with open(out) as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert float(row["price"]) == pytest.approx(185.2258, rel=1e-4)

    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "nested" / "dir" / "out.csv"
        events_to_csv([self._make_event()], out)
        assert out.exists()


# ---------------------------------------------------------------------------
# Integration: fixture CSV → BacktestRunner (no network)
# ---------------------------------------------------------------------------

class TestFixtureBacktest:
    def test_fixture_csv_exists(self):
        assert FIXTURE_CSV.exists(), f"Fixture not found: {FIXTURE_CSV}"

    def test_fixture_loads_without_error(self):
        events = BacktestRunner.load_events_from_csv(FIXTURE_CSV)
        assert len(events) > 0

    def test_fixture_has_market_open_event(self):
        events = BacktestRunner.load_events_from_csv(FIXTURE_CSV)
        types = {e.event_type for e in events}
        assert EventType.MARKET_OPEN in types

    def test_fixture_has_market_close_event(self):
        events = BacktestRunner.load_events_from_csv(FIXTURE_CSV)
        types = {e.event_type for e in events}
        assert EventType.MARKET_CLOSE in types

    def test_fixture_has_price_tick_events(self):
        events = BacktestRunner.load_events_from_csv(FIXTURE_CSV)
        ticks = [e for e in events if e.event_type == EventType.PRICE_TICK]
        assert len(ticks) > 0

    def test_fixture_all_prices_positive(self):
        events = BacktestRunner.load_events_from_csv(FIXTURE_CSV)
        for e in events:
            if e.event_type == EventType.PRICE_TICK:
                assert e.price > 0, f"Non-positive price: {e.price}"

    def test_fixture_backtest_runs_deterministically(self):
        from uuid import uuid4

        from event_trading_engine.engine.strategy import MovingAverageCrossoverStrategy

        events = BacktestRunner.load_events_from_csv(FIXTURE_CSV)

        def _run():
            run_id = uuid4()
            strategy = MovingAverageCrossoverStrategy(
                run_id=run_id, symbol="AAPL", short_window=2, long_window=3, quantity=5
            )
            runner = BacktestRunner(run_id=run_id, strategy=strategy)
            result = runner.run(events)
            return [t.fill_price for t in result.trades]

        # Two runs on the same events must produce the same trade prices
        assert _run() == _run()

    def test_source_label_is_yfinance(self):
        events = BacktestRunner.load_events_from_csv(FIXTURE_CSV)
        sources = {e.source for e in events if e.event_type == EventType.PRICE_TICK}
        assert "YFINANCE_HISTORICAL" in sources
