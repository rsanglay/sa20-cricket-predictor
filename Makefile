.PHONY: help dev test migrate seed train sim clean install

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

dev: ## Run docker compose in dev mode
	docker-compose up --build

dev-detached: ## Run docker compose in detached mode
	docker-compose up -d --build

dev-down: ## Stop docker compose
	docker-compose down

migrate: ## Run Alembic migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new Alembic migration (usage: make migrate-create NAME=description)
	cd backend && alembic revision --autogenerate -m "$(NAME)"

migrate-downgrade: ## Downgrade one migration
	cd backend && alembic downgrade -1

seed: ## Load seed data
	cd backend && python data_pipeline/seed_database.py

train: ## Train ML models
	cd backend && python -m app.ml.training.train_match_model
	cd backend && python -m app.ml.training.train_player_models

sim: ## Run season simulation (1000 runs)
	cd backend && python -c "from app.services.prediction_service import PredictionService; from app.db.session import SessionLocal; service = PredictionService(SessionLocal()); result = service.simulate_season(1000); print(result)"

test: ## Run unit + integration tests
	cd backend && pytest tests/ -v

test-unit: ## Run unit tests only
	cd backend && pytest tests/unit/ -v

test-integration: ## Run integration tests only
	cd backend && pytest tests/integration/ -v

test-e2e: ## Run E2E tests (headless)
	cd frontend && npm run test:e2e

lint: ## Run linters
	cd backend && ruff check . && black --check . && isort --check .
	cd frontend && npm run lint

format: ## Format code
	cd backend && black . && isort .
	cd frontend && npm run format

typecheck: ## Type check code
	cd backend && mypy app/
	cd frontend && npm run typecheck

install: ## Install dependencies
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	cd backend && rm -rf .pytest_cache .mypy_cache .ruff_cache
	cd frontend && rm -rf node_modules/.cache dist

db-reset: ## Reset database (WARNING: deletes all data)
	docker-compose down -v
	docker-compose up -d postgres redis
	sleep 5
	$(MAKE) migrate
	$(MAKE) seed

strategy: ## Run strategy advisor smoke tests
	cd backend && python -c "from app.services.simulate import xi_optimizer, bowling_advisor, drs_model; print('Strategy services available')"

fantasy: ## Run fantasy optimizer with sample slate
	cd backend && python -c "from app.services.fantasy import optimizer; print('Fantasy optimizer available')"

