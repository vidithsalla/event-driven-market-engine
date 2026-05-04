"""SimulationService: runs a backtest and persists all results to the database.

This is the boundary between the engine (pure Python, no DB) and the persistence
layer. It calls the engine, then uses BacktestRepository to write results.
The engine modules are never imported from the DB layer, only from here.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from event_trading_engine.app.db.models import SimulationRunModel
from event_trading_engine.app.repositories.backtest_repository import BacktestRepository
from event_trading_engine.engine.backtest import BacktestResult, BacktestRunner
from event_trading_engine.engine.execution import ExecutionConfig
from event_trading_engine.engine.risk import RiskConfig
from event_trading_engine.engine.strategy import Strategy


class SimulationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = BacktestRepository(session)

    def run_backtest_from_csv(
        self,
        run_id: UUID,
        csv_path: Path,
        strategy: Strategy,
        initial_cash: float = 100_000.0,
        risk_config: RiskConfig | None = None,
        execution_config: ExecutionConfig | None = None,
        save_events: bool = False,
        save_snapshots: bool = False,
    ) -> BacktestResult:
        run_id_str = str(run_id)
        config = {
            "strategy": strategy.name,
            "initial_cash": initial_cash,
            "risk": vars(risk_config) if risk_config else {},
            "execution": vars(execution_config) if execution_config else {},
        }

        self.repo.create_run(
            run_id=run_id_str,
            strategy_name=strategy.name,
            initial_cash=initial_cash,
            config_json=json.dumps(config),
        )

        try:
            events = BacktestRunner.load_events_from_csv(csv_path)

            runner = BacktestRunner(
                run_id=run_id,
                strategy=strategy,
                initial_cash=initial_cash,
                risk_config=risk_config,
                execution_config=execution_config,
            )
            result = runner.run(events)

            if save_events:
                self.repo.save_events(run_id_str, events)

            self.repo.save_signals(run_id_str, result.signals)
            self.repo.save_orders(run_id_str, result.orders)
            self.repo.save_trades(run_id_str, result.trades)
            self.repo.save_positions(run_id_str, result.positions)

            if save_snapshots:
                self.repo.save_snapshots(run_id_str, result.snapshots)

            self.repo.update_run_status(
                run_id_str,
                "COMPLETED",
                ended_at=datetime.now(timezone.utc),
            )

        except Exception:
            self.repo.update_run_status(
                run_id_str,
                "FAILED",
                ended_at=datetime.now(timezone.utc),
            )
            raise

        return result

    def get_run(self, run_id: str) -> SimulationRunModel | None:
        return self.repo.get_run(run_id)

    def list_runs(self) -> list[SimulationRunModel]:
        return self.repo.list_runs()

    def get_trades(self, run_id: str):
        return self.repo.get_trades(run_id)

    def get_positions(self, run_id: str):
        return self.repo.get_positions(run_id)

    def get_orders(self, run_id: str):
        return self.repo.get_orders(run_id)

    def get_signals(self, run_id: str):
        return self.repo.get_signals(run_id)

    def get_snapshots(self, run_id: str):
        return self.repo.get_snapshots(run_id)
