# ADR 0002: Bounded service-level fault injection

- Status: accepted
- Date: 2026-08-12

## Context

The demo must reproduce incidents without destabilizing the developer host.

## Decision

Faults are opt-in, time-bounded, recorded experiments applied inside target
service containers. CPU and memory intensity are capped and containers have
resource limits. No host networking, privileged mode, kernel manipulation, or
random scheduling is used.

## Alternatives considered

- Toxiproxy: strong network fault model, but would not demonstrate an owned
  experiment control plane or service-local pressure.
- Chaos Mesh/Litmus: appropriate for clusters, excessive for the Compose-first
  acceptance path and dependent on privileged Kubernetes capabilities.
- Host stress tools: rejected because isolation and cleanup are harder to prove.

## Consequences

Experiments are reproducible and safe by construction, but they cannot model
kernel, node, packet-level, or multi-zone failures.

