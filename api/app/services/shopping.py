"""Shopping list generation and management service per PRD Section 6.7, 8.7, 10, and 11.9."""

import logging
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError, ItemNotFoundError, MealPlanNotFoundError
from app.db.models.auth import User
from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient, ShelfLife
from app.db.models.inventory import InventoryItem
from app.db.models.planning import MealPlan, ShoppingList
from app.schemas.shopping import (
    ManualShoppingItem,
    RecipeServingsItem,
    ShoppingItemPatchRequest,
    ShoppingListCreateRequest,
    ShoppingListItem,
    ShoppingListResponse,
)
from app.services.freshness import get_freshness_for_item
from app.services.recommendations import invalidate_recommendation_cache
from app.services.units import (
    UNIT_MULTIPLIERS_TO_BASE,
    calculate_estimated_cost,
    convert_quantity_to_grams,
)

logger = logging.getLogger("fridgechef.shopping")


def _get_active_inventory_base(db: Session, user_id: uuid.UUID) -> dict[str, Decimal]:
    """Sum active inventory quantities per canonical ID in base units (grams for weight/volume, piece for piece)."""
    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.user_id == user_id,
            InventoryItem.archived_at.is_(None),
            InventoryItem.quantity > 0,
        )
        .all()
    )

    ingredients = {ing.id: ing for ing in db.query(Ingredient).all()}
    inv_base: dict[str, Decimal] = defaultdict(Decimal)

    for item in items:
        if not item.ingredient_id or item.quantity <= 0:
            continue
        cid = item.ingredient_id.strip().lower()
        ing_model = ingredients.get(cid)
        qty = Decimal(str(item.quantity))
        u = item.unit.strip().lower()

        if ing_model:
            try:
                g = convert_quantity_to_grams(ing_model, qty, u)
                inv_base[cid] += g
            except Exception:
                # Fallback multiplier
                _, factor = UNIT_MULTIPLIERS_TO_BASE.get(u, ("piece", Decimal("1")))
                inv_base[cid] += qty * factor
        else:
            _, factor = UNIT_MULTIPLIERS_TO_BASE.get(u, ("piece", Decimal("1")))
            inv_base[cid] += qty * factor

    return inv_base


def generate_shopping_items(
    db: Session,
    user: User,
    source: str,
    plan_id: uuid.UUID | None = None,
    recipes: list[RecipeServingsItem] | None = None,
    manual_items: list[ManualShoppingItem] | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Aggregate required ingredients, subtract available inventory, group by category,

    and calculate estimated costs per PRD Section 8.7.
    """
    ingredients = {ing.id: ing for ing in db.query(Ingredient).all()}
    required_quantities: dict[str, tuple[Decimal, str]] = {}  # cid -> (qty_in_base, display_unit)

    source_upper = source.strip().upper()

    if source_upper == "PLAN":
        if not plan_id:
            raise AppError(code="PLAN_ID_REQUIRED", message="plan_id is required when source is 'PLAN'.", status_code=422)
        plan = db.query(MealPlan).filter(MealPlan.id == plan_id, MealPlan.user_id == user.id).first()
        if not plan:
            raise MealPlanNotFoundError(f"Meal plan '{plan_id}' not found.")

        slots = plan.plan.get("slots", [])
        recipe_ids = [s["recipe_id"] for s in slots if "recipe_id" in s]

        recipes_db = (
            db.query(Recipe)
            .options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))
            .filter(Recipe.id.in_(recipe_ids))
            .all()
        )
        recipe_lookup = {r.id: r for r in recipes_db}

        for slot in slots:
            r_id = slot.get("recipe_id")
            if not r_id or r_id not in recipe_lookup:
                continue
            r_obj = recipe_lookup[r_id]
            target_servings = slot.get("servings", r_obj.base_servings)
            scale = Decimal(str(target_servings)) / Decimal(str(r_obj.base_servings))

            for ri in r_obj.ingredients:
                cid = ri.ingredient_id.strip().lower()
                ing_model = ingredients.get(cid)
                qty_scaled = Decimal(str(ri.qty)) * scale
                u = ri.unit.strip().lower()

                if ing_model:
                    try:
                        g = convert_quantity_to_grams(ing_model, qty_scaled, u)
                        current_g, disp_u = required_quantities.get(cid, (Decimal("0.0"), ing_model.default_unit))
                        required_quantities[cid] = (current_g + g, disp_u)
                    except Exception:
                        current_qty, disp_u = required_quantities.get(cid, (Decimal("0.0"), u))
                        required_quantities[cid] = (current_qty + qty_scaled, disp_u)
                else:
                    current_qty, disp_u = required_quantities.get(cid, (Decimal("0.0"), u))
                    required_quantities[cid] = (current_qty + qty_scaled, disp_u)

    elif source_upper == "RECIPES":
        if not recipes:
            raise AppError(code="RECIPES_REQUIRED", message="recipes list is required when source is 'RECIPES'.", status_code=422)

        recipe_ids = [r.recipe_id for r in recipes]
        recipes_db = (
            db.query(Recipe)
            .options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))
            .filter(Recipe.id.in_(recipe_ids))
            .all()
        )
        recipe_lookup = {r.id: r for r in recipes_db}

        for r_input in recipes:
            if r_input.recipe_id not in recipe_lookup:
                continue
            r_obj = recipe_lookup[r_input.recipe_id]
            scale = Decimal(str(r_input.servings)) / Decimal(str(r_obj.base_servings))

            for ri in r_obj.ingredients:
                cid = ri.ingredient_id.strip().lower()
                ing_model = ingredients.get(cid)
                qty_scaled = Decimal(str(ri.qty)) * scale
                u = ri.unit.strip().lower()

                if ing_model:
                    try:
                        g = convert_quantity_to_grams(ing_model, qty_scaled, u)
                        current_g, disp_u = required_quantities.get(cid, (Decimal("0.0"), ing_model.default_unit))
                        required_quantities[cid] = (current_g + g, disp_u)
                    except Exception:
                        current_qty, disp_u = required_quantities.get(cid, (Decimal("0.0"), u))
                        required_quantities[cid] = (current_qty + qty_scaled, disp_u)
                else:
                    current_qty, disp_u = required_quantities.get(cid, (Decimal("0.0"), u))
                    required_quantities[cid] = (current_qty + qty_scaled, disp_u)

    elif source_upper == "MANUAL":
        if not manual_items:
            raise AppError(code="MANUAL_ITEMS_REQUIRED", message="manual_items is required when source is 'MANUAL'.", status_code=422)

        for m_item in manual_items:
            cid = m_item.canonical_id.strip().lower()
            ing_model = ingredients.get(cid)
            qty = Decimal(str(m_item.qty))
            u = m_item.unit.strip().lower()

            if ing_model:
                try:
                    g = convert_quantity_to_grams(ing_model, qty, u)
                    current_g, disp_u = required_quantities.get(cid, (Decimal("0.0"), ing_model.default_unit))
                    required_quantities[cid] = (current_g + g, disp_u)
                except Exception:
                    current_qty, disp_u = required_quantities.get(cid, (Decimal("0.0"), u))
                    required_quantities[cid] = (current_qty + qty, disp_u)
            else:
                current_qty, disp_u = required_quantities.get(cid, (Decimal("0.0"), u))
                required_quantities[cid] = (current_qty + qty, disp_u)

    else:
        raise AppError(code="INVALID_SOURCE", message=f"Invalid source '{source}'. Must be PLAN, RECIPES, or MANUAL.", status_code=422)

    # Subtract active inventory quantities (floored at 0) per PRD Section 8.7 Step 2
    inv_base = _get_active_inventory_base(db, user.id)
    items_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_cost = Decimal("0.0")

    for cid, (req_qty, disp_unit) in required_quantities.items():
        inv_qty = inv_base.get(cid, Decimal("0.0"))
        missing_qty = max(Decimal("0.0"), req_qty - inv_qty)

        # Drop items where remainder is 0 per PRD Section 8.7 Step 3
        if missing_qty <= Decimal("0.0"):
            continue

        ing_model = ingredients.get(cid)
        category = ing_model.category if ing_model and ing_model.category else "Other"
        display_name = ing_model.display_name if ing_model else cid.replace("_", " ").title()

        # Format display quantity & unit
        if ing_model and disp_unit == "piece" and ing_model.grams_per_piece:
            # If default unit is piece, convert grams to pieces
            pieces = round(missing_qty / Decimal(str(ing_model.grams_per_piece)), 1)
            final_qty = float(pieces)
            final_unit = "piece"
            cost = calculate_estimated_cost(ing_model, missing_qty, "g")
        else:
            final_qty = round(float(missing_qty), 1)
            final_unit = disp_unit
            cost = calculate_estimated_cost(ing_model, missing_qty, "g") if ing_model else Decimal("0.0")

        total_cost += cost

        item_dict = {
            "canonical_id": cid,
            "display_name": display_name,
            "category": category,
            "quantity": final_qty,
            "unit": final_unit,
            "est_cost_inr": round(float(cost), 2),
            "bought": False,
        }
        items_by_category[category].append(item_dict)

    # Sort categories alphabetically and sort items alphabetically within each category (PRD 8.7 Step 4)
    flat_items: list[dict[str, Any]] = []
    for cat in sorted(items_by_category.keys()):
        category_items = sorted(items_by_category[cat], key=lambda x: x["display_name"].lower())
        flat_items.extend(category_items)

    return flat_items, round(float(total_cost), 2)


def create_shopping_list(
    db: Session,
    user: User,
    request: ShoppingListCreateRequest,
) -> ShoppingListResponse:
    """Create and persist a new shopping list per PRD Section 11.9."""
    items, total_cost = generate_shopping_items(
        db=db,
        user=user,
        source=request.source,
        plan_id=request.plan_id,
        recipes=request.recipes,
        manual_items=request.manual_items,
    )

    s_list = ShoppingList(
        id=uuid.uuid4(),
        user_id=user.id,
        source=request.source.upper(),
        items=items,
    )
    db.add(s_list)
    db.commit()
    db.refresh(s_list)

    return ShoppingListResponse(
        id=s_list.id,
        user_id=s_list.user_id,
        source=s_list.source,
        items=[ShoppingListItem(**it) for it in s_list.items],
        total_est_cost_inr=total_cost,
        created_at=s_list.created_at,
    )


def get_shopping_list(
    db: Session,
    user: User,
    list_id: uuid.UUID,
) -> ShoppingListResponse:
    """Retrieve shopping list by ID (owner only) per PRD Section 11.9."""
    s_list = db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
    if not s_list or s_list.user_id != user.id:
        raise ItemNotFoundError(f"Shopping list '{list_id}' not found.")

    total_cost = round(sum(it.get("est_cost_inr", 0.0) for it in s_list.items), 2)

    return ShoppingListResponse(
        id=s_list.id,
        user_id=s_list.user_id,
        source=s_list.source,
        items=[ShoppingListItem(**it) for it in s_list.items],
        total_est_cost_inr=total_cost,
        created_at=s_list.created_at,
    )


def patch_shopping_item(
    db: Session,
    user: User,
    list_id: uuid.UUID,
    canonical_id: str,
    request: ShoppingItemPatchRequest,
) -> ShoppingListResponse:
    """Update bought status of a shopping list item and optionally add to inventory per PRD Section 6.7 (FR-062)."""
    s_list = db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
    if not s_list or s_list.user_id != user.id:
        raise ItemNotFoundError(f"Shopping list '{list_id}' not found.")

    cid_lower = canonical_id.strip().lower()
    target_item: dict[str, Any] | None = None

    for it in s_list.items:
        if it.get("canonical_id", "").strip().lower() == cid_lower:
            target_item = it
            break

    if not target_item:
        raise ItemNotFoundError(f"Item with canonical ID '{canonical_id}' not found in shopping list.")

    target_item["bought"] = request.bought

    # If bought and add_to_inventory requested (FR-062)
    if request.bought and request.add_to_inventory:
        # Find default storage from shelf life
        shelf_entry = (
            db.query(ShelfLife)
            .filter(ShelfLife.ingredient_id == cid_lower)
            .order_by(ShelfLife.days.desc())
            .first()
        )
        storage_choice = shelf_entry.storage if shelf_entry else "PANTRY"

        # Check existing inventory item
        existing_inv = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.user_id == user.id,
                InventoryItem.ingredient_id == cid_lower,
                InventoryItem.archived_at.is_(None),
                InventoryItem.storage == storage_choice,
            )
            .first()
        )

        today = date.today()
        qty = Decimal(str(target_item["quantity"]))
        unit = target_item["unit"]

        if existing_inv:
            existing_inv.quantity += qty
            try:
                fr = get_freshness_for_item(
                    db=db,
                    ingredient_id=cid_lower,
                    storage=storage_choice,
                    added_on=existing_inv.added_on,
                    opened_on=existing_inv.opened_on,
                    today=today,
                )
                existing_inv.expires_on = fr.expires_on
                existing_inv.shelf_life_days_estimate = fr.base_life
            except Exception:
                pass
        else:
            new_inv = InventoryItem(
                id=uuid.uuid4(),
                user_id=user.id,
                ingredient_id=cid_lower,
                display_name=target_item.get("display_name", cid_lower.title()),
                quantity=qty,
                unit=unit,
                storage=storage_choice,
                added_on=today,
            )
            try:
                fr = get_freshness_for_item(
                    db=db,
                    ingredient_id=cid_lower,
                    storage=storage_choice,
                    added_on=today,
                    opened_on=None,
                    today=today,
                )
                new_inv.expires_on = fr.expires_on
                new_inv.shelf_life_days_estimate = fr.base_life
            except Exception:
                pass
            db.add(new_inv)

        invalidate_recommendation_cache(db, user.id)

    flag_modified(s_list, "items")
    db.commit()
    db.refresh(s_list)

    total_cost = round(sum(it.get("est_cost_inr", 0.0) for it in s_list.items), 2)

    return ShoppingListResponse(
        id=s_list.id,
        user_id=s_list.user_id,
        source=s_list.source,
        items=[ShoppingListItem(**it) for it in s_list.items],
        total_est_cost_inr=total_cost,
        created_at=s_list.created_at,
    )
