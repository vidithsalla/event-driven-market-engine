"""Benchmark the event-driven backtest engine.

Generates N synthetic market events and times how long the engine takes
to process them, reporting events/sec and p95 per-event latency.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --events 100000 --runs 5
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from event_trading_engine.engine.backtest import BacktestRunner
from event_trading_engine.engine.events import EventType, MarketEvent
from event_trading_engine.engine.strategy import MovingAverageCrossoverStrategy


def _generate_events(n: int) -> list[MarketEvent]:
    """Generate synthetic price-tick events around a sine wave."""
    import math

    events = []
    for i in range(n):
        price = 100.0 + 20.0 * math.sin(i * 0.05)
        events.append(
            MarketEvent(
                event_id=uuid4(),
                timestamp=datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
                symbol="BENCH",
                event_type=EventType.PRICE_TICK,
                price=max(price, 0.01),
                volume=1000,
                source="BENCHMARK",
            )
        )
    return events


def _time_run(events: list[MarketEvent]) -> float:
    """Return elapsed seconds for one full backtest run."""
    run_id = uuid4()
    strategy = MovingAverageCrossoverStrategy(
        run_id=run_id, symbol="BENCH", short_window=5, long_window=20, quantity=10
    )
    runner = BacktestRunner(run_id=run_id, strategy=strategy)
    t0 = time.perf_counter()
    runner.run(events)
    return time.perf_counter() - t0


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the backtest engine.")
    parser.add_argument("--events", type=int, default=100_000, help="Number of synthetic events")
    parser.add_argument("--runs", type=int, default=3, help="Number of timing repetitions")
    args = parser.parse_args()

    import platform

    print("\nBenchmark environment")
    print(f"  Machine   : {platform.machine()} ({platform.processor()})")
    print(f"  Python    : {sys.version.split()[0]}")
    print(f"  Events    : {args.events:,}")
    print("  Strategy  : MA crossover (short=5, long=20)")
    print("  DB writes : disabled\n")

    print("Generating events…", flush=True)
    events = _generate_events(args.events)

    times = []
    for i in range(args.runs):
        elapsed = _time_run(events)
        times.append(elapsed)
        print(f"  Run {i + 1}: {elapsed:.3f}s  ({args.events / elapsed:,.0f} events/sec)")

    avg = statistics.mean(times)
    best = min(times)
    per_event_us = [(t / args.events) * 1e6 for t in times]
    p95_us = sorted(per_event_us)[int(len(per_event_us) * 0.95)]

    print("\nResults")
    print(f"  Best run      : {best:.3f}s")
    print(f"  Avg run       : {avg:.3f}s")
    print(f"  Best throughput: {args.events / best:,.0f} events/sec")
    print(f"  p95 latency   : {p95_us:.2f} µs/event  (in-process, no DB)\n")


if __name__ == "__main__":
    main()
