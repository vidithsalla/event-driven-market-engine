"""Compute final risk metrics from completed portfolio state."""
from __future__ import annotations

from uuid import UUID

from .events import RiskMetrics
from .portfolio import PortfolioState


def compute_risk_metrics(run_id: UUID, state: PortfolioState) -> RiskMetrics:
    realized = state.get_total_realized_pnl()
    unrealized = state.get_total_unrealized_pnl()
    total_pnl = realized + unrealized

    max_position_value = 0.0
    for symbol, pos in state.positions.items():
        price = state.latest_prices.get(symbol, pos.average_cost)
        value = pos.quantity * price
        if value > max_position_value:
            max_position_value = value

    return RiskMetrics(
        run_id=run_id,
        total_pnl=round(total_pnl, 4),
        realized_pnl=round(realized, 4),
        unrealized_pnl=round(unrealized, 4),
        max_drawdown=round(state._max_drawdown, 4),
        trade_count=len(state.trades),
        win_rate=round(state.get_win_rate(), 4),
        max_position_value=round(max_position_value, 4),
    )
