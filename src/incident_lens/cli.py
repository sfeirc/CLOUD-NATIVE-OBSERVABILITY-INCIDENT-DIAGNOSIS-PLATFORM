from __future__ import annotations

import argparse
import os

import uvicorn

APPS = {
    "api": "incident_lens.api_service:app",
    "order": "incident_lens.order_service:app",
    "payment": "incident_lens.payment_service:app",
    "diagnosis": "incident_lens.diagnosis_service:app",
    "chaos": "incident_lens.chaos_service:app",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an Incident Lens component")
    parser.add_argument("component", choices=APPS)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(APPS[args.component], host=os.getenv("BIND_HOST", "127.0.0.1"), port=args.port)


if __name__ == "__main__":
    main()
