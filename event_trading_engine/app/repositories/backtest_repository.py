"""Single repository covering all backtest persistence operations.

All methods accept domain objects from the engine layer and convert them
to ORM models internally. The engine layer never imports from this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from event_trading_engine.app.db.models import (
    MarketEventModel,
    OrderModel,
    PortfolioSnapshotModel,
    PositionModel,
    SignalModel,
    SimulationRunModel,
    TradeModel,
)
from event_trading_engine.engine.events import (
    MarketEvent,
    PortfolioSnapshot,
    Position,
    Signal,
    SimulatedOrder,
    Trade,
)


class BacktestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Simulation runs
    # ------------------------------------------------------------------

    def create_run(
        self,
        run_id: str,
        strategy_name: str,
        initial_cash: float = 100_000.0,
        config_json: str = "{}",
    ) -> SimulationRunModel:
        run = SimulationRunModel(
            id=run_id,
            strategy_name=strategy_name,
            status="RUNNING",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            ended_at=None,
            config_json=config_json,
            initial_cash=initial_cash,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def get_run(self, run_id: str) -> SimulationRunModel | None:
        return self.session.get(SimulationRunModel, run_id)

    def list_runs(self) -> list[SimulationRunModel]:
        return self.session.query(SimulationRunModel).order_by(
            SimulationRunModel.started_at.desc()
        ).all()

    def update_run_status(
        self,
        run_id: str,
        status: str,
        ended_at: datetime | None = None,
    ) -> None:
        run = self.session.get(SimulationRunModel, run_id)
        if run is None:
            raise ValueError(f"run {run_id} not found")
        run.status = status
        if ended_at is not None:
            run.ended_at = ended_at.replace(tzinfo=None) if ended_at.tzinfo else ended_at
        self.session.flush()

    # ------------------------------------------------------------------
    # Market events
    # ------------------------------------------------------------------

    def save_events(self, run_id: str, events: list[MarketEvent]) -> None:
        for e in events:
            ts = e.timestamp.replace(tzinfo=None) if e.timestamp.tzinfo else e.timestamp
            self.session.add(
                MarketEventModel(
                    id=str(e.event_id),
                    run_id=run_id,
                    timestamp=ts,
                    symbol=e.symbol,
                    event_type=e.event_type.value,
                    price=e.price,
                    volume=e.volume,
                    source=e.source,
                )
            )
        self.session.flush()

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def save_signals(self, run_id: str, signals: list[Signal]) -> None:
        for s in signals:
            ts = s.timestamp.replace(tzinfo=None) if s.timestamp.tzinfo else s.timestamp
            self.session.add(
                SignalModel(
                    id=str(s.signal_id),
                    run_id=run_id,
                    timestamp=ts,
                    symbol=s.symbol,
                    action=s.action.value,
                    quantity=s.quantity,
                    reason=s.reason,
                )
            )
        self.session.flush()

    def get_signals(self, run_id: str) -> list[SignalModel]:
        return (
            self.session.query(SignalModel)
            .filter(SignalModel.run_id == run_id)
            .order_by(SignalModel.timestamp)
            .all()
        )

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def save_orders(self, run_id: str, orders: list[SimulatedOrder]) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for o in orders:
            self.session.add(
                OrderModel(
                    id=str(o.order_id),
                    run_id=run_id,
                    signal_id=str(o.signal_id),
                    symbol=o.symbol,
                    side=o.side.value,
                    quantity=o.quantity,
                    requested_price=o.requested_price,
                    status=o.status.value,
                    rejection_reason=o.rejection_reason,
                    created_at=now,
                )
            )
        self.session.flush()

    def get_orders(self, run_id: str) -> list[OrderModel]:
        return (
            self.session.query(OrderModel)
            .filter(OrderModel.run_id == run_id)
            .all()
        )

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    def save_trades(self, run_id: str, trades: list[Trade]) -> None:
        for t in trades:
            ts = t.timestamp.replace(tzinfo=None) if t.timestamp.tzinfo else t.timestamp
            self.session.add(
                TradeModel(
                    id=str(t.trade_id),
                    run_id=run_id,
                    order_id=str(t.order_id),
                    symbol=t.symbol,
                    side=t.side.value,
                    quantity=t.quantity,
                    fill_price=t.fill_price,
                    fee=t.fee,
                    timestamp=ts,
                )
            )
        self.session.flush()

    def get_trades(self, run_id: str) -> list[TradeModel]:
        return (
            self.session.query(TradeModel)
            .filter(TradeModel.run_id == run_id)
            .order_by(TradeModel.timestamp)
            .all()
        )

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def save_positions(self, run_id: str, positions: list[Position]) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for p in positions:
            self.session.add(
                PositionModel(
                    id=str(uuid4()),
                    run_id=run_id,
                    symbol=p.symbol,
                    quantity=p.quantity,
                    average_cost=p.average_cost,
                    realized_pnl=p.realized_pnl,
                    unrealized_pnl=p.unrealized_pnl,
                    updated_at=now,
                )
            )
        self.session.flush()

    def get_positions(self, run_id: str) -> list[PositionModel]:
        return (
            self.session.query(PositionModel)
            .filter(PositionModel.run_id == run_id)
            .all()
        )

    # ------------------------------------------------------------------
    # Portfolio snapshots
    # ------------------------------------------------------------------

    def save_snapshots(self, run_id: str, snapshots: list[PortfolioSnapshot]) -> None:
        for s in snapshots:
            ts = s.timestamp.replace(tzinfo=None) if s.timestamp.tzinfo else s.timestamp
            self.session.add(
                PortfolioSnapshotModel(
                    id=str(uuid4()),
                    run_id=run_id,
                    timestamp=ts,
                    cash=s.cash,
                    equity=s.equity,
                    gross_exposure=s.gross_exposure,
                    net_exposure=s.net_exposure,
                    realized_pnl=s.realized_pnl,
                    unrealized_pnl=s.unrealized_pnl,
                    total_pnl=s.total_pnl,
                )
            )
        self.session.flush()

    def get_snapshots(self, run_id: str) -> list[PortfolioSnapshotModel]:
        return (
            self.session.query(PortfolioSnapshotModel)
            .filter(PortfolioSnapshotModel.run_id == run_id)
            .order_by(PortfolioSnapshotModel.timestamp)
            .all()
        )
