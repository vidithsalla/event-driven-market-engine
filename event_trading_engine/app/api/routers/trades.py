"""Trade, order, and signal endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from event_trading_engine.app.api.dependencies import get_db
from event_trading_engine.app.api.schemas import OrderResponse, SignalResponse, TradeResponse
from event_trading_engine.app.repositories.backtest_repository import BacktestRepository

router = APIRouter(prefix="/api/runs", tags=["trades"])


def _require_run(run_id: str, repo: BacktestRepository):
    if repo.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")


@router.get("/{run_id}/trades", response_model=list[TradeResponse])
def get_trades(run_id: str, db: Session = Depends(get_db)):
    repo = BacktestRepository(db)
    _require_run(run_id, repo)
    return repo.get_trades(run_id)


@router.get("/{run_id}/orders", response_model=list[OrderResponse])
def get_orders(run_id: str, db: Session = Depends(get_db)):
    repo = BacktestRepository(db)
    _require_run(run_id, repo)
    return repo.get_orders(run_id)


@router.get("/{run_id}/signals", response_model=list[SignalResponse])
def get_signals(run_id: str, db: Session = Depends(get_db)):
    repo = BacktestRepository(db)
    _require_run(run_id, repo)
    return repo.get_signals(run_id)
