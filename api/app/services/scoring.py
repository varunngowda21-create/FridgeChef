"""Deterministic recipe scoring engine per PRD Section 8.2 and FR-043 to FR-045.

Calculates match score, urgency, quantity fit, preference, and time fit.
Enforces hard exclusion filters (allergies, avoided items, diet, cooking time > 2x, coverage < 40%).
Produces deterministic explanations and tie-breaking.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from app.db.models.auth import UserPreference
from app.db.models.catalogue import Ingredient, Recipe
from app.schemas.recommendations import MissingIngredient, UsesExpiringItem
from app.services.freshness import FreshnessStatus
from app.services.units import calculate_estimated_cost, convert_quantity_to_grams

# Diet hierarchy mapping allowed recipe diets per user diet
DIET_HIERARCHY: dict[str, set[str]] = {
    "VEGAN": {"VEGAN"},
    "VEGETARIAN": {"VEGETARIAN", "VEGAN"},
    "EGGLESS": {"EGGLESS", "VEGETARIAN", "VEGAN"},
    "NON_VEGETARIAN": {"NON_VEGETARIAN", "EGGLESS", "VEGETARIAN", "VEGAN"},
}

SPICE_LEVELS: dict[str, int] = {
    "MILD": 0,
    "MEDIUM": 1,
    "HOT": 2,
}


@dataclass(frozen=True)
class InventoryItemSummary:
    canonical_id: str
    display_name: str
    total_quantity: Decimal
    unit: str
    min_days_left: int
    status: FreshnessStatus


@dataclass
class ScoredRecipe:
    recipe: Recipe
    score: float
    coverage: float
    urgency: float
    quantity_fit: float
    preference: float
    time_fit: float
    match_percent: int
    servings: int
    uses_expiring: list[UsesExpiringItem] = field(default_factory=list)
    missing: list[MissingIngredient] = field(default_factory=list)
    missing_cost_inr: float = 0.0
    reason: str = ""


def check_hard_filters(
    recipe: Recipe,
    preferences: UserPreference,
    inventory_map: dict[str, InventoryItemSummary],
    ingredient_catalogue: dict[str, Ingredient],
) -> tuple[bool, str | None]:
    """Evaluate hard exclusion filters per PRD Section 8.2.

    Returns (True, None) if recipe passes, or (False, reason) if excluded.

    Filters:
    1. Contains allergen or avoided ingredient.
    2. Violates diet.
    3. Cooking time exceeds 2x max_cooking_time.
    4. Coverage < 0.40 (too many missing ingredients).
    """
    # 1. Allergies and avoided ingredients check
    user_allergies = {a.strip().lower() for a in (preferences.allergies or []) if a.strip()}
    user_avoided = {a.strip().lower() for a in (preferences.avoided_ingredients or []) if a.strip()}

    for ri in recipe.ingredients:
        ing_id = ri.ingredient_id.strip().lower()
        ing = ingredient_catalogue.get(ri.ingredient_id)

        # Check canonical ID
        if ing_id in user_allergies or ing_id in user_avoided:
            return False, f"Contains allergen/avoided ingredient: {ing_id}"

        if ing:
            # Check allergen group
            if ing.allergen_group and ing.allergen_group.strip().lower() in user_allergies:
                return False, f"Contains allergen group '{ing.allergen_group}': {ing_id}"

            # Check aliases
            ing_aliases = {a.strip().lower() for a in (ing.aliases or []) if isinstance(a, str)}
            if user_allergies.intersection(ing_aliases):
                return False, f"Contains allergen alias for: {ing_id}"
            if user_avoided.intersection(ing_aliases):
                return False, f"Contains avoided alias for: {ing_id}"

            # Check display name
            disp_lower = ing.display_name.strip().lower()
            if disp_lower in user_allergies or disp_lower in user_avoided:
                return False, f"Contains allergen/avoided display name: {ing.display_name}"

    # 2. Diet violation check
    user_diet = (preferences.diet or "VEGETARIAN").strip().upper()
    recipe_diet = (recipe.diet or "VEGETARIAN").strip().upper()
    allowed_diets = DIET_HIERARCHY.get(user_diet, {user_diet})
    if recipe_diet not in allowed_diets:
        return False, f"Violates diet: user is {user_diet}, recipe is {recipe_diet}"

    # 3. Cooking time constraint (exceeds 2x max_cooking_time)
    max_time = preferences.max_cooking_time or 45
    if recipe.cooking_time_minutes > 2 * max_time:
        return False, f"Cooking time ({recipe.cooking_time_minutes}m) exceeds 2x limit ({2 * max_time}m)"

    # 4. Coverage threshold (< 0.40)
    required_ingredients = [ri for ri in recipe.ingredients if not ri.is_optional]
    if required_ingredients:
        matched_count = sum(
            1
            for ri in required_ingredients
            if ri.ingredient_id in inventory_map and inventory_map[ri.ingredient_id].total_quantity > 0
        )
        coverage = matched_count / float(len(required_ingredients))
        if coverage < 0.40:
            return False, f"Ingredient coverage {coverage:.2f} is below minimum 0.40 threshold"

    return True, None


def generate_recommendation_reason(
    matched_count: int,
    required_count: int,
    uses_expiring: list[UsesExpiringItem],
    ingredient_catalogue: dict[str, Ingredient],
) -> str:
    """Generate deterministic template-based reason per PRD Section 8.2 and 11.6."""
    if uses_expiring:
        first_exp = uses_expiring[0]
        ing = ingredient_catalogue.get(first_exp.canonical_id)
        name1 = ing.display_name if ing else first_exp.canonical_id.replace("_", " ").title()

        if first_exp.days_left == 0:
            expiry_text = "expiring today"
        elif first_exp.days_left == 1:
            expiry_text = "expiring tomorrow"
        else:
            expiry_text = f"expiring in {first_exp.days_left} days"

        if len(uses_expiring) == 1:
            return f"Uses {name1} {expiry_text}; you have {matched_count} of {required_count} required items."
        else:
            second_exp = uses_expiring[1]
            ing2 = ingredient_catalogue.get(second_exp.canonical_id)
            name2 = ing2.display_name if ing2 else second_exp.canonical_id.replace("_", " ").title()
            return f"Uses {name1} and {name2} expiring soon; you have {matched_count} of {required_count} required items."

    if matched_count == required_count:
        return f"You have all {required_count} required ingredients fresh in your kitchen!"
    return f"You have {matched_count} of {required_count} required items fresh in your kitchen."


def score_recipe(
    recipe: Recipe,
    preferences: UserPreference,
    inventory_map: dict[str, InventoryItemSummary],
    ingredient_catalogue: dict[str, Ingredient],
    target_servings: int,
    feedback_adjustment: float = 0.0,
) -> ScoredRecipe:
    """Calculate the deterministic score for a recipe per PRD Section 8.2."""
    required_ingredients = [ri for ri in recipe.ingredients if not ri.is_optional]
    scale_factor = target_servings / float(recipe.base_servings)

    # 1. Coverage
    matched_ingredients = [
        ri
        for ri in required_ingredients
        if ri.ingredient_id in inventory_map and inventory_map[ri.ingredient_id].total_quantity > 0
    ]
    if required_ingredients:
        coverage = len(matched_ingredients) / float(len(required_ingredients))
    else:
        coverage = 1.0

    # 2. Urgency
    if matched_ingredients:
        u_values: list[float] = []
        for ri in matched_ingredients:
            inv = inventory_map[ri.ingredient_id]
            u = max(0.0, 1.0 - (inv.min_days_left / 7.0))
            u_values.append(u)
        urgency = sum(u_values) / float(len(u_values))
    else:
        urgency = 0.0

    # 3. Quantity Fit
    if matched_ingredients:
        q_ratios: list[float] = []
        for ri in matched_ingredients:
            inv = inventory_map[ri.ingredient_id]
            needed_qty = Decimal(str(ri.qty)) * Decimal(str(scale_factor))
            inv_qty = inv.total_quantity

            if inv.unit.strip().lower() == ri.unit.strip().lower():
                ratio = min(1.0, float(inv_qty / needed_qty)) if needed_qty > 0 else 1.0
            else:
                ing = ingredient_catalogue.get(ri.ingredient_id)
                try:
                    if ing:
                        inv_g = convert_quantity_to_grams(ing, inv_qty, inv.unit)
                        needed_g = convert_quantity_to_grams(ing, needed_qty, ri.unit)
                        ratio = min(1.0, float(inv_g / needed_g)) if needed_g > 0 else 1.0
                    else:
                        ratio = min(1.0, float(inv_qty / needed_qty)) if needed_qty > 0 else 1.0
                except Exception:
                    ratio = min(1.0, float(inv_qty / needed_qty)) if needed_qty > 0 else 1.0
            q_ratios.append(ratio)
        quantity_fit = sum(q_ratios) / float(len(q_ratios))
    else:
        quantity_fit = 0.0

    # 4. Preference (Cuisine + Spice match + feedback adjustment)
    pref_cuisines = [c.strip().lower() for c in (preferences.cuisines or []) if c.strip()]
    cuisine_factor = 1.0 if recipe.cuisine.strip().lower() in pref_cuisines else 0.5

    user_spice_val = SPICE_LEVELS.get(preferences.spice_level.strip().upper(), 1)
    recipe_spice_val = SPICE_LEVELS.get(recipe.spice_level.strip().upper(), 1)
    spice_diff = abs(user_spice_val - recipe_spice_val)

    if spice_diff == 0:
        spice_factor = 1.0
    elif spice_diff == 1:
        spice_factor = 0.7
    else:
        spice_factor = 0.4

    base_preference = cuisine_factor * spice_factor
    preference = min(1.0, max(0.0, base_preference + feedback_adjustment))

    # 5. Time Fit
    max_time = preferences.max_cooking_time or 45
    if recipe.cooking_time_minutes <= max_time:
        time_fit = 1.0
    else:
        time_fit = max(0.0, (2 * max_time - recipe.cooking_time_minutes) / float(max_time))

    # Final weighted score
    score = (
        0.35 * coverage
        + 0.35 * urgency
        + 0.10 * quantity_fit
        + 0.10 * preference
        + 0.10 * time_fit
    )

    match_percent = int(round(100.0 * coverage))

    # Expiring items used
    uses_expiring: list[UsesExpiringItem] = []
    for ri in matched_ingredients:
        inv = inventory_map[ri.ingredient_id]
        if inv.status in (FreshnessStatus.USE_FIRST, FreshnessStatus.USE_SOON):
            uses_expiring.append(
                UsesExpiringItem(
                    canonical_id=ri.ingredient_id,
                    status=inv.status.value,
                    days_left=inv.min_days_left,
                )
            )
    uses_expiring.sort(key=lambda x: (x.days_left, x.canonical_id))

    # Missing ingredients
    missing: list[MissingIngredient] = []
    total_missing_cost = Decimal("0.0")

    for ri in required_ingredients:
        needed_qty = Decimal(str(ri.qty)) * Decimal(str(scale_factor))
        inv_item = inventory_map.get(ri.ingredient_id)
        inv_qty = inv_item.total_quantity if inv_item else Decimal("0.0")

        # Estimate missing quantity
        if not inv_item or inv_qty <= 0:
            missing_qty = needed_qty
        elif inv_item.unit.strip().lower() == ri.unit.strip().lower():
            missing_qty = max(Decimal("0.0"), needed_qty - inv_qty)
        else:
            ing = ingredient_catalogue.get(ri.ingredient_id)
            try:
                if ing:
                    needed_g = convert_quantity_to_grams(ing, needed_qty, ri.unit)
                    inv_g = convert_quantity_to_grams(ing, inv_qty, inv_item.unit)
                    diff_g = max(Decimal("0.0"), needed_g - inv_g)
                    # Convert back to recipe unit if possible
                    missing_qty = (diff_g / needed_g) * needed_qty if needed_g > 0 else Decimal("0.0")
                else:
                    missing_qty = max(Decimal("0.0"), needed_qty - inv_qty)
            except Exception:
                missing_qty = max(Decimal("0.0"), needed_qty - inv_qty)

        if missing_qty > 0:
            ing = ingredient_catalogue.get(ri.ingredient_id)
            if ing:
                est_cost = calculate_estimated_cost(ing, missing_qty, ri.unit)
            else:
                est_cost = Decimal("0.0")
            total_missing_cost += est_cost
            missing.append(
                MissingIngredient(
                    canonical_id=ri.ingredient_id,
                    qty=float(round(missing_qty, 2)),
                    unit=ri.unit,
                    est_cost_inr=float(round(est_cost, 2)),
                )
            )

    reason = generate_recommendation_reason(
        matched_count=len(matched_ingredients),
        required_count=len(required_ingredients),
        uses_expiring=uses_expiring,
        ingredient_catalogue=ingredient_catalogue,
    )

    return ScoredRecipe(
        recipe=recipe,
        score=round(score, 4),
        coverage=round(coverage, 4),
        urgency=round(urgency, 4),
        quantity_fit=round(quantity_fit, 4),
        preference=round(preference, 4),
        time_fit=round(time_fit, 4),
        match_percent=match_percent,
        servings=target_servings,
        uses_expiring=uses_expiring,
        missing=missing,
        missing_cost_inr=float(round(total_missing_cost, 2)),
        reason=reason,
    )


def rank_recipes(
    recipes: list[Recipe],
    preferences: UserPreference,
    inventory_map: dict[str, InventoryItemSummary],
    ingredient_catalogue: dict[str, Ingredient],
    target_servings: int,
    limit: int = 5,
    feedback_map: dict[str, float] | None = None,
) -> list[ScoredRecipe]:
    """Filter, score, and rank recipes deterministically per PRD Section 8.2.

    Tie-breaking:
    1. Higher score (desc)
    2. Higher coverage (desc)
    3. Shorter cooking time (asc)
    4. Recipe ID alphabetically (asc)
    """
    if feedback_map is None:
        feedback_map = {}

    candidates: list[ScoredRecipe] = []

    for recipe in recipes:
        passes, _ = check_hard_filters(
            recipe=recipe,
            preferences=preferences,
            inventory_map=inventory_map,
            ingredient_catalogue=ingredient_catalogue,
        )
        if not passes:
            continue

        adj = feedback_map.get(recipe.id, 0.0)
        scored = score_recipe(
            recipe=recipe,
            preferences=preferences,
            inventory_map=inventory_map,
            ingredient_catalogue=ingredient_catalogue,
            target_servings=target_servings,
            feedback_adjustment=adj,
        )
        candidates.append(scored)

    # Sort deterministically
    candidates.sort(
        key=lambda s: (
            -s.score,
            -s.coverage,
            s.recipe.cooking_time_minutes,
            s.recipe.id,
        )
    )

    return candidates[:limit]
