"""Enrolled-provider lookup for unscheduled visits.

Searches ONLY public directory fields: NPI and provider name. It never searches or returns date of birth or SSN, so
it can't be used to find "whoever matches these personal details". Verification stays 1:1 against the chosen record.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.db import get_session
from app.models import Provider
from app.routers.visits import provider_summary
from app.schemas import ProviderSearchHit

router = APIRouter(prefix="/api/providers", tags=["providers"])

MAX_RESULTS = 10
MIN_NAME_CHARS = 2
MIN_NPI_DIGITS = 4


@router.get("/search", response_model=list[ProviderSearchHit])
def search(q: str = Query(..., max_length=80), session: Session = Depends(get_session)) -> list[ProviderSearchHit]:
    query = q.strip()
    digits = query.replace(" ", "").replace("-", "")

    if digits.isdigit():
        # Digits only: treat as an NPI prefix. A 9-digit SSN-shaped query can only ever hit NPIs, never SSNs.
        if len(digits) < MIN_NPI_DIGITS:
            raise HTTPException(422, detail={"code": "query_too_short",
                                             "message": f"Enter at least {MIN_NPI_DIGITS} digits of the NPI."})
        stmt = select(Provider).where(Provider.npi.startswith(digits))
    else:
        if len(query) < MIN_NAME_CHARS:
            raise HTTPException(422, detail={"code": "query_too_short",
                                             "message": f"Enter at least {MIN_NAME_CHARS} letters of the name."})
        if any(ch.isdigit() for ch in query):
            raise HTTPException(422, detail={"code": "invalid_query",
                                             "message": "Search by provider name or NPI only."})
        # Every word must appear in the first or last name ("rob kow" finds Robert Kowalski).
        conditions = []
        for word in query.lower().split():
            pattern = f"%{word}%"
            conditions.append(or_(func.lower(Provider.first_name).like(pattern),
                                  func.lower(Provider.last_name).like(pattern)))
        stmt = select(Provider).where(*conditions)

    providers = session.exec(stmt.order_by(Provider.last_name, Provider.first_name).limit(MAX_RESULTS)).all()
    return [
        ProviderSearchHit(provider=provider_summary(p),
                          practice_address=f"{p.street}, {p.city}, {p.state} {p.zip5}")
        for p in providers
    ]
