"""Fetch historical OHLCV data from Yahoo Finance and write to a normalized CSV.

The output CSV has the same schema as data/sample_events.csv and can be fed
directly into BacktestRunner or the backtest CLI.

Requirements:
    pip install -e ".[historical]"

Usage:
    python scripts/fetch_historical.py --symbol AAPL --start 2024-01-01 --end 2024-04-01
    python scripts/fetch_historical.py --symbol MSFT --start 2024-06-01 --end 2024-09-01 --interval 1d
    python scripts/fetch_historical.py --symbol TSLA --start 2024-01-01 --end 2024-02-01 --out data/tsla_jan24.csv

Disclaimer:
    Data is sourced from Yahoo Finance for educational and research purposes.
    This is not real-time data. Not suitable for live trading.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from event_trading_engine.adapters.yfinance_provider import YFinanceProvider, events_to_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch historical market data and write to a normalized event CSV."
    )
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD, inclusive)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD, exclusive)")
    parser.add_argument(
        "--interval",
        default="1h",
        help="Bar interval: 1m, 5m, 15m, 30m, 1h, 1d (default: 1h)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path (default: data/{symbol}_{start}_{end}_{interval}.csv)",
    )
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else Path(
        f"data/{args.symbol.lower()}_{args.start}_{args.end}_{args.interval}.csv"
    )

    print(f"Fetching {args.symbol} from {args.start} to {args.end} (interval={args.interval})…")

    try:
        provider = YFinanceProvider()
        events = provider.fetch(
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            interval=args.interval,
        )
    except ImportError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    n = events_to_csv(events, out_path)
    print(f"Written {n} events to {out_path}")
    print()
    print("To run a backtest on this data:")
    print(f"  python -m event_trading_engine.engine.backtest --input {out_path} --symbol {args.symbol.upper()}")


if __name__ == "__main__":
    main()
