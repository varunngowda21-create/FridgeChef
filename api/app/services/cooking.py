"""Recipe cooking service with atomic inventory decrements per PRD Section 11.7 and FR-071."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, RecipeNotFoundError
from app.db.models.auth import User, UserPreference
from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient
from app.db.models.inventory import CookingEvent, InventoryItem, WasteLog
from app.schemas.recipes import RecipeCookedRequest, RecipeCookedResponse
from app.services.freshness import FreshnessStatus, get_freshness_for_item
from app.services.recommendations import invalidate_recommendation_cache
from app.services.units import calculate_estimated_cost, convert_quantity_to_grams

logger = logging.getLogger("fridgechef.cooking")


def record_recipe_cooked(
    db: Session,
    user: User,
    recipe_id: str,
    request: RecipeCookedRequest,
) -> RecipeCookedResponse:
    """Atomically record a cooking event, decrement inventory quantities (floored at 0),

    log waste prevention for USE_FIRST/USE_SOON items, and invalidate recommendation cache.
    """
    # 1. Fetch recipe with ingredients
    stmt = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)
        )
        .where(Recipe.id == recipe_id)
    )
    recipe = db.scalars(stmt).first()
    if not recipe:
        raise RecipeNotFoundError(f"Recipe '{recipe_id}' not found.")

    # 2. Determine target servings
    if request.servings is not None:
        target_servings = request.servings
    else:
        pref = user.preferences
        if not pref:
            pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
        target_servings = pref.household_size if pref else recipe.base_servings

    scale_factor = target_servings / float(recipe.base_servings)

    # 3. Fetch active inventory items for this user
    active_items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.user_id == user.id,
            InventoryItem.archived_at.is_(None),
            InventoryItem.quantity > 0,
        )
        .all()
    )

    # Group active inventory items by canonical ingredient_id, sorted by expires_on ascending
    items_by_ing: dict[str, list[InventoryItem]] = {}
    for item in active_items:
        if not item.ingredient_id:
            continue
        items_by_ing.setdefault(item.ingredient_id, []).append(item)

    for ing_id in items_by_ing:
        items_by_ing[ing_id].sort(key=lambda x: (x.expires_on, x.added_on))

    decremented_count = 0
    waste_prevented_logged = False

    try:
        # 4. Process each recipe ingredient
        for ri in recipe.ingredients:
            needed_qty = Decimal(str(ri.qty)) * Decimal(str(scale_factor))
            inv_list = items_by_ing.get(ri.ingredient_id, [])

            for item in inv_list:
                if needed_qty <= Decimal("0.0"):
                    break
                if item.quantity <= Decimal("0.0") or not item.ingredient_id:
                    continue

                # Calculate item freshness before decrement
                try:
                    freshness = get_freshness_for_item(
                        db=db,
                        ingredient_id=item.ingredient_id,
                        storage=item.storage,
                        added_on=item.added_on,
                        opened_on=item.opened_on,
                    )
                except Exception:
                    freshness = None

                # Calculate consumed quantity considering units
                if item.unit.strip().lower() == ri.unit.strip().lower():
                    consumed = min(item.quantity, needed_qty)
                    needed_qty -= consumed
                else:
                    ing_model = ri.ingredient or db.query(Ingredient).filter(Ingredient.id == ri.ingredient_id).first()
                    try:
                        if ing_model:
                            item_g = convert_quantity_to_grams(ing_model, item.quantity, item.unit)
                            needed_g = convert_quantity_to_grams(ing_model, needed_qty, ri.unit)
                            consumed_g = min(item_g, needed_g)
                            consumed = (consumed_g / item_g) * item.quantity if item_g > 0 else Decimal("0.0")
                            consumed = min(item.quantity, round(consumed, 2))
                            needed_used_qty = (consumed_g / needed_g) * needed_qty if needed_g > 0 else Decimal("0.0")
                            needed_qty = max(Decimal("0.0"), needed_qty - needed_used_qty)
                        else:
                            consumed = min(item.quantity, needed_qty)
                            needed_qty -= consumed
                    except Exception:
                        consumed = min(item.quantity, needed_qty)
                        needed_qty -= consumed

                if consumed > Decimal("0.0"):
                    item.quantity = max(Decimal("0.0"), item.quantity - consumed)
                    if item.quantity == Decimal("0.0"):
                        item.archived_at = datetime.now(timezone.utc)
                    decremented_count += 1

                    # Log USED_BEFORE_EXPIRY if item was USE_FIRST or USE_SOON
                    if freshness and freshness.status in (FreshnessStatus.USE_FIRST, FreshnessStatus.USE_SOON):
                        ing_model = ri.ingredient or db.query(Ingredient).filter(Ingredient.id == ri.ingredient_id).first()
                        if ing_model:
                            est_val = calculate_estimated_cost(ing_model, consumed, item.unit)
                        else:
                            est_val = Decimal("0.0")

                        waste_entry = WasteLog(
                            user_id=user.id,
                            inventory_item_id=item.id,
                            ingredient_id=item.ingredient_id,
                            quantity=consumed,
                            unit=item.unit,
                            action="USED_BEFORE_EXPIRY",
                            estimated_value_inr=est_val,
                        )
                        db.add(waste_entry)
                        waste_prevented_logged = True

        # 5. Record CookingEvent
        event = CookingEvent(
            id=uuid.uuid4(),
            user_id=user.id,
            recipe_id=recipe.id,
            servings=target_servings,
            rating=request.rating,
        )
        db.add(event)

        # 6. Invalidate recommendation cache (PRD FR-046)
        invalidate_recommendation_cache(db=db, user_id=user.id)

        # 7. Commit transaction
        db.commit()
        db.refresh(event)

        logger.info(
            f"User {user.id} cooked recipe '{recipe.id}' for {target_servings} servings. "
            f"Decremented {decremented_count} items."
        )

        return RecipeCookedResponse(
            event_id=event.id,
            recipe_id=event.recipe_id,
            servings=event.servings,
            rating=event.rating,
            decremented_items_count=decremented_count,
            waste_prevented_logged=waste_prevented_logged,
            created_at=event.created_at,
        )

    except AppError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Cooking action failed: {exc}", exc_info=True)
        raise AppError(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred while recording cooking action.",
            status_code=500,
        ) from None
