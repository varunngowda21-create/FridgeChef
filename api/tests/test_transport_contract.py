import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_cookie_transport_contract(client: TestClient):
    settings = get_settings()
    assert settings.AUTH_REFRESH_TRANSPORT == "cookie"

    email = f"contract_cookie_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Cookie User"},
    )
    assert reg.status_code == 201
    data = reg.json()

    # In cookie transport, refresh token is NOT in the JSON body
    assert data["refresh_token"] is None

    # Cookies must be set
    assert "refresh_token" in reg.cookies
    assert "csrf_token" in reg.cookies

    # Inspect cookie flags
    cookie_headers = reg.headers.get_list("set-cookie")
    refresh_header = next(h for h in cookie_headers if "refresh_token=" in h)
    assert "httponly" in refresh_header.lower()
    assert "path=/api/v1/auth" in refresh_header.lower()
    assert "samesite=lax" in refresh_header.lower()

    # Refresh endpoint requires cookie transport (body token ignored / cookie required)
    # Attempting to refresh without cookie returns 401
    bad_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "some_body_token"},
    )
    assert bad_refresh.status_code in (401, 403)


def test_sessionstorage_transport_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    # Temporarily configure transport to sessionstorage
    settings = get_settings()
    monkeypatch.setattr(settings, "AUTH_REFRESH_TRANSPORT", "sessionstorage")

    email = f"contract_ss_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Storage User"},
    )
    assert reg.status_code == 201
    data = reg.json()

    # In sessionstorage transport, refresh token IS in the JSON body
    assert data["refresh_token"] is not None
    ss_token = data["refresh_token"]

    # Cookies should NOT be set
    assert "refresh_token" not in reg.cookies

    # Refresh endpoint accepts body token
    ref_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ss_token},
    )
    assert ref_resp.status_code == 200
    ref_data = ref_resp.json()
    assert ref_data["access_token"] is not None
    assert ref_data["refresh_token"] is not None
    assert ref_data["refresh_token"] != ss_token  # Rotated!
