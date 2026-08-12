from __future__ import annotations

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from .service_factory import create_service
from .telemetry import propagation_headers

app, settings, logger, instruments, faults = create_service("checkout-api")


class CheckoutRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0, le=100_000)


@app.post("/checkout")
async def checkout(payload: CheckoutRequest, request: Request) -> dict[str, object]:
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.post(
                f"{settings.order_url}/orders",
                json=payload.model_dump(),
                headers=propagation_headers(request),
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        instruments.dependency_errors.add(
            1, {"service": settings.service_name, "dependency": "order-service"}
        )
        logger.error(
            "checkout.order_failed",
            extra={"request_id": request.state.request_id, "error_type": type(exc).__name__},
        )
        raise HTTPException(502, "order service failed") from exc
    return {"status": "accepted", "order": response.json()}
