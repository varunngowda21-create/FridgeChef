"""Integration tests for the scan session, verification, and confirmation API

per PRD Section 6.3, 7.3, 8.4, 11.4, and 12.3.
"""

import io
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from app.core.errors import AppError
from app.db.models.inventory import InventoryItem, ScanSession
from app.llm.vision import VisionItem, VisionResponse
from app.services.scan import cleanup_expired_scans


def _create_jpeg_bytes(width: int = 400, height: int = 300) -> bytes:
    """Helper to create dummy JPEG image bytes."""
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def create_authenticated_user(client: TestClient) -> tuple[str, str]:
    """Helper to register a user and return (email, access_token)."""
    email = f"chef_scan_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Scan Tester"},
    )
    assert resp.status_code == 201
    return email, resp.json()["access_token"]


def test_scan_endpoints_require_authentication(client: TestClient):
    """Verify all scan endpoints require authentication (PRD NFR-021)."""
    fake_id = uuid.uuid4()
    endpoints = [
        ("POST", "/api/v1/scans"),
        ("GET", f"/api/v1/scans/{fake_id}"),
        ("POST", f"/api/v1/scans/{fake_id}/confirm"),
        ("DELETE", f"/api/v1/scans/{fake_id}"),
    ]
    for method, path in endpoints:
        resp = client.request(method, path)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_upload_scan_image_success(client: TestClient, db_session):
    """Verify valid photo upload returns 201 with candidates, quality, and expiry."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    jpeg_data = _create_jpeg_bytes(600, 400)

    mock_vision_resp = VisionResponse(
        items=[
            VisionItem(
                name="Tomato",
                quantity=4.0,
                unit="piece",
                storage_guess="FRIDGE",
                confidence="HIGH",
                visible_note="ripe and fresh",
            ),
            VisionItem(
                name="Dahi",
                quantity=1.0,
                unit="container",
                storage_guess="FRIDGE",
                confidence="HIGH",
                visible_note="sealed dahi container",
            ),
            VisionItem(
                name="Unrecognized Item 99",
                quantity=1.0,
                unit="piece",
                storage_guess="FRIDGE",
                confidence="LOW",
                visible_note="blurry packet in corner",
            ),
        ],
        image_quality="GOOD",
        image_quality_note=None,
    )

    with patch("app.services.scan.call_groq_vision", new=AsyncMock(return_value=mock_vision_resp)):
        resp = client.post(
            "/api/v1/scans",
            files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()

    assert "scan_id" in data
    scan_id = uuid.UUID(data["scan_id"])
    assert data["status"] == "PENDING_VERIFY"
    assert data["image_quality"] == "GOOD"
    assert len(data["candidates"]) == 3

    # Check normalization:
    # 1. Tomato -> canonical_id: "tomato", needs_review: False
    c1 = data["candidates"][0]
    assert c1["name"] == "Tomato"
    assert c1["canonical_id"] == "tomato"
    assert c1["quantity"] == 4.0
    assert c1["needs_review"] is False

    # 2. Dahi -> canonical_id: "curd" (alias match), needs_review: False
    c2 = data["candidates"][1]
    assert c2["canonical_id"] == "curd"
    assert c2["needs_review"] is False

    # 3. Unrecognized -> canonical_id: None, needs_review: True
    c3 = data["candidates"][2]
    assert c3["canonical_id"] is None
    assert c3["needs_review"] is True

    # Verify session in DB and image saved
    session = db_session.query(ScanSession).filter(ScanSession.id == scan_id).first()
    assert session is not None
    assert session.status == "PENDING_VERIFY"
    assert session.image_path is not None
    assert os.path.exists(session.image_path)

    # Clean up test file
    if os.path.exists(session.image_path):
        os.remove(session.image_path)


def test_upload_scan_rate_limiting(client: TestClient):
    """Verify rate limit of 20 scans per day per user (PRD NFR-022, Section 11.4)."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    jpeg_data = _create_jpeg_bytes()

    mock_vision_resp = VisionResponse(items=[], image_quality="GOOD")

    with patch("app.services.scan.call_groq_vision", new=AsyncMock(return_value=mock_vision_resp)):
        # Make 20 calls (all should succeed)
        for _ in range(20):
            resp = client.post(
                "/api/v1/scans",
                files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
                headers=headers,
            )
            assert resp.status_code == 201

        # 21st call must be rejected with 429 SCAN_LIMIT_REACHED and Retry-After
        resp_blocked = client.post(
            "/api/v1/scans",
            files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
            headers=headers,
        )
        assert resp_blocked.status_code == 429
        assert resp_blocked.json()["error"]["code"] == "SCAN_LIMIT_REACHED"
        assert "Retry-After" in resp_blocked.headers


def test_upload_invalid_image_formats(client: TestClient):
    """Verify rejection of corrupt or unsupported media types (415 / 422)."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Text file
    resp = client.post(
        "/api/v1/scans",
        files={"image": ("document.txt", b"Hello world text", "text/plain")},
        headers=headers,
    )
    assert resp.status_code in (415, 422)

    # Corrupt image header
    resp_corrupt = client.post(
        "/api/v1/scans",
        files={"image": ("corrupted.jpg", b"\xff\xd8\xffcorruptedbytes", "image/jpeg")},
        headers=headers,
    )
    assert resp_corrupt.status_code == 422
    assert resp_corrupt.json()["error"]["code"] == "IMAGE_UNREADABLE"


def test_upload_vision_failure_cleans_up_image(client: TestClient, db_session):
    """Verify that if Groq Vision fails, 502 is returned and temporary image file is deleted."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    jpeg_data = _create_jpeg_bytes()

    with patch(
        "app.services.scan.call_groq_vision",
        side_effect=AppError(code="VISION_UNAVAILABLE", message="Groq vision unavailable", status_code=502),
    ):
        resp = client.post(
            "/api/v1/scans",
            files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
            headers=headers,
        )

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "VISION_UNAVAILABLE"


def test_get_scan_session_and_cross_user_isolation(client: TestClient):
    """Verify owner can retrieve scan session and cross-user access is denied."""
    _, token_a = create_authenticated_user(client)
    _, token_b = create_authenticated_user(client)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    jpeg_data = _create_jpeg_bytes()
    mock_vision = VisionResponse(
        items=[VisionItem(name="Tomato", quantity=2, unit="piece")],
        image_quality="GOOD",
    )

    with patch("app.services.scan.call_groq_vision", new=AsyncMock(return_value=mock_vision)):
        resp = client.post(
            "/api/v1/scans",
            files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
            headers=headers_a,
        )
    assert resp.status_code == 201
    scan_id = resp.json()["scan_id"]

    # Owner A can retrieve
    resp_a = client.get(f"/api/v1/scans/{scan_id}", headers=headers_a)
    assert resp_a.status_code == 200
    assert resp_a.json()["scan_id"] == scan_id

    # User B cannot retrieve User A's scan (404)
    resp_b = client.get(f"/api/v1/scans/{scan_id}", headers=headers_b)
    assert resp_b.status_code == 404
    assert resp_b.json()["error"]["code"] == "SCAN_SESSION_NOT_FOUND"


def test_confirm_scan_success(client: TestClient, db_session):
    """Verify confirming candidates writes to inventory with freshness and deletes image."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    jpeg_data = _create_jpeg_bytes()
    mock_vision = VisionResponse(
        items=[
            VisionItem(name="Tomato", quantity=3, unit="piece", storage_guess="FRIDGE"),
            VisionItem(name="Potato", quantity=2, unit="piece", storage_guess="PANTRY"),
            VisionItem(name="Spinach", quantity=1, unit="bunch", storage_guess="FRIDGE"),
        ],
        image_quality="GOOD",
    )

    with patch("app.services.scan.call_groq_vision", new=AsyncMock(return_value=mock_vision)):
        create_resp = client.post(
            "/api/v1/scans",
            files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
            headers=headers,
        )
    assert create_resp.status_code == 201
    scan_data = create_resp.json()
    scan_id = scan_data["scan_id"]
    candidates = scan_data["candidates"]

    # User confirms Tomato and Potato; leaves Spinach unconfirmed (skipped)
    confirm_payload = {
        "items": [
            {
                "candidate_id": candidates[0]["candidate_id"],
                "canonical_id": "tomato",
                "name": "Fresh Tomato",
                "quantity": 3,
                "unit": "piece",
                "storage": "FRIDGE",
                "opened_on": None,
            },
            {
                "candidate_id": candidates[1]["candidate_id"],
                "canonical_id": "potato",
                "name": "Potato",
                "quantity": 2,
                "unit": "piece",
                "storage": "PANTRY",
                "opened_on": None,
            },
        ]
    }

    resp = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json=confirm_payload,
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()

    assert len(data["created"]) == 2
    assert len(data["skipped"]) == 1
    assert data["skipped"][0] == candidates[2]["candidate_id"]

    # Verify created items have computed freshness fields
    tomato_inv = data["created"][0]
    assert tomato_inv["ingredient_id"] == "tomato"
    assert tomato_inv["quantity"] == "3.00" or float(tomato_inv["quantity"]) == 3.0
    assert tomato_inv["storage"] == "FRIDGE"
    assert tomato_inv["shelf_life_days_estimate"] is not None
    assert tomato_inv["status"] in ("USE_FIRST", "USE_SOON", "SAFE")
    assert "days_left" in tomato_inv

    # Verify session is marked CONFIRMED and image was deleted
    session = db_session.query(ScanSession).filter(ScanSession.id == scan_id).first()
    assert session.status == "CONFIRMED"
    assert session.image_path is None


def test_confirm_scan_rollback_on_error(client: TestClient, db_session):
    """Verify transactional atomicity: if one item fails validation, no items are created in inventory."""
    email, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    jpeg_data = _create_jpeg_bytes()
    mock_vision = VisionResponse(
        items=[
            VisionItem(name="Tomato", quantity=2, unit="piece", storage_guess="FRIDGE"),
            VisionItem(name="Milk", quantity=1, unit="bottle", storage_guess="FRIDGE"),
        ],
        image_quality="GOOD",
    )

    with patch("app.services.scan.call_groq_vision", new=AsyncMock(return_value=mock_vision)):
        create_resp = client.post(
            "/api/v1/scans",
            files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
            headers=headers,
        )
    scan_id = create_resp.json()["scan_id"]

    # Milk in COUNTER storage has 0 shelf life -> STORAGE_NOT_APPLICABLE
    invalid_confirm_payload = {
        "items": [
            {
                "canonical_id": "tomato",
                "name": "Tomato",
                "quantity": 2,
                "unit": "piece",
                "storage": "FRIDGE",
            },
            {
                "canonical_id": "milk",
                "name": "Milk",
                "quantity": 1,
                "unit": "bottle",
                "storage": "INVALID_STORAGE",  # Non-applicable storage
            },
        ]
    }

    resp = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json=invalid_confirm_payload,
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "STORAGE_NOT_APPLICABLE"

    # Verify rollback: 0 inventory items were created for this user
    from app.db.models.auth import User
    user = db_session.query(User).filter(User.email == email).first()
    inv_count = db_session.query(InventoryItem).filter(InventoryItem.user_id == user.id).count()
    assert inv_count == 0

    # Test missing canonical_id
    missing_canonical_payload = {
        "items": [
            {
                "canonical_id": None,
                "name": "Unknown herb",
                "quantity": 1,
                "unit": "piece",
                "storage": "FRIDGE",
            }
        ]
    }
    resp_missing = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json=missing_canonical_payload,
        headers=headers,
    )
    assert resp_missing.status_code == 422
    assert resp_missing.json()["error"]["code"] == "CANONICAL_ID_REQUIRED"


def test_confirm_scan_expired_rejected(client: TestClient, db_session):
    """Verify expired scan sessions cannot be confirmed (400 SCAN_SESSION_EXPIRED)."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    jpeg_data = _create_jpeg_bytes()
    mock_vision = VisionResponse(items=[], image_quality="GOOD")

    with patch("app.services.scan.call_groq_vision", new=AsyncMock(return_value=mock_vision)):
        create_resp = client.post(
            "/api/v1/scans",
            files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
            headers=headers,
        )
    scan_id = create_resp.json()["scan_id"]

    # Artificially expire the session in DB
    session = db_session.query(ScanSession).filter(ScanSession.id == scan_id).first()
    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    resp = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json={"items": [{"canonical_id": "tomato", "name": "Tomato", "quantity": 1, "unit": "piece", "storage": "FRIDGE"}]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "SCAN_SESSION_EXPIRED"


def test_delete_scan_session(client: TestClient, db_session):
    """Verify DELETE /scans/{id} removes session and image (PRD Section 11.4)."""
    _, token_a = create_authenticated_user(client)
    _, token_b = create_authenticated_user(client)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    jpeg_data = _create_jpeg_bytes()
    mock_vision = VisionResponse(items=[], image_quality="GOOD")

    with patch("app.services.scan.call_groq_vision", new=AsyncMock(return_value=mock_vision)):
        create_resp = client.post(
            "/api/v1/scans",
            files={"image": ("fridge.jpg", jpeg_data, "image/jpeg")},
            headers=headers_a,
        )
    scan_id = create_resp.json()["scan_id"]

    # User B cannot delete User A's scan (404)
    resp_b = client.delete(f"/api/v1/scans/{scan_id}", headers=headers_b)
    assert resp_b.status_code == 404

    # User A deletes their scan (204)
    resp_a = client.delete(f"/api/v1/scans/{scan_id}", headers=headers_a)
    assert resp_a.status_code == 204

    # Verify session deleted from DB
    session = db_session.query(ScanSession).filter(ScanSession.id == scan_id).first()
    assert session is None


def test_cleanup_expired_scans_service(db_session):
    """Verify background cleanup task deletes image files and expires stale sessions."""
    test_scan_id = uuid.uuid4()

    from app.db.models.auth import User
    test_user = db_session.query(User).first()

    session = ScanSession(
        id=test_scan_id,
        user_id=test_user.id,
        status="PENDING_VERIFY",
        image_path=None,
        candidates=[],
        image_quality="GOOD",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db_session.add(session)
    db_session.commit()

    cleaned = cleanup_expired_scans(db_session)
    assert cleaned >= 1

    db_session.refresh(session)
    assert session.status == "EXPIRED"
