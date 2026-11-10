"""Integration tests for shopping list aggregation per PRD Section 6.7, 8.7, 10, and 11.9."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.analytics import RecommendationCache
from app.db.models.catalogue import Recipe
from app.db.models.inventory import InventoryItem


def create_authenticated_user(client: TestClient, email_prefix: str = "shopping") -> tuple[str, str, uuid.UUID]:
    """Helper to register a user and return (email, token, user_id)."""
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Shopping Chef"},
    )
    assert resp.status_code == 201
    data = resp.json()
    return email, data["access_token"], uuid.UUID(data["user"]["id"])


def test_shopping_list_unauthenticated(client: TestClient):
    resp = client.post("/api/v1/shopping-lists", json={"source": "MANUAL"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_shopping_list_validation_errors(client: TestClient):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Missing plan_id when source is PLAN
    resp1 = client.post("/api/v1/shopping-lists", json={"source": "PLAN"}, headers=headers)
    assert resp1.status_code == 422

    # Missing recipes when source is RECIPES
    resp2 = client.post("/api/v1/shopping-lists", json={"source": "RECIPES"}, headers=headers)
    assert resp2.status_code == 422

    # Missing manual_items when source is MANUAL
    resp3 = client.post("/api/v1/shopping-lists", json={"source": "MANUAL"}, headers=headers)
    assert resp3.status_code == 422


def test_shopping_list_from_manual_items_and_inventory_subtraction(client: TestClient, db_session: Session):
    _, token, user_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add 2 tomatoes to inventory
    today = date.today()
    inv_item = InventoryItem(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="tomato",
        display_name="Tomato",
        quantity=Decimal("2"),
        unit="piece",
        storage="FRIDGE",
        added_on=today,
        shelf_life_days_estimate=7,
        expires_on=today + timedelta(days=7),
    )
    db_session.add(inv_item)
    db_session.commit()

    # Request 5 tomatoes (needed: 5 - 2 = 3) and 2 onions (needed: 2 - 0 = 2)
    manual_items = [
        {"canonical_id": "tomato", "qty": 5, "unit": "piece"},
        {"canonical_id": "onion", "qty": 2, "unit": "piece"},
    ]
    resp = client.post(
        "/api/v1/shopping-lists",
        json={"source": "MANUAL", "manual_items": manual_items},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["source"] == "MANUAL"
    assert data["total_est_cost_inr"] > 0.0

    items_by_id = {item["canonical_id"]: item for item in data["items"]}
    assert "tomato" in items_by_id
    assert items_by_id["tomato"]["quantity"] == 3.0  # 5 requested - 2 in inventory = 3
    assert items_by_id["tomato"]["bought"] is False
    assert items_by_id["tomato"]["est_cost_inr"] > 0.0

    assert "onion" in items_by_id
    assert items_by_id["onion"]["quantity"] == 2.0


def test_shopping_list_omits_items_fully_covered_by_inventory(client: TestClient, db_session: Session):
    _, token, user_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add 10 onions to inventory
    today = date.today()
    inv_item = InventoryItem(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="onion",
        display_name="Onion",
        quantity=Decimal("10"),
        unit="piece",
        storage="PANTRY",
        added_on=today,
        shelf_life_days_estimate=14,
        expires_on=today + timedelta(days=14),
    )
    db_session.add(inv_item)
    db_session.commit()

    # Request 3 onions (10 available >= 3 needed -> 0 remainder -> dropped from list)
    manual_items = [
        {"canonical_id": "onion", "qty": 3, "unit": "piece"},
    ]
    resp = client.post(
        "/api/v1/shopping-lists",
        json={"source": "MANUAL", "manual_items": manual_items},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()

    # Should be empty because all requested items are in inventory
    assert len(data["items"]) == 0
    assert data["total_est_cost_inr"] == 0.0


def test_shopping_list_from_plan(client: TestClient, db_session: Session):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a meal plan
    plan_resp = client.post("/api/v1/meal-plans", json={}, headers=headers)
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]

    # 2. Generate shopping list from plan
    shop_resp = client.post(
        "/api/v1/shopping-lists",
        json={"source": "PLAN", "plan_id": plan_id},
        headers=headers,
    )
    assert shop_resp.status_code == 201
    data = shop_resp.json()

    assert data["source"] == "PLAN"
    assert len(data["items"]) > 0
    assert data["total_est_cost_inr"] > 0.0

    # Ensure items are grouped and formatted
    for it in data["items"]:
        assert it["canonical_id"]
        assert it["category"]
        assert it["quantity"] > 0
        assert it["unit"]
        assert it["est_cost_inr"] >= 0.0
        assert it["bought"] is False


def test_shopping_list_from_recipes(client: TestClient, db_session: Session):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    recipe = db_session.query(Recipe).filter(Recipe.status == "APPROVED").first()
    assert recipe is not None

    req_body = {
        "source": "RECIPES",
        "recipes": [{"recipe_id": recipe.id, "servings": 4}],
    }
    resp = client.post("/api/v1/shopping-lists", json=req_body, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["source"] == "RECIPES"
    assert len(data["items"]) > 0


def test_patch_shopping_item_bought_and_add_to_inventory(client: TestClient, db_session: Session):
    _, token, user_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Seed recommendation cache to test invalidation
    cache_entry = RecommendationCache(
        user_id=user_id,
        cache_key="test_cache_key",
        payload={"dummy": True},
        expires_at=date.today() + timedelta(days=1),
    )
    db_session.add(cache_entry)
    db_session.commit()

    # 1. Create shopping list
    manual_items = [{"canonical_id": "ginger", "qty": 100, "unit": "g"}]
    resp = client.post(
        "/api/v1/shopping-lists",
        json={"source": "MANUAL", "manual_items": manual_items},
        headers=headers,
    )
    assert resp.status_code == 201
    list_id = resp.json()["id"]

    # 2. Patch item to bought = True without adding to inventory
    patch1 = client.patch(
        f"/api/v1/shopping-lists/{list_id}/items/ginger",
        json={"bought": True, "add_to_inventory": False},
        headers=headers,
    )
    assert patch1.status_code == 200
    ginger_item = next(it for it in patch1.json()["items"] if it["canonical_id"] == "ginger")
    assert ginger_item["bought"] is True

    # No inventory item should have been created
    inv_count = db_session.query(InventoryItem).filter(
        InventoryItem.user_id == user_id,
        InventoryItem.ingredient_id == "ginger",
    ).count()
    assert inv_count == 0

    # 3. Patch item with add_to_inventory = True
    patch2 = client.patch(
        f"/api/v1/shopping-lists/{list_id}/items/ginger",
        json={"bought": True, "add_to_inventory": True},
        headers=headers,
    )
    assert patch2.status_code == 200

    # Now inventory item exists
    inv_ginger = (
        db_session.query(InventoryItem)
        .filter(InventoryItem.user_id == user_id, InventoryItem.ingredient_id == "ginger")
        .first()
    )
    assert inv_ginger is not None
    assert inv_ginger.quantity == Decimal("100")
    assert inv_ginger.unit == "g"

    # Cache should be invalidated
    cached = (
        db_session.query(RecommendationCache)
        .filter(RecommendationCache.user_id == user_id, RecommendationCache.cache_key == "test_cache_key")
        .first()
    )
    assert cached is None


def test_shopping_list_user_isolation(client: TestClient):
    _, token1, _ = create_authenticated_user(client, "user1")
    _, token2, _ = create_authenticated_user(client, "user2")

    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    # User 1 creates shopping list
    resp = client.post(
        "/api/v1/shopping-lists",
        json={"source": "MANUAL", "manual_items": [{"canonical_id": "salt", "qty": 1, "unit": "packet"}]},
        headers=headers1,
    )
    assert resp.status_code == 201
    list_id = resp.json()["id"]

    # User 2 cannot access user 1's shopping list
    get_resp = client.get(f"/api/v1/shopping-lists/{list_id}", headers=headers2)
    assert get_resp.status_code == 404

    # User 2 cannot patch user 1's shopping list
    patch_resp = client.patch(
        f"/api/v1/shopping-lists/{list_id}/items/salt",
        json={"bought": True},
        headers=headers2,
    )
    assert patch_resp.status_code == 404
