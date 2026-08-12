from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str
    service_version: str
    otlp_endpoint: str
    order_url: str
    payment_url: str
    database_url: str
    redis_url: str

    @classmethod
    def from_env(cls, service_name: str) -> Settings:
        return cls(
            service_name=service_name,
            service_version=os.getenv("SERVICE_VERSION", "dev"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
            order_url=os.getenv("ORDER_URL", "http://localhost:8001"),
            payment_url=os.getenv("PAYMENT_URL", "http://localhost:8002"),
            database_url=os.getenv(
                "DATABASE_URL", "postgresql://incident:incident@localhost:5432/incident"
            ),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        )
