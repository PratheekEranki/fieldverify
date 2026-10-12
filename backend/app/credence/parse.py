"""Turn Credence verification responses into one shape the rest of the app understands.

Response shapes (docs, Oct 2026; confirm against real fixtures as they're captured):
- Flow A verifyDocRequest: {"res": bool, "resDetails": "<JSON string of flat claims>"}
- Flow B validate:         {"res": bool, "resDetails": "<JSON string {identity: {...}, authentication: {...}}>"}
                           or {"cancelled": true, "message": "..."}
- Flow C mdoc/result:      {"success": bool, "identity": "<JSON string of flat claims>" | null, "error": str | null}
Claims may use ISO mDL names (given_name, family_name, birth_date) or AAMVA PDF417 element ids (DAC, DCS, DBB).
"""
import json
import re
from dataclasses import dataclass, field
from datetime import date

# AAMVA PDF417 element ids (DL/ID card design standard) -> ISO mDL claim names.
AAMVA_TO_ISO = {"DCS": "family_name", "DAC": "given_name", "DBB": "birth_date", "DAJ": "issuing_jurisdiction"}
ISSUER_KEYS = ("issuing_authority", "issuing_jurisdiction", "issuer", "issuing_country")


@dataclass
class DigitalOutcome:
    status: str  # verified / failed / cancelled / error
    claims: dict = field(default_factory=dict)  # normalized ISO names; never logged
    checks: dict[str, bool] = field(default_factory=dict)
    issuer: str | None = None
    message: str | None = None

    @property
    def attributes(self) -> dict[str, bool]:
        """Non-identifying attestations the wallet shared, e.g. {"age_over_21": True} from an age-check profile."""
        return {k: v for k, v in self.claims.items() if isinstance(v, bool) and re.fullmatch(r"age_over_\d{2}", k)}

    @property
    def first_name(self) -> str | None:
        return self.claims.get("given_name")

    @property
    def last_name(self) -> str | None:
        return self.claims.get("family_name")

    @property
    def dob(self) -> date | None:
        return parse_birth_date(self.claims.get("birth_date"))

    @property
    def portrait_data_url(self) -> str | None:
        p = self.claims.get("portrait")
        if not isinstance(p, str) or not p:
            return None
        if p.startswith("data:"):
            return p
        # mDL portraits are JPEG; base64 JPEG starts with "/9j/".
        return f"data:image/jpeg;base64,{p}" if re.fullmatch(r"[A-Za-z0-9+/=\s]+", p[:200]) else None


def parse_birth_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", v):
            return date.fromisoformat(v[:10])
        if re.fullmatch(r"\d{8}", v):  # AAMVA US format MMDDCCYY
            return date(int(v[4:8]), int(v[0:2]), int(v[2:4]))
    except ValueError:
        return None
    return None


def _loads(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _normalize_claims(raw: dict) -> dict:
    """Flatten namespaces ({"org.iso.18013.5.1": {...}}) and map AAMVA ids to ISO names."""
    flat: dict = {}
    for key, value in raw.items():
        if isinstance(value, dict) and ("." in key or key in ("identity", "claims")):
            flat.update(_normalize_claims(value))
        else:
            flat[AAMVA_TO_ISO.get(key, key)] = value
    return flat


def _issuer(claims: dict) -> str | None:
    for key in ISSUER_KEYS:
        if isinstance(claims.get(key), str) and claims[key]:
            return claims[key]
    return None


def _bool_checks(auth: dict) -> dict[str, bool]:
    return {k: v for k, v in auth.items() if isinstance(v, bool)}


def parse_res_response(body: dict) -> DigitalOutcome:
    """Flows A and B."""
    if body.get("cancelled"):
        return DigitalOutcome("cancelled", message=body.get("message") or "Cancelled in the wallet.")
    details = _loads(body.get("resDetails"))
    identity = details.get("identity") if isinstance(details.get("identity"), dict) else details
    auth = details.get("authentication") if isinstance(details.get("authentication"), dict) else {}
    claims = _normalize_claims({k: v for k, v in identity.items() if k != "authentication"})
    checks = _bool_checks(auth)
    ok = body.get("res") is True and all(checks.values())
    return DigitalOutcome("verified" if ok else "failed", claims, checks, _issuer(claims),
                          None if ok else "The credential did not pass Credence verification.")


def parse_mdoc_result(body: dict) -> DigitalOutcome:
    """Flow C (already past the 202 'pending' stage)."""
    if body.get("success") is True:
        claims = _normalize_claims(_loads(body.get("identity")))
        return DigitalOutcome("verified", claims, {}, _issuer(claims))
    message = body.get("error") or "The wallet did not complete the presentation."
    status = "cancelled" if "denied" in message.lower() or "cancel" in message.lower() else "failed"
    return DigitalOutcome(status, message=message)
