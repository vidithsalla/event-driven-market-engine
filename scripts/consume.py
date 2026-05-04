"""Consume market events from Redpanda/Kafka and run the simulation engine."""

import argparse
import logging
import sys
from pathlib import Path
from uuid import uuid4

import redis

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from event_trading_engine.engine.strategy import MovingAverageCrossoverStrategy
from event_trading_engine.streaming.consumer import StreamingConsumer
from event_trading_engine.streaming.schemas import MARKET_EVENTS_TOPIC
from event_trading_engine.streaming.state_cache import StateCache

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume market events and run simulation.")
    parser.add_argument("--broker", default="localhost:9092")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--topic", default=MARKET_EVENTS_TOPIC)
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--max-messages", type=int, default=None)
    args = parser.parse_args()

    run_id = uuid4()
    redis_client = redis.from_url(args.redis_url)
    cache = StateCache(redis_client)

    strategy = MovingAverageCrossoverStrategy(
        run_id=run_id,
        symbol=args.symbol,
        short_window=5,
        long_window=20,
        quantity=10,
    )

    def on_trade(trade):
        logging.info("Trade: %s %s %s @ %.4f", trade.side.value, trade.quantity, trade.symbol, trade.fill_price)

    consumer = StreamingConsumer(
        run_id=run_id,
        strategy=strategy,
        state_cache=cache,
        bootstrap_servers=args.broker,
        on_trade=on_trade,
    )
    consumer.subscribe(args.topic)
    print(f"Consuming from '{args.topic}' on {args.broker} — run_id={run_id}")
    consumer.run(max_messages=args.max_messages)

    state = consumer._runner.state
    print(f"\nDone. Trades: {len(state.trades)}")
    for pos in state.positions.values():
        print(f"  {pos.symbol}: qty={pos.quantity} unrealized_pnl={pos.unrealized_pnl:.2f}")


if __name__ == "__main__":
    main()
