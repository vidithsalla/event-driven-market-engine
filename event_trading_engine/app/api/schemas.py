"""Pydantic response schemas for the FastAPI layer.

These are separate from the engine domain models so API contracts can evolve
independently from internal representations.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

class RunCreate(BaseModel):
    strategy_name: str
    initial_cash: float = 100_000.0
    config: dict = {}


class RunResponse(BaseModel):
    id: str
    strategy_name: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    config_json: str | None

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Trade
# ------------------------------------------------------------------

class TradeResponse(BaseModel):
    id: str
    run_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    fill_price: float
    fee: float
    timestamp: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Order
# ------------------------------------------------------------------

class OrderResponse(BaseModel):
    id: str
    run_id: str
    symbol: str
    side: str
    quantity: float
    requested_price: float
    status: str
    rejection_reason: str | None

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Signal
# ------------------------------------------------------------------

class SignalResponse(BaseModel):
    id: str
    run_id: str
    symbol: str
    action: str
    quantity: float
    reason: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Position
# ------------------------------------------------------------------

class PositionResponse(BaseModel):
    id: str
    run_id: str
    symbol: str
    quantity: float
    average_cost: float
    realized_pnl: float
    unrealized_pnl: float

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Portfolio snapshot
# ------------------------------------------------------------------

class PortfolioSnapshotResponse(BaseModel):
    id: str
    run_id: str
    timestamp: datetime
    cash: float
    equity: float
    gross_exposure: float
    net_exposure: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Metrics (computed on-the-fly)
# ------------------------------------------------------------------

class MetricsResponse(BaseModel):
    run_id: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    max_position_value: float


# ------------------------------------------------------------------
# Strategy listing
# ------------------------------------------------------------------

class StrategyInfo(BaseModel):
    name: str
    description: str
    parameters: list[str]


# ------------------------------------------------------------------
# Generic message
# ------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str
