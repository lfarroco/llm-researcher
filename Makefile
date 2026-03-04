.PHONY: up down build restart logs shell db-shell test lint

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

## Run linter inside the app container
lint:
	docker compose exec app ruff check app/

## Start services and stream logs
dev:
	docker compose up --build
