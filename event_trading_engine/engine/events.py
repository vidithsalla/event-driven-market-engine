"""Domain models for the trading simulation engine.

All external-facing data uses Pydantic for validation. Enum fields use
string values so they round-trip cleanly through CSV and JSON.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


class EventType(str, Enum):
    PRICE_TICK = "PRICE_TICK"
    TRADE_PRINT = "TRADE_PRINT"
    MARKET_OPEN = "MARKET_OPEN"
    MARKET_CLOSE = "MARKET_CLOSE"


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    REJECTED_RISK = "REJECTED_RISK"
    FILLED = "FILLED"


class MarketEvent(BaseModel):
    event_id: UUID
    timestamp: datetime
    symbol: str
    event_type: EventType
    price: float = 0.0
    volume: int = 0
    source: str = "SIMULATED"

    @field_validator("symbol")
    @classmethod
    def symbol_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("symbol must not be empty")
        return v.upper()

    @field_validator("volume")
    @classmethod
    def volume_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("volume must be non-negative")
        return v

    @model_validator(mode="after")
    def price_positive_for_price_events(self) -> MarketEvent:
        if self.event_type in (EventType.PRICE_TICK, EventType.TRADE_PRINT):
            if self.price <= 0:
                raise ValueError(
                    f"price must be positive for {self.event_type}, got {self.price}"
                )
        return self


class Signal(BaseModel):
    signal_id: UUID
    run_id: UUID
    timestamp: datetime
    symbol: str
    action: SignalAction
    quantity: int
    reason: str = ""


class SimulatedOrder(BaseModel):
    order_id: UUID
    run_id: UUID
    signal_id: UUID
    symbol: str
    side: OrderSide
    quantity: int
    requested_price: float
    status: OrderStatus = OrderStatus.CREATED
    rejection_reason: str = ""


class Trade(BaseModel):
    trade_id: UUID
    run_id: UUID
    order_id: UUID
    symbol: str
    side: OrderSide
    quantity: int
    fill_price: float
    fee: float
    timestamp: datetime


class Position(BaseModel):
    """Mutable position state. Updated in-place by PortfolioState."""

    run_id: UUID
    symbol: str
    quantity: int = 0
    average_cost: float = 0.0
    market_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class PortfolioSnapshot(BaseModel):
    run_id: UUID
    timestamp: datetime
    cash: float
    equity: float
    gross_exposure: float
    net_exposure: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float


class RiskMetrics(BaseModel):
    run_id: UUID
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    max_position_value: float
