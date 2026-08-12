# ADR 0005: Single-snapshot correlation analysis

- Status: accepted
- Date: 2026-08-12

## Context

Profiling the 10,000-item benchmark showed repeated full-window scans dominated
analysis. SLO extraction scanned the same evidence lists per objective, ranking
rescanned current/baseline lists per service, and deployment lookup queried the
store once per service. Those reads could also observe slightly different store
states during concurrent ingestion.

## Decision

Take one locked, consistent one-hour snapshot per analysis. Partition the current
and baseline windows from that snapshot, group server spans and per-service
evidence in single passes, and reuse those groups for SLO and hypothesis work.
For upper percentiles, use exact nearest-rank selection over the small upper tail;
retain full sorting when that would not reduce work.

## Alternatives considered

- Add permanent indexes to the in-memory store: faster selective queries, but
  increases write cost, retention bookkeeping, and synchronization complexity.
- Cache SLO calculations: cheaper repeated reads, but introduces invalidation and
  can rank against a different evidence revision.
- Approximate quantiles: scalable, but unnecessary at the demonstrated size and
  changes exact incident thresholds.

## Consequences

The 10,000-item benchmark median decreased from 27.011 ms to 18.411 ms and p95
from 30.629 ms to 21.129 ms on matched recorded hardware/configuration (30 runs
per version). This is a measured in-memory improvement, not a throughput claim.
The analysis now allocates grouping dictionaries proportional to the snapshot and
still performs a linear snapshot copy; durable/high-volume designs need indexed
storage or streaming aggregates.

