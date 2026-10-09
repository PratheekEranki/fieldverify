from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    res = TestClient(app).get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "credence_configured" in body
    # The license key must never appear in an API response.
    assert "CS" not in str(body.get("credence_configured"))
