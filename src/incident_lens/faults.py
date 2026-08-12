from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, Field


class FaultType(StrEnum):
    LATENCY = "latency"
    HTTP_500 = "http_500"
    DROP = "drop"
    DEPENDENCY_TIMEOUT = "dependency_timeout"
    CPU_PRESSURE = "cpu_pressure"
    MEMORY_PRESSURE = "memory_pressure"
    DATABASE_SLOWDOWN = "database_slowdown"


class FaultRequest(BaseModel):
    experiment_id: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{3,64}$")]
    fault_type: FaultType
    intensity: Annotated[float, Field(ge=0.01, le=1.0)]
    duration_seconds: Annotated[int, Field(ge=1, le=300)]


@dataclass
class ActiveFault:
    request: FaultRequest
    service: str
    started_at: float
    ends_at: float
    allocations: list[bytearray] = field(default_factory=list)

    def as_dict(self) -> dict[str, str | float]:
        return {
            "experiment_id": self.request.experiment_id,
            "fault_type": self.request.fault_type.value,
            "intensity": self.request.intensity,
            "affected_service": self.service,
            "start_time": self.started_at,
            "end_time": self.ends_at,
        }


class FaultRegistry:
    """Process-local bounded fault state; containers provide the isolation boundary."""

    def __init__(self, service: str) -> None:
        self.service = service
        self._active: dict[str, ActiveFault] = {}

    def start(self, request: FaultRequest) -> ActiveFault:
        now = time.time()
        fault = ActiveFault(request, self.service, now, now + request.duration_seconds)
        if request.fault_type == FaultType.MEMORY_PRESSURE:
            size_mib = max(1, int(request.intensity * 32))
            fault.allocations.append(bytearray(size_mib * 1024 * 1024))
        self._active[request.experiment_id] = fault
        return fault

    def stop(self, experiment_id: str) -> ActiveFault | None:
        return self._active.pop(experiment_id, None)

    def active(self) -> list[ActiveFault]:
        now = time.time()
        expired = [key for key, value in self._active.items() if value.ends_at <= now]
        for key in expired:
            self._active.pop(key, None)
        return list(self._active.values())

    async def apply_request_faults(self) -> None:
        for fault in self.active():
            intensity = fault.request.intensity
            match fault.request.fault_type:
                case FaultType.LATENCY:
                    await asyncio.sleep(0.05 + 0.95 * intensity)
                case FaultType.HTTP_500:
                    raise HTTPException(500, "controlled fault injection")
                case FaultType.DROP:
                    await asyncio.sleep(2 * intensity)
                    raise HTTPException(503, "controlled dropped request")
                case FaultType.CPU_PRESSURE:
                    deadline = time.perf_counter() + 0.1 * intensity
                    payload = b"incident-lens"
                    while time.perf_counter() < deadline:
                        payload = hashlib.sha256(payload).digest()
                case FaultType.MEMORY_PRESSURE:
                    await asyncio.sleep(0.15 * intensity)
                case _:
                    continue

    async def dependency_delay(self, database: bool = False) -> None:
        for fault in self.active():
            if database and fault.request.fault_type == FaultType.DATABASE_SLOWDOWN:
                await asyncio.sleep(0.1 + 1.4 * fault.request.intensity)
            elif not database and fault.request.fault_type == FaultType.DEPENDENCY_TIMEOUT:
                await asyncio.sleep(1 + 3 * fault.request.intensity)
