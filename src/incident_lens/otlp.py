from __future__ import annotations

from typing import Any

from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.trace.v1.trace_pb2 import Span

from .model import Evidence, SignalKind


class MalformedOTLP(ValueError):
    pass


def any_value(value: AnyValue) -> Any:
    field = value.WhichOneof("value")
    if field == "array_value":
        return [any_value(item) for item in value.array_value.values]
    if field == "kvlist_value":
        return attributes(value.kvlist_value.values)
    if field == "bytes_value":
        return value.bytes_value.hex()
    return getattr(value, field) if field else None


def attributes(values: list[KeyValue] | Any) -> dict[str, Any]:
    return {item.key: any_value(item.value) for item in values}


def _resource(values: Any) -> tuple[str, str, dict[str, Any]]:
    attrs = attributes(values)
    return (
        str(attrs.get("service.name", "unknown")),
        str(attrs.get("service.version", "unknown")),
        attrs,
    )


def decode_traces(payload: bytes) -> tuple[list[Evidence], bytes]:
    request = ExportTraceServiceRequest()
    try:
        request.ParseFromString(payload)
    except DecodeError as exc:
        raise MalformedOTLP("invalid OTLP trace protobuf") from exc
    output: list[Evidence] = []
    for resource_spans in request.resource_spans:
        service, version, _ = _resource(resource_spans.resource.attributes)
        for scope in resource_spans.scope_spans:
            for span in scope.spans:
                attrs = attributes(span.attributes)
                kind_name = Span.SpanKind.Name(span.kind).removeprefix("SPAN_KIND_")
                attrs.update({"span.kind": kind_name, "service.version": version})
                status_code = int(attrs.get("http.response.status_code", 0) or 0)
                error = span.status.code == 2 or status_code >= 500
                attrs["error"] = error
                output.append(
                    Evidence(
                        timestamp=span.start_time_unix_nano / 1_000_000_000,
                        service=service,
                        kind=SignalKind.ERROR if error else SignalKind.SPAN,
                        name=span.name,
                        value=(span.end_time_unix_nano - span.start_time_unix_nano) / 1_000_000,
                        unit="ms",
                        trace_id=span.trace_id.hex() or None,
                        span_id=span.span_id.hex() or None,
                        parent_span_id=span.parent_span_id.hex() or None,
                        attributes=attrs,
                    )
                )
    return output, ExportTraceServiceResponse().SerializeToString()


def decode_metrics(payload: bytes) -> tuple[list[Evidence], bytes]:
    request = ExportMetricsServiceRequest()
    try:
        request.ParseFromString(payload)
    except DecodeError as exc:
        raise MalformedOTLP("invalid OTLP metric protobuf") from exc
    output: list[Evidence] = []
    for resource_metrics in request.resource_metrics:
        service, version, _ = _resource(resource_metrics.resource.attributes)
        for scope in resource_metrics.scope_metrics:
            for metric in scope.metrics:
                data_kind = metric.WhichOneof("data")
                data = getattr(metric, data_kind) if data_kind else None
                for point in getattr(data, "data_points", []):
                    value = _metric_value(point)
                    attrs = attributes(point.attributes)
                    attrs["service.version"] = version
                    timestamp = point.time_unix_nano / 1_000_000_000
                    output.append(
                        Evidence(
                            timestamp=timestamp,
                            service=service,
                            kind=SignalKind.METRIC,
                            name=metric.name,
                            value=value,
                            unit=metric.unit,
                            attributes=attrs,
                        )
                    )
    return output, ExportMetricsServiceResponse().SerializeToString()


def _metric_value(point: Any) -> float:
    if hasattr(point, "count"):
        return float(point.sum / point.count) if point.count else 0.0
    field = point.WhichOneof("value") if hasattr(point, "WhichOneof") else None
    return float(getattr(point, field)) if field else 0.0


def decode_logs(payload: bytes) -> tuple[list[Evidence], bytes]:
    request = ExportLogsServiceRequest()
    try:
        request.ParseFromString(payload)
    except DecodeError as exc:
        raise MalformedOTLP("invalid OTLP log protobuf") from exc
    output: list[Evidence] = []
    for resource_logs in request.resource_logs:
        service, version, _ = _resource(resource_logs.resource.attributes)
        for scope in resource_logs.scope_logs:
            for record in scope.log_records:
                attrs = attributes(record.attributes)
                attrs["service.version"] = version
                body = str(any_value(record.body))
                event_name = str(attrs.get("event_name", body))
                if event_name == "deployment.started" or body == "deployment.started":
                    kind = SignalKind.DEPLOYMENT
                elif event_name.startswith("chaos.experiment") or body.startswith(
                    "chaos.experiment"
                ):
                    kind = SignalKind.CHAOS
                else:
                    kind = SignalKind.LOG
                output.append(
                    Evidence(
                        timestamp=(record.time_unix_nano or record.observed_time_unix_nano)
                        / 1_000_000_000,
                        service=service,
                        kind=kind,
                        name=event_name,
                        trace_id=record.trace_id.hex() or None,
                        span_id=record.span_id.hex() or None,
                        attributes=attrs,
                    )
                )
    return output, ExportLogsServiceResponse().SerializeToString()
