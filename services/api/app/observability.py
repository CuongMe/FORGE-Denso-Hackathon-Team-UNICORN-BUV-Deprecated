from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4


_request_id: ContextVar[str | None] = ContextVar("forge_request_id", default=None)


class JsonFormatter(logging.Formatter):
    """Small JSON formatter for operational events, without request contents."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        structured = getattr(record, "structured", {})
        if isinstance(structured, dict):
            payload.update(structured)
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def new_request_id() -> str:
    return uuid4().hex


def bind_request_id(value: str):
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def current_request_id() -> str | None:
    return _request_id.get()


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    logger.info(event, extra={"event": event, "structured": fields})


def configure_json_logging() -> None:
    logger = logging.getLogger("forge")
    if any(getattr(handler, "_forge_json", False) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler._forge_json = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
