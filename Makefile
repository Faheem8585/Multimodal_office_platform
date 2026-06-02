# Convenience targets. Backend commands assume backend/.venv is set up.
.PHONY: help up down seed logs be-install be-test be-lint be-fmt fe-install fe-dev fe-build openapi

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'

up: ## Start the full local stack (Docker Compose)
	docker compose up --build

down: ## Stop the stack
	docker compose down

seed: ## Seed roles, users, and default workflows
	docker compose exec api python -m app.initial_data

logs: ## Tail API + worker logs
	docker compose logs -f api worker

be-install: ## Install backend (full + dev) into a local venv
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[full,dev]"

be-test: ## Run backend tests
	cd backend && . .venv/bin/activate && pytest

be-lint: ## Lint + type-check backend
	cd backend && . .venv/bin/activate && ruff check app tests && black --check app tests && mypy app

be-fmt: ## Auto-format backend
	cd backend && . .venv/bin/activate && ruff check app tests --fix && black app tests

fe-install: ## Install frontend deps
	cd frontend && npm install

fe-dev: ## Run the frontend dev server
	cd frontend && npm run dev

fe-build: ## Build + type-check the frontend
	cd frontend && npm run typecheck && npm run build

openapi: ## Regenerate docs/openapi.json from the app
	cd backend && . .venv/bin/activate && \
	JWT_SECRET=doc-gen-secret-1234567890xx ENVIRONMENT=dev \
	python -c "import json, app.main as m; open('../docs/openapi.json','w').write(json.dumps(m.app.openapi(), indent=2))"
