# Contributing to tomldiary

Thank you for your interest in contributing to tomldiary! This document provides guidelines and instructions for contributing.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tomldiary.git
cd tomldiary
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

## Running Tests

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=tomldiary --cov-report=html
```

## Code Style

We use `ruff` for linting and formatting. The pre-commit hooks will automatically format your code, but you can also run manually:

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Fix auto-fixable issues
ruff check --fix .
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