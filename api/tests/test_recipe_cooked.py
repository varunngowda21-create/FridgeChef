"""Integration tests for recipe cooking action and inventory decrements per PRD Section 11.7."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.analytics import RecommendationCache
from app.db.models.auth import User
from app.db.models.catalogue import Recipe
from app.db.models.inventory import CookingEvent, InventoryItem, WasteLog


def create_authenticated_user(client: TestClient) -> tuple[str, str]:
    """Helper to register a user and return (email, access_token)."""
    email = f"cook_chef_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Cooking Chef"},
    )
    assert resp.status_code == 201
    return email, resp.json()["access_token"]


def test_cooking_action_requires_authentication(client: TestClient):
    resp = client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 2})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_cooking_action_non_existent_recipe(client: TestClient):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/recipes/non_existent_recipe_12345/cooked", json={"servings": 2}, headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RECIPE_NOT_FOUND"


def test_cooking_action_validation_errors(client: TestClient):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # servings = 0
    resp1 = client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 0}, headers=headers)
    assert resp1.status_code == 422

    # rating = 6 (> 5)
    resp2 = client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 2, "rating": 6}, headers=headers)
    assert resp2.status_code == 422

    # rating = 0 (< 1)
    resp3 = client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 2, "rating": 0}, headers=headers)
    assert resp3.status_code == 422


def test_cooking_action_decrements_inventory_and_logs_waste_prevention(client: TestClient, db_session: Session):
    """Verify inventory quantity decrements, archiving on 0, and waste log generation for USE_FIRST/USE_SOON items."""
    email, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None

    # Find a recipe with known base_servings (dal_tadka has base_servings: 4, toor_dal: 150g, onion: 1 piece, tomato: 2 piece)
    recipe = db_session.query(Recipe).filter(Recipe.id == "dal_tadka").first()
    assert recipe is not None

    # 1. Add expiring tomato (opened 5 days ago in fridge -> shelf life 5 days -> 0 or 1 day left -> USE_FIRST)
    past_date = date.today() - timedelta(days=5)
    inv_tomato_resp = client.post(
        "/api/v1/inventory",
        json={
            "canonical_id": "tomato",
            "quantity": 2,
            "unit": "piece",
            "storage": "FRIDGE",
            "opened_on": past_date.isoformat(),
            "added_on": past_date.isoformat(),
        },
        headers=headers,
    )
    assert inv_tomato_resp.status_code == 201
    tomato_id = inv_tomato_resp.json()["id"]
    assert inv_tomato_resp.json()["status"] in ("USE_FIRST", "USE_SOON")

    # 2. Add fresh safe toor_dal (pantry shelf life > 300 days -> SAFE)
    inv_dal_resp = client.post(
        "/api/v1/inventory",
        json={
            "canonical_id": "toor_dal",
            "quantity": 300,
            "unit": "g",
            "storage": "PANTRY",
        },
        headers=headers,
    )
    assert inv_dal_resp.status_code == 201
    dal_id = inv_dal_resp.json()["id"]
    assert inv_dal_resp.json()["status"] == "SAFE"

    # Cook for 4 servings (scale_factor = 4/4 = 1.0)
    # This requires 150g toor_dal and 2 pieces tomato
    cook_resp = client.post(
        "/api/v1/recipes/dal_tadka/cooked",
        json={"servings": 4, "rating": 5},
        headers=headers,
    )
    assert cook_resp.status_code == 201
    cook_data = cook_resp.json()

    assert cook_data["recipe_id"] == "dal_tadka"
    assert cook_data["servings"] == 4
    assert cook_data["rating"] == 5
    assert cook_data["decremented_items_count"] >= 2
    assert cook_data["waste_prevented_logged"] is True
    assert "event_id" in cook_data

    # Verify Tomato item is completely consumed (2 - 2 = 0) and archived
    tomato_item = db_session.query(InventoryItem).filter(InventoryItem.id == uuid.UUID(tomato_id)).first()
    assert tomato_item is not None
    assert tomato_item.quantity == Decimal("0.0")
    assert tomato_item.archived_at is not None

    # Verify Toor Dal item is partially consumed (300 - 150 = 150) and active
    dal_item = db_session.query(InventoryItem).filter(InventoryItem.id == uuid.UUID(dal_id)).first()
    assert dal_item is not None
    assert float(dal_item.quantity) == 150.0
    assert dal_item.archived_at is None

    # Verify WasteLog entry created for Tomato (which was USE_FIRST), but NOT for safe Toor Dal
    waste_entries = db_session.query(WasteLog).filter(WasteLog.user_id == user.id).all()
    assert len(waste_entries) >= 1
    tomato_waste = next((w for w in waste_entries if w.ingredient_id == "tomato"), None)
    assert tomato_waste is not None
    assert tomato_waste.action == "USED_BEFORE_EXPIRY"
    assert tomato_waste.quantity == Decimal("2.0")
    assert tomato_waste.estimated_value_inr > Decimal("0.0")

    # Verify CookingEvent was recorded in DB
    event = db_session.query(CookingEvent).filter(CookingEvent.id == uuid.UUID(cook_data["event_id"])).first()
    assert event is not None
    assert event.user_id == user.id
    assert event.recipe_id == "dal_tadka"
    assert event.servings == 4
    assert event.rating == 5


def test_cooking_uses_items_closest_to_expiry_first(client: TestClient, db_session: Session):
    """When a user has multiple inventory batches of an ingredient, the one closest to expiry is consumed first."""
    email, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Batch 1: Expiring in 2 days (USE_SOON)
    past_date = date.today() - timedelta(days=4)
    resp1 = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 1, "unit": "piece", "storage": "FRIDGE", "opened_on": past_date.isoformat(), "added_on": past_date.isoformat()},
        headers=headers,
    )
    b1_id = resp1.json()["id"]

    # Batch 2: Fresh tomato expiring in 7 days (SAFE)
    resp2 = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 5, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    )
    b2_id = resp2.json()["id"]

    # Dal Tadka base_servings is 4 (uses 2 pieces of tomato)
    # Scaling to 2 servings requires 1 piece of tomato (scale_factor = 2/4 = 0.5; 2 * 0.5 = 1 piece)
    client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 2}, headers=headers)

    # Batch 1 (closer to expiry) should be consumed to 0 and archived
    b1_item = db_session.query(InventoryItem).filter(InventoryItem.id == uuid.UUID(b1_id)).first()
    assert b1_item is not None
    assert b1_item.quantity == Decimal("0.0")
    assert b1_item.archived_at is not None

    # Batch 2 (fresher) should remain untouched (5 pieces)
    b2_item = db_session.query(InventoryItem).filter(InventoryItem.id == uuid.UUID(b2_id)).first()
    assert b2_item is not None
    assert b2_item.quantity == Decimal("5.0")
    assert b2_item.archived_at is None


def test_cooking_invalidates_recommendation_cache(client: TestClient, db_session: Session):
    """Verify that cooking a recipe invalidates recommendation cache."""
    email, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None

    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 10, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    )

    # 1. Warm recommendation cache
    r1 = client.get("/api/v1/recommendations", headers=headers)
    assert r1.json()["cache"] == "MISS"
    r2 = client.get("/api/v1/recommendations", headers=headers)
    assert r2.json()["cache"] == "HIT"

    # 2. Cook a recipe
    client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 2}, headers=headers)

    # 3. Cache must be cleared
    cache_rows = db_session.query(RecommendationCache).filter(RecommendationCache.user_id == user.id).all()
    assert len(cache_rows) == 0

    # Next call is MISS
    r3 = client.get("/api/v1/recommendations", headers=headers)
    assert r3.json()["cache"] == "MISS"


def test_cooking_atomic_transaction_rollback_on_failure(client: TestClient, db_session: Session):
    """Verify transactional atomicity: if an exception happens during cooking, changes are rolled back."""
    email, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None

    inv_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 5, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    )
    inv_id = inv_resp.json()["id"]

    # Force an unexpected DB error during cooking commit
    with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("Simulated database failure")):
        resp = client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 4}, headers=headers)
        assert resp.status_code == 500

    # Verify inventory was NOT decremented
    db_session.rollback()
    item = db_session.query(InventoryItem).filter(InventoryItem.id == uuid.UUID(inv_id)).first()
    assert item is not None
    assert float(item.quantity) == 5.0
    assert item.archived_at is None

    # Verify no cooking event persisted
    events = db_session.query(CookingEvent).filter(CookingEvent.user_id == user.id).all()
    assert len(events) == 0


def test_cooking_with_unit_conversion(client: TestClient, db_session: Session):
    """Verify that cooking decrements inventory properly when recipe unit and inventory unit differ."""
    email, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Tomato catalogue has grams_per_piece = 90g
    # Add tomato in grams: 180g (which is 2 pieces)
    inv_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 180, "unit": "g", "storage": "FRIDGE"},
        headers=headers,
    )
    assert inv_resp.status_code == 201
    item_id = inv_resp.json()["id"]

    # Dal tadka has base_servings = 4 and requires 2 pieces of tomato
    # Cooking for 2 servings requires 1 piece (scale_factor = 0.5, 2 * 0.5 = 1 piece = 90g)
    cook_resp = client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 2}, headers=headers)
    assert cook_resp.status_code == 201

    item = db_session.query(InventoryItem).filter(InventoryItem.id == uuid.UUID(item_id)).first()
    assert item is not None
    # 180g - 90g = 90g remaining
    assert float(item.quantity) == 90.0
    assert item.archived_at is None


def test_cooking_default_servings_and_flooring_at_zero(client: TestClient, db_session: Session):
    """Verify cooking with default servings (omitted from request body) and inventory floored at zero."""
    email, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add 1 piece tomato (recipe dal_tadka base 4 servings needs 2 pieces)
    inv_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 1, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    )
    item_id = inv_resp.json()["id"]

    # Post cooking without specifying servings -> defaults to household_size (default 2)
    # For 2 servings, dal tadka needs 1 piece of tomato -> consumes exactly 1 piece
    cook_resp = client.post("/api/v1/recipes/dal_tadka/cooked", json={}, headers=headers)
    assert cook_resp.status_code == 201
    assert cook_resp.json()["servings"] == 2

    item = db_session.query(InventoryItem).filter(InventoryItem.id == uuid.UUID(item_id)).first()
    assert item is not None
    assert item.quantity == Decimal("0.0")
    assert item.archived_at is not None

    # Cook again when inventory is 0 -> decrements what is available, floored at 0 without error
    cook_resp2 = client.post("/api/v1/recipes/dal_tadka/cooked", json={"servings": 4}, headers=headers)
    assert cook_resp2.status_code == 201

