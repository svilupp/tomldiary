.PHONY: install install-dev lint format test ci save help

# Default target
.DEFAULT_GOAL := help

# Help command
help:
	@echo "Available commands:"
	@echo "  make install      Install the package in development mode"
	@echo "  make install-dev  Install the package with development dependencies"
	@echo "  make lint         Run linting checks with ruff"
	@echo "  make format       Format code with ruff"
	@echo "  make test         Run tests with pytest"
	@echo "  make ci           Run linting and tests (for CI)"
	@echo "  make save         Stage changes and commit with a message"

# Install the package in development mode
install:
	uv pip install -e .

# Install with development dependencies
install-dev:
	uv pip install -e ".[dev]"

# Run linting
lint:
	ruff check src tests

# Format code
format:
	ruff format src tests
	ruff check --fix src tests

# Run tests
test:
	pytest

# CI target - run lint and test
ci: lint test

# Git save - add all changes and commit
save:
	@read -p "Enter commit message: " msg; \
	git add -A && \
	git commit -m "$$msg"