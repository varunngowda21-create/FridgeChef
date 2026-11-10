"""Tests for database seeding safety, idempotency, and user data preservation.

PRD References: Section 8.3, 10.2, 13.4, 15.1.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.auth import User
from app.db.models.catalogue import Ingredient, Recipe, ShelfLife
from app.db.models.inventory import InventoryItem
from app.services.recipe_catalogue import seed_catalogue_data


def test_seed_catalogue_idempotency(db_session: Session):
    """Verify that seeding repeatedly does not duplicate rows or corrupt catalogue data."""
    # 1. First seeding execution
    ing_count_1, sl_count_1, rec_count_1 = seed_catalogue_data(db_session)
    assert ing_count_1 >= 200, f"Expected at least 200 ingredients, got {ing_count_1}"
    assert sl_count_1 > 0
    assert rec_count_1 >= 50

    total_ingredients_1 = db_session.scalar(select(func.count(Ingredient.id)))
    total_shelf_life_1 = db_session.scalar(select(func.count(ShelfLife.id)))
    total_recipes_1 = db_session.scalar(select(func.count(Recipe.id)))

    # 2. Second seeding execution (simulating container restart)
    ing_count_2, sl_count_2, rec_count_2 = seed_catalogue_data(db_session)
    assert ing_count_2 == ing_count_1
    assert sl_count_2 == sl_count_1
    assert rec_count_2 == rec_count_1

    total_ingredients_2 = db_session.scalar(select(func.count(Ingredient.id)))
    total_shelf_life_2 = db_session.scalar(select(func.count(ShelfLife.id)))
    total_recipes_2 = db_session.scalar(select(func.count(Recipe.id)))

    # Exact equality: zero duplicate records created
    assert total_ingredients_2 == total_ingredients_1
    assert total_shelf_life_2 == total_shelf_life_1
    assert total_recipes_2 == total_recipes_1


def test_seeding_preserves_user_generated_data(db_session: Session):
    """Verify that running catalogue seed never overwrites, modifies, or deletes user data."""
    # Create test user and inventory item
    user = User(
        email="seed_safety_user@example.com",
        password_hash="hashed_password_123",
        display_name="Seed Safety Chef",
    )
    db_session.add(user)
    db_session.flush()

    inventory_item = InventoryItem(
        user_id=user.id,
        ingredient_id="potato",
        display_name="Yukon Gold Potatoes",
        quantity=Decimal("3.50"),
        unit="piece",
        storage="COUNTER",
        shelf_life_days_estimate=14,
    )
    db_session.add(inventory_item)
    db_session.commit()

    item_id = inventory_item.id
    user_id = user.id

    # Execute seeding
    seed_catalogue_data(db_session)

    # Verify user data remains completely untouched
    persisted_user = db_session.get(User, user_id)
    assert persisted_user is not None
    assert persisted_user.email == "seed_safety_user@example.com"
    assert persisted_user.display_name == "Seed Safety Chef"

    persisted_item = db_session.get(InventoryItem, item_id)
    assert persisted_item is not None
    assert persisted_item.ingredient_id == "potato"
    assert persisted_item.display_name == "Yukon Gold Potatoes"
    assert persisted_item.quantity == Decimal("3.50")

    # Cleanup test user
    db_session.delete(persisted_item)
    db_session.delete(persisted_user)
    db_session.commit()
