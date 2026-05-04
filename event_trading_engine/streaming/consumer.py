"""Kafka/Redpanda market event consumer that drives the simulation engine."""

import logging
from collections.abc import Callable
from uuid import UUID

from confluent_kafka import Consumer, KafkaError, KafkaException, Message

from event_trading_engine.engine.backtest import BacktestRunner
from event_trading_engine.engine.execution import ExecutionConfig
from event_trading_engine.engine.risk import RiskConfig
from event_trading_engine.engine.strategy import Strategy
from event_trading_engine.streaming.schemas import MARKET_EVENTS_TOPIC, deserialize_event
from event_trading_engine.streaming.state_cache import StateCache

logger = logging.getLogger(__name__)


class StreamingConsumer:
    """
    Consumes market events from a Kafka topic and drives a BacktestRunner.

    Idempotency is enforced through StateCache.is_seen() — duplicate event_ids
    are skipped before they reach the engine.
    """

    def __init__(
        self,
        run_id: UUID,
        strategy: Strategy,
        state_cache: StateCache,
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "trading-engine",
        initial_cash: float = 100_000.0,
        risk_config: RiskConfig | None = None,
        execution_config: ExecutionConfig | None = None,
        on_trade: Callable | None = None,
    ) -> None:
        self._run_id = str(run_id)
        self._cache = state_cache
        self._on_trade = on_trade

        self._runner = BacktestRunner(
            run_id=run_id,
            strategy=strategy,
            initial_cash=initial_cash,
            risk_config=risk_config or RiskConfig(),
            execution_config=execution_config or ExecutionConfig(),
        )

        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )

    def subscribe(self, topic: str = MARKET_EVENTS_TOPIC) -> None:
        self._consumer.subscribe([topic])

    def _process_message(self, msg: Message) -> None:
        raw = msg.value()
        if raw is None:
            return

        try:
            event = deserialize_event(raw)
        except Exception:
            logger.warning("Failed to deserialize message, skipping")
            return

        if self._cache.is_seen(self._run_id, str(event.event_id)):
            logger.debug("Duplicate event %s skipped", event.event_id)
            return

        self._cache.mark_seen(self._run_id, str(event.event_id))
        self._runner.process_event(event)
        self._cache.save_state(self._run_id, self._runner.state)

        if self._on_trade and self._runner.state.trades:
            self._on_trade(self._runner.state.trades[-1])

    def run(self, max_messages: int | None = None, timeout: float = 1.0) -> None:
        """Poll until max_messages consumed or KeyboardInterrupt."""
        consumed = 0
        try:
            while True:
                msg = self._consumer.poll(timeout=timeout)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise KafkaException(msg.error())
                self._process_message(msg)
                consumed += 1
                if max_messages is not None and consumed >= max_messages:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self._consumer.close()

    def close(self) -> None:
        self._consumer.close()
