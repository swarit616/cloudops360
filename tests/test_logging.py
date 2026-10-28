"""Structured logging and secret redaction."""

from __future__ import annotations

import json
import logging

from app.logging_config import REDACTED, JsonFormatter, log_event, redact, request_id_var


def format_record(**context):
    logger = logging.getLogger("cloudops360.test")
    record = logger.makeRecord("cloudops360.test", logging.INFO, __file__, 1, "demo.event", (), None, extra={"event": "demo.event", "context": context})
    return json.loads(JsonFormatter().format(record))


def test_log_line_has_required_fields():
    token = request_id_var.set("req-1")
    try:
        line = format_record(action="disk_cleanup")
    finally:
        request_id_var.reset(token)
    assert line["event"] == "demo.event"
    assert line["level"] == "INFO"
    assert line["component"] == "test"
    assert line["request_id"] == "req-1"
    assert line["context"] == {"action": "disk_cleanup"}
    assert line["timestamp"].endswith("+00:00")


def test_secrets_are_redacted_by_key_and_by_pattern():
    line = format_record(
        password="hunter2",
        api_key="key-value-1",
        aws_secret_access_key="secret-value-2",
        nested={"Authorization": "Bearer token.value.3", "ok": "fine"},
        note="key AKIAABCDEFGHIJKLMNOP leaked",
    )
    dumped = json.dumps(line)
    for secret in ("hunter2", "key-value-1", "secret-value-2", "token.value.3", "AKIAABCDEFGHIJKLMNOP"):
        assert secret not in dumped
    assert line["context"]["password"] == REDACTED
    assert line["context"]["nested"]["ok"] == "fine"
    assert REDACTED in line["context"]["note"]


def test_redact_leaves_ordinary_values_alone():
    assert redact({"private_ip": "10.0.0.1", "count": 3}) == {"private_ip": "10.0.0.1", "count": 3}


def test_log_event_emits_through_logger(caplog):
    logger = logging.getLogger("cloudops360.test")
    logger.addHandler(caplog.handler)

    try:
        with caplog.at_level(logging.INFO, logger="cloudops360.test"):
            log_event(logger, logging.INFO, "thing.happened", count=2)

        assert caplog.records
        record = caplog.records[-1]
        assert record.event == "thing.happened"
        assert record.context == {"count": 2}
    finally:
        logger.removeHandler(caplog.handler)
