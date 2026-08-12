# Benchmark methodology

`python benchmarks/run.py --output <label>` measures only
`CorrelationEngine.analyze`; evidence
construction is outside the timed region. Each configured size is warmed once,
then measured 30 times with a monotonic high-resolution clock. The workload has
one baseline checkout span per configured item and a 20% incident window with a
checkout and payment database span per request.

The runner refuses a dirty Git tree by default. To compare recorded runs:

```shell
python benchmarks/compare.py \
  --baseline local \
  --candidate optimized-02b13ad \
  --output comparison-02b13ad
```

The comparison fails unless hardware, OS, Python, sizes, and repetition counts
match. It generates JSON and SVG from the recorded summaries.

The benchmark is a local algorithm-cost characterization. It does **not** measure
Collector ingestion, backend storage, Docker networking, traffic throughput, or
multi-tenant scale. Results are not portable across hardware. Raw samples,
hardware, OS, package versions, commit, configuration, and generated SVG live in
the selected directory under `benchmarks/results/`.
