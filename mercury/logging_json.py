"""Structured JSON logging for mercury.

Emits one JSON object per log record to stdout, tagged with the per-request id
set by mercury.middleware.RequestIDMiddleware. Sensitive-looking keys are
redacted so tokens / DB passwords never reach the log stream.
"""
from __future__ import annotations

import json
import logging
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIDFilter(logging.Filter):
    """Injects request_id from the current context into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    _SKIP = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "message",
            "taskName",
        }
    )

    _REDACT = frozenset(
        {
            "password",
            "secret",
            "token",
            "access_token",
            "refresh_token",
            "authorization",
            "api_key",
            "apikey",
            "credential",
            "private_key",
            "secret_key",
            "service_key",
        }
    )

    _REDACTED = "[REDACTED]"

    @classmethod
    def _should_redact(cls, key: str) -> bool:
        return key.lower() in cls._REDACT

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        log: dict = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        if hasattr(record, "request_id") and record.request_id:
            log["request_id"] = record.request_id

        if record.exc_info:
            log["exception"] = "".join(traceback.format_exception(*record.exc_info))

        for key, value in record.__dict__.items():
            if key not in self._SKIP:
                if self._should_redact(key):
                    log[key] = self._REDACTED
                else:
                    log[key] = value

        return json.dumps(log, default=str)
