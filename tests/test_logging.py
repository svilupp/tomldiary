"""Tests for tomldiary logging configuration."""

import logging

import pytest

from tomldiary.logging import configure_stdlib_logging_intercept


@pytest.fixture
def restore_root_logging():
    """Snapshot and restore root logger state mutated by basicConfig(force=True)."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    try:
        yield
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


def test_intercept_handles_shallow_record(restore_root_logging):
    """A pre-built record forwarded via handle() has a shallow stack.

    The old hardcoded sys._getframe(6) raised ValueError on such stacks.
    """
    configure_stdlib_logging_intercept()

    record = logging.LogRecord(
        name="shallow.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="forwarded message",
        args=(),
        exc_info=None,
    )

    # Must not raise ValueError: call stack is not deep enough.
    logging.getLogger("shallow.test").handle(record)


def test_intercept_normal_logging_call(restore_root_logging):
    """A normal logger.info() call must still work after intercept."""
    configure_stdlib_logging_intercept()

    logging.getLogger("normal.test").info("hello from stdlib logging")
