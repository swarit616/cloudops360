"""Structured (JSON) logging with automatic secret redaction.

Every log line is one JSON object with ``timestamp``, ``level``, ``event``,
``component`` and, when available, ``request_id`` and a ``context`` object.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

ROOT_LOGGER_NAME = "cloudops360"
REDACTED = "***REDACTED***"

# Correlates all log lines produced while handling one HTTP request.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_SENSITIVE_KEY = re.compile(
    r"pass(word)?|secret|token|api[_-]?key|access[_-]?key|credential|authorization|private[_-]?key",
    re.IGNORECASE,
)
_AWS_ACCESS_KEY_ID = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


def redact(value: Any, key: str | None = None) -> Any:
    """Return ``value`` with anything that looks like a secret replaced."""
    if key is not None and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _BEARER.sub(REDACTED, _AWS_ACCESS_KEY_ID.sub(REDACTED, value))
    return value


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "event": getattr(record, "event", None) or message,
            "component": record.name.removeprefix(f"{ROOT_LOGGER_NAME}."),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        context = getattr(record, "context", None)
        if context:
            payload["context"] = redact(context)
        if record.exc_info and record.exc_info[0] is not None:
            # Only the exception type: messages and tracebacks can contain secrets.
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON handler on the ``cloudops360`` logger (idempotent)."""
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False


def get_logger(component: str) -> logging.Logger:
    """Return the logger for a named component, e.g. ``remediation``."""
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{component}")


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    """Log a named event with structured context."""
    logger.log(level, event, extra={"event": event, "context": context})
