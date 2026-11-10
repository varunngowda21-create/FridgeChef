"""Comprehensive unit and integration tests for Phase 6: AI Recipe Generation Fallback & Budget Controls
per PRD Sections 6.5, 7.5, 8.3, 9.4, 9.5, 9.6, 10; FR-041, FR-042; NFR-011, NFR-041.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from groq import RateLimitError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.analytics import LLMCall
from app.db.models.auth import User, UserPreference
from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient
from app.llm.budget import (
    calculate_call_cost_usd,
    get_monthly_llm_spend_usd,
    is_llm_budget_exceeded,
)
from app.llm.recipe_gen import (
    GeneratedRecipe,
    GeneratedRecipeIngredient,
    call_groq_recipe_generation,
    validate_generated_recipe,
)


def _create_authenticated_user(client: TestClient, name: str = "Chef") -> tuple[str, str, uuid.UUID]:
    """Helper to register a user and return (email, token, user_id)."""
    email = f"chef_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": name},
    )
    assert resp.status_code == 201
    data = resp.json()
    user_id = uuid.UUID(data["user"]["id"])
    return email, data["access_token"], user_id


def _mock_groq_chat_response(recipes_payload: dict, prompt_tokens: int = 500, completion_tokens: int = 400):
    """Helper to mock a Groq API response object."""
    content_str = json.dumps(recipes_payload)
    usage_mock = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    message_mock = MagicMock(content=content_str)
    choice_mock = MagicMock(message=message_mock)
    return MagicMock(choices=[choice_mock], usage=usage_mock)


def _get_catalogue_map(db: Session) -> dict[str, Ingredient]:
    return {ing.id: ing for ing in db.query(Ingredient).all()}


# =====================================================================
# 1. Validation Logic Tests (FR-042, PRD 8.3, 9.4)
# =====================================================================

def test_validate_generated_recipe_success(db_session: Session):
    """A well-formed generated recipe with valid canonical IDs passes validation."""
    cat_map = _get_catalogue_map(db_session)
    pref = UserPreference(
        user_id=uuid.uuid4(),
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cuisines=["North Indian"],
        max_cooking_time=45,
        allergies=[],
        avoided_ingredients=[],
    )

    valid_recipe = GeneratedRecipe(
        title="Quick Jeera Aloo",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=25,
        base_servings=2,
        ingredients=[
            GeneratedRecipeIngredient(canonical_id="potato", qty=400.0, unit="g", is_optional=False),
            GeneratedRecipeIngredient(canonical_id="cumin_seeds", qty=10.0, unit="g", is_optional=False),
            GeneratedRecipeIngredient(canonical_id="turmeric_powder", qty=5.0, unit="g", is_optional=True),
        ],
        steps=[
            "Boil and peel the potatoes, then cube them into bite-sized pieces.",
            "Heat oil in a pan, add cumin seeds, and let them crackle.",
            "Add the cubed potatoes, turmeric powder, and salt. Saute for 5 minutes.",
        ],
        nutrition={"kcal": 210.0, "protein_g": 4.0, "carbs_g": 35.0, "fat_g": 6.0, "fiber_g": 4.0},
        tags=["quick", "potato"],
    )

    is_valid, reason = validate_generated_recipe(valid_recipe, cat_map, pref)
    assert is_valid is True
    assert reason is None


def test_validate_generated_recipe_rejects_empty_title_or_cuisine(db_session: Session):
    cat_map = _get_catalogue_map(db_session)
    pref = UserPreference(user_id=uuid.uuid4(), diet="VEGETARIAN")

    r1 = GeneratedRecipe(
        title="",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r1, cat_map, pref)
    assert is_valid is False
    assert "title" in reason.lower()

    r2 = GeneratedRecipe(
        title="Aloo Fry",
        cuisine="   ",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r2, cat_map, pref)
    assert is_valid is False
    assert "cuisine" in reason.lower()


def test_validate_generated_recipe_rejects_invalid_enums_and_bounds(db_session: Session):
    cat_map = _get_catalogue_map(db_session)
    pref = UserPreference(user_id=uuid.uuid4(), diet="VEGETARIAN")

    # Invalid diet
    r_diet = GeneratedRecipe(
        title="Keto Dish",
        cuisine="Indian",
        diet="KETO_MEAT",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r_diet, cat_map, pref)
    assert is_valid is False
    assert "invalid diet" in reason.lower()

    # Invalid spice level
    r_spice = GeneratedRecipe(
        title="Mild Dish",
        cuisine="Indian",
        diet="VEGETARIAN",
        spice_level="EXTRA_HOT_EXTREME",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r_spice, cat_map, pref)
    assert is_valid is False
    assert "invalid spice" in reason.lower()

    # Cooking time out of bounds (< 5 or > 180)
    r_time = GeneratedRecipe(
        title="Too Fast Dish",
        cuisine="Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=2,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r_time, cat_map, pref)
    assert is_valid is False
    assert "cooking time" in reason.lower()

    # Step count out of bounds (< 3 or > 12) per PRD Section 8.3
    r_few_steps = GeneratedRecipe(
        title="Fast Aloo",
        cuisine="Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Just boil it.", "Eat it."],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r_few_steps, cat_map, pref)
    assert is_valid is False
    assert "step count" in reason.lower()

    # Blank/empty step string
    r_empty_step = GeneratedRecipe(
        title="Aloo Step",
        cuisine="Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "   ", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r_empty_step, cat_map, pref)
    assert is_valid is False
    assert "empty" in reason.lower()


def test_validate_generated_recipe_discards_unknown_canonical_id(db_session: Session):
    """PRD Section 9.4: Discard recipes with unknown canonical IDs (do not attempt to repair)."""
    cat_map = _get_catalogue_map(db_session)
    pref = UserPreference(user_id=uuid.uuid4(), diet="VEGETARIAN")

    r_unknown = GeneratedRecipe(
        title="Mystery Vegetable Dish",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=25,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[
            GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g"),
            GeneratedRecipeIngredient(canonical_id="alien_root_vegetable_xyz", qty=100.0, unit="g"),
        ],
    )
    is_valid, reason = validate_generated_recipe(r_unknown, cat_map, pref)
    assert is_valid is False
    assert "unknown canonical ingredient id" in reason.lower()


def test_validate_generated_recipe_discards_duplicate_canonical_ids(db_session: Session):
    """Rejects recipes that provide duplicate canonical IDs to preserve DB unique constraint."""
    cat_map = _get_catalogue_map(db_session)
    pref = UserPreference(user_id=uuid.uuid4(), diet="VEGETARIAN")

    r_dup = GeneratedRecipe(
        title="Double Potato",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[
            GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g"),
            GeneratedRecipeIngredient(canonical_id="potato", qty=100.0, unit="g"),
        ],
    )
    is_valid, reason = validate_generated_recipe(r_dup, cat_map, pref)
    assert is_valid is False
    assert "duplicate canonical ingredient id" in reason.lower()


def test_validate_generated_recipe_discards_invalid_quantities_or_no_required_items(db_session: Session):
    cat_map = _get_catalogue_map(db_session)
    pref = UserPreference(user_id=uuid.uuid4(), diet="VEGETARIAN")

    # Negative quantity
    r_neg = GeneratedRecipe(
        title="Negative Aloo",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=-50.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r_neg, cat_map, pref)
    assert is_valid is False
    assert "invalid ingredient quantity" in reason.lower()

    # All ingredients optional
    r_all_opt = GeneratedRecipe(
        title="Optional Aloo",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g", is_optional=True)],
    )
    is_valid, reason = validate_generated_recipe(r_all_opt, cat_map, pref)
    assert is_valid is False
    assert "no non-optional ingredients" in reason.lower()


def test_validate_generated_recipe_discards_allergen_and_diet_violations(db_session: Session):
    """PRD Section 9.4: Discard recipes that break diet or allergy rules (double-check server-side)."""
    cat_map = _get_catalogue_map(db_session)

    # 1. Allergy constraint (e.g. peanut allergy)
    pref_allergy = UserPreference(
        user_id=uuid.uuid4(),
        diet="VEGETARIAN",
        allergies=["peanuts"],
        avoided_ingredients=[],
    )
    r_peanut = GeneratedRecipe(
        title="Peanut Curry",
        cuisine="Maharashtrian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[
            GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g"),
            GeneratedRecipeIngredient(canonical_id="peanuts", qty=50.0, unit="g"),
        ],
    )
    is_valid, reason = validate_generated_recipe(r_peanut, cat_map, pref_allergy)
    assert is_valid is False
    assert "violates user constraints" in reason.lower()

    # 2. Avoided ingredient constraint (e.g. coriander_leaves avoided)
    pref_avoid = UserPreference(
        user_id=uuid.uuid4(),
        diet="VEGETARIAN",
        allergies=[],
        avoided_ingredients=["coriander_leaves"],
    )
    r_coriander = GeneratedRecipe(
        title="Dhania Aloo",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[
            GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g"),
            GeneratedRecipeIngredient(canonical_id="coriander_leaves", qty=20.0, unit="g"),
        ],
    )
    is_valid, reason = validate_generated_recipe(r_coriander, cat_map, pref_avoid)
    assert is_valid is False
    assert "violates user constraints" in reason.lower()

    # 3. Diet violation (e.g. non-veg chicken recipe for vegetarian user)
    pref_veg = UserPreference(
        user_id=uuid.uuid4(),
        diet="VEGETARIAN",
    )
    r_chicken = GeneratedRecipe(
        title="Chicken Curry",
        cuisine="North Indian",
        diet="NON_VEGETARIAN",
        spice_level="HOT",
        cooking_time_minutes=40,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[
            GeneratedRecipeIngredient(canonical_id="chicken_breast", qty=500.0, unit="g"),
            GeneratedRecipeIngredient(canonical_id="onion", qty=100.0, unit="g"),
        ],
    )
    is_valid, reason = validate_generated_recipe(r_chicken, cat_map, pref_veg)
    assert is_valid is False
    assert "violates user constraints" in reason.lower()

    # 4. Cooking time constraint (exceeds 2x max_cooking_time)
    pref_time = UserPreference(
        user_id=uuid.uuid4(),
        diet="VEGETARIAN",
        max_cooking_time=30,  # 2x limit = 60
    )
    r_slow = GeneratedRecipe(
        title="Slow Dal",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=90,
        steps=["Step 1", "Step 2", "Step 3"],
        ingredients=[GeneratedRecipeIngredient(canonical_id="potato", qty=200.0, unit="g")],
    )
    is_valid, reason = validate_generated_recipe(r_slow, cat_map, pref_time)
    assert is_valid is False
    assert "violates user constraints" in reason.lower()


# =====================================================================
# 2. Monthly Budget Cap Tests (PRD 9.6, NFR-041)
# =====================================================================

def test_calculate_call_cost_usd():
    """Verify call cost computation based on prompt and completion token counts."""
    # llama-3.3-70b-versatile: prompt $0.59/M, completion $0.79/M
    cost = calculate_call_cost_usd("llama-3.3-70b-versatile", 1_000_000, 1_000_000)
    assert round(cost, 2) == 1.38

    # meta-llama/llama-4-scout-17b-16e-instruct: prompt $0.15/M, completion $0.60/M
    cost_vision = calculate_call_cost_usd("meta-llama/llama-4-scout-17b-16e-instruct", 1_000_000, 1_000_000)
    assert round(cost_vision, 2) == 0.75

    # None tokens handled gracefully
    assert calculate_call_cost_usd("llama-3.3-70b-versatile", None, None) == 0.0


def test_monthly_llm_spend_calculation_and_budget_exceeded(db_session: Session):
    """PRD Section 9.6: If spend exceeds 80% of budget, disable AI recipe generation."""
    # Clean up any leftover 2030 records from previous test runs
    db_session.query(LLMCall).filter(LLMCall.created_at >= datetime(2030, 1, 1, tzinfo=timezone.utc)).delete()
    db_session.commit()

    # Create test user for foreign key
    user = User(email=f"budget_{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", display_name="B")
    db_session.add(user)
    db_session.commit()

    now = datetime(2030, 5, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Insert a record in the previous month (should be excluded)
    prev_month_call = LLMCall(
        user_id=user.id,
        purpose="RECIPE_GEN",
        model="llama-3.3-70b-versatile",
        prompt_version="recipes.v1",
        prompt_tokens=10_000_000,  # $5.90
        completion_tokens=10_000_000,  # $7.90
        latency_ms=1200,
        status="OK",
        created_at=datetime(2030, 4, 28, 12, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(prev_month_call)
    db_session.commit()

    spend = get_monthly_llm_spend_usd(db_session, now=now)
    assert spend == 0.0

    # Insert current month record: 5,000,000 prompt + 5,000,000 completion ($2.95 + $3.95 = $6.90)
    current_call = LLMCall(
        user_id=user.id,
        purpose="RECIPE_GEN",
        model="llama-3.3-70b-versatile",
        prompt_version="recipes.v1",
        prompt_tokens=5_000_000,
        completion_tokens=5_000_000,
        latency_ms=1500,
        status="OK",
        created_at=datetime(2030, 5, 5, 10, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(current_call)
    db_session.commit()

    spend = get_monthly_llm_spend_usd(db_session, now=now)
    assert round(spend, 2) == 6.90

    # Budget $10.00: 80% threshold is $8.00. Current spend $6.90 < $8.00 -> NOT exceeded
    assert is_llm_budget_exceeded(db_session, budget_usd=10.0, now=now) is False

    # Budget $8.00: 80% threshold is $6.40. Current spend $6.90 >= $6.40 -> EXCEEDED
    assert is_llm_budget_exceeded(db_session, budget_usd=8.0, now=now) is True

    # Unset/None budget -> NEVER exceeded
    assert is_llm_budget_exceeded(db_session, budget_usd=None, now=now) is False
    assert is_llm_budget_exceeded(db_session, budget_usd=0.0, now=now) is False


# =====================================================================
# 3. AI Generation Pipeline & 30-Minute Caching Tests
# =====================================================================

@pytest.mark.asyncio
async def test_call_groq_recipe_generation_success_and_caching(db_session: Session):
    """PRD Section 9.4 & 9.6: Calls Groq, persists recipes with source='AI' and status='PENDING_REVIEW',

    and caches result per (inventory, preferences) for 30 minutes.
    """
    cat_map = _get_catalogue_map(db_session)
    user = User(email=f"gen_{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", display_name="Gen")
    db_session.add(user)
    db_session.commit()

    pref = UserPreference(
        user_id=user.id,
        household_size=2,
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cuisines=["North Indian"],
        max_cooking_time=45,
        allergies=[],
        avoided_ingredients=[],
        version=1,
    )
    db_session.add(pref)
    db_session.commit()

    available_items = [
        {"canonical_id": "potato", "display_name": "Potato", "quantity": 500, "unit": "g", "status": "USE_FIRST"},
        {"canonical_id": "cumin_seeds", "display_name": "Cumin Seeds", "quantity": 50, "unit": "g", "status": "SAFE"},
    ]

    mock_llm_recipes = {
        "recipes": [
            {
                "title": "Jeera Aloo Fry",
                "cuisine": "North Indian",
                "diet": "VEGETARIAN",
                "spice_level": "MEDIUM",
                "cooking_time_minutes": 20,
                "base_servings": 2,
                "ingredients": [
                    {"canonical_id": "potato", "qty": 300.0, "unit": "g", "is_optional": False},
                    {"canonical_id": "cumin_seeds", "qty": 10.0, "unit": "g", "is_optional": False},
                ],
                "steps": [
                    "Peel and dice the potatoes.",
                    "Heat oil in a pan, add cumin seeds until fragrant.",
                    "Add potatoes and saute until golden and tender.",
                ],
                "nutrition": {"kcal": 220.0, "protein_g": 4.0, "carbs_g": 35.0, "fat_g": 7.0, "fiber_g": 4.0},
                "tags": ["quick", "ai-dish"],
            }
        ]
    }
    mock_resp = _mock_groq_chat_response(mock_llm_recipes, prompt_tokens=400, completion_tokens=250)

    # 1. First Call: Groq invoked, recipes saved to DB, cache populated
    with patch("app.llm.recipe_gen.execute_groq_call_with_retries", new=AsyncMock(return_value=mock_resp)) as mock_exec:
        recipes = await call_groq_recipe_generation(
            db=db_session,
            user=user,
            available_items=available_items,
            preferences=pref,
            catalogue_map=cat_map,
            num_recipes=1,
        )
        assert mock_exec.call_count == 1
        assert len(recipes) == 1
        saved = recipes[0]
        assert saved.source == "AI"
        assert saved.status == "PENDING_REVIEW"
        assert saved.created_by_user_id == user.id
        assert saved.title == "Jeera Aloo Fry"
        assert len(saved.ingredients) == 2

        # Verify llm_calls telemetry logged (NFR-041)
        llm_record = db_session.query(LLMCall).filter(
            LLMCall.user_id == user.id,
            LLMCall.purpose == "RECIPE_GEN",
        ).order_by(LLMCall.created_at.desc()).first()
        assert llm_record is not None
        assert llm_record.status == "OK"
        assert llm_record.prompt_tokens == 400
        assert llm_record.completion_tokens == 250

    # 2. Second Call with identical inventory and preferences: Must HIT 30-min cache and NOT call Groq
    with patch("app.llm.recipe_gen.execute_groq_call_with_retries", new=AsyncMock()) as mock_exec_2:
        cached_recipes = await call_groq_recipe_generation(
            db=db_session,
            user=user,
            available_items=available_items,
            preferences=pref,
            catalogue_map=cat_map,
            num_recipes=1,
        )
        assert mock_exec_2.call_count == 0  # Groq NOT called
        assert len(cached_recipes) == 1
        assert cached_recipes[0].id == saved.id


@pytest.mark.asyncio
async def test_call_groq_recipe_generation_respects_budget_cap(db_session: Session):
    """When budget cap reached, call_groq_recipe_generation exits early without calling Groq."""
    cat_map = _get_catalogue_map(db_session)
    user = User(email=f"cap_{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", display_name="Cap")
    db_session.add(user)
    db_session.commit()

    pref = UserPreference(user_id=user.id, diet="VEGETARIAN")
    db_session.add(pref)
    db_session.commit()

    settings = Settings(LLM_MONTHLY_BUDGET_USD=0.01)  # tiny budget

    # Insert an LLM call that immediately consumes the budget
    db_session.add(
        LLMCall(
            user_id=user.id,
            purpose="RECIPE_GEN",
            model="llama-3.3-70b-versatile",
            prompt_version="recipes.v1",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            latency_ms=1000,
            status="OK",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    try:
        with patch("app.llm.recipe_gen.execute_groq_call_with_retries", new=AsyncMock()) as mock_exec:
            recipes = await call_groq_recipe_generation(
                db=db_session,
                user=user,
                available_items=[{"canonical_id": "potato", "quantity": 100}],
                preferences=pref,
                catalogue_map=cat_map,
                settings=settings,
            )
            assert mock_exec.call_count == 0
            assert recipes == []
    finally:
        db_session.query(LLMCall).filter(LLMCall.user_id == user.id).delete()
        db_session.commit()


# =====================================================================
# 4. End-to-End Recommendations API Integration with AI Fallback
# =====================================================================

def test_recommendations_triggers_ai_fallback_when_curated_under_5(client: TestClient, db_session: Session):
    """PRD Section 6.5 FR-041: Recipe recommendation triggers AI recipe generation

    when fewer than 5 curated recipes score >= 40% match.
    """
    _, token, user_id = _create_authenticated_user(client, "Sparse Fridge Chef")
    headers = {"Authorization": f"Bearer {token}"}

    # Add sparse inventory (only capsicum and mustard seeds) which matches < 5 curated recipes
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "capsicum", "quantity": 2, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    )
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "mustard_seeds", "quantity": 20, "unit": "g", "storage": "PANTRY"},
        headers=headers,
    )

    mock_llm_response = {
        "recipes": [
            {
                "title": "Spiced Capsicum Stir-Fry",
                "cuisine": "South Indian",
                "diet": "VEGETARIAN",
                "spice_level": "MEDIUM",
                "cooking_time_minutes": 15,
                "base_servings": 2,
                "ingredients": [
                    {"canonical_id": "capsicum", "qty": 2.0, "unit": "piece", "is_optional": False},
                    {"canonical_id": "mustard_seeds", "qty": 5.0, "unit": "g", "is_optional": False},
                ],
                "steps": [
                    "Dice the capsicum into cubes.",
                    "Temper mustard seeds in hot oil.",
                    "Add capsicum and saute for 5-7 minutes.",
                ],
                "nutrition": {"kcal": 90.0, "protein_g": 2.0, "carbs_g": 9.0, "fat_g": 4.0, "fiber_g": 3.0},
                "tags": ["quick", "capsicum"],
            }
        ]
    }
    mock_resp = _mock_groq_chat_response(mock_llm_response)

    with patch("app.llm.recipe_gen.execute_groq_call_with_retries", new=AsyncMock(return_value=mock_resp)):
        resp = client.get("/api/v1/recommendations?limit=5", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["degraded"] is False

    # At least one item should be from AI source
    ai_items = [it for it in data["items"] if it["source"] == "AI"]
    assert len(ai_items) >= 1
    assert ai_items[0]["title"] == "Spiced Capsicum Stir-Fry"
    assert ai_items[0]["match_percent"] >= 40


def test_recommendations_groq_failure_sets_degraded_mode(client: TestClient):
    """PRD Section 7.2 (NFR-011): If Groq is unavailable, recommendations fall back

    to curated recipes only and set degraded = True.
    """
    _, token, _ = _create_authenticated_user(client, "Degraded Chef")
    headers = {"Authorization": f"Bearer {token}"}

    # Add sparse inventory to trigger AI fallback
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "capsicum", "quantity": 2, "unit": "piece", "storage": "FRIDGE"},
        headers=headers,
    )

    # Groq fails with RateLimitError
    with patch("app.llm.recipe_gen.execute_groq_call_with_retries", side_effect=RateLimitError("Rate limit exceeded", response=MagicMock(), body=None)):
        resp = client.get("/api/v1/recommendations?limit=5", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["degraded"] is True


def test_ai_recipes_user_isolation(client: TestClient, db_session: Session):
    """PRD Section 6.1 (FR-005) & 9.4: AI generated recipes with status 'PENDING_REVIEW'

    belong strictly to the creating user and are never visible to other users.
    """
    _, token_a, user_id_a = _create_authenticated_user(client, "User A")
    _, token_b, user_id_b = _create_authenticated_user(client, "User B")

    # Manually insert an AI recipe created by User A
    ai_recipe = Recipe(
        id=f"ai-test-secret-{uuid.uuid4().hex[:6]}",
        title="Secret AI Curry for User A",
        cuisine="North Indian",
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cooking_time_minutes=20,
        base_servings=2,
        steps=["Step 1", "Step 2", "Step 3"],
        nutrition={"kcal": 200},
        tags=["ai-generated"],
        source="AI",
        status="PENDING_REVIEW",
        created_by_user_id=user_id_a,
    )
    ai_recipe.ingredients = [
        RecipeIngredient(
            recipe_id=ai_recipe.id,
            ingredient_id="potato",
            qty=Decimal("200"),
            unit="g",
            is_optional=False,
        )
    ]
    db_session.add(ai_recipe)
    db_session.commit()

    # User B requests recommendations with potato in inventory
    client.post(
        "/api/v1/inventory",
        json={"canonical_id": "potato", "quantity": 1000, "unit": "g", "storage": "PANTRY"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    resp_b = client.get("/api/v1/recommendations?limit=20", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    b_recipe_ids = [it["recipe_id"] for it in resp_b.json()["items"]]

    # User B must NOT see User A's AI recipe
    assert ai_recipe.id not in b_recipe_ids
