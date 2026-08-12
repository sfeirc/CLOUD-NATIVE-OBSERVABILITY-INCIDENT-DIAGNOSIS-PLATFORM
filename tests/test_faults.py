import asyncio
import time

import pytest
from fastapi import HTTPException

from incident_lens.faults import FaultRegistry, FaultRequest, FaultType


@pytest.mark.asyncio
async def test_memory_fault_is_bounded_and_released() -> None:
    registry = FaultRegistry("payment-service")
    fault = registry.start(
        FaultRequest(
            experiment_id="mem-test",
            fault_type=FaultType.MEMORY_PRESSURE,
            intensity=1,
            duration_seconds=1,
        )
    )

    assert sum(len(chunk) for chunk in fault.allocations) == 32 * 1024 * 1024
    assert registry.stop("mem-test") is fault
    assert registry.active() == []


def test_expired_fault_is_not_applied() -> None:
    registry = FaultRegistry("order-service")
    fault = registry.start(
        FaultRequest(
            experiment_id="old-fault",
            fault_type=FaultType.HTTP_500,
            intensity=1,
            duration_seconds=1,
        )
    )
    fault.ends_at = time.time() - 1

    assert registry.active() == []


@pytest.mark.asyncio
async def test_http_error_fault_is_deterministic() -> None:
    registry = FaultRegistry("checkout-api")
    registry.start(
        FaultRequest(
            experiment_id="error-test",
            fault_type=FaultType.HTTP_500,
            intensity=0.5,
            duration_seconds=5,
        )
    )

    with pytest.raises(HTTPException, match="controlled fault"):
        await registry.apply_request_faults()


@pytest.mark.asyncio
async def test_latency_drop_and_dependency_delays_are_controlled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []

    async def capture_delay(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", capture_delay)
    registry = FaultRegistry("payment-service")
    registry.start(
        FaultRequest(
            experiment_id="latency-test",
            fault_type=FaultType.LATENCY,
            intensity=0.5,
            duration_seconds=5,
        )
    )
    await registry.apply_request_faults()
    registry.stop("latency-test")
    registry.start(
        FaultRequest(
            experiment_id="database-test",
            fault_type=FaultType.DATABASE_SLOWDOWN,
            intensity=0.5,
            duration_seconds=5,
        )
    )
    await registry.dependency_delay(database=True)
    registry.stop("database-test")
    registry.start(
        FaultRequest(
            experiment_id="drop-test",
            fault_type=FaultType.DROP,
            intensity=0.5,
            duration_seconds=5,
        )
    )

    with pytest.raises(HTTPException, match="dropped request"):
        await registry.apply_request_faults()

    assert delays == pytest.approx([0.525, 0.8, 1.0])


@pytest.mark.asyncio
async def test_cpu_pressure_is_bounded() -> None:
    registry = FaultRegistry("order-service")
    registry.start(
        FaultRequest(
            experiment_id="cpu-test",
            fault_type=FaultType.CPU_PRESSURE,
            intensity=0.01,
            duration_seconds=5,
        )
    )
    started = time.perf_counter()

    await registry.apply_request_faults()

    assert time.perf_counter() - started < 0.1
