"""Tests for Phase 3 streaming — state_cache and serialization.

Integration tests (requiring live Redpanda) are marked @pytest.mark.integration
and skipped by default.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import fakeredis
import pytest

from event_trading_engine.engine.events import EventType, MarketEvent
from event_trading_engine.engine.portfolio import PortfolioState
from event_trading_engine.streaming.schemas import deserialize_event, serialize_event
from event_trading_engine.streaming.state_cache import StateCache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(symbol: str = "AAPL", price: float = 100.0) -> MarketEvent:
    return MarketEvent(
        event_id=uuid4(),
        timestamp=datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
        symbol=symbol,
        event_type=EventType.PRICE_TICK,
        price=price,
        volume=100,
        source="TEST",
    )


def _make_cache() -> StateCache:
    client = fakeredis.FakeRedis()
    return StateCache(client)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_roundtrip(self):
        event = _make_event(price=185.5)
        assert deserialize_event(serialize_event(event)) == event

    def test_symbol_preserved(self):
        event = _make_event(symbol="MSFT")
        recovered = deserialize_event(serialize_event(event))
        assert recovered.symbol == "MSFT"

    def test_price_precision(self):
        event = _make_event(price=123.456789)
        recovered = deserialize_event(serialize_event(event))
        assert abs(recovered.price - 123.456789) < 1e-6


# ---------------------------------------------------------------------------
# StateCache — deduplication
# ---------------------------------------------------------------------------

class TestStateCacheDedup:
    def test_unseen_event_returns_false(self):
        cache = _make_cache()
        event = _make_event()
        assert not cache.is_seen("run-1", str(event.event_id))

    def test_mark_then_seen(self):
        cache = _make_cache()
        event = _make_event()
        cache.mark_seen("run-1", str(event.event_id))
        assert cache.is_seen("run-1", str(event.event_id))

    def test_different_run_ids_are_isolated(self):
        cache = _make_cache()
        event = _make_event()
        cache.mark_seen("run-1", str(event.event_id))
        assert not cache.is_seen("run-2", str(event.event_id))

    def test_multiple_events(self):
        cache = _make_cache()
        ids = [str(uuid4()) for _ in range(5)]
        for eid in ids:
            cache.mark_seen("run-1", eid)
        for eid in ids:
            assert cache.is_seen("run-1", eid)


# ---------------------------------------------------------------------------
# StateCache — portfolio
# ---------------------------------------------------------------------------

class TestStateCachePortfolio:
    def _make_state(self, cash: float = 50_000.0) -> PortfolioState:
        run_id = uuid4()
        return PortfolioState(run_id=run_id, initial_cash=cash)

    def test_save_and_get_portfolio(self):
        cache = _make_cache()
        state = self._make_state()
        cache.save_portfolio("r1", state)
        result = cache.get_portfolio("r1")
        assert result is not None
        assert result["cash"] == 50_000.0
        assert result["market_open"] is False

    def test_get_missing_returns_none(self):
        cache = _make_cache()
        assert cache.get_portfolio("nonexistent") is None

    def test_save_position(self):
        cache = _make_cache()
        cache.save_position("r1", "AAPL", quantity=10, avg_cost=185.0)
        pos = cache.get_position("r1", "AAPL")
        assert pos is not None
        assert pos["quantity"] == 10
        assert pos["average_cost"] == 185.0

    def test_get_missing_position_returns_none(self):
        cache = _make_cache()
        assert cache.get_position("r1", "MSFT") is None

    def test_save_state_persists_portfolio_and_positions(self):
        cache = _make_cache()
        run_id = uuid4()
        state = PortfolioState(run_id=run_id, initial_cash=100_000.0)

        event = MarketEvent(
            event_id=uuid4(),
            timestamp=datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
            symbol="AAPL",
            event_type=EventType.MARKET_OPEN,
            price=0.0,
            volume=0,
            source="TEST",
        )
        state.on_market_event(event)

        cache.save_state("r1", state)
        portfolio = cache.get_portfolio("r1")
        assert portfolio is not None
        assert portfolio["cash"] == 100_000.0

    def test_flush_run_removes_keys(self):
        cache = _make_cache()
        cache.mark_seen("r1", "evt-1")
        cache.save_position("r1", "AAPL", 10, 100.0)
        cache.flush_run("r1")
        assert not cache.is_seen("r1", "evt-1")
        assert cache.get_position("r1", "AAPL") is None


# ---------------------------------------------------------------------------
# Integration test stubs (skipped without live broker)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestStreamingIntegration:
    """These tests require a running Redpanda instance on localhost:9092."""

    def test_produce_and_consume(self):
        pytest.importorskip("confluent_kafka")
        from confluent_kafka.admin import AdminClient, NewTopic

        admin = AdminClient({"bootstrap.servers": "localhost:9092"})
        topic_name = f"test_market_events_{uuid4().hex[:8]}"
        admin.create_topics([NewTopic(topic_name, num_partitions=1)])

        from pathlib import Path

        import fakeredis

        from event_trading_engine.engine.backtest import BacktestRunner
        from event_trading_engine.engine.strategy import MovingAverageCrossoverStrategy
        from event_trading_engine.streaming.consumer import StreamingConsumer
        from event_trading_engine.streaming.producer import MarketEventProducer

        events = BacktestRunner.load_events_from_csv(Path("data/sample_events.csv"))
        producer = MarketEventProducer(bootstrap_servers="localhost:9092")
        producer.send_batch(events, topic=topic_name)

        run_id = uuid4()
        strategy = MovingAverageCrossoverStrategy(
            run_id=run_id, symbol="AAPL", short_window=5, long_window=20, quantity=10
        )
        cache = StateCache(fakeredis.FakeRedis())
        consumer = StreamingConsumer(
            run_id=run_id,
            strategy=strategy,
            state_cache=cache,
            bootstrap_servers="localhost:9092",
            group_id=f"test-group-{uuid4().hex[:8]}",
        )
        consumer.subscribe(topic_name)
        consumer.run(max_messages=len(events))

        assert len(consumer._runner.state.trades) >= 1
