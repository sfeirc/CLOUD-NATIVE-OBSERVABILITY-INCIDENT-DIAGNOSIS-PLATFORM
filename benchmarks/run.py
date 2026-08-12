from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path

import psutil

from incident_lens.correlation import CorrelationEngine, percentile
from incident_lens.model import Evidence, EvidenceStore, SignalKind

ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "benchmarks" / "results"
SIZES = (100, 1_000, 5_000, 10_000)
REPETITIONS = 30


def make_store(size: int) -> EvidenceStore:
    store = EvidenceStore(max_items=size * 3)
    now = 10_000.0
    baseline_count = size
    current_count = max(10, size // 5)
    for index in range(baseline_count):
        timestamp = now - 180 + index / max(1, baseline_count)
        store.add(
            Evidence(
                timestamp,
                "checkout-api",
                SignalKind.SPAN,
                "POST /checkout",
                70 + index % 9,
                "ms",
                attributes={"span.kind": "SERVER", "error": False},
            )
        )
    for index in range(current_count):
        timestamp = now - 20 + index / max(1, current_count)
        store.add_many(
            [
                Evidence(
                    timestamp,
                    "checkout-api",
                    SignalKind.SPAN,
                    "POST /checkout",
                    700 + index % 20,
                    "ms",
                    attributes={"span.kind": "SERVER", "error": False},
                ),
                Evidence(
                    timestamp,
                    "payment-service",
                    SignalKind.SPAN,
                    "INSERT payments",
                    600 + index % 20,
                    "ms",
                    attributes={"span.kind": "CLIENT", "db.system": "postgresql"},
                ),
            ]
        )
    return store


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def metadata(label: str, clean: bool) -> dict[str, object]:
    packages = {
        package: importlib.metadata.version(package)
        for package in ("incident-lens", "pydantic", "opentelemetry-proto")
    }
    return {
        "timestamp": time.time(),
        "hardware": {
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpus": psutil.cpu_count(),
            "physical_cpus": psutil.cpu_count(logical=False),
            "memory_bytes": psutil.virtual_memory().total,
        },
        "operating_system": platform.platform(),
        "software": {"python": platform.python_version(), "packages": packages},
        "commit": git_output("rev-parse", "HEAD"),
        "working_tree_clean": clean,
        "configuration": {
            "sizes": SIZES,
            "repetitions": REPETITIONS,
            "clock": "time.perf_counter_ns",
            "measured_operation": "CorrelationEngine.analyze over an in-memory EvidenceStore",
            "process_id": os.getpid(),
            "result_label": label,
        },
    }


def run(label: str, allow_dirty: bool = False) -> dict[str, object]:
    if Path(label).name != label or label in {"", ".", ".."}:
        raise ValueError("result label must be a single safe directory name")
    clean = git_output("status", "--porcelain") == ""
    if not clean and not allow_dirty:
        raise RuntimeError(
            "refusing to benchmark a dirty tree; commit changes or use --allow-dirty"
        )
    output = RESULTS_ROOT / label
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, int | float]] = []
    for size in SIZES:
        store = make_store(size)
        engine = CorrelationEngine(store)
        engine.analyze(10_000.0)  # unmeasured warm-up
        for repetition in range(REPETITIONS):
            started = time.perf_counter_ns()
            incident = engine.analyze(10_000.0)
            elapsed = time.perf_counter_ns() - started
            rows.append(
                {
                    "evidence_items": len(store),
                    "configured_baseline_items": size,
                    "repetition": repetition,
                    "duration_ms": elapsed / 1_000_000,
                    "hypothesis_count": len(incident.hypotheses) if incident else 0,
                }
            )

    raw_path = output / "raw_measurements.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summaries = []
    for size in SIZES:
        samples = [
            float(row["duration_ms"]) for row in rows if row["configured_baseline_items"] == size
        ]
        summaries.append(
            {
                "configured_baseline_items": size,
                "median_ms": statistics.median(samples),
                "p95_ms": percentile(samples, 0.95),
                "min_ms": min(samples),
                "max_ms": max(samples),
            }
        )
    result: dict[str, object] = {"metadata": metadata(label, clean), "summary": summaries}
    (output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Incident Lens correlation analysis")
    parser.add_argument(
        "--output", default="local", help="directory label under benchmarks/results"
    )
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    run(args.output, args.allow_dirty)


if __name__ == "__main__":
    main()
