from __future__ import annotations

import time
from typing import Annotated

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .faults import FaultType
from .service_factory import create_service

app, settings, logger, instruments, local_faults = create_service("chaos-controller")

TARGETS = {
    "checkout-api": "http://checkout-api:8000",
    "order-service": "http://order-service:8000",
    "payment-service": "http://payment-service:8000",
}


class ExperimentRequest(BaseModel):
    experiment_id: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{3,64}$")]
    affected_service: Annotated[str, Field(pattern=r"^[a-z-]+$")]
    fault_type: FaultType
    intensity: Annotated[float, Field(ge=0.01, le=1.0)]
    duration_seconds: Annotated[int, Field(ge=1, le=300)]


experiments: dict[str, dict[str, object]] = {}


@app.post("/experiments")
async def start_experiment(request: ExperimentRequest) -> dict[str, object]:
    target = TARGETS.get(request.affected_service)
    if target is None:
        raise HTTPException(422, "unknown affected service")
    started = time.time()
    payload = request.model_dump(exclude={"affected_service"}, mode="json")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(f"{target}/_internal/faults", json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "target service rejected experiment") from exc
    experiment: dict[str, object] = {
        **request.model_dump(mode="json"),
        "start_time": started,
        "end_time": started + request.duration_seconds,
        "status": "running",
    }
    experiments[request.experiment_id] = experiment
    logger.warning(
        "chaos.experiment.started",
        extra={
            "event_name": "chaos.experiment.started",
            "experiment_id": request.experiment_id,
            "affected_service": request.affected_service,
            "fault_type": request.fault_type.value,
            "intensity": request.intensity,
            "start_time": started,
            "end_time": started + request.duration_seconds,
        },
    )
    return experiment


@app.get("/experiments")
async def list_experiments() -> list[dict[str, object]]:
    now = time.time()
    for experiment in experiments.values():
        end_time = experiment["end_time"]
        if isinstance(end_time, int | float) and end_time <= now:
            experiment["status"] = "completed"
    return list(experiments.values())


@app.delete("/experiments/{experiment_id}")
async def stop_experiment(experiment_id: str) -> dict[str, object]:
    experiment = experiments.get(experiment_id)
    if experiment is None:
        raise HTTPException(404, "experiment not found")
    service = str(experiment["affected_service"])
    async with httpx.AsyncClient(timeout=3) as client:
        await client.delete(f"{TARGETS[service]}/_internal/faults/{experiment_id}")
    experiment["status"] = "stopped"
    experiment["end_time"] = time.time()
    return experiment
