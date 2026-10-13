"""Android second read: name/DOB from an open-source read attached to a Tap2iD result (capped at yellow)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.seed import seed

TOKEN = "device-token-for-tests"
H = {"X-Device-Token": TOKEN}
UTOPIA = "Utopia Department of Motor Vehicles"


def tap2id_doc(trusted: bool) -> dict:
    return {"doc_type": "org.iso.18013.5.1.mDL", "issuer_signed_valid": True, "device_signed_valid": True,
            "digests_valid": True, "issuer_trusted": trusted, "chain_status": "VERIFIED" if trusted else "UNTRUSTED",
            "mso_status": "VALID", "namespaces": {"org.iso.18013.5.1": {"issuing_authority": UTOPIA,
                                                                       "age_over_21": True}}}


def second(result_id: str, **overrides) -> dict:
    body = {"result_id": result_id, "reader": "multipaz-0.101.0", "doc_type": "org.iso.18013.5.1.mDL",
            "issuer_signed_valid": True, "device_signed_valid": True, "digests_valid": True, "valid_now": True,
            "issuer_dn": "C=US,CN=OWF Multipaz TEST IACA", "issuing_authority": UTOPIA,
            "given_name": "Erika", "family_name": "Mustermann", "birth_date": "1971-09-01"}
    body.update(overrides)
    return body


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setattr(settings, "android_device_token", TOKEN)
    seed(today=date.today())
    with TestClient(app) as c:
        yield c


def first_read(api, name="Erika Mustermann", trusted=True) -> dict:
    vid = next(v["id"] for v in api.get("/api/visits").json() if v["provider"]["name"] == name)
    r = api.post("/api/verify/digital/tap2id", headers=H,
                 json={"visit_id": vid, "status": "SUCCESS" if trusted else "PARTIAL_SUCCESS",
                       "documents": [tap2id_doc(trusted)]})
    assert r.status_code == 200
    return r.json()


def test_requires_device_token(api):
    rid = first_read(api)["id"]
    assert api.post("/api/verify/digital/second-read", json=second(rid)).status_code == 401


def test_genuine_first_read_plus_matching_second_read_is_capped_yellow(api):
    first = first_read(api)
    r = api.post("/api/verify/digital/second-read", headers=H, json=second(first["id"]))
    assert r.status_code == 200
    out = r.json()
    assert out["match"]["band"] == "green" and out["match"]["score"] == 100
    assert out["outcome"]["color"] == "yellow" and "not checked by Credence" in out["outcome"]["label"]
    assert out["match_source"] == "second_read" and out["supplements"] == first["id"]
    assert out["authenticity"] == first["authenticity"]  # authenticity is never changed by the second read


def test_untrusted_first_read_stays_red_but_shows_match(api):
    first = first_read(api, trusted=False)
    out = api.post("/api/verify/digital/second-read", headers=H, json=second(first["id"])).json()
    assert out["outcome"]["color"] == "red" and out["match"]["band"] == "green"


def test_wrong_person_is_red(api):
    first = first_read(api, name="Robert Kowalski")
    out = api.post("/api/verify/digital/second-read", headers=H, json=second(first["id"])).json()
    assert out["match"]["band"] == "red" and out["outcome"]["color"] == "red"


@pytest.mark.parametrize("override", [{"issuer_signed_valid": False}, {"device_signed_valid": False},
                                      {"digests_valid": False}, {"valid_now": False}])
def test_failed_second_read_checks_are_rejected(api, override):
    rid = first_read(api)["id"]
    r = api.post("/api/verify/digital/second-read", headers=H, json=second(rid, **override))
    assert r.status_code == 422 and r.json()["error"]["code"] == "second_read_failed_checks"


def test_different_issuer_is_rejected(api):
    rid = first_read(api)["id"]
    r = api.post("/api/verify/digital/second-read", headers=H, json=second(rid, issuing_authority="Illinois SOS"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "second_read_different_issuer"


def test_missing_details_rejected(api):
    rid = first_read(api)["id"]
    r = api.post("/api/verify/digital/second-read", headers=H, json=second(rid, family_name=None))
    assert r.status_code == 422


def test_only_once_and_only_for_tap2id(api):
    rid = first_read(api)["id"]
    done = api.post("/api/verify/digital/second-read", headers=H, json=second(rid)).json()
    assert api.post("/api/verify/digital/second-read", headers=H, json=second(done["id"])).status_code == 409


def test_saved_to_audit_with_second_read_source(api):
    rid = first_read(api)["id"]
    out = api.post("/api/verify/digital/second-read", headers=H, json=second(rid)).json()
    assert api.post("/api/audit", json={"result_id": out["id"], "photo_checked": True}).status_code == 201
    entry = api.get("/api/audit").json()[0]
    assert entry["match_source"] == "second_read" and entry["channel"] == "android"
    # Presented values (what the ID said) are never logged, only per-field outcomes.
    assert "Mustermann" not in str(entry["field_results"]) and "1971" not in str(entry)
    assert api.get("/api/audit/verify-chain").json()["ok"] is True
