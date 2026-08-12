from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

import psutil
from fastapi import FastAPI, Request, Response
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from .config import Settings


class JsonFormatter(logging.Formatter):
    """Stable JSON log schema used on stdout and by the OTLP logging handler."""

    def __init__(self, service: str, version: str) -> None:
        super().__init__()
        self.service = service
        self.version = version

    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span().get_span_context()
        payload: dict[str, Any] = {
            "timestamp": time.time_ns(),
            "severity": record.levelname,
            "service": self.service,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "trace_id": f"{span.trace_id:032x}" if span.is_valid else None,
            "deployment_version": self.version,
        }
        error_type = getattr(record, "error_type", None)
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message": getattr(record, "error_message", record.getMessage()),
            }
        return json.dumps(payload, separators=(",", ":"))


@dataclass
class Instruments:
    requests: Any
    errors: Any
    duration: Any
    dependency_errors: Any
    queue_depth: Any
    database_duration: Any
    process_memory: Any
    process_cpu: Any


def configure_telemetry(settings: Settings) -> tuple[logging.Logger, Instruments]:
    resource = Resource.create(
        {SERVICE_NAME: settings.service_name, SERVICE_VERSION: settings.service_version}
    )
    traces = TracerProvider(resource=resource)
    traces.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{settings.otlp_endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(traces)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{settings.otlp_endpoint}/v1/metrics"),
        export_interval_millis=int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "5000")),
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    logs = LoggerProvider(resource=resource)
    logs.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{settings.otlp_endpoint}/v1/logs"))
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    stdout = logging.StreamHandler()
    stdout.setFormatter(JsonFormatter(settings.service_name, settings.service_version))
    root.handlers[:] = [stdout, LoggingHandler(logger_provider=logs)]

    meter = metrics.get_meter(settings.service_name)
    instruments = Instruments(
        requests=meter.create_counter("http.server.requests", unit="{request}"),
        errors=meter.create_counter("http.server.errors", unit="{error}"),
        duration=meter.create_histogram("http.server.duration", unit="ms"),
        dependency_errors=meter.create_counter("dependency.errors", unit="{error}"),
        queue_depth=meter.create_up_down_counter("service.queue.depth", unit="{request}"),
        database_duration=meter.create_histogram("database.client.duration", unit="ms"),
        process_memory=meter.create_histogram("process.memory.usage", unit="By"),
        process_cpu=meter.create_histogram("process.cpu.utilization", unit="1"),
    )
    HTTPXClientInstrumentor().instrument()
    return logging.getLogger(settings.service_name), instruments


class RequestTelemetryMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service: str, version: str, instruments: Instruments) -> None:
        super().__init__(app)
        self.service = service
        self.version = version
        self.instruments = instruments

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        route = request.scope.get("route")
        route_name = getattr(route, "path", request.url.path)
        labels = {"service": self.service, "method": request.method, "route": route_name}
        started = time.perf_counter()
        self.instruments.queue_depth.add(1, {"service": self.service})
        try:
            response = await call_next(request)
        except Exception:
            self.instruments.errors.add(1, {**labels, "status_class": "5xx"})
            raise
        finally:
            self.instruments.queue_depth.add(-1, {"service": self.service})
        elapsed_ms = (time.perf_counter() - started) * 1000
        status_class = f"{response.status_code // 100}xx"
        bounded = {**labels, "status_class": status_class, "version": self.version}
        self.instruments.requests.add(1, bounded)
        self.instruments.duration.record(elapsed_ms, bounded)
        if response.status_code >= 500:
            self.instruments.errors.add(1, bounded)
        process = psutil.Process()
        self.instruments.process_memory.record(process.memory_info().rss, {"service": self.service})
        self.instruments.process_cpu.record(
            min(process.cpu_percent(interval=None) / 100, 1), {"service": self.service}
        )
        response.headers["x-request-id"] = request_id
        return response


def instrument_app(app: FastAPI, settings: Settings, instruments: Instruments) -> None:
    app.add_middleware(
        RequestTelemetryMiddleware,
        service=settings.service_name,
        version=settings.service_version,
        instruments=instruments,
    )
    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz")


def deployment_log(logger: logging.Logger, settings: Settings) -> None:
    logger.info(
        "deployment.started",
        extra={"event_name": "deployment.started", "deployed_at": time.time_ns()},
    )


def propagation_headers(request: Request) -> dict[str, str]:
    """Preserve request identity; OTel HTTPX instrumentation injects trace context."""
    return {"x-request-id": request.state.request_id}
