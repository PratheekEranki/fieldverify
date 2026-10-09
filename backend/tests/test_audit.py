"""T09 audit log + T10 hash chain."""
import csv
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.seed import seed

BODY = dict(first_name="Robert", last_name="Kowalski", dob="1971-04-12", ssn="900-11-2233",
            street="214 N Main St", zip5="63301", photo_checked=True)


@pytest.fixture()
def client():
    seed(today=date.today())
    with TestClient(app) as c:
        yield c


def new_result(client, **overrides) -> dict:
    visits = client.get("/api/visits").json()
    vid = next(v["id"] for v in visits if v["provider"]["name"] == "Robert Kowalski")
    return client.post("/api/verify/manual", json={**BODY, "visit_id": vid, **overrides}).json()


def test_save_list_and_no_sensitive_values(client):
    result = new_result(client)
    saved = client.post("/api/audit", json={"result_id": result["id"], "notes": "Provider present at site"})
    assert saved.status_code == 201
    rows = client.get("/api/audit").json()
    assert len(rows) == 1 and rows[0]["notes"] == "Provider present at site"
    raw = client.get("/api/audit").text + client.get("/api/audit/export.csv").text
    assert "900112233" not in raw and "2233" not in raw and "1971-04-12" not in raw


def test_cannot_save_twice_or_unknown(client):
    result = new_result(client)
    assert client.post("/api/audit", json={"result_id": result["id"]}).status_code == 201
    assert client.post("/api/audit", json={"result_id": result["id"]}).status_code == 409
    assert client.post("/api/audit", json={"result_id": "nope"}).status_code == 404


def test_filters_and_csv(client):
    for overrides in ({}, {"dob": "1971-12-04"}, {"dob": "1990-01-01", "ssn": "911111111"}):
        client.post("/api/audit", json={"result_id": new_result(client, **overrides)["id"]})
    assert len(client.get("/api/audit?band=yellow").json()) == 1
    assert len(client.get("/api/audit?mode=manual").json()) == 3
    res = client.get("/api/audit/export.csv")
    assert res.headers["content-type"].startswith("text/csv")
    reader = list(csv.reader(io.StringIO(res.content.decode("utf-8-sig"))))
    assert reader[0][0] == "id" and len(reader) == 4


def test_no_update_or_delete_routes_exist():
    for route in app.routes:
        if getattr(route, "path", "").startswith("/api/audit"):
            assert not ({"PUT", "PATCH", "DELETE"} & set(getattr(route, "methods", set()))), route.path


def test_chain_verifies_then_detects_tampering(client):
    for _ in range(3):
        client.post("/api/audit", json={"result_id": new_result(client)["id"]})
    assert client.get("/api/audit/verify-chain").json() == {"ok": True, "entries": 3, "first_bad_id": None}

    # Simulate someone editing the database directly: rewrite entry 2's notes.
    with engine.begin() as conn:
        conn.execute(text("UPDATE auditentry SET notes = 'Provider verified, all good' WHERE id = 2"))
    check = client.get("/api/audit/verify-chain").json()
    assert check["ok"] is False and check["first_bad_id"] == 2


def test_chain_detects_upgraded_band(client):
    client.post("/api/audit", json={"result_id": new_result(client, dob="1990-01-01", ssn="911111111")["id"]})
    with engine.begin() as conn:
        conn.execute(text("UPDATE auditentry SET band = 'green', score = 100 WHERE id = 1"))
    check = client.get("/api/audit/verify-chain").json()
    assert check["ok"] is False and check["first_bad_id"] == 1


def test_chain_detects_deleted_row(client):
    for _ in range(3):
        client.post("/api/audit", json={"result_id": new_result(client)["id"]})
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM auditentry WHERE id = 2"))
    check = client.get("/api/audit/verify-chain").json()
    assert check["ok"] is False and check["first_bad_id"] == 3
