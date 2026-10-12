"""Android reader endpoint: device token, authenticity recomputed from Tap2iD's individual checks, scoring, audit."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.seed import seed

TOKEN = "device-token-for-tests"
HEADERS = {"X-Device-Token": TOKEN}
PORTRAIT_B64 = "/9j/4AAQSkZJRgABAQAAAQABAAD"


def doc(**overrides) -> dict:
    d = {
        "doc_type": "org.iso.18013.5.1.mDL",
        "issuer_signed_valid": True, "device_signed_valid": True, "digests_valid": True,
        "issuer_trusted": True, "chain_status": "VERIFIED", "mso_status": "VALID",
        "issuer_dn": "CN=Illinois IACA", "validation_errors": [],
        "namespaces": {"org.iso.18013.5.1": {
            "given_name": "Robert", "family_name": "Kowalski", "birth_date": "1971-04-12",
            "issuing_authority": "Illinois Secretary of State", "portrait": PORTRAIT_B64, "age_over_21": True}},
    }
    d.update(overrides)
    return d


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setattr(settings, "android_device_token", TOKEN)
    seed(today=date.today())
    with TestClient(app) as c:
        yield c


def kowalski_visit(api) -> int:
    return next(v["id"] for v in api.get("/api/visits").json() if v["provider"]["name"] == "Robert Kowalski")


def post(api, visit_id, documents, status="SUCCESS", headers=HEADERS):
    return api.post("/api/verify/digital/tap2id", headers=headers,
                    json={"visit_id": visit_id, "sdk_version": "2.0.0", "status": status, "documents": documents})


def test_rejects_missing_or_wrong_token(api):
    vid = kowalski_visit(api)
    assert post(api, vid, [doc()], headers={}).status_code == 401
    assert post(api, vid, [doc()], headers={"X-Device-Token": "nope"}).status_code == 401


def test_disabled_when_server_has_no_token(api, monkeypatch):
    monkeypatch.setattr(settings, "android_device_token", "")
    assert post(api, kowalski_visit(api), [doc()]).status_code == 503


def test_genuine_matching_mdl_is_green_and_marked_android(api):
    res = post(api, kowalski_visit(api), [doc()])
    assert res.status_code == 200
    r = res.json()
    assert (r["mode"], r["channel"], r["flow"], r["match_source"]) == ("digital", "android", "tap2id", "wallet")
    assert r["authenticity"]["status"] == "verified"
    assert r["authenticity"]["issuer"] == "Illinois Secretary of State"
    assert r["match"]["band"] == "green" and r["outcome"]["color"] == "green"
    assert r["attributes"] == {"age_over_21": True}
    assert r["portrait_data_url"].startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize("override", [
    {"issuer_signed_valid": False}, {"device_signed_valid": False}, {"digests_valid": False},
    {"issuer_trusted": False}, {"chain_status": "UNTRUSTED"}, {"mso_status": "EXPIRED"},
    {"validation_errors": ["digest mismatch"]},
])
def test_any_failed_check_fails_authenticity(api, override):
    r = post(api, kowalski_visit(api), [doc(**override)]).json()
    assert r["authenticity"]["status"] == "failed"
    assert r["outcome"]["color"] == "red"
    assert not all(r["authenticity"]["checks"].values())


def test_partial_success_is_not_verified(api):
    r = post(api, kowalski_visit(api), [doc()], status="PARTIAL_SUCCESS").json()
    assert r["authenticity"]["status"] == "failed"


def test_no_documents_fails(api):
    r = post(api, kowalski_visit(api), []).json()
    assert r["authenticity"]["status"] == "failed"


def test_prefers_mdl_over_other_doc_types(api):
    other = doc(doc_type="org.iso.23220.photoid.1", issuer_trusted=False)
    r = post(api, kowalski_visit(api), [other, doc()]).json()
    assert r["authenticity"]["status"] == "verified"


def test_age_check_profile_without_name_is_not_red(api):
    ns = {"org.iso.18013.5.1": {"issuing_authority": "Illinois Secretary of State", "portrait": PORTRAIT_B64,
                                "age_over_21": True}}
    r = post(api, kowalski_visit(api), [doc(namespaces=ns)]).json()
    assert r["authenticity"]["status"] == "verified"
    assert r["match_source"] == "none" and r["outcome"]["color"] == "yellow"


def test_issuer_dn_used_when_no_issuing_authority(api):
    r = post(api, kowalski_visit(api), [doc(namespaces={"org.iso.18013.5.1": {"family_name": "Kowalski"}})]).json()
    assert r["authenticity"]["issuer"] == "CN=Illinois IACA"


def test_unknown_visit_404(api):
    assert post(api, 999999, [doc()]).status_code == 404


def test_saves_to_audit_with_android_channel(api):
    rid = post(api, kowalski_visit(api), [doc()]).json()["id"]
    saved = api.post("/api/audit", json={"result_id": rid, "photo_checked": True})
    assert saved.status_code in (200, 201)
    entry = api.get("/api/audit").json()[0]
    assert (entry["channel"], entry["flow"], entry["authenticity"]) == ("android", "tap2id", "verified")
    assert "Kowalski" not in str(entry["field_results"]) and "1971" not in str(entry)
    assert api.get("/api/audit/verify-chain").json()["ok"] is True
