.DEFAULT_GOAL := help

.PHONY: help dev test lint typecheck fmt ci clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Run SDeck locally
	uv run sdeck

test: ## Run tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=sdeck --cov-fail-under=80

lint: ## Run linter
	uv run ruff check .

typecheck: ## Run type checker
	uv run mypy src

fmt: ## Format code
	uv run ruff format .

ci: lint typecheck test ## Run full CI suite locally

clean: ## Clean build artifacts
	rm -rf dist/ build/ __pycache__/ .mypy_cache/ .pytest_cache/ .ruff_cache/ .coverage htmlcov/
