"""structlog JSON logging configuration."""

from __future__ import annotations

import logging

_configured = False


def configure_structlog() -> None:
    """Configure structlog with JSON output. Safe to call multiple times."""
    global _configured
    if _configured:
        return
    try:
        import structlog  # type: ignore[import-untyped]

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )
        _configured = True
        logging.getLogger(__name__).info("structlog JSON logging configured")
    except ImportError:
        logging.info("structlog not installed — using standard logging format")
