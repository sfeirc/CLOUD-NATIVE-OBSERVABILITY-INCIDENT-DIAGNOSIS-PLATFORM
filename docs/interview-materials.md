# Interview materials

## Engineering talking points

- Why the Collector fans the same OTLP stream to storage and diagnosis instead of
  relying on a second application event channel.
- How bounded metric labels prevent request/trace identity from multiplying time
  series while preserving correlation in spans and logs.
- Why a rule score is an evidence weight rather than a probability, and how each
  contribution cites inspectable signals.
- How multi-window burn alerts connect operational urgency to error-budget policy.
- Why fault duration, memory, and CPU work are capped and constrained to service
  containers.
- What must change for durability, tenancy, HA ingestion, authentication, and
  statistically robust baselines.

## Three CV bullets

- Built a three-service OpenTelemetry observability lab that correlates RED/system
  metrics, structured logs, distributed traces, deployment markers, and bounded
  chaos experiments through a Collector fan-out to Prometheus, Loki, and Tempo.
- Implemented an evidence-citing incident engine with OTLP protobuf ingestion,
  SLO/error-budget arithmetic, multi-window burn alerts, deterministic hypothesis
  scoring, timeline generation, and incident deduplication; achieved 81.88% local
  core test coverage across 13 tests.
- Benchmarked the owned correlation path with 120 raw measurements and reproducible
  environment metadata; measured 33.365 ms median and 43.508 ms p95 analysis at
  10,000 configured baseline evidence items on the recorded four-core Windows host.

## LinkedIn project description

I built Incident Lens, a Compose-first observability and incident-diagnosis lab
for a distributed checkout flow. The services emit OpenTelemetry metrics, logs,
and traces through a real Collector into Prometheus, Loki, and Tempo. An owned
OTLP receiver calculates SLO/error-budget burn and ranks transparent root-cause
hypotheses with evidence IDs—no black-box “AI RCA” claim. A bounded chaos control
plane reproduces database latency, bad deployment, memory pressure, and dependency
outage scenarios, while Grafana and a dedicated timeline UI connect deployments,
traces, logs, and incidents. The repository includes tests, CI, ADRs, Kubernetes
manifests, raw benchmark samples, and explicit unverified/known limitations.

## 30-second pitch

Incident Lens is an observability lab where you can break a distributed checkout
system and see exactly why the platform suspects a cause. Three instrumented
services send metrics, logs, and traces through an OpenTelemetry Collector to the
Grafana stack and an incident engine I wrote. That engine computes SLO burn,
compares baseline and incident windows, ranks explicit hypotheses, cites the
underlying evidence, and builds a deployment-aware timeline. The important design
choice is transparency: it is deterministic correlation, not magical AI RCA.

## Two-minute technical pitch

The application is a checkout API calling order, then payment, with PostgreSQL and
Redis at the bottom. W3C trace context and a request ID cross both HTTP hops. Each
service records RED histograms/counters with bounded labels, database and cache
spans, process signals, and JSON logs carrying service, version, request, trace,
severity, and error fields.

The OpenTelemetry Collector is the single telemetry boundary. It exports metrics
to Prometheus, traces to Tempo, logs to Loki, and the same OTLP payloads to a
receiver I implemented. That receiver parses protobuf into a bounded evidence
model. SLO code calculates compliance, remaining budget, and short/long burn
rates. When checkout p99 or errors cross the documented condition, the correlation
engine compares service, database, CPU, memory, error, and deployment evidence.
Candidates receive capped score contributions and every contribution references
evidence IDs, so an operator can challenge the conclusion.

The chaos controller provides time-bounded faults inside resource-limited
containers. `make demo-incident` builds the stack, establishes baseline traffic,
injects a database slowdown, drives an SLO violation, asks the engine to analyze,
and prints the timeline and ranked hypotheses while leaving Grafana available.
Unit/API verification passed locally, and the in-memory correlation benchmark is
committed with raw measurements and environment metadata. Docker was unavailable
on the development host, so I explicitly do not claim the Compose/Kubernetes path
was runtime-validated or that this is production-ready.
