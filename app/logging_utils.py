"""Structured JSON logging plus a small in-memory buffer for the console.

The buffer lets the operator console show recent requests without a log
shipping stack. In a real environment this role belongs to Splunk, Datadog,
Loki or similar.
"""
import json
import logging
import sys
import threading
from collections import deque
from datetime import datetime, timezone

LOGGER_NAME = "productionwatch"
# Field names that must never be written to logs, even if passed by mistake.
REDACTED_KEYS = {"token", "demo_token", "authorization", "x-demo-token", "password"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        extra = getattr(record, "fields", None) or {}
        for key, value in extra.items():
            entry[key] = "[REDACTED]" if key.lower() in REDACTED_KEYS else value
        return json.dumps(entry, default=str)


class RecentLogBuffer(logging.Handler):
    """Keeps the most recent structured log entries in memory."""

    def __init__(self, maxlen: int = 500):
        super().__init__()
        self._entries: deque[dict] = deque(maxlen=maxlen)
        self._lock_entries = threading.Lock()
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        entry = json.loads(self.format(record))
        with self._lock_entries:
            self._entries.append(entry)

    def recent(self, limit: int = 50) -> list[dict]:
        with self._lock_entries:
            items = list(self._entries)
        return items[-limit:][::-1]

    def snapshot(self) -> list[dict]:
        with self._lock_entries:
            return list(self._entries)


def configure_logging(level: str, buffer: RecentLogBuffer) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(JsonFormatter())
    logger.addHandler(stream)
    logger.addHandler(buffer)
    return logger


def log_event(logger: logging.Logger, level: int, message: str, **fields) -> None:
    logger.log(level, message, extra={"fields": fields})
