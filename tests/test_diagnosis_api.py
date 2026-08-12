from fastapi.testclient import TestClient

from incident_lens.diagnosis_service import alerts, app, incidents, store


def setup_function() -> None:
    store.clear()
    incidents.clear()
    alerts.clear()


def test_malformed_telemetry_and_alert_payloads_are_rejected() -> None:
    with TestClient(app) as client:
        assert client.post("/v1/traces", content=b"\xff").status_code == 400
        assert client.post("/api/alerts", json={"wrong": []}).status_code == 400


def test_health_dashboard_and_alert_webhook() -> None:
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/healthz").json()["evidence_count"] == 0
        response = client.post("/api/alerts", json={"alerts": [{"status": "firing"}]})
        assert response.json() == {"accepted": 1}
        assert client.post("/api/analyze").json()["incident"] is None
        assert client.get("/api/incidents/missing").status_code == 404
