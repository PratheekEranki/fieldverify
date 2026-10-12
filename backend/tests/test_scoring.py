"""Scoring engine tests (spec §5). Written before the implementation."""
from datetime import date

import pytest

from app.scoring.engine import Presented, RecordView, outcome_for, score_identity
from app.scoring.fields import (
    MATCH,
    NO_MATCH,
    NOT_PROVIDED,
    PARTIAL,
    score_address,
    score_dob,
    score_first_name,
    score_last_name,
    score_ssn,
)
from app.scoring.normalize import house_number, normalize_name, normalize_street

# ---------- T04 normalization ----------


@pytest.mark.parametrize(
    "raw, expected",
    [("O'Brien", "obrien"), ("José", "jose"), ("Smith Jr., MD", "smith"), ("  ANNE   marie ", "anne marie"),
     ("Garcia-Lopez", "garcia lopez")],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [("123 N Main St.", "123 n main street"), ("3020 W Clay St Apt 4B", "3020 w clay street"),
     ("2440 Hwy 94 Ste 110", "2440 highway 94"), ("1550 Zumbehl Rd", "1550 zumbehl road")],
)
def test_normalize_street(raw, expected):
    assert normalize_street(raw) == expected


def test_house_number():
    assert house_number("214 N Main St") == "214"
    assert house_number("N Main St") is None


# ---------- T05 names ----------


def test_last_name_exact_alias_typo_hyphen_none():
    assert score_last_name("Thompson", "Thompson", []).result == MATCH
    assert score_last_name("garcia", "Thompson", ["Garcia"]).result == MATCH  # maiden name
    assert score_last_name("Jonson", "Johnson", []).result == PARTIAL  # typo
    assert score_last_name("Garcia", "Garcia-Lopez", []).result == PARTIAL  # one part of hyphenated name
    assert score_last_name("Brown", "Johnson", []).result == NO_MATCH
    assert score_last_name("", "Johnson", []).result == NOT_PROVIDED


def test_first_name_nickname_and_near_misses():
    assert score_first_name("Bob", "Robert").result == MATCH
    assert score_first_name("Liz", "Elizabeth").result == MATCH
    assert score_first_name("Roberta", "Robert").result == PARTIAL  # close spelling is never full credit
    assert score_first_name("Grace", "Robert").result == NO_MATCH
    assert score_first_name(None, "Robert").result == NOT_PROVIDED


# ---------- T06 DOB, SSN, address ----------


def test_dob_rules():
    rec = date(1985, 7, 3)
    assert score_dob(date(1985, 7, 3), rec).result == MATCH
    swapped = score_dob(date(1985, 3, 7), rec)
    assert swapped.result == PARTIAL and "swapped" in swapped.reason.lower()
    assert score_dob(date(1985, 7, 8), rec).result == PARTIAL  # one digit differs
    assert score_dob(date(1990, 1, 1), rec).result == NO_MATCH
    assert score_dob(None, rec).result == NOT_PROVIDED


def test_ssn_rules():
    assert score_ssn("900-12-3456", "900123456").result == MATCH
    t = score_ssn("900213456", "900123456")
    assert t.result == PARTIAL and t.points == pytest.approx(30 * 0.4)
    assert score_ssn("911111111", "900123456").result == NO_MATCH
    assert score_ssn("12345", "900123456").result == NO_MATCH  # malformed never matches
    assert score_ssn("", "900123456").result == NOT_PROVIDED


def test_ssn_reason_never_contains_digits():
    for presented in ("900123456", "900213456", "911111111"):
        assert not any(ch.isdigit() for ch in score_ssn(presented, "900123456").reason)


def test_address_rules():
    assert score_address("214 North Main Street", "63301", "214 N Main St", "63301").result == MATCH
    assert score_address("9 Elm St", "63301", "214 N Main St", "63301").result == PARTIAL
    assert score_address("214 N Main St", "10001", "214 N Main St", "63301").result == NO_MATCH
    assert score_address("214 N Main St", None, "214 N Main St", "63301").result == NOT_PROVIDED


def test_every_result_has_reason():
    results = [score_last_name("x", "y", []), score_first_name("Bob", "Robert"), score_dob(None, date(2000, 1, 1)),
               score_ssn("900123456", "900123456"), score_address("1 A St", "63301", "1 A St", "63301")]
    assert all(r.reason for r in results)


# ---------- T07 engine ----------

RECORD = RecordView(first_name="Robert", last_name="Kowalski", aliases=[], dob=date(1971, 4, 12),
                    ssn="900112233", street="214 N Main St", zip5="63301")


def full(**overrides):
    base = dict(first_name="Robert", last_name="Kowalski", dob=date(1971, 4, 12), ssn="900112233",
                street="214 N Main St", zip5="63301")
    base.update(overrides)
    return Presented(**base)


def test_all_exact_is_100_green():
    r = score_identity(full(), RECORD)
    assert r.score == 100 and r.band == "green" and not r.insufficient_data


def test_dob_and_ssn_wrong_is_red_even_if_names_match():
    r = score_identity(full(dob=date(1990, 1, 1), ssn="911111111"), RECORD)
    assert r.band == "red" and r.hard_rule


def test_both_names_wrong_is_red():
    r = score_identity(full(first_name="Grace", last_name="Lee"), RECORD)
    assert r.band == "red" and r.hard_rule


def test_digital_style_input_scores_out_of_55_and_can_be_green():
    r = score_identity(Presented(first_name="Robert", last_name="Kowalski", dob=date(1971, 4, 12)), RECORD)
    assert r.provided_weight == 55 and r.score == 100 and r.band == "green"


def test_less_than_50_points_provided_caps_at_yellow():
    r = score_identity(Presented(last_name="Kowalski", dob=date(1971, 4, 12)), RECORD)
    assert r.provided_weight == 45 and r.score == 100
    assert r.band == "yellow" and r.insufficient_data


def test_swapped_dob_drops_to_yellow():
    r = score_identity(full(dob=date(1971, 12, 4)), RECORD)
    assert r.band == "yellow"


def test_outcome_labels():
    assert outcome_for("manual", "not_checked", "green")[0] == "Record match only: not cryptographically verified"
    assert outcome_for("digital", "verified", "green")[0] == "Verified: cryptographic + record match"
    assert outcome_for("digital", "failed", "green")[1] == "red"
    # Manual mode can never produce a "Verified" label (ADR-0002).
    for band in ("green", "yellow", "red"):
        assert not outcome_for("manual", "not_checked", band)[0].startswith("Verified")


def test_nothing_provided_is_yellow_never_red():
    r = score_identity(Presented(), RECORD)
    assert r.band == "yellow" and r.insufficient_data and r.hard_rule is None and r.provided_weight == 0
