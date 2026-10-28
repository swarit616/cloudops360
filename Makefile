.DEFAULT_GOAL := help
PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
TF_DIRS := terraform/aws terraform/azure

.PHONY: help install test lint format run docker-up docker-down docker-logs terraform-fmt terraform-check security health clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: ## Create .venv and install dependencies
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements-dev.txt
	@test -f .env || cp .env.example .env

test: ## Run the test-suite
	$(BIN)/python -m pytest

lint: ## Ruff + Black (check only)
	$(BIN)/ruff check .
	$(BIN)/black --check .

format: ## Auto-format and apply safe lint fixes
	$(BIN)/ruff check --fix .
	$(BIN)/black .

run: ## Run the API locally with auto-reload (http://127.0.0.1:8000/docs)
	$(BIN)/uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000

docker-up: ## Build and start API + Prometheus + Grafana + Node Exporter
	docker compose up -d --build

docker-down: ## Stop the stack (add -v manually to also delete volumes)
	docker compose down

docker-logs: ## Follow the API logs
	docker compose logs -f cloudops-api

terraform-fmt: ## Format Terraform files
	terraform fmt -recursive terraform

terraform-check: ## fmt check + init (no backend) + validate for AWS and Azure
	@set -e; for dir in $(TF_DIRS); do \
	    echo "== $$dir =="; \
	    terraform -chdir=$$dir fmt -check -recursive; \
	    terraform -chdir=$$dir init -backend=false -input=false >/dev/null; \
	    terraform -chdir=$$dir validate; \
	done

security: ## Static security checks (bandit + pip-audit)
	$(BIN)/bandit -q -r app -ll
	$(BIN)/pip-audit -r requirements.txt

health: ## Probe the running stack
	./scripts/health_check.sh

clean: ## Remove caches and the virtualenv
	rm -rf $(VENV) .pytest_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
