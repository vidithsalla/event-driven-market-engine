"""Run management endpoints."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from event_trading_engine.app.api.dependencies import get_db
from event_trading_engine.app.api.schemas import RunCreate, RunResponse
from event_trading_engine.app.repositories.backtest_repository import BacktestRepository
from event_trading_engine.app.services.simulation_service import SimulationService
from event_trading_engine.engine.execution import ExecutionConfig
from event_trading_engine.engine.risk import RiskConfig
from event_trading_engine.engine.strategy import (
    MeanReversionStrategy,
    MovingAverageCrossoverStrategy,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])

_SAMPLE_CSV = Path(__file__).resolve().parents[4] / "data" / "sample_events.csv"


def _build_strategy(run_id, strategy_name: str, config: dict):
    if strategy_name == "mean_reversion":
        return MeanReversionStrategy(
            run_id=run_id,
            symbol=config.get("symbol", "AAPL"),
            window=config.get("window", 20),
            z_threshold=config.get("z_threshold", 1.5),
            quantity=config.get("quantity", 10),
        )
    return MovingAverageCrossoverStrategy(
        run_id=run_id,
        symbol=config.get("symbol", "AAPL"),
        short_window=config.get("short_window", 5),
        long_window=config.get("long_window", 20),
        quantity=config.get("quantity", 10),
    )


@router.post("", response_model=RunResponse, status_code=201)
def create_and_start_run(body: RunCreate, db: Session = Depends(get_db)):
    run_id = uuid4()
    service = SimulationService(db)
    strategy = _build_strategy(run_id, body.strategy_name, body.config)
    try:
        service.run_backtest_from_csv(
            run_id=run_id,
            csv_path=_SAMPLE_CSV,
            strategy=strategy,
            initial_cash=body.initial_cash,
            risk_config=RiskConfig(),
            execution_config=ExecutionConfig(),
            save_snapshots=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    run = service.get_run(str(run_id))
    if run is None:
        raise HTTPException(status_code=500, detail="Run not found after creation")
    return run


@router.get("", response_model=list[RunResponse])
def list_runs(db: Session = Depends(get_db)):
    return BacktestRepository(db).list_runs()


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = BacktestRepository(db).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
