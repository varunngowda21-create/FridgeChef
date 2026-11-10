"""Integration tests for weekly meal planner per PRD Section 6.6, 8.6, 10, and 11.8."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.catalogue import Recipe
from app.db.models.inventory import InventoryItem


def create_authenticated_user(client: TestClient, email_prefix: str = "planner") -> tuple[str, str, uuid.UUID]:
    """Helper to register a user and return (email, token, user_id)."""
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Planner Chef"},
    )
    assert resp.status_code == 201
    data = resp.json()
    return email, data["access_token"], uuid.UUID(data["user"]["id"])


def test_meal_plan_unauthenticated(client: TestClient):
    resp = client.post("/api/v1/meal-plans", json={})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"

    resp2 = client.get("/api/v1/meal-plans/active")
    assert resp2.status_code == 401


def test_meal_plan_validation_errors(client: TestClient):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Invalid day < 1
    resp1 = client.post(
        "/api/v1/meal-plans",
        json={"locked_slots": [{"day": 0, "meal": "LUNCH", "recipe_id": "aloo_gobi"}]},
        headers=headers,
    )
    assert resp1.status_code == 422

    # Invalid day > 7
    resp2 = client.post(
        "/api/v1/meal-plans",
        json={"locked_slots": [{"day": 8, "meal": "LUNCH", "recipe_id": "aloo_gobi"}]},
        headers=headers,
    )
    assert resp2.status_code == 422


def test_generate_weekly_meal_plan_structure_and_constraints(client: TestClient, db_session: Session):
    _, token, user_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add expiring items into inventory to test prioritization
    today = date.today()
    item1 = InventoryItem(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="spinach",
        display_name="Fresh Spinach",
        quantity=Decimal("300"),
        unit="g",
        storage="FRIDGE",
        added_on=today - timedelta(days=2),
        shelf_life_days_estimate=3,
        expires_on=today + timedelta(days=1),
    )
    db_session.add(item1)
    db_session.commit()

    resp = client.post("/api/v1/meal-plans", json={}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert "id" in data
    assert data["status"] == "ACTIVE"
    plan_payload = data["plan"]
    assert "slots" in plan_payload
    assert "shopping_list" in plan_payload
    assert "total_waste_prevented_kg" in plan_payload

    slots = plan_payload["slots"]
    assert len(slots) == 14  # 7 days * 2 meals (LUNCH, DINNER)

    # Check slot properties
    recipe_counts: dict[str, int] = {}
    for i, slot in enumerate(slots):
        assert 1 <= slot["day"] <= 7
        assert slot["meal"] in ("LUNCH", "DINNER")
        assert "recipe_id" in slot
        assert "recipe_title" in slot
        assert slot["servings"] >= 1
        assert isinstance(slot["prioritised_ingredients"], list)
        assert slot["waste_prevented_g"] >= 0.0

        r_id = slot["recipe_id"]
        recipe_counts[r_id] = recipe_counts.get(r_id, 0) + 1

        # Check no consecutive meals have the same recipe (unless catalogue is extremely small)
        if i > 0 and not data["low_variety"]:
            prev_slot = slots[i - 1]
            assert r_id != prev_slot["recipe_id"], f"Consecutive slots have same recipe: {r_id}"

    # Normal mode check: max 2 repeats per week (unless low_variety)
    if not data["low_variety"]:
        for r_id, count in recipe_counts.items():
            assert count <= 2, f"Recipe {r_id} repeated {count} times (max 2 allowed)"


def test_meal_plan_locked_slots_preservation(client: TestClient, db_session: Session):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch an approved recipe slug
    recipe = db_session.query(Recipe).filter(Recipe.status == "APPROVED").first()
    assert recipe is not None

    locked = [
        {"day": 2, "meal": "DINNER", "recipe_id": recipe.id},
        {"day": 5, "meal": "LUNCH", "recipe_id": recipe.id},
    ]

    resp = client.post(
        "/api/v1/meal-plans",
        json={"locked_slots": locked},
        headers=headers,
    )
    assert resp.status_code == 201
    slots = resp.json()["plan"]["slots"]

    day2_dinner = next(s for s in slots if s["day"] == 2 and s["meal"] == "DINNER")
    assert day2_dinner["recipe_id"] == recipe.id

    day5_lunch = next(s for s in slots if s["day"] == 5 and s["meal"] == "LUNCH")
    assert day5_lunch["recipe_id"] == recipe.id


def test_regenerate_single_plan_slot(client: TestClient, db_session: Session):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create plan
    resp = client.post("/api/v1/meal-plans", json={}, headers=headers)
    assert resp.status_code == 201
    plan_id = resp.json()["id"]
    original_slots = resp.json()["plan"]["slots"]

    # Target slot: day 3, LUNCH
    target_day = 3
    target_meal = "LUNCH"

    # 2. Regenerate slot
    regen_resp = client.post(
        f"/api/v1/meal-plans/{plan_id}/slots/{target_day}/{target_meal}/regenerate",
        headers=headers,
    )
    assert regen_resp.status_code == 200
    new_slots = regen_resp.json()["plan"]["slots"]
    assert len(new_slots) == 14

    # 3. Verify other 13 slots remain unchanged
    for idx in range(14):
        orig = original_slots[idx]
        updated = new_slots[idx]
        if orig["day"] == target_day and orig["meal"] == target_meal:
            # Target slot is present
            assert updated["day"] == target_day
            assert updated["meal"] == target_meal
        else:
            assert orig["recipe_id"] == updated["recipe_id"]
            assert orig["day"] == updated["day"]
            assert orig["meal"] == updated["meal"]
            assert orig["servings"] == updated["servings"]


def test_active_plan_lifecycle_and_archiving(client: TestClient, db_session: Session):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Initially no active plan -> 404
    resp_init = client.get("/api/v1/meal-plans/active", headers=headers)
    assert resp_init.status_code == 404
    assert resp_init.json()["error"]["code"] == "MEAL_PLAN_NOT_FOUND"

    # Generate plan 1
    resp_plan1 = client.post("/api/v1/meal-plans", json={}, headers=headers)
    assert resp_plan1.status_code == 201
    plan1_id = resp_plan1.json()["id"]

    # Active plan is plan 1
    resp_act1 = client.get("/api/v1/meal-plans/active", headers=headers)
    assert resp_act1.status_code == 200
    assert resp_act1.json()["id"] == plan1_id

    # Generate plan 2 -> plan 1 is archived
    resp_plan2 = client.post("/api/v1/meal-plans", json={}, headers=headers)
    assert resp_plan2.status_code == 201
    plan2_id = resp_plan2.json()["id"]
    assert plan2_id != plan1_id

    # Active plan is now plan 2
    resp_act2 = client.get("/api/v1/meal-plans/active", headers=headers)
    assert resp_act2.status_code == 200
    assert resp_act2.json()["id"] == plan2_id

    # Plan 1 still retrievable by ID, status ARCHIVED
    resp_p1 = client.get(f"/api/v1/meal-plans/{plan1_id}", headers=headers)
    assert resp_p1.status_code == 200
    assert resp_p1.json()["status"] == "ARCHIVED"

    # Archive plan 2 explicitly (DELETE)
    del_resp = client.delete(f"/api/v1/meal-plans/{plan2_id}", headers=headers)
    assert del_resp.status_code == 204

    # Now no active plan
    resp_act3 = client.get("/api/v1/meal-plans/active", headers=headers)
    assert resp_act3.status_code == 404


def test_meal_plan_user_isolation(client: TestClient):
    _, token_user1, _ = create_authenticated_user(client, "user1")
    _, token_user2, _ = create_authenticated_user(client, "user2")

    headers1 = {"Authorization": f"Bearer {token_user1}"}
    headers2 = {"Authorization": f"Bearer {token_user2}"}

    # User 1 creates a meal plan
    resp = client.post("/api/v1/meal-plans", json={}, headers=headers1)
    assert resp.status_code == 201
    plan_id = resp.json()["id"]

    # User 2 cannot access user 1's plan
    get_resp = client.get(f"/api/v1/meal-plans/{plan_id}", headers=headers2)
    assert get_resp.status_code == 404

    # User 2 cannot regenerate user 1's plan
    regen_resp = client.post(f"/api/v1/meal-plans/{plan_id}/slots/1/LUNCH/regenerate", headers=headers2)
    assert regen_resp.status_code == 404

    # User 2 cannot archive user 1's plan
    del_resp = client.delete(f"/api/v1/meal-plans/{plan_id}", headers=headers2)
    assert del_resp.status_code == 404
