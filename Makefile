.PHONY: up down build restart logs shell db-shell test lint help

## Show this help message
help:
	@echo "LLM Researcher - Available Make Commands"
	@echo "========================================"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /'
	@echo ""

## Start all services
up:
	docker compose up -d

## Stop all services
down:
	docker compose down

## Build Docker images
build:
	docker compose build

## Rebuild and restart all services
restart:
	docker compose down
	docker compose up -d --build

## Follow logs for all services (use svc=<service> to filter)
logs:
	docker compose logs -f $(svc)

## Open a shell in the app container
shell:
	docker compose exec app bash

## Open a psql shell in the db container
db-shell:
	docker compose exec db psql -U postgres -d researcher

## Run tests inside the app container
test:
	docker compose exec app pytest tests/ -v

## Run WebSocket and real-time features test
ws:
	docker compose exec app python -m pytest tests/test_websocket_researcher.py -v

## Run linter inside the app container
lint:
	docker compose exec app ruff check app/

## Start services and stream logs
dev:
	docker compose up -d --build db app grobid
	docker compose stop frontend || true
	cd frontend && npm run dev
## Database Migrations
## Run pending migrations
migrate:
	docker compose exec app alembic upgrade head

## Create a new migration (use msg="description" to set message)
migration:
	docker compose exec app alembic revision --autogenerate -m "$(msg)"

## Rollback last migration
migrate-down:
	docker compose exec app alembic downgrade -1

## Show current migration revision
migrate-status:
	docker compose exec app alembic current

## Frontend Commands
## Install frontend dependencies
frontend-install:
	cd frontend && npm install

## Start frontend dev server (with hot reload)
frontend-dev:
	cd frontend && npm run dev

## Build frontend for production
frontend-build:
	cd frontend && npm run build

## Open frontend shell
frontend-shell:
	docker compose exec frontend sh

## Show migration history
migrate-history:
	docker compose exec app alembic history

## Run an end-to-end smoke test (in-process, no server needed)
## Usage: make e2e query="my research question"
e2e:
	.venv/bin/python scripts/smoke_research.py "$(query)"

## Start the local dev server (SQLite, no Docker) on http://127.0.0.1:8000
local-dev:
	.venv/bin/python scripts/dev_server.py

## Stop the local dev server
local-down:
	@pkill -f "scripts/dev_server.py" || echo "No dev server running."