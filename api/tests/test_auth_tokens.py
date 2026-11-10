import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token
from app.db.models.auth import RefreshToken
from app.main import app


def test_refresh_token_rotation_and_revocation(db_session: Session):
    with TestClient(app) as test_client:
        email = f"rotation_{uuid.uuid4().hex[:8]}@example.com"
        reg = test_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!", "display_name": "Rotation User"},
        )
        assert reg.status_code == 201
        old_refresh_token = reg.cookies.get("refresh_token")
        csrf_token = reg.cookies.get("csrf_token")
        assert old_refresh_token is not None
        assert csrf_token is not None

        # Verify old token exists in DB and is active
        old_hash = hash_token(old_refresh_token)
        db_old_token = db_session.query(RefreshToken).filter(RefreshToken.token_hash == old_hash).first()
        assert db_old_token is not None
        assert db_old_token.revoked_at is None

        # Call /refresh with CSRF header (cookies are automatically sent by test_client)
        refresh_resp = test_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert refresh_resp.status_code == 200
        data = refresh_resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600

        new_refresh_token = refresh_resp.cookies.get("refresh_token")
        assert new_refresh_token is not None
        assert new_refresh_token != old_refresh_token

        # Verify old token in DB is now revoked
        db_session.refresh(db_old_token)
        assert db_old_token.revoked_at is not None

        # Verify new token in DB is active
        new_hash = hash_token(new_refresh_token)
        db_new_token = db_session.query(RefreshToken).filter(RefreshToken.token_hash == new_hash).first()
        assert db_new_token is not None
        assert db_new_token.revoked_at is None


def test_refresh_token_reuse_detection(db_session: Session):
    email = f"reuse_{uuid.uuid4().hex[:8]}@example.com"

    # Legitimate user registers and gets initial token
    with TestClient(app) as user_client:
        reg = user_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!", "display_name": "Reuse User"},
        )
        assert reg.status_code == 201
        stolen_old_token = reg.cookies.get("refresh_token")
        user_csrf = reg.cookies.get("csrf_token")
        assert stolen_old_token is not None
        assert user_csrf is not None

        # Legitimate user rotates token
        legit_refresh = user_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": user_csrf},
        )
        assert legit_refresh.status_code == 200
        active_token = legit_refresh.cookies.get("refresh_token")
        assert active_token is not None

    # Attacker on another client tries to replay the old stolen token
    with TestClient(app) as attacker_client:
        attacker_csrf = "attacker_csrf_secret"
        attacker_client.cookies.set("refresh_token", stolen_old_token, path="/api/v1/auth")
        attacker_client.cookies.set("csrf_token", attacker_csrf, path="/")

        reuse_resp = attacker_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": attacker_csrf},
        )
        assert reuse_resp.status_code == 401
        assert reuse_resp.json()["error"]["code"] == "TOKEN_REUSE_DETECTED"

    # Verify all tokens for this user have been invalidated as a security precaution
    active_hash = hash_token(active_token)
    active_record = db_session.query(RefreshToken).filter(RefreshToken.token_hash == active_hash).first()
    assert active_record is not None
    assert active_record.revoked_at is not None


def test_refresh_token_expired(db_session: Session):
    with TestClient(app) as test_client:
        email = f"expired_{uuid.uuid4().hex[:8]}@example.com"
        reg = test_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!", "display_name": "Expired User"},
        )
        raw_token = reg.cookies.get("refresh_token")
        csrf_token = reg.cookies.get("csrf_token")
        assert raw_token is not None
        assert csrf_token is not None

        # Set expiry in the past
        token_h = hash_token(raw_token)
        record = db_session.query(RefreshToken).filter(RefreshToken.token_hash == token_h).first()
        assert record is not None
        record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.commit()

        resp = test_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "REFRESH_TOKEN_EXPIRED"


def test_csrf_protection_on_cookie_endpoints():
    with TestClient(app) as test_client:
        email = f"csrf_{uuid.uuid4().hex[:8]}@example.com"
        reg = test_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!", "display_name": "CSRF User"},
        )
        assert reg.status_code == 201

        # Missing X-CSRF-Token header
        resp1 = test_client.post("/api/v1/auth/refresh")
        assert resp1.status_code == 403
        assert resp1.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

        # Mismatched X-CSRF-Token header
        resp2 = test_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": "wrong_csrf_token_value"},
        )
        assert resp2.status_code == 403
        assert resp2.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

        # Missing CSRF on logout
        resp3 = test_client.post("/api/v1/auth/logout")
        assert resp3.status_code == 403
        assert resp3.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


def test_logout_revocation(db_session: Session):
    with TestClient(app) as test_client:
        email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
        reg = test_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!", "display_name": "Logout User"},
        )
        raw_token = reg.cookies.get("refresh_token")
        csrf_token = reg.cookies.get("csrf_token")
        assert raw_token is not None
        assert csrf_token is not None

        logout_resp = test_client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert logout_resp.status_code == 204

        # Verify token is revoked in DB
        token_h = hash_token(raw_token)
        record = db_session.query(RefreshToken).filter(RefreshToken.token_hash == token_h).first()
        assert record is not None
        assert record.revoked_at is not None

        # Subsequent refresh attempt fails because cookies were cleared
        refresh_resp = test_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert refresh_resp.status_code in (401, 403)

    # Replaying the logged-out (revoked) token from an attacker session must fail with 401
    with TestClient(app) as attacker_client:
        attacker_csrf = "attacker_session_csrf"
        attacker_client.cookies.set("refresh_token", raw_token, path="/api/v1/auth")
        attacker_client.cookies.set("csrf_token", attacker_csrf, path="/")
        replay_resp = attacker_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": attacker_csrf},
        )
        assert replay_resp.status_code == 401



def test_access_token_expired():
    with TestClient(app) as test_client:
        settings = get_settings()
        # Create an expired JWT
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "email": "expired@example.com",
            "type": "access",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        }
        expired_token = jwt.encode(expired_payload, settings.JWT_SECRET, algorithm="HS256")

        resp = test_client.get("/api/v1/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_access_token_tampered_signature():
    with TestClient(app) as test_client:
        # Create a token signed with wrong secret
        tampered_payload = {
            "sub": str(uuid.uuid4()),
            "email": "hacker@example.com",
            "type": "access",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        tampered_token = jwt.encode(tampered_payload, "wrong_secret_12345678901234567890", algorithm="HS256")

        resp = test_client.get("/api/v1/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_TOKEN"
