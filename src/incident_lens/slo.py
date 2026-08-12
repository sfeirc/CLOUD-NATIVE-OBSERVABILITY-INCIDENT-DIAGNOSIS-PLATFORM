from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SLODefinition:
    name: str
    service: str
    target: float
    indicator: str
    threshold_ms: float | None = None


@dataclass(frozen=True)
class SLOStatus:
    definition: SLODefinition
    total_events: int
    bad_events: int
    compliance: float
    budget_consumed: float
    budget_remaining: float
    short_burn_rate: float
    long_burn_rate: float
    alerting: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


DEFAULT_SLOS = (
    SLODefinition("Checkout availability", "checkout-api", 0.999, "availability"),
    SLODefinition("Checkout p99 latency", "checkout-api", 0.99, "latency", 300),
    SLODefinition("Payment success rate", "payment-service", 0.99, "availability"),
)


def calculate_slo(
    definition: SLODefinition,
    *,
    total_events: int,
    bad_events: int,
    short_bad_fraction: float | None = None,
    long_bad_fraction: float | None = None,
) -> SLOStatus:
    compliance = 1.0 if total_events == 0 else 1 - bad_events / total_events
    allowed_bad = 1 - definition.target
    observed_bad = 0.0 if total_events == 0 else bad_events / total_events
    consumed = observed_bad / allowed_bad
    short_burn = (
        short_bad_fraction if short_bad_fraction is not None else observed_bad
    ) / allowed_bad
    long_burn = (long_bad_fraction if long_bad_fraction is not None else observed_bad) / allowed_bad
    # Multi-window, multi-burn-rate alert. Both windows must be burning.
    alerting = (short_burn >= 14.4 and long_burn >= 14.4) or (short_burn >= 6 and long_burn >= 6)
    return SLOStatus(
        definition=definition,
        total_events=total_events,
        bad_events=bad_events,
        compliance=compliance,
        budget_consumed=consumed,
        budget_remaining=max(0.0, 1 - consumed),
        short_burn_rate=short_burn,
        long_burn_rate=long_burn,
        alerting=alerting,
    )
