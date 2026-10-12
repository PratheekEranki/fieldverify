"""Demo-only reset: wipe the audit log and re-seed today's visits before recording a demo.

Disabled (404) unless DEMO_RESET_TOKEN is set, and requires that token in the X-Demo-Reset-Token header.
A real deployment would not ship this route; the audit log is otherwise append-only.
"""
import hmac

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.seed import seed

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
def reset(x_demo_reset_token: str | None = Header(default=None)) -> dict:
    if not settings.demo_reset_token:
        raise HTTPException(404, detail={"code": "not_found", "message": "Not found"})
    if not x_demo_reset_token or not hmac.compare_digest(x_demo_reset_token, settings.demo_reset_token):
        raise HTTPException(403, detail={"code": "forbidden", "message": "Wrong or missing reset token."})
    return seed()
