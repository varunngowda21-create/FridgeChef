"""Integration tests for the dashboard synthesis endpoint per PRD Section 6.8, 11.10, and 12.3."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.auth import User
from app.db.models.inventory import InventoryItem, WasteLog


def create_authenticated_user(client: TestClient, email_prefix: str = "dash") -> tuple[str, str, uuid.UUID]:
    """Helper to register a user and return (email, token, user_id)."""
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Dashboard Chef"},
    )
    assert resp.status_code == 201
    data = resp.json()
    return email, data["access_token"], uuid.UUID(data["user"]["id"])


def test_dashboard_unauthenticated(client: TestClient):
    resp = client.get("/api/v1/dashboard")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_dashboard_empty_initial_state(client: TestClient):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "status_counts" in data
    assert data["status_counts"]["USE_FIRST"] == 0
    assert data["status_counts"]["USE_SOON"] == 0
    assert data["status_counts"]["SAFE"] == 0
    assert data["status_counts"]["TOTAL"] == 0

    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)

    assert data["active_plan"] is None

    assert "impact" in data
    assert data["impact"]["waste_prevented_kg"] == 0.0
    assert data["impact"]["food_wasted_kg"] == 0.0
    assert data["impact"]["money_saved_inr"] == 0.0
    assert data["impact"]["is_estimate"] is True


def test_dashboard_with_inventory_freshness_counts(client: TestClient, db_session: Session):
    _, token, user_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()

    # 1. Item expiring tomorrow -> USE_FIRST (spinach shelf life in FRIDGE is 4 days, added 3 days ago -> 1 day left)
    item_first = InventoryItem(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="spinach",
        display_name="Spinach",
        quantity=Decimal("200"),
        unit="g",
        storage="FRIDGE",
        added_on=today - timedelta(days=3),
        shelf_life_days_estimate=4,
        expires_on=today + timedelta(days=1),
    )
    # 2. Item expiring in 2 days -> USE_SOON (spinach in FRIDGE, added 2 days ago -> 2 days left)
    item_soon = InventoryItem(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="spinach",
        display_name="Spinach Soon",
        quantity=Decimal("150"),
        unit="g",
        storage="FRIDGE",
        added_on=today - timedelta(days=2),
        shelf_life_days_estimate=4,
        expires_on=today + timedelta(days=2),
    )
    # 3. Item expiring in 14 days -> SAFE (onion in PANTRY, added today -> 14 days left)
    item_safe = InventoryItem(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="onion",
        display_name="Onion",
        quantity=Decimal("4"),
        unit="piece",
        storage="PANTRY",
        added_on=today,
        shelf_life_days_estimate=14,
        expires_on=today + timedelta(days=14),
    )
    # 4. Item with invalid/unmapped storage location to verify exception fallback
    item_fallback = InventoryItem(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="onion",
        display_name="Onion Unknown Storage",
        quantity=Decimal("1"),
        unit="piece",
        storage="INVALID_STORAGE_LOCATION",
        added_on=today,
    )

    db_session.add_all([item_first, item_soon, item_safe, item_fallback])
    db_session.commit()

    resp = client.get("/api/v1/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    counts = data["status_counts"]
    assert counts["TOTAL"] == 4
    assert counts["USE_FIRST"] == 1
    assert counts["USE_SOON"] == 1
    assert counts["SAFE"] == 2  # item_safe + item_fallback safely caught in exception


def test_dashboard_active_plan_summary_and_today_meals(client: TestClient, db_session: Session):
    _, token, _ = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Generate a meal plan starting today
    today = date.today()
    plan_resp = client.post(
        "/api/v1/meal-plans",
        json={"start_date": today.isoformat()},
        headers=headers,
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]

    resp = client.get("/api/v1/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    active_plan = data["active_plan"]
    assert active_plan is not None
    assert active_plan["id"] == plan_id
    assert active_plan["days_count"] == 7
    assert isinstance(active_plan["today_meals"], list)
    # Today should have 2 meals (LUNCH and DINNER)
    assert len(active_plan["today_meals"]) == 2


def test_dashboard_month_to_date_impact_calculation(client: TestClient, db_session: Session):
    _, token, user_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    now = datetime.now(timezone.utc)

    # 1. Used before expiry this month: 500g tomato, saved 25 INR
    log_used = WasteLog(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="tomato",
        quantity=Decimal("500"),
        unit="g",
        action="USED_BEFORE_EXPIRY",
        estimated_value_inr=Decimal("25.0"),
        created_at=now,
    )

    # 2. Wasted this month: 300g spinach
    log_wasted = WasteLog(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="spinach",
        quantity=Decimal("300"),
        unit="g",
        action="WASTED",
        estimated_value_inr=Decimal("15.0"),
        created_at=now,
    )

    # 3. Log from previous month (should be excluded)
    last_month = (now.replace(day=1) - timedelta(days=10)).replace(tzinfo=timezone.utc)
    log_old = WasteLog(
        id=uuid.uuid4(),
        user_id=user_id,
        ingredient_id="onion",
        quantity=Decimal("1000"),
        unit="g",
        action="USED_BEFORE_EXPIRY",
        estimated_value_inr=Decimal("40.0"),
        created_at=last_month,
    )

    db_session.add_all([log_used, log_wasted, log_old])
    db_session.commit()

    resp = client.get("/api/v1/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    impact = data["impact"]
    assert impact["is_estimate"] is True
    assert impact["waste_prevented_kg"] == 0.5  # 500g = 0.5kg
    assert impact["food_wasted_kg"] == 0.3      # 300g = 0.3kg
    assert impact["money_saved_inr"] == 25.0    # 25 INR (old 40 INR excluded)


@pytest.mark.asyncio
async def test_get_dashboard_data_direct_service_invocation(db_session: Session):
    from unittest.mock import patch

    from app.services.dashboard import get_dashboard_data

    # Create user directly in db
    user = User(
        id=uuid.uuid4(),
        email=f"direct_dash_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="fakehash",
        display_name="Direct Dash User",
    )
    db_session.add(user)
    db_session.commit()

    # Call with settings=None to test default settings initialization
    data = await get_dashboard_data(db=db_session, user=user, settings=None)
    assert data.status_counts.TOTAL == 0
    assert data.impact.is_estimate is True

    # Test recommendation exception fallback
    with patch("app.services.dashboard.get_recommendations", side_effect=RuntimeError("Groq Down")):
        data_err = await get_dashboard_data(db=db_session, user=user, settings=None)
        assert data_err.recommendations == []

    # Test active meal plan general exception fallback
    with patch("app.services.dashboard.get_active_meal_plan", side_effect=RuntimeError("DB plan error")):
        data_plan_err = await get_dashboard_data(db=db_session, user=user, settings=None)
        assert data_plan_err.active_plan is None

