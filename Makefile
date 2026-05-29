.DEFAULT_GOAL := help

.PHONY: help up down logs shell-be shell-fe test lint collect-all catalog forecast migrate bootstrap

help: ## Show this help message
	@echo "SupplyTracker — available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Build and start all services in detached mode
	docker compose up -d --build

down: ## Stop and remove all containers
	docker compose down

logs: ## Follow logs for all services (last 200 lines)
	docker compose logs -f --tail=200

shell-be: ## Open a bash shell in the backend container
	docker compose exec backend bash

shell-fe: ## Open a sh shell in the frontend container
	docker compose exec frontend sh

test: ## Run the backend test suite with pytest
	docker compose exec -w /app/backend backend python -m pytest -q

lint: ## Run ruff and mypy against the backend
	docker compose exec -w /app/backend backend ruff check . && docker compose exec -w /app/backend backend mypy app

migrate: ## Apply all pending Alembic migrations
	docker compose exec -w /app/backend backend alembic upgrade head

bootstrap: ## Migrate then seed the development database
	$(MAKE) migrate && docker compose exec -w /app/backend backend python -m app.scripts.seed_dev

collect-all: ## Trigger full data collection across all sources
	docker compose exec -w /app/backend backend python -m app.scripts.collect_all

forecast: ## Run the freight-rate forecast pipeline
	docker compose exec -w /app/backend backend python -m app.scripts.run_forecast
