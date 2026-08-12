from incident_lens.correlation import CorrelationEngine
from incident_lens.model import Evidence, EvidenceStore, SignalKind


def span(
    timestamp: float,
    service: str,
    duration: float,
    *,
    kind: str = "SERVER",
    db: bool = False,
    error: bool = False,
) -> Evidence:
    attrs: dict[str, object] = {"span.kind": kind, "error": error}
    if db:
        attrs["db.system"] = "postgresql"
    return Evidence(
        timestamp=timestamp,
        service=service,
        kind=SignalKind.ERROR if error else SignalKind.SPAN,
        name="INSERT payments" if db else "request",
        value=duration,
        unit="ms",
        trace_id=f"{int(timestamp):032x}",
        attributes=attrs,
    )


def test_database_regression_is_ranked_with_cited_evidence() -> None:
    store = EvidenceStore()
    now = 10_000.0
    for offset in range(20):
        at = now - 180 + offset
        store.add_many(
            [
                span(at, "checkout-api", 80),
                span(at, "order-service", 60),
                span(at, "payment-service", 30),
                span(at, "payment-service", 5, kind="CLIENT", db=True),
            ]
        )
    deployment = Evidence(
        timestamp=now - 120,
        service="payment-service",
        kind=SignalKind.DEPLOYMENT,
        name="deployment.started",
        attributes={"service.version": "v1.7"},
    )
    store.add(deployment)
    for offset in range(10):
        at = now - 20 + offset
        store.add_many(
            [
                span(at, "checkout-api", 750),
                span(at, "order-service", 700),
                span(at, "payment-service", 650),
                span(at, "payment-service", 600, kind="CLIENT", db=True),
                Evidence(
                    timestamp=at,
                    service="payment-service",
                    kind=SignalKind.METRIC,
                    name="process.cpu.utilization",
                    value=0.25,
                    unit="1",
                ),
            ]
        )

    incident = CorrelationEngine(store).analyze(now)

    assert incident is not None
    assert incident.title == "Checkout latency increased"
    assert incident.hypotheses[0].title == "Database interaction regression"
    assert incident.hypotheses[0].service == "payment-service"
    rules = {item.rule for item in incident.hypotheses[0].contributions}
    assert {"database_latency_factor", "recent_deployment", "no_cpu_saturation"} <= rules
    assert all(
        contribution.evidence_ids
        for contribution in incident.hypotheses[0].contributions
        if contribution.rule != "no_cpu_saturation"
    )
    assert any("Suspected root cause" in event.event for event in incident.timeline)


def test_healthy_window_does_not_create_incident() -> None:
    store = EvidenceStore()
    now = 5_000.0
    for offset in range(10):
        store.add(span(now - offset, "checkout-api", 50))

    assert CorrelationEngine(store).analyze(now) is None
