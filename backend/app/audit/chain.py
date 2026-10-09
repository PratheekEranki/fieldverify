"""Tamper-evident hash chain for the audit log (spec F6).

entry_hash = sha256(prev_hash + canonical_json(entry)). Changing any stored field of any row breaks that row's
hash, and every later row's prev_hash link. The first row links to GENESIS.
"""
import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timezone

GENESIS = "0" * 64

# Fields covered by the hash. id and the hashes themselves are excluded (id is assigned by the DB after hashing).
HASHED_FIELDS = (
    "created_at", "auditor", "visit_id", "provider_id", "mode", "channel", "flow", "authenticity", "auth_checks",
    "issuer", "score", "band", "outcome", "field_results", "photo_checked", "notes",
)


def _utc_iso(value: datetime) -> str:
    # SQLite may hand datetimes back without tzinfo; treat naive values as UTC so the hash is stable on re-read.
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


def canonical_json(entry) -> str:
    payload = {}
    for name in HASHED_FIELDS:
        value = getattr(entry, name)
        payload[name] = _utc_iso(value) if isinstance(value, datetime) else value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_hash(prev_hash: str, entry) -> str:
    return hashlib.sha256((prev_hash + canonical_json(entry)).encode("utf-8")).hexdigest()


def verify_chain(entries: Iterable) -> int | None:
    """Return the id of the first broken entry, or None if the whole chain verifies. Entries must be in id order."""
    expected_prev = GENESIS
    for entry in entries:
        if entry.prev_hash != expected_prev or compute_hash(entry.prev_hash, entry) != entry.entry_hash:
            return entry.id
        expected_prev = entry.entry_hash
    return None
