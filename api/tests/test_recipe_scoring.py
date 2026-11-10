"""Unit tests for deterministic recipe scoring engine per PRD Section 8.2 and FR-043 to FR-045."""

from decimal import Decimal

from app.db.models.auth import UserPreference
from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient
from app.schemas.recommendations import UsesExpiringItem
from app.services.freshness import FreshnessStatus
from app.services.scoring import (
    InventoryItemSummary,
    check_hard_filters,
    generate_recommendation_reason,
    rank_recipes,
    score_recipe,
)


def _make_dummy_ingredient(
    ing_id: str,
    display_name: str,
    aliases: list[str] | None = None,
    allergen_group: str | None = None,
    price: float = 50.0,
) -> Ingredient:
    ing = Ingredient(
        id=ing_id,
        display_name=display_name,
        category="Vegetables",
        aliases=aliases or [],
        default_unit="g",
        grams_per_piece=Decimal("100"),
        ml_per_piece=None,
        price_inr_per_kg=Decimal(str(price)),
        allergen_group=allergen_group,
    )
    return ing


def _make_dummy_recipe(
    recipe_id: str,
    title: str = "Test Recipe",
    cuisine: str = "North Indian",
    diet: str = "VEGETARIAN",
    spice_level: str = "MEDIUM",
    cooking_time: int = 30,
    base_servings: int = 2,
    ingredients_spec: list[tuple[str, float, str, bool]] | None = None,
) -> Recipe:
    recipe = Recipe(
        id=recipe_id,
        title=title,
        cuisine=cuisine,
        diet=diet,
        spice_level=spice_level,
        cooking_time_minutes=cooking_time,
        base_servings=base_servings,
        steps=["Step 1", "Step 2", "Step 3"],
        nutrition={"kcal": 200, "protein_g": 5, "carbs_g": 30, "fat_g": 4, "fiber_g": 3},
        tags=["test"],
        source="CURATED",
        status="APPROVED",
    )
    r_ings: list[RecipeIngredient] = []
    for ing_id, qty, unit, is_opt in (ingredients_spec or []):
        ri = RecipeIngredient(
            recipe_id=recipe_id,
            ingredient_id=ing_id,
            qty=Decimal(str(qty)),
            unit=unit,
            is_optional=is_opt,
        )
        r_ings.append(ri)
    recipe.ingredients = r_ings
    return recipe


def _make_dummy_preferences(
    diet: str = "VEGETARIAN",
    spice_level: str = "MEDIUM",
    cuisines: list[str] | None = None,
    max_cooking_time: int = 30,
    allergies: list[str] | None = None,
    avoided_ingredients: list[str] | None = None,
    household_size: int = 2,
) -> UserPreference:
    pref = UserPreference(
        household_size=household_size,
        diet=diet,
        spice_level=spice_level,
        cuisines=cuisines if cuisines is not None else ["North Indian"],
        max_cooking_time=max_cooking_time,
        allergies=allergies or [],
        avoided_ingredients=avoided_ingredients or [],
        version=1,
    )
    return pref


def test_hard_filters_allergen_and_avoided():
    """Verify that recipes with allergens (canonical ID, alias, or allergen group) or avoided items are excluded."""
    pref = _make_dummy_preferences(allergies=["peanut", "dairy"], avoided_ingredients=["capsicum"])

    catalogue = {
        "peanut": _make_dummy_ingredient("peanut", "Peanut", aliases=["groundnut", "moongfali"]),
        "paneer": _make_dummy_ingredient("paneer", "Paneer", allergen_group="dairy"),
        "tomato": _make_dummy_ingredient("tomato", "Tomato", aliases=["tamatar"]),
        "capsicum": _make_dummy_ingredient("capsicum", "Capsicum", aliases=["shimla mirch"]),
        "potato": _make_dummy_ingredient("potato", "Potato", aliases=["aloo"]),
    }

    inv_map = {
        "tomato": InventoryItemSummary("tomato", "Tomato", Decimal("500"), "g", 5, FreshnessStatus.SAFE),
        "potato": InventoryItemSummary("potato", "Potato", Decimal("500"), "g", 5, FreshnessStatus.SAFE),
    }

    # 1. Contains canonical allergy
    r_allergy1 = _make_dummy_recipe("r1", ingredients_spec=[("peanut", 100, "g", False), ("tomato", 100, "g", False)])
    passes, reason = check_hard_filters(r_allergy1, pref, inv_map, catalogue)
    assert not passes
    assert "peanut" in (reason or "")

    # 2. Contains allergen group match (paneer has allergen_group="dairy")
    r_allergy2 = _make_dummy_recipe("r2", ingredients_spec=[("paneer", 200, "g", False), ("tomato", 100, "g", False)])
    passes, reason = check_hard_filters(r_allergy2, pref, inv_map, catalogue)
    assert not passes
    assert "dairy" in (reason or "")

    # 3. Contains avoided ingredient
    r_avoided = _make_dummy_recipe("r3", ingredients_spec=[("capsicum", 100, "g", False), ("potato", 100, "g", False)])
    passes, reason = check_hard_filters(r_avoided, pref, inv_map, catalogue)
    assert not passes
    assert "capsicum" in (reason or "")

    # 4. Clean recipe passes
    r_clean = _make_dummy_recipe("r4", ingredients_spec=[("potato", 200, "g", False), ("tomato", 100, "g", False)])
    passes, reason = check_hard_filters(r_clean, pref, inv_map, catalogue)
    assert passes
    assert reason is None


def test_hard_filters_diet_violations():
    """Verify diet hierarchy: VEGAN, VEGETARIAN, EGGLESS, NON_VEGETARIAN."""
    catalogue = {
        "potato": _make_dummy_ingredient("potato", "Potato"),
        "tomato": _make_dummy_ingredient("tomato", "Tomato"),
    }
    inv_map = {
        "potato": InventoryItemSummary("potato", "Potato", Decimal("500"), "g", 5, FreshnessStatus.SAFE),
        "tomato": InventoryItemSummary("tomato", "Tomato", Decimal("500"), "g", 5, FreshnessStatus.SAFE),
    }
    spec = [("potato", 200, "g", False), ("tomato", 100, "g", False)]

    r_vegan = _make_dummy_recipe("r_v", diet="VEGAN", ingredients_spec=spec)
    r_veg = _make_dummy_recipe("r_veg", diet="VEGETARIAN", ingredients_spec=spec)
    r_eggless = _make_dummy_recipe("r_eggless", diet="EGGLESS", ingredients_spec=spec)
    r_nonveg = _make_dummy_recipe("r_nonveg", diet="NON_VEGETARIAN", ingredients_spec=spec)

    # User is VEGAN
    pref_vegan = _make_dummy_preferences(diet="VEGAN")
    assert check_hard_filters(r_vegan, pref_vegan, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_veg, pref_vegan, inv_map, catalogue)[0] is False
    assert check_hard_filters(r_nonveg, pref_vegan, inv_map, catalogue)[0] is False

    # User is VEGETARIAN
    pref_veg = _make_dummy_preferences(diet="VEGETARIAN")
    assert check_hard_filters(r_vegan, pref_veg, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_veg, pref_veg, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_nonveg, pref_veg, inv_map, catalogue)[0] is False

    # User is EGGLESS
    pref_eggless = _make_dummy_preferences(diet="EGGLESS")
    assert check_hard_filters(r_vegan, pref_eggless, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_veg, pref_eggless, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_eggless, pref_eggless, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_nonveg, pref_eggless, inv_map, catalogue)[0] is False

    # User is NON_VEGETARIAN
    pref_nonveg = _make_dummy_preferences(diet="NON_VEGETARIAN")
    assert check_hard_filters(r_vegan, pref_nonveg, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_veg, pref_nonveg, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_nonveg, pref_nonveg, inv_map, catalogue)[0] is True


def test_hard_filters_cooking_time_boundary():
    """Verify cooking time boundary: <= 2x max_cooking_time passes, > 2x fails."""
    catalogue = {"potato": _make_dummy_ingredient("potato", "Potato")}
    inv_map = {"potato": InventoryItemSummary("potato", "Potato", Decimal("500"), "g", 5, FreshnessStatus.SAFE)}
    spec = [("potato", 200, "g", False)]

    pref = _make_dummy_preferences(max_cooking_time=30)  # 2x is 60m

    r_at_limit = _make_dummy_recipe("r_60", cooking_time=60, ingredients_spec=spec)
    r_over_limit = _make_dummy_recipe("r_61", cooking_time=61, ingredients_spec=spec)
    r_under_limit = _make_dummy_recipe("r_45", cooking_time=45, ingredients_spec=spec)

    assert check_hard_filters(r_under_limit, pref, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_at_limit, pref, inv_map, catalogue)[0] is True
    assert check_hard_filters(r_over_limit, pref, inv_map, catalogue)[0] is False


def test_hard_filters_coverage_boundary():
    """Verify coverage boundary: coverage >= 0.40 passes, < 0.40 fails."""
    catalogue = {f"item_{i}": _make_dummy_ingredient(f"item_{i}", f"Item {i}") for i in range(1, 6)}

    # Recipe requires 5 non-optional items
    spec = [(f"item_{i}", 100, "g", False) for i in range(1, 6)]
    recipe = _make_dummy_recipe("r_5items", ingredients_spec=spec)
    pref = _make_dummy_preferences()

    # Case 1: 1 of 5 matched = 20% (0.20 < 0.40 -> fails)
    inv_1 = {"item_1": InventoryItemSummary("item_1", "Item 1", Decimal("100"), "g", 5, FreshnessStatus.SAFE)}
    passes_1, reason_1 = check_hard_filters(recipe, pref, inv_1, catalogue)
    assert not passes_1
    assert "0.20" in (reason_1 or "")

    # Case 2: 2 of 5 matched = 40% (0.40 == 0.40 -> passes)
    inv_2 = {
        "item_1": InventoryItemSummary("item_1", "Item 1", Decimal("100"), "g", 5, FreshnessStatus.SAFE),
        "item_2": InventoryItemSummary("item_2", "Item 2", Decimal("100"), "g", 5, FreshnessStatus.SAFE),
    }
    passes_2, reason_2 = check_hard_filters(recipe, pref, inv_2, catalogue)
    assert passes_2
    assert reason_2 is None

    # Case 3: 3 of 5 matched = 60% (> 0.40 -> passes)
    inv_3 = {
        "item_1": InventoryItemSummary("item_1", "Item 1", Decimal("100"), "g", 5, FreshnessStatus.SAFE),
        "item_2": InventoryItemSummary("item_2", "Item 2", Decimal("100"), "g", 5, FreshnessStatus.SAFE),
        "item_3": InventoryItemSummary("item_3", "Item 3", Decimal("100"), "g", 5, FreshnessStatus.SAFE),
    }
    passes_3, reason_3 = check_hard_filters(recipe, pref, inv_3, catalogue)
    assert passes_3


def test_exact_scoring_components():
    """Verify exact formula weights and individual component values per Section 8.2."""
    catalogue = {
        "spinach": _make_dummy_ingredient("spinach", "Spinach", price=40),
        "potato": _make_dummy_ingredient("potato", "Potato", price=30),
    }

    # Recipe: 2 servings, 25m, North Indian, MEDIUM spice
    recipe = _make_dummy_recipe(
        "aloo_palak",
        cuisine="North Indian",
        spice_level="MEDIUM",
        cooking_time=25,
        base_servings=2,
        ingredients_spec=[
            ("spinach", 200, "g", False),
            ("potato", 200, "g", False),
        ],
    )

    # Preferences: household_size=2, max_cooking_time=30, preferred North Indian, MEDIUM spice
    pref = _make_dummy_preferences(
        household_size=2,
        max_cooking_time=30,
        cuisines=["North Indian"],
        spice_level="MEDIUM",
    )

    # Inventory:
    # spinach has 1 day left (USE_FIRST) -> u(spinach) = 1 - 1/7 = 6/7 ≈ 0.8571
    # potato has 7 days left (SAFE) -> u(potato) = 0.0
    # Both have 200g in stock (quantity_fit = 1.0 each)
    inv_map = {
        "spinach": InventoryItemSummary("spinach", "Spinach", Decimal("200"), "g", 1, FreshnessStatus.USE_FIRST),
        "potato": InventoryItemSummary("potato", "Potato", Decimal("200"), "g", 7, FreshnessStatus.SAFE),
    }

    scored = score_recipe(
        recipe=recipe,
        preferences=pref,
        inventory_map=inv_map,
        ingredient_catalogue=catalogue,
        target_servings=2,
    )

    # 1. Coverage = 2/2 = 1.0
    assert scored.coverage == 1.0
    assert scored.match_percent == 100

    # 2. Urgency = (6/7 + 0.0) / 2 = 3/7 ≈ 0.4286
    expected_urgency = round((6.0 / 7.0 + 0.0) / 2.0, 4)
    assert scored.urgency == expected_urgency

    # 3. Quantity fit = (1.0 + 1.0) / 2 = 1.0
    assert scored.quantity_fit == 1.0

    # 4. Preference = cuisine (1.0) * spice (1.0) = 1.0
    assert scored.preference == 1.0

    # 5. Time fit: cooking_time 25 <= max_time 30 -> 1.0
    assert scored.time_fit == 1.0

    # Final score = 0.35 * 1.0 + 0.35 * (3/7) + 0.10 * 1.0 + 0.10 * 1.0 + 0.10 * 1.0
    expected_score = round(0.35 * 1.0 + 0.35 * (3.0 / 7.0) + 0.10 * 1.0 + 0.10 * 1.0 + 0.10 * 1.0, 4)
    assert scored.score == expected_score

    # Expiring items uses: spinach (days_left = 1, USE_FIRST)
    assert len(scored.uses_expiring) == 1
    assert scored.uses_expiring[0].canonical_id == "spinach"
    assert scored.uses_expiring[0].days_left == 1

    # Missing: 0 items missing
    assert len(scored.missing) == 0
    assert scored.missing_cost_inr == 0.0

    # Reason mentions spinach expiring tomorrow
    assert "spinach expiring tomorrow" in scored.reason.lower()


def test_time_fit_linear_decrease():
    """Verify time_fit decreases linearly between max_time and 2*max_time."""
    catalogue = {"potato": _make_dummy_ingredient("potato", "Potato")}
    inv_map = {"potato": InventoryItemSummary("potato", "Potato", Decimal("200"), "g", 7, FreshnessStatus.SAFE)}
    pref = _make_dummy_preferences(max_cooking_time=30)

    # Case 1: time == max_time (30) -> time_fit = 1.0
    r30 = _make_dummy_recipe("r30", cooking_time=30, ingredients_spec=[("potato", 100, "g", False)])
    s30 = score_recipe(r30, pref, inv_map, catalogue, target_servings=2)
    assert s30.time_fit == 1.0

    # Case 2: time == 45 (halfway between 30 and 60) -> time_fit = 0.5
    r45 = _make_dummy_recipe("r45", cooking_time=45, ingredients_spec=[("potato", 100, "g", False)])
    s45 = score_recipe(r45, pref, inv_map, catalogue, target_servings=2)
    assert s45.time_fit == 0.5

    # Case 3: time == 60 (at 2x max_time) -> time_fit = 0.0
    r60 = _make_dummy_recipe("r60", cooking_time=60, ingredients_spec=[("potato", 100, "g", False)])
    s60 = score_recipe(r60, pref, inv_map, catalogue, target_servings=2)
    assert s60.time_fit == 0.0


def test_spice_match_values():
    """Verify spice match factors: exact = 1.0, adjacent = 0.7, distant = 0.4."""
    catalogue = {"potato": _make_dummy_ingredient("potato", "Potato")}
    inv_map = {"potato": InventoryItemSummary("potato", "Potato", Decimal("200"), "g", 7, FreshnessStatus.SAFE)}
    spec = [("potato", 100, "g", False)]

    # User pref: MILD
    pref = _make_dummy_preferences(spice_level="MILD", cuisines=["North Indian"])

    r_mild = _make_dummy_recipe("r_mild", spice_level="MILD", cuisine="North Indian", ingredients_spec=spec)
    r_med = _make_dummy_recipe("r_med", spice_level="MEDIUM", cuisine="North Indian", ingredients_spec=spec)
    r_hot = _make_dummy_recipe("r_hot", spice_level="HOT", cuisine="North Indian", ingredients_spec=spec)

    s_mild = score_recipe(r_mild, pref, inv_map, catalogue, target_servings=2)
    s_med = score_recipe(r_med, pref, inv_map, catalogue, target_servings=2)
    s_hot = score_recipe(r_hot, pref, inv_map, catalogue, target_servings=2)

    assert s_mild.preference == 1.0
    assert s_med.preference == 0.7
    assert s_hot.preference == 0.4


def test_deterministic_ranking_and_tie_breaking():
    """Verify tie-breaking order: score (desc), coverage (desc), cooking_time (asc), recipe_id (asc)."""
    catalogue = {
        "potato": _make_dummy_ingredient("potato", "Potato"),
        "onion": _make_dummy_ingredient("onion", "Onion"),
    }
    inv_map = {
        "potato": InventoryItemSummary("potato", "Potato", Decimal("200"), "g", 7, FreshnessStatus.SAFE),
    }

    pref = _make_dummy_preferences()

    # Recipes with identical score and coverage, different cooking times
    r_fast = _make_dummy_recipe("r_fast", cooking_time=20, ingredients_spec=[("potato", 100, "g", False)])
    r_slow = _make_dummy_recipe("r_slow", cooking_time=30, ingredients_spec=[("potato", 100, "g", False)])

    ranked = rank_recipes([r_slow, r_fast], pref, inv_map, catalogue, target_servings=2)
    assert ranked[0].recipe.id == "r_fast"
    assert ranked[1].recipe.id == "r_slow"

    # Recipes with identical score, coverage, and cooking time -> alphabetical by ID
    r_b = _make_dummy_recipe("b_recipe", cooking_time=25, ingredients_spec=[("potato", 100, "g", False)])
    r_a = _make_dummy_recipe("a_recipe", cooking_time=25, ingredients_spec=[("potato", 100, "g", False)])
    ranked_alpha = rank_recipes([r_b, r_a], pref, inv_map, catalogue, target_servings=2)
    assert ranked_alpha[0].recipe.id == "a_recipe"
    assert ranked_alpha[1].recipe.id == "b_recipe"


def test_reason_generation_templates():
    """Verify explanation strings for 0 days, 1 day, multiple items, and fresh matches."""
    catalogue = {
        "tomato": _make_dummy_ingredient("tomato", "Tomato"),
        "coriander": _make_dummy_ingredient("coriander", "Coriander Leaves"),
    }

    # 1. Expiring today
    exp_today = [UsesExpiringItem(canonical_id="tomato", status="USE_FIRST", days_left=0)]
    r_today = generate_recommendation_reason(3, 4, exp_today, catalogue)
    assert "expiring today" in r_today
    assert "3 of 4" in r_today

    # 2. Expiring tomorrow
    exp_tomorrow = [UsesExpiringItem(canonical_id="tomato", status="USE_FIRST", days_left=1)]
    r_tomorrow = generate_recommendation_reason(3, 4, exp_tomorrow, catalogue)
    assert "expiring tomorrow" in r_tomorrow

    # 3. Multiple expiring items
    exp_multi = [
        UsesExpiringItem(canonical_id="tomato", status="USE_FIRST", days_left=1),
        UsesExpiringItem(canonical_id="coriander", status="USE_SOON", days_left=2),
    ]
    r_multi = generate_recommendation_reason(4, 4, exp_multi, catalogue)
    assert "tomato and coriander leaves expiring soon" in r_multi.lower()

    # 4. Fresh complete match
    r_all_fresh = generate_recommendation_reason(4, 4, [], catalogue)
    assert "all 4 required ingredients fresh" in r_all_fresh.lower()

    # 5. Partial fresh match
    r_part_fresh = generate_recommendation_reason(2, 4, [], catalogue)
    assert "2 of 4 required items fresh" in r_part_fresh.lower()
