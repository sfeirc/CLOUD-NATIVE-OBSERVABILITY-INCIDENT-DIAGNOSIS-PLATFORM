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
