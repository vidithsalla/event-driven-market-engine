"""Serialization helpers for streaming market events over Kafka/Redpanda."""

import json

from event_trading_engine.engine.events import MarketEvent

MARKET_EVENTS_TOPIC = "market_events"


def serialize_event(event: MarketEvent) -> bytes:
    return event.model_dump_json().encode("utf-8")


def deserialize_event(data: bytes) -> MarketEvent:
    return MarketEvent.model_validate_json(data.decode("utf-8"))


def serialize_json(obj: dict) -> bytes:
    return json.dumps(obj).encode("utf-8")


def deserialize_json(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))
