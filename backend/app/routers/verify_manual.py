"""Manual fallback verification: typed details from a physical ID, matched against the enrollment record."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app import results
from app.db import get_session
from app.models import Provider, Visit
from app.routers.visits import provider_summary
from app.schemas import (
    AuthenticityOut,
    FieldResultOut,
    ManualVerifyRequest,
    MatchOut,
    OutcomeOut,
    VerificationResult,
)
from app.scoring.engine import MatchResult, Presented, RecordView, outcome_for, score_identity
from app.scoring.normalize import digits_only

router = APIRouter(prefix="/api/verify", tags=["verify"])


def record_view(p: Provider) -> RecordView:
    return RecordView(first_name=p.first_name, last_name=p.last_name, aliases=p.aliases or [], dob=p.dob,
                      ssn=p.ssn, street=p.street, zip5=p.zip5)


def match_out(m: MatchResult) -> MatchOut:
    return MatchOut(score=m.score, band=m.band, insufficient_data=m.insufficient_data,
                    provided_weight=m.provided_weight, hard_rule=m.hard_rule, caps=m.caps,
                    fields=[FieldResultOut(**f.to_dict()) for f in m.fields])


def mask_ssn(ssn: str | None) -> str | None:
    d = digits_only(ssn)
    return f"***-**-{d[-4:]}" if len(d) >= 4 else None


def load_visit_and_provider(session: Session, visit_id: int) -> tuple[Visit, Provider]:
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, detail={"code": "visit_not_found", "message": f"No visit with id {visit_id}"})
    return visit, session.get(Provider, visit.provider_id)


@router.post("/manual", response_model=VerificationResult)
def verify_manual(body: ManualVerifyRequest, session: Session = Depends(get_session)) -> VerificationResult:
    if not body.photo_checked:
        raise HTTPException(
            422,
            detail={"code": "photo_check_required",
                    "message": "Confirm you compared the photo on the physical ID to the person present."},
        )
    visit, provider = load_visit_and_provider(session, body.visit_id)
    presented = Presented(first_name=body.first_name, last_name=body.last_name, dob=body.dob, ssn=body.ssn,
                          street=body.street, zip5=body.zip5)
    match = score_identity(presented, record_view(provider))
    label, color = outcome_for("manual", "not_checked", match.band)

    result = VerificationResult(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        visit_id=visit.id,
        visit_type=visit.visit_type,
        provider=provider_summary(provider),
        mode="manual",
        channel="web",
        authenticity=AuthenticityOut(status="not_checked"),
        match=match_out(match),
        outcome=OutcomeOut(label=label, color=color),
        photo_checked=True,
        presented_ssn_masked=mask_ssn(body.ssn),
    )
    results.put(result)
    return result


@router.get("/results/{result_id}", response_model=VerificationResult)
def get_result(result_id: str) -> VerificationResult:
    """Fetch a not-yet-expired result (lets the result page survive a browser refresh)."""
    result = results.get(result_id)
    if result is None:
        raise HTTPException(404, detail={"code": "result_not_found",
                                         "message": "Result not found or expired. Run the verification again."})
    return result
