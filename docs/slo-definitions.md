# Service-level objectives

| SLO | Target | Indicator | Budget interpretation |
|---|---:|---|---|
| Checkout availability | 99.9% | non-error checkout server spans / all checkout server spans | 0.1% failures allowed |
| Checkout latency | 99% below 300 ms | checkout server spans at or below 300 ms / all checkout server spans | 1% slow requests allowed |
| Payment success | 99% | non-error payment server spans / all payment server spans | 1% failures allowed |

For a window with `total` events and `bad` events:

```text
compliance       = 1 - bad / total
budget consumed  = (bad / total) / (1 - target)
budget remaining = max(0, 1 - budget consumed)
burn rate        = observed bad fraction / allowed bad fraction
```

The diagnosis engine evaluates five-minute and one-hour bad-event fractions. A
fast-burn page requires both windows at or above 14.4×. A slower ticket condition
requires both at or above 6×. Requiring both windows reduces alerts for isolated
single-window spikes. The short demo may have only a partial one-hour sample; the
UI reports the event counts so this is visible.

Prometheus records the same RED counters and contains matching multi-window alert
rules. The in-process calculation is what attaches explicit event evidence to an
incident; Prometheus remains the independent alert evaluator.

