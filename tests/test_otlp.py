import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span, Status

from incident_lens.model import SignalKind
from incident_lens.otlp import MalformedOTLP, decode_traces


def kv(key: str, value: str | int) -> KeyValue:
    if isinstance(value, str):
        return KeyValue(key=key, value=AnyValue(string_value=value))
    return KeyValue(key=key, value=AnyValue(int_value=value))


def test_trace_parentage_and_error_attributes_survive_otlp_decode() -> None:
    trace_id = bytes.fromhex("01" * 16)
    parent_id = bytes.fromhex("02" * 8)
    child_id = bytes.fromhex("03" * 8)
    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        kv("service.name", "payment-service"),
                        kv("service.version", "v1.7"),
                    ]
                ),
                scope_spans=[
                    ScopeSpans(
                        spans=[
                            Span(
                                trace_id=trace_id,
                                span_id=child_id,
                                parent_span_id=parent_id,
                                name="INSERT payments",
                                kind=Span.SPAN_KIND_CLIENT,
                                start_time_unix_nano=1_000_000_000,
                                end_time_unix_nano=1_025_000_000,
                                attributes=[
                                    kv("db.system", "postgresql"),
                                    kv("http.response.status_code", 503),
                                ],
                                status=Status(code=Status.STATUS_CODE_ERROR),
                            )
                        ]
                    )
                ],
            )
        ]
    )

    items, _ = decode_traces(request.SerializeToString())

    assert len(items) == 1
    assert items[0].trace_id == trace_id.hex()
    assert items[0].span_id == child_id.hex()
    assert items[0].parent_span_id == parent_id.hex()
    assert items[0].value == 25
    assert items[0].kind == SignalKind.ERROR
    assert items[0].attributes["service.version"] == "v1.7"


def test_malformed_otlp_is_rejected() -> None:
    with pytest.raises(MalformedOTLP):
        decode_traces(b"\xff")
