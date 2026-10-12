"""App settings, read from the repo-root .env (locally) or environment variables (Render)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Credence Cloud SDK (backend-only; never sent to the browser)
    credence_license_key: str = ""
    credence_profile_id: str = ""
    credence_base_url: str = "https://credenceid.com/cloudsdk/playground"
    credence_origin: str = ""

    # App
    database_url: str = f"sqlite:///{(REPO_ROOT / 'backend' / 'fieldverify.db').as_posix()}"
    demo_auditor_name: str = "Demo Auditor"
    result_ttl_seconds: int = 900
    serve_frontend: bool = False

    # Android reader shared secret (X-Device-Token)
    android_device_token: str = ""

    # Demo reset (POST /api/demo/reset). Disabled unless set. Clears the audit log and re-seeds today's visits.
    demo_reset_token: str = ""

    # Demo provider (the candidate's own wallet identity; seeded locally only)
    demo_provider_first: str = ""
    demo_provider_last: str = ""
    demo_provider_dob: str = ""


settings = Settings()
