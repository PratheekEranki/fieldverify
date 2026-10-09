"""Audit log: append-only. There are deliberately no update or delete routes."""
import csv
import io
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import results
from app.audit.chain import GENESIS, compute_hash, verify_chain
from app.config import settings
from app.db import get_session
from app.models import AuditEntry, Provider

router = APIRouter(prefix="/api/audit", tags=["audit"])
_append_lock = threading.Lock()  # one writer at a time, so two saves can't link to the same prev_hash


class SaveRequest(BaseModel):
    result_id: str
    notes: str = Field(default="", max_length=2000)


class AuditEntryOut(BaseModel):
    id: int
    created_at: datetime
    auditor: str
    visit_id: int
    provider_name: str
    provider_npi: str
    mode: str
    channel: str
    flow: str | None
    authenticity: str
    auth_checks: dict
    issuer: str | None
    score: int | None
    band: str
    outcome: str
    field_results: list
    photo_checked: bool | None
    notes: str
    entry_hash: str


def _out(e: AuditEntry, p: Provider) -> AuditEntryOut:
    return AuditEntryOut(
        id=e.id, created_at=e.created_at, auditor=e.auditor, visit_id=e.visit_id,
        provider_name=f"{p.first_name} {p.last_name}", provider_npi=p.npi, mode=e.mode, channel=e.channel,
        flow=e.flow, authenticity=e.authenticity, auth_checks=e.auth_checks or {}, issuer=e.issuer, score=e.score,
        band=e.band, outcome=e.outcome, field_results=e.field_results or [], photo_checked=e.photo_checked,
        notes=e.notes, entry_hash=e.entry_hash,
    )


@router.post("", response_model=AuditEntryOut, status_code=201)
def save(body: SaveRequest, session: Session = Depends(get_session)) -> AuditEntryOut:
    result = results.get(body.result_id)
    if result is None:
        raise HTTPException(404, detail={"code": "result_not_found",
                                         "message": "Result not found or expired. Run the verification again."})
    if result.saved:
        raise HTTPException(409, detail={"code": "already_saved", "message": "This result is already in the log."})

    with _append_lock:
        last = session.exec(select(AuditEntry).order_by(AuditEntry.id.desc())).first()
        entry = AuditEntry(
            created_at=datetime.now(timezone.utc),
            auditor=settings.demo_auditor_name,
            visit_id=result.visit_id,
            provider_id=result.provider.id,
            mode=result.mode,
            channel=result.channel,
            flow=result.flow,
            authenticity=result.authenticity.status,
            auth_checks=result.authenticity.checks,
            issuer=result.authenticity.issuer,
            score=result.match.score,
            band=result.match.band,
            outcome=result.outcome.label,
            # Per-field outcomes only: field name, result, points, reason. No presented values.
            field_results=[f.model_dump() for f in result.match.fields],
            photo_checked=result.photo_checked,
            notes=body.notes.strip(),
            prev_hash=last.entry_hash if last else GENESIS,
            entry_hash="",
        )
        entry.entry_hash = compute_hash(entry.prev_hash, entry)
        session.add(entry)
        session.commit()
        session.refresh(entry)
        results.mark_saved(body.result_id)

    return _out(entry, session.get(Provider, entry.provider_id))


def _query(session: Session, mode: str | None, band: str | None):
    stmt = select(AuditEntry, Provider).join(Provider, Provider.id == AuditEntry.provider_id)
    if mode:
        stmt = stmt.where(AuditEntry.mode == mode)
    if band:
        stmt = stmt.where(AuditEntry.band == band)
    return session.exec(stmt.order_by(AuditEntry.id.desc())).all()


@router.get("", response_model=list[AuditEntryOut])
def list_entries(mode: str | None = None, band: str | None = None,
                 session: Session = Depends(get_session)) -> list[AuditEntryOut]:
    return [_out(e, p) for e, p in _query(session, mode, band)]


CSV_COLUMNS = ["id", "created_at_utc", "auditor", "visit_id", "provider_name", "provider_npi", "mode", "channel",
               "flow", "authenticity", "issuer", "score", "band", "outcome", "field_results", "photo_checked",
               "notes", "entry_hash"]


@router.get("/export.csv")
def export_csv(mode: str | None = None, band: str | None = None,
               session: Session = Depends(get_session)) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for e, p in _query(session, mode, band):
        o = _out(e, p)
        writer.writerow([
            o.id, o.created_at.isoformat(), o.auditor, o.visit_id, o.provider_name, o.provider_npi, o.mode,
            o.channel, o.flow or "", o.authenticity, o.issuer or "", o.score if o.score is not None else "", o.band,
            o.outcome, "; ".join(f"{f['field']}={f['result']}" for f in o.field_results),
            "" if o.photo_checked is None else ("yes" if o.photo_checked else "no"), o.notes, o.entry_hash,
        ])
    # utf-8-sig adds a BOM so Excel opens the file with the right encoding.
    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(iter([data]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=fieldverify-audit-log.csv"})


@router.get("/verify-chain")
def verify(session: Session = Depends(get_session)) -> dict:
    entries = session.exec(select(AuditEntry).order_by(AuditEntry.id)).all()
    first_bad = verify_chain(entries)
    return {"ok": first_bad is None, "entries": len(entries), "first_bad_id": first_bad}
