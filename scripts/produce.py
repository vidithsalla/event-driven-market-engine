"""Produce sample market events from CSV into a Redpanda/Kafka topic."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from event_trading_engine.engine.backtest import BacktestRunner
from event_trading_engine.streaming.producer import MarketEventProducer
from event_trading_engine.streaming.schemas import MARKET_EVENTS_TOPIC


def main() -> None:
    parser = argparse.ArgumentParser(description="Produce market events to Kafka/Redpanda.")
    parser.add_argument("--input", default="data/sample_events.csv")
    parser.add_argument("--broker", default="localhost:9092")
    parser.add_argument("--topic", default=MARKET_EVENTS_TOPIC)
    args = parser.parse_args()

    events = BacktestRunner.load_events_from_csv(Path(args.input))
    producer = MarketEventProducer(bootstrap_servers=args.broker)
    producer.send_batch(events, topic=args.topic)
    print(f"Produced {len(events)} events to topic '{args.topic}' on {args.broker}")


if __name__ == "__main__":
    main()
