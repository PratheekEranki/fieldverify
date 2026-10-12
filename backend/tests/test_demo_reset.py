from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.seed import seed


@pytest.fixture()
def api():
    seed(today=date.today())
    with TestClient(app) as c:
        yield c


def save_one(api):
    vid = api.get("/api/visits").json()[0]["id"]
    rid = api.post("/api/verify/manual", json={"visit_id": vid, "last_name": "X", "dob": "1990-01-01",
                                               "photo_checked": True}).json()["id"]
    api.post("/api/audit", json={"result_id": rid})


def test_reset_disabled_without_token(api, monkeypatch):
    monkeypatch.setattr(settings, "demo_reset_token", "")
    assert api.post("/api/demo/reset").status_code == 404


def test_reset_requires_matching_token_and_clears_audit(api, monkeypatch):
    monkeypatch.setattr(settings, "demo_reset_token", "s3cret-token")
    save_one(api)
    assert len(api.get("/api/audit").json()) == 1
    assert api.post("/api/demo/reset", headers={"X-Demo-Reset-Token": "wrong"}).status_code == 403
    assert len(api.get("/api/audit").json()) == 1
    res = api.post("/api/demo/reset", headers={"X-Demo-Reset-Token": "s3cret-token"})
    assert res.status_code == 200 and res.json()["visits"] == 6
    assert api.get("/api/audit").json() == []
