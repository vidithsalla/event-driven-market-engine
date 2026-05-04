"""Kafka/Redpanda market event producer."""

from confluent_kafka import Producer

from event_trading_engine.engine.events import MarketEvent
from event_trading_engine.streaming.schemas import MARKET_EVENTS_TOPIC, serialize_event


class MarketEventProducer:
    def __init__(self, bootstrap_servers: str = "localhost:9092") -> None:
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})

    def send(self, event: MarketEvent, topic: str = MARKET_EVENTS_TOPIC) -> None:
        self._producer.produce(
            topic=topic,
            key=event.symbol.encode("utf-8"),
            value=serialize_event(event),
        )

    def flush(self, timeout: float = 10.0) -> None:
        self._producer.flush(timeout=timeout)

    def send_batch(self, events: list[MarketEvent], topic: str = MARKET_EVENTS_TOPIC) -> None:
        for event in events:
            self.send(event, topic=topic)
        self.flush()
