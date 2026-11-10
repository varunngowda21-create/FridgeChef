import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.auth import RefreshToken, User


def test_me_unauthenticated(client: TestClient):
    endpoints = [
        ("GET", "/api/v1/me"),
        ("PUT", "/api/v1/me/preferences"),
        ("GET", "/api/v1/me/export"),
        ("DELETE", "/api/v1/me"),
    ]
    for method, path in endpoints:
        resp = client.request(method, path)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_profile_and_preferences(client: TestClient):
    email = f"profile_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Profile Owner"},
    )
    token = reg.json()["access_token"]

    resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["email"] == email.lower()
    assert data["display_name"] == "Profile Owner"
    assert data["preferences"] is not None
    assert data["preferences"]["household_size"] == 2
    assert data["preferences"]["diet"] == "VEGETARIAN"
    assert data["preferences"]["version"] == 1


def test_update_preferences_lifecycle(client: TestClient):
    email = f"pref_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Chef Preferences"},
    )
    token = reg.json()["access_token"]

    update_payload = {
        "household_size": 4,
        "diet": "VEGAN",
        "spice_level": "HOT",
        "cuisines": ["North Indian", "South Indian"],
        "max_cooking_time": 30,
        "allergies": ["peanut", "mustard"],
        "avoided_ingredients": ["mushroom"],
    }

    put_resp = client.put(
        "/api/v1/me/preferences",
        json=update_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert put_resp.status_code == 200
    pref_data = put_resp.json()

    assert pref_data["household_size"] == 4
    assert pref_data["diet"] == "VEGAN"
    assert pref_data["spice_level"] == "HOT"
    assert pref_data["cuisines"] == ["North Indian", "South Indian"]
    assert pref_data["max_cooking_time"] == 30
    assert pref_data["allergies"] == ["peanut", "mustard"]
    assert pref_data["avoided_ingredients"] == ["mushroom"]
    assert pref_data["version"] == 2  # Incremented from 1

    # Verify GET /me returns the updated preferences
    get_resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 200
    assert get_resp.json()["preferences"]["version"] == 2


def test_update_preferences_validation_errors(client: TestClient):
    email = f"val_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Validation Tester"},
    )
    token = reg.json()["access_token"]

    # Invalid diet
    bad_diet = client.put(
        "/api/v1/me/preferences",
        json={
            "household_size": 2,
            "diet": "KETOGENIC_NOT_ALLOWED",
            "spice_level": "MEDIUM",
            "cuisines": [],
            "max_cooking_time": 45,
            "allergies": [],
            "avoided_ingredients": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_diet.status_code == 422

    # Invalid household size (< 1 or > 10)
    bad_size = client.put(
        "/api/v1/me/preferences",
        json={
            "household_size": 25,
            "diet": "VEGETARIAN",
            "spice_level": "MEDIUM",
            "cuisines": [],
            "max_cooking_time": 45,
            "allergies": [],
            "avoided_ingredients": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_size.status_code == 422

    # Unknown field rejected
    unknown_field = client.put(
        "/api/v1/me/preferences",
        json={
            "household_size": 2,
            "diet": "VEGETARIAN",
            "spice_level": "MEDIUM",
            "cuisines": [],
            "max_cooking_time": 45,
            "allergies": [],
            "avoided_ingredients": [],
            "extra_custom_setting": "malicious",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert unknown_field.status_code == 422


def test_cross_user_isolation(client: TestClient):
    # Register User A
    user_a_email = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
    reg_a = client.post(
        "/api/v1/auth/register",
        json={"email": user_a_email, "password": "Password123!", "display_name": "User A"},
    )
    token_a = reg_a.json()["access_token"]

    # Register User B
    user_b_email = f"user_b_{uuid.uuid4().hex[:8]}@example.com"
    reg_b = client.post(
        "/api/v1/auth/register",
        json={"email": user_b_email, "password": "Password123!", "display_name": "User B"},
    )
    token_b = reg_b.json()["access_token"]

    # User A updates preferences
    client.put(
        "/api/v1/me/preferences",
        json={
            "household_size": 5,
            "diet": "NON_VEGETARIAN",
            "spice_level": "HOT",
            "cuisines": ["Bengali"],
            "max_cooking_time": 60,
            "allergies": ["shellfish"],
            "avoided_ingredients": [],
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # User B queries their profile
    resp_b = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    b_data = resp_b.json()
    assert b_data["email"] == user_b_email.lower()
    assert b_data["preferences"]["household_size"] == 2
    assert b_data["preferences"]["diet"] == "VEGETARIAN"
    assert b_data["preferences"]["cuisines"] == []


def test_export_user_data(client: TestClient):
    email = f"export_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Export User"},
    )
    token = reg.json()["access_token"]

    resp = client.get("/api/v1/me/export", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    export_data = resp.json()

    assert "user" in export_data
    assert export_data["user"]["email"] == email.lower()
    assert "preferences" in export_data
    assert "inventory_items" in export_data
    assert "scan_sessions" in export_data
    assert "waste_log" in export_data
    assert "meal_plans" in export_data
    assert "shopping_lists" in export_data
    assert "cooking_events" in export_data
    assert "exported_at" in export_data


def test_delete_account_lifecycle(client: TestClient, db_session: Session):
    email = f"delete_{uuid.uuid4().hex[:8]}@example.com"
    password = "DeletePassword123!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Doomed User"},
    )
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]

    # Wrong password attempt
    bad_del = client.request(
        "DELETE",
        "/api/v1/me",
        json={"password": "WrongPassword99!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_del.status_code == 401
    assert bad_del.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # Correct password deletion request
    del_resp = client.request(
        "DELETE",
        "/api/v1/me",
        json={"password": password},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 202
    del_data = del_resp.json()
    assert del_data["status"] == "SCHEDULED"
    assert "scheduled_deletion_at" in del_data

    # Verify user record in DB has deleted_at set
    db_user = db_session.query(User).filter(User.id == uuid.UUID(user_id)).first()
    assert db_user is not None
    assert db_user.deleted_at is not None

    # Verify all refresh tokens are revoked
    tokens = db_session.query(RefreshToken).filter(RefreshToken.user_id == uuid.UUID(user_id)).all()
    assert all(t.revoked_at is not None for t in tokens)

    # Subsequent access with old token is rejected
    get_after_del = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert get_after_del.status_code == 401

    # Subsequent login attempt is rejected
    login_after_del = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_after_del.status_code == 401
