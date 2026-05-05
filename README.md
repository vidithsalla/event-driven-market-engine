# Event-Driven Trading Simulation Engine

A portfolio project demonstrating backend systems engineering for event-driven, stateful, and correctness-sensitive applications. The focus is on clean architecture, deterministic outputs, and tested state transitions — not dashboard polish.

**This project uses simulated market data. No real trades are executed. No real brokerage connectivity exists.**

---

## What It Does

The engine ingests simulated market events, routes them through strategy modules, generates trade signals, applies risk checks, simulates order execution, and tracks portfolio state, PnL, and risk metrics. Results are persisted to PostgreSQL, exposed through a FastAPI REST API, and visualized in a React dashboard.

---

## Architecture

```
Simulated Market Data (CSV / Redpanda)
        |
        v
Event Consumer (streaming) or BacktestRunner (batch)
        |
        v
Strategy Engine  (MA Crossover | Mean Reversion)
        |
        v
Risk Engine  (position limits, notional caps, loss limits)
        |
        v
Execution Engine  (market fill, slippage, fees)
        |
        v
Portfolio State  (positions, PnL, drawdown)
        |
        +-------> PostgreSQL  (trades, orders, signals, positions, snapshots)
        |
        +-------> Redis  (live state cache for streaming runs)
        |
        v
FastAPI  (REST API)
        |
        v
React Dashboard
```

### Dependency direction

```
dashboard → API → application services → engine → domain models
```

The engine has zero knowledge of FastAPI, SQLAlchemy, Kafka, or Redis.

---

## Stack

| Layer | Technology |
|---|---|
| Core engine | Python 3.10+ |
| Domain models | Pydantic v2 |
| Database | PostgreSQL 15, SQLAlchemy 2.0 |
| Streaming | Redpanda (Kafka-compatible), Redis |
| API | FastAPI, Uvicorn |
| Frontend | React, TypeScript, Vite, Recharts, TanStack Query, Tailwind |
| Testing | pytest (153 passing, 1 integration skipped) |
| Infrastructure | Docker Compose, Makefile |

---

## Local Development

### Requirements

- Python 3.10+
- Docker + Docker Compose
- Node.js 18+ (dashboard only)

### Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run tests

```bash
make test
```

### Run a sample backtest (no Docker required)

```bash
make run-sample
```

---

## Running the Full Stack

### 1. Start infrastructure

```bash
make infra-up
```

Starts Postgres (5432), Redpanda (9092), Redis (6379), and Adminer (8080).

### 2. Run the API server

```bash
make api
```

API available at `http://localhost:8000`. OpenAPI docs at `http://localhost:8000/docs`.

### 3. Run the dashboard

```bash
make frontend
```

Dashboard available at `http://localhost:5173`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/runs` | Create and run a simulation |
| GET | `/api/runs` | List all runs |
| GET | `/api/runs/{id}` | Get run by ID |
| GET | `/api/runs/{id}/trades` | Trades for a run |
| GET | `/api/runs/{id}/orders` | Orders (filled + rejected) |
| GET | `/api/runs/{id}/signals` | Strategy signals |
| GET | `/api/runs/{id}/positions` | Final positions |
| GET | `/api/runs/{id}/portfolio` | Portfolio snapshots |
| GET | `/api/runs/{id}/metrics` | PnL and risk metrics |
| GET | `/api/strategies` | Available strategies |

---

## Strategies

### Moving Average Crossover

- Buy when the short MA crosses above the long MA.
- Sell when the short MA crosses below the long MA.
- Default: `short_window=5`, `long_window=20`.

### Mean Reversion

- Buy when the price z-score drops below `-threshold`.
- Sell when the price z-score rises above `+threshold`.
- Default: `window=20`, `z_threshold=1.5`.

---

## Risk Engine

Every order passes through the risk engine before execution. An order is rejected (status: `REJECTED_RISK`) if any rule fails:

1. Market is closed (no `MARKET_OPEN` event seen yet)
2. Order would exceed max position quantity per symbol
3. Order would exceed max symbol notional exposure
4. Order would exceed max total portfolio notional
5. Sell order exceeds current position
6. Cumulative loss exceeds the configured max loss limit

---

## Execution Model

Market orders fill at latest market price with configurable slippage and fees:

```
fill_price = market_price × (1 ± slippage_bps / 10000)
fee        = quantity × fill_price × fee_rate
```

Defaults: `slippage_bps=5`, `fee_rate=0.001`. No partial fills in v1.

---

## Benchmark

Measured on Apple M-series (arm64), Python 3.10, in-process only, no DB writes:

| Events | Best run | Avg run | Throughput | p95 latency |
|---|---|---|---|---|
| 100,000 | 1.03s | 1.15s | ~97,000 events/sec | ~12 µs/event |

These numbers reflect pure Python in-process event processing (strategy + risk + execution + portfolio update). Database write overhead adds ~2–5× latency per event at typical Postgres I/O rates.

---

## Design Decisions

**Engine independence**: The engine modules (`engine/`) have zero imports from FastAPI, SQLAlchemy, Redis, or Kafka. This makes the engine independently testable and deployable without infrastructure.

**Deterministic backtests**: The same CSV input always produces the same output. This is verified by an explicit test (`test_backtest_is_deterministic`).

**Flush without commit**: The service layer flushes writes to the session buffer but delegates commit to the API layer's `get_db` dependency. This follows SQLAlchemy's unit-of-work pattern and keeps the service layer testable with either SQLite or Postgres.

**Redis deduplication**: The streaming consumer checks `StateCache.is_seen()` before processing each event. This prevents duplicate events (e.g. broker retries) from generating duplicate trades.

**Redpanda over Kafka**: Redpanda is a single binary with no Zookeeper, which simplifies the local Docker Compose setup while remaining Kafka-compatible.

---

## Historical Market Data (Phase 7)

### Adapter architecture

The engine is provider-agnostic. The `adapters/` package sits entirely outside the engine and converts external data into the `MarketEvent` objects the engine already understands:

```
yfinance (Yahoo Finance)
        |
        v
YFinanceProvider          adapters/yfinance_provider.py
        |
        v  OHLCV → MarketEvent (PRICE_TICK, MARKET_OPEN, MARKET_CLOSE)
        |
        v
events_to_csv()           writes normalized CSV
        |
        v
BacktestRunner            engine unchanged — reads CSV as before
```

The engine modules (`engine/`) import nothing from `adapters/`. yfinance and pandas are lazy imports inside the adapter — they are not loaded unless you actually call `fetch()`. If the `[historical]` extra is not installed, the adapter raises a clear `ImportError` with installation instructions.

### Install historical extras

```bash
pip install -e ".[historical]"
```

### Fetch historical data

```bash
python scripts/fetch_historical.py --symbol AAPL --start 2024-01-01 --end 2024-04-01
# Output: data/aapl_2024-01-01_2024-04-01_1h.csv

python scripts/fetch_historical.py --symbol MSFT --start 2024-06-01 --end 2024-09-01 --interval 1d
python scripts/fetch_historical.py --symbol TSLA --start 2024-01-01 --end 2024-02-01 --out data/tsla_jan24.csv
```

### Run a backtest from fetched data

```bash
python -m event_trading_engine.engine.backtest \
    --input data/aapl_2024-01-01_2024-04-01_1h.csv \
    --symbol AAPL \
    --strategy ma_crossover \
    --short-window 5 \
    --long-window 20
```

### Data caveat

Data is sourced from Yahoo Finance (`yfinance`) for educational and research purposes only. Yahoo Finance data quality, accuracy, and availability are not guaranteed. This project does not have a data provider agreement. Do not use for real trading decisions.

Each OHLCV bar is converted to two `PRICE_TICK` events (open price and close price) bracketed by `MARKET_OPEN` / `MARKET_CLOSE` events per trading day. This mirrors the structure of the synthetic sample CSV so the engine's market-hours risk check works without modification.

---

## Git and Commit Hygiene

This project was developed iteratively without intermediate commits. When publishing:

**Do not** fake a multi-commit history with rewritten timestamps. Engineers will notice.

**Recommended approach:** One clean commit or a small set of logical commits from the current state:

```bash
git init
git add .
git commit -m "initial implementation: event-driven trading simulation engine (phases 1–7)

- Core engine: domain models, MA crossover + mean reversion strategies,
  portfolio accounting, risk engine, execution engine, deterministic backtest runner
- PostgreSQL persistence via SQLAlchemy 2.0
- Redpanda/Kafka streaming with Redis state cache and idempotent dedup
- FastAPI REST API with 10 endpoints
- React dashboard (Vite, Recharts, TanStack Query, Tailwind)
- Historical market data adapter (yfinance → normalized MarketEvent CSV)
- Benchmark: ~97k events/sec in-process on Apple M-series
- 180 tests passing, 0 lint errors"
```

Or split into phase-by-phase commits on a single day, each describing what it adds and why. Either approach is honest.

---

## Limitations

- The default sample data is synthetic. Historical data from yfinance is real OHLCV bars, not tick data.
- OHLCV bars are converted to two price observations per bar (open + close). This is a simplification — intra-bar price movement is not modeled.
- Orders fill using a simplified model — no order book, no partial fills.
- No real exchange or brokerage integration. No live trading.
- Risk metrics (drawdown, win rate) are computed in-engine; the metrics endpoint returns simplified values derived from stored positions, not recomputed from full snapshot history.
- No authentication on the API.
- Benchmark numbers reflect in-process Python event processing with no DB writes. Production throughput depends heavily on I/O, network, and serialization overhead.
- Low-latency claims are not made. The benchmark reports honest local throughput only.

---

## Future Improvements

- Add C++ implementation of the hot-path event processor and benchmark against the Python version.
- Add support for replaying historical event streams from the database.
- Add more robust out-of-order event handling.
- Add richer risk metrics: Sharpe ratio, Sortino ratio, rolling drawdown.
- Add WebSocket endpoint for live streaming run state to the dashboard.
- Add authentication to the API.
