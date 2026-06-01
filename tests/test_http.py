from fastapi.testclient import TestClient

from elenchus_core.http import app


def valid_payload():
    return {
        "traceId": "route-v2-001",
        "domain": "sre",
        "context": "Postgres has 95% I/O wait and 12 idle in transaction sessions holding locks on audit_logs.",
        "proposedAction": {"type": "terminate_idle_sessions", "target": "postgres-primary", "riskLevel": "medium"},
        "rationale": "Because 12 idle in transaction sessions hold locks on audit_logs, terminating idle sessions addresses the specific lock contention.",
    }


def test_v2_evaluate_returns_report_shape(monkeypatch):
    monkeypatch.delenv("ELENCHUS_API_TOKEN", raising=False)
    client = TestClient(app)

    response = client.post("/api/v2/evaluate", json=valid_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["calibration"] == "uncalibrated_internal_alpha"
    assert body["grounding"] is not None
    assert body["readiness"]["operatorReviewRequired"] is True


def test_v2_auth_required_when_token_configured(monkeypatch):
    monkeypatch.setenv("ELENCHUS_API_TOKEN", "secret-token")
    client = TestClient(app)

    missing = client.post("/api/v2/evaluate", json=valid_payload())
    authorized = client.post("/api/v2/evaluate", headers={"Authorization": "Bearer secret-token"}, json=valid_payload())

    assert missing.status_code == 401
    assert authorized.status_code == 200


def test_invalid_v2_request_returns_status_safe_error(monkeypatch):
    monkeypatch.delenv("ELENCHUS_API_TOKEN", raising=False)
    client = TestClient(app)

    response = client.post("/api/v2/evaluate", json={"traceId": "x"})

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["overallSignal"] is None
    assert body["subscores"] is None


def test_v1_intercept_preserves_legacy_shape(monkeypatch):
    monkeypatch.delenv("ELENCHUS_API_TOKEN", raising=False)
    client = TestClient(app)
    payload = {
        "traceId": "legacy-v1",
        "context": "A service is slow and CPU saturation is high.",
        "proposedAction": {"type": "scale_service", "target": "api"},
        "reasoning": "Because CPU saturation is high, scaling the service adds capacity.",
    }

    response = client.post("/api/v1/intercept", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"score", "terminalLog"}
    assert isinstance(body["score"], int)
    assert isinstance(body["terminalLog"], list)
