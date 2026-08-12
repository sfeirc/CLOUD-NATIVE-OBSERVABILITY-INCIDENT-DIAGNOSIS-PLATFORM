from __future__ import annotations

import heapq
import math
import time
import uuid
from collections import defaultdict
from collections.abc import Iterable

from .model import (
    Evidence,
    EvidenceStore,
    Hypothesis,
    Incident,
    ScoreContribution,
    SignalKind,
    TimelineEvent,
)
from .slo import DEFAULT_SLOS, SLODefinition, SLOStatus, calculate_slo


def percentile(values: Iterable[float], quantile: float) -> float:
    samples = list(values)
    if not samples:
        return 0.0
    index = max(0, math.ceil(quantile * len(samples)) - 1)
    upper_count = len(samples) - index
    if upper_count <= len(samples) // 4:
        return heapq.nlargest(upper_count, samples)[-1]
    return sorted(samples)[index]


class CorrelationEngine:
    """Deterministic, evidence-citing incident rules; deliberately not an ML RCA system."""

    def __init__(self, store: EvidenceStore) -> None:
        self.store = store

    @staticmethod
    def _request_spans(items: list[Evidence], service: str) -> list[Evidence]:
        return [
            item
            for item in items
            if item.service == service
            and item.kind in {SignalKind.SPAN, SignalKind.ERROR}
            and item.attributes.get("span.kind") == "SERVER"
        ]

    def slo_statuses(self, now: float | None = None) -> list[SLOStatus]:
        current = now or time.time()
        long_items = self.store.query(since=current - 3600, until=current)
        return self._slo_statuses_from_items(long_items, current)

    def _slo_statuses_from_items(
        self, long_items: list[Evidence], current: float
    ) -> list[SLOStatus]:
        long_spans: dict[str, list[Evidence]] = defaultdict(list)
        short_spans: dict[str, list[Evidence]] = defaultdict(list)
        short_start = current - 300
        for item in long_items:
            if (
                item.kind in {SignalKind.SPAN, SignalKind.ERROR}
                and item.attributes.get("span.kind") == "SERVER"
            ):
                long_spans[item.service].append(item)
                if item.timestamp >= short_start:
                    short_spans[item.service].append(item)
        statuses: list[SLOStatus] = []
        for definition in DEFAULT_SLOS:
            service_long = long_spans[definition.service]
            service_short = short_spans[definition.service]
            long_bad = self._bad_count(definition, service_long)
            short_bad = self._bad_count(definition, service_short)
            statuses.append(
                calculate_slo(
                    definition,
                    total_events=len(service_long),
                    bad_events=long_bad,
                    short_bad_fraction=(short_bad / len(service_short) if service_short else 0),
                    long_bad_fraction=(long_bad / len(service_long) if service_long else 0),
                )
            )
        return statuses

    @staticmethod
    def _bad_count(definition: SLODefinition, spans: list[Evidence]) -> int:
        if definition.indicator == "latency":
            threshold = definition.threshold_ms or 0
            return sum(item.value > threshold for item in spans)
        return sum(
            bool(item.kind == SignalKind.ERROR or item.attributes.get("error")) for item in spans
        )

    def analyze(self, now: float | None = None) -> Incident | None:
        current_time = now or time.time()
        hour_items = self.store.query(since=current_time - 3600, until=current_time)
        markers = [
            item
            for item in hour_items
            if item.timestamp >= current_time - 300
            and item.kind in {SignalKind.CHAOS, SignalKind.DEPLOYMENT}
        ]
        recent_markers = [item for item in markers if item.timestamp >= current_time - 55]
        if recent_markers:
            current_start = min(item.timestamp for item in recent_markers)
            baseline_width = max(15, current_time - current_start)
            baseline_start = current_start - baseline_width
            baseline_end = current_start - 0.001
        else:
            current_start = current_time - 60
            baseline_start = current_time - 360
            baseline_end = current_time - 60.001
        current = [item for item in hour_items if item.timestamp >= current_start]
        baseline = [item for item in hour_items if baseline_start <= item.timestamp <= baseline_end]
        checkout_current = self._request_spans(current, "checkout-api")
        checkout_baseline = self._request_spans(baseline, "checkout-api")
        if len(checkout_current) < 3:
            return None

        current_p99 = percentile((item.value for item in checkout_current), 0.99)
        baseline_p99 = percentile((item.value for item in checkout_baseline), 0.99)
        errors = sum(item.kind == SignalKind.ERROR for item in checkout_current)
        error_rate = errors / len(checkout_current)
        latency_triggered = current_p99 > 300 and current_p99 > max(1, baseline_p99) * 1.5
        error_triggered = error_rate > 0.01
        if not latency_triggered and not error_triggered:
            return None

        all_items = baseline + current
        hypotheses = self._rank_hypotheses(baseline, current, hour_items, current_time)
        statuses = self._slo_statuses_from_items(hour_items, current_time)
        timeline = self._timeline(all_items, hypotheses, current_time, statuses)
        title = "Checkout latency increased" if latency_triggered else "Checkout errors increased"
        return Incident(
            incident_id=f"inc-{uuid.uuid4().hex[:10]}",
            title=title,
            created_at=current_time,
            status="firing",
            hypotheses=tuple(hypotheses),
            timeline=tuple(timeline),
            slo={status.definition.name: status.to_dict() for status in statuses},
        )

    def _rank_hypotheses(
        self,
        baseline: list[Evidence],
        current: list[Evidence],
        hour_items: list[Evidence],
        now: float,
    ) -> list[Hypothesis]:
        current_by_service: dict[str, list[Evidence]] = defaultdict(list)
        baseline_by_service: dict[str, list[Evidence]] = defaultdict(list)
        deployments_by_service: dict[str, list[Evidence]] = defaultdict(list)
        for item in current:
            if item.service:
                current_by_service[item.service].append(item)
        for item in baseline:
            if item.service:
                baseline_by_service[item.service].append(item)
        for item in hour_items:
            if item.timestamp >= now - 600 and item.service and item.kind == SignalKind.DEPLOYMENT:
                deployments_by_service[item.service].append(item)

        candidates: list[tuple[str, str, list[ScoreContribution]]] = []
        for service in sorted(current_by_service):
            service_current = current_by_service[service]
            service_baseline = baseline_by_service[service]
            current_spans = [item for item in service_current if item.kind == SignalKind.SPAN]
            baseline_spans = [item for item in service_baseline if item.kind == SignalKind.SPAN]
            latency_factor, latency_evidence = self._factor(current_spans, baseline_spans)
            recent_deploy = deployments_by_service[service]
            errors = [item for item in service_current if item.kind == SignalKind.ERROR]

            db_current = [item for item in current_spans if item.attributes.get("db.system")]
            db_baseline = [item for item in baseline_spans if item.attributes.get("db.system")]
            db_factor, db_evidence = self._factor(db_current, db_baseline)
            db_rules: list[ScoreContribution] = []
            if db_factor >= 2:
                db_rules.append(
                    ScoreContribution(
                        "database_latency_factor",
                        min(4, db_factor / 2),
                        f"Database span p99 increased {db_factor:.1f}x",
                        tuple(item.evidence_id for item in db_evidence),
                    )
                )
            if db_rules and latency_factor >= 1.5:
                db_rules.append(
                    ScoreContribution(
                        "service_latency_factor",
                        min(3, latency_factor),
                        f"{service} span p99 increased {latency_factor:.1f}x",
                        tuple(item.evidence_id for item in latency_evidence),
                    )
                )
            if db_rules and recent_deploy:
                db_rules.append(
                    ScoreContribution(
                        "recent_deployment",
                        1.5,
                        "A deployment marker occurred within the prior 10 minutes",
                        tuple(item.evidence_id for item in recent_deploy[-2:]),
                    )
                )
            cpu = [
                item
                for item in service_current
                if item.kind == SignalKind.METRIC and item.name == "process.cpu.utilization"
            ]
            if db_rules and (not cpu or max(item.value for item in cpu) < 0.8):
                db_rules.append(
                    ScoreContribution(
                        "no_cpu_saturation",
                        0.5,
                        "No CPU utilization sample reached 80%; CPU pressure is less likely",
                        tuple(item.evidence_id for item in cpu[-3:]),
                    )
                )
            if db_rules:
                candidates.append(("Database interaction regression", service, db_rules))

            deployment_rules: list[ScoreContribution] = []
            if recent_deploy:
                deployment_rules.append(
                    ScoreContribution(
                        "recent_deployment",
                        3,
                        "The service was deployed within the prior 10 minutes",
                        tuple(item.evidence_id for item in recent_deploy[-2:]),
                    )
                )
            if recent_deploy and errors:
                deployment_rules.append(
                    ScoreContribution(
                        "concurrent_errors",
                        min(3, len(errors) / 2),
                        f"Observed {len(errors)} error spans in the incident window",
                        tuple(item.evidence_id for item in errors[-5:]),
                    )
                )
            if deployment_rules:
                candidates.append(("Bad deployment", service, deployment_rules))

            memory = [
                item
                for item in service_current
                if item.kind == SignalKind.METRIC and item.name == "process.memory.usage"
            ]
            old_memory = [
                item
                for item in service_baseline
                if item.kind == SignalKind.METRIC and item.name == "process.memory.usage"
            ]
            memory_factor, memory_evidence = self._factor(memory, old_memory)
            if memory_factor >= 1.2 and latency_factor >= 1.5:
                candidates.append(
                    (
                        "Memory pressure causing processing degradation",
                        service,
                        [
                            ScoreContribution(
                                "memory_growth",
                                min(4, memory_factor),
                                f"Memory samples increased {memory_factor:.1f}x",
                                tuple(item.evidence_id for item in memory_evidence),
                            ),
                            ScoreContribution(
                                "concurrent_latency",
                                min(3, latency_factor),
                                f"Span latency increased {latency_factor:.1f}x",
                                tuple(item.evidence_id for item in latency_evidence),
                            ),
                        ],
                    )
                )

            dependency_errors = [
                item
                for item in service_current
                if item.kind == SignalKind.ERROR and item.attributes.get("span.kind") == "CLIENT"
            ]
            if dependency_errors:
                candidates.append(
                    (
                        "Downstream dependency outage",
                        service,
                        [
                            ScoreContribution(
                                "failed_client_spans",
                                min(6, len(dependency_errors) * 1.5),
                                f"Observed {len(dependency_errors)} failed downstream calls",
                                tuple(item.evidence_id for item in dependency_errors[-5:]),
                            )
                        ],
                    )
                )

        ordered = sorted(candidates, key=lambda row: sum(c.points for c in row[2]), reverse=True)
        return [
            Hypothesis(index + 1, title, service, sum(c.points for c in rules), tuple(rules))
            for index, (title, service, rules) in enumerate(ordered[:5])
        ]

    @staticmethod
    def _factor(current: list[Evidence], baseline: list[Evidence]) -> tuple[float, list[Evidence]]:
        if not current:
            return 0, []
        current_p99 = percentile((item.value for item in current), 0.99)
        baseline_p99 = percentile((item.value for item in baseline), 0.99)
        factor = current_p99 / max(1, baseline_p99)
        evidence = sorted(
            heapq.nlargest(3, current, key=lambda item: item.value), key=lambda item: item.value
        )
        return factor, evidence

    @staticmethod
    def _timeline(
        items: list[Evidence],
        hypotheses: list[Hypothesis],
        now: float,
        statuses: list[SLOStatus],
    ) -> list[TimelineEvent]:
        events = [
            TimelineEvent(item.timestamp, f"{item.name}: {item.service}", (item.evidence_id,))
            for item in items
            if item.kind in {SignalKind.DEPLOYMENT, SignalKind.CHAOS}
        ]
        firing = [status for status in statuses if status.alerting]
        if firing:
            events.append(
                TimelineEvent(
                    now - 1,
                    "Error-budget burn alert: "
                    + ", ".join(status.definition.name for status in firing),
                )
            )
        events.append(TimelineEvent(now, "Incident created"))
        if hypotheses:
            events.append(
                TimelineEvent(
                    now + 0.001,
                    f"Suspected root cause: {hypotheses[0].title} in {hypotheses[0].service}",
                    tuple(
                        evidence_id
                        for rule in hypotheses[0].contributions
                        for evidence_id in rule.evidence_ids
                    ),
                )
            )
        return sorted(events, key=lambda event: event.timestamp)
