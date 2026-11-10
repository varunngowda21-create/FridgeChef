import io
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import JSONFormatter, mask_email, sanitize_log_message
from app.db.models.auth import RefreshToken
from app.db.models.inventory import ScanSession
from app.main import app
from app.media.image_pipeline import save_processed_image, validate_and_process_image


def test_security_headers_enforcement(client: TestClient):
    """Verify that every HTTP response enforces strict security headers."""
    response = client.get("/api/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert headers.get("X-XSS-Protection") == "1; mode=block"


def test_hsts_header_in_production(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Verify HSTS header is strictly enforced under production HTTPS conditions (PRD 15.1, RFC 6797)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "production")

    # 1. Plain HTTP request without secure proxy headers must NOT emit HSTS (RFC 6797 Sec 7.2)
    response_http = client.get("/api/health")
    assert response_http.status_code == 200
    assert "Strict-Transport-Security" not in response_http.headers

    # 2. HTTPS request (or forwarded from trusted proxy) in production must emit HSTS
    response_https = client.get("/api/health", headers={"X-Forwarded-Proto": "https"})
    assert response_https.status_code == 200
    assert "Strict-Transport-Security" in response_https.headers
    assert "max-age=31536000" in response_https.headers["Strict-Transport-Security"]


def test_cross_user_inventory_authorization_isolation(db_session: Session):
    """Verify that User B cannot read, update, use, waste, or delete User A's inventory items."""
    with TestClient(app) as client:
        # 1. Register User A and create an inventory item
        email_a = f"usera_{uuid.uuid4().hex[:8]}@example.com"
        reg_a = client.post(
            "/api/v1/auth/register",
            json={"email": email_a, "password": "Password123!", "display_name": "User A"},
        )
        assert reg_a.status_code == 201
        token_a = reg_a.json()["access_token"]

        item_res = client.post(
            "/api/v1/inventory",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "canonical_id": "tomato",
                "display_name": "Fresh Tomatoes",
                "quantity": 5.0,
                "unit": "piece",
                "storage": "FRIDGE",
            },
        )
        assert item_res.status_code == 201
        item_id = item_res.json()["id"]

        # 2. Register User B
        email_b = f"userb_{uuid.uuid4().hex[:8]}@example.com"
        reg_b = client.post(
            "/api/v1/auth/register",
            json={"email": email_b, "password": "Password123!", "display_name": "User B"},
        )
        assert reg_b.status_code == 201
        token_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 3. User B attempts unauthorized access to User A's item
        # Read
        get_res = client.get(f"/api/v1/inventory/{item_id}", headers=headers_b)
        assert get_res.status_code == 404
        assert get_res.json()["error"]["code"] == "INVENTORY_ITEM_NOT_FOUND"

        # Update
        patch_res = client.patch(
            f"/api/v1/inventory/{item_id}",
            headers=headers_b,
            json={"display_name": "Hacked Tomatoes"},
        )
        assert patch_res.status_code == 404

        # Use
        use_res = client.post(
            f"/api/v1/inventory/{item_id}/use",
            headers=headers_b,
            json={"quantity": 1.0},
        )
        assert use_res.status_code == 404

        # Waste
        waste_res = client.post(
            f"/api/v1/inventory/{item_id}/waste",
            headers=headers_b,
            json={"quantity": 1.0},
        )
        assert waste_res.status_code == 404

        # Delete
        del_res = client.delete(f"/api/v1/inventory/{item_id}", headers=headers_b)
        assert del_res.status_code == 404

        # 4. Verify User A's item is completely unaltered
        item_a = client.get(f"/api/v1/inventory/{item_id}", headers={"Authorization": f"Bearer {token_a}"})
        assert item_a.status_code == 200
        assert item_a.json()["display_name"] == "Fresh Tomatoes"
        assert Decimal(str(item_a.json()["quantity"])) == Decimal("5.00")


def test_cross_user_scan_session_isolation(db_session: Session):
    """Verify that User B cannot read, confirm, or delete User A's scan session."""
    with TestClient(app) as client:
        # Register User A and create a simulated scan session
        email_a = f"scan_a_{uuid.uuid4().hex[:8]}@example.com"
        reg_a = client.post(
            "/api/v1/auth/register",
            json={"email": email_a, "password": "Password123!", "display_name": "User A"},
        )
        user_a_id = uuid.UUID(reg_a.json()["user"]["id"])

        scan_id = uuid.uuid4()
        session_a = ScanSession(
            id=scan_id,
            user_id=user_a_id,
            status="PENDING_VERIFY",
            candidates=[],
            image_quality="GOOD",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db_session.add(session_a)
        db_session.commit()

        # Register User B
        email_b = f"scan_b_{uuid.uuid4().hex[:8]}@example.com"
        reg_b = client.post(
            "/api/v1/auth/register",
            json={"email": email_b, "password": "Password123!", "display_name": "User B"},
        )
        token_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B attempts to access User A's scan session
        assert client.get(f"/api/v1/scans/{scan_id}", headers=headers_b).status_code == 404
        assert client.post(f"/api/v1/scans/{scan_id}/confirm", headers=headers_b, json={"items": []}).status_code == 404
        assert client.delete(f"/api/v1/scans/{scan_id}", headers=headers_b).status_code == 404


def test_cross_user_planning_and_shopping_isolation(db_session: Session):
    """Verify that shopping lists are completely isolated across users."""
    with TestClient(app) as client:
        # Register User A
        reg_a = client.post(
            "/api/v1/auth/register",
            json={"email": f"plan_a_{uuid.uuid4().hex[:8]}@example.com", "password": "Password123!", "display_name": "Planner A"},
        )
        token_a = reg_a.json()["access_token"]

        # Register User B
        reg_b = client.post(
            "/api/v1/auth/register",
            json={"email": f"plan_b_{uuid.uuid4().hex[:8]}@example.com", "password": "Password123!", "display_name": "Planner B"},
        )
        token_b = reg_b.json()["access_token"]

        # Create shopping list for User A
        shop_res = client.post(
            "/api/v1/shopping-lists",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "source": "MANUAL",
                "manual_items": [{"canonical_id": "ginger", "qty": 100.0, "unit": "g"}],
            },
        )
        assert shop_res.status_code == 201
        list_id = shop_res.json()["id"]

        # User B attempts to fetch User A's shopping list by ID -> 404
        list_b = client.get(f"/api/v1/shopping-lists/{list_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert list_b.status_code == 404
        assert list_b.json()["error"]["code"] == "ITEM_NOT_FOUND"


def test_csrf_protection_with_cookie_transport(db_session: Session):
    """Verify CSRF token enforcement for state-changing auth operations using cookies."""
    with TestClient(app) as client:
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": f"csrf_{uuid.uuid4().hex[:8]}@example.com", "password": "Password123!", "display_name": "CSRF User"},
        )
        assert reg.status_code == 201
        valid_csrf = reg.cookies.get("csrf_token")
        assert valid_csrf is not None

        # 1. Calling /refresh without X-CSRF-Token header -> 403 CSRF_TOKEN_INVALID
        no_header_resp = client.post("/api/v1/auth/refresh")
        assert no_header_resp.status_code == 403
        assert no_header_resp.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

        # 2. Calling /refresh with mismatched X-CSRF-Token header -> 403 CSRF_TOKEN_INVALID
        mismatch_resp = client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": "tampered_token_value_123"},
        )
        assert mismatch_resp.status_code == 403
        assert mismatch_resp.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

        # 3. Calling /logout with mismatched X-CSRF-Token -> 403 CSRF_TOKEN_INVALID
        bad_logout = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": "invalid_csrf_header"},
        )
        assert bad_logout.status_code == 403

        # 4. Calling /refresh with valid X-CSRF-Token header -> 200 OK
        valid_refresh = client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": valid_csrf},
        )
        assert valid_refresh.status_code == 200


def test_account_deletion_security_and_cleanup(db_session: Session, tmp_path):
    """Verify that account deletion enforces password authentication and immediately purges user assets."""
    with TestClient(app) as client:
        email = f"delete_{uuid.uuid4().hex[:8]}@example.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!", "display_name": "Delete Target"},
        )
        token = reg.json()["access_token"]
        user_id = uuid.UUID(reg.json()["user"]["id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Create dummy image file for scan session
        img_file = tmp_path / f"{uuid.uuid4()}.jpg"
        img_file.write_bytes(b"dummy_image_data")
        assert img_file.exists()

        scan = ScanSession(
            id=uuid.uuid4(),
            user_id=user_id,
            status="PENDING_VERIFY",
            image_path=str(img_file),
            candidates=[],
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db_session.add(scan)
        db_session.commit()

        # 1. Attempt deletion with incorrect password -> 401 INVALID_CREDENTIALS
        bad_del = client.request("DELETE", "/api/v1/me", headers=headers, json={"password": "WrongPassword!"})
        assert bad_del.status_code == 401
        assert bad_del.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert img_file.exists()

        # 2. Delete with correct password -> 202 ACCEPTED
        good_del = client.request("DELETE", "/api/v1/me", headers=headers, json={"password": "Password123!"})
        assert good_del.status_code == 202
        assert good_del.json()["status"] == "SCHEDULED"

        # 3. Verify image file was physically unlinked
        assert not img_file.exists()

        # 4. Verify all refresh tokens are revoked
        active_tokens = db_session.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        ).count()
        assert active_tokens == 0

        # 5. Subsequent access token requests are immediately rejected
        aftermath = client.get("/api/v1/me", headers=headers)
        assert aftermath.status_code == 401
        assert aftermath.json()["error"]["code"] == "UNAUTHORIZED"


def test_logging_privacy_and_email_masking():
    """Verify PRD NFR-032 log sanitization and email masking."""
    # Unit test mask_email
    assert mask_email("charlie@example.com") == "c***@example.com"
    assert mask_email("a@example.com") == "*@example.com"
    assert mask_email("invalid_email") == "invalid_email"
    assert mask_email(None) is None

    # Unit test sanitize_log_message
    msg = "User logged in with email alice.smith@fridgechef.org and ip 127.0.0.1"
    sanitized = sanitize_log_message(msg)
    assert "alice.smith@fridgechef.org" not in sanitized
    assert "a***@fridgechef.org" in sanitized

    # Verify JSONFormatter sanitizes output
    import logging
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Failed login for bob.jones@domain.co.in",
        args=(),
        exc_info=None,
    )
    formatter = JSONFormatter()
    output = formatter.format(record)
    assert "bob.jones@domain.co.in" not in output
    assert "b***@domain.co.in" in output


def test_path_traversal_prevention_on_upload(tmp_path):
    """Verify that save_processed_image strictly constructs UUID-based filenames within UPLOAD_DIR."""
    upload_dir = tmp_path / "uploads"
    scan_id = uuid.uuid4()
    saved_path = save_processed_image(
        scan_id=scan_id,
        image_bytes=b"dummy_safe_bytes",
        upload_dir=str(upload_dir),
    )

    # Path must end in '<scan_id>.jpg'
    assert os.path.basename(saved_path) == f"{scan_id}.jpg"
    # File must reside strictly inside the upload_dir
    assert os.path.dirname(os.path.abspath(saved_path)) == str(upload_dir.resolve())
    assert os.path.exists(saved_path)


def test_cookie_security_flags_and_attributes(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Verify that auth cookies enforce HttpOnly, Path=/api/v1/auth, SameSite=lax, and Secure in production."""
    settings = get_settings()

    # 1. Test in development
    resp_dev = client.post(
        "/api/v1/auth/register",
        json={"email": f"cookie_dev_{uuid.uuid4().hex[:8]}@example.com", "password": "Password123!", "display_name": "Dev User"},
    )
    assert resp_dev.status_code == 201
    cookie_header_dev = resp_dev.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header_dev or "httponly" in cookie_header_dev
    assert "Path=/api/v1/auth" in cookie_header_dev or "path=/api/v1/auth" in cookie_header_dev

    # 2. Test in production (Secure flag must be emitted)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    resp_prod = client.post(
        "/api/v1/auth/register",
        json={"email": f"cookie_prod_{uuid.uuid4().hex[:8]}@example.com", "password": "Password123!", "display_name": "Prod User"},
    )
    assert resp_prod.status_code == 201
    cookie_header_prod = resp_prod.headers.get("set-cookie", "")
    assert "Secure" in cookie_header_prod or "secure" in cookie_header_prod


def test_cross_user_meal_plan_isolation(client: TestClient, db_session: Session):
    """Verify that User B cannot read or regenerate User A's meal plans."""
    # Register User A and create a meal plan
    reg_a = client.post(
        "/api/v1/auth/register",
        json={"email": f"mp_a_{uuid.uuid4().hex[:8]}@example.com", "password": "Password123!", "display_name": "MealPlan User A"},
    )
    assert reg_a.status_code == 201
    token_a = reg_a.json()["access_token"]
    plan_res = client.post("/api/v1/meal-plans", headers={"Authorization": f"Bearer {token_a}"}, json={})
    assert plan_res.status_code == 201
    plan_id = plan_res.json()["id"]

    # Register User B
    reg_b = client.post(
        "/api/v1/auth/register",
        json={"email": f"mp_b_{uuid.uuid4().hex[:8]}@example.com", "password": "Password123!", "display_name": "MealPlan User B"},
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B attempts to view User A's meal plan -> 404
    get_res = client.get(f"/api/v1/meal-plans/{plan_id}", headers=headers_b)
    assert get_res.status_code == 404

    # User B attempts to regenerate a slot in User A's meal plan -> 404
    regen_res = client.post(
        f"/api/v1/meal-plans/{plan_id}/slots/1/LUNCH/regenerate",
        headers=headers_b,
    )
    assert regen_res.status_code == 404


def test_upload_validation_mime_size_and_exif_stripping():
    """Verify upload MIME validation, 8MB boundary, corrupt file rejection, and EXIF stripping."""
    # 1. Oversized image > 8MB
    huge_data = b"X" * (8 * 1024 * 1024 + 10)
    with pytest.raises(AppError) as exc_info:
        validate_and_process_image(huge_data)
    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "IMAGE_TOO_LARGE"

    # 2. Corrupt / empty file
    with pytest.raises(AppError) as exc_info:
        validate_and_process_image(b"not_an_image_file")
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "IMAGE_UNREADABLE"

    # 3. EXIF metadata stripping: generate valid image with EXIF orientation metadata
    img = Image.new("RGB", (200, 200), color="red")
    exif_data = img.getexif()
    exif_data[0x0112] = 6  # Orientation tag
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_data)
    raw_bytes_with_exif = buf.getvalue()

    # Confirm raw bytes actually have EXIF tag
    raw_img = Image.open(io.BytesIO(raw_bytes_with_exif))
    assert raw_img.getexif().get(0x0112) == 6

    # Process through pipeline
    processed = validate_and_process_image(raw_bytes_with_exif)
    assert processed.format == "JPEG"

    # Verify processed image has NO EXIF orientation metadata
    processed_img = Image.open(io.BytesIO(processed.data))
    processed_exif = processed_img.getexif()
    assert 0x0112 not in processed_exif


def test_sensitive_endpoints_require_authentication(client: TestClient):
    """Verify that unauthenticated requests to sensitive endpoints return HTTP 401."""
    sensitive_routes = [
        ("GET", "/api/v1/me"),
        ("GET", "/api/v1/inventory"),
        ("POST", "/api/v1/inventory"),
        ("GET", "/api/v1/recommendations"),
        ("POST", "/api/v1/meal-plans"),
        ("POST", "/api/v1/shopping-lists"),
        ("POST", "/api/v1/scans"),
    ]

    for method, path in sensitive_routes:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"{method} {path} returned {res.status_code} instead of 401"
        assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_error_responses_standard_envelope_no_leakage(client: TestClient):
    """Verify PRD standard error envelope across error codes and verify no internal trace leaks."""
    # 404 Not Found
    res_404 = client.get(f"/api/v1/inventory/{uuid.uuid4()}", headers={"Authorization": "Bearer invalid_token"})
    assert res_404.status_code == 401  # Token invalid

    # 422 Unprocessable Content (validation error)
    res_422 = client.post("/api/v1/auth/login", json={"email": "bad-email", "password": "123"})
    assert res_422.status_code == 422
    data_422 = res_422.json()
    assert "error" in data_422
    assert "code" in data_422["error"]
    assert "message" in data_422["error"]
    assert "request_id" in data_422["error"]
    # Ensure sensitive system details or raw stack traces do not appear
    err_str = str(data_422)
    assert "Traceback" not in err_str
    assert "password" not in data_422["error"]["message"].lower()
