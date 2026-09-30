import json
import logging

from app.observability import JsonFormatter, log_event


def test_json_formatter_emits_event_fields_without_message_content():
    record = logging.LogRecord("forge", logging.INFO, __file__, 1, "ignored", (), None)
    record.event = "query_completed"
    record.structured = {"request_id": "req-1", "latency_ms": 12.5}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "query_completed"
    assert payload["request_id"] == "req-1"
    assert payload["latency_ms"] == 12.5
    assert "ignored" not in payload


def test_log_event_attaches_structured_fields():
    logger = logging.getLogger("forge.test")
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Capture()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        log_event(logger, "cache_hit", request_id="req-2", cache_hit=True)
    finally:
        logger.removeHandler(handler)

    assert records[-1].event == "cache_hit"
    assert records[-1].structured["cache_hit"] is True
