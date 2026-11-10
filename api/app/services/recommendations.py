"""Recipe recommendation service with 30-minute caching per PRD Section 6.5, 8.2, 11.6, and FR-046."""

import hashlib
import json
import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.ratelimit import recommendation_rate_limiter
from app.db.models.analytics import RecommendationCache
from app.db.models.auth import User, UserPreference
from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient
from app.db.models.inventory import InventoryItem
from app.llm.budget import is_llm_budget_exceeded
from app.llm.recipe_gen import call_groq_recipe_generation
from app.schemas.recommendations import (
    RecommendationItem,
    RecommendationResponse,
)
from app.services.freshness import FreshnessResult, FreshnessStatus, get_freshness_for_item
from app.services.scoring import (
    InventoryItemSummary,
    rank_recipes,
)

logger = logging.getLogger("fridgechef.recommendations")

CACHE_TTL_MINUTES = 30


def invalidate_recommendation_cache(db: Session, user_id: uuid.UUID) -> int:
    """Invalidate cached recommendations for a user.

    Ensures that any inventory or preference mutation immediately clears stale recommendations.
    Preserves 30-minute AI recipe generation cache keys ('ai_gen:...') so that temporary
    recipe results remain cached per (inventory, preferences) per PRD Section 9.4 and 9.6.
    """
    deleted_count = (
        db.query(RecommendationCache)
        .filter(
            RecommendationCache.user_id == user_id,
            ~RecommendationCache.cache_key.startswith("ai_gen:"),
        )
        .delete(synchronize_session=False)
    )
    return deleted_count


def compute_cache_key(
    inventory_items: list[InventoryItem],
    preferences_version: int,
    diet: str,
    max_cooking_time: int,
    household_size: int,
    target_servings: int,
    limit: int,
) -> str:
    """Compute deterministic SHA-256 hash key representing inventory snapshot and preference version."""
    inv_snapshot = [
        (
            item.ingredient_id,
            str(item.quantity),
            item.unit.strip().lower(),
            item.storage.strip().upper(),
            str(item.expires_on),
        )
        for item in inventory_items
        if item.archived_at is None and item.quantity > 0
    ]
    inv_snapshot.sort()

    key_payload = {
        "inv": inv_snapshot,
        "pref_v": preferences_version,
        "diet": diet,
        "max_time": max_cooking_time,
        "hh_size": household_size,
        "servings": target_servings,
        "limit": limit,
    }
    encoded = json.dumps(key_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_inventory_summary(
    db: Session,
    inventory_items: list[InventoryItem],
    today: date | None = None,
) -> dict[str, InventoryItemSummary]:
    """Aggregate active inventory items by canonical ID and compute current freshness."""
    if today is None:
        today = date.today()

    by_ingredient: dict[str, list[tuple[InventoryItem, FreshnessResult]]] = defaultdict(list)
    for item in inventory_items:
        if not item.ingredient_id or item.quantity <= 0 or item.archived_at is not None:
            continue
        try:
            freshness = get_freshness_for_item(
                db=db,
                ingredient_id=item.ingredient_id,
                storage=item.storage,
                added_on=item.added_on,
                opened_on=item.opened_on,
                today=today,
            )
            by_ingredient[item.ingredient_id].append((item, freshness))
        except Exception as exc:
            logger.warning(f"Failed to calculate freshness for item {item.id}: {exc}")

    summary_map: dict[str, InventoryItemSummary] = {}
    for ing_id, items in by_ingredient.items():
        total_qty = sum(it.quantity for it, _ in items)
        min_days = min(fr.days_left for _, fr in items)
        primary_item, _ = min(items, key=lambda x: x[1].days_left)

        if min_days <= 1:
            status = FreshnessStatus.USE_FIRST
        elif min_days <= 3:
            status = FreshnessStatus.USE_SOON
        else:
            status = FreshnessStatus.SAFE

        summary_map[ing_id] = InventoryItemSummary(
            canonical_id=ing_id,
            display_name=primary_item.display_name,
            total_quantity=Decimal(str(total_qty)),
            unit=primary_item.unit,
            min_days_left=min_days,
            status=status,
        )

    return summary_map


async def get_recommendations(
    db: Session,
    user: User,
    limit: int = 5,
    servings: int | None = None,
    settings: Settings | None = None,
    active_items: list[InventoryItem] | None = None,
) -> RecommendationResponse:
    """Retrieve top-ranked recipe recommendations with deterministic scoring, 30m caching,

    and AI recipe generation fallback when fewer than 5 curated recipes match at >= 40%.
    """
    if settings is None:
        settings = get_settings()

    # 1. Enforce rate limit (60 requests per hour per user)
    recommendation_rate_limiter.check_and_record(str(user.id))

    # 2. Fetch user preferences
    pref = user.preferences
    if not pref:
        pref = (
            db.query(UserPreference)
            .filter(UserPreference.user_id == user.id)
            .first()
        )
    if not pref:
        # Default preferences if user has not yet set any
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

    target_servings = servings if servings is not None else pref.household_size
    if target_servings <= 0:
        target_servings = pref.household_size or 2

    # 3. Fetch active inventory items
    if active_items is None:
        active_items = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.user_id == user.id,
                InventoryItem.archived_at.is_(None),
                InventoryItem.quantity > 0,
            )
            .all()
        )

    # 4. Check cache
    cache_key = compute_cache_key(
        inventory_items=active_items,
        preferences_version=pref.version,
        diet=pref.diet,
        max_cooking_time=pref.max_cooking_time,
        household_size=pref.household_size,
        target_servings=target_servings,
        limit=limit,
    )

    now = datetime.now(timezone.utc)
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
            logger.info(f"Recommendation cache HIT for user {user.id}")
            payload = dict(cached_entry.payload)
            payload["cache"] = "HIT"
            return RecommendationResponse.model_validate(payload)
        else:
            # Stale entry expired
            db.delete(cached_entry)
            db.commit()

    logger.info(f"Recommendation cache MISS for user {user.id}")

    # 5. Build inventory summary and load catalogue
    inventory_map = build_inventory_summary(db=db, inventory_items=active_items)

    all_ingredients = db.query(Ingredient).all()
    ingredient_catalogue = {ing.id: ing for ing in all_ingredients}

    # Load approved recipes AND any user-created AI recipes
    stmt = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)
        )
        .where(
            or_(
                Recipe.status == "APPROVED",
                and_(
                    Recipe.source == "AI",
                    Recipe.created_by_user_id == user.id,
                ),
            )
        )
    )
    recipes: list[Recipe] = list(db.scalars(stmt).all())

    # 6. Evaluate curated match count against trigger threshold (< 5 curated recipes matching >= 40%)
    curated_recipes = [r for r in recipes if r.source == "CURATED"]
    curated_ranked = rank_recipes(
        recipes=curated_recipes,
        preferences=pref,
        inventory_map=inventory_map,
        ingredient_catalogue=ingredient_catalogue,
        target_servings=target_servings,
        limit=5,
    )
    curated_match_count = sum(1 for r in curated_ranked if r.coverage >= 0.40)

    degraded = False

    # Trigger AI fallback if curated matches < 5 and user has active inventory items (PRD Section 6.5 FR-041, Section 9.4)
    if curated_match_count < 5 and len(inventory_map) > 0:
        # Check monthly budget cap (PRD Section 9.6)
        if is_llm_budget_exceeded(db=db, budget_usd=settings.LLM_MONTHLY_BUDGET_USD):
            logger.warning(
                f"User {user.id} has only {curated_match_count} curated matches, "
                "but monthly LLM budget cap has reached or exceeded 80%. Serving curated recipes only."
            )
        else:
            available_items = [
                {
                    "canonical_id": k,
                    "display_name": v.display_name,
                    "quantity": float(v.total_quantity),
                    "unit": v.unit,
                    "status": v.status.value,
                }
                for k, v in inventory_map.items()
            ]
            try:
                ai_recipes = await call_groq_recipe_generation(
                    db=db,
                    user=user,
                    available_items=available_items,
                    preferences=pref,
                    catalogue_map=ingredient_catalogue,
                    settings=settings,
                    num_recipes=5 - curated_match_count,
                )
                if ai_recipes:
                    recipes.extend(ai_recipes)
            except Exception as exc:
                logger.warning(f"AI recipe generation call failed (falling back to curated only per NFR-011): {exc}")
                degraded = True

    # 7. Rank combined candidate pool deterministically
    ranked = rank_recipes(
        recipes=recipes,
        preferences=pref,
        inventory_map=inventory_map,
        ingredient_catalogue=ingredient_catalogue,
        target_servings=target_servings,
        limit=limit,
    )

    # 8. Build response items
    items: list[RecommendationItem] = []
    for sc in ranked:
        items.append(
            RecommendationItem(
                recipe_id=sc.recipe.id,
                title=sc.recipe.title,
                cuisine=sc.recipe.cuisine,
                cooking_time_minutes=sc.recipe.cooking_time_minutes,
                servings=sc.servings,
                match_percent=sc.match_percent,
                source=sc.recipe.source,
                uses_expiring=sc.uses_expiring,
                missing=sc.missing,
                missing_cost_inr=sc.missing_cost_inr,
                reason=sc.reason,
            )
        )

    response = RecommendationResponse(
        degraded=degraded,
        generated_at=now,
        cache="MISS",
        items=items,
    )

    # 9. Persist into recommendation_cache with 30m TTL
    expires_at = now + timedelta(minutes=CACHE_TTL_MINUTES)
    cache_record = RecommendationCache(
        user_id=user.id,
        cache_key=cache_key,
        payload=response.model_dump(mode="json"),
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
        logger.warning(f"Failed to save recommendation cache: {exc}")

    return response

