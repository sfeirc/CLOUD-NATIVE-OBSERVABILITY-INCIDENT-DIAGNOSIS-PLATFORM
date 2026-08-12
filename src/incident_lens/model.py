from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class SignalKind(StrEnum):
    SPAN = "span"
    ERROR = "error"
    METRIC = "metric"
    LOG = "log"
    DEPLOYMENT = "deployment"
    CHAOS = "chaos"


@dataclass(frozen=True)
class Evidence:
    timestamp: float
    service: str
    kind: SignalKind
    name: str
    value: float = 0
    unit: str = ""
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    evidence_id: str = field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        return value


@dataclass(frozen=True)
class ScoreContribution:
    rule: str
    points: float
    explanation: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class Hypothesis:
    rank: int
    title: str
    service: str
    score: float
    contributions: tuple[ScoreContribution, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TimelineEvent:
    timestamp: float
    event: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Incident:
    incident_id: str
    title: str
    created_at: float
    status: str
    hypotheses: tuple[Hypothesis, ...]
    timeline: tuple[TimelineEvent, ...]
    slo: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceStore:
    def __init__(self, max_items: int = 100_000) -> None:
        self._items: deque[Evidence] = deque(maxlen=max_items)
        self._lock = threading.Lock()

    def add(self, evidence: Evidence) -> None:
        with self._lock:
            self._items.append(evidence)

    def add_many(self, evidence: list[Evidence]) -> None:
        with self._lock:
            self._items.extend(evidence)

    def query(
        self,
        *,
        since: float = 0,
        until: float | None = None,
        service: str | None = None,
        kind: SignalKind | None = None,
    ) -> list[Evidence]:
        end = until if until is not None else time.time()
        with self._lock:
            return [
                item
                for item in self._items
                if since <= item.timestamp <= end
                and (service is None or item.service == service)
                and (kind is None or item.kind == kind)
            ]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
