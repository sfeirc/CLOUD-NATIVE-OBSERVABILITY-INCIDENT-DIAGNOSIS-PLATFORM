# Root-cause ranking specification

The engine is a deterministic ranking system, not AI root-cause analysis. It
receives the same OTLP export as Tempo, Loki, and Prometheus and retains a bounded
in-memory evidence window.

## Window selection

If a deployment or chaos marker exists in the previous 55 seconds, the current
window begins at the earliest marker and the baseline immediately precedes it
with at least 15 seconds of width. Otherwise, current is the last 60 seconds and
baseline is the preceding five minutes. At least three current checkout server
spans are required.

An incident triggers when either:

- checkout p99 is above 300 ms and at least 1.5× baseline p99; or
- checkout error rate is above 1%.

## Candidate scores

| Candidate | Evidence rule | Points |
|---|---|---:|
| Database interaction regression | database-span p99 ≥2× baseline | `min(4, factor / 2)` |
|  | service span p99 ≥1.5× baseline | `min(3, factor)` |
|  | deployment in prior 10 minutes | 1.5 |
|  | no CPU sample ≥80% | 0.5 |
| Bad deployment | deployment in prior 10 minutes | 3 |
|  | concurrent error spans | `min(3, error_count / 2)` |
| Memory pressure | memory samples ≥1.2× baseline | `min(4, factor)` |
|  | service span p99 ≥1.5× baseline | `min(3, factor)` |
| Downstream dependency outage | failed client spans | `min(6, count × 1.5)` |

Candidates are sorted by total points and the top five are returned. Each score
contribution contains rule name, points, explanation, and evidence IDs. The UI
does not hide contradictory evidence: for example, the absence of CPU saturation
adds only 0.5 points and cannot create a database candidate by itself.

## Known statistical limits

Nearest-rank p99 is unstable with small samples, correlation is not causation,
and a recent deployment can be coincidental. The rules do not model seasonality,
retry amplification, topology changes, multi-region failures, or change-point
confidence. Operators must inspect the cited traces and logs before remediation.

