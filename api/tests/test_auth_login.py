import uuid

from fastapi.testclient import TestClient

from app.core.ratelimit import login_rate_limiter


def test_login_success(client: TestClient):
    email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword1!"

    # Register user first
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Login Tester"},
    )
    assert reg.status_code == 201

    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600
    assert data["user"]["email"] == email.lower()
    assert "refresh_token" in login_resp.cookies
    assert "csrf_token" in login_resp.cookies


def test_login_incorrect_password(client: TestClient):
    email = f"wrongpass_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword1!"

    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Wrong Pass"},
    )

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword99!"},
    )
    assert resp.status_code == 401
    err = resp.json()["error"]
    assert err["code"] == "INVALID_CREDENTIALS"
    assert err["message"] == "Invalid email or password."


def test_login_nonexistent_account(client: TestClient):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent_ghost@example.com", "password": "Password123!"},
    )
    assert resp.status_code == 401
    err = resp.json()["error"]
    # Generic error message identical to wrong password — no account enumeration
    assert err["code"] == "INVALID_CREDENTIALS"
    assert err["message"] == "Invalid email or password."


def test_login_case_insensitive_email(client: TestClient):
    email = f"CaseInsensitive_{uuid.uuid4().hex[:8]}@Example.COM"
    password = "Password123!"

    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Case Sensitive"},
    )

    # Login with all lowercase
    resp1 = client.post(
        "/api/v1/auth/login",
        json={"email": email.lower(), "password": password},
    )
    assert resp1.status_code == 200

    # Login with all uppercase
    resp2 = client.post(
        "/api/v1/auth/login",
        json={"email": email.upper(), "password": password},
    )
    assert resp2.status_code == 200


def test_login_rate_limiting(client: TestClient):
    login_rate_limiter.clear()
    email = f"ratelimit_{uuid.uuid4().hex[:8]}@example.com"

    # Send 10 failed login attempts (allowed per NFR-023: 10 attempts per 15 min)
    for _ in range(10):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "BadPassword123!"},
        )
        assert resp.status_code == 401

    # 11th attempt must be blocked by rate limiter
    blocked_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "BadPassword123!"},
    )
    assert blocked_resp.status_code == 429
    err = blocked_resp.json()["error"]
    assert err["code"] == "RATE_LIMIT_EXCEEDED"
    assert "retry_after_seconds" in err["details"]
    assert err["details"]["retry_after_seconds"] > 0
