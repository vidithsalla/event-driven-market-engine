"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from event_trading_engine.app.api.routers import portfolio, runs, strategies, trades


def create_app() -> FastAPI:
    app = FastAPI(
        title="Event-Driven Trading Simulation Engine",
        description="REST API for running simulations, querying trades, positions, and metrics.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(runs.router)
    app.include_router(trades.router)
    app.include_router(portfolio.router)
    app.include_router(strategies.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("event_trading_engine.app.api.app:app", host="0.0.0.0", port=8000, reload=True)
