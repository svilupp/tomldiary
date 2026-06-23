.PHONY: help install install-dev lint format format-check typecheck test ci check save \
	_ck-lint _ck-format _ck-type _ck-test

# Default target
.DEFAULT_GOAL := help

# ANSI colors for the gate summary (export NO_COLOR=1 to disable).
ifndef NO_COLOR
GREEN := \033[32m
RED   := \033[31m
BOLD  := \033[1m
RESET := \033[0m
endif

# Tool invocations live here once so the verbose targets and the quiet gate run
# byte-identical commands (and stay aligned with .github/workflows/ci.yml).
LINT_CMD      := uv run ruff check src tests
FMT_CHECK_CMD := uv run ruff format --check src tests
TYPECHECK_CMD := uv run mypy src/tomldiary
TEST_CMD      := uv run -m pytest --cov=tomldiary --cov-report=term-missing

# run_quiet: run a command with NO output on success (success = silence) and the
# full combined stdout+stderr only on failure. Used by the standalone checks.
#   usage:  @$(call run_quiet,$(LINT_CMD))
define run_quiet
out=$$($(1) 2>&1); st=$$?; [ $$st -eq 0 ] || { printf '%s\n' "$$out"; exit $$st; }
endef

# run_check: like run_quiet but prints a one-line "<label>: OK" on success (and
# "<label>: FAIL" + the full output on failure). Used by the `ci`/`check` gate so
# each leg reports that it ran.
#   usage:  @$(call run_check,Lint,$(LINT_CMD))
define run_check
out=$$($(2) 2>&1); st=$$?; if [ $$st -eq 0 ]; then printf '  $(GREEN)%-11s OK$(RESET)\n' '$(1):'; else printf '  $(RED)%-11s FAIL$(RESET)\n' '$(1):'; printf '%s\n' "$$out"; exit $$st; fi
endef

# Help command
help:
	@echo "Available commands:"
	@echo "  make install      Install the package in development mode"
	@echo "  make install-dev  Install the package with development dependencies"
	@echo "  make lint         Run ruff lint checks (quiet unless it fails)"
	@echo "  make format       Format + autofix with ruff (mutates files)"
	@echo "  make format-check Check formatting without mutating (quiet unless it fails)"
	@echo "  make typecheck    Run mypy (quiet unless it fails)"
	@echo "  make test         Run pytest with coverage (verbose)"
	@echo "  make ci           Full gate: lint + format-check + typecheck + test (quiet, prints OK per leg)"
	@echo "  make check        Alias for 'make ci'"
	@echo "  make save         Stage all changes and commit with a message"

# Install the package in development mode
install:
	uv pip install -e .

# Install with development dependencies
install-dev:
	uv pip install -e ".[dev]"

# Static-check targets: SILENT on success, full output only on failure.
lint:
	@$(call run_quiet,$(LINT_CMD))

format-check:
	@$(call run_quiet,$(FMT_CHECK_CMD))

typecheck:
	@$(call run_quiet,$(TYPECHECK_CMD))

# Format code (mutates files; stays verbose so you see what changed).
format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

# Tests stay verbose when run directly.
test:
	$(TEST_CMD)

# Full hygiene gate: quiet on success, one "<name>: OK" line per leg.
ci:
	@printf '$(BOLD)Running make ci...$(RESET)\n'
	@$(MAKE) --no-print-directory _ck-lint _ck-format _ck-type _ck-test
	@printf '$(GREEN)$(BOLD)All checks passed.$(RESET)\n'

# Alias for ci.
check: ci

# OK-printing wrappers used only by the gate (the public targets stay
# silent-on-success; the public `test` target stays verbose).
_ck-lint:
	@$(call run_check,Lint,$(LINT_CMD))

_ck-format:
	@$(call run_check,Format,$(FMT_CHECK_CMD))

_ck-type:
	@$(call run_check,Typecheck,$(TYPECHECK_CMD))

_ck-test:
	@$(call run_check,Tests,$(TEST_CMD))

# Git save - add all changes and commit
save:
	@read -p "Enter commit message: " msg; \
	git add -A && \
	git commit -m "$$msg"
