"""Integration tests for recommendations API and 30-minute caching per PRD Section 11.6 and FR-046."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.analytics import RecommendationCache


def create_authenticated_user(client: TestClient) -> tuple[str, str]:
    """Helper to register a user and return (email, access_token)."""
    email = f"rec_chef_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Rec Chef"},
    )
    assert resp.status_code == 201
    return email, resp.json()["access_token"]


def test_recommendations_require_authentication(client: TestClient):
    resp = client.get("/api/v1/recommendations")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_recommendations_empty_inventory(client: TestClient):
    """With empty inventory, user has 0% coverage on all recipes (below 40% threshold), so items is empty."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/recommendations", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["degraded"] is False
    assert data["cache"] == "MISS"
    assert "generated_at" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 0


def test_recommendations_with_matching_inventory_and_caching(client: TestClient, db_session: Session):
    """Test recommendations flow, response shape, and cache HIT/MISS behavior."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add items to inventory matching common Indian recipes (e.g. potato, tomato, onion, cumin_seeds, garlic, ginger)
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 1000, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 500, "unit": "g", "storage": "FRIDGE"},
        headers=headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "onion", "quantity": 500, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "cumin_seeds", "quantity": 100, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "garlic", "quantity": 10, "unit": "piece", "storage": "PANTRY"},
        headers=headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "ginger", "quantity": 100, "unit": "g", "storage": "FRIDGE"},
        headers=headers,
    )

    # First call: cache MISS
    resp1 = client.get("/api/v1/recommendations?limit=5", headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()

    assert data1["cache"] == "MISS"
    assert data1["degraded"] is False
    assert len(data1["items"]) > 0
    assert len(data1["items"]) <= 5

    first_item = data1["items"][0]
    assert "recipe_id" in first_item
    assert "title" in first_item
    assert "cuisine" in first_item
    assert "cooking_time_minutes" in first_item
    assert "servings" in first_item
    assert first_item["match_percent"] >= 40
    assert first_item["source"] == "CURATED"
    assert "uses_expiring" in first_item
    assert "missing" in first_item
    assert "missing_cost_inr" in first_item
    assert "reason" in first_item
    assert len(first_item["reason"]) > 0

    # Second call: cache HIT
    resp2 = client.get("/api/v1/recommendations?limit=5", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["cache"] == "HIT"
    assert len(data2["items"]) == len(data1["items"])
    assert data2["items"][0]["recipe_id"] == data1["items"][0]["recipe_id"]


def test_cache_invalidation_on_inventory_mutation(client: TestClient):
    """Verify that adding, updating, or deleting inventory items invalidates recommendation cache."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add initial inventory
    inv_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 500, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    )
    item_id = inv_resp.json()["id"]

    # 1. Warm cache
    r1 = client.get("/api/v1/recommendations", headers=headers)
    assert r1.json()["cache"] == "MISS"

    r2 = client.get("/api/v1/recommendations", headers=headers)
    assert r2.json()["cache"] == "HIT"

    # 2. Mutate inventory via PATCH
    client.patch(
        f"/api/v1/inventory/{item_id}",
        json={"quantity": 1000},
        headers=headers,
    )

    # Next call must be MISS
    r3 = client.get("/api/v1/recommendations", headers=headers)
    assert r3.json()["cache"] == "MISS"

    # Now warm again
    r4 = client.get("/api/v1/recommendations", headers=headers)
    assert r4.json()["cache"] == "HIT"

    # 3. Mutate inventory via DELETE
    client.delete(f"/api/v1/inventory/{item_id}", headers=headers)

    # Next call must be MISS
    r5 = client.get("/api/v1/recommendations", headers=headers)
    assert r5.json()["cache"] == "MISS"


def test_cache_invalidation_on_preference_update(client: TestClient):
    """Verify that updating user preferences immediately invalidates recommendation cache."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 1000, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    )

    # Warm cache
    r1 = client.get("/api/v1/recommendations", headers=headers)
    assert r1.json()["cache"] == "MISS"

    r2 = client.get("/api/v1/recommendations", headers=headers)
    assert r2.json()["cache"] == "HIT"

    # Update preferences
    pref_update = {
        "household_size": 4,
        "diet": "VEGETARIAN",
        "spice_level": "HOT",
        "cuisines": ["South Indian"],
        "max_cooking_time": 60,
        "allergies": [],
        "avoided_ingredients": [],
    }
    pref_resp = client.put("/api/v1/me/preferences", json=pref_update, headers=headers)
    assert pref_resp.status_code == 200

    # Next call must be MISS and scale to new household size (4)
    r3 = client.get("/api/v1/recommendations", headers=headers)
    assert r3.json()["cache"] == "MISS"


def test_cache_expiration(client: TestClient, db_session: Session):
    """Verify that a cached entry with expires_at in the past is treated as a MISS."""
    from app.db.models.auth import User

    email, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 1000, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    )

    # Warm cache
    r1 = client.get("/api/v1/recommendations", headers=headers)
    assert r1.json()["cache"] == "MISS"

    r2 = client.get("/api/v1/recommendations", headers=headers)
    assert r2.json()["cache"] == "HIT"

    # Force expiration in DB
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    db_session.query(RecommendationCache).filter(
        RecommendationCache.user_id == user.id
    ).update({"expires_at": datetime.now(timezone.utc) - timedelta(minutes=5)})
    db_session.commit()

    # Next call must be MISS
    r3 = client.get("/api/v1/recommendations", headers=headers)
    assert r3.json()["cache"] == "MISS"


def test_recommendation_rate_limiting(client: TestClient):
    """Verify that exceeding 60 recommendation requests per hour returns HTTP 429."""
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(60):
        resp = client.get("/api/v1/recommendations", headers=headers)
        assert resp.status_code == 200

    # 61st request triggers rate limit
    resp_blocked = client.get("/api/v1/recommendations", headers=headers)
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp_blocked.headers
