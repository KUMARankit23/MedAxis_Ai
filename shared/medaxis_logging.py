"""
MedAxis — Shared structured JSON logging with correlation ID propagation.

Usage in each service:
    from medaxis_logging import setup_logging, get_logger, correlation_id_var

    setup_logging(service_name="auth-service")
    logger = get_logger(__name__)

    # In FastAPI middleware:
    correlation_id_var.set(request.headers.get("X-Correlation-ID", str(uuid.uuid4())))
"""
import json
import logging
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

# Context variable — stores correlation ID for the current async task
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class _StructuredFormatter(logging.Formatter):
    """Emit every log record as a single-line JSON object."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "correlation_id": correlation_id_var.get("-"),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach any extra fields passed via logger.info("msg", extra={...})
        for key, val in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "taskName",
            ):
                entry[key] = val

        if record.exc_info:
            entry["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            entry["exception_message"] = str(record.exc_info[1])
            entry["traceback"] = traceback.format_exception(*record.exc_info)

        return json.dumps(entry, default=str)


def setup_logging(service_name: str, level: Optional[str] = None) -> None:
    """
    Configure root logger with structured JSON output.
    Call once at application startup.
    """
    import os
    log_level = getattr(logging, (level or os.getenv("LOG_LEVEL", "INFO")).upper(), logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(_StructuredFormatter(service_name))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call after setup_logging()."""
    return logging.getLogger(name)
