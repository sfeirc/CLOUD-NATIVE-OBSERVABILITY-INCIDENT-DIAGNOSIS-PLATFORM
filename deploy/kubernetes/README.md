# Kubernetes extension

The manifests cover the application, diagnosis, chaos controller, PostgreSQL,
Redis, and Kubernetes-native service discovery. Deploy only after validating the
Compose path:

```shell
kubectl apply -f deploy/kubernetes/platform.yaml
kubectl apply -f deploy/kubernetes/otel-collector.yaml
```

Build and publish `incident-lens:0.1.0` first, replace the demonstration database
secret, and connect the Collector exporters to managed or in-cluster Prometheus,
Loki, Tempo, and Grafana endpoints. The repository does not claim these manifests
were cluster-tested: the development host used for the recorded verification had
neither Docker nor Kubernetes available.

