"""Deterministic weekly meal planner service per PRD Section 6.6, 8.6, 10, and 11.8."""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError, ItemNotFoundError, MealPlanNotFoundError, RecipeNotFoundError
from app.db.models.auth import User, UserPreference
from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient
from app.db.models.inventory import InventoryItem
from app.db.models.planning import MealPlan
from app.schemas.meal_plans import LockedSlotInput, MealPlanResponse
from app.services.freshness import FreshnessStatus
from app.services.recommendations import build_inventory_summary
from app.services.scoring import (
    check_hard_filters,
    score_recipe,
)
from app.services.units import (
    UNIT_MULTIPLIERS_TO_BASE,
    calculate_estimated_cost,
    convert_quantity_to_grams,
)

logger = logging.getLogger("fridgechef.planner")

MEALS_SEQUENCE = ["LUNCH", "DINNER"]


@dataclass
class SimulatedInventoryItem:
    canonical_id: str
    display_name: str
    total_quantity: Decimal
    unit: str
    min_days_left: int
    status: FreshnessStatus



def _get_active_inventory_base(db: Session, user_id: uuid.UUID) -> dict[str, Decimal]:
    """Sum active inventory quantities per canonical ID in base units."""
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
                _, factor = UNIT_MULTIPLIERS_TO_BASE.get(u, ("piece", Decimal("1")))
                inv_base[cid] += qty * factor
        else:
            _, factor = UNIT_MULTIPLIERS_TO_BASE.get(u, ("piece", Decimal("1")))
            inv_base[cid] += qty * factor

    return inv_base


def _calculate_plan_shopping_gap(
    db: Session,
    user_id: uuid.UUID,
    slots: list[dict[str, Any]],
    recipe_lookup: dict[str, Recipe],
    catalogue_map: dict[str, Ingredient],
) -> tuple[list[dict[str, Any]], float]:
    """Calculate missing ingredients across the 14 meal plan slots after subtracting original inventory."""
    inv_base = _get_active_inventory_base(db, user_id)
    total_required: dict[str, tuple[Decimal, str]] = {}

    for slot in slots:
        r_id = slot.get("recipe_id")
        if not r_id or r_id not in recipe_lookup:
            continue
        r = recipe_lookup[r_id]
        servings = slot.get("servings", r.base_servings)
        scale = Decimal(str(servings)) / Decimal(str(r.base_servings))

        for ri in r.ingredients:
            if ri.is_optional:
                continue
            cid = ri.ingredient_id.strip().lower()
            ing_model = catalogue_map.get(cid)
            qty_scaled = Decimal(str(ri.qty)) * scale
            u = ri.unit.strip().lower()

            if ing_model:
                try:
                    g = convert_quantity_to_grams(ing_model, qty_scaled, u)
                    current_g, disp_u = total_required.get(cid, (Decimal("0.0"), ing_model.default_unit))
                    total_required[cid] = (current_g + g, disp_u)
                except Exception:
                    current_qty, disp_u = total_required.get(cid, (Decimal("0.0"), u))
                    total_required[cid] = (current_qty + qty_scaled, disp_u)
            else:
                current_qty, disp_u = total_required.get(cid, (Decimal("0.0"), u))
                total_required[cid] = (current_qty + qty_scaled, disp_u)

    shopping_items: list[dict[str, Any]] = []
    total_cost = Decimal("0.0")

    for cid, (req_base, disp_u) in total_required.items():
        have_base = inv_base.get(cid, Decimal("0.0"))
        missing_base = max(Decimal("0.0"), req_base - have_base)
        if missing_base <= Decimal("0.0"):
            continue

        ing_model = catalogue_map.get(cid)
        category = ing_model.category if ing_model and ing_model.category else "Other"
        display_name = ing_model.display_name if ing_model else cid.replace("_", " ").title()

        if ing_model and disp_u == "piece" and ing_model.grams_per_piece:
            final_qty = float(round(missing_base / Decimal(str(ing_model.grams_per_piece)), 1))
            final_unit = "piece"
            cost = calculate_estimated_cost(ing_model, missing_base, "g")
        else:
            final_qty = round(float(missing_base), 1)
            final_unit = disp_u
            cost = calculate_estimated_cost(ing_model, missing_base, "g") if ing_model else Decimal("0.0")

        total_cost += cost
        shopping_items.append({
            "canonical_id": cid,
            "display_name": display_name,
            "category": category,
            "quantity": final_qty,
            "unit": final_unit,
            "est_cost_inr": round(float(cost), 2),
            "bought": False,
        })

    shopping_items.sort(key=lambda x: (x["category"].lower(), x["display_name"].lower()))
    return shopping_items, round(float(total_cost), 2)


def generate_weekly_meal_plan(
    db: Session,
    user: User,
    start_date: date | None = None,
    locked_slots: list[LockedSlotInput] | None = None,
) -> MealPlanResponse:
    """Deterministic greedy weekly meal planner per PRD Section 6.6, 8.6, and FR-050–FR-054."""
    if start_date is None:
        start_date = date.today()

    pref = user.preferences
    if not pref:
        pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if not pref:
        pref = UserPreference(
            user_id=user.id,
            household_size=2,
            diet="VEGETARIAN",
            spice_level="MEDIUM",
            cuisines=[],
            max_cooking_time=45,
            allergies=[],
            avoided_ingredients=[],
            version=1,
        )

    target_servings = pref.household_size if pref.household_size and pref.household_size > 0 else 2

    # 1. Fetch eligible recipes (approved curated + user's accepted AI recipes)
    stmt = (
        select(Recipe)
        .options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))
        .where(
            or_(
                Recipe.status == "APPROVED",
                (Recipe.source == "AI") & (Recipe.created_by_user_id == user.id),
            )
        )
    )
    all_recipes = list(db.scalars(stmt).all())
    recipe_lookup = {r.id: r for r in all_recipes}

    all_ingredients = db.query(Ingredient).all()
    catalogue_map = {ing.id: ing for ing in all_ingredients}

    # Fetch active inventory snapshot
    active_items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.user_id == user.id,
            InventoryItem.archived_at.is_(None),
            InventoryItem.quantity > 0,
        )
        .all()
    )
    initial_inventory_summary = build_inventory_summary(db=db, inventory_items=active_items, today=start_date)

    # 2. Build candidate set: recipes passing hard filters from 8.2 against original snapshot (PRD 8.6 Step 1)
    eligible_candidates: list[Recipe] = []
    for r in all_recipes:
        passes, _ = check_hard_filters(
            recipe=r,
            preferences=pref,
            inventory_map=initial_inventory_summary,
            ingredient_catalogue=catalogue_map,
        )
        if passes:
            eligible_candidates.append(r)

    # If fewer than 14 candidates pass coverage >= 40%, relax coverage constraint so all 14 slots can be planned (PRD 8.6)
    low_variety = False
    if len(eligible_candidates) < 14:
        low_variety = True
        logger.info(f"Only {len(eligible_candidates)} candidates passed 40% coverage for user {user.id}. Marking low_variety=True.")
        # Fallback to recipes passing allergy, diet, and cooking time constraints
        relaxed_candidates: list[Recipe] = []
        for r in all_recipes:
            passes, reason = check_hard_filters(
                recipe=r,
                preferences=pref,
                inventory_map={},  # ignore coverage
                ingredient_catalogue=catalogue_map,
            )
            if passes or (reason and "coverage" in reason.lower()):
                relaxed_candidates.append(r)
        eligible_candidates = relaxed_candidates

    if not eligible_candidates:
        raise AppError(
            code="NO_ELIGIBLE_RECIPES",
            message="No recipes in catalogue match your dietary constraints and preferences.",
            status_code=422,
        )

    # Map locked slots by (day, meal)
    locked_map: dict[tuple[int, str], str] = {}
    if locked_slots:
        for ls in locked_slots:
            meal_upper = ls.meal.strip().upper()
            if meal_upper not in MEALS_SEQUENCE:
                raise AppError(code="INVALID_MEAL", message=f"Meal must be LUNCH or DINNER, got '{ls.meal}'.", status_code=422)
            if ls.recipe_id not in recipe_lookup:
                raise RecipeNotFoundError(f"Locked recipe '{ls.recipe_id}' does not exist.")
            locked_map[(ls.day, meal_upper)] = ls.recipe_id

    # 3. Simulate inventory consumption across slots (PRD 8.6 Step 2)
    simulated_inv: dict[str, Any] = {
        k: SimulatedInventoryItem(
            canonical_id=v.canonical_id,
            display_name=v.display_name,
            total_quantity=Decimal(str(v.total_quantity)),
            unit=v.unit,
            min_days_left=v.min_days_left,
            status=v.status,
        )
        for k, v in initial_inventory_summary.items()
    }
    scheduled_counts: dict[str, int] = defaultdict(int)
    slots_output: list[dict[str, Any]] = []
    previous_recipe_id: str | None = None
    total_waste_prevented_grams = Decimal("0.0")

    for day_idx in range(1, 8):
        current_date = start_date + timedelta(days=day_idx - 1)
        for meal in MEALS_SEQUENCE:
            chosen_recipe: Recipe | None = None
            slot_key = (day_idx, meal)

            # Check if locked
            if slot_key in locked_map:
                chosen_recipe = recipe_lookup[locked_map[slot_key]]
            else:
                # Score all candidates against current simulated inventory using 8.2
                scored_candidates: list[tuple[float, float, int, str, Recipe]] = []
                for cand in eligible_candidates:
                    # Enforce repetition constraints per PRD 8.6:
                    # (b) Exclude recipe scheduled twice (unless low_variety)
                    if not low_variety and scheduled_counts[cand.id] >= 2:
                        continue
                    # (c) Exclude recipe scheduled on previous slot
                    if cand.id == previous_recipe_id and (len(eligible_candidates) > 1 or not low_variety):
                        continue

                    sc = score_recipe(
                        recipe=cand,
                        preferences=pref,
                        inventory_map=simulated_inv,
                        ingredient_catalogue=catalogue_map,
                        target_servings=target_servings,
                    )
                    # Tie-breaking tuple: (score, coverage, -cooking_time, -id)
                    scored_candidates.append((
                        sc.score,
                        sc.coverage,
                        -cand.cooking_time_minutes,
                        cand.id,
                        cand,
                    ))

                if scored_candidates:
                    # Sort descending by final score, coverage, shorter cooking time, then alphabetically by ID
                    scored_candidates.sort(
                        key=lambda x: (x[0], x[1], x[2], -ord(x[3][0]) if x[3] else 0),
                        reverse=True,
                    )
                    chosen_recipe = scored_candidates[0][4]
                else:
                    # If exhausted due to repetition, fallback to any candidate not matching previous slot
                    fallback_pool = [c for c in eligible_candidates if c.id != previous_recipe_id] or eligible_candidates
                    chosen_recipe = fallback_pool[0]

            # Prioritised ingredients and waste prevented
            scale_factor = Decimal(str(target_servings)) / Decimal(str(chosen_recipe.base_servings))
            prioritised_ings: list[str] = []
            slot_waste_prevented_g = Decimal("0.0")

            for ri in chosen_recipe.ingredients:
                cid = ri.ingredient_id.strip().lower()
                inv_item = simulated_inv.get(cid)
                if inv_item and inv_item.total_quantity > Decimal("0.0"):
                    if inv_item.status in (FreshnessStatus.USE_FIRST, FreshnessStatus.USE_SOON):
                        if cid not in prioritised_ings:
                            prioritised_ings.append(cid)

                    needed = Decimal(str(ri.qty)) * scale_factor
                    consumed = min(inv_item.total_quantity, needed)

                    if inv_item.status == FreshnessStatus.USE_FIRST:
                        ing_m = catalogue_map.get(cid)
                        if ing_m:
                            try:
                                consumed_g = convert_quantity_to_grams(ing_m, consumed, ri.unit)
                            except Exception:
                                consumed_g = consumed * Decimal("100.0")
                        else:
                            consumed_g = consumed * Decimal("100.0")
                        slot_waste_prevented_g += consumed_g

                    # Subtract from simulated inventory (floored at 0) per PRD 8.6 Step 2d
                    inv_item.total_quantity = max(Decimal("0.0"), inv_item.total_quantity - consumed)

            scheduled_counts[chosen_recipe.id] += 1
            previous_recipe_id = chosen_recipe.id
            total_waste_prevented_grams += slot_waste_prevented_g

            slots_output.append({
                "day": day_idx,
                "date": current_date.isoformat(),
                "meal": meal,
                "recipe_id": chosen_recipe.id,
                "recipe_title": chosen_recipe.title,
                "servings": target_servings,
                "prioritised_ingredients": prioritised_ings,
                "waste_prevented_g": round(float(slot_waste_prevented_g), 1),
            })

    # 4. Compute shopping gap across the whole plan (PRD 8.6 Step 3)
    shopping_items, _ = _calculate_plan_shopping_gap(
        db=db,
        user_id=user.id,
        slots=slots_output,
        recipe_lookup=recipe_lookup,
        catalogue_map=catalogue_map,
    )

    total_waste_kg = round(float(total_waste_prevented_grams / Decimal("1000.0")), 2)

    plan_payload = {
        "slots": slots_output,
        "shopping_list": shopping_items,
        "total_waste_prevented_kg": total_waste_kg,
    }

    # 5. Archive previous active plan if one exists (PRD FR-054)
    db.query(MealPlan).filter(
        MealPlan.user_id == user.id,
        MealPlan.status == "ACTIVE",
    ).update({"status": "ARCHIVED"}, synchronize_session=False)

    # 6. Save new active meal plan
    new_plan = MealPlan(
        id=uuid.uuid4(),
        user_id=user.id,
        start_date=start_date,
        status="ACTIVE",
        low_variety=low_variety,
        plan=plan_payload,
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)

    logger.info(f"Created active meal plan {new_plan.id} for user {user.id} (low_variety={low_variety})")

    return MealPlanResponse(
        id=new_plan.id,
        user_id=new_plan.user_id,
        start_date=new_plan.start_date,
        status=new_plan.status,
        low_variety=new_plan.low_variety,
        plan=new_plan.plan,
        created_at=new_plan.created_at,
    )


def get_active_meal_plan(db: Session, user: User) -> MealPlanResponse:
    """Retrieve the current active meal plan for a user per PRD Section 11.8."""
    plan = (
        db.query(MealPlan)
        .filter(MealPlan.user_id == user.id, MealPlan.status == "ACTIVE")
        .order_by(MealPlan.created_at.desc())
        .first()
    )
    if not plan:
        raise MealPlanNotFoundError("No active meal plan found.")

    return MealPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        start_date=plan.start_date,
        status=plan.status,
        low_variety=plan.low_variety,
        plan=plan.plan,
        created_at=plan.created_at,
    )


def get_meal_plan_by_id(db: Session, user: User, plan_id: uuid.UUID) -> MealPlanResponse:
    """Retrieve meal plan by ID (owner only) per PRD Section 11.8."""
    plan = db.query(MealPlan).filter(MealPlan.id == plan_id).first()
    if not plan or plan.user_id != user.id:
        raise MealPlanNotFoundError(f"Meal plan '{plan_id}' not found.")

    return MealPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        start_date=plan.start_date,
        status=plan.status,
        low_variety=plan.low_variety,
        plan=plan.plan,
        created_at=plan.created_at,
    )


def regenerate_plan_slot(
    db: Session,
    user: User,
    plan_id: uuid.UUID,
    day: int,
    meal: str,
) -> MealPlanResponse:
    """Regenerate a single slot in an existing meal plan while keeping all other slots unchanged per PRD Section 6.6 (FR-053)."""
    plan = db.query(MealPlan).filter(MealPlan.id == plan_id).first()
    if not plan or plan.user_id != user.id:
        raise MealPlanNotFoundError(f"Meal plan '{plan_id}' not found.")

    meal_upper = meal.strip().upper()
    if meal_upper not in MEALS_SEQUENCE:
        raise AppError(code="INVALID_MEAL", message=f"Meal must be LUNCH or DINNER, got '{meal}'.", status_code=422)

    if not (1 <= day <= 7):
        raise AppError(code="INVALID_DAY", message=f"Day must be between 1 and 7, got {day}.", status_code=422)

    slots: list[dict[str, Any]] = list(plan.plan.get("slots", []))
    target_slot_idx: int | None = None
    for idx, s in enumerate(slots):
        if s.get("day") == day and s.get("meal", "").strip().upper() == meal_upper:
            target_slot_idx = idx
            break

    if target_slot_idx is None:
        raise ItemNotFoundError(f"Slot for day {day} {meal_upper} not found in meal plan.")

    current_recipe_id = slots[target_slot_idx].get("recipe_id")

    # Determine previous and next recipes
    prev_recipe_id = slots[target_slot_idx - 1].get("recipe_id") if target_slot_idx > 0 else None
    next_recipe_id = slots[target_slot_idx + 1].get("recipe_id") if target_slot_idx < len(slots) - 1 else None

    # Count scheduled recipes across the other 13 slots
    other_counts: dict[str, int] = defaultdict(int)
    for idx, s in enumerate(slots):
        if idx != target_slot_idx and s.get("recipe_id"):
            other_counts[s["recipe_id"]] += 1

    # Fetch candidate recipes
    stmt = (
        select(Recipe)
        .options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))
        .where(
            or_(
                Recipe.status == "APPROVED",
                (Recipe.source == "AI") & (Recipe.created_by_user_id == user.id),
            )
        )
    )
    all_recipes = list(db.scalars(stmt).all())
    recipe_lookup = {r.id: r for r in all_recipes}
    catalogue_map = {ing.id: ing for ing in db.query(Ingredient).all()}

    pref = user.preferences
    if not pref:
        pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if not pref:
        pref = UserPreference(user_id=user.id, household_size=2, diet="VEGETARIAN")

    # Find replacement recipe that:
    # 1. Passes diet/allergy constraints
    # 2. Is not scheduled > 2 times in other slots (unless low_variety)
    # 3. Is not identical to previous or next meal
    # 4. Is different from current recipe if possible
    valid_replacements: list[Recipe] = []
    for cand in all_recipes:
        passes, _ = check_hard_filters(
            recipe=cand,
            preferences=pref,
            inventory_map={},
            ingredient_catalogue=catalogue_map,
        )
        if not passes:
            continue
        if not plan.low_variety and other_counts[cand.id] >= 2:
            continue
        if cand.id == prev_recipe_id or cand.id == next_recipe_id:
            continue
        if cand.id == current_recipe_id and len(all_recipes) > 2:
            continue
        valid_replacements.append(cand)

    if not valid_replacements:
        # Relax consecutive constraint if catalogue is tight
        for cand in all_recipes:
            passes, _ = check_hard_filters(recipe=cand, preferences=pref, inventory_map={}, ingredient_catalogue=catalogue_map)
            if passes and cand.id != current_recipe_id:
                valid_replacements.append(cand)

    if not valid_replacements:
        valid_replacements = all_recipes

    new_recipe = valid_replacements[0]
    target_servings = slots[target_slot_idx].get("servings", pref.household_size or 2)

    # Update target slot only
    slots[target_slot_idx]["recipe_id"] = new_recipe.id
    slots[target_slot_idx]["recipe_title"] = new_recipe.title
    slots[target_slot_idx]["servings"] = target_servings

    # Recalculate plan shopping gap
    shopping_items, _ = _calculate_plan_shopping_gap(
        db=db,
        user_id=user.id,
        slots=slots,
        recipe_lookup=recipe_lookup,
        catalogue_map=catalogue_map,
    )

    plan.plan["slots"] = slots
    plan.plan["shopping_list"] = shopping_items
    flag_modified(plan, "plan")
    db.commit()
    db.refresh(plan)

    logger.info(f"Regenerated slot (day {day}, {meal_upper}) with recipe '{new_recipe.id}' in meal plan {plan.id}")

    return MealPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        start_date=plan.start_date,
        status=plan.status,
        low_variety=plan.low_variety,
        plan=plan.plan,
        created_at=plan.created_at,
    )


def archive_meal_plan(db: Session, user: User, plan_id: uuid.UUID) -> None:
    """Archive a meal plan per PRD Section 11.8 (DELETE /meal-plans/{id} -> 204)."""
    plan = db.query(MealPlan).filter(MealPlan.id == plan_id).first()
    if not plan or plan.user_id != user.id:
        raise MealPlanNotFoundError(f"Meal plan '{plan_id}' not found.")

    plan.status = "ARCHIVED"
    db.commit()
    logger.info(f"Archived meal plan {plan_id} for user {user.id}")
