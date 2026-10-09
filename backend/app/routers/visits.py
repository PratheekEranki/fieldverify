"""Today's site visits."""
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Provider, Visit
from app.schemas import ProviderSummary, UnscheduledVisitRequest, VisitOut

router = APIRouter(prefix="/api/visits", tags=["visits"])


def provider_summary(p: Provider) -> ProviderSummary:
    return ProviderSummary(id=p.id, name=f"{p.first_name} {p.last_name}", npi=p.npi, specialty=p.specialty,
                           risk_level=p.risk_level)


def visit_out(v: Visit, p: Provider) -> VisitOut:
    return VisitOut(id=v.id, scheduled_at=v.scheduled_at, site_address=v.site_address, status=v.status,
                    visit_type=v.visit_type, provider=provider_summary(p))


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


@router.post("/unscheduled", response_model=VisitOut, status_code=201)
def create_unscheduled_visit(body: UnscheduledVisitRequest, session: Session = Depends(get_session)) -> VisitOut:
    """Start a visit that wasn't on today's schedule (unannounced visit, or a different provider found on site)."""
    provider = session.get(Provider, body.provider_id)
    if not provider:
        raise HTTPException(404, detail={"code": "provider_not_found", "message": "No enrolled provider with that id"})
    visit = Visit(
        provider_id=provider.id,
        scheduled_at=datetime.now().replace(second=0, microsecond=0),
        site_address=f"{provider.street}, {provider.city}, {provider.state} {provider.zip5}",
        visit_type="unscheduled",
    )
    session.add(visit)
    session.commit()
    session.refresh(visit)
    return visit_out(visit, provider)
