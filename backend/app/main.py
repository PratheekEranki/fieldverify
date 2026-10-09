"""FieldVerify API entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import REPO_ROOT, settings
from app.credence.client import get_client
from app.db import init_db
from app.routers import audit, providers, verify_digital, verify_manual, visits
from app.seed import ensure_seeded


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_seeded()  # Render's free disk is wiped on each deploy, so seed if empty
    yield


app = FastAPI(title="FieldVerify API", version="0.2.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse({"error": detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 body echoes the submitted value, which could be an SSN. Report field + reason only.
    problems = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse({"error": {"code": "invalid_request", "message": "Invalid request", "fields": problems}},
                        status_code=422)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        # Reports whether keys are configured, never the keys themselves.
        "credence_configured": bool(settings.credence_license_key and settings.credence_profile_id),
    }


@app.get("/api/credence/status")
def credence_status() -> dict:
    """Can the server get a Credence session right now? Uses the cached token, so it's cheap."""
    return get_client().status()


app.include_router(visits.router)
app.include_router(providers.router)
app.include_router(verify_manual.router)
app.include_router(verify_digital.router)
app.include_router(audit.router)

# Demo/production mode: serve the built web app from the same origin as the API,
# so the page origin matches the domain registered with Credence.
DIST = REPO_ROOT / "frontend" / "dist"
if settings.serve_frontend and DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = DIST / full_path
        if full_path and not full_path.startswith("api/") and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(Path(DIST / "index.html"))
