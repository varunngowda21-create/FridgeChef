import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import RecipeNotFoundError
from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient
from app.db.session import get_db
from app.schemas.catalogue import (
    IngredientListResponse,
    IngredientOut,
    NutritionEstimate,
    RecipeIngredientOut,
    RecipeOut,
    ShelfLifeItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Catalogue"])


@router.get(
    "/ingredients",
    response_model=IngredientListResponse,
    summary="List and search canonical ingredients",
    description="Returns canonical ingredients with shelf-life data. Supports search and category filter.",
)
def list_ingredients(
    query: str | None = Query(None, description="Search term for display name or aliases"),
    category: str | None = Query(None, description="Category filter (e.g. Vegetables, Dairy and Eggs)"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (max 100)"),
    cursor: str | None = Query(None, description="Pagination cursor (last ingredient ID)"),
    db: Session = Depends(get_db),
) -> IngredientListResponse:
    stmt = (
        select(Ingredient)
        .options(selectinload(Ingredient.shelf_lives))
        .order_by(Ingredient.id.asc())
    )

    if cursor:
        stmt = stmt.where(Ingredient.id > cursor)

    if category:
        stmt = stmt.where(Ingredient.category.ilike(category.strip()))

    if query:
        q = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Ingredient.id.ilike(q),
                Ingredient.display_name.ilike(q),
                # Note: aliases is JSONB array; checking cast to text allows fast matching
                Ingredient.aliases.cast(Ingredient.display_name.type).ilike(q),
            )
        )

    # Fetch limit + 1 to determine if next page exists
    results = db.scalars(stmt.limit(limit + 1)).all()

    items = []
    has_more = len(results) > limit
    page_results = results[:limit]

    for ing in page_results:
        sl_items = [
            ShelfLifeItem(
                storage=sl.storage,
                days=sl.days,
                opened_days=sl.opened_days,
            )
            for sl in ing.shelf_lives
        ]
        items.append(
            IngredientOut(
                id=ing.id,
                display_name=ing.display_name,
                category=ing.category,
                aliases=ing.aliases,
                default_unit=ing.default_unit,
                grams_per_piece=float(ing.grams_per_piece) if ing.grams_per_piece is not None else None,
                ml_per_piece=float(ing.ml_per_piece) if ing.ml_per_piece is not None else None,
                price_inr_per_kg=float(ing.price_inr_per_kg),
                allergen_group=ing.allergen_group,
                shelf_life=sl_items,
            )
        )

    next_cursor = page_results[-1].id if has_more and page_results else None
    return IngredientListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/recipes/{id}",
    response_model=RecipeOut,
    summary="Get recipe by ID with dynamic servings scaling",
    description="Retrieves a curated recipe. If servings is provided, ingredient quantities scale linearly.",
)
def get_recipe(
    id: str,
    servings: int | None = Query(None, ge=1, le=24, description="Target servings to scale quantities"),
    db: Session = Depends(get_db),
) -> RecipeOut:
    stmt = (
        select(Recipe)
        .options(
            joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient)
        )
        .where(Recipe.id == id)
    )
    recipe = db.scalars(stmt).first()

    if not recipe:
        raise RecipeNotFoundError(f"Recipe '{id}' not found.")

    target_servings = servings if servings is not None else recipe.base_servings
    scale_factor = target_servings / float(recipe.base_servings)

    recipe_ingredients = []
    for ri in recipe.ingredients:
        scaled_qty = round(float(ri.qty) * scale_factor, 2)
        display_name = ri.ingredient.display_name if ri.ingredient else ri.ingredient_id
        recipe_ingredients.append(
            RecipeIngredientOut(
                canonical_id=ri.ingredient_id,
                display_name=display_name,
                qty=scaled_qty,
                unit=ri.unit,
                is_optional=ri.is_optional,
            )
        )

    nut = recipe.nutrition or {}
    nutrition = NutritionEstimate(
        kcal=float(nut.get("kcal", 0)),
        protein_g=float(nut.get("protein_g", 0)),
        carbs_g=float(nut.get("carbs_g", 0)),
        fat_g=float(nut.get("fat_g", 0)),
        fiber_g=float(nut.get("fiber_g", 0)),
    )

    return RecipeOut(
        id=recipe.id,
        title=recipe.title,
        cuisine=recipe.cuisine,
        diet=recipe.diet,
        spice_level=recipe.spice_level,
        cooking_time_minutes=recipe.cooking_time_minutes,
        base_servings=recipe.base_servings,
        scaled_servings=target_servings,
        nutrition_per_serving=nutrition,
        ingredients=recipe_ingredients,
        steps=recipe.steps,
        tags=recipe.tags,
        source=recipe.source,
    )
