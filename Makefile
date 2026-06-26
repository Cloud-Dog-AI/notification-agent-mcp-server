# Makefile for Notification Agent MCP Server
# Version: 0.1.0

.PHONY: help install dev up down test lint format clean

help: ## Show this help message
	@echo "Notification Agent MCP Server - Make Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

dev: ## Start development servers locally
	@test -n "$(ENV_FILE)" || (echo "Set ENV_FILE"; exit 1)
	@echo "Starting API server on <API_BASE_URL>"
	python start_api_server.py --env $(ENV_FILE) &
	@echo "Starting Web UI on <WEB_BASE_URL>"
	python start_web_server.py --env $(ENV_FILE) &
	@echo "Starting MCP server on <MCP_PORT>"
	python start_mcp_server.py --env $(ENV_FILE) &
	@echo "Starting A2A server on <A2A_PORT>"
	python start_a2a_server.py --env $(ENV_FILE) &
	@echo "All servers started. Use 'make stop' to shutdown."

up: ## Start all services with Docker Compose
	docker-compose up -d
	@echo "Services starting..."
	@echo "API Server: <API_BASE_URL>"
	@echo "Web UI: <WEB_BASE_URL>"
	@echo "MCP Server: <MCP_BASE_URL>"
	@echo "A2A Server: <A2A_BASE_URL>"

down: ## Stop all Docker Compose services
	docker-compose down

logs: ## View Docker Compose logs
	docker-compose logs -f

test: ## Run all tests (with timeout and live output)
	pytest test/ --cov=src --cov-report=term --cov-report=html

test-unit: ## Run unit tests only (with timeout and live output)
	pytest test/test_config.py test/test_database.py test/test_job_manager.py test/test_adapters.py

test-api: ## Run API tests (requires running server, with timeout and live output)
	pytest test/test_api_server.py test/test_messages_api.py test/test_channels_api.py

test-integration: ## Run integration tests (with timeout and live output)
	pytest test/test_background_workers.py test/test_reliability.py

lint: ## Run code linters
	flake8 src/ test/ --max-line-length=120 --exclude=__pycache__
	mypy src/ --ignore-missing-imports

format: ## Format code with black and isort
	black src/ test/ --line-length=120
	isort src/ test/ --profile=black

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf cache/*.json cache/backups/*
	rm -f logs/*.log

db-migrate: ## Apply database migrations
	python scripts/migrate_database.py

db-reset: ## Reset database (WARNING: destroys all data)
	rm -f database/notify.db
	python scripts/migrate_database.py

health: ## Check health of all services
	@echo "Checking API server..."
	@test -n "$(API_BASE_URL)" || (echo "Set API_BASE_URL"; exit 1)
	@curl -s $(API_BASE_URL)/health | python -m json.tool || echo "API server not responding"
	@echo "\nChecking Web UI..."
	@test -n "$(WEB_BASE_URL)" || (echo "Set WEB_BASE_URL"; exit 1)
	@curl -s -o /dev/null -w "Status: %{http_code}\n" $(WEB_BASE_URL)/ || echo "Web UI not responding"

stop: ## Stop all local development processes
	@pkill -f "start_api_server.py" || true
	@pkill -f "start_web_server.py" || true
	@pkill -f "start_mcp_server.py" || true
	@pkill -f "start_a2a_server.py" || true
	@echo "All servers stopped."

