import uuid
from datetime import date

from fastapi.testclient import TestClient


def create_authenticated_user(client: TestClient) -> tuple[str, str]:
    """Helper to register a user and return (email, access_token)."""
    email = f"chef_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Test Chef"},
    )
    assert resp.status_code == 201
    return email, resp.json()["access_token"]


def test_inventory_endpoints_require_authentication(client: TestClient):
    endpoints = [
        ("GET", "/api/v1/inventory"),
        ("POST", "/api/v1/inventory"),
        ("GET", f"/api/v1/inventory/{uuid.uuid4()}"),
        ("PATCH", f"/api/v1/inventory/{uuid.uuid4()}"),
        ("POST", f"/api/v1/inventory/{uuid.uuid4()}/use"),
        ("POST", f"/api/v1/inventory/{uuid.uuid4()}/waste"),
        ("DELETE", f"/api/v1/inventory/{uuid.uuid4()}"),
    ]
    for method, path in endpoints:
        resp = client.request(method, path)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_inventory_item_success(client: TestClient):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "canonical_id": "tomato",
        "quantity": 5,
        "unit": "piece",
        "storage": "FRIDGE",
        "display_name": "Fresh Red Tomatoes",
    }
    resp = client.post("/api/v1/inventory", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["ingredient_id"] == "tomato"
    assert data["display_name"] == "Fresh Red Tomatoes"
    assert float(data["quantity"]) == 5.0
    assert data["unit"] == "piece"
    assert data["storage"] == "FRIDGE"
    assert data["shelf_life_days_estimate"] == 7
    assert data["days_left"] == 7
    assert data["status"] == "SAFE"
    assert "id" in data


def test_create_inventory_item_validations(client: TestClient):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Non-existent canonical ID
    bad_id_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "non_existent_herb", "quantity": 1, "unit": "g", "storage": "FRIDGE"},
        headers=headers,
    )
    assert bad_id_resp.status_code == 404
    assert bad_id_resp.json()["error"]["code"] == "INGREDIENT_NOT_FOUND"

    # Quantity <= 0
    bad_qty_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 0, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    )
    assert bad_qty_resp.status_code == 422

    # Storage not applicable (e.g. potato has no shelf life in FREEZER if not configured)
    # Let's test with invalid / non-applicable storage
    bad_storage_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 2, "unit": "piece", "storage": "NON_EXISTENT_LOCATION"},
        headers=headers,
    )
    assert bad_storage_resp.status_code == 422
    assert bad_storage_resp.json()["error"]["code"] == "STORAGE_NOT_APPLICABLE"

    # Future added date
    bad_date_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 2, "unit": "piece", "storage": "FRIDGE", "added_on": "2099-01-01"},
        headers=headers,
    )
    assert bad_date_resp.status_code == 422
    assert bad_date_resp.json()["error"]["code"] == "INVALID_DATE"

    # Unknown fields rejected
    unknown_resp = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 2, "unit": "piece", "storage": "FRIDGE", "extra_prop": "bad"},
        headers=headers,
    )
    assert unknown_resp.status_code == 422


def test_list_and_filter_inventory(client: TestClient):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add tomato in FRIDGE (7 days shelf life -> SAFE)
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 2, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    )

    # Add potato in PANTRY (30 days shelf life -> SAFE)
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 1000, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    )

    # List all
    list_all = client.get("/api/v1/inventory", headers=headers)
    assert list_all.status_code == 200
    all_data = list_all.json()
    assert len(all_data["items"]) == 2

    # Filter by storage
    fridge_only = client.get("/api/v1/inventory?storage=FRIDGE", headers=headers)
    assert fridge_only.status_code == 200
    assert len(fridge_only.json()["items"]) == 1
    assert fridge_only.json()["items"][0]["storage"] == "FRIDGE"

    pantry_only = client.get("/api/v1/inventory?storage=PANTRY", headers=headers)
    assert pantry_only.status_code == 200
    assert len(pantry_only.json()["items"]) == 1
    assert pantry_only.json()["items"][0]["storage"] == "PANTRY"

    # Filter by status
    safe_only = client.get("/api/v1/inventory?status=SAFE", headers=headers)
    assert safe_only.status_code == 200
    assert len(safe_only.json()["items"]) == 2

    first_only = client.get("/api/v1/inventory?status=USE_FIRST", headers=headers)
    assert first_only.status_code == 200
    assert len(first_only.json()["items"]) == 0


def test_patch_inventory_item(client: TestClient):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create item
    created = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 4, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    ).json()
    item_id = created["id"]
    assert created["days_left"] == 7

    # Update opened_on to today -> tomato opened shelf life is 3 days
    patch_resp = client.patch(
        f"/api/v1/inventory/{item_id}",
        json={"opened_on": str(date.today()), "quantity": 3},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    patched_data = patch_resp.json()
    assert float(patched_data["quantity"]) == 3.0
    assert patched_data["days_left"] == 3
    assert patched_data["status"] == "USE_SOON"


def test_delete_inventory_item(client: TestClient):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 2, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    ).json()
    item_id = created["id"]

    # Delete
    del_resp = client.delete(f"/api/v1/inventory/{item_id}", headers=headers)
    assert del_resp.status_code == 204

    # Subsequent GET returns 404
    get_resp = client.get(f"/api/v1/inventory/{item_id}", headers=headers)
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "INVENTORY_ITEM_NOT_FOUND"


def test_cross_user_inventory_isolation(client: TestClient):
    _, token_a = create_authenticated_user(client)
    _, token_b = create_authenticated_user(client)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates item
    created_a = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 5, "unit": "piece", "storage": "FRIDGE"},
        headers=headers_a,
    ).json()
    item_id_a = created_a["id"]

    # User B cannot see User A's item in list
    list_b = client.get("/api/v1/inventory", headers=headers_b)
    assert len(list_b.json()["items"]) == 0

    # User B cannot GET User A's item
    get_b = client.get(f"/api/v1/inventory/{item_id_a}", headers=headers_b)
    assert get_b.status_code == 404
    assert get_b.json()["error"]["code"] == "INVENTORY_ITEM_NOT_FOUND"

    # User B cannot PATCH User A's item
    patch_b = client.patch(
        f"/api/v1/inventory/{item_id_a}",
        json={"quantity": 10},
        headers=headers_b,
    )
    assert patch_b.status_code == 404

    # User B cannot DELETE User A's item
    del_b = client.delete(f"/api/v1/inventory/{item_id_a}", headers=headers_b)
    assert del_b.status_code == 404
