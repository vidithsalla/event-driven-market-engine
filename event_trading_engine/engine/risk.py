"""Risk engine: validates every order before it reaches execution.

All checks are stateless relative to the order — they read current portfolio
state and the risk config to decide pass or fail. The engine never mutates state.
"""
from __future__ import annotations

from dataclasses import dataclass

from .events import OrderSide, OrderStatus, SimulatedOrder
from .portfolio import PortfolioState


@dataclass
class RiskConfig:
    max_position_quantity: int = 100
    max_symbol_notional: float = 25_000.0
    max_total_notional: float = 100_000.0
    max_loss: float = 5_000.0


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def check(
        self, order: SimulatedOrder, state: PortfolioState
    ) -> tuple[bool, str]:
        """Return (passes, rejection_reason). reason is empty string when passing."""

        if not state.market_open:
            return False, "market is closed"

        price = state.latest_prices.get(order.symbol, order.requested_price)

        if order.side == OrderSide.BUY:
            existing = state.get_position(order.symbol)
            current_qty = existing.quantity if existing else 0
            new_qty = current_qty + order.quantity

            if new_qty > self.config.max_position_quantity:
                return (
                    False,
                    f"max_position_quantity exceeded: {new_qty} > {self.config.max_position_quantity}",
                )

            symbol_notional = new_qty * price
            if symbol_notional > self.config.max_symbol_notional:
                return (
                    False,
                    f"max_symbol_notional exceeded: {symbol_notional:.2f} > {self.config.max_symbol_notional:.2f}",
                )

            additional_notional = order.quantity * price
            if state.get_total_notional() + additional_notional > self.config.max_total_notional:
                return (
                    False,
                    "max_total_notional exceeded",
                )

        else:  # SELL
            existing = state.get_position(order.symbol)
            current_qty = existing.quantity if existing else 0
            if order.quantity > current_qty:
                return (
                    False,
                    f"insufficient position: have {current_qty}, trying to sell {order.quantity}",
                )

        total_pnl = state.get_total_realized_pnl() + state.get_total_unrealized_pnl()
        if total_pnl < -self.config.max_loss:
            return (
                False,
                f"max_loss exceeded: pnl={total_pnl:.2f} < -{self.config.max_loss:.2f}",
            )

        return True, ""

    def apply_rejection(self, order: SimulatedOrder, reason: str) -> SimulatedOrder:
        order.status = OrderStatus.REJECTED_RISK
        order.rejection_reason = reason
        return order
