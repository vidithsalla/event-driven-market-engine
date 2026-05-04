#!/usr/bin/env python3
"""Seed the database with a sample backtest run.

Requires a running PostgreSQL instance (see docker-compose.yml).

Usage:
    python scripts/seed.py
    DATABASE_URL=postgresql+psycopg2://... python scripts/seed.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

# Allow running as a script without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.exc import OperationalError

from event_trading_engine.app.db.models import Base
from event_trading_engine.app.db.session import (
    DEFAULT_DATABASE_URL,
    build_engine,
    build_session_factory,
)
from event_trading_engine.app.services.simulation_service import SimulationService
from event_trading_engine.engine.execution import ExecutionConfig
from event_trading_engine.engine.risk import RiskConfig
from event_trading_engine.engine.strategy import (
    MeanReversionStrategy,
    MovingAverageCrossoverStrategy,
)

CSV_PATH = Path(__file__).parent.parent / "data" / "sample_events.csv"


def seed(db_url: str = DEFAULT_DATABASE_URL) -> None:
    print(f"Connecting to: {db_url}")

    try:
        engine = build_engine(db_url)
        Base.metadata.create_all(engine)
    except OperationalError as exc:
        print(f"Could not connect to database: {exc}")
        print("Is Docker Compose running? Try: docker compose up -d")
        sys.exit(1)

    session_factory = build_session_factory(engine)

    # --- Run 1: Moving average crossover ---
    run1_id = uuid4()
    with session_factory() as session:
        svc = SimulationService(session)
        strategy = MovingAverageCrossoverStrategy(
            run_id=run1_id,
            symbol="AAPL",
            short_window=5,
            long_window=20,
            quantity=10,
        )
        result = svc.run_backtest_from_csv(
            run_id=run1_id,
            csv_path=CSV_PATH,
            strategy=strategy,
            risk_config=RiskConfig(),
            execution_config=ExecutionConfig(slippage_bps=5.0, fee_rate=0.001),
            save_events=True,
            save_snapshots=True,
        )
        session.commit()

    print(f"\nRun 1 (MA crossover): {run1_id}")
    print(f"  Trades    : {len(result.trades)}")
    print(f"  PnL       : {result.metrics.total_pnl:.4f}")

    # --- Run 2: Mean reversion ---
    run2_id = uuid4()
    with session_factory() as session:
        svc = SimulationService(session)
        strategy = MeanReversionStrategy(
            run_id=run2_id,
            symbol="AAPL",
            window=15,
            z_threshold=1.2,
            quantity=10,
        )
        result = svc.run_backtest_from_csv(
            run_id=run2_id,
            csv_path=CSV_PATH,
            strategy=strategy,
            risk_config=RiskConfig(),
            execution_config=ExecutionConfig(slippage_bps=5.0, fee_rate=0.001),
            save_events=False,
            save_snapshots=True,
        )
        session.commit()

    print(f"\nRun 2 (mean reversion): {run2_id}")
    print(f"  Trades    : {len(result.trades)}")
    print(f"  PnL       : {result.metrics.total_pnl:.4f}")

    print("\nSeed complete. Two simulation runs stored in the database.")


if __name__ == "__main__":
    seed()
