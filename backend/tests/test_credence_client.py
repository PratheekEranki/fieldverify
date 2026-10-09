"""T14: Credence client token lifecycle, against a fake Credence API (httpx.MockTransport)."""
import json

import httpx
import pytest

from app.credence.client import CredenceClient, CredenceError


class FakeCredence:
    def __init__(self):
        self.calls: list[str] = []
        self.setup_count = 0
        self.refresh_count = 0
        self.valid_access: set[str] = set()
        self.fail_refresh = False
        self.origins: list[str | None] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/cloudsdk/playground")
        self.calls.append(path)
        self.origins.append(request.headers.get("origin"))
        if path == "/v1/setup":
            body = json.loads(request.content)
            if body["licenseKey"] != "CS_good":
                return httpx.Response(401, json={"error": "INVALID_LICENSE_KEY", "message": "Invalid License Key"})
            self.setup_count += 1
            return self._tokens(f"a{self.setup_count}", profile="Test Profile")
        if path == "/v1/refresh":
            if self.fail_refresh:
                return httpx.Response(401, json={"error": "REFRESH_TOKEN_EXPIRED", "message": "expired"})
            self.refresh_count += 1
            return self._tokens(f"r{self.refresh_count}")
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if token not in self.valid_access:
            return httpx.Response(401, json={"error": "TOKEN_EXPIRED", "message": "Token expired"})
        return httpx.Response(200, json={"ok": True, "token": token})

    def _tokens(self, access: str, profile: str | None = None) -> httpx.Response:
        self.valid_access = {access}
        body = {"accessToken": access, "refreshToken": f"rt-{access}", "expiresIn": 900, "tokenType": "Bearer"}
        if profile:
            body["profileName"] = profile
        return httpx.Response(200, json=body)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(fake, clock, key="CS_good"):
    return CredenceClient("https://credenceid.com/cloudsdk/playground", key, "prof-1",
                          "https://fieldverify-avyq.onrender.com", transport=httpx.MockTransport(fake.handler),
                          clock=clock)


def test_setup_once_then_cached_with_origin_header():
    fake, clock = FakeCredence(), Clock()
    client = make(fake, clock)
    assert client.access_token() == "a1"
    assert client.access_token() == "a1"
    assert fake.setup_count == 1
    assert fake.origins[0] == "https://fieldverify-avyq.onrender.com"
    assert client.status() == {"ok": True, "profile": "Test Profile"}


def test_refreshes_when_less_than_60s_left():
    fake, clock = FakeCredence(), Clock()
    client = make(fake, clock)
    client.access_token()
    clock.now += 900 - 30
    assert client.access_token() == "r1"
    assert fake.refresh_count == 1 and fake.setup_count == 1
    assert client.profile_name == "Test Profile"  # kept across refresh (refresh omits it)


def test_falls_back_to_setup_when_refresh_fails():
    fake, clock = FakeCredence(), Clock()
    client = make(fake, clock)
    client.access_token()
    fake.fail_refresh = True
    clock.now += 2000
    assert client.access_token() == "a2"
    assert fake.setup_count == 2


def test_post_retries_once_on_expired_token():
    fake, clock = FakeCredence(), Clock()
    client = make(fake, clock)
    client.access_token()
    fake.valid_access = set()  # server-side expiry the client didn't know about
    res = client.post("/dcapi/openid4vp/v1/initiate")
    assert res.status_code == 200 and fake.setup_count == 2


def test_bad_key_raises_credence_code():
    fake, clock = FakeCredence(), Clock()
    client = make(fake, clock, key="CS_bad")
    with pytest.raises(CredenceError) as exc:
        client.access_token()
    assert exc.value.code == "INVALID_LICENSE_KEY"
    assert client.status() == {"ok": False, "code": "INVALID_LICENSE_KEY"}


def test_not_configured():
    client = CredenceClient("https://x", "", "", "")
    assert client.status() == {"ok": False, "code": "NOT_CONFIGURED"}
