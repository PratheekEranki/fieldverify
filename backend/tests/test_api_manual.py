"""T08: manual verify API, including the five scripted demo cases (tasks/todo.md T08)."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed

KOWALSKI = dict(first_name="Robert", last_name="Kowalski", dob="1971-04-12", ssn="900-11-2233",
                street="214 N Main St", zip5="63301")
RECORD_SSN = "900112233"


@pytest.fixture()
def client():
    seed(today=date.today())
    with TestClient(app) as c:
        yield c


def kowalski_visit_id(client) -> int:
    visits = client.get("/api/visits").json()
    return next(v["id"] for v in visits if v["provider"]["name"] == "Robert Kowalski")


def verify(client, **overrides):
    body = {**KOWALSKI, "visit_id": kowalski_visit_id(client), "photo_checked": True, **overrides}
    body = {k: v for k, v in body.items() if v is not None}
    return client.post("/api/verify/manual", json=body)


def test_visits_list_has_no_sensitive_fields(client):
    visits = client.get("/api/visits").json()
    assert len(visits) == 7
    raw = json.dumps(visits)
    assert "ssn" not in raw and "dob" not in raw and RECORD_SSN not in raw


def test_case1_all_exact_green_record_match_only(client):
    r = verify(client).json()
    assert r["match"]["band"] == "green" and r["match"]["score"] == 100
    assert r["outcome"]["label"] == "Record match only: not cryptographically verified"
    assert r["authenticity"]["status"] == "not_checked"


def test_case2_bob_for_robert_green(client):
    r = verify(client, first_name="Bob").json()
    assert r["match"]["band"] == "green"
    first = next(f for f in r["match"]["fields"] if f["field"] == "first_name")
    assert first["result"] == "match" and "nickname" in first["reason"].lower()


def test_case3_swapped_dob_yellow_with_reason(client):
    r = verify(client, dob="1971-12-04").json()
    assert r["match"]["band"] == "yellow"
    dob = next(f for f in r["match"]["fields"] if f["field"] == "dob")
    assert dob["result"] == "partial" and "swapped" in dob["reason"].lower()


def test_case4_wrong_dob_and_ssn_red_hard_rule(client):
    r = verify(client, dob="1990-01-01", ssn="911-11-1111").json()
    assert r["match"]["band"] == "red" and r["match"]["hard_rule"]
    assert r["outcome"]["label"] == "Cannot verify: escalate, do not proceed"


def test_case5_last_name_and_dob_only_yellow_insufficient(client):
    r = verify(client, first_name=None, ssn=None, street=None, zip5=None).json()
    assert r["match"]["band"] == "yellow" and r["match"]["insufficient_data"]


def test_response_never_contains_full_ssn(client):
    res = verify(client)
    assert RECORD_SSN not in res.text and "900-11-2233" not in res.text
    assert res.json()["presented_ssn_masked"] == "***-**-2233"


def test_validation_error_does_not_echo_ssn(client):
    res = verify(client, dob="not-a-date", ssn="900-11-2233")
    assert res.status_code == 422
    assert "2233" not in res.text


def test_photo_check_required(client):
    res = verify(client, photo_checked=False)
    assert res.status_code == 422 and res.json()["error"]["code"] == "photo_check_required"


def test_unknown_visit_404(client):
    res = client.post("/api/verify/manual", json={**KOWALSKI, "visit_id": 9999, "photo_checked": True})
    assert res.status_code == 404 and res.json()["error"]["code"] == "visit_not_found"


def test_result_can_be_fetched_again_until_saved_state_changes(client):
    r = verify(client).json()
    again = client.get(f"/api/verify/results/{r['id']}")
    assert again.status_code == 200 and again.json()["match"] == r["match"]
    assert client.get("/api/verify/results/nope").status_code == 404
