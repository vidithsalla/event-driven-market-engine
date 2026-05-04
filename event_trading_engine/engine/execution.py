"""Execution engine: converts a risk-approved order into a trade.

Simple model: market fills at latest price with configurable slippage and fees.
No partial fills. Slippage is directional (buys pay more, sells receive less).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from .events import OrderSide, OrderStatus, SimulatedOrder, Trade


@dataclass
class ExecutionConfig:
    slippage_bps: float = 5.0
    fee_rate: float = 0.001


class ExecutionEngine:
    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self.config = config or ExecutionConfig()

    def execute(
        self,
        order: SimulatedOrder,
        market_price: float,
        timestamp: datetime,
    ) -> Trade:
        slippage = self.config.slippage_bps / 10_000.0

        if order.side == OrderSide.BUY:
            fill_price = market_price * (1.0 + slippage)
        else:
            fill_price = market_price * (1.0 - slippage)

        fee = order.quantity * fill_price * self.config.fee_rate

        order.status = OrderStatus.FILLED

        return Trade(
            trade_id=uuid4(),
            run_id=order.run_id,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=round(fill_price, 6),
            fee=round(fee, 6),
            timestamp=timestamp,
        )
