import json
import logging

from incident_lens.config import Settings
from incident_lens.telemetry import JsonFormatter


def test_settings_and_structured_log_schema(monkeypatch: object) -> None:
    monkeypatch.setenv("SERVICE_VERSION", "v9")  # type: ignore[attr-defined]
    settings = Settings.from_env("order-service")
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "failed", (), None)
    record.request_id = "request-1"  # type: ignore[attr-defined]
    record.error_type = "TimeoutError"  # type: ignore[attr-defined]

    payload = json.loads(
        JsonFormatter(settings.service_name, settings.service_version).format(record)
    )

    assert payload["service"] == "order-service"
    assert payload["deployment_version"] == "v9"
    assert payload["request_id"] == "request-1"
    assert payload["error"]["type"] == "TimeoutError"
    assert "timestamp" in payload and "trace_id" in payload
