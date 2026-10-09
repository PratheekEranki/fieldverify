"""FieldVerify API entry point."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import REPO_ROOT, settings

app = FastAPI(title="FieldVerify API", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        # Reports whether keys are configured, never the keys themselves.
        "credence_configured": bool(settings.credence_license_key and settings.credence_profile_id),
    }


# Demo/production mode: serve the built web app from the same origin as the API,
# so the page origin matches the domain registered with Credence.
DIST = REPO_ROOT / "frontend" / "dist"
if settings.serve_frontend and DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(Path(DIST / "index.html"))
