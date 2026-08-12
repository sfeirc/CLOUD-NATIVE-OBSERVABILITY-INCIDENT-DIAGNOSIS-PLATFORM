import math

import pytest

from incident_lens.correlation import CorrelationEngine, percentile
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


@pytest.mark.parametrize("quantile", [0, 0.5, 0.95, 0.99, 1])
def test_heap_percentile_matches_nearest_rank(quantile: float) -> None:
    values = [float((index * 17) % 101) for index in range(1, 1_004)]
    ordered = sorted(values)
    expected = ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]

    assert percentile(values, quantile) == expected


class CountingStore(EvidenceStore):
    def __init__(self) -> None:
        super().__init__()
        self.query_count = 0

    def query(self, **kwargs: object) -> list[Evidence]:
        self.query_count += 1
        return super().query(**kwargs)  # type: ignore[arg-type]


def test_analysis_takes_one_consistent_store_snapshot() -> None:
    store = CountingStore()
    now = 2_000.0
    for offset in range(5):
        store.add(span(now - offset, "checkout-api", 500))

    assert CorrelationEngine(store).analyze(now) is not None
    assert store.query_count == 1


def scenario_store(now: float) -> EvidenceStore:
    store = EvidenceStore()
    for offset in range(10):
        at = now - 40 + offset
        store.add_many(
            [
                span(at, "checkout-api", 80),
                span(at, "order-service", 60),
                span(at, "payment-service", 30),
                Evidence(
                    timestamp=at,
                    service="payment-service",
                    kind=SignalKind.METRIC,
                    name="process.memory.usage",
                    value=100,
                    unit="By",
                ),
            ]
        )
    return store


def test_memory_pressure_scenario_ranks_memory_hypothesis() -> None:
    now = 4_000.0
    store = scenario_store(now)
    store.add(Evidence(now - 20, "chaos-controller", SignalKind.CHAOS, "chaos.experiment.started"))
    for offset in range(10):
        at = now - 15 + offset
        store.add_many(
            [
                span(at, "checkout-api", 700),
                span(at, "payment-service", 600),
                Evidence(
                    timestamp=at,
                    service="payment-service",
                    kind=SignalKind.METRIC,
                    name="process.memory.usage",
                    value=160,
                    unit="By",
                ),
            ]
        )

    incident = CorrelationEngine(store).analyze(now)

    assert incident is not None
    assert incident.hypotheses[0].title == "Memory pressure causing processing degradation"
    assert incident.hypotheses[0].service == "payment-service"


def test_dependency_outage_does_not_invent_deployment() -> None:
    now = 6_000.0
    store = scenario_store(now)
    store.add(Evidence(now - 20, "chaos-controller", SignalKind.CHAOS, "chaos.experiment.started"))
    for offset in range(10):
        at = now - 15 + offset
        store.add_many(
            [
                span(at, "checkout-api", 40, error=True),
                span(at, "order-service", 30, kind="CLIENT", error=True),
            ]
        )

    incident = CorrelationEngine(store).analyze(now)

    assert incident is not None
    assert incident.hypotheses[0].title == "Downstream dependency outage"
    assert all(item.title != "Bad deployment" for item in incident.hypotheses)


def test_bad_deployment_requires_and_cites_deployment_marker() -> None:
    now = 8_000.0
    store = scenario_store(now)
    deployment = Evidence(
        now - 20,
        "payment-service",
        SignalKind.DEPLOYMENT,
        "deployment.started",
        attributes={"service.version": "v1.7-bad"},
    )
    store.add(deployment)
    for offset in range(10):
        at = now - 15 + offset
        store.add_many(
            [
                span(at, "checkout-api", 40, error=True),
                span(at, "payment-service", 30, error=True),
            ]
        )

    incident = CorrelationEngine(store).analyze(now)

    assert incident is not None
    bad_deployment = next(item for item in incident.hypotheses if item.title == "Bad deployment")
    assert bad_deployment.service == "payment-service"
    assert deployment.evidence_id in {
        evidence_id for rule in bad_deployment.contributions for evidence_id in rule.evidence_ids
    }
