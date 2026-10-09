"""Unscheduled visits: provider lookup by NPI/name only, then a 1:1 verification as usual."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed


@pytest.fixture()
def client():
    seed(today=date.today())
    with TestClient(app) as c:
        yield c


def names(hits):
    return [h["provider"]["name"] for h in hits]


def test_search_by_name_words_and_case(client):
    assert names(client.get("/api/providers/search", params={"q": "rob kow"}).json()) == ["Robert Kowalski"]
    assert "Grace Lee" in names(client.get("/api/providers/search", params={"q": "LEE"}).json())


def test_search_by_npi_prefix(client):
    hit = client.get("/api/providers/search", params={"q": "rob kow"}).json()[0]
    npi = hit["provider"]["npi"]
    assert names(client.get("/api/providers/search", params={"q": npi}).json()) == ["Robert Kowalski"]
    assert "Robert Kowalski" in names(client.get("/api/providers/search", params={"q": npi[:6]}).json())


def test_search_never_matches_or_returns_ssn_or_dob(client):
    # Kowalski's SSN is 900112233 and DOB 1971-04-12. Neither can be used to find him.
    assert client.get("/api/providers/search", params={"q": "900112233"}).json() == []
    assert client.get("/api/providers/search", params={"q": "900-11-2233"}).json() == []
    assert client.get("/api/providers/search", params={"q": "1971-04-12"}).json() == []
    assert client.get("/api/providers/search", params={"q": "Kowalski 1971"}).status_code == 422
    raw = json.dumps(client.get("/api/providers/search", params={"q": "ar"}).json())
    assert "ssn" not in raw and "dob" not in raw and "900112233" not in raw


def test_search_rejects_too_short_queries(client):
    assert client.get("/api/providers/search", params={"q": "k"}).status_code == 422
    assert client.get("/api/providers/search", params={"q": "100"}).status_code == 422


def test_unscheduled_visit_flows_into_verify_and_audit(client):
    provider_id = client.get("/api/providers/search", params={"q": "grace lee"}).json()[0]["provider"]["id"]
    visit = client.post("/api/visits/unscheduled", json={"provider_id": provider_id})
    assert visit.status_code == 201 and visit.json()["visit_type"] == "unscheduled"
    vid = visit.json()["id"]
    assert vid in [v["id"] for v in client.get("/api/visits").json()]

    result = client.post("/api/verify/manual", json={
        "visit_id": vid, "first_name": "Grace", "last_name": "Lee", "dob": "1977-01-29", "photo_checked": True,
    }).json()
    assert result["visit_type"] == "unscheduled"
    entry = client.post("/api/audit", json={"result_id": result["id"]}).json()
    assert entry["visit_type"] == "unscheduled"
    assert client.get("/api/audit/verify-chain").json()["ok"] is True
    assert ",unscheduled," in client.get("/api/audit/export.csv").content.decode("utf-8-sig")


def test_unscheduled_visit_unknown_provider_404(client):
    assert client.post("/api/visits/unscheduled", json={"provider_id": 9999}).status_code == 404
