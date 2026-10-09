"""Credence ID Cloud SDK client: authentication, token lifecycle, and authenticated calls.

Confirmed behavior (docs + live check, Oct 9 2026):
- POST /v1/setup {licenseKey, profileId} with an Origin header equal to the registered domain
  -> {accessToken, refreshToken, expiresIn (900 s), tokenType, customerName, profileName}
- POST /v1/refresh {refreshToken} -> new accessToken + rotated refreshToken (refresh token lives 7 days)
- Every other call: Authorization: Bearer <accessToken>
The license key never leaves the backend.
"""
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

REFRESH_MARGIN_SECONDS = 60
TOKEN_ERRORS = {"TOKEN_EXPIRED", "INVALID_TOKEN", "MISSING_TOKEN"}


class CredenceError(Exception):
    """A failed Credence call, with Credence's error code when it gave one."""

    def __init__(self, code: str, message: str, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class _Tokens:
    access: str
    refresh: str
    expires_at: float  # monotonic clock
    profile_name: str | None = None


def _error_from(res: httpx.Response) -> CredenceError:
    try:
        body = res.json()
    except ValueError:
        body = {}
    raw = body.get("error") if isinstance(body, dict) else None
    # Credence returns either {"error": "CODE", "message": "..."} or {"error": "<message>"}.
    if isinstance(raw, str) and raw.isupper() and " " not in raw:
        code, message = raw, body.get("message") or raw
    else:
        code, message = f"HTTP_{res.status_code}", (raw or res.text[:200] or f"HTTP {res.status_code}")
    return CredenceError(code, message, res.status_code)


class CredenceClient:
    def __init__(
        self,
        base_url: str,
        license_key: str,
        profile_id: str,
        origin: str,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = 20.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._license_key = license_key
        self._profile_id = profile_id
        self.origin = origin
        self._clock = clock
        self._lock = threading.Lock()
        self._tokens: _Tokens | None = None
        self._http = httpx.Client(base_url=self.base_url, transport=transport, timeout=timeout)

    @property
    def configured(self) -> bool:
        return bool(self._license_key and self._profile_id and self.origin)

    @property
    def profile_name(self) -> str | None:
        return self._tokens.profile_name if self._tokens else None

    # ---------- token lifecycle ----------

    def _store(self, body: dict, profile_name: str | None) -> None:
        self._tokens = _Tokens(
            access=body["accessToken"],
            refresh=body["refreshToken"],
            expires_at=self._clock() + int(body.get("expiresIn", 900)),
            profile_name=body.get("profileName") or profile_name,
        )

    def _setup(self) -> None:
        if not self.configured:
            raise CredenceError("NOT_CONFIGURED", "Credence Cloud SDK keys are not configured on this server.")
        res = self._http.post(
            "/v1/setup",
            json={"licenseKey": self._license_key, "profileId": self._profile_id},
            headers={"Origin": self.origin},
        )
        if res.status_code != 200:
            raise _error_from(res)
        self._store(res.json(), None)

    def _refresh(self) -> None:
        assert self._tokens is not None
        res = self._http.post("/v1/refresh", json={"refreshToken": self._tokens.refresh})
        if res.status_code != 200:
            raise _error_from(res)
        self._store(res.json(), self._tokens.profile_name)

    def access_token(self) -> str:
        """A valid access token: cached, refreshed when < 60 s remain, or a fresh setup if refresh fails."""
        with self._lock:
            if self._tokens is None:
                self._setup()
            elif self._tokens.expires_at - self._clock() < REFRESH_MARGIN_SECONDS:
                try:
                    self._refresh()
                except CredenceError:
                    self._tokens = None
                    self._setup()
            return self._tokens.access

    def invalidate(self) -> None:
        with self._lock:
            self._tokens = None

    # ---------- authenticated calls ----------

    def post(self, path: str, json: dict | None = None) -> httpx.Response:
        """Authenticated POST. Retries once with a fresh session if Credence says the token is bad.

        Returns the raw response (callers handle 200 / 201 / 202); raises CredenceError for 4xx/5xx.
        """
        for attempt in (1, 2):
            res = self._http.post(
                path,
                json=json if json is not None else {},
                headers={"Authorization": f"Bearer {self.access_token()}", "Origin": self.origin},
            )
            if res.status_code < 400:
                return res
            err = _error_from(res)
            if attempt == 1 and (res.status_code == 401 or err.code in TOKEN_ERRORS):
                self.invalidate()
                continue
            raise err
        raise AssertionError("unreachable")

    def status(self) -> dict:
        """For /api/health: can we get a token right now? Uses the cache, so it doesn't spend rate limit."""
        if not self.configured:
            return {"ok": False, "code": "NOT_CONFIGURED"}
        try:
            self.access_token()
            return {"ok": True, "profile": self.profile_name}
        except CredenceError as e:
            return {"ok": False, "code": e.code}
        except httpx.HTTPError:
            return {"ok": False, "code": "NETWORK_ERROR"}


_client: CredenceClient | None = None


def get_client() -> CredenceClient:
    """Process-wide client built from settings (one token cache per server process)."""
    global _client
    if _client is None:
        from app.config import settings

        _client = CredenceClient(settings.credence_base_url, settings.credence_license_key,
                                 settings.credence_profile_id, settings.credence_origin)
    return _client
