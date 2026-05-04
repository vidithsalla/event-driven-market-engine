"""BacktestRunner: processes a list of MarketEvents through the full engine pipeline.

Pipeline per price event:
  1. Skip duplicates (same event_id).
  2. Update portfolio state (prices, market open/close).
  3. Ask strategy for a signal.
  4. If BUY/SELL signal: create order, run risk check, execute if approved.
  5. Record snapshot.

Entry point: `python -m event_trading_engine.engine.backtest --input <csv>`
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from .events import (
    EventType,
    MarketEvent,
    OrderSide,
    OrderStatus,
    PortfolioSnapshot,
    Position,
    RiskMetrics,
    Signal,
    SignalAction,
    SimulatedOrder,
    Trade,
)
from .execution import ExecutionConfig, ExecutionEngine
from .metrics import compute_risk_metrics
from .portfolio import PortfolioState
from .risk import RiskConfig, RiskEngine
from .strategy import Strategy


@dataclass
class BacktestResult:
    run_id: UUID
    positions: list[Position]
    trades: list[Trade]
    orders: list[SimulatedOrder]
    signals: list[Signal]
    metrics: RiskMetrics
    snapshots: list[PortfolioSnapshot] = field(default_factory=list)


class BacktestRunner:
    def __init__(
        self,
        run_id: UUID,
        strategy: Strategy,
        initial_cash: float = 100_000.0,
        risk_config: RiskConfig | None = None,
        execution_config: ExecutionConfig | None = None,
    ) -> None:
        self.run_id = run_id
        self.strategy = strategy
        self.state = PortfolioState(run_id=run_id, initial_cash=initial_cash)
        self.risk_engine = RiskEngine(risk_config)
        self.execution_engine = ExecutionEngine(execution_config)
        self._orders: list[SimulatedOrder] = []
        self._signals: list[Signal] = []

    def process_event(self, event: MarketEvent) -> None:
        """Process a single event — used by the streaming consumer."""
        if self.state.is_duplicate_event(event.event_id):
            return

        self.state.mark_event_seen(event.event_id)
        self.state.on_market_event(event)

        if event.event_type in (EventType.PRICE_TICK, EventType.TRADE_PRINT):
            signal = self.strategy.on_event(event, self.state)
            if signal is not None:
                self._signals.append(signal)

            if signal is not None and signal.action in (SignalAction.BUY, SignalAction.SELL):
                order = SimulatedOrder(
                    order_id=uuid4(),
                    run_id=self.run_id,
                    signal_id=signal.signal_id,
                    symbol=signal.symbol,
                    side=OrderSide(signal.action.value),
                    quantity=signal.quantity,
                    requested_price=event.price,
                )
                self._orders.append(order)

                passes, reason = self.risk_engine.check(order, self.state)
                if passes:
                    market_price = self.state.latest_prices.get(event.symbol, event.price)
                    trade = self.execution_engine.execute(order, market_price, event.timestamp)
                    self.state.apply_trade(trade)
                else:
                    self.risk_engine.apply_rejection(order, reason)

    def run(self, events: list[MarketEvent]) -> BacktestResult:
        snapshots: list[PortfolioSnapshot] = []

        for event in events:
            self.process_event(event)
            snapshots.append(self.state.snapshot(event.timestamp))

        metrics = compute_risk_metrics(self.run_id, self.state)
        return BacktestResult(
            run_id=self.run_id,
            positions=list(self.state.positions.values()),
            trades=list(self.state.trades),
            orders=list(self._orders),
            signals=list(self._signals),
            metrics=metrics,
            snapshots=snapshots,
        )

    @staticmethod
    def load_events_from_csv(path: Path) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_price = row.get("price", "").strip()
                raw_volume = row.get("volume", "").strip()
                event = MarketEvent(
                    event_id=row["event_id"],
                    timestamp=row["timestamp"],
                    symbol=row["symbol"],
                    event_type=row["event_type"],
                    price=float(raw_price) if raw_price else 0.0,
                    volume=int(raw_volume) if raw_volume else 0,
                    source=row.get("source", "SIMULATED").strip() or "SIMULATED",
                )
                events.append(event)
        return events


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run a backtest from a CSV event file.")
    parser.add_argument("--input", required=True, help="Path to events CSV")
    parser.add_argument(
        "--strategy",
        default="ma_crossover",
        choices=["ma_crossover", "mean_reversion"],
        help="Strategy to use",
    )
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--short-window", type=int, default=5)
    parser.add_argument("--long-window", type=int, default=20)
    parser.add_argument("--quantity", type=int, default=10)
    args = parser.parse_args()

    run_id = uuid4()
    events = BacktestRunner.load_events_from_csv(Path(args.input))

    if args.strategy == "ma_crossover":
        from .strategy import MovingAverageCrossoverStrategy

        strategy: Strategy = MovingAverageCrossoverStrategy(
            run_id=run_id,
            symbol=args.symbol,
            short_window=args.short_window,
            long_window=args.long_window,
            quantity=args.quantity,
        )
    else:
        from .strategy import MeanReversionStrategy

        strategy = MeanReversionStrategy(
            run_id=run_id,
            symbol=args.symbol,
            window=args.long_window,
            quantity=args.quantity,
        )

    runner = BacktestRunner(run_id=run_id, strategy=strategy, initial_cash=args.initial_cash)
    result = runner.run(events)

    print(f"\nBacktest complete — run_id: {run_id}")
    print(f"Events processed : {len(events)}")
    print(f"Signals          : {len(result.signals)}")
    print(f"Orders           : {len(result.orders)}")
    print(f"Trades           : {len(result.trades)}")

    filled = [o for o in result.orders if o.status == OrderStatus.FILLED]
    rejected = [o for o in result.orders if o.status == OrderStatus.REJECTED_RISK]
    print(f"  Filled         : {len(filled)}")
    print(f"  Rejected       : {len(rejected)}")

    print("\nFinal Positions:")
    if result.positions:
        for pos in result.positions:
            if pos.quantity > 0:
                print(
                    f"  {pos.symbol}: qty={pos.quantity} avg_cost={pos.average_cost:.4f}"
                    f" unrealized_pnl={pos.unrealized_pnl:.2f}"
                )
    else:
        print("  (none)")

    print("\nTrades:")
    for t in result.trades:
        print(
            f"  {t.timestamp.isoformat()}  {t.side.value:4}  {t.quantity:3} {t.symbol}"
            f" @ {t.fill_price:.4f}  fee={t.fee:.4f}"
        )

    m = result.metrics
    print("\nMetrics:")
    print(f"  total_pnl        : {m.total_pnl:.4f}")
    print(f"  realized_pnl     : {m.realized_pnl:.4f}")
    print(f"  unrealized_pnl   : {m.unrealized_pnl:.4f}")
    print(f"  max_drawdown     : {m.max_drawdown:.4f}")
    print(f"  trade_count      : {m.trade_count}")
    print(f"  win_rate         : {m.win_rate:.4f}")
    print(f"  max_position_val : {m.max_position_value:.4f}")


if __name__ == "__main__":
    _main()
