"""Today's site visits."""
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Provider, Visit
from app.schemas import ProviderSummary, VisitOut

router = APIRouter(prefix="/api/visits", tags=["visits"])


def provider_summary(p: Provider) -> ProviderSummary:
    return ProviderSummary(id=p.id, name=f"{p.first_name} {p.last_name}", npi=p.npi, specialty=p.specialty,
                           risk_level=p.risk_level)


def visit_out(v: Visit, p: Provider) -> VisitOut:
    return VisitOut(id=v.id, scheduled_at=v.scheduled_at, site_address=v.site_address, status=v.status,
                    provider=provider_summary(p))


@router.get("", response_model=list[VisitOut])
def list_visits(day: date | None = None, session: Session = Depends(get_session)) -> list[VisitOut]:
    day = day or date.today()
    start, end = datetime.combine(day, time.min), datetime.combine(day, time.max)
    rows = session.exec(
        select(Visit, Provider)
        .join(Provider, Provider.id == Visit.provider_id)
        .where(Visit.scheduled_at >= start, Visit.scheduled_at <= end)
        .order_by(Visit.scheduled_at)
    ).all()
    return [visit_out(v, p) for v, p in rows]


@router.get("/{visit_id}", response_model=VisitOut)
def get_visit(visit_id: int, session: Session = Depends(get_session)) -> VisitOut:
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, detail={"code": "visit_not_found", "message": f"No visit with id {visit_id}"})
    return visit_out(visit, session.get(Provider, visit.provider_id))
