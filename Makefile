.PHONY: install install-historical test test-cov lint lint-fix \
        run-sample run-mean-reversion \
        fetch-historical \
        db-up db-down db-seed db-reset \
        infra-up infra-down \
        produce consume \
        api \
        frontend frontend-build \
        clean

install:
	pip install -e ".[dev]"

install-historical:
	pip install -e ".[dev,historical]"

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

test:
	pytest tests/ -v

test-integration:
	pytest tests/ -v --integration

test-cov:
	pytest tests/ -v --cov=event_trading_engine --cov-report=term-missing

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------

lint:
	ruff check event_trading_engine/ tests/ scripts/

lint-fix:
	ruff check --fix event_trading_engine/ tests/ scripts/

# ---------------------------------------------------------------------------
# Local backtest (no DB required)
# ---------------------------------------------------------------------------

run-sample:
	python -m event_trading_engine.engine.backtest \
		--input data/sample_events.csv \
		--strategy ma_crossover \
		--symbol AAPL \
		--short-window 5 \
		--long-window 20 \
		--quantity 10

run-mean-reversion:
	python -m event_trading_engine.engine.backtest \
		--input data/sample_events.csv \
		--strategy mean_reversion \
		--symbol AAPL \
		--long-window 20 \
		--quantity 10

# ---------------------------------------------------------------------------
# Historical data adapter (Phase 7 — requires make install-historical)
# ---------------------------------------------------------------------------

fetch-historical:
	python scripts/fetch_historical.py \
		--symbol AAPL \
		--start 2024-01-01 \
		--end 2024-04-01 \
		--interval 1h

# ---------------------------------------------------------------------------
# Postgres only (Phase 2)
# ---------------------------------------------------------------------------

db-up:
	docker compose up -d postgres adminer
	@echo "Postgres available at localhost:5432"
	@echo "Adminer UI at http://localhost:8080"

db-down:
	docker compose down

db-seed:
	python scripts/seed.py

db-reset:
	docker compose down -v
	docker compose up -d postgres adminer
	@sleep 3
	python scripts/seed.py

# ---------------------------------------------------------------------------
# Full infra: Postgres + Redpanda + Redis (Phase 3)
# ---------------------------------------------------------------------------

infra-up:
	docker compose up -d
	@echo "Postgres   : localhost:5432"
	@echo "Redpanda   : localhost:9092"
	@echo "Redis      : localhost:6379"
	@echo "Adminer UI : http://localhost:8080"

infra-down:
	docker compose down

# ---------------------------------------------------------------------------
# Streaming helpers (require infra-up)
# ---------------------------------------------------------------------------

produce:
	python scripts/produce.py

consume:
	python scripts/consume.py

# ---------------------------------------------------------------------------
# API server (Phase 4)
# ---------------------------------------------------------------------------

api:
	uvicorn event_trading_engine.app.api.app:app --reload --port 8000

# ---------------------------------------------------------------------------
# Frontend (Phase 5)
# ---------------------------------------------------------------------------

frontend:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .pytest_cache/
	rm -rf frontend/dist
