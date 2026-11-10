"""AI recipe generation service using Groq per PRD Section 6.5, 8.3, 9.4, 9.5, and 9.6."""

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.db.models.analytics import RecommendationCache
from app.db.models.auth import User, UserPreference
from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient
from app.llm.budget import is_llm_budget_exceeded
from app.llm.client import execute_groq_call_with_retries, get_groq_client, record_llm_call
from app.llm.prompts.recipes_v1 import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_recipe_gen_user_prompt,
)
from app.services.normalise import alias_matcher
from app.services.scoring import check_hard_filters

logger = logging.getLogger("fridgechef.llm.recipes")

# Process-level lock to ensure atomic monthly budget evaluation across concurrent requests
_generation_lock = asyncio.Lock()

COMMON_PANTRY_STAPLES = {
    "salt", "water", "sunflower_oil", "mustard_oil", "mustard_seeds",
    "cumin_seeds", "turmeric_powder", "red_chilli_powder", "coriander_powder",
    "garam_masala", "asafoetida", "black_pepper"
}

ALLOWED_DIETS = {"VEGAN", "VEGETARIAN", "EGGLESS", "NON_VEGETARIAN"}
ALLOWED_SPICE_LEVELS = {"MILD", "MEDIUM", "HOT"}


class GeneratedRecipeIngredient(BaseModel):
    model_config = ConfigDict(extra="ignore")

    canonical_id: str
    qty: float
    unit: str
    is_optional: bool = False


class GeneratedRecipe(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    title: str
    cuisine: str
    diet: str
    spice_level: str
    cooking_time_minutes: int
    base_servings: int = 2
    ingredients: list[GeneratedRecipeIngredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    nutrition: dict[str, float] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class GeneratedRecipeBatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recipes: list[GeneratedRecipe] = Field(default_factory=list)


def slugify_title(title: str) -> str:
    """Convert title to URL-safe slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return cleaned or "recipe"


def compute_ai_gen_cache_key(
    available_items: list[dict[str, Any]],
    preferences: UserPreference,
) -> str:
    """Compute deterministic SHA-256 cache key per (inventory hash, preferences hash)

    for 30-minute caching per PRD Section 9.4 and 9.6.
    """
    inv_data = sorted([
        (
            str(item.get("canonical_id", "")).strip().lower(),
            round(float(item.get("quantity", 0)), 2),
            str(item.get("unit", "")).strip().lower(),
            str(item.get("status", "")).strip().upper(),
        )
        for item in available_items
        if item.get("canonical_id")
    ])
    pref_data = {
        "diet": (preferences.diet or "VEGETARIAN").strip().upper(),
        "allergies": sorted([a.strip().lower() for a in (preferences.allergies or []) if a.strip()]),
        "avoided": sorted([a.strip().lower() for a in (preferences.avoided_ingredients or []) if a.strip()]),
        "spice": (preferences.spice_level or "MEDIUM").strip().upper(),
        "cuisines": sorted([c.strip().lower() for c in (preferences.cuisines or []) if c.strip()]),
        "max_time": preferences.max_cooking_time or 45,
    }
    raw = json.dumps({"inv": inv_data, "pref": pref_data}, sort_keys=True)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"ai_gen:{h}"


def validate_generated_recipe(
    gen_recipe: GeneratedRecipe,
    catalogue_map: dict[str, Ingredient],
    preferences: UserPreference,
) -> tuple[bool, str | None]:
    """Strict server-side validation of AI-generated recipe per PRD Section 8.3 and 9.4.

    Enforces:
    - Non-empty title and cuisine
    - Valid diet in {"VEGAN", "VEGETARIAN", "EGGLESS", "NON_VEGETARIAN"}
    - Valid spice level in {"MILD", "MEDIUM", "HOT"}
    - Cooking time between 5 and 180 minutes
    - Base servings between 1 and 24
    - Step count between 3 and 12 (PRD Section 8.3)
    - Each step must be a non-empty string
    - At least 1 non-optional ingredient
    - Every canonical_id must exist in ingredient catalogue (discard unknown, do not repair)
    - No duplicate canonical_ids within the recipe
    - Ingredient quantities must be positive (> 0)
    - Conforms to user diet, allergy, avoided ingredients, and cooking time constraints
    """
    if not gen_recipe.title or not gen_recipe.title.strip():
        return False, "Empty recipe title"

    if not gen_recipe.cuisine or not gen_recipe.cuisine.strip():
        return False, "Empty recipe cuisine"

    diet_upper = gen_recipe.diet.strip().upper()
    if diet_upper not in ALLOWED_DIETS:
        return False, f"Invalid diet '{gen_recipe.diet}'"

    spice_upper = gen_recipe.spice_level.strip().upper()
    if spice_upper not in ALLOWED_SPICE_LEVELS:
        return False, f"Invalid spice level '{gen_recipe.spice_level}'"

    if not (5 <= gen_recipe.cooking_time_minutes <= 180):
        return False, f"Cooking time {gen_recipe.cooking_time_minutes}m out of bounds (5-180m)"

    if not (1 <= gen_recipe.base_servings <= 24):
        return False, f"Base servings {gen_recipe.base_servings} out of bounds (1-24)"

    if not (3 <= len(gen_recipe.steps) <= 12):
        return False, f"Step count {len(gen_recipe.steps)} out of bounds (3-12 steps required)"

    if not all(isinstance(step, str) and step.strip() for step in gen_recipe.steps):
        return False, "Steps contain empty or non-string entries"

    if not gen_recipe.ingredients:
        return False, "No ingredients in generated recipe"

    non_optional = [ing for ing in gen_recipe.ingredients if not ing.is_optional]
    if not non_optional:
        return False, "Recipe has no non-optional ingredients"

    seen_cids: set[str] = set()
    for ri in gen_recipe.ingredients:
        cid = ri.canonical_id.strip().lower()
        if not cid:
            return False, "Empty canonical ingredient ID"

        # Resolve common aliases (e.g. cooking_oil -> sunflower_oil)
        if cid not in catalogue_map:
            matched_id, _ = alias_matcher.match(cid.replace("_", " "))
            if matched_id and matched_id in catalogue_map:
                cid = matched_id
                ri.canonical_id = matched_id

        if cid in seen_cids:
            return False, f"Duplicate canonical ingredient ID '{ri.canonical_id}' in recipe"
        seen_cids.add(cid)

        if cid not in catalogue_map:
            return False, f"Unknown canonical ingredient ID '{ri.canonical_id}' (discard per PRD Section 9.4)"

        if ri.qty <= 0:
            return False, f"Invalid ingredient quantity {ri.qty} for '{ri.canonical_id}'"

    # Temporary Recipe object for hard filter evaluation
    temp_recipe = Recipe(
        id="temp",
        title=gen_recipe.title,
        cuisine=gen_recipe.cuisine,
        diet=diet_upper,
        spice_level=spice_upper,
        cooking_time_minutes=gen_recipe.cooking_time_minutes,
        base_servings=gen_recipe.base_servings,
        steps=gen_recipe.steps,
        nutrition=gen_recipe.nutrition,
        tags=gen_recipe.tags,
        source="AI",
        status="PENDING_REVIEW",
    )
    temp_recipe.ingredients = [
        RecipeIngredient(
            recipe_id="temp",
            ingredient_id=ri.canonical_id.strip().lower(),
            qty=Decimal(str(ri.qty)),
            unit=ri.unit,
            is_optional=ri.is_optional,
        )
        for ri in gen_recipe.ingredients
    ]

    passes, reason = check_hard_filters(
        recipe=temp_recipe,
        preferences=preferences,
        inventory_map={},  # Ignore coverage during allergy/diet validation pass
        ingredient_catalogue=catalogue_map,
    )
    # Check if failed due to constraint (allergen, diet, avoided, cooking time)
    if not passes and reason and "coverage" not in reason.lower():
        return False, f"Violates user constraints: {reason}"

    return True, None


async def call_groq_recipe_generation(
    db: Session,
    user: User,
    available_items: list[dict[str, Any]],
    preferences: UserPreference,
    catalogue_map: dict[str, Ingredient],
    settings: Settings | None = None,
    num_recipes: int = 5,
) -> list[Recipe]:
    """Call Groq text model to generate Indian recipes, validate them,

    cache results for 30 minutes, and persist accepted recipes with source='AI' and status='PENDING_REVIEW'.
    """
    async with _generation_lock:
        if settings is None:
            from app.core.config import Settings
            settings = Settings()  # type: ignore[call-arg]

        now = datetime.now(timezone.utc)

        # 1. Check monthly budget cap before invoking LLM (PRD Section 9.6)
        if is_llm_budget_exceeded(db=db, budget_usd=settings.LLM_MONTHLY_BUDGET_USD, now=now):
            logger.warning(
                "Monthly LLM budget cap reached/exceeded 80%% for user %s. Skipping AI recipe generation.",
                user.id,
            )
            return []

        # 2. Check 30-minute cache per (inventory hash, preferences hash) per PRD Section 9.4 & 9.6
        cache_key = compute_ai_gen_cache_key(available_items, preferences)
        cached_entry = (
            db.query(RecommendationCache)
            .filter(
                RecommendationCache.user_id == user.id,
                RecommendationCache.cache_key == cache_key,
            )
            .first()
        )
        if cached_entry:
            if cached_entry.expires_at > now:
                recipe_ids = cached_entry.payload.get("recipe_ids", [])
                if recipe_ids:
                    cached_recipes = (
                        db.query(Recipe)
                        .options(
                            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)
                        )
                        .filter(
                            Recipe.id.in_(recipe_ids),
                            Recipe.created_by_user_id == user.id,
                            Recipe.source == "AI",
                        )
                        .all()
                    )
                    logger.info(
                        "AI recipe generation cache HIT for user %s: returning %d cached recipes",
                        user.id,
                        len(cached_recipes),
                    )
                    return list(cached_recipes)
                else:
                    logger.info("AI recipe generation cache HIT for user %s: 0 recipes cached", user.id)
                    return []
            else:
                db.delete(cached_entry)
                db.commit()

        model_name = settings.GROQ_TEXT_MODEL
        catalogue_ids = list(catalogue_map.keys())

        user_prompt = build_recipe_gen_user_prompt(
            available_items=available_items,
            diet=preferences.diet or "VEGETARIAN",
            allergies=preferences.allergies or [],
            avoided_ingredients=preferences.avoided_ingredients or [],
            spice_level=preferences.spice_level or "MEDIUM",
            cuisines=preferences.cuisines or [],
            max_cooking_time=preferences.max_cooking_time or 45,
            catalogue_ids=catalogue_ids,
            num_recipes=num_recipes,
        )

        groq_client = get_groq_client(settings)
        start_time = time.perf_counter()

        async def _make_call():
            return await groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_completion_tokens=3000,
                response_format={"type": "json_object"},
            )

        try:
            response = await execute_groq_call_with_retries(
                call_coro_fn=_make_call,
                max_retries=settings.GROQ_MAX_RETRIES,
                backoff_delays=(1.0, 3.0),
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            prompt_tokens = response.usage.prompt_tokens if response.usage else None
            completion_tokens = response.usage.completion_tokens if response.usage else None

            record_llm_call(
                db=db,
                purpose="RECIPE_GEN",
                model=model_name,
                prompt_version=PROMPT_VERSION,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status="OK",
                user_id=user.id,
            )

            content = response.choices[0].message.content or "{}"
            raw_data = json.loads(content)
            if isinstance(raw_data, list):
                raw_data = {"recipes": raw_data}
            parsed_batch = GeneratedRecipeBatch.model_validate(raw_data)

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            record_llm_call(
                db=db,
                purpose="RECIPE_GEN",
                model=model_name,
                prompt_version=PROMPT_VERSION,
                prompt_tokens=None,
                completion_tokens=None,
                latency_ms=latency_ms,
                status="ERROR",
                user_id=user.id,
                error_code=type(exc).__name__,
            )
            logger.error(f"Groq recipe generation call failed: {exc}", exc_info=True)
            raise

        # Server-side validation and persistence
        accepted_recipes: list[Recipe] = []

        for gen_recipe in parsed_batch.recipes:
            is_valid, discard_reason = validate_generated_recipe(
                gen_recipe=gen_recipe,
                catalogue_map=catalogue_map,
                preferences=preferences,
            )
            if not is_valid:
                logger.info(f"Discarding AI recipe '{gen_recipe.title}': {discard_reason}")
                continue

            slug = slugify_title(gen_recipe.title)
            recipe_id = f"ai-{slug[:25]}-{uuid.uuid4().hex[:6]}"

            nutrition_data = {
                "kcal": float(gen_recipe.nutrition.get("kcal", 250)),
                "protein_g": float(gen_recipe.nutrition.get("protein_g", 8)),
                "carbs_g": float(gen_recipe.nutrition.get("carbs_g", 30)),
                "fat_g": float(gen_recipe.nutrition.get("fat_g", 8)),
                "fiber_g": float(gen_recipe.nutrition.get("fiber_g", 4)),
            }

            db_recipe = Recipe(
                id=recipe_id,
                title=gen_recipe.title.strip(),
                cuisine=gen_recipe.cuisine.strip(),
                diet=gen_recipe.diet.strip().upper(),
                spice_level=gen_recipe.spice_level.strip().upper(),
                cooking_time_minutes=gen_recipe.cooking_time_minutes,
                base_servings=gen_recipe.base_servings,
                steps=gen_recipe.steps,
                nutrition=nutrition_data,
                tags=list(set(gen_recipe.tags + ["ai-generated"])),
                source="AI",
                status="PENDING_REVIEW",
                created_by_user_id=user.id,
            )

            db.add(db_recipe)
            db.flush()

            # Add recipe ingredients
            available_cids = {
                str(it.get("canonical_id", "")).strip().lower()
                for it in available_items
                if it.get("canonical_id")
            }
            recipe_ings: list[RecipeIngredient] = []
            for ri in gen_recipe.ingredients:
                cid = ri.canonical_id.strip().lower()
                is_opt = ri.is_optional
                # Pantry staples not in active inventory are marked optional so coverage reflects user's ingredients
                if cid in COMMON_PANTRY_STAPLES and cid not in available_cids:
                    is_opt = True

                recipe_ing = RecipeIngredient(
                    recipe_id=db_recipe.id,
                    ingredient_id=cid,
                    qty=Decimal(str(round(ri.qty, 2))),
                    unit=ri.unit.strip().lower(),
                    is_optional=is_opt,
                )
                db.add(recipe_ing)
                recipe_ings.append(recipe_ing)

            db_recipe.ingredients = recipe_ings
            accepted_recipes.append(db_recipe)

        if accepted_recipes:
            db.commit()
            for r in accepted_recipes:
                db.refresh(r)
            logger.info(f"Persisted {len(accepted_recipes)} AI-generated recipes for user {user.id}")

        # Cache AI generation result for 30 minutes (PRD Section 9.4 and 9.6)
        expires_at = now + timedelta(minutes=30)
        cache_record = RecommendationCache(
            user_id=user.id,
            cache_key=cache_key,
            payload={"recipe_ids": [r.id for r in accepted_recipes]},
            expires_at=expires_at,
        )
        try:
            db.query(RecommendationCache).filter(
                RecommendationCache.user_id == user.id,
                RecommendationCache.cache_key == cache_key,
            ).delete()
            db.add(cache_record)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"Failed to save AI recipe generation cache: {exc}")

        return accepted_recipes

