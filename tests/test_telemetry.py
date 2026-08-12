import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider

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


@pytest.mark.asyncio
async def test_httpx_instrumentation_injects_w3c_trace_context() -> None:
    provider = TracerProvider()
    tracer = provider.get_tracer("propagation-test")
    observed_traceparent = ""

    class DownstreamHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            nonlocal observed_traceparent
            observed_traceparent = self.headers.get("traceparent", "")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), DownstreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    instrumentation = HTTPXClientInstrumentor()
    instrumentation.instrument(tracer_provider=provider)
    try:
        with tracer.start_as_current_span("checkout") as root:
            expected_trace_id = f"{root.get_span_context().trace_id:032x}"
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{server.server_port}/orders")
    finally:
        instrumentation.uninstrument()
        server.shutdown()
        thread.join(timeout=2)

    assert response.status_code == 200
    assert observed_traceparent.startswith("00-")
    assert observed_traceparent.split("-")[1] == expected_trace_id
