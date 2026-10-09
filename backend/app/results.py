"""Server-side holding area for verification results between "verify" and "save to audit log".

Results live here (in memory, with a TTL) so the client can only save a result by id and can't alter the score
before it's logged. Nothing sensitive is kept beyond the response shape (no raw SSN or DOB).
"""
import threading
import time

from app.config import settings
from app.schemas import VerificationResult

_lock = threading.Lock()
_store: dict[str, tuple[float, VerificationResult]] = {}


def put(result: VerificationResult) -> None:
    with _lock:
        _purge_expired()
        _store[result.id] = (time.monotonic() + settings.result_ttl_seconds, result)


def get(result_id: str) -> VerificationResult | None:
    with _lock:
        _purge_expired()
        item = _store.get(result_id)
        return item[1] if item else None


def mark_saved(result_id: str) -> None:
    with _lock:
        item = _store.get(result_id)
        if item:
            item[1].saved = True


def _purge_expired() -> None:
    now = time.monotonic()
    for key in [k for k, (exp, _) in _store.items() if exp < now]:
        del _store[key]
