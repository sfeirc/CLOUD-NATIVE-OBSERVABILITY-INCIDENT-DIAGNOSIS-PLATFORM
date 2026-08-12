from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from .config import Settings
from .faults import FaultRegistry, FaultRequest
from .telemetry import Instruments, configure_telemetry, deployment_log, instrument_app


def create_service(
    name: str,
) -> tuple[FastAPI, Settings, logging.Logger, Instruments, FaultRegistry]:
    settings = Settings.from_env(name)
    logger, instruments = configure_telemetry(settings)
    registry = FaultRegistry(name)
    app = FastAPI(title=f"Incident Lens {name}", version=settings.service_version)

    @app.get("/healthz", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": name}

    @app.get("/readyz", include_in_schema=False)
    async def ready() -> dict[str, str]:
        return {"status": "ready", "service": name}

    @app.get("/_internal/faults", include_in_schema=False)
    async def list_faults() -> list[dict[str, str | float]]:
        return [fault.as_dict() for fault in registry.active()]

    @app.post("/_internal/faults", include_in_schema=False)
    async def start_fault(request: FaultRequest) -> dict[str, str | float]:
        fault = registry.start(request)
        logger.warning(
            "chaos.experiment.started",
            extra={"experiment_id": request.experiment_id, "fault_type": request.fault_type},
        )
        return fault.as_dict()

    @app.delete("/_internal/faults/{experiment_id}", include_in_schema=False)
    async def stop_fault(experiment_id: str) -> dict[str, object]:
        fault = registry.stop(experiment_id)
        return {"stopped": fault is not None, "experiment_id": experiment_id}

    @app.middleware("http")
    async def inject_faults(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not request.url.path.startswith(("/healthz", "/readyz", "/_internal")):
            await registry.apply_request_faults()
        return await call_next(request)

    instrument_app(app, settings, instruments)
    deployment_log(logger, settings)
    return app, settings, logger, instruments, registry
