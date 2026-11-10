import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.inventory import WasteLog
from tests.test_inventory_crud import create_authenticated_user


def test_use_inventory_item_safe_status(client: TestClient, db_session: Session):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add tomato with added_on = today -> 7 days shelf life (SAFE)
    created = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 5, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    ).json()
    item_id = created["id"]
    assert created["status"] == "SAFE"

    # Use 2 pieces
    use_resp = client.post(
        f"/api/v1/inventory/{item_id}/use",
        json={"quantity": 2},
        headers=headers,
    )
    assert use_resp.status_code == 200
    data = use_resp.json()
    assert float(data["item"]["quantity"]) == 3.0
    assert float(data["quantity_used"]) == 2.0
    assert data["action_logged"] is None
    assert data["is_archived"] is False

    # Verify no WasteLog entry was created since status was SAFE
    waste_count = (
        db_session.query(WasteLog)
        .filter(WasteLog.inventory_item_id == uuid.UUID(item_id))
        .count()
    )
    assert waste_count == 0


def test_use_inventory_item_expiring_status(client: TestClient, db_session: Session):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add tomato added 6 days ago -> 1 day left (USE_FIRST)
    six_days_ago = str(date.today() - timedelta(days=6))
    created = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 4, "unit": "piece", "storage": "FRIDGE", "added_on": six_days_ago},
        headers=headers,
    ).json()
    item_id = created["id"]
    assert created["status"] == "USE_FIRST"
    assert created["days_left"] == 1

    # Use 2 pieces
    use_resp = client.post(
        f"/api/v1/inventory/{item_id}/use",
        json={"quantity": 2},
        headers=headers,
    )
    assert use_resp.status_code == 200
    data = use_resp.json()
    assert float(data["item"]["quantity"]) == 2.0
    assert data["action_logged"] == "USED_BEFORE_EXPIRY"
    assert data["is_archived"] is False

    # Verify WasteLog entry in DB
    waste_entry = (
        db_session.query(WasteLog)
        .filter(WasteLog.inventory_item_id == uuid.UUID(item_id))
        .first()
    )
    assert waste_entry is not None
    assert waste_entry.action == "USED_BEFORE_EXPIRY"
    assert waste_entry.quantity == Decimal("2")
    assert waste_entry.estimated_value_inr > Decimal("0")


def test_use_item_to_zero_archives_it(client: TestClient):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "tomato", "quantity": 2, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    ).json()
    item_id = created["id"]

    # Use all remaining 2 pieces
    use_resp = client.post(
        f"/api/v1/inventory/{item_id}/use",
        json={"quantity": 2},
        headers=headers,
    )
    assert use_resp.status_code == 200
    data = use_resp.json()
    assert float(data["item"]["quantity"]) == 0.0
    assert data["is_archived"] is True
    assert data["item"]["archived_at"] is not None

    # Excluded from active inventory list
    active_items = client.get("/api/v1/inventory", headers=headers).json()["items"]
    assert not any(i["id"] == item_id for i in active_items)


def test_waste_inventory_item(client: TestClient, db_session: Session):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Add 1000g of potato
    created = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 1000, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    ).json()
    item_id = created["id"]

    # Waste 400g
    waste_resp = client.post(
        f"/api/v1/inventory/{item_id}/waste",
        json={"quantity": 400},
        headers=headers,
    )
    assert waste_resp.status_code == 200
    w_data = waste_resp.json()
    assert float(w_data["item"]["quantity"]) == 600.0
    assert w_data["action_logged"] == "WASTED"
    assert float(w_data["quantity_wasted"]) == 400.0
    assert float(w_data["estimated_value_inr"]) > 0

    # Verify WasteLog record in DB
    waste_entry = (
        db_session.query(WasteLog)
        .filter(WasteLog.inventory_item_id == uuid.UUID(item_id))
        .first()
    )
    assert waste_entry is not None
    assert waste_entry.action == "WASTED"
    assert waste_entry.quantity == Decimal("400")


def test_waste_log_preservation_on_item_delete(client: TestClient, db_session: Session):
    _, token = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 500, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    ).json()
    item_id = created["id"]

    # Log waste for item
    client.post(
        f"/api/v1/inventory/{item_id}/waste",
        json={"quantity": 200},
        headers=headers,
    )

    # Delete the inventory item
    del_resp = client.delete(f"/api/v1/inventory/{item_id}", headers=headers)
    assert del_resp.status_code == 204

    # WasteLog should still exist in database, with inventory_item_id set to NULL
    logs = (
        db_session.query(WasteLog)
        .filter(WasteLog.ingredient_id == "potato")
        .all()
    )
    assert len(logs) >= 1
    # Latest log entry is preserved
    latest = logs[-1]
    assert latest.inventory_item_id is None
