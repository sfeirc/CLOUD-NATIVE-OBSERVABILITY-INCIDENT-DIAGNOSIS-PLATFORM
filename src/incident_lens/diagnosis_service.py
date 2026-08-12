from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request, Response

from .correlation import CorrelationEngine
from .model import EvidenceStore, Incident, SignalKind
from .otlp import MalformedOTLP, decode_logs, decode_metrics, decode_traces

app = FastAPI(title="Incident Lens diagnosis API", version="0.1.0")
store = EvidenceStore()
engine = CorrelationEngine(store)
incidents: dict[str, Incident] = {}


async def _ingest(
    request: Request, decoder: Callable[[bytes], tuple[list[object], bytes]]
) -> Response:
    try:
        evidence, response = decoder(await request.body())
    except MalformedOTLP as exc:
        raise HTTPException(400, str(exc)) from exc
    store.add_many(evidence)  # type: ignore[arg-type]
    return Response(response, media_type="application/x-protobuf")


@app.post("/v1/traces")
async def traces(request: Request) -> Response:
    return await _ingest(request, decode_traces)  # type: ignore[arg-type]


@app.post("/v1/metrics")
async def metrics(request: Request) -> Response:
    return await _ingest(request, decode_metrics)  # type: ignore[arg-type]


@app.post("/v1/logs")
async def logs(request: Request) -> Response:
    return await _ingest(request, decode_logs)  # type: ignore[arg-type]


@app.get("/healthz", include_in_schema=False)
async def health() -> dict[str, object]:
    return {"status": "ok", "evidence_count": len(store)}


@app.get("/api/evidence")
async def evidence(
    service: str | None = None, kind: SignalKind | None = None, limit: int = 200
) -> list[dict[str, object]]:
    return [item.to_dict() for item in store.query(service=service, kind=kind)[-min(limit, 1000) :]]


@app.get("/api/slos")
async def slos() -> list[dict[str, object]]:
    return [status.to_dict() for status in engine.slo_statuses()]


@app.post("/api/analyze")
async def analyze() -> dict[str, object]:
    incident = engine.analyze()
    if incident is None:
        return {"incident": None, "reason": "no alert condition met"}
    incidents[incident.incident_id] = incident
    return {"incident": incident.to_dict()}


@app.get("/api/incidents")
async def list_incidents() -> list[dict[str, object]]:
    return [incident.to_dict() for incident in incidents.values()]


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict[str, object]:
    if incident_id not in incidents:
        raise HTTPException(404, "incident not found")
    return incidents[incident_id].to_dict()
