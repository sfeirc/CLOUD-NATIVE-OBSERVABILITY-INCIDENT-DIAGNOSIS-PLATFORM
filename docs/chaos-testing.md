# Controlled failure scenarios

The controller only calls private fault endpoints inside resource-limited service
containers. Every request includes an experiment ID, affected service, bounded
intensity, start time, and automatic end time. The maximum duration is five
minutes; memory allocation is capped at 32 MiB per experiment and per-request CPU
work is capped at 100 ms. The implementation never uses privileged containers,
host PID/network namespaces, kernel controls, or host stress tools.

Run the default database scenario with `make demo-incident`. Other scenarios:

```shell
python scripts/demo_incident.py --scenario bad-deployment
python scripts/demo_incident.py --scenario memory-pressure
python scripts/demo_incident.py --scenario dependency-outage
```

| Scenario | Controlled fault | Expected evidence path |
|---|---|---|
| Database latency | Delay before payment SQL span | Checkout latency → payment latency → DB span latency |
| Bad deployment | Recreate `payment-service` as `v1.7-bad`, then return 500 | deployment marker → payment errors → cascading client errors |
| Memory pressure | 32 MiB retained allocation plus bounded delay | memory samples → payment processing degradation → latency |
| Dependency outage | Payment returns controlled 500 | failed order→payment span → order error → checkout error |

Stop an experiment early with `DELETE /experiments/{experiment_id}` on port
8081. `docker compose down` removes running containers; add `-v` only when the
stored database and telemetry volumes should also be discarded.

