import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.auth import RefreshToken, User, UserPreference


def test_register_success(client: TestClient, db_session: Session):
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "Password123!",
        "display_name": "Test Chef",
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    # Response envelope verification
    assert "user" in data
    assert data["user"]["email"] == unique_email.lower()
    assert data["user"]["display_name"] == "Test Chef"
    assert "id" in data["user"]
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600
    # In cookie transport, refresh_token is not in JSON body
    assert data["refresh_token"] is None

    # Cookie verification
    assert "refresh_token" in response.cookies
    assert "csrf_token" in response.cookies

    # Verify cookies headers
    set_cookie_headers = response.headers.get_list("set-cookie")
    refresh_cookie_header = next((h for h in set_cookie_headers if "refresh_token=" in h), "")
    assert "HttpOnly" in refresh_cookie_header or "httponly" in refresh_cookie_header.lower()
    assert "path=/api/v1/auth" in refresh_cookie_header.lower()
    assert "samesite=lax" in refresh_cookie_header.lower()

    # Verify database persistence
    user = db_session.query(User).filter(User.email == unique_email.lower()).first()
    assert user is not None
    assert user.display_name == "Test Chef"
    assert user.password_hash != "Password123!"  # Hashed

    # Verify default user preferences
    pref = db_session.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    assert pref is not None
    assert pref.household_size == 2
    assert pref.diet == "VEGETARIAN"
    assert pref.spice_level == "MEDIUM"
    assert pref.max_cooking_time == 45
    assert pref.version == 1

    # Verify refresh token record in DB
    token_records = db_session.query(RefreshToken).filter(RefreshToken.user_id == user.id).all()
    assert len(token_records) == 1
    assert token_records[0].revoked_at is None


def test_register_duplicate_email(client: TestClient):
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "Password123!",
        "display_name": "First User",
    }
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    # Attempt to register with the exact same email
    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    err = r2.json()["error"]
    assert err["code"] == "EMAIL_ALREADY_EXISTS"
    assert "already exists" in err["message"].lower()

    # Attempt to register with mixed-case variant of email
    r3 = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email.upper(),
            "password": "Password123!",
            "display_name": "Different Name",
        },
    )
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_register_password_policy(client: TestClient):
    base_email = f"policy_{uuid.uuid4().hex[:8]}@example.com"

    # Too short (< 8 chars)
    r1 = client.post(
        "/api/v1/auth/register",
        json={"email": base_email, "password": "Pass1", "display_name": "Short"},
    )
    assert r1.status_code in (422, 400)

    # No uppercase letter
    r2 = client.post(
        "/api/v1/auth/register",
        json={"email": base_email, "password": "password123!", "display_name": "No Upper"},
    )
    assert r2.status_code in (422, 400)

    # No lowercase letter
    r3 = client.post(
        "/api/v1/auth/register",
        json={"email": base_email, "password": "PASSWORD123!", "display_name": "No Lower"},
    )
    assert r3.status_code in (422, 400)

    # No digit
    r4 = client.post(
        "/api/v1/auth/register",
        json={"email": base_email, "password": "PasswordOnly!", "display_name": "No Digit"},
    )
    assert r4.status_code in (422, 400)


def test_register_invalid_email(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "Password123!", "display_name": "Bad Email"},
    )
    assert response.status_code == 422


def test_register_rejects_unknown_fields(client: TestClient):
    unique_email = f"unknown_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "Password123!",
            "display_name": "Admin",
            "is_admin": True,  # Unknown field
        },
    )
    assert response.status_code == 422
