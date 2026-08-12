# Known limitations

- The development host had no container runtime. GitHub Actions validated the
  Docker image build and Compose model on Linux, but did not execute the complete
  Grafana/Tempo/Loki/Prometheus/Alertmanager stack or Kubernetes manifests.
- The diagnosis store and incident registry are process-local and non-durable.
  Horizontal replicas would require shared storage and leader/deduplication logic.
- OTLP ingestion retains a useful subset, not every OTLP field. Exponential
  histogram buckets, exemplars, links, and events are not part of ranking.
- The rules use nearest-rank percentiles and fixed windows. They do not establish
  statistical causality or handle seasonality and low-traffic confidence.
- Cardinality is bounded in owned metrics, but backend retention and tenancy are
  demonstration defaults, not capacity-planned production settings.
- Fault injection is service-local. It does not model packet loss, node failure,
  DNS, zones, clocks, kernels, or managed-cloud control planes.
- PostgreSQL credentials in Compose are demonstration values. Kubernetes includes
  a placeholder Secret that must be replaced before deployment.
- The local benchmark measures only in-memory correlation analysis. It says
  nothing about request throughput, Collector capacity, or backend ingestion.
- The default PyPI audit endpoint could not validate the host TLS chain. The same
  hash-locked dependency set was successfully audited through OSV with no known
  vulnerabilities on 2026-08-12; this point-in-time result can become stale.
