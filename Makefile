# MedAxis Platform — Developer Makefile
# Usage: make <target>
# Prerequisites: Docker, Docker Compose, Python 3.12+

.PHONY: help up down build logs seed test lint clean ps restart

COMPOSE     = docker compose
COMPOSE_DEV = $(COMPOSE) -f docker-compose.yml
COMPOSE_PRD = $(COMPOSE) -f docker-compose.prod.yml

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Development ───────────────────────────────────────────────────────────────

up: ## Start all services (dev)
	$(COMPOSE_DEV) up -d --build

down: ## Stop all services (dev)
	$(COMPOSE_DEV) down

build: ## Rebuild all images (dev)
	$(COMPOSE_DEV) build --no-cache

logs: ## Tail logs for all services
	$(COMPOSE_DEV) logs -f

logs-%: ## Tail logs for a specific service  e.g. make logs-auth-service
	$(COMPOSE_DEV) logs -f $*

ps: ## Show running containers
	$(COMPOSE_DEV) ps

restart: ## Restart all services without rebuilding
	$(COMPOSE_DEV) restart

restart-%: ## Restart a single service  e.g. make restart-billing-service
	$(COMPOSE_DEV) restart $*

shell-%: ## Open a shell in a running container  e.g. make shell-auth-service
	$(COMPOSE_DEV) exec $* sh

# ── Data ──────────────────────────────────────────────────────────────────────

seed: ## Seed demo data (services must be running)
	python init-db/02_seed_data.py

seed-wait: ## Wait for services then seed
	@echo "Waiting 30s for services to be ready..."
	sleep 30
	python init-db/02_seed_data.py

cache-clear: ## Clear the reporting Redis cache
	$(COMPOSE_DEV) exec redis redis-cli DEL "dashboard:cache"

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run all tests
	pytest tests/ services/ -v --tb=short --asyncio-mode=auto

test-cov: ## Run tests with coverage report
	pytest tests/ services/ -v --tb=short --asyncio-mode=auto --cov=services --cov-report=html

lint: ## Lint all Python code with ruff
	ruff check services/ shared/

lint-fix: ## Lint and auto-fix
	ruff check --fix services/ shared/

# ── Production ────────────────────────────────────────────────────────────────

prod-up: ## Start production stack
	$(COMPOSE_PRD) up -d --build

prod-down: ## Stop production stack
	$(COMPOSE_PRD) down

prod-logs: ## Tail production logs
	$(COMPOSE_PRD) logs -f

prod-ps: ## Show production containers
	$(COMPOSE_PRD) ps

cert-gen: ## Generate self-signed TLS certs for local HTTPS testing
	bash nginx/generate-self-signed-cert.sh

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean: ## Remove stopped containers, dangling images, and volumes
	$(COMPOSE_DEV) down -v --remove-orphans
	docker image prune -f

clean-all: ## Full cleanup including all images (WARNING: destructive)
	$(COMPOSE_DEV) down -v --remove-orphans
	docker system prune -af

# ── Utilities ─────────────────────────────────────────────────────────────────

env: ## Copy .env.example to .env (skips if .env already exists)
	@test -f .env && echo ".env already exists — skipping" || (cp .env.example .env && echo "Created .env from .env.example")

db-shell: ## Open a psql shell on the postgres container
	$(COMPOSE_DEV) exec postgres psql -U postgres

health: ## Check health of all gateway services
	curl -s http://localhost:8000/health | python -m json.tool
