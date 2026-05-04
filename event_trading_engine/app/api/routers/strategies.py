"""Strategy listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from event_trading_engine.app.api.schemas import StrategyInfo

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

_STRATEGIES = [
    StrategyInfo(
        name="ma_crossover",
        description="Buy when short MA crosses above long MA; sell when it crosses below.",
        parameters=["symbol", "short_window", "long_window", "quantity"],
    ),
    StrategyInfo(
        name="mean_reversion",
        description="Buy when price z-score drops below -threshold; sell when it rises above threshold.",
        parameters=["symbol", "window", "z_threshold", "quantity"],
    ),
]


@router.get("", response_model=list[StrategyInfo])
def list_strategies():
    return _STRATEGIES
