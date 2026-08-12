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

The local run on 2026-08-12 passed 13 tests with 82.18% coverage over the selected
owned core (entrypoint and container glue excluded). Tests cover trace parentage,
error attributes, OTLP metrics/logs, malformed payload rejection, SLO arithmetic,
dual-window alerts, database hypothesis ranking, evidence citations, safe memory
fault bounds, deterministic HTTP faults, structured logs, and API validation.

The recorded correlation benchmark uses 30 repetitions per size. Median analysis
time was 0.310 ms at 100 configured baseline items, 2.725 ms at 1,000, 13.982 ms
at 5,000, and 27.011 ms at 10,000. The 10,000-item p95 was 30.629 ms. These are
local in-memory algorithm measurements on the hardware recorded in
`benchmarks/results/local/summary.json`; no container or throughput inference is
made.

## Unverified acceptance path

The Compose and Kubernetes paths were not executable on this host. Accordingly,
this report does not claim the platform is production-ready or that the main
branch is remotely green. CI is configured to run formatting, linting, tests,
package/container builds, Compose validation, dependency audit, and static
security checks on GitHub-hosted runners.

Bandit completed locally with no findings. The local dependency audit did not
complete because PyPI TLS validation failed on a self-signed certificate in the
host chain; TLS verification was not bypassed, so no clean audit result is claimed.
