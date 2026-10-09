"""One rule per field (spec §5). Each returns a FieldResult with points earned and a human-readable reason.

Reasons are shown to the auditor, so they never echo sensitive values (no SSN or DOB digits).
"""
from dataclasses import asdict, dataclass
from datetime import date

import jellyfish

from app.scoring.nicknames import are_nickname_equivalent
from app.scoring.normalize import digits_only, house_number, normalize_name

MATCH, PARTIAL, NO_MATCH, NOT_PROVIDED = "match", "partial", "no_match", "not_provided"

WEIGHTS = {"last_name": 20, "first_name": 10, "dob": 25, "ssn": 30, "address": 15}
TYPO_THRESHOLD = 0.88  # Jaro-Winkler; measured rationale in spec §5


@dataclass(frozen=True)
class FieldResult:
    field: str
    result: str
    points: float
    max: int
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _res(field: str, result: str, fraction: float, reason: str) -> FieldResult:
    weight = WEIGHTS[field]
    points = 0.0 if result == NOT_PROVIDED else round(weight * fraction, 2)
    return FieldResult(field=field, result=result, points=points, max=weight, reason=reason)


def score_last_name(presented: str | None, record: str, aliases: list[str]) -> FieldResult:
    p, r = normalize_name(presented), normalize_name(record)
    if not p:
        return _res("last_name", NOT_PROVIDED, 0, "Not provided")
    if p == r:
        return _res("last_name", MATCH, 1, "Exact match")
    if p in {normalize_name(a) for a in aliases}:
        return _res("last_name", MATCH, 1, "Matches a recorded former / maiden name")
    record_parts = r.split()
    if len(record_parts) > 1 and p in record_parts:
        return _res("last_name", PARTIAL, 0.5, "Matches one part of a hyphenated / compound last name")
    similarity = jellyfish.jaro_winkler_similarity(p, r)
    if similarity >= TYPO_THRESHOLD:
        return _res("last_name", PARTIAL, 0.5, f"Close spelling (similarity {similarity:.2f}), likely a typo")
    return _res("last_name", NO_MATCH, 0, "Does not match")


def score_first_name(presented: str | None, record: str) -> FieldResult:
    p, r = normalize_name(presented), normalize_name(record)
    if not p:
        return _res("first_name", NOT_PROVIDED, 0, "Not provided")
    if p == r:
        return _res("first_name", MATCH, 1, "Exact match")
    # Compare first tokens too, so "Anne Marie" vs "Anne" or nickname checks work on the given name itself.
    p0, r0 = p.split()[0], r.split()[0]
    if p0 == r0:
        return _res("first_name", MATCH, 1, "Matches the first given name")
    if are_nickname_equivalent(p0, r0):
        return _res("first_name", MATCH, 1, f"Common nickname equivalent ({p0} / {r0})")
    similarity = jellyfish.jaro_winkler_similarity(p, r)
    if similarity >= TYPO_THRESHOLD:
        return _res("first_name", PARTIAL, 0.5, f"Close spelling (similarity {similarity:.2f}), not an exact match")
    return _res("first_name", NO_MATCH, 0, "Does not match")


def score_dob(presented: date | None, record: date) -> FieldResult:
    if presented is None:
        return _res("dob", NOT_PROVIDED, 0, "Not provided")
    if presented == record:
        return _res("dob", MATCH, 1, "Exact match")
    if (presented.year == record.year and presented.month == record.day and presented.day == record.month):
        return _res("dob", PARTIAL, 0.5, "Day and month appear swapped (common data-entry error)")
    a, b = presented.strftime("%Y%m%d"), record.strftime("%Y%m%d")
    if sum(x != y for x, y in zip(a, b, strict=True)) == 1:
        return _res("dob", PARTIAL, 0.5, "Differs by a single digit (possible typo)")
    return _res("dob", NO_MATCH, 0, "Does not match")


def score_ssn(presented: str | None, record: str) -> FieldResult:
    p, r = digits_only(presented), digits_only(record)
    if not p:
        return _res("ssn", NOT_PROVIDED, 0, "Not provided")
    if len(p) != 9:
        return _res("ssn", NO_MATCH, 0, "Not a valid 9-digit SSN")
    if p == r:
        return _res("ssn", MATCH, 1, "Exact match")
    diffs = [i for i in range(9) if p[i] != r[i]]
    if len(diffs) == 2 and diffs[1] == diffs[0] + 1 and p[diffs[0]] == r[diffs[1]] and p[diffs[1]] == r[diffs[0]]:
        return _res("ssn", PARTIAL, 0.4, "Two adjacent digits appear transposed (possible typo)")
    return _res("ssn", NO_MATCH, 0, "Does not match")


def score_address(presented_street: str | None, presented_zip: str | None, record_street: str,
                  record_zip: str) -> FieldResult:
    pz = digits_only(presented_zip)[:5]
    if not pz:
        return _res("address", NOT_PROVIDED, 0, "Not provided")
    if pz != record_zip:
        return _res("address", NO_MATCH, 0, "ZIP code does not match")
    if house_number(presented_street) and house_number(presented_street) == house_number(record_street):
        return _res("address", MATCH, 1, "ZIP code and house number match")
    return _res("address", PARTIAL, 0.5, "ZIP code matches; house number missing or different")
