# ADR 0004: Multi-window error-budget burn alerts

- Status: accepted
- Date: 2026-08-12

## Context

Instantaneous error thresholds page on brief noise and do not express user-impact
relative to an SLO.

## Decision

Calculate bad-event fractions against the allowed SLO budget and require both a
short and long window to cross 14.4× (page) or 6× (ticket) burn rates.

## Alternatives considered

- Static error rate: easy, but insensitive to different SLO targets.
- Remaining budget only: useful for planning, too slow for acute incidents.
- Forecasting: needs traffic history unavailable in a reproducible local demo.

## Consequences

Alerts align to budget consumption and reject single-window spikes. Low traffic
can still produce unstable ratios, so event counts remain visible.

