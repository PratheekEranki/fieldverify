"""Combine field results into a record-match score, band, and outcome label (spec §3 and §5)."""
from dataclasses import dataclass, field
from datetime import date

from app.scoring.fields import (
    NO_MATCH,
    NOT_PROVIDED,
    PARTIAL,
    FieldResult,
    score_address,
    score_dob,
    score_first_name,
    score_last_name,
    score_ssn,
)

GREEN_MIN, YELLOW_MIN = 85, 60
MIN_PROVIDED_WEIGHT = 50


@dataclass
class Presented:
    """What was presented: wallet claims (digital) or the typed form (manual). Missing = None."""

    first_name: str | None = None
    last_name: str | None = None
    dob: date | None = None
    ssn: str | None = None
    street: str | None = None
    zip5: str | None = None


@dataclass
class RecordView:
    """The enrollment-record fields the engine needs (decoupled from the DB model)."""

    first_name: str
    last_name: str
    aliases: list[str]
    dob: date
    ssn: str
    street: str
    zip5: str


@dataclass
class MatchResult:
    score: int
    band: str
    insufficient_data: bool
    provided_weight: int
    hard_rule: str | None
    caps: list[str] = field(default_factory=list)
    fields: list[FieldResult] = field(default_factory=list)


def _band(score: int) -> str:
    return "green" if score >= GREEN_MIN else "yellow" if score >= YELLOW_MIN else "red"


def score_identity(presented: Presented, record: RecordView) -> MatchResult:
    fields = [
        score_last_name(presented.last_name, record.last_name, record.aliases),
        score_first_name(presented.first_name, record.first_name),
        score_dob(presented.dob, record.dob),
        score_ssn(presented.ssn, record.ssn),
        score_address(presented.street, presented.zip5, record.street, record.zip5),
    ]
    by_name = {f.field: f for f in fields}
    provided = [f for f in fields if f.result != NOT_PROVIDED]
    provided_weight = sum(f.max for f in provided)

    if provided_weight == 0:
        # Nothing to compare is not evidence of a mismatch (e.g. an age-check profile shares no name or DOB).
        # Never red here: red means "different person". Yellow + insufficient data sends it to a human.
        return MatchResult(0, "yellow", True, 0, None, ["No identity details were shared to compare"], fields)

    score = round(sum(f.points for f in provided) / provided_weight * 100)
    band = _band(score)
    caps: list[str] = []
    hard_rule: str | None = None

    # Hard rules override the score entirely.
    if by_name["dob"].result == NO_MATCH and by_name["ssn"].result == NO_MATCH:
        hard_rule = "Date of birth and SSN both do not match"
    elif by_name["last_name"].result == NO_MATCH and by_name["first_name"].result == NO_MATCH:
        hard_rule = "First and last name both do not match"
    if hard_rule:
        return MatchResult(score, "red", provided_weight < MIN_PROVIDED_WEIGHT, provided_weight, hard_rule,
                           fields=fields)

    # Caps can only lower a green to yellow.
    insufficient = provided_weight < MIN_PROVIDED_WEIGHT
    if insufficient:
        caps.append(f"Only {provided_weight} of 100 weight points provided (minimum {MIN_PROVIDED_WEIGHT})")
    for key, label in (("dob", "Date of birth"), ("ssn", "SSN")):
        if by_name[key].result == PARTIAL:
            caps.append(f"{label} discrepancy always needs follow-up")
    if caps and band == "green":
        band = "yellow"

    return MatchResult(score, band, insufficient, provided_weight, None, caps, fields)


OUTCOMES = {
    ("digital", "verified", "green"): ("Verified: cryptographic + record match", "green"),
    ("digital", "verified", "yellow"): ("Credential genuine: record discrepancy, follow up", "yellow"),
    ("digital", "verified", "red"): ("Credential genuine but different person: escalate", "red"),
    ("manual", "not_checked", "green"): ("Record match only: not cryptographically verified", "green"),
    ("manual", "not_checked", "yellow"): ("Partial record match: follow up", "yellow"),
    ("manual", "not_checked", "red"): ("Cannot verify: escalate, do not proceed", "red"),
}


ID_DETAILS_OUTCOMES = {
    "green": ("Credential genuine + photo confirmed; ID details match record", "green"),
    "yellow": ("Credential genuine + photo confirmed; ID details partly match: follow up", "yellow"),
    "red": ("Credential genuine, but ID details don't match the record: escalate", "red"),
}

# Android only: name/DOB from a second, open-source read (Multipaz library) after the Tap2iD read. The issuer
# signature on those fields was checked by that library, not by Credence, and nothing proves both reads were the same
# credential, so a match is capped at yellow ("confirm") and never reads as verified. See docs/android/CONTEXT.md §12.
SECOND_READ_OUTCOMES = {
    "green": ("Credential genuine; second-read name/DOB match record (not checked by Credence): confirm", "yellow"),
    "yellow": ("Credential genuine; second-read name/DOB partly match: follow up", "yellow"),
    "red": ("Credential genuine, but second-read name/DOB don't match the record: escalate", "red"),
}


def outcome_for(mode: str, authenticity: str, band: str, nothing_compared: bool = False,
                match_source: str | None = None) -> tuple[str, str]:
    """Outcome label + color from spec §3. A failed credential is red regardless of the match.

    match_source="id_details": the wallet proved the credential genuine but shared no name/DOB (age-check profile),
    the auditor confirmed the photo, and the name/DOB were taken from the physical ID. Labelled so nobody mistakes
    it for a wallet-attested record match.
    """
    if mode == "digital" and authenticity == "failed":
        return ("Credential failed verification: escalate", "red")
    if mode == "digital" and match_source == "id_details":
        return ID_DETAILS_OUTCOMES[band]
    if mode == "digital" and match_source == "second_read":
        return SECOND_READ_OUTCOMES[band]
    if mode == "digital" and nothing_compared:
        return ("Credential genuine: no name or DOB shared, compare the photo", "yellow")
    return OUTCOMES[(mode, authenticity, band)]
