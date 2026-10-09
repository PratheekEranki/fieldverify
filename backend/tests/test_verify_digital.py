"""T15: digital verification endpoints against a fake Credence (documented response shapes)."""
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.credence import client as credence_client_module
from app.credence.client import CredenceClient
from app.credence.parse import parse_birth_date, parse_mdoc_result, parse_res_response
from app.main import app
from app.routers import verify_digital
from app.seed import seed

FIXTURES = Path(__file__).parent / "fixtures"
B_INITIATE = FIXTURES / "flow_b_initiate_age_check_profile.json"
PORTRAIT_B64 = "/9j/4AAQSkZJRgABAQAAAQABAAD"  # start of a JPEG, enough for the data-URL check
KOWALSKI = {"given_name": "Robert", "family_name": "Kowalski", "birth_date": "1971-04-12",
            "issuing_authority": "Illinois Secretary of State", "portrait": PORTRAIT_B64}


class FakeCredence:
    def __init__(self):
        self.validate_body: dict = {"res": True, "resDetails": json.dumps(
            {"identity": KOWALSKI, "authentication": {"issuerTrusted": True, "signatureValid": True}})}
        self.c_results: list[tuple[int, dict]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/cloudsdk/playground")
        if path == "/v1/setup":
            return httpx.Response(200, json={"accessToken": "tok", "refreshToken": "rt", "expiresIn": 900})
        if path == "/dcapi/openid4vp/v1/initiate":
            return httpx.Response(200, json=json.loads(B_INITIATE.read_text()))
        if path == "/dcapi/openid4vp/v1/validate":
            return httpx.Response(200, json=self.validate_body)
        if path == "/openid4vp/v1/mdoc/initiate":
            return httpx.Response(200, json=json.loads((FIXTURES / "flow_c_initiate.json").read_text()))
        if path == "/openid4vp/v1/mdoc/result":
            status, body = self.c_results.pop(0)
            return httpx.Response(status, json=body)
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture()
def fake(monkeypatch):
    fake = FakeCredence()
    client = CredenceClient("https://credenceid.com/cloudsdk/playground", "CS_x", "prof", "https://fv.example",
                            transport=httpx.MockTransport(fake.handler))
    monkeypatch.setattr(verify_digital, "get_client", lambda: client)
    return fake


@pytest.fixture()
def api():
    seed(today=date.today())
    with TestClient(app) as c:
        yield c


def kowalski_visit(api) -> int:
    return next(v["id"] for v in api.get("/api/visits").json() if v["provider"]["name"] == "Robert Kowalski")


def run_b(api) -> httpx.Response:
    started = api.post("/api/verify/digital/start", json={"visit_id": kowalski_visit(api), "flow": "B"}).json()
    assert started["browser"]["protocol"] == "openid4vp"
    assert "dcql_query" in started["browser"]["request"]
    return api.post("/api/verify/digital/complete", json={"session_id": started["session_id"], "data": "jwe.token"})


def test_flow_b_verified_matching_person_is_green(api, fake):
    r = run_b(api).json()
    assert r["mode"] == "digital" and r["flow"] == "B"
    assert r["authenticity"]["status"] == "verified"
    assert r["authenticity"]["issuer"] == "Illinois Secretary of State"
    assert r["authenticity"]["checks"] == {"issuerTrusted": True, "signatureValid": True}
    assert r["match"]["band"] == "green" and r["match"]["provided_weight"] == 55
    assert r["outcome"]["label"] == "Verified: cryptographic + record match"
    assert r["portrait_data_url"].startswith("data:image/jpeg;base64,")


def test_flow_b_genuine_credential_different_person_is_red(api, fake):
    other = {**KOWALSKI, "given_name": "Grace", "family_name": "Lee", "birth_date": "1977-01-29"}
    fake.validate_body = {"res": True, "resDetails": json.dumps({"identity": other, "authentication": {}})}
    r = run_b(api).json()
    assert r["authenticity"]["status"] == "verified"
    assert r["outcome"]["label"] == "Credential genuine but different person: escalate"


def test_flow_b_failed_check_is_red_even_if_names_match(api, fake):
    fake.validate_body = {"res": True, "resDetails": json.dumps(
        {"identity": KOWALSKI, "authentication": {"issuerTrusted": False}})}
    r = run_b(api).json()
    assert r["authenticity"]["status"] == "failed"
    assert r["outcome"] == {"label": "Credential failed verification: escalate", "color": "red"}


def test_flow_b_cancelled_is_409_and_session_is_single_use(api, fake):
    fake.validate_body = {"cancelled": True, "message": "Verification was cancelled by the user."}
    res = run_b(api)
    assert res.status_code == 409 and res.json()["error"]["code"] == "wallet_cancelled"


def test_flow_c_pending_then_done_with_aamva_claims(api, fake):
    aamva = {"DCS": "KOWALSKI", "DAC": "ROBERT", "DBB": "04121971", "DAJ": "IL"}
    fake.c_results = [(202, {"status": "pending"}),
                      (200, {"success": True, "identity": json.dumps(aamva), "error": None})]
    started = api.post("/api/verify/digital/start", json={"visit_id": kowalski_visit(api), "flow": "C"}).json()
    assert started["browser"]["wallet_uri"].startswith("mdoc-openid4vp://")
    assert api.get(f"/api/verify/digital/status/{started['session_id']}").json() == {"status": "pending",
                                                                                     "result": None}
    done = api.get(f"/api/verify/digital/status/{started['session_id']}").json()
    assert done["status"] == "done"
    assert done["result"]["match"]["band"] == "green" and done["result"]["authenticity"]["issuer"] == "IL"
    # Session is consumed once finished.
    assert api.get(f"/api/verify/digital/status/{started['session_id']}").status_code == 404


def test_flow_c_consent_denied_is_cancelled(api, fake):
    fake.c_results = [(200, {"success": False, "identity": None, "error": "User denied consent."})]
    started = api.post("/api/verify/digital/start", json={"visit_id": kowalski_visit(api), "flow": "C"}).json()
    res = api.get(f"/api/verify/digital/status/{started['session_id']}")
    assert res.status_code == 409 and res.json()["error"]["code"] == "wallet_cancelled"


def test_digital_result_saves_to_audit_without_portrait_or_claims(api, fake):
    r = run_b(api).json()
    entry = api.post("/api/audit", json={"result_id": r["id"]}).json()
    assert entry["mode"] == "digital" and entry["flow"] == "B" and entry["authenticity"] == "verified"
    dump = api.get("/api/audit").text + api.get("/api/audit/export.csv").text
    assert PORTRAIT_B64 not in dump and "1971-04-12" not in dump
    assert api.get("/api/audit/verify-chain").json()["ok"] is True


def test_unknown_session_and_bad_flow(api, fake):
    assert api.post("/api/verify/digital/complete", json={"session_id": "nope", "data": "x"}).status_code == 404
    assert api.post("/api/verify/digital/start", json={"visit_id": kowalski_visit(api), "flow": "Z"}).status_code == 422


def test_not_configured_is_503(api, monkeypatch):
    monkeypatch.setattr(verify_digital, "get_client", lambda: CredenceClient("https://x", "", "", ""))
    res = api.post("/api/verify/digital/start", json={"visit_id": kowalski_visit(api), "flow": "B"})
    assert res.status_code == 503 and res.json()["error"]["code"] == "credence_not_configured"


# ---------- parser units ----------

def test_parse_birth_date_formats():
    assert parse_birth_date("1971-04-12") == date(1971, 4, 12)
    assert parse_birth_date("04121971") == date(1971, 4, 12)
    assert parse_birth_date("1971-04-12T00:00:00Z") == date(1971, 4, 12)
    assert parse_birth_date("garbage") is None and parse_birth_date(None) is None


def test_parse_flattens_namespaces_and_flow_a_flat_details():
    out = parse_res_response({"res": True, "resDetails": json.dumps(
        {"org.iso.18013.5.1": {"given_name": "Jane", "family_name": "Smith", "birth_date": "1990-01-15"}})})
    assert out.status == "verified" and out.first_name == "Jane" and out.dob == date(1990, 1, 15)
    flat = parse_res_response({"res": True, "resDetails": '{"family_name":"Smith","given_name":"Jane"}'})
    assert flat.last_name == "Smith"
    assert parse_res_response({"res": False, "resDetails": "{}"}).status == "failed"
    assert parse_mdoc_result({"success": False, "error": "Timeout"}).status == "failed"


def test_get_client_singleton_uses_settings(monkeypatch):
    monkeypatch.setattr(credence_client_module, "_client", None)
    assert credence_client_module.get_client() is credence_client_module.get_client()
