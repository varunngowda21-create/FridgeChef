"""Comprehensive end-to-end user journey integration tests for Phase 8 audit validation.

Exercises the 10 core user journeys sequentially against the FastAPI application:
1. Registration & authentication
2. Session restoration & protected profile access
3. Dashboard & inventory loading
4. Inventory mutations (create, use, delete)
5. Scan flow (upload, candidate fetch, discard)
6. Recipe recommendations & cooking event logging
7. Weekly 14-slot meal plan creation & slot regeneration
8. Shopping list creation & bought item status update
9. Dietary preferences update & data export
10. Logout & unauthenticated route protection
"""

import io
import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from app.llm.vision import VisionItem, VisionResponse


def _create_jpeg_bytes(width: int = 400, height: int = 300) -> bytes:
    img = Image.new("RGB", (width, height), color=(180, 120, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_ten_core_user_journeys_sequential(client: TestClient):
    # -------------------------------------------------------------
    # Journey 1: Register and obtain session
    # -------------------------------------------------------------
    unique_id = uuid.uuid4().hex[:8]
    email = f"journey_{unique_id}@example.com"
    password = "SecurePassword123!"

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Journey Chef"},
    )
    assert reg_resp.status_code == 201, reg_resp.text
    reg_data = reg_resp.json()
    token = reg_data["access_token"]
    user_id = reg_data["user"]["id"]
    csrf_token = reg_resp.cookies.get("csrf_token")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # -------------------------------------------------------------
    # Journey 2: Restore session and access protected profile
    # -------------------------------------------------------------
    me_resp = client.get("/api/v1/me", headers=auth_headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == email.lower()
    assert me_data["display_name"] == "Journey Chef"
    assert me_data["preferences"]["household_size"] == 2
    assert me_data["preferences"]["diet"] == "VEGETARIAN"

    # -------------------------------------------------------------
    # Journey 3: Load dashboard and inventory
    # -------------------------------------------------------------
    dash_resp = client.get("/api/v1/dashboard", headers=auth_headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert "status_counts" in dash_data
    assert "recommendations" in dash_data

    inv_resp = client.get("/api/v1/inventory", headers=auth_headers)
    assert inv_resp.status_code == 200
    inv_data = inv_resp.json()
    assert "items" in inv_data

    # -------------------------------------------------------------
    # Journey 4: Supported inventory mutation (create, use, delete)
    # -------------------------------------------------------------
    # Add item
    add_resp = client.post(
        "/api/v1/inventory",
        json={
            "canonical_id": "spinach",
            "quantity": 300,
            "unit": "g",
            "storage": "FRIDGE",
        },
        headers=auth_headers,
    )
    assert add_resp.status_code == 201, add_resp.text
    item_id = add_resp.json()["id"]

    # Use partial quantity
    use_resp = client.post(
        f"/api/v1/inventory/{item_id}/use",
        json={"quantity": 100},
        headers=auth_headers,
    )
    assert use_resp.status_code == 200
    assert float(use_resp.json()["item"]["quantity"]) == 200.0
    assert float(use_resp.json()["quantity_used"]) == 100.0

    # Delete item
    del_resp = client.delete(f"/api/v1/inventory/{item_id}", headers=auth_headers)
    assert del_resp.status_code in (200, 204)

    # Add staple items so recommendations and meal planner have active inventory (>= 40% coverage)
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 1000, "unit": "g", "storage": "PANTRY"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "onion", "quantity": 500, "unit": "g", "storage": "PANTRY"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 500, "unit": "g", "storage": "FRIDGE"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "garlic", "quantity": 10, "unit": "piece", "storage": "PANTRY"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "ginger", "quantity": 50, "unit": "g", "storage": "FRIDGE"},
        headers=auth_headers,
    )

    # -------------------------------------------------------------
    # Journey 5: Exercise image scan flow (upload, inspect, discard)
    # -------------------------------------------------------------
    mock_vision = VisionResponse(
        items=[
            VisionItem(
                name="Fresh Tomato",
                quantity=4.0,
                unit="piece",
                storage_guess="FRIDGE",
                confidence="HIGH",
                needs_review=False,
                visible_note=None,
            )
        ],
        image_quality="GOOD",
        image_quality_note=None,
    )

    with patch("app.services.scan.call_groq_vision", new=AsyncMock(return_value=mock_vision)):
        jpeg_data = _create_jpeg_bytes()
        scan_resp = client.post(
            "/api/v1/scans",
            files={"image": ("fridge_test.jpg", jpeg_data, "image/jpeg")},
            headers=auth_headers,
        )
        assert scan_resp.status_code == 201, scan_resp.text
        scan_id = scan_resp.json()["scan_id"]

    # Retrieve candidates
    get_scan_resp = client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers)
    assert get_scan_resp.status_code == 200
    candidates = get_scan_resp.json()["candidates"]
    assert len(candidates) >= 1

    # Discard scan
    discard_resp = client.delete(f"/api/v1/scans/{scan_id}", headers=auth_headers)
    assert discard_resp.status_code == 204

    # -------------------------------------------------------------
    # Journey 6: Recommendations and recipe cooking action
    # -------------------------------------------------------------
    recs_resp = client.get("/api/v1/recommendations?limit=5", headers=auth_headers)
    assert recs_resp.status_code == 200
    recs_data = recs_resp.json()
    assert "items" in recs_data
    assert len(recs_data["items"]) > 0
    recipe_id = recs_data["items"][0]["recipe_id"]

    cook_resp = client.post(
        f"/api/v1/recipes/{recipe_id}/cooked",
        json={"servings": 2, "rating": 5},
        headers=auth_headers,
    )
    assert cook_resp.status_code == 201
    cook_data = cook_resp.json()
    assert cook_data["recipe_id"] == recipe_id
    assert cook_data["rating"] == 5

    # -------------------------------------------------------------
    # Journey 7: Weekly meal plan creation & slot regeneration
    # -------------------------------------------------------------
    plan_resp = client.post(
        "/api/v1/meal-plans",
        json={},
        headers=auth_headers,
    )
    assert plan_resp.status_code == 201, plan_resp.text
    plan_data = plan_resp.json()
    plan_id = plan_data["id"]
    slots = plan_data["plan"]["slots"]
    # Verify exactly 14 slots (7 days * 2 meals: Lunch and Dinner)
    assert len(slots) == 14
    lunch_count = sum(1 for s in slots if s["meal"] == "LUNCH")
    dinner_count = sum(1 for s in slots if s["meal"] == "DINNER")
    assert lunch_count == 7
    assert dinner_count == 7

    # Retrieve active meal plan
    active_plan_resp = client.get("/api/v1/meal-plans/active", headers=auth_headers)
    assert active_plan_resp.status_code == 200
    assert active_plan_resp.json()["id"] == plan_id

    # Regenerate a single slot (Day 1 Dinner)
    regen_resp = client.post(
        f"/api/v1/meal-plans/{plan_id}/slots/1/DINNER/regenerate",
        headers=auth_headers,
    )
    assert regen_resp.status_code == 200
    regen_slots = regen_resp.json()["plan"]["slots"]
    assert len(regen_slots) == 14

    # -------------------------------------------------------------
    # Journey 8: Shopping list creation & bought item status update
    # -------------------------------------------------------------
    shop_resp = client.post(
        "/api/v1/shopping-lists",
        json={"source": "PLAN", "plan_id": plan_id},
        headers=auth_headers,
    )
    assert shop_resp.status_code == 201, shop_resp.text
    shop_data = shop_resp.json()
    shop_id = shop_data["id"]

    if shop_data["items"]:
        first_item = shop_data["items"][0]
        cid = first_item["canonical_id"]
        patch_resp = client.patch(
            f"/api/v1/shopping-lists/{shop_id}/items/{cid}",
            json={"bought": True, "add_to_inventory": True},
            headers=auth_headers,
        )
        assert patch_resp.status_code == 200
        patched_item = next(i for i in patch_resp.json()["items"] if i["canonical_id"] == cid)
        assert patched_item["bought"] is True

    # -------------------------------------------------------------
    # Journey 9: Dietary preferences update & data export
    # -------------------------------------------------------------
    pref_update_resp = client.put(
        "/api/v1/me/preferences",
        json={
            "household_size": 4,
            "diet": "VEGAN",
            "spice_level": "HOT",
            "cuisines": ["North Indian", "South Indian"],
            "max_cooking_time": 30,
            "allergies": ["peanut"],
            "avoided_ingredients": ["mushroom"],
        },
        headers=auth_headers,
    )
    assert pref_update_resp.status_code == 200
    updated_pref = pref_update_resp.json()
    assert updated_pref["household_size"] == 4
    assert updated_pref["diet"] == "VEGAN"
    assert updated_pref["version"] == 2

    # Export personal data
    export_resp = client.get("/api/v1/me/export", headers=auth_headers)
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data["user"]["id"] == user_id
    assert export_data["preferences"]["diet"] == "VEGAN"
    assert "exported_at" in export_data

    # -------------------------------------------------------------
    # Journey 10: Logout and verify protected route returns 401
    # -------------------------------------------------------------
    logout_headers = {"X-CSRF-Token": csrf_token, **auth_headers} if csrf_token else auth_headers
    logout_resp = client.post("/api/v1/auth/logout", headers=logout_headers)
    assert logout_resp.status_code == 204

    # Unauthenticated request to /me must fail
    unauth_resp = client.get("/api/v1/me")
    assert unauth_resp.status_code == 401
    assert unauth_resp.json()["error"]["code"] == "UNAUTHORIZED"
