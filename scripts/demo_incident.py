from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = "http://localhost:8080/checkout"
CHAOS = "http://localhost:8081/experiments"
DIAGNOSIS = "http://localhost:8082"

SCENARIOS = {
    "database-latency": {
        "affected_service": "payment-service",
        "fault_type": "database_slowdown",
        "intensity": 0.85,
    },
    "bad-deployment": {
        "affected_service": "payment-service",
        "fault_type": "http_500",
        "intensity": 1.0,
    },
    "memory-pressure": {
        "affected_service": "payment-service",
        "fault_type": "memory_pressure",
        "intensity": 1.0,
    },
    "dependency-outage": {
        "affected_service": "payment-service",
        "fault_type": "http_500",
        "intensity": 1.0,
    },
}


def compose(*args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        env=env,
        check=True,
    )


async def wait_ready(url: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                if (await client.get(url, timeout=2)).is_success:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    raise RuntimeError(f"timed out waiting for {url}")


async def send_traffic(count: int, concurrency: int) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(concurrency)

    async def one(index: int) -> dict[str, Any]:
        async with semaphore, httpx.AsyncClient(timeout=4) as client:
            started = time.perf_counter()
            try:
                response = await client.post(
                    CHECKOUT,
                    json={"customer_id": f"demo-{index % 20}", "amount": 42.50},
                )
                status = response.status_code
            except httpx.HTTPError:
                status = 0
            return {
                "sequence": index,
                "status": status,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }

    return await asyncio.gather(*(one(index) for index in range(count)))


async def run(scenario_name: str) -> dict[str, Any]:
    config = SCENARIOS[scenario_name]
    compose("up", "--build", "-d", "--wait")
    await wait_ready(f"{DIAGNOSIS}/healthz")
    await wait_ready("http://localhost:8080/healthz")

    print("[1/5] Establishing a healthy baseline with 40 checkout requests")
    baseline = await send_traffic(40, concurrency=4)
    await asyncio.sleep(4)

    if scenario_name == "bad-deployment":
        print("[2/5] Recreating payment-service as version v1.7-bad")
        changed_env = os.environ.copy()
        changed_env["PAYMENT_VERSION"] = "v1.7-bad"
        compose("up", "-d", "--no-deps", "--force-recreate", "payment-service", env=changed_env)
        await asyncio.sleep(5)
    else:
        print(f"[2/5] Starting controlled experiment: {scenario_name}")

    experiment_id = f"demo-{scenario_name}-{int(time.time())}"
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            CHAOS,
            json={
                "experiment_id": experiment_id,
                **config,
                "duration_seconds": 45,
            },
        )
        response.raise_for_status()
        experiment = response.json()

    print("[3/5] Driving traffic through the fault window")
    fault = await send_traffic(32, concurrency=4)
    await asyncio.sleep(6)

    print("[4/5] Asking the diagnosis engine to evaluate exported telemetry")
    async with httpx.AsyncClient(timeout=10) as client:
        analysis = (await client.post(f"{DIAGNOSIS}/api/analyze")).json()
        slos = (await client.get(f"{DIAGNOSIS}/api/slos")).json()
    if analysis.get("incident") is None:
        raise RuntimeError("telemetry arrived, but the configured incident trigger did not fire")

    metadata = {
        "recorded_at": time.time(),
        "operating_system": platform.platform(),
        "python": sys.version,
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
        ).stdout.strip(),
        "docker": subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip(),
        "scenario": scenario_name,
        "configuration": config,
    }
    report = {
        "metadata": metadata,
        "experiment": experiment,
        "raw_measurements": {"baseline": baseline, "fault": fault},
        "slos": slos,
        "analysis": analysis,
    }
    output = ROOT / "reports" / "demo-latest.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    incident = analysis["incident"]
    print("[5/5] Incident created")
    print(f"  {incident['title']} ({incident['incident_id']})")
    for hypothesis in incident["hypotheses"][:3]:
        print(
            f"  #{hypothesis['rank']} {hypothesis['title']} in "
            f"{hypothesis['service']} — score {hypothesis['score']:.1f}"
        )
    print("  Timeline:")
    for event in incident["timeline"]:
        print(
            f"    {time.strftime('%H:%M:%S', time.localtime(event['timestamp']))} {event['event']}"
        )
    print(f"  Raw demo evidence: {output}")
    print("  Diagnosis console: http://localhost:8082")
    print("  Grafana: http://localhost:3000/d/incident-lens")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible Incident Lens scenario")
    parser.add_argument("--scenario", choices=SCENARIOS, default="database-latency")
    args = parser.parse_args()
    if shutil.which("docker") is None:
        raise SystemExit("Docker is required for the end-to-end demo but was not found on PATH.")
    asyncio.run(run(args.scenario))


if __name__ == "__main__":
    main()
