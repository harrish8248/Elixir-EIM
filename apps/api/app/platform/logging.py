"""
Enterprise Structured JSON Logger with Correlation and Tenant Context.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from apps.api.app.platform.config import settings
from apps.api.app.platform.correlation import get_correlation_id


class JSONFormatter(logging.Formatter):
    """Formats log records into single-line structured JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        # Include custom extra attributes if present
        if hasattr(record, "tenant_id"):
            log_entry["tenant_id"] = record.tenant_id
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging() -> logging.Logger:
    """Configures structured JSON logging for the application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    if settings.log_format.lower() == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(console_handler)
    return logging.getLogger("elixir.platform")


logger = setup_logging()
