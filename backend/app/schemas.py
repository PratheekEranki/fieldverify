"""API request/response models. Front ends (web + Android) mirror these shapes."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class ProviderSummary(BaseModel):
    """What front ends may see about a provider. Never includes DOB or SSN."""

    id: int
    name: str
    npi: str
    specialty: str
    risk_level: str


class VisitOut(BaseModel):
    id: int
    scheduled_at: datetime
    site_address: str
    status: str
    provider: ProviderSummary


class ManualVerifyRequest(BaseModel):
    visit_id: int
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    dob: date
    ssn: str | None = Field(default=None, max_length=11)
    street: str | None = Field(default=None, max_length=200)
    zip5: str | None = Field(default=None, max_length=10)
    photo_checked: bool


class FieldResultOut(BaseModel):
    field: str
    result: str
    points: float
    max: int
    reason: str


class AuthenticityOut(BaseModel):
    status: str  # verified / failed / not_checked
    checks: dict[str, bool] = {}
    issuer: str | None = None


class MatchOut(BaseModel):
    score: int
    band: str
    insufficient_data: bool
    provided_weight: int
    hard_rule: str | None
    caps: list[str]
    fields: list[FieldResultOut]


class OutcomeOut(BaseModel):
    label: str
    color: str


class VerificationResult(BaseModel):
    id: str
    created_at: datetime
    visit_id: int
    provider: ProviderSummary
    mode: str  # digital / manual
    channel: str  # web / android
    flow: str | None = None
    authenticity: AuthenticityOut
    match: MatchOut
    outcome: OutcomeOut
    photo_checked: bool | None = None
    presented_ssn_masked: str | None = None  # e.g. ***-**-1234; never the full number
    saved: bool = False
