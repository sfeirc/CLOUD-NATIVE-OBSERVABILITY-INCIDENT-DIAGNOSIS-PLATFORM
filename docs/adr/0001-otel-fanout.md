# ADR 0001: Diagnose from an OpenTelemetry Collector fan-out

- Status: accepted
- Date: 2026-08-12

## Context

The demonstration needs deterministic correlation without pretending that
Grafana, Tempo, or Prometheus expose a unified incident model.

## Decision

The Collector exports OTLP to both the Grafana LGTM backend and a small diagnosis
receiver. The receiver derives a bounded evidence model from OTLP resources,
metrics, logs, and spans. Hypotheses cite evidence IDs and rule contributions.

## Alternatives considered

- Query each backend independently: realistic, but couples analysis to three
  backend query APIs and introduces ingestion-delay races in a short demo.
- Emit a second application event stream: simpler, but bypasses the actual
  telemetry pipeline and can disagree with the exported signals.
- Train an ML model: no representative labeled incident corpus exists here.

## Consequences

Advantages are deterministic ingestion, one propagation path, and inspectable
rules. Disadvantages are maintaining an OTLP receiver and storing only the
subset of telemetry required for correlation. This is an educational local
architecture, not a replacement for durable telemetry backends.

