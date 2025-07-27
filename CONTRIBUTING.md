# Contributing to tomldiary

Thank you for your interest in contributing to tomldiary! This document provides guidelines and instructions for contributing.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tomldiary.git
cd tomldiary
```

2. Install dependencies with uv:
```bash
uv sync --group dev
```

3. Install pre-commit hooks:
```bash
uv run pre-commit install
```

## Running Tests

Run the test suite:
```bash
uv run pytest
```

Run with coverage:
```bash
uv run pytest --cov=tomldiary --cov-report=html
```

## Code Style

We use `ruff` for linting and formatting. The pre-commit hooks will automatically format your code, but you can also run manually:

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .
```

## Making Changes

1. Create a new branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and write tests

3. Run the test suite to ensure everything passes

4. Commit your changes:
```bash
git add .
git commit -m "feat: add new feature"
```

## Commit Messages

We follow conventional commits format:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `style:` - Code style changes
- `chore:` - Maintenance tasks

## Pull Request Process

1. Update documentation if needed
2. Ensure all tests pass
3. Update the README.md if needed
4. Submit a pull request with a clear description

## Reporting Issues

When reporting issues, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages/stack traces

## Questions?

Feel free to open an issue for any questions about contributing!