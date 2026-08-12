from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request
from opentelemetry import trace
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from .service_factory import create_service

app, settings, logger, instruments, faults = create_service("payment-service")
tracer = trace.get_tracer("incident-lens.payment")


class ChargeRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0, le=100_000)


@asynccontextmanager
async def lifespan(_: object) -> AsyncIterator[None]:
    pool = AsyncConnectionPool(settings.database_url, min_size=1, max_size=5, open=False)
    await pool.open()
    async with pool.connection() as connection:
        await connection.execute(
            "CREATE TABLE IF NOT EXISTS payments "
            "(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, amount DOUBLE PRECISION NOT NULL)"
        )
    app.state.pool = pool
    app.state.cache = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield
    finally:
        await app.state.cache.aclose()
        await pool.close()


app.router.lifespan_context = lifespan


@app.post("/charge")
async def charge(payload: ChargeRequest, request: Request) -> dict[str, object]:
    payment_id = str(uuid.uuid4())
    await faults.dependency_delay(database=True)
    started = time.perf_counter()
    try:
        with tracer.start_as_current_span("INSERT payments") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.operation.name", "INSERT")
            span.set_attribute("server.address", "postgres")
            async with app.state.pool.connection() as connection:
                await connection.execute(
                    "INSERT INTO payments (id, customer_id, amount) VALUES (%s, %s, %s)",
                    (payment_id, payload.customer_id, payload.amount),
                )
        instruments.database_duration.record(
            (time.perf_counter() - started) * 1000,
            {"service": settings.service_name, "database": "payments", "operation": "INSERT"},
        )
        with tracer.start_as_current_span("SET payment cache") as span:
            span.set_attribute("db.system", "redis")
            span.set_attribute("db.operation.name", "SET")
            await app.state.cache.setex(f"payment:{payment_id}", 300, "captured")
    except Exception as exc:
        instruments.dependency_errors.add(
            1, {"service": settings.service_name, "dependency": "payment-database"}
        )
        logger.error(
            "payment.storage_failed",
            extra={
                "request_id": request.state.request_id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise HTTPException(503, "payment storage unavailable") from exc
    return {"status": "captured", "payment_id": payment_id}
