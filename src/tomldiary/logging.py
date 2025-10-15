"""Centralized logging configuration for tomldiary using loguru.

This module provides a consistent logging setup across all tomldiary components.
It uses loguru for its superior defaults and ease of use.

Configuration via environment variables:
    TOMLDIARY_LOG_LEVEL: Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                         Default: INFO
    TOMLDIARY_LOG_FILE: Optional file path for logging output
                        If set, logs will be written to this file in addition to stderr

Example:
    from tomldiary.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Starting operation")
    logger.debug("Debug details", extra_data=value)
"""

import os
import sys

from loguru import logger

# Remove default handler to reconfigure
logger.remove()

# Get configuration from environment
log_level = os.getenv("TOMLDIARY_LOG_LEVEL", "INFO").upper()
log_file = os.getenv("TOMLDIARY_LOG_FILE")

# Configure stderr handler with colored output
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=log_level,
    colorize=True,
)

# Add file handler if specified
if log_file:
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level,
        rotation="10 MB",  # Rotate when file reaches 10MB
        retention="1 week",  # Keep logs for 1 week
        compression="zip",  # Compress rotated logs
    )


def get_logger(name: str):
    """Get a logger instance for the given module name.

    Args:
        name: Usually __name__ from the calling module

    Returns:
        A loguru logger instance bound to the module name

    Example:
        logger = get_logger(__name__)
        logger.info("Message")
    """
    return logger.bind(name=name)


def configure_stdlib_logging_intercept():
    """Configure loguru to intercept standard library logging.

    This is useful for libraries that use standard logging.
    Call this function if you need compatibility with code using stdlib logging.

    Example:
        from tomldiary.logging import configure_stdlib_logging_intercept
        configure_stdlib_logging_intercept()
    """
    import logging

    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            # Get corresponding Loguru level if it exists
            level: str | int
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame = sys._getframe(6)
            depth = 6
            while frame and frame.f_code.co_filename == logging.__file__:
                if frame.f_back is None:
                    break
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# For convenience, expose the main logger directly
__all__ = ["logger", "get_logger", "configure_stdlib_logging_intercept"]
