"""Portfolio, positions, and metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from event_trading_engine.app.api.dependencies import get_db
from event_trading_engine.app.api.schemas import (
    MetricsResponse,
    PortfolioSnapshotResponse,
    PositionResponse,
)
from event_trading_engine.app.repositories.backtest_repository import BacktestRepository

router = APIRouter(prefix="/api/runs", tags=["portfolio"])


def _require_run(run_id: str, repo: BacktestRepository):
    if repo.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")


@router.get("/{run_id}/positions", response_model=list[PositionResponse])
def get_positions(run_id: str, db: Session = Depends(get_db)):
    repo = BacktestRepository(db)
    _require_run(run_id, repo)
    return repo.get_positions(run_id)


@router.get("/{run_id}/portfolio", response_model=list[PortfolioSnapshotResponse])
def get_portfolio_snapshots(run_id: str, db: Session = Depends(get_db)):
    repo = BacktestRepository(db)
    _require_run(run_id, repo)
    return repo.get_snapshots(run_id)


@router.get("/{run_id}/metrics", response_model=MetricsResponse)
def get_metrics(run_id: str, db: Session = Depends(get_db)):
    repo = BacktestRepository(db)
    _require_run(run_id, repo)
    trades = repo.get_trades(run_id)
    positions = repo.get_positions(run_id)

    realized_pnl = sum(p.realized_pnl for p in positions)
    unrealized_pnl = sum(p.unrealized_pnl for p in positions)
    total_pnl = realized_pnl + unrealized_pnl
    max_pos = max((p.quantity * p.average_cost for p in positions), default=0.0)

    return MetricsResponse(
        run_id=run_id,
        total_pnl=total_pnl,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        max_drawdown=0.0,
        trade_count=len(trades),
        win_rate=0.0,
        max_position_value=max_pos,
    )
