# Technical report

## Scope

Incident Lens is a Compose-first observability laboratory. Three services create
a checkout trace across HTTP, PostgreSQL, and Redis. Owned instrumentation emits
bounded RED/system metrics, W3C trace context, database/cache spans, and JSON logs
with request and deployment identity. The OpenTelemetry Collector fans out the
same signals to Grafana backends and an owned OTLP diagnosis receiver.

## Implemented internals

The repository implements its evidence model, protobuf-to-evidence adapter,
bounded store, nearest-rank percentile, SLO/error-budget arithmetic, multi-window
burn evaluation, incident trigger, hypothesis scoring, evidence citations,
timeline construction, incident deduplication, and bounded chaos registry. It
uses OpenTelemetry, FastAPI, PostgreSQL/psycopg, Redis, Prometheus, Loki, Tempo,
Grafana, and their documented protocols rather than hiding those dependencies.

## Telemetry model

Metric labels are restricted to service, route template, method, status class,
dependency, operation, database, and deployment version. High-cardinality request
and trace identity remains in logs and spans. The Collector exports metrics to a
Prometheus endpoint, traces to Tempo, logs to Loki, and all three OTLP payloads to
the diagnosis receiver. Grafana provisions trace-to-log and trace-to-metric links.

## Verification evidence

The local run on 2026-08-12 passed 27 tests with 86.08% coverage over the selected
owned core (entrypoint and container glue excluded). Tests cover trace parentage,
real HTTP W3C propagation, error attributes, all OTLP signal types and malformed
payloads, SLO arithmetic, dual-window alerts, all four incident scenarios,
one-snapshot analysis, exact percentile behavior, evidence citations, safe memory
fault bounds, deterministic HTTP faults, structured logs, and API validation.

Profiling attributed most correlation time to repeated evidence-window scans and
SLO extraction. The optimized engine takes one consistent hour snapshot, groups
signals by service once, reuses it for SLO calculation and ranking, and uses an
exact nearest-rank selection path that avoids full sorting for upper percentiles.
At 10,000 configured baseline items, the recorded median fell from 27.011 ms to
18.411 ms (31.8% lower) and p95 from 30.629 ms to 21.129 ms (31.0% lower). Both
runs use 30 repetitions on the same recorded hardware, OS, Python, and workload;
the comparison JSON verifies those fields. These remain local in-memory algorithm
measurements, not container or throughput results.

## Container acceptance boundary

The Compose and Kubernetes paths were not executable on the development host.
GitHub-hosted Linux CI independently completed the Python package build, Compose
model validation, and Docker image build. It does not execute the complete stack,
so backend interoperability and the killer demo remain runtime-unverified. This
report does not call the platform production-ready.

Bandit completed locally with no findings. Runtime and development dependencies
are hash-locked; an OSV audit of the lock completed with no known vulnerabilities
on 2026-08-12. This is a point-in-time result, not a permanent safety claim.
