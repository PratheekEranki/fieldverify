"""Database tables. See docs/architecture.md §3.

Provider stands in for the state Medicaid enrollment record. All seed data is synthetic (ADR-0004).
"""
from datetime import date, datetime, timezone

from pydantic import NaiveDatetime
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Provider(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    npi: str = Field(index=True, max_length=10)
    first_name: str
    last_name: str
    aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON))  # maiden / former last names
    dob: date
    ssn: str = Field(max_length=9)  # synthetic, 9xx range; never returned by any API
    street: str
    city: str
    state: str = Field(max_length=2)
    zip5: str = Field(max_length=5)
    specialty: str
    risk_level: str  # limited / moderate / high (CMS screening levels)


class Visit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    provider_id: int = Field(foreign_key="provider.id", index=True)
    scheduled_at: NaiveDatetime  # local wall-clock schedule time, deliberately timezone-free
    site_address: str
    status: str = "scheduled"  # scheduled / completed
    visit_type: str = "scheduled"  # scheduled / unscheduled (auditor looked the provider up on site)


class AuditEntry(SQLModel, table=True):
    """Append-only. No API route updates or deletes rows. Never holds raw SSN, DOB, or portrait."""

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    auditor: str
    visit_id: int = Field(foreign_key="visit.id")
    provider_id: int = Field(foreign_key="provider.id")
    visit_type: str = "scheduled"  # scheduled / unscheduled
    match_source: str = "none"  # wallet / id_details / manual / none
    mode: str  # digital / manual
    channel: str  # web / android
    flow: str | None = None  # A/B/C/D or tap2id
    authenticity: str  # verified / failed / not_checked
    auth_checks: dict = Field(default_factory=dict, sa_column=Column(JSON))
    issuer: str | None = None
    score: int | None = None
    band: str  # green / yellow / red
    outcome: str
    field_results: list = Field(default_factory=list, sa_column=Column(JSON))
    photo_checked: bool | None = None
    notes: str = ""
    prev_hash: str = Field(max_length=64)
    entry_hash: str = Field(max_length=64, index=True)
