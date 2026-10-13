"""Digital verification: the provider presents a wallet ID, Credence verifies it, we score it against the record.

Flows A/B (DC API): start -> browser calls navigator.credentials.get -> complete.
Flow C (QR / deep link): start -> browser shows a QR code -> poll status until the wallet answers.
Claims are never logged. The portrait is held only in the in-memory result, never in the audit log.
"""
import hmac
import threading
import time
import uuid
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import results
from app.config import settings
from app.credence import flows
from app.credence.client import CredenceError, get_client
from app.credence.parse import DigitalOutcome, _issuer, _normalize_claims
from app.db import get_session
from app.models import Provider, Visit
from app.routers.verify_manual import load_visit_and_provider, match_out, record_view
from app.routers.visits import provider_summary
from app.schemas import AuthenticityOut, OutcomeOut, VerificationResult
from app.scoring.engine import Presented, outcome_for, score_identity

router = APIRouter(prefix="/api/verify/digital", tags=["verify"])

SESSION_TTL_SECONDS = 600
_sessions: dict[str, tuple[float, str, int]] = {}  # credence session id -> (expires, flow, visit_id)
_lock = threading.Lock()


class StartRequest(BaseModel):
    visit_id: int
    flow: str = Field(pattern="^[ABC]$")


class StartResponse(BaseModel):
    session_id: str
    flow: str
    browser: dict
    expires_in: int


class CompleteRequest(BaseModel):
    session_id: str
    data: str = Field(min_length=1, max_length=200_000)


class StatusResponse(BaseModel):
    status: str  # pending / done
    result: VerificationResult | None = None


def _credence_failure(e: Exception) -> HTTPException:
    if isinstance(e, CredenceError):
        if e.code == "NOT_CONFIGURED":
            return HTTPException(503, detail={"code": "credence_not_configured", "message": e.message})
        return HTTPException(502, detail={"code": "credence_error", "message": f"Credence: {e.message} ({e.code})"})
    return HTTPException(502, detail={"code": "credence_unreachable", "message": "Could not reach Credence ID."})


def _remember(session_id: str, flow: str, visit_id: int) -> None:
    with _lock:
        now = time.monotonic()
        for key in [k for k, (exp, _, _) in _sessions.items() if exp < now]:
            del _sessions[key]
        _sessions[session_id] = (now + SESSION_TTL_SECONDS, flow, visit_id)


def _lookup(session_id: str) -> tuple[str, int]:
    with _lock:
        item = _sessions.get(session_id)
    if not item or item[0] < time.monotonic():
        raise HTTPException(404, detail={"code": "session_not_found",
                                         "message": "This verification session expired. Start again."})
    return item[1], item[2]


def _forget(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


def build_digital_result(visit: Visit, provider: Provider, flow: str, outcome: DigitalOutcome,
                         channel: str = "web") -> VerificationResult:
    presented = Presented(first_name=outcome.first_name, last_name=outcome.last_name, dob=outcome.dob)
    match = score_identity(presented, record_view(provider))
    authenticity = "verified" if outcome.status == "verified" else "failed"
    nothing_compared = match.provided_weight == 0
    label, color = outcome_for("digital", authenticity, match.band, nothing_compared=nothing_compared)
    result = VerificationResult(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        visit_id=visit.id,
        visit_type=visit.visit_type,
        provider=provider_summary(provider),
        mode="digital",
        channel=channel,
        flow=flow,
        authenticity=AuthenticityOut(status=authenticity, checks=outcome.checks, issuer=outcome.issuer),
        match=match_out(match),
        outcome=OutcomeOut(label=label, color=color),
        portrait_data_url=outcome.portrait_data_url,
        attributes=outcome.attributes,
        match_source="none" if nothing_compared else "wallet",
    )
    results.put(result)
    return result


def _finish(session_id: str, flow: str, visit_id: int, outcome: DigitalOutcome,
            session: Session) -> VerificationResult:
    _forget(session_id)
    if outcome.status == "cancelled":
        raise HTTPException(409, detail={"code": "wallet_cancelled",
                                         "message": outcome.message or "The provider cancelled in their wallet."})
    visit, provider = load_visit_and_provider(session, visit_id)
    return build_digital_result(visit, provider, flow, outcome)


@router.post("/start", response_model=StartResponse)
def start(body: StartRequest, session: Session = Depends(get_session)) -> StartResponse:
    load_visit_and_provider(session, body.visit_id)  # 404 early if the visit doesn't exist
    try:
        started = flows.start(get_client(), body.flow)
    except (CredenceError, httpx.HTTPError) as e:
        raise _credence_failure(e) from e
    _remember(started["session_id"], body.flow, body.visit_id)
    return StartResponse(session_id=started["session_id"], flow=body.flow, browser=started["browser"],
                         expires_in=SESSION_TTL_SECONDS)


@router.post("/complete", response_model=VerificationResult)
def complete(body: CompleteRequest, session: Session = Depends(get_session)) -> VerificationResult:
    flow, visit_id = _lookup(body.session_id)
    if flow not in ("A", "B"):
        raise HTTPException(400, detail={"code": "wrong_flow", "message": "This session is polled, not completed."})
    try:
        outcome = flows.complete(get_client(), flow, body.session_id, body.data)
    except (CredenceError, httpx.HTTPError) as e:
        raise _credence_failure(e) from e
    return _finish(body.session_id, flow, visit_id, outcome, session)


@router.get("/status/{session_id}", response_model=StatusResponse)
def status(session_id: str, session: Session = Depends(get_session)) -> StatusResponse:
    flow, visit_id = _lookup(session_id)
    if flow != "C":
        raise HTTPException(400, detail={"code": "wrong_flow", "message": "This session is completed, not polled."})
    try:
        outcome = flows.poll(get_client(), session_id)
    except (CredenceError, httpx.HTTPError) as e:
        raise _credence_failure(e) from e
    if outcome is None:
        return StatusResponse(status="pending")
    return StatusResponse(status="done", result=_finish(session_id, flow, visit_id, outcome, session))


class SupplementRequest(BaseModel):
    """Complete an age-check-profile result: the auditor confirms the photo and takes name/DOB from the physical ID."""

    result_id: str
    photo_checked: bool
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    dob: date


@router.post("/supplement", response_model=VerificationResult)
def supplement(body: SupplementRequest, session: Session = Depends(get_session)) -> VerificationResult:
    """Only for a verified credential that shared no name/DOB. Authenticity is carried over from Credence's check;
    the record match uses the ID's printed details and is labelled as such (match_source="id_details")."""
    original = results.get(body.result_id)
    if original is None:
        raise HTTPException(404, detail={"code": "result_not_found",
                                         "message": "Result not found or expired. Run the verification again."})
    if not (original.mode == "digital" and original.authenticity.status == "verified"
            and original.match_source == "none"):
        raise HTTPException(409, detail={"code": "not_supplementable",
                                         "message": "Only a verified mobile ID that shared no name or DOB can be "
                                                    "completed with details from the ID."})
    if not body.photo_checked:
        raise HTTPException(422, detail={"code": "photo_check_required",
                                         "message": "Confirm the photo from the credential matches the person "
                                                    "present."})
    visit, provider = load_visit_and_provider(session, original.visit_id)
    match = score_identity(Presented(first_name=body.first_name, last_name=body.last_name, dob=body.dob),
                           record_view(provider))
    label, color = outcome_for("digital", "verified", match.band, match_source="id_details")
    result = original.model_copy(update={
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc),
        "match": match_out(match),
        "outcome": OutcomeOut(label=label, color=color),
        "photo_checked": True,
        "match_source": "id_details",
        "supplements": original.id,
        "saved": False,
    })
    results.put(result)
    return result


# --- Android reader (Tap2iD SDK, in person). See docs/android/CONTEXT.md §7-8. ----------------------------------

MDL_DOC_TYPE = "org.iso.18013.5.1.mDL"


class Tap2iDDocument(BaseModel):
    """One document from Tap2iD's VerificationResult, flattened by the app. Raw SDK facts; the server decides."""

    doc_type: str = Field(max_length=200)
    issuer_signed_valid: bool
    device_signed_valid: bool
    digests_valid: bool
    issuer_trusted: bool
    chain_status: str = Field(max_length=20)  # VERIFIED / EXPIRED / UNTRUSTED
    mso_status: str = Field(max_length=20)  # VALID / NOT_YET_VALID / EXPIRED / UNKNOWN
    issuer_dn: str | None = Field(default=None, max_length=500)
    validation_errors: list[str] = Field(default_factory=list, max_length=50)
    namespaces: dict[str, dict] = Field(default_factory=dict)


class Tap2iDRequest(BaseModel):
    visit_id: int
    sdk_version: str | None = Field(default=None, max_length=40)
    status: str = Field(max_length=20)  # SUCCESS / PARTIAL_SUCCESS / FAILURE
    documents: list[Tap2iDDocument] = Field(default_factory=list, max_length=5)


def require_device_token(x_device_token: str | None = Header(default=None)) -> None:
    """Prototype device auth: a shared secret. Production would use Play Integrity attestation or mTLS."""
    if not settings.android_device_token:
        raise HTTPException(503, detail={"code": "android_not_configured",
                                         "message": "The server has no Android device token configured."})
    if not x_device_token or not hmac.compare_digest(x_device_token, settings.android_device_token):
        raise HTTPException(401, detail={"code": "bad_device_token", "message": "Unknown device."})


def tap2id_checks(doc: Tap2iDDocument) -> dict[str, bool]:
    return {
        "issuerSignedValid": doc.issuer_signed_valid,
        "deviceSignedValid": doc.device_signed_valid,
        "digestsValid": doc.digests_valid,
        "issuerTrusted": doc.issuer_trusted,
        "chainVerified": doc.chain_status.upper() == "VERIFIED",
        "msoValid": doc.mso_status.upper() == "VALID",
        "noValidationErrors": not doc.validation_errors,
    }


def tap2id_outcome(body: Tap2iDRequest) -> DigitalOutcome:
    """Authenticity is recomputed here from the individual checks, never taken from a single flag sent by the app."""
    if not body.documents:
        return DigitalOutcome("failed", message="The reader returned no document.")
    doc = next((d for d in body.documents if d.doc_type == MDL_DOC_TYPE), body.documents[0])
    checks = tap2id_checks(doc)
    claims = _normalize_claims(doc.namespaces)
    ok = body.status.upper() == "SUCCESS" and all(checks.values())
    return DigitalOutcome("verified" if ok else "failed", claims, checks, _issuer(claims) or doc.issuer_dn,
                          None if ok else "The credential did not pass the in-person check.")


@router.post("/tap2id", response_model=VerificationResult, dependencies=[Depends(require_device_token)])
def tap2id(body: Tap2iDRequest, session: Session = Depends(get_session)) -> VerificationResult:
    visit, provider = load_visit_and_provider(session, body.visit_id)
    return build_digital_result(visit, provider, "tap2id", tap2id_outcome(body), channel="android")


# --- Android: second read for name/DOB (open-source Multipaz reader). See docs/android/CONTEXT.md §12. -------------

class SecondReadRequest(BaseModel):
    """Name/DOB fetched by a second, separate ISO 18013-5 read after the Tap2iD read. Raw facts; the server decides."""

    result_id: str
    reader: str = Field(default="multipaz", max_length=40)
    doc_type: str = Field(max_length=200)
    issuer_signed_valid: bool
    device_signed_valid: bool
    digests_valid: bool
    valid_now: bool
    issuer_dn: str | None = Field(default=None, max_length=500)
    issuing_authority: str | None = Field(default=None, max_length=200)
    given_name: str | None = Field(default=None, max_length=80)
    family_name: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None


@router.post("/second-read", response_model=VerificationResult, dependencies=[Depends(require_device_token)])
def second_read(body: SecondReadRequest, session: Session = Depends(get_session)) -> VerificationResult:
    """Attach name/DOB from a second read to a Tap2iD result that shared none (age-check profile).

    Authenticity stays exactly what the Tap2iD read said. The second read's own integrity checks must all pass, and
    it must come from the same issuer as the first read (a weak link between the two reads; see CONTEXT.md §12).
    """
    original = results.get(body.result_id)
    if original is None:
        raise HTTPException(404, detail={"code": "result_not_found",
                                         "message": "Result not found or expired. Run the verification again."})
    if not (original.mode == "digital" and original.flow == "tap2id" and original.match_source == "none"):
        raise HTTPException(409, detail={"code": "not_supplementable",
                                         "message": "Only an in-person mobile ID read that shared no name or DOB "
                                                    "can be completed with a second read."})
    checks = {"issuerSignedValid": body.issuer_signed_valid, "deviceSignedValid": body.device_signed_valid,
              "digestsValid": body.digests_valid, "validNow": body.valid_now}
    if not all(checks.values()):
        failed = ", ".join(k for k, v in checks.items() if not v)
        raise HTTPException(422, detail={"code": "second_read_failed_checks",
                                         "message": f"The second read failed its own checks ({failed}); its details "
                                                    "were not used."})
    if body.doc_type != MDL_DOC_TYPE:
        raise HTTPException(422, detail={"code": "second_read_wrong_doc",
                                         "message": "The second read returned a different kind of document."})
    first_issuer = (original.authenticity.issuer or "").strip().lower()
    second_issuer = (body.issuing_authority or "").strip().lower()
    if first_issuer and second_issuer and first_issuer != second_issuer:
        raise HTTPException(409, detail={"code": "second_read_different_issuer",
                                         "message": "The second read came from a different issuer than the first "
                                                    "read. It may be a different ID; start again."})
    if not (body.family_name and body.birth_date):
        raise HTTPException(422, detail={"code": "second_read_no_details",
                                         "message": "The wallet didn't share a last name and date of birth in the "
                                                    "second read."})
    visit, provider = load_visit_and_provider(session, original.visit_id)
    match = score_identity(Presented(first_name=body.given_name, last_name=body.family_name, dob=body.birth_date),
                           record_view(provider))
    label, color = outcome_for("digital", original.authenticity.status, match.band, match_source="second_read")
    result = original.model_copy(update={
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc),
        "match": match_out(match),
        "outcome": OutcomeOut(label=label, color=color),
        "match_source": "second_read",
        "supplements": original.id,
        "saved": False,
    })
    results.put(result)
    return result
