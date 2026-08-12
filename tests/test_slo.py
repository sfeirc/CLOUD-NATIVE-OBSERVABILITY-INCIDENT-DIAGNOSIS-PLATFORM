from incident_lens.slo import SLODefinition, calculate_slo


def test_error_budget_and_burn_rate_are_derived_from_events() -> None:
    status = calculate_slo(
        SLODefinition("availability", "api", 0.99, "availability"),
        total_events=1_000,
        bad_events=20,
        short_bad_fraction=0.03,
        long_bad_fraction=0.02,
    )

    assert status.compliance == 0.98
    assert round(status.budget_consumed, 4) == 2.0
    assert status.budget_remaining == 0
    assert round(status.short_burn_rate, 4) == 3.0
    assert not status.alerting


def test_burn_alert_requires_both_windows() -> None:
    definition = SLODefinition("availability", "api", 0.999, "availability")
    only_short = calculate_slo(
        definition,
        total_events=1_000,
        bad_events=1,
        short_bad_fraction=0.02,
        long_bad_fraction=0.001,
    )
    both = calculate_slo(
        definition,
        total_events=1_000,
        bad_events=20,
        short_bad_fraction=0.02,
        long_bad_fraction=0.02,
    )

    assert not only_short.alerting
    assert both.alerting
