"""Redis-backed live state cache for streaming simulation runs."""

import json
from typing import Any

import redis

from event_trading_engine.engine.portfolio import PortfolioState


class StateCache:
    """Wraps a Redis client to store streaming run state."""

    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    # ------------------------------------------------------------------
    # Seen-event deduplication
    # ------------------------------------------------------------------

    def mark_seen(self, run_id: str, event_id: str) -> None:
        self._r.sadd(f"seen_events:{run_id}", event_id)

    def is_seen(self, run_id: str, event_id: str) -> bool:
        return bool(self._r.sismember(f"seen_events:{run_id}", event_id))

    # ------------------------------------------------------------------
    # Portfolio snapshot
    # ------------------------------------------------------------------

    def save_portfolio(self, run_id: str, state: PortfolioState) -> None:
        payload = {
            "cash": state.cash,
            "market_open": state.market_open,
            "realized_pnl": sum(p.realized_pnl for p in state.positions.values()),
            "unrealized_pnl": sum(p.unrealized_pnl for p in state.positions.values()),
        }
        self._r.set(f"portfolio:{run_id}", json.dumps(payload))

    def get_portfolio(self, run_id: str) -> dict[str, Any] | None:
        raw = self._r.get(f"portfolio:{run_id}")
        if raw is None:
            return None
        return json.loads(raw)

    # ------------------------------------------------------------------
    # Per-symbol position
    # ------------------------------------------------------------------

    def save_position(self, run_id: str, symbol: str, quantity: float, avg_cost: float) -> None:
        payload = {"quantity": quantity, "average_cost": avg_cost}
        self._r.set(f"position:{run_id}:{symbol}", json.dumps(payload))

    def get_position(self, run_id: str, symbol: str) -> dict[str, Any] | None:
        raw = self._r.get(f"position:{run_id}:{symbol}")
        if raw is None:
            return None
        return json.loads(raw)

    def save_state(self, run_id: str, state: PortfolioState) -> None:
        """Persist portfolio summary and all positions in one call."""
        self.save_portfolio(run_id, state)
        for symbol, pos in state.positions.items():
            self.save_position(run_id, symbol, pos.quantity, pos.average_cost)

    def flush_run(self, run_id: str) -> None:
        """Delete all keys for a run (e.g. after completion)."""
        for key in self._r.scan_iter(f"*:{run_id}*"):
            self._r.delete(key)
